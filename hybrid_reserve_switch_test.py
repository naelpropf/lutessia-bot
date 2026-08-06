"""
Point 1 de la relance : la flotte demarre en structure ACTUELLE (5ers prix
realiste + FTMO/Blueberry scaling plafonne, 3 comptes), PUIS bascule vers la
structure "comptes fixes" (growth restructure en 16x50k + FXIFY 8 comptes
fixes) des que la RESERVE COMMUNE (5ers+growth reunies dans UN seul pool
partage des le depart, cf. discussion "reserve commune") franchit un seuil.

Au moment de la bascule :
- Les 3 anciens comptes growth (scaling plafonne) sont GELES (plus aucun
  nouveau trade) -- on ne peut pas "redimensionner" un compte funded dans la
  vraie vie, donc la bascule reelle consiste a arreter d'ouvrir de nouveaux
  challenges dessus et rediriger l'effort/capital vers la nouvelle structure.
- 16 comptes growth fixes (50k, 333$/reset, jamais scales) + 8 comptes FXIFY
  (5k->400k, couts sources, 4% daily/10% trailing) sont ouverts d'un coup,
  payes depuis la reserve commune (shortfall en cash reel si insuffisante).
- Le compte 5ers (prix realiste 179$->545$ a 26 jours) continue inchange sur
  tout l'horizon, jamais affecte par la bascule.

Seuils testes : 20k$, 50k$, 100k$ de reserve commune accumulee.
"""
import random
import time

import pandas as pd

from scaling_simulation import (
    CHALLENGE_TARGET_PCT, MIN_TRADING_DAYS, BREAK_DD_PCT, RESERVE_SHARE,
    MAX_POSITIONS, CORR_THRESHOLD, feasible_risk_pct, load_market_data,
    TIER_SEQUENCE, CHALLENGE_COST, UPGRADE_COST,
)
from monte_carlo_simulation import precompute_correlation_pairs, N_SIMULATIONS
from trailing_payoff_population import build_population_with_trailing, build_trades_trailing
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from winrate_sensitivity_test import build_degraded_trades, DEGRADE_SEED
from fxify_fleet_test import FXIFY_TIERS, FXIFY_DAILY_LOSS_PCT, FXIFY_MAX_DD_PCT

YEAR_SECONDS = 365.25 * 86400
BLOCK_MONTHS = 2
DAY_SECONDS = 86400

LOW_RISK, HIGH_RISK, RAMP_TRADES = 0.5, 2.0, 12

# --- 5ers (prix realiste, inchange par la bascule) ---
PALIER_5ERS, SUMMER_COST, POST_SUMMER_COST = 100000, 179, 545
DAILY_LOSS_5ERS, PRICE_CUTOFF_SECONDS = 3.0, 26 * DAY_SECONDS
N_5ERS = 4

# --- growth ancien (scaling plafonne, gele a la bascule) ---
N_GROWTH_OLD = 3
GROWTH_FIRMS = ["FTMO", "FTMO", "Blueberry"]
FIRM_CAP = {"FTMO": 400000, "Blueberry": 400000}
DAILY_LOSS_GROWTH = 5.0

# --- growth nouveau (fixe, ouvert a la bascule) ---
N_GROWTH_FIXED, PALIER_GROWTH_FIXED, COST_GROWTH_FIXED = 16, 50000, CHALLENGE_COST[50000]

RESERVE_THRESHOLDS = [20000, 50000, 100000]


def make_acc(palier, cost):
    return {"palier": palier, "cost": cost, "phase": "challenge", "cumulative_since_reset": 0.0,
            "peak_since_reset": 0.0, "trading_days_since_reset": set(), "open_positions": [],
            "total_funded_pnl": 0.0, "total_fees_paid": cost, "trades_taken": 0, "daily_pnl": {},
            "active": True}


