"""chantier_pivot_corr_tighten_2026-08-23.py

Suite a chantier_pivot_carryunwind_16j_2026-08-23.py (risque_casse_PIVOT
11,00%->0,50% pour le choc carry-unwind force a 16j/1000$, mecanisme :
1er bloc B typique souvent domine par le cluster metaux correles
[or/argent/platine/palladium, corr 0,52-0,94] alors que le choc carry-unwind
est un mix equilibre 53% metaux/47% forex, accidentellement plus diversifie).

Question posee par l'utilisateur : un plafond d'exposition correlee
EXPLICITE pendant la phase pivot seule (7-10j reels avant qu'un 2e groupe
ouvre, cf. chantier_coldstart_pivot_carryunwind_2026-08-23.py) reproduirait-
il, sur un demarrage ALEATOIRE, une partie du gain observe par accident sur
carry-unwind ?

Mecanisme teste : resserrement TEMPORAIRE du seuil d'exclusion correlee
(CORR_TH_NEW=0,80, precompute_correlation_pairs dans monte_carlo_
simulation.py, applique dans process_trade_mf ligne 326 -- bloque
l'ouverture d'un nouveau trade si un ticker deja ouvert sur le MEME COMPTE
est correle au-dessus du seuil) a 0,50 et 0,60, UNIQUEMENT pour le compte
Blueberry ET UNIQUEMENT pendant les PIVOT_WINDOW_DAYS premiers jours de
simulation (Blueberry demarre a t=0, is_day0=True -- le seuil normal 0,80
s'applique partout ailleurs, y compris sur Blueberry apres la fenetre).

Instrumentation : meme technique que chantier_pivot_carryunwind_16j_2026-
08-23.py (inspect.getsource + exec sur s18.run_one, pas de copie manuelle
des ~500 lignes) -- DEUX ajouts au lieu d'un : (1) blueberry_breaks comme
avant, (2) selection de la carte d'exclusion appliquee a process_trade_
corr_swap_rr/process_trade_mf : excluded_map_tight si gname=="Blueberry" et
now < pivot_window_seconds, sinon excluded_map (0,80) inchangee -- la
condition est evaluee au point d'appel existant, aucune autre ligne du
moteur n'est touchee.
"""
import importlib.util
import inspect
import random
import sys
import time

import numpy as np
import pandas as pd

_spec = importlib.util.spec_from_file_location("pdb", "point_d_bloc1_bloc2_2026-08-22.py")
pdb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pdb)
bsl = pdb.bsl
s18 = pdb.s18
abm = pdb.abm
ei = pdb.ei

from monte_carlo_simulation import precompute_correlation_pairs
from real_cash_risk_year1_block_bootstrap import build_blocks
from reference_metrics_final import build_full_block_bootstrap_sequence

DAY_SECONDS = 86400
BLOCK_SECONDS = 2 * 30 * DAY_SECONDS


