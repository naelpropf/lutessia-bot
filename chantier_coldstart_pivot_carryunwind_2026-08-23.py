"""chantier_coldstart_pivot_carryunwind_2026-08-23.py

Suite a la decouverte du choc carry-unwind JPY/Sahm (aout 2024, delta EV
-1,65R/-1,79R A/B, winrate effondre, 100% des pertes en -1,00R classique --
[[project_omicron_detail_et_carry_unwind_2026-08-23]]) : le test cold-start
deja fait (chantier_coldstart_svb_isrhamas_2026-08-23.py) ne couvrait QUE
SVB/Israel-Hamas, tournait la trajectoire COMPLETE (4 ans), et rapportait
annee1_neg/year1_net_split (metriques PROJET) -- jamais state["total_breaks"]
(deja track par le moteur, s18.run_one ligne 630, jamais extrait avant).

Ce chantier isole specifiquement le risque de CASSE DU COMPTE PIVOT LUI-MEME
(pas la solvabilite projet a 4 ans) dans les 30-60 premiers jours, quand
SEUL le compte pivot Blueberry existe (STARTER=Blueberry, is_day0=True,
seuil FTMO=1000$ reserve avant que le 2e groupe ouvre -- verifie via le
compteur total_opens deja track par le moteur, qui compte les OUVERTURES de
compte : si total_opens reste a 1 (le pivot seul, initialise a
sum(...last_open_time==0.0)) sur toute la fenetre tronquee, aucun autre
groupe n'a ouvert -- validation empirique, pas suppose).

Meme mecanisme de forcage que chantier_coldstart_svb_isrhamas_2026-08-23.py
(1er segment de la trajectoire = trades reels de la fenetre choc, reste en
bootstrap standard) MAIS trajectoire TRONQUEE a target_duration_override
(45j et 60j testes) au lieu de la duree complete -- le reste du bootstrap
normal ne sert qu'a completer les jours restants apres la fenetre choc dans
la fenetre tronquee, pas 4 ans.
"""
import importlib.util
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

from real_cash_risk_year1_block_bootstrap import build_blocks
from reference_metrics_final import build_full_block_bootstrap_sequence

DAY_SECONDS = 86400
BLOCK_SECONDS = 2 * 30 * DAY_SECONDS
CARRY_UNWIND_WINDOW = (pd.Timestamp("2024-08-01"), pd.Timestamp("2024-08-16"))


def run_propagated_truncated(pop, market_data, excluded_map, ceiling, seq_grouped, format_by_firm, emergency,
                              eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult, n_sims, seed,
                              alpha_post, beta_post, target_duration_days, forced_window=None, **kw):
    rng_wr = random.Random(seed)
    rng_boot = random.Random(seed + 1)
    sub_sorted = pop.sort_values("date_creation").reset_index(drop=True)
    target_duration = target_duration_days * DAY_SECONDS

    forced_mask = None
    if forced_window is not None:
        start_ts, end_ts = forced_window
        forced_mask = (sub_sorted["date_creation"] >= start_ts) & (sub_sorted["date_creation"] < end_ts)
        assert int(forced_mask.sum()) > 0, f"fenetre forcee vide : {forced_window}"

    rows = []
    for _ in range(n_sims):
        wr_draw = rng_wr.betavariate(alpha_post, beta_post)
        trades, slot_arrivals = s18.build_flexible_population_with_rr(pop, wr_draw, 1.0, False, random.Random(rng_boot.random()))
        blocks = build_blocks(trades, slot_arrivals, BLOCK_SECONDS)

        if forced_window is None:
            raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, BLOCK_SECONDS, rng_boot, target_duration)
        else:
            idxs = [i for i, keep in enumerate(forced_mask.to_numpy()) if keep]
            base_slot = min(slot_arrivals[i] for i in idxs)
            raw_trades, raw_slots = [], []
            for i in idxs:
                raw_trades.append(trades[i])
                raw_slots.append(slot_arrivals[i] - base_slot)
            # <<< FIX 2026-08-23 : pour une trajectoire TRONQUEE (<=60j), demarrer la
            # reprise du bootstrap normal juste apres la duree REELLE de la fenetre
            # forcee (pas un BLOCK_SECONDS=60j fixe, qui depassait immediatement toute
            # target_duration<=60j et coupait la simulation net a la fin du choc force).
            forced_span = max(raw_slots) if raw_slots else 0.0
            cursor = forced_span
            while cursor < target_duration:
                block = blocks[rng_boot.randrange(len(blocks))]
                for trade, offset in block:
                    raw_trades.append(trade)
                    raw_slots.append(cursor + offset)
                cursor += BLOCK_SECONDS
        # tronque STRICTEMENT a target_duration_days (le forcage + le dernier bloc bootstrap peuvent deborder)
        keep = [i for i, s in enumerate(raw_slots) if s < target_duration]
        raw_trades = [raw_trades[i] for i in keep]
        raw_slots = [raw_slots[i] for i in keep]

        order = list(range(len(raw_trades)))
        res = s18.run_one(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, seq_grouped, format_by_firm,
                           emergency, eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult, **kw)
        rows.append(res)
    return pd.DataFrame(rows)


