"""
Etape AF (08/11) : mesure l'impact du remplacement du fichier historique
stale (historique_lutessia_15k.csv, 646 trades filtres, arrete au 27/07)
par le fichier a jour (historique_lutessia_15k_force.csv, 721 trades
filtres, jusqu'au 30/07, disponible depuis le 01/08) -- point ouvert #2
de registre_strategie_trading.md.

Patch rr_threshold_test.HIST_PATH avant l'appel a build_population_with_
trailing (meme convention min_rr=1.25 que partout ailleurs dans le
moteur) puis relance les DEUX drivers de reference officiels avec seed=
9999 (comparable aux baselines n=300 deja enregistrees) :
- 1000$ : REF_V2_combine (etape_q_v2_plus_ftmo_gft_2026-08-10.py), meme
  config que etape_v_blueberry_cap_retest_driver.py -- baseline 646
  trades deja dans etape_v_refv2_apres_n300.csv.
- 3000$ : solo_BB REF pure (etape_t_piste_a_prime_2x_blueberry_2026-08-10
  .py) -- baseline 646 trades deja dans etape_t_piste_a_prime_n300.csv.

N'importe pas ce script directement (convention du projet).
"""
import importlib.util
import sys
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
import rr_threshold_test as rrt
from point_liquidity_rules import CORR_TH
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs
import etape_e_fleet_integration as ei

NEW_HIST_PATH = "historique_lutessia_15k_force.csv"


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


if __name__ == "__main__":
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    t_start = time.time()

    print(f"[verif] HIST_PATH avant patch = {rrt.HIST_PATH}")
    rrt.HIST_PATH = NEW_HIST_PATH
    print(f"[verif] HIST_PATH apres patch = {rrt.HIST_PATH}")

    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=True)
    print(f"[verif] population construite : {len(pop)} trades (attendu ~721 filtres)")

    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)
    seq = ei.seq_grouped_multi(1000, 15000, 25000, 25000)
    config = ei.CONFIG_REF
    EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK = 1.25, 1.90, 1.75

    rows = []

    # --- 1000$ : REF_V2_combine (reference officielle a ce plafond) ---
    etape_q_mod = load_module("etape_q_v2_plus_ftmo_gft_2026-08-10.py", "etape_q_mod")
    t0 = time.time()
    df = etape_q_mod.run_propagated(pop, market_data, excluded_map, 1000.0, seq, config, ei.DEFAULT_EMERGENCY,
                                     EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                                     ei.EXTRA_THRESHOLD_MULT, n_sims=n_sims, seed=9999,
                                     b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True,
                                     ftmo_discount=True, gft_goat_guard=True)
    row = etape_q_mod.summarize(df, "REF_V2_combine_pop721", 1000.0)
    rows.append(row)
    print(f"[1000$ pop721] profit={row['profit']:+,.0f}$ ruine={row['ruine']:.2f}% "
          f"annee1<0={row['annee1_neg']:.2f}% (pre={row['annee1_neg_pre']:.2f}%) ({time.time()-t0:.0f}s)")

    # --- 3000$ : solo_BB REF pure (reference officielle a ce plafond) ---
    etape_t_mod = load_module("etape_t_piste_a_prime_2x_blueberry_2026-08-10.py", "etape_t_mod")
    starters, starter_count = etape_t_mod.COMBOS["solo_BB"]
    t0 = time.time()
    df2 = etape_t_mod.run_propagated(pop, market_data, excluded_map, 3000.0, seq, config, ei.DEFAULT_EMERGENCY,
                                      EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                                      ei.EXTRA_THRESHOLD_MULT, n_sims=n_sims, seed=9999,
                                      starters=starters, starter_count=starter_count)
    row2 = etape_t_mod.summarize(df2, "solo_BB_pop721", 3000.0)
    rows.append(row2)
    print(f"[3000$ pop721] profit={row2['profit']:+,.0f}$ ruine={row2['ruine']:.2f}% "
          f"annee1<0={row2['annee1_neg']:.2f}% (pre={row2['annee1_neg_pre']:.2f}%) ({time.time()-t0:.0f}s)")

    pd.DataFrame(rows).to_csv(f"etape_af_pop721_impact_n{n_sims}.csv", index=False)
    print(f"\nTermine en {time.time()-t_start:.0f}s.")
