"""
Verification demandee : le resweep de risque du 08/09 (eval_risk descendu a
1,00-1,25%) a garde GFT_EVAL_RISK fixe a 1,75% (herite de l'ancien moteur,
jamais reteste) -- ce qui inverse la relation d'origine : GFT etait cense
avoir un risque REDUIT vs les autres firms (1,75% < 2,25% ancien), mais
avec le nouveau eval_risk a 1,00-1,25%, GFT a maintenant un risque PLUS
ELEVE que les autres (1,75% > 1,00-1,25%) -- oppose a l'intention
d'origine (proteger GFT de son DD plus serre).

Teste gft_eval_risk in [1.00, 1.25, 1.50, 1.75] avec eval_risk (autres
firms) fixe a chacun des deux points retenus (1,00% et 1,25%), fleet_risk
fixe a 1,90%. n=300, plafond 1000$ (le plus contraignant).
"""
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
from point_liquidity_rules import CORR_TH
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs

import etape_e_fleet_integration as ei

GFT_GRID = [1.00, 1.25, 1.50, 1.75]
EVAL_POINTS = [1.00, 1.25]
FLEET_RISK = 1.90
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
    for eval_r in EVAL_POINTS:
        for gft_r in GFT_GRID:
            t0 = time.time()
            df = ei.run_propagated(pop, market_data, excluded_map, CEILING, seq, ei.CONFIG_REF, ei.DEFAULT_EMERGENCY,
                                    eval_r, FLEET_RISK, gft_r, ei.FINAL_RESERVE_SHARE, ei.EXTRA_THRESHOLD_MULT,
                                    n_sims=N_SIMS, seed=4242)
            net = df["final_net_split"] - df["is_paid_cum"]
            row = dict(eval_risk=eval_r, gft_eval_risk=gft_r, fleet_risk=FLEET_RISK, profit=net.mean(),
                       ruine=(net < 0).sum() / len(df) * 100, annee1_neg=(df["year1_net_split"] < 0).sum() / len(df) * 100)
            rows.append(row)
            print(f"eval={eval_r}% gft_eval={gft_r}% profit={row['profit']:+,.0f}$ ruine={row['ruine']:.2f}% "
                  f"annee1<0={row['annee1_neg']:.2f}% ({time.time()-t0:.0f}s)")
            pd.DataFrame(rows).to_csv("gft_confirm_results.csv", index=False)

    print(f"\nTermine en {time.time()-t_start:.0f}s.")
