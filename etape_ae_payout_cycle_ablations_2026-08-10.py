"""
Etape AE (08/10 nuit, suite 13) : driver d'ablations pour le cycle de
payout (etape_ad, charge via importlib -- nom de fichier avec tirets).
4 configs :
  ref        = payout_cycle=False, GoatGuard=True, V2=True   (reference actuelle, deja connue)
  corrige    = payout_cycle=True,  GoatGuard=True, V2=True   (nouvelle reference candidate, point 2)
  sans_gg    = payout_cycle=True,  GoatGuard=False,V2=True   (isole la valeur de Goat Guard, point 3)
  sans_v2    = payout_cycle=True,  GoatGuard=True, V2=False  (isole la valeur de V2, point 4)
FTMO -10% toujours actif (fait partie de la reference officielle, non
concerne par le cycle de payout).

Usage : python etape_ae_payout_cycle_ablations_2026-08-10.py <n_sims> <ceilings_csv> <configs_csv>
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

spec = importlib.util.spec_from_file_location("etape_ad_mod", "etape_ad_payout_cycle_2026-08-10.py")
etape_ad_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(etape_ad_mod)

CONFIGS = {
    "ref": dict(payout_cycle=False, gft_goat_guard=True, b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True),
    "corrige": dict(payout_cycle=True, gft_goat_guard=True, b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True),
    "sans_gg": dict(payout_cycle=True, gft_goat_guard=False, b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True),
    "sans_v2": dict(payout_cycle=True, gft_goat_guard=True, b_entry_frac=None, b_reduction=None, pre_unlock_only=False),
}

if __name__ == "__main__":
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    ceilings_arg = [float(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [1000.0, 3000.0]
    configs_arg = sys.argv[3].split(",") if len(sys.argv) > 3 else list(CONFIGS.keys())

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
    for label in configs_arg:
        cfg = CONFIGS[label]
        for ceiling in ceilings_arg:
            t0 = time.time()
            df = etape_ad_mod.run_propagated(pop, market_data, excluded_map, ceiling, seq, config, ei.DEFAULT_EMERGENCY,
                                              EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                                              ei.EXTRA_THRESHOLD_MULT, n_sims=n_sims, seed=9999,
                                              b_entry_frac=cfg["b_entry_frac"], b_reduction=cfg["b_reduction"],
                                              pre_unlock_only=cfg["pre_unlock_only"],
                                              ftmo_discount=True, gft_goat_guard=cfg["gft_goat_guard"],
                                              payout_cycle=cfg["payout_cycle"])
            row = etape_ad_mod.summarize(df, label, ceiling)
            rows.append(row)
            forfeit_str = ""
            if label != "ref":
                parts = []
                for g in etape_ad_mod.PAYOUT_CYCLE_FIRMS:
                    pre_v = row.get(f"forfeited_pre_{g}", 0.0)
                    post_v = row.get(f"forfeited_post_{g}", 0.0)
                    parts.append(f"{g}=pre{pre_v:,.0f}$/post{post_v:,.0f}$")
                forfeit_str = " forfeit[" + " ".join(parts) + "]"
            print(f"[{label:8s} plafond={ceiling:.0f}$] profit={row['profit']:+,.0f}$ ruine={row['ruine']:.2f}% "
                  f"annee1<0={row['annee1_neg']:.2f}% (pre={row['annee1_neg_pre']:.2f}%) "
                  f"casse<=30j={row['break_rate_30d_pct']:.2f}%{forfeit_str} ({time.time()-t0:.0f}s)")
            pd.DataFrame(rows).to_csv(f"etape_ae_payout_ablations_n{n_sims}.csv", index=False)

    print(f"\nTermine en {time.time()-t_start:.0f}s.")
