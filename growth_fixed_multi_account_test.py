"""
Point 1 de la relance strategique : teste l'hypothese "plusieurs comptes de
taille FIXE (jamais de scaling interne, casse+rachat au meme palier) au lieu
d'un compte qui grossit 50k->200k->500k plafonne par le capital combine par
firm (400k)".

CONFIRME PAR LECTURE DE CODE (three_firm_fleet_dailydd.py, run_growth_segment) :
- FIRM_CAP = 400000 pour FTMO et Blueberry.
- Les 2 comptes FTMO plafonnent a 200k CHACUN (200k+200k=400k=plafond exact,
  tout upgrade au-dela est bloque par le check
  `would_be_combined = firm_combined_palier(...) + next_tier <= FIRM_CAP`).
- Le compte Blueberry (SEUL, sans autre compte du meme firm) plafonne aussi a
  200k, car meme seul, sauter a 500k (500000 > 400000) depasse deja le
  plafond de la firm a lui seul. Ce n'est PAS une histoire de partage de
  capital entre plusieurs comptes -- le palier 500k est structurellement
  inaccessible chez une firm dont le plafond combine est 400k, point final.
- Ce n'est PAS une restriction de copytrade (aucune des firms concernees ne
  l'interdit entre ses propres comptes) : c'est un plafond de capital
  combine propre a chaque firm, qui existe independamment du nombre de
  comptes utilises pour l'atteindre.
- Le Regime A (7,7M$ reference) ne modelise AUCUN plafond de ce type -- ses 3
  comptes scalent librement jusqu'a 500k chacun (jusqu'a 1,5M$ de capital
  combine total), ce qui est l'hypothese optimiste corrigee par le modele a
  3 firms (plafond reel = ~600k de capital combine max, atteint lentement).

Ce script chiffre l'alternative : remplacer les 3 comptes scalants (plafonnes
a ~600k de capital combine, atteint progressivement) par N comptes de taille
FIXE 50k (cout de challenge connu : 333$), jamais scales, casses frequentes
assumees -- meme philosophie que The5%ers. N=16 comptes x 50k = 800k de
capital combine (2 firms x 400k de plafond, rempli directement des le
depart plutot que via un scaling progressif).
"""
import random
import time

import pandas as pd

from scaling_simulation import (
    CHALLENGE_TARGET_PCT, MIN_TRADING_DAYS, BREAK_DD_PCT, RESERVE_SHARE,
    MAX_POSITIONS, CORR_THRESHOLD, feasible_risk_pct, load_market_data,
    CHALLENGE_COST,
)
from monte_carlo_simulation import precompute_correlation_pairs, N_SIMULATIONS
from trailing_payoff_population import build_population_with_trailing, build_trades_trailing
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from winrate_sensitivity_test import build_degraded_trades, DEGRADE_SEED

YEAR_SECONDS = 365.25 * 86400
BLOCK_MONTHS = 2
LOW_RISK, HIGH_RISK, RAMP_TRADES = 0.5, 2.0, 12
DAILY_LOSS_PCT_GROWTH = 5.0

PALIER_FIXED = 50000
CHALLENGE_COST_FIXED = CHALLENGE_COST[PALIER_FIXED]  # 333$
N_ACCOUNTS_FIXED = 16  # 2 firms x 400k de plafond / 50k = 8+8


def run_fixed_fleet(trades, slot_arrivals, market_data, excluded_map, order, mark_seconds_list, n_accounts):
    accounts = []
    for _ in range(n_accounts):
        accounts.append({
            "phase": "challenge", "cumulative_since_reset": 0.0,
            "peak_since_reset": 0.0, "trading_days_since_reset": set(), "open_positions": [],
            "total_funded_pnl": 0.0, "total_fees_paid": CHALLENGE_COST_FIXED,
            "trades_taken": 0, "daily_pnl": {},
        })
    reserve = 0.0
    ever_funded = False
    real_cash_paid = CHALLENGE_COST_FIXED * n_accounts
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
            eff_risk, _ = feasible_risk_pct(trade["ticker"], trade["sl_distance"], PALIER_FIXED, current_risk, market_data)
            risk_amount = eff_risk / 100 * PALIER_FIXED
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
            broke = (trailing_dd >= BREAK_DD_PCT / 100 * PALIER_FIXED
                     or daily_dd >= DAILY_LOSS_PCT_GROWTH / 100 * PALIER_FIXED)

            if broke:
                total_breaks += 1
                if reserve >= CHALLENGE_COST_FIXED:
                    reserve -= CHALLENGE_COST_FIXED
                else:
                    shortfall = CHALLENGE_COST_FIXED - reserve
                    reserve = 0.0
                    if not ever_funded:
                        real_cash_paid += shortfall
                acc["total_fees_paid"] += CHALLENGE_COST_FIXED
                acc["phase"] = "challenge"
                acc["cumulative_since_reset"] = 0.0
                acc["peak_since_reset"] = 0.0
                acc["trading_days_since_reset"] = set()
                acc["daily_pnl"] = {}
                continue

            if (acc["phase"] == "challenge"
                    and acc["cumulative_since_reset"] >= CHALLENGE_TARGET_PCT / 100 * PALIER_FIXED
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
        snaps = run_fixed_fleet(raw_trades, raw_slots, market_data, excluded_map, order, mark_seconds_list, n_accounts)
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
                          mark_seconds_list, market_data, excluded_map, N_ACCOUNTS_FIXED)
        df.to_csv(f"growth_fixed_N{N_ACCOUNTS_FIXED}_{suffix}.csv", index=False)
        row = dict(winrate=wr_label, n_accounts=N_ACCOUNTS_FIXED, palier=PALIER_FIXED,
                   capital_combine=N_ACCOUNTS_FIXED * PALIER_FIXED,
                   profit_year1=df["year1_net"].mean(), profit_final=df["final_net"].mean(),
                   cash_worst=df["final_cash"].max(), casses_final=df["final_breaks"].mean())
        rows.append(row)
        print(f"  N={N_ACCOUNTS_FIXED}x{PALIER_FIXED} (fixe, jamais scale) : profit final {row['profit_final']:+,.0f}$ "
              f"| casses {row['casses_final']:.1f} | cash pire cas {row['cash_worst']:,.0f}$ ({time.time()-t0:.0f}s)")

    out = pd.DataFrame(rows)
    out.to_csv("growth_fixed_multi_account_summary.csv", index=False)
    print(f"\nTerminé en {time.time()-t_start:.0f}s.")


if __name__ == "__main__":
    main()
