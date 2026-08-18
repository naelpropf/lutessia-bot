"""
Suite de risk_sweep_and_year1.py : la grille eval x flotte deja testee n'avait
mesure que profit final + ruine finale, jamais P(annee1<0) par combo -- alors
que la casse seche en evaluation (qui domine le debut de trajectoire, cf.
diagnostic du plateau) devrait toucher l'annee 1 de facon disproportionnee
par rapport a son effet sur le profit/ruine finale (dilues par ~4 ans de
compounding). Ce script ajoute P(annee1<0) sur la MEME grille (eval in
[1.25,1.5,1.75,2.0,2.25] -- 2.5% exclu, mur de ruine deja identifie ; flotte
in [2.0,2.25,2.5,2.75,3.0]), meme config finale (reserve 30k+amorcage 300+
downgrade Blueberry pre-deblocage+split 80% flat+IS reel+RESERVE_SHARE 95%),
n=300 pour la grille puis confirmation n=600 du meilleur compromis sur les
3 metriques simultanement.

Reutilise le moteur de risk_sweep_and_year1.py tel quel (run_one/run_propagated
identiques), capture_year1=True active sur TOUTE la grille (pas seulement la
confirmation finale).
"""
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
from point_liquidity_rules import CORR_TH
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs
from risk_sweep_and_year1 import run_propagated, DEFAULT_RESERVE, DEFAULT_EMERGENCY, FINAL_RESERVE_SHARE

if __name__ == "__main__":
    import sys
    t_start = time.time()
    n_sims_grid = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    n_sims_confirm = int(sys.argv[2]) if len(sys.argv) > 2 else 600

    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

    eval_risks = [1.25, 1.5, 1.75, 2.0, 2.25]  # 2.5% exclu -- mur de ruine deja identifie
    fleet_risks = [2.0, 2.25, 2.5, 2.75, 3.0]

    print("\n" + "=" * 100 + f"\nPARTIE 1 -- GRILLE eval x flotte AVEC P(ANNEE1<0) (config finale, n={n_sims_grid})\n" + "=" * 100)
    grid_rows = []
    for ceiling in (1000.0, 3000.0):
        print(f"\n--- Plafond {ceiling:.0f}$ ---")
        for er in eval_risks:
            for fr in fleet_risks:
                t0 = time.time()
                df = run_propagated(pop, market_data, excluded_map, ceiling, DEFAULT_RESERVE, DEFAULT_EMERGENCY,
                                     fr, er, FINAL_RESERVE_SHARE, n_sims_grid, seed=4000, capture_year1=True)
                net_split_is = df["final_net_split"] - df["is_paid_cum"]
                n_ruin = (net_split_is < 0).sum()
                n_y1_neg = (df["year1_net_split"] < 0).sum()
                row = dict(ceiling=ceiling, eval_risk=er, fleet_risk=fr,
                           profit_net_split_is_mean=net_split_is.mean(),
                           p_ruine_pct=n_ruin / len(df) * 100,
                           p_annee1_neg_pct=n_y1_neg / len(df) * 100,
                           delai_deblocage_median=df["reserve_hit_30k_month"].median())
                grid_rows.append(row)
                print(f"[eval={er}% fleet={fr}%] profit={row['profit_net_split_is_mean']:+,.0f}$ | "
                      f"ruine_finale={row['p_ruine_pct']:.2f}% | P(annee1<0)={row['p_annee1_neg_pct']:.2f}% "
                      f"({time.time()-t0:.0f}s)")
        pd.DataFrame(grid_rows).to_csv("year1_risk_sweep_grid.csv", index=False)
    grid_df = pd.DataFrame(grid_rows)
    grid_df.to_csv("year1_risk_sweep_grid.csv", index=False)

    print("\n" + "=" * 100 + "\nZONE OPTIMALE POUR MINIMISER P(ANNEE1<0)\n" + "=" * 100)
    best_combo_by_ceiling = {}
    for ceiling in (1000.0, 3000.0):
        sub = grid_df[grid_df["ceiling"] == ceiling].copy()
        print(f"\n--- Plafond {ceiling:.0f}$ ---")
        abs_min = sub.loc[sub["p_annee1_neg_pct"].idxmin()]
        print(f"  Minimum absolu P(annee1<0) : eval={abs_min['eval_risk']}% fleet={abs_min['fleet_risk']}% -> "
              f"P(annee1<0)={abs_min['p_annee1_neg_pct']:.2f}% | ruine_finale={abs_min['p_ruine_pct']:.2f}% | "
              f"profit={abs_min['profit_net_split_is_mean']:+,.0f}$")

        # recherche du "coude" : parmi les combos eval=1.25% (le plus protecteur en eval),
        # celui qui maximise le profit sans perdre le benefice du P(annee1<0) minimal
        sub_e125 = sub[sub["eval_risk"] == 1.25].sort_values("fleet_risk")
        print(f"  Effet du risque flotte a eval=1,25% fixe (le plus protecteur) :")
        for _, r in sub_e125.iterrows():
            print(f"    fleet={r['fleet_risk']}% -> P(annee1<0)={r['p_annee1_neg_pct']:.2f}% | "
                  f"ruine={r['p_ruine_pct']:.2f}% | profit={r['profit_net_split_is_mean']:+,.0f}$")
        best_at_e125 = sub_e125.loc[sub_e125["profit_net_split_is_mean"].idxmax()]
        best_combo_by_ceiling[ceiling] = (best_at_e125["eval_risk"], best_at_e125["fleet_risk"])
        print(f"  Meilleur compromis retenu (eval=1,25% fixe, profit max) : "
              f"eval={best_at_e125['eval_risk']}% fleet={best_at_e125['fleet_risk']}% -> "
              f"P(annee1<0)={best_at_e125['p_annee1_neg_pct']:.2f}% | profit={best_at_e125['profit_net_split_is_mean']:+,.0f}$")

        print(f"\n  Verification hypothese -- effet du risque EVAL isole (fleet=2,75% fixe) :")
        sub_f275 = sub[sub["fleet_risk"] == 2.75].sort_values("eval_risk")
        for _, r in sub_f275.iterrows():
            print(f"    eval={r['eval_risk']}% -> P(annee1<0)={r['p_annee1_neg_pct']:.2f}% | "
                  f"ruine_finale={r['p_ruine_pct']:.2f}% | profit={r['profit_net_split_is_mean']:+,.0f}$")
        print(f"  Verification hypothese -- effet du risque FLOTTE isole (eval=2,0% fixe) :")
        sub_e20 = sub[sub["eval_risk"] == 2.0].sort_values("fleet_risk")
        for _, r in sub_e20.iterrows():
            print(f"    fleet={r['fleet_risk']}% -> P(annee1<0)={r['p_annee1_neg_pct']:.2f}% | "
                  f"ruine_finale={r['p_ruine_pct']:.2f}% | profit={r['profit_net_split_is_mean']:+,.0f}$")

    print("\nPartie 1 terminee -- selection manuelle du combo a confirmer avant partie 2 "
          "(cf. analyse du coude), pas d'auto-pick aveugle sur une heuristique fixe.")
    print(f"\nTermine en {time.time()-t_start:.0f}s.")
