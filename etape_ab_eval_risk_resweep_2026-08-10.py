"""
Etape AB (08/10 nuit, suite 11) : resweep du risque eval au-dela de
1,25% (1,50/1,75/2,00/2,50/3,00%, flotte=1,90% inchange) sous le moteur
actuel corrige (REF+V2 + cap Blueberry corrige + FTMO-10%/GFT Goat
Guard) -- l'ancien sweep (Etape E chantier 1, 08/09) datait d'avant la
correction Blueberry et avant le mecanisme V2/FTMO-10/GoatGuard.

Reutilise etape_q_v2_plus_ftmo_gft_2026-08-10.py (charge via importlib),
meme config officielle, seul EVAL_RISK varie.

N'importe pas ce script directement (convention du projet).
"""
import importlib.util
import sys
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
from point_liquidity_rules import CORR_TH
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs
import etape_e_fleet_integration as ei

spec = importlib.util.spec_from_file_location("etape_q_mod", "etape_q_v2_plus_ftmo_gft_2026-08-10.py")
etape_q_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(etape_q_mod)

if __name__ == "__main__":
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    ceilings_arg = [float(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [1000.0, 3000.0]
    eval_risks = [float(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else [1.25, 1.50, 1.75, 2.00, 2.50, 3.00]

    t_start = time.time()
    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)
    seq = ei.seq_grouped_multi(1000, 15000, 25000, 25000)
    config = ei.CONFIG_REF
    FLEET_RISK, GFT_EVAL_RISK = 1.90, 1.75

    print(f"[verif] FIRM_MAX_ACCOUNTS Blueberry = {ei.FIRM_MAX_ACCOUNTS['Blueberry']}, "
          f"FIRM_CAPITAL_CAP Blueberry = {ei.FIRM_CAPITAL_CAP['Blueberry']:,.0f}$")

    rows = []
    for eval_risk in eval_risks:
        for ceiling in ceilings_arg:
            t0 = time.time()
            df = etape_q_mod.run_propagated(pop, market_data, excluded_map, ceiling, seq, config, ei.DEFAULT_EMERGENCY,
                                             eval_risk, FLEET_RISK, GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                                             ei.EXTRA_THRESHOLD_MULT, n_sims=n_sims, seed=9999,
                                             b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True,
                                             ftmo_discount=True, gft_goat_guard=True)
            row = etape_q_mod.summarize(df, f"eval={eval_risk:.2f}%", ceiling)
            rows.append(row)
            print(f"[eval={eval_risk:.2f}% plafond={ceiling:.0f}$] profit={row['profit']:+,.0f}$ "
                  f"ruine={row['ruine']:.2f}% annee1<0={row['annee1_neg']:.2f}% (pre={row['annee1_neg_pre']:.2f}%) "
                  f"casse<=30j={row['break_rate_30d_pct']:.2f}% quasi_gele={row['quasi_frozen_pct']:.1f}% "
                  f"({time.time()-t0:.0f}s)")
            pd.DataFrame(rows).to_csv(f"etape_ab_eval_risk_resweep_n{n_sims}.csv", index=False)

    print(f"\nTermine en {time.time()-t_start:.0f}s.")
