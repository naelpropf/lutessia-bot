"""
Rerun du point 4 (grille risque x maxpos sur The5%ers) avec le prix de rachat
realiste : 179$ pendant les 26 premiers jours (fin aout 2026, offre Summer
Plan), 545$ ensuite (source : the5ers_pricing_engine.py). Meme grille que
the5ers_risk_maxpos_grid.py (risque flat in {2,1.5,1,0.75,0.5}% x maxpos in
{1,2,3}), recombinee avec le segment croissance FTMO/Blueberry inchange.
"""
import time

import pandas as pd

from scaling_simulation import CORR_THRESHOLD, load_market_data
from monte_carlo_simulation import precompute_correlation_pairs
from trailing_payoff_population import build_population_with_trailing
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
import the5ers_viability_scenarios as base
import the5ers_pricing_engine as eng

YEAR_SECONDS = 365.25 * 86400
BLOCK_MONTHS = 2
CUTOFF_SECONDS = 26 * eng.DAY_SECONDS  # fin aout 2026

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
                df = eng.run_variant(*common_args, n_accounts=4, low_risk=risk, high_risk=risk,
                                      ramp_trades=0, max_positions=maxpos, cutoff_seconds=CUTOFF_SECONDS)
                tag = f"risk{str(risk).replace('.','_')}_maxpos{maxpos}_{suffix}"
                df.to_csv(f"gridrp_5ers_{tag}.csv", index=False)

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
    df5.to_csv("gridrp_5ers_only_summary.csv", index=False)
    dff.to_csv("gridrp_flotte_summary.csv", index=False)
    print(f"\nTerminé en {time.time()-t_start:.0f}s.")


if __name__ == "__main__":
    main()
