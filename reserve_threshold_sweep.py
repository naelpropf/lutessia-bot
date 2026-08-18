"""
Cascade check complet (etape_e_cascade_check.py, deja corrige du bug
tax_breach_*) sur les DEUX nouveaux points de risque candidats trouves lors
du re-criblage du 08/09 (eval=1,25%/flotte=1,90% et eval=1,00%/flotte=1,90%),
aux deux plafonds (1000$/3000$). L'ancien cascade check utilisait
eval=1,25%/flotte=1,75%, desormais obsolete.

Ne suppose PAS qu'un point gagnant sur profit/ruine passe automatiquement
le cascade check -- verdict GO/NOT GO explicite et independant pour chacun.
"""
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
from point_liquidity_rules import CORR_TH
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs

import etape_e_fleet_integration as ei
from etape_e_cascade_check import run_propagated_instrumented

N_SIMS = 600
CANDIDATES = [("eval=1.25/fleet=1.90", 1.25, 1.90), ("eval=1.00/fleet=1.90", 1.00, 1.90)]

if __name__ == "__main__":
    t_start = time.time()
    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)
    seq = ei.seq_grouped_multi(1000, 15000, 25000, 25000)

    rows = []
    for label, eval_r, fleet_r in CANDIDATES:
        for ceiling in (1000.0, 3000.0):
            t0 = time.time()
            df = run_propagated_instrumented(pop, market_data, excluded_map, ceiling, seq, ei.CONFIG_REF,
                                              ei.DEFAULT_EMERGENCY, eval_r, fleet_r, 1.75, ei.FINAL_RESERVE_SHARE,
                                              ei.EXTRA_THRESHOLD_MULT, n_sims=N_SIMS, seed=999)
            break_rate_30d = df["breaks_within_30d"].sum() / df["total_opens"].sum() * 100
            break_rate_60d = df["breaks_within_60d"].sum() / df["total_opens"].sum() * 100
            quasi_frozen = (df["final_reserve"] < 100).mean() * 100
            row = dict(point=label, eval_risk=eval_r, fleet_risk=fleet_r, ceiling=ceiling,
                       break_rate_30d_pct=break_rate_30d, break_rate_60d_pct=break_rate_60d,
                       reserve_min_6mo_worst=df["reserve_min_6mo"].min(),
                       reserve_min_after_unlock_worst=df["reserve_min_after_first_unlock"].dropna().min(),
                       quasi_frozen_pct=quasi_frozen)
            rows.append(row)
            print(f"[{label} plafond={ceiling:.0f}$] casse<=30j={break_rate_30d:.2f}% casse<=60j={break_rate_60d:.2f}% "
                  f"reserve_min_6mo(pire cas)={row['reserve_min_6mo_worst']:,.0f}$ "
                  f"quasi_gele={quasi_frozen:.1f}% ({time.time()-t0:.0f}s)")
            pd.DataFrame(rows).to_csv("reserve_threshold_sweep_cascade_results.csv", index=False)

    print(f"\nTermine en {time.time()-t_start:.0f}s.")
