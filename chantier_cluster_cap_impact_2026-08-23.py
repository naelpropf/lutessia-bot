"""chantier_cluster_cap_impact_2026-08-23.py

Point 3 de l'extension cluster (suite a chantier_cluster_budget_verification_
2026-08-23.py, point 1 : AUCUN budget de cluster modelise nulle part dans le
moteur -- seulement cap 1,5%/trade Instant individuel + exclusion binaire
|corr|>0,80). Simule l'impact d'AJOUTER un vrai plafond de cluster (perte
combinee <= CLUSTER_CAP=1,5% par cluster, pas par position) sur les 3
familles confirmees (metaux or/argent, FX Majors, indices US), sur
B_tradable_pgp (les 3 clusters presents) et A (FX Majors + indices seulement,
0% metaux).

Injection technique (meme methode que chantier_pivot_carryunwind_16j_2026-
08-23.py : inspect.getsource + exec dans une COPIE du namespace du module,
zero modification des fichiers source reels) -- 3 couches necessaires car
process_trade_corr_swap_rr (utilise quand use_any_rr=True, le cas officiel
B/A) appelle process_trade_mf par NOM resolu dans SES PROPRES __globals__
(le module reel, pas une copie) :
  1. process_trade_mf_cluster : copie de engine_multiformat.process_trade_mf
     + ajout d'un budget de risque combine par cluster (acc["_cluster_risk_
     open"], prune sur close_time>now, cap le risk_pct de la nouvelle
     position au budget cluster restant, skip le trade si budget epuise).
  2. process_trade_corr_swap_rr_cluster : copie de chantier_S1_8_regen_
     population_2026-08-19.py::process_trade_corr_swap_rr, exec'ee dans un
     namespace ou "process_trade_mf" pointe vers la version #1.
  3. run_one_cluster : copie de s18.run_one, exec'ee dans un namespace ou
     "process_trade_mf" ET "process_trade_corr_swap_rr" pointent vers les
     versions #1/#2.
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
eng = s18.eng if hasattr(s18, "eng") else None

import engine_multiformat as emf

from real_cash_risk_year1_block_bootstrap import build_blocks
from reference_metrics_final import build_full_block_bootstrap_sequence

DAY_SECONDS = 86400
BLOCK_SECONDS = 2 * 30 * DAY_SECONDS
CLUSTER_CAP = 1.5  # %, meme valeur que BB_INSTANT_RISK_CAP pour comparabilite directe

FX_MAJORS = {"EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "USD/CAD", "AUD/USD", "NZD/USD"}
INDICES_US = {"NASDAQ100 - MINI NASDAQ100 FULL0926", "NASDAQ100 INDEX", "S&P500 - MINI S&P500 FULL0926"}
METAUX = {"GOLD - AUD", "GOLD - EUR", "GOLD - GBP", "GOLD - USD", "SILVER - AUD", "SILVER - EUR", "SILVER - USD",
          "PALLADIUM", "PLATINUM"}

CLUSTER_SETS = {"metaux": METAUX, "fx_majors": FX_MAJORS, "indices_us": INDICES_US}


def cluster_of(ticker):
    for cname, cset in CLUSTER_SETS.items():
        if ticker in cset:
            return cname
    return None


def build_process_trade_mf_cluster(active_clusters):
    src = inspect.getsource(emf.process_trade_mf)
    src = src.replace("def process_trade_mf(", "def process_trade_mf_cluster(", 1)
    marker = 'eff_risk, _ = eng.feasible_risk_pct('
    assert marker in src, "point d'injection introuvable dans process_trade_mf"
    inject = (
        '    _cl = CLUSTER_OF.get(trade["ticker"])\n'
        '    if _cl is not None and _cl in ACTIVE_CLUSTERS:\n'
        '        _open = acc.setdefault("_cluster_risk_open", {})\n'
        '        _open[_cl] = [(c, rp) for (c, rp) in _open.get(_cl, []) if c > now]\n'
        '        _committed = sum(rp for c, rp in _open[_cl])\n'
        '        _remaining = max(0.0, CLUSTER_CAP - _committed)\n'
        '        risk_pct = min(risk_pct, _remaining)\n'
        '        if risk_pct <= 0:\n'
        '            return False\n'
        '        _open[_cl].append((close_time, risk_pct))\n'
        '    ' + marker
    )
    src = src.replace('    ' + marker, inject, 1)
    ns = dict(emf.process_trade_mf.__globals__)
    ns["CLUSTER_OF"] = {t: cluster_of(t) for cset in CLUSTER_SETS.values() for t in cset}
    ns["CLUSTER_CAP"] = CLUSTER_CAP
    ns["ACTIVE_CLUSTERS"] = active_clusters
    code = compile(src, "<process_trade_mf_cluster>", "exec")
    exec(code, ns)
    return ns["process_trade_mf_cluster"], ns


def build_process_trade_corr_swap_rr_cluster(process_trade_mf_cluster_fn):
    src = inspect.getsource(s18.process_trade_corr_swap_rr)
    src = src.replace("def process_trade_corr_swap_rr(", "def process_trade_corr_swap_rr_cluster(", 1)
    ns = dict(s18.process_trade_corr_swap_rr.__globals__)
    ns["process_trade_mf"] = process_trade_mf_cluster_fn
    code = compile(src, "<process_trade_corr_swap_rr_cluster>", "exec")
    exec(code, ns)
    return ns["process_trade_corr_swap_rr_cluster"]


def build_run_one_cluster(active_clusters):
    process_trade_mf_cluster_fn, _ = build_process_trade_mf_cluster(active_clusters)
    process_trade_corr_swap_rr_cluster_fn = build_process_trade_corr_swap_rr_cluster(process_trade_mf_cluster_fn)

    src = inspect.getsource(s18.run_one)
    src = src.replace("def run_one(", "def run_one_cluster(", 1)
    code = compile(src, "<run_one_cluster>", "exec")
    ns = dict(s18.run_one.__globals__)
    ns["process_trade_mf"] = process_trade_mf_cluster_fn
    ns["process_trade_corr_swap_rr"] = process_trade_corr_swap_rr_cluster_fn
    exec(code, ns)
    return ns["run_one_cluster"]


def run_propagated(pop, market_data, excluded_map, ceiling, seq_grouped, format_by_firm, emergency,
                    eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult, n_sims, seed,
                    alpha_post, beta_post, run_one_fn, **kw):
    rng_wr = random.Random(seed)
    rng_boot = random.Random(seed + 1)
    rows = []
    for _ in range(n_sims):
        wr_draw = rng_wr.betavariate(alpha_post, beta_post)
        trades, slot_arrivals = s18.build_flexible_population_with_rr(pop, wr_draw, 1.0, False, random.Random(rng_boot.random()))
        blocks = build_blocks(trades, slot_arrivals, BLOCK_SECONDS)
        target_duration = slot_arrivals[-1]
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, BLOCK_SECONDS, rng_boot, target_duration)
        order = list(range(len(raw_trades)))
        res = run_one_fn(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, seq_grouped, format_by_firm,
                          emergency, eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult, **kw)
        rows.append(res)
    return pd.DataFrame(rows)


def run_config(pop, market_data, excluded_map, alpha_post, beta_post, ceiling, n_sims, seed, run_one_fn, label):
    common_kwargs = dict(emergency=ei.DEFAULT_EMERGENCY, eval_risk=abm.EVAL_RISK, fleet_risk=abm.FLEET_RISK,
                          gft_eval_risk=abm.GFT_EVAL_RISK, reserve_share=ei.FINAL_RESERVE_SHARE,
                          extra_threshold_mult=ei.EXTRA_THRESHOLD_MULT, n_sims=n_sims, seed=seed,
                          b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True,
                          ftmo_discount=True, gft_goat_guard=True, payout_cycle=True)
    bb_th = abm.BB_THRESHOLD_BY_CEILING[ceiling]
    t0 = time.time()
    df = run_propagated(pop, market_data, excluded_map, ceiling,
                         ei.seq_grouped_multi(1000, 15000, 25000, 25000), ei.CONFIG_REF,
                         bb_threshold=bb_th, use_any_rr=True, apply_instant_risk_cap=True,
                         alpha_post=alpha_post, beta_post=beta_post, run_one_fn=run_one_fn,
                         **common_kwargs)
    row = s18.summarize(df, label, ceiling, bb_th, True)
    dt = time.time() - t0
    print(f"[{label} c={ceiling:.0f}$] profit_moy={row['profit_moyen']:+,.0f}$ "
          f"solde_neg_an4={row['solde_negatif_annee4']:.2f}% annee1<0={row['annee1_neg']:.2f}% n={n_sims} ({dt:.0f}s)", flush=True)
    return row


def main():
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 24681357

    pop_b, market_data_b, excluded_map_b, alpha_post_b, beta_post_b, _ = pdb.load_scenario_pgp()
    pop_a, market_data_a, excluded_map_a, alpha_post_a, beta_post_a, _ = bsl.load_scenario("A")

    run_one_plain = s18.run_one

    SINGLE_CLUSTERS = [("metaux", {"metaux"}), ("fx_majors", {"fx_majors"}), ("indices_us", {"indices_us"})]
    ALL_CLUSTERS = ("tous_clusters", {"metaux", "fx_majors", "indices_us"})

    all_rows = []
    for pop_name, pop, market_data, excluded_map, alpha_post, beta_post in [
        ("B_tradable_pgp", pop_b, market_data_b, excluded_map_b, alpha_post_b, beta_post_b),
        ("A", pop_a, market_data_a, excluded_map_a, alpha_post_a, beta_post_a),
    ]:
        for ceiling in [3000.0, 5000.0]:
            print(f"\n{'='*95}\n{pop_name} c={ceiling:.0f}$\n{'='*95}", flush=True)
            row_ref = run_config(pop, market_data, excluded_map, alpha_post, beta_post, ceiling, n_sims, seed,
                                  run_one_plain, f"{pop_name}_REF c={ceiling:.0f}")
            row_ref["variant"] = "REF"
            row_ref["pop"] = pop_name
            all_rows.append(row_ref)

            for cname, cset in SINGLE_CLUSTERS + [ALL_CLUSTERS]:
                run_one_fn = build_run_one_cluster(cset)
                row = run_config(pop, market_data, excluded_map, alpha_post, beta_post, ceiling, n_sims, seed,
                                  run_one_fn, f"{pop_name}_cap_{cname} c={ceiling:.0f}")
                delta_profit = (row["profit_moyen"] - row_ref["profit_moyen"]) / abs(row_ref["profit_moyen"]) * 100
                print(f"  -> impact cap {cname:14s} : delta profit={delta_profit:+.2f}%, "
                      f"delta solde_neg={row['solde_negatif_annee4']-row_ref['solde_negatif_annee4']:+.2f}pts, "
                      f"delta annee1<0={row['annee1_neg']-row_ref['annee1_neg']:+.2f}pts", flush=True)
                row["variant"] = cname
                row["pop"] = pop_name
                all_rows.append(row)
                pd.DataFrame(all_rows).to_csv("chantier_cluster_cap_impact_2026-08-23.csv", index=False)

    print(f"\n{'='*95}\nSYNTHESE\n{'='*95}")
    print(pd.DataFrame(all_rows)[["pop", "ceiling", "variant", "profit_moyen", "solde_negatif_annee4", "annee1_neg"]].to_string(index=False))


if __name__ == "__main__":
    main()
