"""
Version corrigée de the5ers_summer_100k_N_accounts_test.py : ajoute la limite de
perte JOURNALIÈRE réelle du plan Summer The5%ers (3%, confirmé officiellement) en
plus du drawdown trailing 10% déjà modélisé. Voir daily_dd_threshold_verification.py
pour la démonstration du bug sur la trajectoire réelle (+70.6% de casses à 100k/2%).

Perte journalière = P&L réalisé agrégé des trades qui se clôturent le même jour
SIMULÉ (index synthétique close_time//86400 -- pas la date calendaire d'origine du
trade, rebrassée par le block bootstrap). Reste sinon identique au script original.
"""
import random

import pandas as pd

from scaling_simulation import (
    CHALLENGE_TARGET_PCT, MIN_TRADING_DAYS, BREAK_DD_PCT, RESERVE_SHARE,
    MAX_POSITIONS, CORR_THRESHOLD, feasible_risk_pct, load_market_data,
)
from monte_carlo_simulation import precompute_correlation_pairs, N_SIMULATIONS
from trailing_payoff_population import build_population_with_trailing, build_trades_trailing
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from winrate_sensitivity_test import build_degraded_trades, DEGRADE_SEED

YEAR_SECONDS = 365.25 * 86400
BLOCK_MONTHS = 2
LOW_RISK, HIGH_RISK = 0.5, 2.0
RAMP_TRADES = 12

PALIER_100K = 100000
CHALLENGE_COST_100K = 179
DAILY_LOSS_PCT = 3.0  # The5%ers Summer Plan (confirmé officiellement)

N_VARIANTS = [3, 4]


