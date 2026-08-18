"""
Reconciliation du "0% negatif annee 3/4" (historique, year1_outcome_recovery_
full.py, 31/07) vs le P5 negatif observe aujourd'hui (winrate_uncertainty_
propagation.py, 07/08). Diagnostic : caracterise les trajectoires du P5
negatif + teste si le plafond personnel (1000$/3000$) est la cause racine,
en comparant a un plafond artificiellement illimite.

Reutilise l'engine point_liquidity_hybrid.run_one tel quel (deja valide),
avec winrate tire du posterior Beta(260,388) par run (deja valide dans
winrate_uncertainty_propagation.py) -- SEUL ajout : marques annuelles
1/2/3/4 (au lieu de [annee1, horizon final] seulement) pour voir OU la
trajectoire decroche, et capture du nombre de casses a chaque marque.
"""
import random
import time

import numpy as np
import pandas as pd

import robustness_5ers_risk_challenge as eng
from point_liquidity_hybrid import run_one as hybrid_run_one
from point_liquidity_rules import DAY_SECONDS
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs
from real_cash_risk_year1_block_bootstrap import DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence

CORR_TH = 0.6
ALPHA_POST, BETA_POST = 260, 388
YEAR_SECONDS = 365.25 * DAY_SECONDS
MONTH_SECONDS = DAYS_PER_MONTH * DAY_SECONDS
YEAR_MARKS = [1, 2, 3, 4]


def run_propagated_multi_mark(pop, market_data, excluded_map, ceiling, n_sims, seed, total_horizon_cap=None):
    rng_wr = random.Random(seed)
    rng_boot = random.Random(seed + 1)
    rows = []
    for _ in range(n_sims):
        wr_draw = rng_wr.betavariate(ALPHA_POST, BETA_POST)
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_draw, 1.0, False, random.Random(rng_wr.random()))
        sub_horizon = slot_arrivals[-1]
        target_duration = min(sub_horizon, total_horizon_cap) if total_horizon_cap else sub_horizon
        from real_cash_risk_year1_block_bootstrap import build_blocks
        block_seconds = 2 * DAYS_PER_MONTH * DAY_SECONDS
        blocks = build_blocks(trades, slot_arrivals, block_seconds)
        marks = [min(y * YEAR_SECONDS, target_duration) for y in YEAR_MARKS]
        marks = sorted(set(marks))

        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot, target_duration)
        order = list(range(len(raw_trades)))
        snaps, hit_ceiling, full_month = hybrid_run_one(raw_trades, raw_slots, market_data, excluded_map, order,
                                                          marks, ceiling)
        row = {"wr_draw": wr_draw, "hit_ceiling": hit_ceiling, "full_structure_month": full_month}
        for i, m in enumerate(marks):
            yr_label = round(m / YEAR_SECONDS, 2)
            row[f"net_t{i}"] = snaps[i][1]
            row[f"cash_t{i}"] = snaps[i][2]
            row[f"breaks_t{i}"] = snaps[i][3]
            row[f"yr_t{i}"] = yr_label
        rows.append(row)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    import sys
    t_start = time.time()
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 800

    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

    all_summary = []
    for ceiling_label, ceiling in [("1000$", 1000.0), ("3000$", 3000.0), ("illimite", 1e12)]:
        t0 = time.time()
        df = run_propagated_multi_mark(pop, market_data, excluded_map, ceiling, n_sims, seed=200)
        df.to_csv(f"p5_diagnosis_ceiling_{ceiling_label.replace('$','').replace('é','e')}.csv", index=False)
        final_col = [c for c in df.columns if c.startswith("net_t")][-1]
        n_neg = (df[final_col] < 0).sum()
        p5 = df[final_col].quantile(0.05)
        print(f"[ceiling={ceiling_label}] n={len(df)} | profit final moy={df[final_col].mean():+,.0f}$ | "
              f"P5={p5:+,.0f}$ | P(final<0)={n_neg/len(df)*100:.2f}% ({n_neg}/{len(df)}) ({time.time()-t0:.0f}s)")
        all_summary.append(dict(ceiling=ceiling_label, n=len(df), p5=p5, p_negatif_pct=n_neg/len(df)*100,
                                 mean=df[final_col].mean()))

    pd.DataFrame(all_summary).to_csv("p5_diagnosis_ceiling_ablation_summary.csv", index=False)
    print(f"\nTermine en {time.time()-t_start:.0f}s.")
