"""
Section 2 (suite, 08/12) : config 4 dual-trader (A/B, reserve commune) avec
le risque optimise pour T2 (eval=1,75%, identifie en Section 2 comme
dominant le 1,25% de reference sur Strategie B isolee -- profit, solde_neg,
annee1<0 meilleurs, hit_ceiling ~identique). T1 garde 1,25%/1,90%
(reference Strategie A, inchangee). n=300 exploration, deux plafonds.

N'importe pas ce script directement (convention du projet).
"""
import importlib.util
import random
import sys
import time

import pandas as pd

spec = importlib.util.spec_from_file_location("dt", "dual_trader_2026-08-11.py")
dt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dt)

import robustness_5ers_risk_challenge as eng
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from point_liquidity_rules import DAY_SECONDS
import etape_e_fleet_integration as ei

T2_EVAL_OPTIMIZED = 1.75  # Section 2 : dominant vs 1.25% reference sur Strategie B isolee


def run(n_sims, ceiling, seed=9999):
    pop, market_data, excluded_map, seq, config = dt._common_setup()
    cpop = dt._contrarian_population()

    configs = [
        ("4_baseline_eval1.25_both", {"T1": dt.EVAL_RISK, "T2": dt.EVAL_RISK}, {"T1": dt.FLEET_RISK, "T2": dt.FLEET_RISK}),
        ("4_T2_eval1.75_optimized", {"T1": dt.EVAL_RISK, "T2": T2_EVAL_OPTIMIZED}, {"T1": dt.FLEET_RISK, "T2": dt.FLEET_RISK}),
    ]
    rows = []
    for label, eval_risk_d, fleet_risk_d in configs:
        rng_wr = random.Random(seed)
        rng_boot = random.Random(seed + 1)
        rng_wr_c = random.Random(seed + 2)
        rng_boot_c = random.Random(seed + 3)
        recs = []
        t0 = time.time()
        for run_idx in range(n_sims):
            wr_draw = rng_wr.betavariate(ei.ALPHA_POST, ei.BETA_POST)
            trades, slot_arrivals = eng.build_flexible_population(pop, wr_draw, 1.0, False, random.Random(rng_boot.random()))
            block_seconds = 2 * 30 * DAY_SECONDS
            blocks = build_blocks(trades, slot_arrivals, block_seconds)
            target_duration = slot_arrivals[-1]
            raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot, target_duration)
            order = list(range(len(raw_trades)))

            wr_draw_c = rng_wr_c.betavariate(ei.ALPHA_POST, ei.BETA_POST)
            trades_c, slots_c = eng.build_flexible_population(cpop, wr_draw_c, 1.0, False, random.Random(rng_boot_c.random()))
            blocks_c = build_blocks(trades_c, slots_c, block_seconds)
            raw_trades_c, raw_slots_c = build_full_block_bootstrap_sequence(blocks_c, block_seconds, rng_boot_c, target_duration)

            res = dt.run_dual(raw_trades, raw_slots, market_data, excluded_map, order, seq, config,
                               ei.DEFAULT_EMERGENCY, eval_risk_d, fleet_risk_d, dt.GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                               ei.EXTRA_THRESHOLD_MULT, ceiling_combined=ceiling, reserve_pooled=True,
                               bb_variant="split", spec_variant="rr_band",
                               contrarian_trades=raw_trades_c, contrarian_slots=raw_slots_c)
            recs.append(res)

        df = pd.DataFrame(recs)
        combined_net = df["combined_net"] - df["combined_is_paid"]
        year1_neg = df["combined_year1_net"] < 0
        row = dict(config=label, ceiling=ceiling, n=len(df),
                   profit_moyen=combined_net.mean(), profit_median=combined_net.median(),
                   solde_negatif_annee4=(combined_net < 0).mean() * 100,
                   hit_ceiling_pct=df["combined_hit_ceiling"].mean() * 100,
                   annee1_neg=year1_neg.mean() * 100,
                   T1_net_moyen=df["T1_net"].mean(), T2_net_moyen=df["T2_net"].mean())
        rows.append(row)
        print(f"[{label:28s} ceiling={ceiling:.0f}$] profit_moyen={row['profit_moyen']:+,.0f}$ "
              f"solde_negatif_annee4={row['solde_negatif_annee4']:.2f}% hit_ceiling={row['hit_ceiling_pct']:.2f}% "
              f"annee1<0={row['annee1_neg']:.2f}% (T1={row['T1_net_moyen']:+,.0f}$/T2={row['T2_net_moyen']:+,.0f}$) "
              f"({time.time()-t0:.0f}s)")
        pd.DataFrame(rows).to_csv(f"dual_trader_config4_t2_risk_n{n_sims}_c{int(ceiling)}.csv", index=False)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    ceiling = float(sys.argv[2]) if len(sys.argv) > 2 else 3000.0
    t_start = time.time()
    import rr_threshold_test as rrt
    print(f"[verif] HIST_PATH = {rrt.HIST_PATH}, FIRM_MAX_ACCOUNTS Blueberry = {ei.FIRM_MAX_ACCOUNTS['Blueberry']}")
    run(n_sims, ceiling)
    print(f"\nTermine en {time.time()-t_start:.0f}s.")