def process_trade(acc, trade, now, market_data, excluded_map, daily_loss_pct, max_dd_pct, state):
    """Traite un trade sur un compte ; met a jour state['reserve'] et
    state['real_cash_paid']/state['ever_funded']/state['total_breaks'] (reserve commune)."""
    if not acc["active"]:
        return
    close_time = now + trade["hold_seconds"]
    acc["open_positions"] = [(t, c) for (t, c) in acc["open_positions"] if c > now]
    if len(acc["open_positions"]) >= MAX_POSITIONS:
        return
    if any(t in excluded_map[trade["ticker"]] for (t, _) in acc["open_positions"]):
        return

    current_risk = LOW_RISK if acc["trades_taken"] < RAMP_TRADES else HIGH_RISK
    eff_risk, _ = feasible_risk_pct(trade["ticker"], trade["sl_distance"], acc["palier"], current_risk, market_data)
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
            state["reserve"] += pnl * RESERVE_SHARE

    trailing_dd = acc["peak_since_reset"] - acc["cumulative_since_reset"]
    daily_dd = -acc["daily_pnl"][close_day]
    broke = (trailing_dd >= max_dd_pct / 100 * acc["palier"] or daily_dd >= daily_loss_pct / 100 * acc["palier"])

    if broke:
        state["total_breaks"] += 1
        cost = acc.get("_dynamic_cost", acc["cost"])
        if state["reserve"] >= cost:
            state["reserve"] -= cost
        else:
            shortfall = cost - state["reserve"]
            state["reserve"] = 0.0
            if not state["ever_funded"]:
                state["real_cash_paid"] += shortfall
        acc["total_fees_paid"] += cost
        acc["phase"] = "challenge"
        acc["cumulative_since_reset"] = 0.0
        acc["peak_since_reset"] = 0.0
        acc["trading_days_since_reset"] = set()
        acc["daily_pnl"] = {}
        return

    if (acc["phase"] == "challenge" and acc["cumulative_since_reset"] >= CHALLENGE_TARGET_PCT / 100 * acc["palier"]
            and len(acc["trading_days_since_reset"]) >= MIN_TRADING_DAYS):
        acc["phase"] = "funded"
        state["ever_funded"] = True
        acc["cumulative_since_reset"] = 0.0
        acc["peak_since_reset"] = 0.0
        acc["trading_days_since_reset"] = set()


def process_growth_old_upgrade(accounts_old, state):
    def firm_combined(firm, exclude_idx=None):
        return sum(a["palier"] for i, a in enumerate(accounts_old)
                   if GROWTH_FIRMS[i] == firm and i != exclude_idx)
    for i, acc in enumerate(accounts_old):
        if acc["phase"] != "funded" or not acc["active"]:
            continue
        idx = TIER_SEQUENCE.index(acc["palier"])
        if idx + 1 >= len(TIER_SEQUENCE):
            continue
        next_tier = TIER_SEQUENCE[idx + 1]
        cost = UPGRADE_COST[next_tier]
        firm = GROWTH_FIRMS[i]
        would_be = firm_combined(firm, exclude_idx=i) + next_tier
        if state["reserve"] >= cost and would_be <= FIRM_CAP[firm]:
            state["reserve"] -= cost
            acc["total_fees_paid"] += cost
            acc["palier"] = next_tier
            acc["cost"] = CHALLENGE_COST[next_tier]
            acc["phase"] = "challenge"
            acc["cumulative_since_reset"] = 0.0
            acc["peak_since_reset"] = 0.0
            acc["trading_days_since_reset"] = set()


