"""
Re-criblage du risque a n>=300 (le sweep initial etait a n=100, sous le
plancher methodologique du projet). Grille resserree autour de la zone
d'interet identifiee au premier passage (eval 1,00-1,50%, flotte
1,50-2,00%), pour REF uniquement (100% 2-step), plafond 1000$.

n=300 minimum pour le criblage complet, puis le point optimal (s'il differe
de eval=1,25%/flotte=1,75% deja retenu) sera reconfirme a n=600 separement.
"""
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
from point_liquidity_rules import CORR_TH
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs

import etape_e_fleet_integration as ei

EVAL_GRID = [1.00, 1.15, 1.25, 1.40, 1.50]
FLEET_GRID = [1.50, 1.65, 1.75, 1.90, 2.00]
GFT_EVAL_RISK = 1.75
N_SIMS = 300
CEILING = 1000.0

if __name__ == "__main__":
    t_start = time.time()
    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)
    seq = ei.seq_grouped_multi(1000, 15000, 25000, 25000)

    rows = []
    for eval_r in EVAL_GRID:
        for fleet_r in FLEET_GRID:
            t0 = time.time()
            df = ei.run_propagated(pop, market_data, excluded_map, CEILING, seq, ei.CONFIG_REF, ei.DEFAULT_EMERGENCY,
                                    eval_r, fleet_r, GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                                    ei.EXTRA_THRESHOLD_MULT, n_sims=N_SIMS, seed=2026)
            net = df["final_net_split"] - df["is_paid_cum"]
            row = dict(eval_risk=eval_r, fleet_risk=fleet_r, profit=net.mean(),
                       ruine=(net < 0).sum() / len(df) * 100,
                       annee1_neg=(df["year1_net_split"] < 0).sum() / len(df) * 100,
                       mean_breaks=df["total_breaks"].mean())
            rows.append(row)
            print(f"eval={eval_r}% flotte={fleet_r}% profit={row['profit']:+,.0f}$ ruine={row['ruine']:.2f}% "
                  f"annee1<0={row['annee1_neg']:.2f}% ({time.time()-t0:.0f}s)")
            pd.DataFrame(rows).to_csv("risk_sweep_n300_results.csv", index=False)

    pd.DataFrame(rows).to_csv("risk_sweep_n300_results.csv", index=False)
    print(f"\nTermine en {time.time()-t_start:.0f}s.")
