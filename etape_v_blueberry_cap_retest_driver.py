"""
Driver temporaire (08/10 nuit, suite 5) : lance UNIQUEMENT la config
"REF_V2 + (a)+(b) combine" de etape_q_v2_plus_ftmo_gft_2026-08-10.py (la
reference officielle REF+V2), aux 2 plafonds, pour comparer avant/apres
la correction du cap Blueberry (FIRM_MAX_ACCOUNTS/FIRM_CAPITAL_CAP dans
etape_e_fleet_integration.py). Le nom de fichier source contient des
tirets (pas un identifiant Python valide) -> charge via importlib.

Usage : python etape_v_blueberry_cap_retest_driver.py <n_sims> <tag> <ceilings comma-sep>
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
    tag = sys.argv[2] if len(sys.argv) > 2 else "run"
    ceilings_arg = [float(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else [1000.0, 3000.0]

    t_start = time.time()
    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)
    seq = ei.seq_grouped_multi(1000, 15000, 25000, 25000)
    config = ei.CONFIG_REF
    EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK = 1.25, 1.90, 1.75

    print(f"[verif] FIRM_MAX_ACCOUNTS Blueberry = {ei.FIRM_MAX_ACCOUNTS['Blueberry']}, "
          f"FIRM_CAPITAL_CAP Blueberry = {ei.FIRM_CAPITAL_CAP['Blueberry']:,.0f}$")

    rows = []
    for ceiling in ceilings_arg:
        t0 = time.time()
        df = etape_q_mod.run_propagated(pop, market_data, excluded_map, ceiling, seq, config, ei.DEFAULT_EMERGENCY,
                                         EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                                         ei.EXTRA_THRESHOLD_MULT, n_sims=n_sims, seed=9999,
                                         b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True,
                                         ftmo_discount=True, gft_goat_guard=True)
        row = etape_q_mod.summarize(df, f"REF_V2_combine_{tag}", ceiling)
        rows.append(row)
        print(f"[{tag:8s} plafond={ceiling:.0f}$] profit={row['profit']:+,.0f}$ ruine={row['ruine']:.2f}% "
              f"annee1<0={row['annee1_neg']:.2f}% (pre={row['annee1_neg_pre']:.2f}%) "
              f"casse<=30j={row['break_rate_30d_pct']:.2f}% ({time.time()-t0:.0f}s)")
        pd.DataFrame(rows).to_csv(f"etape_v_refv2_{tag}_n{n_sims}.csv", index=False)

    print(f"\nTermine en {time.time()-t_start:.0f}s.")
