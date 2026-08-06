"""
Suite du 06/08 : contre-verification robuste du risque optimal 2,5% (structure
"5ers retarde") avant tout lancement de capital reel. 4 blocs :
  1. Risque DIFFERENCIE par palier de daily DD (growth 2,5% fixe, 5ers balaye)
  2. Declencheur 5ers : evenement (immunite) vs delai calendaire fixe
  3. Robustesse : plus de runs / seed different / bornes IC winrate / stress RR
  4. Facteurs non modelises (swap, gap week-end, symetrie slippage, ambiguite
     SL/TP) -- qualitatif sauf le re-test numerique avec slippage reel mesure.

Reprend le meme moteur que les scripts precedents (FTMO corrige 50k->100k->
200k, immunite GLOBALE partagee, prix 5ers realiste 179$->545$ a 26j).
"""
import random
import time

import numpy as np
import pandas as pd

from scaling_simulation import (
    CHALLENGE_TARGET_PCT, MIN_TRADING_DAYS, BREAK_DD_PCT, RESERVE_SHARE,
    MAX_POSITIONS, CORR_THRESHOLD, feasible_risk_pct, load_market_data,
    TIER_SEQUENCE as TIER_SEQUENCE_BB, CHALLENGE_COST as CHALLENGE_COST_BB,
    UPGRADE_COST as UPGRADE_COST_BB,
    TIER_SEQUENCE_FTMO, CHALLENGE_COST_FTMO, UPGRADE_COST_FTMO,
)
from monte_carlo_simulation import precompute_correlation_pairs
import monte_carlo_simulation as mcsim
from trailing_payoff_population import build_population_with_trailing, build_trades_trailing
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence

YEAR_SECONDS = 365.25 * 86400
BLOCK_MONTHS = 2
DAY_SECONDS = 86400
LOW_RISK, RAMP_TRADES = 0.5, 12

PALIER_5ERS, SUMMER_COST, POST_SUMMER_COST_REAL = 100000, 179, 545
PRICE_CUTOFF_SECONDS = 26 * DAY_SECONDS
N_5ERS = 4
DAILY_LOSS_5ERS_REAL = 3.0

GROWTH_FIRMS = ["FTMO", "FTMO", "Blueberry"]
FIRM_CAP = {"FTMO": 400000, "Blueberry": 400000}
DAILY_LOSS_GROWTH = 5.0

TIER_SEQUENCE_BY_FIRM = {"FTMO": TIER_SEQUENCE_FTMO, "Blueberry": TIER_SEQUENCE_BB}
CHALLENGE_COST_BY_FIRM = {"FTMO": CHALLENGE_COST_FTMO, "Blueberry": CHALLENGE_COST_BB}
UPGRADE_COST_BY_FIRM = {"FTMO": UPGRADE_COST_FTMO, "Blueberry": UPGRADE_COST_BB}


def make_acc(palier, cost, active=True):
    return {"palier": palier, "cost": cost, "phase": "challenge", "cumulative_since_reset": 0.0,
            "peak_since_reset": 0.0, "trading_days_since_reset": set(), "open_positions": [],
            "total_funded_pnl": 0.0, "total_fees_paid": cost, "trades_taken": 0, "daily_pnl": {},
            "active": active}


def process_trade(acc, trade, now, market_data, excluded_map, daily_loss_pct, max_dd_pct, state, high_risk,
                   cost_override=None):
    if not acc["active"]:
        return False
    close_time = now + trade["hold_seconds"]
    acc["open_positions"] = [(t, c) for (t, c) in acc["open_positions"] if c > now]
    if len(acc["open_positions"]) >= MAX_POSITIONS:
        return False
    if any(t in excluded_map[trade["ticker"]] for (t, _) in acc["open_positions"]):
        return False

    current_risk = LOW_RISK if acc["trades_taken"] < RAMP_TRADES else high_risk
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

    just_funded = False
    if broke:
        state["total_breaks"] += 1
        cost = cost_override if cost_override is not None else acc["cost"]
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
        return False

    if (acc["phase"] == "challenge" and acc["cumulative_since_reset"] >= CHALLENGE_TARGET_PCT / 100 * acc["palier"]
            and len(acc["trading_days_since_reset"]) >= MIN_TRADING_DAYS):
        acc["phase"] = "funded"
        if not state["ever_funded"]:
            just_funded = True
        state["ever_funded"] = True
        acc["cumulative_since_reset"] = 0.0
        acc["peak_since_reset"] = 0.0
        acc["trading_days_since_reset"] = set()
    return just_funded


