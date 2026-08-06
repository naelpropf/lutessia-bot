"""
Suite du 06/08 : reconstitution en 3 etapes du cash pire cas depuis le Regime A
pur (sans The5%ers) jusqu'a la configuration actuelle (39 046$/43 406$), pour
confirmer NUMERIQUEMENT (pas par recoupement de documents) la contribution de
chaque correction :
  a) FTMO+Blueberry seuls (aucune contribution The5%ers)
  b) + The5%ers daily DD 3% reel, MAIS prix de rachat fixe 179$ perpetuel
     (isole l'effet daily DD seul, sans le bug #9 -- prix Summer Plan)
  c) + prix de rachat reel (179$ puis 495-545$ apres ~26j) = config actuelle

Puis, sur la structure DEJA DECIDEE "The5%ers retarde jusqu'a l'immunite"
(session precedente), balaie le niveau de risque (0.5%..3%, meme ramp 0.5%/12
trades que partout ailleurs dans ce projet) pour verifier si 2% (Regime A)
reste le meilleur compromis une fois cette structure corrigee.

Reprend le meme moteur que les scripts precedents de la session (FTMO corrige
50k->100k->200k, immunite GLOBALE partagee).
"""
import random
import time

import pandas as pd

from scaling_simulation import (
    CHALLENGE_TARGET_PCT, MIN_TRADING_DAYS, BREAK_DD_PCT, RESERVE_SHARE,
    MAX_POSITIONS, CORR_THRESHOLD, feasible_risk_pct, load_market_data,
    TIER_SEQUENCE as TIER_SEQUENCE_BB, CHALLENGE_COST as CHALLENGE_COST_BB,
    UPGRADE_COST as UPGRADE_COST_BB,
    TIER_SEQUENCE_FTMO, CHALLENGE_COST_FTMO, UPGRADE_COST_FTMO,
)
from monte_carlo_simulation import precompute_correlation_pairs, N_SIMULATIONS
from trailing_payoff_population import build_population_with_trailing, build_trades_trailing
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from winrate_sensitivity_test import build_degraded_trades, DEGRADE_SEED

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

RISK_SWEEP = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]


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
            fivers_mode, daily_loss_5ers, price_mode, high_risk):
    """fivers_mode: 't0' / 'delayed' / 'none'.
    price_mode: 'realistic' (179$->545$ a 26j) ou 'perpetual_cheap' (179$ tout l'horizon)."""
    n_5ers = 0 if fivers_mode == "none" else N_5ERS
    fivers = [make_acc(PALIER_5ERS, SUMMER_COST, active=(fivers_mode == "t0")) for _ in range(n_5ers)]
    growth = [make_acc(TIER_SEQUENCE_BY_FIRM[f][0], CHALLENGE_COST_BY_FIRM[f][TIER_SEQUENCE_BY_FIRM[f][0]])
              for f in GROWTH_FIRMS]

    fivers_cost0 = SUMMER_COST * n_5ers
    growth_cost0 = sum(a["cost"] for a in growth)
    state = {
        "reserve": 0.0, "ever_funded": False,
        "real_cash_paid": (fivers_cost0 if fivers_mode == "t0" else 0.0) + growth_cost0,
        "total_breaks": 0,
        "fivers_activated_at": 0.0 if fivers_mode == "t0" else None,
    }

    marks_sorted = sorted(mark_seconds_list)
    mark_idx = 0
    snapshots = []

    def combined_net():
        return sum(a["total_funded_pnl"] - a["total_fees_paid"] for a in fivers + growth)

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]

        while mark_idx < len(marks_sorted) and now > marks_sorted[mark_idx]:
            snapshots.append((marks_sorted[mark_idx], combined_net(), state["real_cash_paid"], state["total_breaks"]))
            mark_idx += 1

        for acc in fivers:
            if price_mode == "realistic":
                cost_now = SUMMER_COST if now < PRICE_CUTOFF_SECONDS else POST_SUMMER_COST_REAL
            else:
                cost_now = SUMMER_COST
            process_trade(acc, trade, now, market_data, excluded_map, daily_loss_5ers, BREAK_DD_PCT, state,
                          high_risk, cost_override=cost_now)

        for acc in growth:
            just_funded = process_trade(acc, trade, now, market_data, excluded_map, DAILY_LOSS_GROWTH, BREAK_DD_PCT,
                                         state, high_risk)
            if just_funded and fivers_mode == "delayed" and state["fivers_activated_at"] is None:
                state["fivers_activated_at"] = now
                cost = fivers_cost0 if fivers_cost0 > 0 else SUMMER_COST * N_5ERS
                if state["reserve"] >= cost:
                    state["reserve"] -= cost
                else:
                    state["reserve"] = 0.0
                for a in fivers:
                    a["active"] = True
                    a["total_fees_paid"] = a["cost"]

        process_growth_upgrade(growth, state)

    while mark_idx < len(marks_sorted):
        snapshots.append((marks_sorted[mark_idx], combined_net(), state["real_cash_paid"], state["total_breaks"]))
        mark_idx += 1

    return snapshots


