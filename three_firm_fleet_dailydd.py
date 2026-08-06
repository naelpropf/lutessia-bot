"""
Version corrigée de three_firm_fleet_test.py : ajoute la limite de perte
JOURNALIÈRE réelle par firm (The5%ers 3%, FTMO/Blueberry 5%, toutes deux confirmées
officiellement) en plus du drawdown trailing 10% déjà modélisé sur les deux
segments. Voir daily_dd_threshold_verification.py pour la démonstration du bug.

Reste identique à three_firm_fleet_test.py sinon (mêmes 4x100k The5%ers +
3 comptes croissance FTMO(2)/Blueberry(1), même plafond 400k/firm).
"""
import random

import pandas as pd

from scaling_simulation import (
    TIER_SEQUENCE, CHALLENGE_COST, UPGRADE_COST, CHALLENGE_TARGET_PCT,
    MIN_TRADING_DAYS, BREAK_DD_PCT, RESERVE_SHARE, MAX_POSITIONS, CORR_THRESHOLD,
    feasible_risk_pct, load_market_data,
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

N_5ERS = 4
PALIER_100K = 100000
CHALLENGE_COST_100K = 179
DAILY_LOSS_PCT_5ERS = 3.0

N_GROWTH = 3
GROWTH_FIRMS = ["FTMO", "FTMO", "Blueberry"]
FIRM_CAP = {"FTMO": 400000, "Blueberry": 400000}
DAILY_LOSS_PCT_GROWTH = 5.0


def make_account(palier, extra_cost):
    return {
        "palier": palier, "phase": "challenge", "cumulative_since_reset": 0.0,
        "peak_since_reset": 0.0, "trading_days_since_reset": set(), "open_positions": [],
        "total_funded_pnl": 0.0, "total_fees_paid": extra_cost, "trades_taken": 0,
        "daily_pnl": {},
    }


def current_risk_for(acc):
    return LOW_RISK if acc["trades_taken"] < RAMP_TRADES else HIGH_RISK


def run_5ers_segment(trades, slot_arrivals, market_data, excluded_map, order, mark_seconds_list):
    accounts = [make_account(PALIER_100K, CHALLENGE_COST_100K) for _ in range(N_5ERS)]
    reserve = 0.0
    ever_funded = False
    real_cash_paid = CHALLENGE_COST_100K * N_5ERS
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

            eff_risk, _ = feasible_risk_pct(trade["ticker"], trade["sl_distance"], PALIER_100K, current_risk_for(acc), market_data)
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
                     or daily_dd >= DAILY_LOSS_PCT_5ERS / 100 * PALIER_100K)

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


def run_growth_segment(trades, slot_arrivals, market_data, excluded_map, order, mark_seconds_list):
    accounts = [make_account(TIER_SEQUENCE[0], CHALLENGE_COST[TIER_SEQUENCE[0]]) for _ in range(N_GROWTH)]
    reserve = 0.0
    ever_funded = False
    real_cash_paid = CHALLENGE_COST[TIER_SEQUENCE[0]] * N_GROWTH
    total_breaks = 0
    blocked_upgrades = 0

    def firm_combined_palier(firm, exclude_idx=None):
        return sum(accounts[i]["palier"] for i in range(N_GROWTH)
                   if GROWTH_FIRMS[i] == firm and i != exclude_idx)

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

        for i, acc in enumerate(accounts):
            close_time = now + trade["hold_seconds"]
            acc["open_positions"] = [(t, c) for (t, c) in acc["open_positions"] if c > now]
            if len(acc["open_positions"]) >= MAX_POSITIONS:
                continue
            if any(t in excluded_map[trade["ticker"]] for (t, _) in acc["open_positions"]):
                continue

            eff_risk, _ = feasible_risk_pct(trade["ticker"], trade["sl_distance"], acc["palier"], current_risk_for(acc), market_data)
            risk_amount = eff_risk / 100 * acc["palier"]
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
            broke = (trailing_dd >= BREAK_DD_PCT / 100 * acc["palier"]
                     or daily_dd >= DAILY_LOSS_PCT_GROWTH / 100 * acc["palier"])

            if broke:
                cost = CHALLENGE_COST[acc["palier"]]
                total_breaks += 1
                if reserve >= cost:
                    reserve -= cost
                else:
                    shortfall = cost - reserve
                    reserve = 0.0
                    if not ever_funded:
                        real_cash_paid += shortfall
                acc["total_fees_paid"] += cost
                acc["phase"] = "challenge"
                acc["cumulative_since_reset"] = 0.0
                acc["peak_since_reset"] = 0.0
                acc["trading_days_since_reset"] = set()
                acc["daily_pnl"] = {}
                continue

            if (acc["phase"] == "challenge"
                    and acc["cumulative_since_reset"] >= CHALLENGE_TARGET_PCT / 100 * acc["palier"]
                    and len(acc["trading_days_since_reset"]) >= MIN_TRADING_DAYS):
                acc["phase"] = "funded"
                ever_funded = True
                acc["cumulative_since_reset"] = 0.0
                acc["peak_since_reset"] = 0.0
                acc["trading_days_since_reset"] = set()

            if acc["phase"] == "funded":
                idx = TIER_SEQUENCE.index(acc["palier"])
                if idx + 1 < len(TIER_SEQUENCE):
                    next_tier = TIER_SEQUENCE[idx + 1]
                    cost = UPGRADE_COST[next_tier]
                    firm = GROWTH_FIRMS[i]
                    would_be_combined = firm_combined_palier(firm, exclude_idx=i) + next_tier
                    if reserve >= cost and would_be_combined <= FIRM_CAP[firm]:
                        reserve -= cost
                        acc["total_fees_paid"] += cost
                        acc["palier"] = next_tier
                        acc["phase"] = "challenge"
                        acc["cumulative_since_reset"] = 0.0
                        acc["peak_since_reset"] = 0.0
                        acc["trading_days_since_reset"] = set()
                    elif reserve >= cost and would_be_combined > FIRM_CAP[firm]:
                        blocked_upgrades += 1

    while mark_idx < len(marks_sorted):
        combined_net = sum(a["total_funded_pnl"] - a["total_fees_paid"] for a in accounts)
        snapshots.append((marks_sorted[mark_idx], combined_net, real_cash_paid, total_breaks))
        mark_idx += 1

    return snapshots, blocked_upgrades


