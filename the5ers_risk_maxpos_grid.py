"""
Point 4 de la relance d'analyse viabilite The5%ers : balayage systematique
risque x maxpos sur les comptes The5%ers (4 comptes 100k, daily DD 3% reel,
horizon complet ~3.96 ans), façon grille de calibration (cf. trailing stop).

Grille : risque par trade in {2%, 1.5%, 1%, 0.75%, 0.5%} (flat, pas de ramp,
pour isoler proprement l'effet du niveau de risque) x maxpos in {1, 2, 3}
= 15 combinaisons, testees en winrate 37.29% et 32%.

Pour chaque combinaison : moteur 5ers-seul (the5ers_viability_scenarios.run_5ers_fleet)
puis recombinaison exacte avec le segment croissance FTMO/Blueberry (meme tirage
aleatoire block-bootstrap par run, cf. growth_only_cash_*.csv et
three_firm_fleet_dailydd_*.csv deja produits) pour obtenir les chiffres flotte
complete sans avoir a rejouer le segment croissance a chaque fois.
"""
import time

import pandas as pd

from scaling_simulation import (
    MAX_POSITIONS as DEFAULT_MAX_POSITIONS, CORR_THRESHOLD, load_market_data,
)
from monte_carlo_simulation import precompute_correlation_pairs, N_SIMULATIONS
from trailing_payoff_population import build_population_with_trailing
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
import the5ers_viability_scenarios as base

YEAR_SECONDS = 365.25 * 86400
BLOCK_MONTHS = 2
PALIER_100K = 100000
CHALLENGE_COST_100K = 179

RISK_GRID = [2.0, 1.5, 1.0, 0.75, 0.5]
MAXPOS_GRID = [1, 2, 3]


def main():
    t_start = time.time()
    pop = build_population_with_trailing("fixed", 0.2, verbose=False)
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    rows_5ers_only = []
    rows_flotte = []

    for wr_label, wr_target, suffix in [("37.29%", None, "37_29pct"), ("32%", 0.32, "32pct")]:
        print(f"\n{'='*100}\nWINRATE {wr_label}\n{'='*100}")
        trades, slot_arrivals = base.build_population(pop, wr_target)
        total_horizon_seconds = slot_arrivals[-1]
        mark_seconds_list = [YEAR_SECONDS, total_horizon_seconds]
        block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
        blocks = build_blocks(trades, slot_arrivals, block_seconds)
        common_args = (trades, slot_arrivals, blocks, block_seconds, total_horizon_seconds,
                       mark_seconds_list, market_data, excluded_map)

        gc = pd.read_csv(f"growth_only_cash_{suffix}.csv")
        g = pd.read_csv(f"three_firm_fleet_dailydd_{suffix}.csv")

        for risk in RISK_GRID:
            for maxpos in MAXPOS_GRID:
                t0 = time.time()
                df = base.run_variant(*common_args, n_accounts=4, palier=PALIER_100K,
                                       challenge_cost=CHALLENGE_COST_100K, daily_loss_pct=3.0,
                                       low_risk=risk, high_risk=risk, ramp_trades=0,
                                       max_positions=maxpos)
                tag = f"risk{str(risk).replace('.','_')}_maxpos{maxpos}_{suffix}"
                df.to_csv(f"grid_5ers_{tag}.csv", index=False)

                year1_f = g["year1_net_growth"] + df["year1_net"]
                final_f = g["final_net_growth"] + df["final_net"]
                cash_f = gc["final_cash_growth"] + df["final_cash"]
                breaks_f = gc["final_breaks_growth"] + df["final_breaks"]

                rows_5ers_only.append(dict(
                    winrate=wr_label, risk_pct=risk, maxpos=maxpos,
                    profit_year1=df["year1_net"].mean(), profit_final=df["final_net"].mean(),
                    cash_worst=df["final_cash"].max(), casses_final=df["final_breaks"].mean(),
                ))
                rows_flotte.append(dict(
                    winrate=wr_label, risk_pct=risk, maxpos=maxpos,
                    profit_year1=year1_f.mean(), profit_final=final_f.mean(),
                    cash_worst=cash_f.max(), casses_final=breaks_f.mean(),
                ))
                print(f"  risk={risk}% maxpos={maxpos} : 5ers seul profit final {df['final_net'].mean():+,.0f}$ "
                      f"casses {df['final_breaks'].mean():.1f} | flotte profit final {final_f.mean():+,.0f}$ "
                      f"casses {breaks_f.mean():.1f} cash_worst {cash_f.max():,.0f}$ ({time.time()-t0:.0f}s)")

    df5 = pd.DataFrame(rows_5ers_only)
    dff = pd.DataFrame(rows_flotte)
    df5.to_csv("grid_5ers_only_summary.csv", index=False)
    dff.to_csv("grid_flotte_summary.csv", index=False)
    print(f"\nTerminé en {time.time()-t_start:.0f}s.")


if __name__ == "__main__":
    main()