def run_variant(trades, slot_arrivals, blocks, block_seconds, target_duration, mark_seconds_list,
                market_data, excluded_map, fivers_mode, daily_loss_5ers, price_mode, high_risk):
    rng = random.Random(42)
    rows = []
    for _ in range(N_SIMULATIONS):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, target_duration)
        order = list(range(len(raw_trades)))
        snaps = run_one(raw_trades, raw_slots, market_data, excluded_map, order, mark_seconds_list,
                        fivers_mode, daily_loss_5ers, price_mode, high_risk)
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

    decomp_rows = []
    risk_rows = []

    for wr_label, wr_target, suffix in [("37.29%", None, "37_29pct"), ("32%", 0.32, "32pct")]:
        print(f"\n{'='*100}\nWINRATE {wr_label}\n{'='*100}")
        trades, slot_arrivals = build_population(pop, wr_target)
        total_horizon_seconds = slot_arrivals[-1]
        mark_seconds_list = [YEAR_SECONDS, total_horizon_seconds]
        block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
        blocks = build_blocks(trades, slot_arrivals, block_seconds)

        print("--- 1. Decomposition 3 etapes (risque 2%, config actuelle sinon) ---")
        steps = [
            ("a_regime_A_seul_sans_5ers", "none", DAILY_LOSS_5ERS_REAL, "realistic"),
            ("b_plus_5ers_dailydd3pct_prix179_perpetuel", "t0", DAILY_LOSS_5ERS_REAL, "perpetual_cheap"),
            ("c_plus_prix_reel_config_actuelle", "t0", DAILY_LOSS_5ERS_REAL, "realistic"),
        ]
        for step_label, mode, dd, price_mode in steps:
            t0 = time.time()
            df = run_variant(trades, slot_arrivals, blocks, block_seconds, total_horizon_seconds,
                              mark_seconds_list, market_data, excluded_map, mode, dd, price_mode, 2.0)
            df.to_csv(f"decomp_{step_label}_{suffix}.csv", index=False)
            row = dict(winrate=wr_label, step=step_label,
                       profit_final_mean=df["final_net"].mean(), cash_worst=df["final_cash"].max(),
                       p_year1_negatif=(df["year1_net"] < 0).mean() * 100)
            decomp_rows.append(row)
            print(f"  [{step_label}] profit final {row['profit_final_mean']:+,.0f}$ | cash pire cas {row['cash_worst']:,.0f}$ "
                  f"| P(an1<0) {row['p_year1_negatif']:.2f}% ({time.time()-t0:.0f}s)")

        print("--- 2. Sensibilite risque, structure 5ers retarde ---")
        for risk in RISK_SWEEP:
            t0 = time.time()
            df = run_variant(trades, slot_arrivals, blocks, block_seconds, total_horizon_seconds,
                              mark_seconds_list, market_data, excluded_map, "delayed", DAILY_LOSS_5ERS_REAL,
                              "realistic", risk)
            df.to_csv(f"risksweep_delayed_5ers_{str(risk).replace('.', '_')}pct_{suffix}.csv", index=False)
            row = dict(winrate=wr_label, risk_pct=risk,
                       profit_final_mean=df["final_net"].mean(), cash_worst=df["final_cash"].max(),
                       p_year1_negatif=(df["year1_net"] < 0).mean() * 100)
            risk_rows.append(row)
            print(f"  risque={risk}% : profit final {row['profit_final_mean']:+,.0f}$ | cash pire cas {row['cash_worst']:,.0f}$ "
                  f"| P(an1<0) {row['p_year1_negatif']:.2f}% ({time.time()-t0:.0f}s)")

    pd.DataFrame(decomp_rows).to_csv("cash_worstcase_decomposition_summary.csv", index=False)
    pd.DataFrame(risk_rows).to_csv("risksweep_delayed_5ers_summary.csv", index=False)
    print(f"\nTerminé en {time.time()-t_start:.0f}s.")


if __name__ == "__main__":
    main()
