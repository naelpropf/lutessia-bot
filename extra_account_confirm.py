import time
import pandas as pd
import robustness_5ers_risk_challenge as eng
from point_liquidity_rules import CORR_TH
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs
from extra_account_vs_scaling import run_propagated, DEFAULT_RESERVE, DEFAULT_EMERGENCY, FINAL_RESERVE_SHARE, FINAL_FLEET_RISK, FINAL_EVAL_RISK

pop = build_population_with_trailing('fixed', 0.15, min_rr=1.25, verbose=False)
market_data = eng.load_market_data()
corr_matrix = pd.read_csv('correlation_matrix.csv', index_col=0)
tickers = sorted(pop['ticker'].unique())
excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

rows = []
for ceiling in (1000.0, 3000.0):
    for label, gm, thr in [("none", "none", None), ("extra_account_3x", "extra_account", 3.0)]:
        t0 = time.time()
        df = run_propagated(pop, market_data, excluded_map, ceiling, DEFAULT_RESERVE, DEFAULT_EMERGENCY,
                             FINAL_FLEET_RISK, FINAL_EVAL_RISK, FINAL_RESERVE_SHARE, gm, thr, 600, seed=4000)
        net = df['final_net_split'] - df['is_paid_cum']
        row = dict(ceiling=ceiling, config=label, profit=net.mean(),
                   ruine=(net < 0).sum()/len(df)*100, annee1_neg=(df['year1_net_split']<0).sum()/len(df)*100,
                   delai_surplus=df['first_extra_month'].median() if gm=="extra_account" else None)
        rows.append(row)
        print(f"[{ceiling:.0f}$ | {label}] profit={row['profit']:+,.0f}$ | ruine={row['ruine']:.2f}% | P(annee1<0)={row['annee1_neg']:.2f}% | delai={row['delai_surplus']} ({time.time()-t0:.0f}s)")
pd.DataFrame(rows).to_csv("extra_account_confirm.csv", index=False)