def run_config(pop, market_data, excluded_map, alpha_post, beta_post, ceiling, n_sims, seed, target_duration_days,
                forced_window, label):
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
                                   target_duration_days=target_duration_days, forced_window=forced_window,
                                   **common_kwargs)
    dt = time.time() - t0
    pivot_break_rate = (df["total_breaks"] > 0).mean() * 100
    other_group_opened = (df["total_opens"] > 1).mean() * 100
    print(f"[{label} dur={target_duration_days}j c={ceiling:.0f}$] "
          f"risque_casse_pivot={pivot_break_rate:.2f}% (total_breaks>0) "
          f"autre_groupe_ouvert={other_group_opened:.2f}% (total_opens>1, validation isolement pivot) "
          f"total_opens_moy={df['total_opens'].mean():.2f} n_sims={n_sims} ({dt:.0f}s)", flush=True)
    return dict(label=label, target_duration_days=target_duration_days, ceiling=ceiling, n=n_sims,
                pivot_break_rate=pivot_break_rate, other_group_opened_rate=other_group_opened,
                total_opens_moy=df["total_opens"].mean(), total_breaks_moy=df["total_breaks"].mean()), df


def main():
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 13579

    pop, market_data, excluded_map, alpha_post, beta_post, label = pdb.load_scenario_pgp()
    n_w = int(((pop["date_creation"] >= CARRY_UNWIND_WINDOW[0]) & (pop["date_creation"] < CARRY_UNWIND_WINDOW[1])).sum())
    print(f"Population : {label}, n={len(pop)} -- fenetre carry-unwind [{CARRY_UNWIND_WINDOW[0].date()}"
          f"->{CARRY_UNWIND_WINDOW[1].date()}] : {n_w} trades reels", flush=True)

    all_rows = []
    for target_days in [45, 60]:
        for ceiling in [1000.0, 3000.0]:
            print(f"\n{'='*95}\nDUREE TRONQUEE={target_days}j, CEILING={ceiling:.0f}$\n{'='*95}", flush=True)
            row_base, _ = run_config(pop, market_data, excluded_map, alpha_post, beta_post, ceiling, n_sims, seed,
                                      target_days, None, "baseline")
            row_shock, _ = run_config(pop, market_data, excluded_map, alpha_post, beta_post, ceiling, n_sims, seed,
                                       target_days, CARRY_UNWIND_WINDOW, "carry_unwind_force")
            delta = row_shock["pivot_break_rate"] - row_base["pivot_break_rate"]
            p1, p2 = row_base["pivot_break_rate"] / 100, row_shock["pivot_break_rate"] / 100
            se = np.sqrt(p1 * (1 - p1) / n_sims + p2 * (1 - p2) / n_sims)
            z = (p2 - p1) / se if se > 0 else float("nan")
            print(f"  -> DELTA risque casse pivot = {delta:+.2f}pts (z approx={z:+.2f})", flush=True)
            all_rows.append(row_base)
            all_rows.append(row_shock)
            pd.DataFrame(all_rows).to_csv("chantier_coldstart_pivot_carryunwind_2026-08-23.csv", index=False)

    print(f"\n{'='*95}\nSYNTHESE\n{'='*95}")
    dfres = pd.DataFrame(all_rows)
    print(dfres.to_string(index=False))


if __name__ == "__main__":
    main()
