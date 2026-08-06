"""
Rerun du point 2 (The5%ers isole, annee 1 vs horizon complet) avec le prix de
rachat realiste : 179$ seulement pendant les ~26 premiers jours (fin aout
2026, offre Summer Plan), 545$ ensuite (source : the5ers_pricing_engine.py).
Sensibilite testee a 21/26/35 jours pour couvrir l'incertitude "3-4 semaines".
"""
import time

import pandas as pd

from scaling_simulation import CORR_THRESHOLD, MAX_POSITIONS, load_market_data
from monte_carlo_simulation import precompute_correlation_pairs
from trailing_payoff_population import build_population_with_trailing
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
import the5ers_viability_scenarios as base
import the5ers_pricing_engine as eng

YEAR_SECONDS = 365.25 * 86400
BLOCK_MONTHS = 2
LOW_RISK, HIGH_RISK, RAMP_TRADES = 0.5, 2.0, 12

CUTOFF_DAYS_SENSITIVITY = [21, 26, 35]


def main():
    t_start = time.time()
    pop = build_population_with_trailing("fixed", 0.2, verbose=False)
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    rows = []
    for wr_label, wr_target, suffix in [("37.29%", None, "37_29pct"), ("32%", 0.32, "32pct")]:
        print(f"\n{'='*100}\nWINRATE {wr_label}\n{'='*100}")
        trades, slot_arrivals = base.build_population(pop, wr_target)
        total_horizon_seconds = slot_arrivals[-1]
        mark_seconds_list = [YEAR_SECONDS, total_horizon_seconds]
        block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
        blocks = build_blocks(trades, slot_arrivals, block_seconds)
        common_args = (trades, slot_arrivals, blocks, block_seconds, total_horizon_seconds,
                       mark_seconds_list, market_data, excluded_map)

        for n in [3, 4]:
            for cutoff_days in CUTOFF_DAYS_SENSITIVITY:
                t0 = time.time()
                df = eng.run_variant(*common_args, n_accounts=n, low_risk=LOW_RISK, high_risk=HIGH_RISK,
                                      ramp_trades=RAMP_TRADES, max_positions=MAX_POSITIONS,
                                      cutoff_seconds=cutoff_days * eng.DAY_SECONDS)
                df.to_csv(f"the5ers_N{n}_realpricing_cutoff{cutoff_days}d_{suffix}.csv", index=False)
                rows.append(dict(
                    n_accounts=n, winrate=wr_label, cutoff_days=cutoff_days,
                    profit_year1_moyen=df["year1_net"].mean(),
                    cash_worst_year1=df["year1_cash"].max(), cash_mean_year1=df["year1_cash"].mean(),
                    casses_moyennes_year1=df["year1_breaks"].mean(),
                    profit_final_moyen=df["final_net"].mean(),
                    cash_worst_final=df["final_cash"].max(),
                    casses_moyennes_final=df["final_breaks"].mean(),
                ))
                print(f"  N={n} cutoff={cutoff_days}j : profit an1 {df['year1_net'].mean():+,.0f}$ "
                      f"(vs ancien {'?':>0}) | cash pire cas an1 {df['year1_cash'].max():,.0f}$ | "
                      f"casses an1 {df['year1_breaks'].mean():.1f} | profit final {df['final_net'].mean():+,.0f}$ "
                      f"({time.time()-t0:.0f}s)")

    out = pd.DataFrame(rows)
    out.to_csv("the5ers_isolated_year1_realistic_pricing.csv", index=False)
    print(f"\nTerminé en {time.time()-t_start:.0f}s.")


if __name__ == "__main__":
    main()