def process_growth_upgrade(accounts, state):
    def firm_combined(firm, exclude_idx=None):
        return sum(a["palier"] for i, a in enumerate(accounts)
                   if GROWTH_FIRMS[i] == firm and i != exclude_idx and a["active"])
    for i, acc in enumerate(accounts):
        if not acc["active"] or acc["phase"] != "funded":
            continue
        firm = GROWTH_FIRMS[i]
        seq = TIER_SEQUENCE_BY_FIRM[firm]
        idx = seq.index(acc["palier"])
        if idx + 1 >= len(seq):
            continue
        next_tier = seq[idx + 1]
        cost = UPGRADE_COST_BY_FIRM[firm][next_tier]
        would_be = firm_combined(firm, exclude_idx=i) + next_tier
        if state["reserve"] >= cost and would_be <= FIRM_CAP[firm]:
            state["reserve"] -= cost
            acc["total_fees_paid"] += cost
            acc["palier"] = next_tier
            acc["cost"] = CHALLENGE_COST_BY_FIRM[firm][next_tier]
            acc["phase"] = "challenge"
            acc["cumulative_since_reset"] = 0.0
            acc["peak_since_reset"] = 0.0
            acc["trading_days_since_reset"] = set()


def run_one(trades, slot_arrivals, market_data, excluded_map, order, mark_seconds_list,
            growth_risk, fivers_risk, trigger, fixed_delay_days=None):
    """trigger: 'event' (immunite globale via 1er financement growth) ou 'fixed_days'
    (active 5ers a fixed_delay_days jours de calendrier, quel que soit l'etat d'immunite)."""
    fivers = [make_acc(PALIER_5ERS, SUMMER_COST, active=False) for _ in range(N_5ERS)]
    growth = [make_acc(TIER_SEQUENCE_BY_FIRM[f][0], CHALLENGE_COST_BY_FIRM[f][TIER_SEQUENCE_BY_FIRM[f][0]])
              for f in GROWTH_FIRMS]

    growth_cost0 = sum(a["cost"] for a in growth)
    state = {
        "reserve": 0.0, "ever_funded": False,
        "real_cash_paid": growth_cost0,
        "total_breaks": 0,
        "fivers_activated_at": None,
    }
    fivers_cost0 = SUMMER_COST * N_5ERS
    fixed_delay_seconds = fixed_delay_days * DAY_SECONDS if fixed_delay_days is not None else None

    marks_sorted = sorted(mark_seconds_list)
    mark_idx = 0
    snapshots = []

    def combined_net():
        return sum(a["total_funded_pnl"] - a["total_fees_paid"] for a in fivers + growth)

    def activate_fivers(now):
        state["fivers_activated_at"] = now
        cost = fivers_cost0
        if state["reserve"] >= cost:
            state["reserve"] -= cost
        else:
            shortfall = cost - state["reserve"]
            state["reserve"] = 0.0
            if not state["ever_funded"]:
                state["real_cash_paid"] += shortfall
        for a in fivers:
            a["active"] = True
            a["total_fees_paid"] = a["cost"]

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]

        while mark_idx < len(marks_sorted) and now > marks_sorted[mark_idx]:
            snapshots.append((marks_sorted[mark_idx], combined_net(), state["real_cash_paid"], state["total_breaks"]))
            mark_idx += 1

        if trigger == "fixed_days" and state["fivers_activated_at"] is None and now >= fixed_delay_seconds:
            activate_fivers(now)

        for acc in fivers:
            cost_now = SUMMER_COST if now < PRICE_CUTOFF_SECONDS else POST_SUMMER_COST_REAL
            process_trade(acc, trade, now, market_data, excluded_map, DAILY_LOSS_5ERS_REAL, BREAK_DD_PCT, state,
                          fivers_risk, cost_override=cost_now)

        for acc in growth:
            just_funded = process_trade(acc, trade, now, market_data, excluded_map, DAILY_LOSS_GROWTH, BREAK_DD_PCT,
                                         state, growth_risk)
            if just_funded and trigger == "event" and state["fivers_activated_at"] is None:
                activate_fivers(now)

        process_growth_upgrade(growth, state)

    while mark_idx < len(marks_sorted):
        snapshots.append((marks_sorted[mark_idx], combined_net(), state["real_cash_paid"], state["total_breaks"]))
        mark_idx += 1

    return snapshots, state["fivers_activated_at"]


