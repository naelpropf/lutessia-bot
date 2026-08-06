"""
Point 1 (suivi) : chiffre l'ajout de FXIFY a la flotte, structure "comptes
fixes multiples" comme teste pour FTMO/Blueberry, MAIS adaptee a la
contrainte reelle de FXIFY (point 3) : le plafond de capital combine
(795 000$) s'obtient via UN SEUL compte de CHAQUE palier distinct
(5k/10k/15k/25k/50k/100k/200k/400k), pas plusieurs comptes de meme taille.
Chaque compte reste fige a sa taille d'origine (casse -> rachat au meme
palier, jamais de scaling interne), meme philosophie que le reste du projet.

Regles FXIFY (programme 2-Phase 2-Step, sourcees ce soir) :
- Daily loss 4%, max drawdown 10% trailing (depuis le pic, comme le modele
  existant BREAK_DD_PCT=10).
- Couts de challenge par palier (propfirmmatch.com / thetrustedprop.com) :
  5k=59$, 10k=75$, 15k=99$, 25k=175$, 50k=379$, 100k=475$, 200k=999$,
  400k=2950$. Total capital combine : 795 000$, cout d'entree initial total
  4 400$ pour les 8 comptes (une fois chacun, PAS de doublon par palier).
"""
import random
import time

import pandas as pd

from scaling_simulation import (
    CHALLENGE_TARGET_PCT, MIN_TRADING_DAYS, RESERVE_SHARE, MAX_POSITIONS,
    CORR_THRESHOLD, feasible_risk_pct, load_market_data,
)
from monte_carlo_simulation import precompute_correlation_pairs, N_SIMULATIONS
from trailing_payoff_population import build_population_with_trailing, build_trades_trailing
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from winrate_sensitivity_test import build_degraded_trades, DEGRADE_SEED
import three_firm_fleet_dailydd as fleet3

YEAR_SECONDS = 365.25 * 86400
BLOCK_MONTHS = 2
LOW_RISK, HIGH_RISK, RAMP_TRADES = 0.5, 2.0, 12

FXIFY_DAILY_LOSS_PCT = 4.0
FXIFY_MAX_DD_PCT = 10.0  # trailing, confirme

FXIFY_TIERS = [
    (5000, 59), (10000, 75), (15000, 99), (25000, 175),
    (50000, 379), (100000, 475), (200000, 999), (400000, 2950),
]
FXIFY_TOTAL_CAPITAL = sum(p for p, _ in FXIFY_TIERS)  # 795 000$
FXIFY_TOTAL_ENTRY_COST = sum(c for _, c in FXIFY_TIERS)  # 4 400$


def run_fxify_fleet(trades, slot_arrivals, market_data, excluded_map, order, mark_seconds_list):
    accounts = []
    for palier, cost in FXIFY_TIERS:
        accounts.append({
            "palier": palier, "cost": cost,
            "phase": "challenge", "cumulative_since_reset": 0.0,
            "peak_since_reset": 0.0, "trading_days_since_reset": set(), "open_positions": [],
            "total_funded_pnl": 0.0, "total_fees_paid": cost,
            "trades_taken": 0, "daily_pnl": {},
        })
    reserve = 0.0
    ever_funded = False
    real_cash_paid = FXIFY_TOTAL_ENTRY_COST
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
            palier = acc["palier"]
            close_time = now + trade["hold_seconds"]
            acc["open_positions"] = [(t, c) for (t, c) in acc["open_positions"] if c > now]
            if len(acc["open_positions"]) >= MAX_POSITIONS:
                continue
            if any(t in excluded_map[trade["ticker"]] for (t, _) in acc["open_positions"]):
                continue

            current_risk = LOW_RISK if acc["trades_taken"] < RAMP_TRADES else HIGH_RISK
            eff_risk, _ = feasible_risk_pct(trade["ticker"], trade["sl_distance"], palier, current_risk, market_data)
            risk_amount = eff_risk / 100 * palier
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
            broke = (trailing_dd >= FXIFY_MAX_DD_PCT / 100 * palier
                     or daily_dd >= FXIFY_DAILY_LOSS_PCT / 100 * palier)

            if broke:
                total_breaks += 1
                cost = acc["cost"]
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
                    and acc["cumulative_since_reset"] >= CHALLENGE_TARGET_PCT / 100 * palier
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
                 market_data, excluded_map):
    rng = random.Random(42)
    rows = []
    for _ in range(N_SIMULATIONS):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, target_duration)
        order = list(range(len(raw_trades)))
        snaps = run_fxify_fleet(raw_trades, raw_slots, market_data, excluded_map, order, mark_seconds_list)
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
    t_start = time.time()
    pop = build_population_with_trailing("fixed", 0.2, verbose=False)
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    rows = []
    for wr_label, wr_target, suffix in [("37.29%", None, "37_29pct"), ("32%", 0.32, "32pct")]:
        print(f"\n{'='*100}\nWINRATE {wr_label}\n{'='*100}")
        trades, slot_arrivals = build_population(pop, wr_target)
        total_horizon_seconds = slot_arrivals[-1]
        mark_seconds_list = [YEAR_SECONDS, total_horizon_seconds]
        block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
        blocks = build_blocks(trades, slot_arrivals, block_seconds)

        t0 = time.time()
        df = run_variant(trades, slot_arrivals, blocks, block_seconds, total_horizon_seconds,
                          mark_seconds_list, market_data, excluded_map)
        df.to_csv(f"fxify_fleet_{suffix}.csv", index=False)
        row = dict(winrate=wr_label, capital_combine=FXIFY_TOTAL_CAPITAL,
                   profit_year1=df["year1_net"].mean(), profit_final=df["final_net"].mean(),
                   cash_worst=df["final_cash"].max(), casses_final=df["final_breaks"].mean())
        rows.append(row)
        print(f"  FXIFY (8 comptes fixes, 795k combine) : profit final {row['profit_final']:+,.0f}$ "
              f"| casses {row['casses_final']:.1f} | cash pire cas {row['cash_worst']:,.0f}$ ({time.time()-t0:.0f}s)")

    out = pd.DataFrame(rows)
    out.to_csv("fxify_fleet_summary.csv", index=False)
    print(f"\nTerminé en {time.time()-t_start:.0f}s.")


if __name__ == "__main__":
    main()
