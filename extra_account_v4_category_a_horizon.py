"""
Session 08/08 (suite, jour 3) -- Objectif 2 : le trou plus profond de la
categorie A a 12 mois sous le mecanisme echelonne (deficit moyen individuel
-59 688$->-91 900$ observe dans project_staggered_unlock_2026-08-08b) est-il
un ARTEFACT DE MESURE (retard de compounding qui se rattrape sur l'horizon
complet, ~3.96 ans) ou un VRAI RISQUE (le coussin de reserve plus fin post-
deblocage absorbe moins bien les chocs suivants, ces runs finissent
structurellement moins bien) ?

Methode : appariement par indice de run. run_propagated (baseline comme
echelonne) consomme les generateurs aleatoires (rng_wr, rng_boot) dans un
ordre FIXE, identique quel que soit le contenu de seq_grouped -- seul
run_one() (deterministe, aucun appel random a l'interieur) differe selon le
mecanisme de deblocage. Donc pour un meme seed=4000 et un meme indice de
simulation i (0..n_sims-1), le tirage de trades/marche est IDENTIQUE entre
les deux configs : on peut comparer directement "le meme tirage de malchance,
sous les deux configs" -- un vrai contrefactuel, pas deux populations
differentes.

Pour les runs classes categorie A (year1_net_split<0 ET year1_fleet_unlocked)
sous CHAQUE config separement, compare le profit net final a l'horizon
complet (final_net_split - is_paid_cum, deja net split+IS) entre baseline et
echelonne, sur CES MEMES indices de run.
"""
import time

import numpy as np
import pandas as pd

import robustness_5ers_risk_challenge as eng
from point_liquidity_rules import CORR_TH
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs
from extra_account_v4_multi_stagger_diagnosis import (run_propagated, seq_grouped_multi, DEFAULT_EMERGENCY,
                                                        FINAL_FLEET_RISK, FINAL_EVAL_RISK, FINAL_GFT_EVAL_RISK,
                                                        FINAL_RESERVE_SHARE, EXTRA_THRESHOLD_MULT)

BASELINE_COMBO = (30000., 30000., 30000., 30000.)


def summarize(label, s):
    if len(s) == 0:
        print(f"    {label} : aucun run")
        return
    print(f"    {label} : n={len(s)} | moy={s.mean():+,.0f}$ | median={s.median():+,.0f}$ | "
          f"p10={np.percentile(s, 10):+,.0f}$ | p90={np.percentile(s, 90):+,.0f}$")


if __name__ == "__main__":
    import sys
    t_start = time.time()
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    if len(sys.argv) > 2:
        t_f, t_v, t_g, t_n = [float(x) * 1000 for x in sys.argv[2].split("-")]
        ech_combo = (t_f, t_v, t_g, t_n)
    else:
        ech_combo = (5000., 15000., 25000., 30000.)

    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

    for ceiling in (1000.0, 3000.0):
        print(f"\n{'='*100}\nPlafond {ceiling:.0f}$ (n={n_sims}) -- baseline vs echelonne "
              f"{ech_combo[0]/1000:.1f}/{ech_combo[1]/1000:.1f}/{ech_combo[2]/1000:.1f}/{ech_combo[3]/1000:.1f}k\n{'='*100}")

        seq_base = seq_grouped_multi(*BASELINE_COMBO)
        df_base = run_propagated(pop, market_data, excluded_map, ceiling, seq_base, DEFAULT_EMERGENCY,
                                  FINAL_FLEET_RISK, FINAL_EVAL_RISK, FINAL_GFT_EVAL_RISK, FINAL_RESERVE_SHARE,
                                  EXTRA_THRESHOLD_MULT, n_sims, seed=4000)
        seq_ech = seq_grouped_multi(*ech_combo)
        df_ech = run_propagated(pop, market_data, excluded_map, ceiling, seq_ech, DEFAULT_EMERGENCY,
                                 FINAL_FLEET_RISK, FINAL_EVAL_RISK, FINAL_GFT_EVAL_RISK, FINAL_RESERVE_SHARE,
                                 EXTRA_THRESHOLD_MULT, n_sims, seed=4000)

        df_base["final_profit"] = df_base["final_net_split"] - df_base["is_paid_cum"]
        df_ech["final_profit"] = df_ech["final_net_split"] - df_ech["is_paid_cum"]
        df_base["run_id"] = range(len(df_base))
        df_ech["run_id"] = range(len(df_ech))

        cat_a_base_idx = df_base.index[(df_base["year1_net_split"] < 0) & (df_base["year1_fleet_unlocked"])]
        cat_a_ech_idx = df_ech.index[(df_ech["year1_net_split"] < 0) & (df_ech["year1_fleet_unlocked"])]

        print(f"\n  Categorie A sous BASELINE : {len(cat_a_base_idx)}/{n_sims} runs")
        print(f"  Categorie A sous ECHELONNE : {len(cat_a_ech_idx)}/{n_sims} runs")

        print(f"\n  --- Runs categorie A SOUS BASELINE (memes tirages), profit final horizon complet ---")
        summarize("profit final sous baseline (config d'origine)", df_base.loc[cat_a_base_idx, "final_profit"])
        summarize("profit final sous echelonne (meme tirage, config alternative)",
                   df_ech.loc[cat_a_base_idx, "final_profit"])
        delta = df_ech.loc[cat_a_base_idx, "final_profit"].values - df_base.loc[cat_a_base_idx, "final_profit"].values
        print(f"    delta (echelonne - baseline) sur ces memes runs : moy={delta.mean():+,.0f}$ | "
              f"median={np.median(delta):+,.0f}$ | p10={np.percentile(delta, 10):+,.0f}$ | "
              f"%runs ou echelonne fait MIEUX={100*(delta > 0).mean():.1f}%")

        print(f"\n  --- Runs categorie A SOUS ECHELONNE (memes tirages), profit final horizon complet ---")
        summarize("profit final sous baseline (meme tirage, config alternative)",
                   df_base.loc[cat_a_ech_idx, "final_profit"])
        summarize("profit final sous echelonne (config d'origine)", df_ech.loc[cat_a_ech_idx, "final_profit"])
        delta2 = df_ech.loc[cat_a_ech_idx, "final_profit"].values - df_base.loc[cat_a_ech_idx, "final_profit"].values
        print(f"    delta (echelonne - baseline) sur ces memes runs : moy={delta2.mean():+,.0f}$ | "
              f"median={np.median(delta2):+,.0f}$ | p10={np.percentile(delta2, 10):+,.0f}$ | "
              f"%runs ou echelonne fait MIEUX={100*(delta2 > 0).mean():.1f}%")

        df_base.to_csv(f"extra_account_v4_category_a_horizon_base_ceiling{int(ceiling)}.csv", index=False)
        df_ech.to_csv(f"extra_account_v4_category_a_horizon_ech_ceiling{int(ceiling)}.csv", index=False)

    print(f"\nTermine en {time.time()-t_start:.0f}s.")