def build_run_one_pivot_corr():
    src = inspect.getsource(s18.run_one)
    src = src.replace("def run_one(", "def run_one_pivot_corr(", 1)
    src = src.replace(
        "bb_threshold=float(\"inf\"), use_any_rr=False, apply_instant_risk_cap=False):",
        "bb_threshold=float(\"inf\"), use_any_rr=False, apply_instant_risk_cap=False,\n"
        "            excluded_map_tight=None, pivot_window_seconds=0.0):",
        1,
    )
    src = src.replace('"total_breaks": 0,', '"total_breaks": 0, "blueberry_breaks": 0,', 1)
    lines = src.split("\n")
    for i, line in enumerate(lines):
        if 'state["total_breaks"] += 1' in line:
            indent = line[:len(line) - len(line.lstrip())]
            lines[i] = line + f'\n{indent}if gname == "Blueberry":\n{indent}    state["blueberry_breaks"] += 1'
            break
    else:
        raise RuntimeError("point d'instrumentation total_breaks non trouve")
    src = "\n".join(lines)
    src = src.replace('"total_breaks": state["total_breaks"], "pre_deblocage": pre,',
                       '"total_breaks": state["total_breaks"], "blueberry_breaks": state["blueberry_breaks"], "pre_deblocage": pre,', 1)

    marker = '                if use_any_rr:\n' \
              '                    just_funded = process_trade_corr_swap_rr(acc, trade, now, fmt, state, r, market_data,\n' \
              '                                                              excluded_map, split_flat=split_this,\n' \
              '                                                              reserve_share=reserve_share, cost_override=0.0)\n' \
              '                else:\n' \
              '                    just_funded = process_trade_mf(acc, trade, now, fmt, state, r, market_data, excluded_map,\n' \
              '                                                    split_flat=split_this, reserve_share=reserve_share,\n' \
              '                                                    cost_override=0.0)'
    assert marker in src, "point d'instrumentation excluded_map (dispatch any-RR) non trouve"
    replacement = '                em = (excluded_map_tight if (excluded_map_tight is not None and gname == "Blueberry"\n' \
                  '                      and now < pivot_window_seconds) else excluded_map)\n' \
                  '                if use_any_rr:\n' \
                  '                    just_funded = process_trade_corr_swap_rr(acc, trade, now, fmt, state, r, market_data,\n' \
                  '                                                              em, split_flat=split_this,\n' \
                  '                                                              reserve_share=reserve_share, cost_override=0.0)\n' \
                  '                else:\n' \
                  '                    just_funded = process_trade_mf(acc, trade, now, fmt, state, r, market_data, em,\n' \
                  '                                                    split_flat=split_this, reserve_share=reserve_share,\n' \
                  '                                                    cost_override=0.0)'
    src = src.replace(marker, replacement, 1)

    ns = dict(s18.run_one.__globals__)
    code = compile(src, "<run_one_pivot_corr_instrumented>", "exec")
    exec(code, ns)
    return ns["run_one_pivot_corr"]


run_one_pivot_corr = build_run_one_pivot_corr()


def run_propagated_truncated(pop, market_data, excluded_map, ceiling, seq_grouped, format_by_firm, emergency,
                              eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult, n_sims, seed,
                              alpha_post, beta_post, target_duration_days, excluded_map_tight, pivot_window_days,
                              **kw):
    rng_wr = random.Random(seed)
    rng_boot = random.Random(seed + 1)
    target_duration = target_duration_days * DAY_SECONDS
    pivot_window_seconds = pivot_window_days * DAY_SECONDS

    rows = []
    for _ in range(n_sims):
        wr_draw = rng_wr.betavariate(alpha_post, beta_post)
        trades, slot_arrivals = s18.build_flexible_population_with_rr(pop, wr_draw, 1.0, False, random.Random(rng_boot.random()))
        blocks = build_blocks(trades, slot_arrivals, BLOCK_SECONDS)
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, BLOCK_SECONDS, rng_boot, target_duration)
        keep = [i for i, s in enumerate(raw_slots) if s < target_duration]
        raw_trades = [raw_trades[i] for i in keep]
        raw_slots = [raw_slots[i] for i in keep]

        order = list(range(len(raw_trades)))
        res = run_one_pivot_corr(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, seq_grouped,
                                  format_by_firm, emergency, eval_risk, fleet_risk, gft_eval_risk, reserve_share,
                                  extra_threshold_mult, excluded_map_tight=excluded_map_tight,
                                  pivot_window_seconds=pivot_window_seconds, **kw)
        rows.append(res)
    return pd.DataFrame(rows)


