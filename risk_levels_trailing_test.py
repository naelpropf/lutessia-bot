"""
Tableau des niveaux de risque (0.5/1/1.5/2/3%), copytrade 3 comptes, pour les 2 configs
de trailing stop post-TP2 identifiées par trailing_stop_sweep.py comme battant TP2 sec :
  - distance fixe 0.5x la distance SL initiale
  - retracement 10% du gain depuis l'entrée
Comparé au payoff TP2 réaliste actuel (sans trailing, risk_levels_realistic_summary.csv).
"""
import random

import pandas as pd

from scaling_simulation import CORR_THRESHOLD, load_market_data
from monte_carlo_simulation import precompute_correlation_pairs, N_SIMULATIONS
from copytrade_simulation_test import run_copytrade_one, summarize_copytrade, build_block_bootstrap_order, BLOCK_MONTHS
from copytrade_risk_levels_test import run_deterministic_monthly_std
from trailing_payoff_population import build_population_with_trailing, build_trades_trailing, WINNING_CONFIGS
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH

RISK_LEVELS = [0.5, 1.0, 1.5, 2.0, 3.0]


def run_for_config(label, kind, param, market_data, corr_matrix, baseline_df):
    pop = build_population_with_trailing(kind, param, verbose=True)
    sub, trades, slot_arrivals = build_trades_trailing(pop)
    tickers = sorted(set(t["ticker"] for t in trades))
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)
    start_date = sub["date_creation"].iloc[0]

    block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
    blocks = build_blocks(trades, slot_arrivals, block_seconds)
    total_horizon_seconds = slot_arrivals[-1]

    print(f"\n{'='*100}\nCONFIG : {label}\n{'='*100}")
    rows = []
    for risk_pct in RISK_LEVELS:
        rng = random.Random(42)
        results = []
        for _ in range(N_SIMULATIONS):
            trades_run, slots_run, order = build_block_bootstrap_order(
                trades, slot_arrivals, blocks, block_seconds, rng, total_horizon_seconds
            )
            results.append(run_copytrade_one(trades_run, slots_run, risk_pct, market_data, excluded_map, order))
        mc = summarize_copytrade(results)
        combined_net_det, monthly_std, monthly_mean, n_months, cum_net = run_deterministic_monthly_std(
            trades, slot_arrivals, risk_pct, market_data, excluded_map, start_date
        )
        row = {"config": label, "risk_pct_per_account": risk_pct, **mc,
               "monthly_std_pct": monthly_std, "monthly_mean_pct": monthly_mean,
               "net_profit_deterministic": combined_net_det}

        base_row = baseline_df[baseline_df["risk_pct_per_account"] == risk_pct]
        if not base_row.empty:
            base_mean = base_row["mean_profit"].iloc[0]
            row["baseline_realiste_mean_profit"] = base_mean
            row["ratio_vs_baseline"] = mc["mean_profit"] / base_mean if base_mean else float("nan")
        rows.append(row)

        print(f"Risque {risk_pct}% : profit moyen {mc['mean_profit']:+,.0f}€ | médian {mc['median_profit']:+,.0f}€ | "
              f"p5 {mc['p5_profit']:+,.0f}€ | casses {mc['mean_broken_count']:.2f} | std mensuel {monthly_std:.2f}%"
              + (f" | ratio vs baseline x{row['ratio_vs_baseline']:.3f}" if "ratio_vs_baseline" in row else ""))

    return pd.DataFrame(rows)


def main():
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)

    try:
        baseline_df = pd.read_csv("risk_levels_realistic_summary.csv")
    except FileNotFoundError:
        baseline_df = pd.DataFrame(columns=["risk_pct_per_account", "mean_profit"])

    all_dfs = []
    for label, (kind, param) in WINNING_CONFIGS.items():
        df = run_for_config(label, kind, param, market_data, corr_matrix, baseline_df)
        all_dfs.append(df)

    combined = pd.concat(all_dfs, ignore_index=True)
    combined.to_csv("risk_levels_trailing_summary.csv", index=False)

    print("\n" + "=" * 100)
    print("TABLEAU COMPARATIF FINAL — payoff réaliste (baseline) vs 2 configs trailing")
    print("=" * 100)
    cols = ["config", "risk_pct_per_account", "mean_profit", "median_profit", "p5_profit",
            "mean_broken_count", "monthly_std_pct", "ratio_vs_baseline"]
    print(combined[cols].to_string(index=False))
    print("\nRésumé enregistré dans risk_levels_trailing_summary.csv")
    return combined


if __name__ == "__main__":
    main()
