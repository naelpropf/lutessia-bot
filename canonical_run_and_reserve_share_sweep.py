"""
Criblage LEGER des seuils de deblocage echelonne sous le nouveau moteur
multi-phase (les seuils actuels FTMO=1k/Fivers=15k/GFT=25k/FundedNext=25k
ont ete optimises sous l'ancien moteur flat-8%, jamais retestes depuis).

Methode : un seuil a la fois varie autour de sa valeur actuelle, les 3
autres fixes -- meme methodologie que le sweep FundedNext du 08/08
(extra_account_v4_fundednext_sweep.py). Si un ecart notable apparait,
prevoir un resweep complet/croise en suivi.

n=300, plafond 1000$, risque eval=1,00%/flotte=1,90%/gft_eval=1,75%
(placeholder -- a reverifier si gft_confirm.py change ce dernier).
"""
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
from point_liquidity_rules import CORR_TH
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs

import etape_e_fleet_integration as ei

EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK = 1.00, 1.90, 1.75
N_SIMS = 300
CEILING = 1000.0

BASE = dict(t_ftmo=1000, t_fivers=15000, t_gft=25000, t_fundednext=25000)
CANDIDATES = {
    "t_ftmo": [500, 1000, 2000, 5000],
    "t_fivers": [10000, 15000, 20000, 25000],
    "t_gft": [15000, 20000, 25000, 30000],
    "t_fundednext": [15000, 20000, 25000, 30000],
}

if __name__ == "__main__":
    t_start = time.time()
    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

    rows = []
    for param, values in CANDIDATES.items():
        for v in values:
            thresholds = dict(BASE)
            thresholds[param] = v
            seq = ei.seq_grouped_multi(thresholds["t_ftmo"], thresholds["t_fivers"],
                                        thresholds["t_gft"], thresholds["t_fundednext"])
            t0 = time.time()
            df = ei.run_propagated(pop, market_data, excluded_map, CEILING, seq, ei.CONFIG_REF, ei.DEFAULT_EMERGENCY,
                                    EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                                    ei.EXTRA_THRESHOLD_MULT, n_sims=N_SIMS, seed=9191)
            net = df["final_net_split"] - df["is_paid_cum"]
            row = dict(param_varied=param, value=v, is_baseline=(v == BASE[param]),
                       profit=net.mean(), ruine=(net < 0).sum() / len(df) * 100,
                       annee1_neg=(df["year1_net_split"] < 0).sum() / len(df) * 100)
            rows.append(row)
            print(f"[{param}={v:>6}] profit={row['profit']:+,.0f}$ ruine={row['ruine']:.2f}% "
                  f"annee1<0={row['annee1_neg']:.2f}% ({time.time()-t0:.0f}s)")
            pd.DataFrame(rows).to_csv("threshold_sweep_light_results.csv", index=False)

    print(f"\nTermine en {time.time()-t_start:.0f}s.")
