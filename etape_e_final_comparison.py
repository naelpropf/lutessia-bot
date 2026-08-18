"""
Etape E, point 5 : comparaison apples-to-apples finale, n=600, meme
mecanisme de croissance (deblocage echelonne + compte supplementaire +
fiscalite) pour REF (100% 2-step) et WINNER (combo gagnant Etape D).

Risque retenu suite au balayage etape_e_risk_sweep.py (grille elargie,
n=100) :
  REF    : eval=1.25%, flotte=1.75% (meilleur profit a ruine basse ~3%)
  WINNER : eval=1.25%, flotte=2.25% (arbitrage explicite : le point a profit
           max, eval=2.75/flotte=2.75, avait 27% de ruine pour seulement
           +15% de profit vs ce point a 14% de ruine -- prefere ce
           compromis plutot que maximiser aveuglement le profit)
"""
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
from point_liquidity_rules import CORR_TH
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs

import etape_e_fleet_integration as ei

N_SIMS = 600
GFT_EVAL_RISK = 1.75

RISK_BY_CONFIG = {
    "REF": dict(eval_risk=1.25, fleet_risk=1.75),
    "WINNER": dict(eval_risk=1.25, fleet_risk=2.25),
}

if __name__ == "__main__":
    t_start = time.time()
    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)
    seq = ei.seq_grouped_multi(1000, 15000, 25000, 25000)

    rows = []
    for label, config in [("REF", ei.CONFIG_REF), ("WINNER", ei.CONFIG_WINNER)]:
        risk = RISK_BY_CONFIG[label]
        for ceiling in (1000.0, 3000.0):
            t0 = time.time()
            df = ei.run_propagated(pop, market_data, excluded_map, ceiling, seq, config, ei.DEFAULT_EMERGENCY,
                                    risk["eval_risk"], risk["fleet_risk"], GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                                    ei.EXTRA_THRESHOLD_MULT, n_sims=N_SIMS, seed=777)
            net = df["final_net_split"] - df["is_paid_cum"]
            row = dict(config=label, ceiling=ceiling, eval_risk=risk["eval_risk"], fleet_risk=risk["fleet_risk"],
                       profit=net.mean(), ruine=(net < 0).sum() / len(df) * 100,
                       annee1_neg=(df["year1_net_split"] < 0).sum() / len(df) * 100,
                       mean_breaks=df["total_breaks"].mean())
            rows.append(row)
            print(f"[{label:7s} plafond={ceiling:.0f}$] profit={row['profit']:+,.0f}$ ruine={row['ruine']:.2f}% "
                  f"annee1<0={row['annee1_neg']:.2f}% breaks_moy={row['mean_breaks']:.0f} ({time.time()-t0:.0f}s)")
            pd.DataFrame(rows).to_csv("etape_e_final_comparison_results.csv", index=False)

    print(f"\nTermine en {time.time()-t_start:.0f}s.")