def run_fleet_100k(trades, slot_arrivals, market_data, excluded_map, order, n_accounts, mark_seconds_list):
    accounts = []
    for _ in range(n_accounts):
        accounts.append({
            "phase": "challenge", "cumulative_since_reset": 0.0,
            "peak_since_reset": 0.0, "trading_days_since_reset": set(), "open_positions": [],
            "total_funded_pnl": 0.0, "total_fees_paid": CHALLENGE_COST_100K,
            "trades_taken": 0, "daily_pnl": {},
        })
    reserve = 0.0
    ever_funded = False
    real_cash_paid = CHALLENGE_COST_100K * n_accounts
    total_breaks = 0

    marks_sorted = sorted(mark_seconds_list)
    mark_idx = 0
    snapshots = []

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]

        while mark_idx < len(marks_sorted) and now > marks_sorted[mark_idx]:
            combined_net = sum(a["total_funded_pnl"] - a["total_fees_paid"] for a in accounts)
            snapshots.append((marks_sorted[mark_idx], combined_net, real_cash_paid, total_breaks))
            mark_idx += 1

        for acc in accounts:
            close_time = now + trade["hold_seconds"]
            acc["open_positions"] = [(t, c) for (t, c) in acc["open_positions"] if c > now]
            if len(acc["open_positions"]) >= MAX_POSITIONS:
                continue
            if any(t in excluded_map[trade["ticker"]] for (t, _) in acc["open_positions"]):
                continue

            current_risk = LOW_RISK if acc["trades_taken"] < RAMP_TRADES else HIGH_RISK
            eff_risk, _ = feasible_risk_pct(trade["ticker"], trade["sl_distance"], PALIER_100K, current_risk, market_data)
            risk_amount = eff_risk / 100 * PALIER_100K
            pnl = trade["outcome_r"] * risk_amount

            acc["open_positions"].append((trade["ticker"], close_time))
            acc["cumulative_since_reset"] += pnl
            acc["peak_since_reset"] = max(acc["peak_since_reset"], acc["cumulative_since_reset"])
            acc["trading_days_since_reset"].add(int(now // 86400))
            acc["trades_taken"] += 1

            close_day = int(close_time // 86400)
            acc["daily_pnl"][close_day] = acc["daily_pnl"].get(close_day, 0.0) + pnl

            if acc["phase"] == "funded":
                acc["total_funded_pnl"] += pnl
                if pnl > 0:
                    reserve += pnl * RESERVE_SHARE

            trailing_dd = acc["peak_since_reset"] - acc["cumulative_since_reset"]
            daily_dd = -acc["daily_pnl"][close_day]
            broke = (trailing_dd >= BREAK_DD_PCT / 100 * PALIER_100K
                     or daily_dd >= DAILY_LOSS_PCT / 100 * PALIER_100K)

            if broke:
                total_breaks += 1
                if reserve >= CHALLENGE_COST_100K:
                    reserve -= CHALLENGE_COST_100K
                else:
                    shortfall = CHALLENGE_COST_100K - reserve
                    reserve = 0.0
                    if not ever_funded:
                        real_cash_paid += shortfall
                acc["total_fees_paid"] += CHALLENGE_COST_100K
                acc["phase"] = "challenge"
                acc["cumulative_since_reset"] = 0.0
                acc["peak_since_reset"] = 0.0
                acc["trading_days_since_reset"] = set()
                acc["daily_pnl"] = {}
                continue

            if (acc["phase"] == "challenge"
                    and acc["cumulative_since_reset"] >= CHALLENGE_TARGET_PCT / 100 * PALIER_100K
                    and len(acc["trading_days_since_reset"]) >= MIN_TRADING_DAYS):
                acc["phase"] = "funded"
                ever_funded = True
                acc["cumulative_since_reset"] = 0.0
                acc["peak_since_reset"] = 0.0
                acc["trading_days_since_reset"] = set()

    while mark_idx < len(marks_sorted):
        combined_net = sum(a["total_funded_pnl"] - a["total_fees_paid"] for a in accounts)
        snapshots.append((marks_sorted[mark_idx], combined_net, real_cash_paid, total_breaks))
        mark_idx += 1

    return snapshots


def run_variant(trades, slot_arrivals, blocks, block_seconds, target_duration, mark_seconds_list,
                 market_data, excluded_map, n_accounts):
    rng = random.Random(42)
    rows = []
    for _ in range(N_SIMULATIONS):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, target_duration)
        order = list(range(len(raw_trades)))
        snaps = run_fleet_100k(raw_trades, raw_slots, market_data, excluded_map, order, n_accounts, mark_seconds_list)
        rows.append({
            "year1_net": snaps[0][1], "year1_cash": snaps[0][2], "year1_breaks": snaps[0][3],
            "final_net": snaps[1][1], "final_cash": snaps[1][2], "final_breaks": snaps[1][3],
        })
    return pd.DataFrame(rows)


def build_population(pop, target_winrate):
    if target_winrate is None:
        return build_trades_trailing(pop)[1:]
    rng = random.Random(DEGRADE_SEED)
    _, trades, slot_arrivals, _ = build_degraded_trades(pop, target_winrate, rng)
    return trades, slot_arrivals


def main():
    pop = build_population_with_trailing("fixed", 0.2, verbose=False)
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    summary_rows = []
    for wr_label, wr_target in [("37.29%", None), ("32%", 0.32)]:
        trades, slot_arrivals = build_population(pop, wr_target)
        total_horizon_seconds = slot_arrivals[-1]
        mark_seconds_list = [YEAR_SECONDS, total_horizon_seconds]
        block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
        blocks = build_blocks(trades, slot_arrivals, block_seconds)

        for n_accounts in N_VARIANTS:
            print(f"Calcul : winrate {wr_label} | N={n_accounts} comptes 100k (daily DD 3%)...")
            df = run_variant(trades, slot_arrivals, blocks, block_seconds, total_horizon_seconds,
                              mark_seconds_list, market_data, excluded_map, n_accounts)
            df.to_csv(f"the5ers_100k_N{n_accounts}_{wr_label.replace('%','pct').replace('.','_')}_dailydd.csv", index=False)

            cash = df["final_cash"]
            row = {
                "winrate": wr_label, "n_accounts": n_accounts, "capital_total": n_accounts * PALIER_100K,
                "profit_year1_moyen": df["year1_net"].mean(), "profit_year1_median": df["year1_net"].median(),
                "profit_final_moyen": df["final_net"].mean(), "profit_final_median": df["final_net"].median(),
                "pct_loss_year1": (df["year1_net"] < 0).mean() * 100,
                "cash_worst": cash.max(), "cash_mean": cash.mean(),
                "p_gt_1000": (cash > 1000).mean() * 100, "p_gt_3000": (cash > 3000).mean() * 100,
                "p_gt_5000": (cash > 5000).mean() * 100, "p_gt_10000": (cash > 10000).mean() * 100,
                "casses_moyennes_final": df["final_breaks"].mean(),
            }
            summary_rows.append(row)
            print(f"  Profit an1  : moyenne {row['profit_year1_moyen']:+,.0f}$ | Profit final: moyenne {row['profit_final_moyen']:+,.0f}$")
            print(f"  Casses moyennes (horizon complet) : {row['casses_moyennes_final']:.2f}")

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv("the5ers_100k_N_accounts_dailydd_summary.csv", index=False)
    print("\nRésumé enregistré dans the5ers_100k_N_accounts_dailydd_summary.csv")


if __name__ == "__main__":
    main()
