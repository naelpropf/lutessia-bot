"""
Décomposition année par année (1/2/3/4), régime hybride 0.5%->2%@5000€, réserve
poolée + immunité perso post-financement (bad_year1_recovery_pooled_reserve.py) --
CETTE FOIS pour les DEUX sous-ensembles côte à côte : année 1 positive (cas normal,
~82.6% des runs) ET année 1 négative (cas déjà traité), pour comparaison directe.
"""
import random

import pandas as pd

from scaling_simulation import CORR_THRESHOLD, load_market_data
from monte_carlo_simulation import precompute_correlation_pairs, N_SIMULATIONS
from trailing_payoff_population import build_population_with_trailing, build_trades_trailing
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from bad_year1_recovery_pooled_reserve import run_fleet_multi_mark_pooled

YEAR_SECONDS = 365.25 * 86400
BLOCK_MONTHS = 2
YEAR_MARKS = [1, 2, 3, 4]


def main():
    pop = build_population_with_trailing("fixed", 0.2, verbose=False)
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    sub, trades, slot_arrivals = build_trades_trailing(pop)
    tickers = sorted(set(t["ticker"] for t in trades))
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
    blocks = build_blocks(trades, slot_arrivals, block_seconds)

    year_marks_seconds = [y * YEAR_SECONDS for y in YEAR_MARKS]
    target_duration = max(YEAR_MARKS) * YEAR_SECONDS

    rng = random.Random(42)
    rows = []
    for _ in range(N_SIMULATIONS):
        synthetic_trades, synthetic_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, target_duration)
        order = list(range(len(synthetic_trades)))
        snaps = run_fleet_multi_mark_pooled(synthetic_trades, synthetic_slots, market_data, excluded_map, order, year_marks_seconds)
        row = {}
        for i, y in enumerate(YEAR_MARKS):
            row[f"year{y}_net"] = snaps[i][1]
        rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv("year1_outcome_recovery_full_detail.csv", index=False)

    n = len(df)
    positive = df[df["year1_net"] >= 0]
    negative = df[df["year1_net"] < 0]

    print("=" * 100)
    print(f"RÉGIME HYBRIDE 0.5%->2%@5000€ -- réserve poolée + immunité perso -- {n} runs")
    print("=" * 100)
    print(f"Année 1 POSITIVE : {len(positive)}/{n} ({len(positive)/n*100:.1f}%)")
    print(f"Année 1 NÉGATIVE : {len(negative)}/{n} ({len(negative)/n*100:.1f}%)")

    def report(subset, label):
        print(f"\n{'='*100}\nSOUS-ENSEMBLE : {label} (n={len(subset)})\n{'='*100}")
        for y in YEAR_MARKS:
            col = f"year{y}_net"
            vals = subset[col]
            mean_v, median_v = vals.mean(), vals.median()
            p5, p95 = vals.quantile(0.05), vals.quantile(0.95)
            print(f"Fin année {y} : moyenne {mean_v:+,.0f}€ | médiane {median_v:+,.0f}€ | "
                  f"P5 {p5:+,.0f}€ | P95 {p95:+,.0f}€")

    report(positive, "ANNÉE 1 POSITIVE (cas normal)")
    report(negative, "ANNÉE 1 NÉGATIVE (cas dégradé, déjà vu)")

    print(f"\nDétail (2000 runs, 4 marques annuelles) enregistré dans year1_outcome_recovery_full_detail.csv")


if __name__ == "__main__":
    main()
