"""
Session 08/08 (jour 6) -- Objectif 1 : re-mesure du chiffre de reference
(config finale verrouillee, seuils 1000/15000/25000/25000$) APRES correction
des 2 bugs DD FundedNext trouves par audit (DD journalier 5%->4%, DD max
non differencie 10%->8%). Compare directement au chiffre n=600 deja connu
AVANT correction (6 029 170$/6 130 198$, ruine 1,67%/0,00%, annee1<0
5,17%/3,50%) sans avoir besoin de revert -- la correction ne touche que
GROUP_DEFS["FundedNext"] et le calcul du DD max, tout le reste du moteur
est identique.
"""
import sys
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
from point_liquidity_rules import CORR_TH
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs
from extra_account_v4_multi import DEFAULT_EMERGENCY, FINAL_RESERVE_SHARE, FINAL_EVAL_RISK, FINAL_FLEET_RISK, \
    FINAL_GFT_EVAL_RISK, EXTRA_THRESHOLD_MULT
from extra_account_v4_multi_stagger import seq_grouped_multi, run_propagated

if __name__ == "__main__":
    t_start = time.time()
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 600

    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

    seq = seq_grouped_multi(1000., 15000., 25000., 25000.)

    rows = []
    for ceiling in (1000.0, 3000.0):
        t0 = time.time()
        df = run_propagated(pop, market_data, excluded_map, ceiling, seq, DEFAULT_EMERGENCY,
                             FINAL_FLEET_RISK, FINAL_EVAL_RISK, FINAL_GFT_EVAL_RISK, FINAL_RESERVE_SHARE,
                             EXTRA_THRESHOLD_MULT, n_sims, seed=4000)
        net = df["final_net_split"] - df["is_paid_cum"]
        row = dict(ceiling=ceiling, profit=net.mean(), ruine=(net < 0).sum() / len(df) * 100,
                   annee1_neg=(df["year1_net_split"] < 0).sum() / len(df) * 100)
        rows.append(row)
        print(f"[plafond {ceiling:.0f}$] profit={row['profit']:+,.0f}$ | ruine={row['ruine']:.2f}% | "
              f"P(annee1<0)={row['annee1_neg']:.2f}% (n={n_sims}, {time.time()-t0:.0f}s)")

    pd.DataFrame(rows).to_csv("dd_audit_rerun.csv", index=False)
    print(f"\nTermine en {time.time()-t_start:.0f}s.")
