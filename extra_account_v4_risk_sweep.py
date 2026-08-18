"""
Volet 2c (08/08) : re-balaye eval x flotte sous le mecanisme de croissance
final issu de 2a/2b (extra_account_v4_multi.py, comptes supplementaires
deplafonnes sous les vrais caps + The5%ers inclus si retenu -- ENABLE_FIVERS
ci-dessous doit etre mis a jour selon le verdict de 2b avant de lancer ce
script). Grille reduite : eval in {2.0, 2.25, 2.5} x flotte in
{2.25, 2.5, 2.75}, gft_eval_risk fixe a 1.75 (deja optimise separement,
hors perimetre de cette grille).
"""
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
from point_liquidity_rules import CORR_TH
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs
from extra_account_v4_multi import (run_propagated, DEFAULT_RESERVE, DEFAULT_EMERGENCY, FINAL_RESERVE_SHARE,
                                     EXTRA_THRESHOLD_MULT, FINAL_GFT_EVAL_RISK)

ENABLE_FIVERS = True  # a synchroniser avec le verdict du volet 2b avant de lancer

if __name__ == "__main__":
    import sys
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    t_start = time.time()

    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

    eval_grid = [2.0, 2.25, 2.5]
    fleet_grid = [2.25, 2.5, 2.75]

    rows = []
    for ceiling in (1000.0, 3000.0):
        print(f"\n{'='*100}\nPlafond {ceiling:.0f}$\n{'='*100}")
        for eval_r in eval_grid:
            for fleet_r in fleet_grid:
                t0 = time.time()
                df, diag = run_propagated(pop, market_data, excluded_map, ceiling, DEFAULT_RESERVE,
                                           DEFAULT_EMERGENCY, fleet_r, eval_r, FINAL_GFT_EVAL_RISK,
                                           FINAL_RESERVE_SHARE, EXTRA_THRESHOLD_MULT, ENABLE_FIVERS,
                                           n_sims, seed=4000, log_gft_diag=False)
                net = df["final_net_split"] - df["is_paid_cum"]
                row = dict(ceiling=ceiling, eval_risk=eval_r, fleet_risk=fleet_r, profit=net.mean(),
                           ruine=(net < 0).sum() / len(df) * 100,
                           annee1_neg=(df["year1_net_split"] < 0).sum() / len(df) * 100)
                rows.append(row)
                print(f"[eval={eval_r}% flotte={fleet_r}%] profit={row['profit']:+,.0f}$ | "
                      f"ruine={row['ruine']:.2f}% | P(annee1<0)={row['annee1_neg']:.2f}% ({time.time()-t0:.0f}s)")
        pd.DataFrame(rows).to_csv("extra_account_v4_risk_sweep.csv", index=False)

    pd.DataFrame(rows).to_csv("extra_account_v4_risk_sweep.csv", index=False)
    print(f"\nTermine en {time.time()-t_start:.0f}s.")
