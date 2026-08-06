"""
Comparaison copytrade vs flotte diversifiée (2%/compte) pour les 2 configs de trailing
stop post-TP2 gagnantes (cf. trailing_stop_sweep.py) : distance fixe 0.5x SL et
retracement 10%. Comparé au payoff TP2 réaliste actuel (copytrade_vs_fleet_realistic_summary.csv).
"""
import random

import pandas as pd

import rr_threshold_test as rrt
from scaling_simulation import CORR_THRESHOLD, load_market_data
from monte_carlo_simulation import precompute_correlation_pairs, N_SIMULATIONS
from copytrade_simulation_test import (
    run_copytrade_one, summarize_copytrade, simulate_account_with_events, N_ACCOUNTS,
    build_block_bootstrap_order, BLOCK_MONTHS,
)
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from fleet_simulation_test import run_fleet_one, summarize_fleet, run_fleet_deterministic, CORR_THRESHOLD_FLEET
from trailing_payoff_population import build_population_with_trailing, build_trades_trailing, WINNING_CONFIGS

RISK_PCT = 2.0


def deterministic_copytrade_monthly(trades, slot_arrivals, risk_pct, market_data, excluded_map, start_date):
    natural_order = list(range(len(trades)))
    account_runs = [
        simulate_account_with_events(trades, slot_arrivals, natural_order, risk_pct, market_data, excluded_map, start_date)
        for _ in range(N_ACCOUNTS)
    ]
    combined_net_det = sum(r["net_profit"] for r in account_runs)
    all_events = []
    for r in account_runs:
        all_events.extend(r["events"])
    ev_df = pd.DataFrame(all_events, columns=["date", "net", "palier"])
    ev_df["month_index"] = ev_df["date"].apply(lambda d: (d.year - start_date.year) * 12 + (d.month - start_date.month))
    n_months = ev_df["month_index"].max() + 1
    palier_by_month = {}
    for i, r in enumerate(account_runs):
        acc_ev = pd.DataFrame(r["events"], columns=["date", "net", "palier"])
        acc_ev["month_index"] = acc_ev["date"].apply(lambda d: (d.year - start_date.year) * 12 + (d.month - start_date.month))
        palier_by_month[i] = acc_ev.groupby("month_index")["palier"].last().reindex(range(n_months)).ffill().bfill()
    combined_palier_by_month = sum(palier_by_month.values())
    monthly_net = ev_df.groupby("month_index")["net"].sum().reindex(range(n_months), fill_value=0.0)
    monthly_pct = monthly_net / combined_palier_by_month * 100
    return combined_net_det, monthly_pct.std(), monthly_pct.mean(), n_months


def deterministic_fleet_monthly(trades, slot_arrivals, risk_pct, market_data, excluded_map, start_date):
    accounts, events, n_taken_det, net_profit_det = run_fleet_deterministic(trades, slot_arrivals, risk_pct, market_data, excluded_map)
    ev_df = pd.DataFrame(events, columns=["date", "net", "combined_palier"])
    ev_df["month_index"] = ev_df["date"].apply(lambda d: (d.year - start_date.year) * 12 + (d.month - start_date.month))
    n_months = ev_df["month_index"].max() + 1
    monthly = ev_df.groupby("month_index").agg(net=("net", "sum"), palier_ref=("combined_palier", "last")).reindex(range(n_months))
    monthly["palier_ref"] = monthly["palier_ref"].ffill().bfill()
    monthly["net"] = monthly["net"].fillna(0.0)
    monthly_pct = monthly["net"] / monthly["palier_ref"] * 100
    return net_profit_det, monthly_pct.std(), monthly_pct.mean(), n_months, n_taken_det