def run_hybrid(trades, slot_arrivals, market_data, excluded_map, order, mark_seconds_list, reserve_threshold):
    fivers = [make_acc(PALIER_5ERS, SUMMER_COST) for _ in range(N_5ERS)]
    growth_old = [make_acc(TIER_SEQUENCE[0], CHALLENGE_COST[TIER_SEQUENCE[0]]) for _ in range(N_GROWTH_OLD)]
    growth_fixed = []  # crees a la bascule
    fxify = []  # crees a la bascule

    state = {"reserve": 0.0, "ever_funded": False,
             "real_cash_paid": SUMMER_COST * N_5ERS + CHALLENGE_COST[TIER_SEQUENCE[0]] * N_GROWTH_OLD,
             "total_breaks": 0, "switched": False, "switch_time": None}

    marks_sorted = sorted(mark_seconds_list)
    mark_idx = 0
    snapshots = []

    def combined_net():
        total = 0.0
        for group in (fivers, growth_old, growth_fixed, fxify):
            total += sum(a["total_funded_pnl"] - a["total_fees_paid"] for a in group)
        return total

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]

        while mark_idx < len(marks_sorted) and now > marks_sorted[mark_idx]:
            snapshots.append((marks_sorted[mark_idx], combined_net(), state["real_cash_paid"], state["total_breaks"]))
            mark_idx += 1

        for acc in fivers:
            acc["_dynamic_cost"] = SUMMER_COST if now < PRICE_CUTOFF_SECONDS else POST_SUMMER_COST
            process_trade(acc, trade, now, market_data, excluded_map, DAILY_LOSS_5ERS, BREAK_DD_PCT, state)

        if not state["switched"]:
            for acc in growth_old:
                process_trade(acc, trade, now, market_data, excluded_map, DAILY_LOSS_GROWTH, BREAK_DD_PCT, state)
            process_growth_old_upgrade(growth_old, state)

            if state["reserve"] >= reserve_threshold:
                state["switched"] = True
                state["switch_time"] = now
                for acc in growth_old:
                    acc["active"] = False
                new_growth_fixed = [make_acc(PALIER_GROWTH_FIXED, COST_GROWTH_FIXED) for _ in range(N_GROWTH_FIXED)]
                new_fxify = [make_acc(p, c) for p, c in FXIFY_TIERS]
                entry_cost = sum(a["cost"] for a in new_growth_fixed) + sum(a["cost"] for a in new_fxify)
                if state["reserve"] >= entry_cost:
                    state["reserve"] -= entry_cost
                else:
                    shortfall = entry_cost - state["reserve"]
                    state["reserve"] = 0.0
                    state["real_cash_paid"] += shortfall
                growth_fixed.extend(new_growth_fixed)
                fxify.extend(new_fxify)
        else:
            for acc in growth_fixed:
                process_trade(acc, trade, now, market_data, excluded_map, DAILY_LOSS_GROWTH, BREAK_DD_PCT, state)
            for acc in fxify:
                process_trade(acc, trade, now, market_data, excluded_map, FXIFY_DAILY_LOSS_PCT, FXIFY_MAX_DD_PCT, state)

    while mark_idx < len(marks_sorted):
        snapshots.append((marks_sorted[mark_idx], combined_net(), state["real_cash_paid"], state["total_breaks"]))
        mark_idx += 1

    return snapshots, state["switch_time"]


def run_variant(trades, slot_arrivals, blocks, block_seconds, target_duration, mark_seconds_list,
                market_data, excluded_map, reserve_threshold):
    rng = random.Random(42)
    rows = []
    for _ in range(N_SIMULATIONS):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, target_duration)
        order = list(range(len(raw_trades)))
        snaps, switch_time = run_hybrid(raw_trades, raw_slots, market_data, excluded_map, order,
                                         mark_seconds_list, reserve_threshold)
        rows.append({
            "year1_net": snaps[0][1], "year1_cash": snaps[0][2], "year1_breaks": snaps[0][3],
            "final_net": snaps[1][1], "final_cash": snaps[1][2], "final_breaks": snaps[1][3],
            "switch_time_days": (switch_time / DAY_SECONDS) if switch_time is not None else None,
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

        for threshold in RESERVE_THRESHOLDS:
            t0 = time.time()
            df = run_variant(trades, slot_arrivals, blocks, block_seconds, total_horizon_seconds,
                              mark_seconds_list, market_data, excluded_map, threshold)
            df.to_csv(f"hybrid_switch_{threshold}_{suffix}.csv", index=False)
            never_switched_pct = df["switch_time_days"].isna().mean() * 100
            row = dict(winrate=wr_label, reserve_threshold=threshold,
                       profit_year1=df["year1_net"].mean(), profit_final=df["final_net"].mean(),
                       cash_worst=df["final_cash"].max(), casses_final=df["final_breaks"].mean(),
                       switch_time_days_median=df["switch_time_days"].median(),
                       never_switched_pct=never_switched_pct)
            rows.append(row)
            print(f"  seuil={threshold}$ : profit final {row['profit_final']:+,.0f}$ | cash pire cas {row['cash_worst']:,.0f}$ "
                  f"| casses {row['casses_final']:.1f} | bascule mediane a {row['switch_time_days_median']:.0f}j "
                  f"| jamais bascule : {never_switched_pct:.1f}% ({time.time()-t0:.0f}s)")

    out = pd.DataFrame(rows)
    out.to_csv("hybrid_reserve_switch_summary.csv", index=False)
    print(f"\nTerminé en {time.time()-t_start:.0f}s.")


if __name__ == "__main__":
    main()