def run_variant(trades, slot_arrivals, blocks, block_seconds, target_duration, mark_seconds_list,
                market_data, excluded_map, growth_risk, fivers_risk, trigger, fixed_delay_days,
                n_sims, seed):
    rng = random.Random(seed)
    rows = []
    for _ in range(n_sims):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, target_duration)
        order = list(range(len(raw_trades)))
        snaps, activated_at = run_one(raw_trades, raw_slots, market_data, excluded_map, order, mark_seconds_list,
                                       growth_risk, fivers_risk, trigger, fixed_delay_days)
        rows.append({
            "year1_net": snaps[0][1], "year1_cash": snaps[0][2], "year1_breaks": snaps[0][3],
            "final_net": snaps[1][1], "final_cash": snaps[1][2], "final_breaks": snaps[1][3],
            "fivers_activated_days": (activated_at / DAY_SECONDS) if activated_at is not None else None,
        })
    return pd.DataFrame(rows)


# --- construction de population flexible : winrate cible (au-dessus OU en dessous du
# winrate reel ~37.29%), stress RR sur les gagnants, substitution slippage reel ---

def build_flexible_population(pop, target_winrate, rr_stress_factor, use_slippage, rng):
    sub = pop.sort_values("date_creation").reset_index(drop=True)
    n = len(sub)
    is_win = (sub["statut_final"] == "OBJECTIF ATTEINT").to_numpy()

    outcome_r = np.where(is_win, sub["r_trailing"].to_numpy(), -1.0)

    if use_slippage:
        import slippage_adjusted_population as slip
        adj = slip.build_adjusted_population("empirical")
        adj_key = adj.set_index(["ticker", "date_creation"])["r_slippage"]
        keys = list(zip(sub["ticker"], sub["date_creation"]))
        slip_r = np.array([adj_key.get(k, np.nan) for k in keys])
        valid = ~np.isnan(slip_r)
        outcome_r = np.where(valid, slip_r, outcome_r)

    if target_winrate is not None:
        current_n_win = int(is_win.sum())
        target_n_win = round(target_winrate * n)
        win_idx = list(sub.index[is_win])
        loss_idx = list(sub.index[~is_win])
        win_r_pool = sub.loc[is_win, "r_trailing"].to_numpy()

        if target_n_win < current_n_win:
            flip_to_loss = set(rng.sample(win_idx, current_n_win - target_n_win))
            for idx in flip_to_loss:
                outcome_r[idx] = -1.0
        elif target_n_win > current_n_win:
            flip_to_win = set(rng.sample(loss_idx, min(target_n_win - current_n_win, len(loss_idx))))
            for idx in flip_to_win:
                outcome_r[idx] = rng.choice(list(win_r_pool))

    if rr_stress_factor != 1.0:
        outcome_r = np.where(outcome_r > 0, outcome_r * rr_stress_factor, outcome_r)

    t0 = sub["date_creation"].iloc[0]
    slot_arrivals = [(d - t0).total_seconds() for d in sub["date_creation"]]
    trades = []
    for i, row in sub.iterrows():
        hold_seconds = (row["resolution_time_est"] - row["date_creation"]).total_seconds()
        sl_distance = abs(row["prix_entree"] - row["stop_loss_init"])
        trades.append({"ticker": row["ticker"], "outcome_r": float(outcome_r[i]),
                       "sl_distance": sl_distance, "hold_seconds": hold_seconds, "date": row["date_creation"]})
    return trades, slot_arrivals


def prep_common(pop):
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)
    return market_data, excluded_map


def summarize(df, label, extra=None):
    row = dict(label=label,
               profit_final_mean=df["final_net"].mean(), cash_worst=df["final_cash"].max(),
               cash_std=df["final_cash"].std(), cash_p90=df["final_cash"].quantile(0.9),
               p_year1_negatif=(df["year1_net"] < 0).mean() * 100,
               casses_final=df["final_breaks"].mean())
    if extra:
        row.update(extra)
    return row