def run_combined(trades, slot_arrivals, blocks, block_seconds, target_duration, mark_seconds_list,
                  market_data, excluded_map):
    rng = random.Random(42)
    rows = []
    total_blocked = 0
    for _ in range(N_SIMULATIONS):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, target_duration)
        order = list(range(len(raw_trades)))

        snaps_5ers = run_5ers_segment(raw_trades, raw_slots, market_data, excluded_map, order, mark_seconds_list)
        snaps_growth, blocked = run_growth_segment(raw_trades, raw_slots, market_data, excluded_map, order, mark_seconds_list)
        total_blocked += blocked

        rows.append({
            "year1_net": snaps_5ers[0][1] + snaps_growth[0][1],
            "year1_cash": snaps_5ers[0][2] + snaps_growth[0][2],
            "year1_breaks": snaps_5ers[0][3] + snaps_growth[0][3],
            "final_net": snaps_5ers[1][1] + snaps_growth[1][1],
            "final_cash": snaps_5ers[1][2] + snaps_growth[1][2],
            "final_breaks": snaps_5ers[1][3] + snaps_growth[1][3],
            "year1_net_5ers": snaps_5ers[0][1], "year1_net_growth": snaps_growth[0][1],
            "final_net_5ers": snaps_5ers[1][1], "final_net_growth": snaps_growth[1][1],
        })
    return pd.DataFrame(rows), total_blocked


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

        print(f"Calcul : winrate {wr_label} | flotte 3 firms (daily DD 3%/5%)...")
        df, total_blocked = run_combined(trades, slot_arrivals, blocks, block_seconds, total_horizon_seconds,
                                          mark_seconds_list, market_data, excluded_map)
        df.to_csv(f"three_firm_fleet_dailydd_{wr_label.replace('%','pct').replace('.','_')}.csv", index=False)

        cash = df["final_cash"]
        row = {
            "winrate": wr_label,
            "profit_year1_moyen": df["year1_net"].mean(), "profit_year1_median": df["year1_net"].median(),
            "profit_year1_5ers_moyen": df["year1_net_5ers"].mean(), "profit_year1_growth_moyen": df["year1_net_growth"].mean(),
            "profit_final_moyen": df["final_net"].mean(), "profit_final_median": df["final_net"].median(),
            "profit_final_5ers_moyen": df["final_net_5ers"].mean(), "profit_final_growth_moyen": df["final_net_growth"].mean(),
            "pct_loss_year1": (df["year1_net"] < 0).mean() * 100,
            "cash_worst": cash.max(), "cash_mean": cash.mean(),
            "p_gt_1000": (cash > 1000).mean() * 100, "p_gt_3000": (cash > 3000).mean() * 100,
            "p_gt_5000": (cash > 5000).mean() * 100, "p_gt_10000": (cash > 10000).mean() * 100,
            "casses_moyennes_final": df["final_breaks"].mean(),
            "upgrades_bloques_moyens_par_run": total_blocked / N_SIMULATIONS,
        }
        summary_rows.append(row)
        print(f"  [TOTAL FLOTTE] Profit an1  : moyenne {row['profit_year1_moyen']:+,.0f}$ (dont The5%ers {row['profit_year1_5ers_moyen']:+,.0f}$ / croissance {row['profit_year1_growth_moyen']:+,.0f}$)")
        print(f"  [TOTAL FLOTTE] Profit final: moyenne {row['profit_final_moyen']:+,.0f}$ (dont The5%ers {row['profit_final_5ers_moyen']:+,.0f}$ / croissance {row['profit_final_growth_moyen']:+,.0f}$)")
        print(f"  P(perte) an1 : {row['pct_loss_year1']:.2f}%")
        print(f"  Cash perso -- moyenne {row['cash_mean']:,.0f}$ | pire cas {row['cash_worst']:,.0f}$")
        print(f"  Casses moyennes (horizon complet) : {row['casses_moyennes_final']:.2f}")
        print(f"  Upgrades bloqués par plafond firm -- moyenne/run : {row['upgrades_bloques_moyens_par_run']:.2f}")

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv("three_firm_fleet_dailydd_summary.csv", index=False)
    print("\nRésumé enregistré dans three_firm_fleet_dailydd_summary.csv")


if __name__ == "__main__":
    main()
