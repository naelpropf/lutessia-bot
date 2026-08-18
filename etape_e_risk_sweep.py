"""
Etape E, point 1 : re-balayage du risque sur le moteur integre
(etape_e_fleet_integration.py), separement pour la config REF (100% 2-step)
et la config WINNER (combo gagnant Etape D) -- les anciennes valeurs
verrouillees (eval 2,25%/flotte 2,75%/GFT 1,75%) avaient ete calibrees sur
l'ANCIEN moteur 1-phase flat (DD generique 8%/4j/10%), pas sur les vraies
contraintes DD par format (statique reel vs trailing).

Note structurelle : pour WINNER, GFT_InstantGOAT n'a AUCUNE phase
d'evaluation (finance des la creation) -- gft_eval_risk n'est donc jamais
utilise pour ce compte (aucun trade n'est joue en phase "challenge" pour un
compte deja "funded"). Le parametre reste passe pour simplicite d'API mais
n'a pas d'effet sous WINNER.

Grille reduite (temps de calcul) : eval_risk x fleet_risk, gft_eval_risk
fixe a 1,75% (valeur historique, non re-balayee separement dans cette
session -- reste pertinente pour REF ou GFT a une vraie phase d'evaluation ;
sans effet pour WINNER). n=100 (screening), un seul plafond (1000$, le plus
contraignant) pour ce balayage -- le plafond n'affecte pas fondamentalement
le risque optimal par trade, seulement le cash reellement injecte.
"""
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
from point_liquidity_rules import CORR_TH
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs

import etape_e_fleet_integration as ei

EVAL_GRID = [1.0, 1.25, 1.5, 1.75, 2.25, 2.75]
FLEET_GRID = [1.75, 2.25, 2.75, 3.25]
GFT_EVAL_RISK = 1.75
N_SIMS = 100
CEILING = 1000.0

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
        for eval_r in EVAL_GRID:
            for fleet_r in FLEET_GRID:
                t0 = time.time()
                df = ei.run_propagated(pop, market_data, excluded_map, CEILING, seq, config, ei.DEFAULT_EMERGENCY,
                                        eval_r, fleet_r, GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                                        ei.EXTRA_THRESHOLD_MULT, n_sims=N_SIMS, seed=42)
                net = df["final_net_split"] - df["is_paid_cum"]
                row = dict(config=label, eval_risk=eval_r, fleet_risk=fleet_r, profit=net.mean(),
                           ruine=(net < 0).sum() / len(df) * 100,
                           annee1_neg=(df["year1_net_split"] < 0).sum() / len(df) * 100,
                           mean_breaks=df["total_breaks"].mean())
                rows.append(row)
                print(f"[{label:7s}] eval={eval_r}% flotte={fleet_r}% profit={row['profit']:+,.0f}$ "
                      f"ruine={row['ruine']:.2f}% annee1<0={row['annee1_neg']:.2f}% breaks={row['mean_breaks']:.0f} "
                      f"({time.time()-t0:.0f}s)")
        pd.DataFrame(rows).to_csv("etape_e_risk_sweep_results.csv", index=False)

    pd.DataFrame(rows).to_csv("etape_e_risk_sweep_results.csv", index=False)
    print(f"\nTermine en {time.time()-t_start:.0f}s.")
