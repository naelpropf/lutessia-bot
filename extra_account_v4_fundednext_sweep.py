"""
Session 08/08 (suite, jour 5) -- Objectif 2 : balayage du seuil FundedNext
SEUL, FTMO/Fivers/GFT FIXES a leurs seuils retenus (1k/15k/25k$, corrige
DD The5%ers=5% -- session courante). FundedNext=30k$ n'a jamais ete
retouche depuis l'introduction de l'echelonnement des 3 autres firms, et
le diagnostic de la session precedente (project_final_diagnosis_ftmo1k_
2026-08-08) a montre que 92-100% des runs ruines restent bloques AVANT
d'atteindre ce seuil -- FundedNext est le goulot d'etranglement structurel
actuel du deblocage complet.

Reutilise EXACTEMENT seq_grouped_multi/run_one/run_propagated de
extra_account_v4_multi_stagger.py.
"""
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
from point_liquidity_rules import CORR_TH
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs
from extra_account_v4_multi_stagger import (seq_grouped_multi, run_propagated, DEFAULT_EMERGENCY,
                                             FINAL_FLEET_RISK, FINAL_EVAL_RISK, FINAL_GFT_EVAL_RISK,
                                             FINAL_RESERVE_SHARE, EXTRA_THRESHOLD_MULT)

FIXED_FTMO = 1000.0
FIXED_FIVERS = 15000.0
FIXED_GFT = 25000.0

if __name__ == "__main__":
    import sys
    t_start = time.time()
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300

    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

    if len(sys.argv) > 2:
        fn_thresholds = [float(x) * 1000 for x in sys.argv[2].split(",")]
    else:
        fn_thresholds = [20000.0, 25000.0, 30000.0]

    rows = []
    for ceiling in (1000.0, 3000.0):
        print(f"\n{'='*100}\nPlafond {ceiling:.0f}$ (n={n_sims}) -- FTMO/Fivers/GFT fixes a "
              f"{FIXED_FTMO/1000:.0f}/{FIXED_FIVERS/1000:.0f}/{FIXED_GFT/1000:.0f}k\n{'='*100}")
        for t_fn in fn_thresholds:
            seq = seq_grouped_multi(FIXED_FTMO, FIXED_FIVERS, FIXED_GFT, t_fn)
            t0 = time.time()
            df = run_propagated(pop, market_data, excluded_map, ceiling, seq, DEFAULT_EMERGENCY,
                                 FINAL_FLEET_RISK, FINAL_EVAL_RISK, FINAL_GFT_EVAL_RISK, FINAL_RESERVE_SHARE,
                                 EXTRA_THRESHOLD_MULT, n_sims, seed=4000)
            net = df["final_net_split"] - df["is_paid_cum"]
            row = dict(ceiling=ceiling, fundednext_threshold=t_fn, profit=net.mean(),
                       ruine=(net < 0).sum()/len(df)*100, annee1_neg=(df["year1_net_split"] < 0).sum()/len(df)*100)
            rows.append(row)
            print(f"[FundedNext={t_fn/1000:.0f}k$] profit={row['profit']:+,.0f}$ | ruine={row['ruine']:.2f}% | "
                  f"P(annee1<0)={row['annee1_neg']:.2f}% ({time.time()-t0:.0f}s)")
        pd.DataFrame(rows).to_csv("extra_account_v4_fundednext_sweep.csv", index=False)

    pd.DataFrame(rows).to_csv("extra_account_v4_fundednext_sweep.csv", index=False)
    print(f"\nTermine en {time.time()-t_start:.0f}s.")