def run_config(pop, market_data, excluded_map, alpha_post, beta_post, ceiling, n_sims, seed, target_duration_days,
               excluded_map_tight, pivot_window_days, label):
    common_kwargs = dict(emergency=ei.DEFAULT_EMERGENCY, eval_risk=abm.EVAL_RISK, fleet_risk=abm.FLEET_RISK,
                          gft_eval_risk=abm.GFT_EVAL_RISK, reserve_share=ei.FINAL_RESERVE_SHARE,
                          extra_threshold_mult=ei.EXTRA_THRESHOLD_MULT, n_sims=n_sims, seed=seed,
                          b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True,
                          ftmo_discount=True, gft_goat_guard=True, payout_cycle=True)
    bb_th = abm.BB_THRESHOLD_BY_CEILING[ceiling]
    t0 = time.time()
    df = run_propagated_truncated(pop, market_data, excluded_map, ceiling,
                                   ei.seq_grouped_multi(1000, 15000, 25000, 25000), ei.CONFIG_REF,
                                   bb_threshold=bb_th, use_any_rr=True, apply_instant_risk_cap=True,
                                   alpha_post=alpha_post, beta_post=beta_post,
                                   target_duration_days=target_duration_days,
                                   excluded_map_tight=excluded_map_tight, pivot_window_days=pivot_window_days,
                                   **common_kwargs)
    dt = time.time() - t0
    pivot_break_rate = (df["blueberry_breaks"] > 0).mean() * 100
    other_group_opened = (df["total_opens"] > 1).mean() * 100
    profit_med = df["final_net_split"].median()
    profit_mean = df["final_net_split"].mean()
    print(f"[{label} dur={target_duration_days}j c={ceiling:.0f}$ pivot_window={pivot_window_days}j] "
          f"risque_casse_PIVOT={pivot_break_rate:.2f}% autre_groupe_ouvert={other_group_opened:.2f}% "
          f"profit_median={profit_med:.2f}$ profit_moyen={profit_mean:.2f}$ "
          f"n_sims={n_sims} ({dt:.0f}s)", flush=True)
    return dict(label=label, target_duration_days=target_duration_days, ceiling=ceiling, n=n_sims,
                pivot_window_days=pivot_window_days, pivot_break_rate=pivot_break_rate,
                other_group_opened_rate=other_group_opened, total_opens_moy=df["total_opens"].mean(),
                profit_median=profit_med, profit_mean=profit_mean), df


def z_test(p1, p2, n):
    p1, p2 = p1 / 100, p2 / 100
    se = np.sqrt(p1 * (1 - p1) / n + p2 * (1 - p2) / n)
    return (p2 - p1) / se if se > 0 else float("nan")


def main():
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 13579

    pop, market_data, excluded_map, alpha_post, beta_post, label = pdb.load_scenario_pgp()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    print(f"Population : {label}, n={len(pop)}", flush=True)

    # deux points testes dans la fourchette demandee (0,50-0,60), fenetre
    # pivot = 10j (borne haute observee de la phase pivot-seule reelle)
    variants = [
        ("resserre_0.60_10j", precompute_correlation_pairs(tickers, corr_matrix, 0.60), 10),
        ("resserre_0.50_10j", precompute_correlation_pairs(tickers, corr_matrix, 0.50), 10),
    ]

    all_rows = []
    target_days, ceiling = 16, 1000.0
    print(f"\n{'='*95}\nDUREE={target_days}j, CEILING={ceiling:.0f}$, demarrage ALEATOIRE (pas de choc force)\n{'='*95}", flush=True)
    row_base, _ = run_config(pop, market_data, excluded_map, alpha_post, beta_post, ceiling, n_sims, seed,
                              target_days, None, 0, "baseline_0.80")
    all_rows.append(row_base)
    for vlabel, em_tight, pw in variants:
        row_v, _ = run_config(pop, market_data, excluded_map, alpha_post, beta_post, ceiling, n_sims, seed,
                               target_days, em_tight, pw, vlabel)
        delta = row_v["pivot_break_rate"] - row_base["pivot_break_rate"]
        z = z_test(row_base["pivot_break_rate"], row_v["pivot_break_rate"], n_sims)
        profit_delta_mean = row_v["profit_mean"] - row_base["profit_mean"]
        profit_delta_pct = (profit_delta_mean / abs(row_base["profit_mean"]) * 100
                             if row_base["profit_mean"] else float("nan"))
        print(f"  -> DELTA risque casse PIVOT = {delta:+.2f}pts (z approx={z:+.2f}) "
              f"| delta profit moyen (fenetre {target_days}j) = {profit_delta_mean:+.2f}$ ({profit_delta_pct:+.2f}%)",
              flush=True)
        all_rows.append(row_v)
        pd.DataFrame(all_rows).to_csv("chantier_pivot_corr_tighten_2026-08-23.csv", index=False)

    print(f"\n{'='*95}\nSYNTHESE\n{'='*95}")
    print(pd.DataFrame(all_rows).to_string(index=False))


if __name__ == "__main__":
    main()