def run_for_config(label, kind, param, market_data, corr_matrix):
    pop = build_population_with_trailing(kind, param, verbose=True)
    sub, trades, slot_arrivals = build_trades_trailing(pop)
    tickers = sorted(set(t["ticker"] for t in trades))
    excluded_map_ct = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)
    excluded_map_fl = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD_FLEET)
    start_date = sub["date_creation"].iloc[0]

    block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
    blocks = build_blocks(trades, slot_arrivals, block_seconds)
    total_horizon_seconds = slot_arrivals[-1]

    rng = random.Random(42)
    ct_results = []
    for _ in range(N_SIMULATIONS):
        trades_run, slots_run, order = build_block_bootstrap_order(
            trades, slot_arrivals, blocks, block_seconds, rng, total_horizon_seconds
        )
        ct_results.append(run_copytrade_one(trades_run, slots_run, RISK_PCT, market_data, excluded_map_ct, order))
    mc_ct = summarize_copytrade(ct_results)
    net_det_ct, std_ct, mean_ct, n_months_ct = deterministic_copytrade_monthly(
        trades, slot_arrivals, RISK_PCT, market_data, excluded_map_ct, start_date
    )
    taken_ct = rrt.taken_trades(pop, corr_matrix)
    pct_captes_ct = len(taken_ct) / len(sub) * 100

    rng = random.Random(42)
    fl_results = [run_fleet_one(trades, slot_arrivals, RISK_PCT, market_data, excluded_map_fl, rng) for _ in range(N_SIMULATIONS)]
    mc_fl = summarize_fleet(fl_results)
    mean_n_taken_fl = sum(r["n_taken"] for r in fl_results) / len(fl_results)
    net_det_fl, std_fl, mean_fl, n_months_fl, n_taken_det_fl = deterministic_fleet_monthly(
        trades, slot_arrivals, RISK_PCT, market_data, excluded_map_fl, start_date
    )

    print(f"\n{'='*100}\nCONFIG : {label}\n{'='*100}")
    print(f"COPYTRADE   : profit moyen {mc_ct['mean_profit']:+,.0f}€ | casses {mc_ct['mean_broken_count']:.2f} | "
          f"std mensuel {std_ct:.2f}% | captés {pct_captes_ct:.1f}%")
    print(f"FLOTTE DIV. : profit moyen {mc_fl['mean_profit']:+,.0f}€ | casses {mc_fl['mean_broken_count']:.2f} | "
          f"std mensuel {std_fl:.2f}% | captés {mean_n_taken_fl/len(sub)*100:.1f}%")

    return pd.DataFrame([
        {"config": label, "structure": "copytrade", "mean_profit": mc_ct["mean_profit"],
         "median_profit": mc_ct["median_profit"], "p5_profit": mc_ct["p5_profit"],
         "mean_broken_count": mc_ct["mean_broken_count"], "monthly_std_pct": std_ct,
         "pct_signaux_captes": pct_captes_ct},
        {"config": label, "structure": "flotte_diversifiee", "mean_profit": mc_fl["mean_profit"],
         "median_profit": mc_fl["median_profit"], "p5_profit": mc_fl["p5_profit"],
         "mean_broken_count": mc_fl["mean_broken_count"], "monthly_std_pct": std_fl,
         "pct_signaux_captes": mean_n_taken_fl / len(sub) * 100},
    ])


def main():
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)

    all_dfs = []
    for label, (kind, param) in WINNING_CONFIGS.items():
        all_dfs.append(run_for_config(label, kind, param, market_data, corr_matrix))

    combined = pd.concat(all_dfs, ignore_index=True)
    combined.to_csv("copytrade_vs_fleet_trailing_summary.csv", index=False)

    baseline = None
    try:
        baseline = pd.read_csv("copytrade_vs_fleet_realistic_summary.csv")
        baseline["config"] = "baseline_realiste_sans_trailing"
    except FileNotFoundError:
        pass

    print("\n" + "=" * 100)
    print("TABLEAU COMPARATIF FINAL")
    print("=" * 100)
    if baseline is not None:
        full = pd.concat([baseline, combined], ignore_index=True)
    else:
        full = combined
    print(full.to_string(index=False))
    print("\nRésumé enregistré dans copytrade_vs_fleet_trailing_summary.csv")
    return combined


if __name__ == "__main__":
    main()
