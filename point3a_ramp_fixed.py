"""
Correction du bug part3a : robustness_5ers_risk_challenge.process_trade applique en
DUR LOW_RISK=0.5%/RAMP_TRADES=12 quel que soit le "high_risk" passe pour
trades_taken<12 -- la premiere version de la rampe (robustness_part2_3_run.py) etait
donc silencieusement ecrasee par ce ramp interne pour ramp_n<=10 (ramp_n=15 partiellement
affecte seulement sur les trades 13-15). Ce script REMPLACE entierement le ramp interne
(process_trade_ramp_pure ne reference jamais eng.LOW_RISK/eng.RAMP_TRADES).
"""
import random
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
from real_cash_risk_year1_block_bootstrap import DAYS_PER_MONTH

POP_CONSTRUCT_SEED = 123
TARGET_RISK = 2.5


def build_ctx(trades, slot_arrivals):
    total_horizon_seconds = slot_arrivals[-1]
    mark_seconds_list = [eng.YEAR_SECONDS, total_horizon_seconds]
    block_seconds = eng.BLOCK_MONTHS * DAYS_PER_MONTH * 86400
    blocks = eng.build_blocks(trades, slot_arrivals, block_seconds)
    return total_horizon_seconds, mark_seconds_list, block_seconds, blocks


def process_trade_ramp_pure(acc, trade, now, market_data, excluded_map, daily_loss_pct, max_dd_pct, state,
                            ramp_risk, ramp_n, target_risk, cost_override=None):
    if not acc["active"]:
        return False
    close_time = now + trade["hold_seconds"]
    acc["open_positions"] = [(t, c) for (t, c) in acc["open_positions"] if c > now]
    if len(acc["open_positions"]) >= eng.MAX_POSITIONS:
        return False
    if any(t in excluded_map[trade["ticker"]] for (t, _) in acc["open_positions"]):
        return False

    current_risk = ramp_risk if acc["trades_taken"] < ramp_n else target_risk
    eff_risk, _ = eng.feasible_risk_pct(trade["ticker"], trade["sl_distance"], acc["palier"], current_risk, market_data)
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
            state["reserve"] += pnl * eng.RESERVE_SHARE

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

    if (acc["phase"] == "challenge" and acc["cumulative_since_reset"] >= eng.CHALLENGE_TARGET_PCT / 100 * acc["palier"]
            and len(acc["trading_days_since_reset"]) >= eng.MIN_TRADING_DAYS):
        acc["phase"] = "funded"
        if not state["ever_funded"]:
            just_funded = True
        state["ever_funded"] = True
        acc["cumulative_since_reset"] = 0.0
        acc["peak_since_reset"] = 0.0
        acc["trading_days_since_reset"] = set()
    return just_funded


def run_one_ramp(trades, slot_arrivals, market_data, excluded_map, order, mark_seconds_list,
                 ramp_risk, ramp_n, target_risk):
    fivers = [eng.make_acc(eng.PALIER_5ERS, eng.SUMMER_COST, active=False) for _ in range(eng.N_5ERS)]
    growth = [eng.make_acc(eng.TIER_SEQUENCE_BY_FIRM[f][0], eng.CHALLENGE_COST_BY_FIRM[f][eng.TIER_SEQUENCE_BY_FIRM[f][0]])
              for f in eng.GROWTH_FIRMS]
    growth_cost0 = sum(a["cost"] for a in growth)
    state = {"reserve": 0.0, "ever_funded": False, "real_cash_paid": growth_cost0,
             "total_breaks": 0, "fivers_activated_at": None}
    fivers_cost0 = eng.SUMMER_COST * eng.N_5ERS

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
            cost_now = eng.SUMMER_COST if now < eng.PRICE_CUTOFF_SECONDS else eng.POST_SUMMER_COST_REAL
            process_trade_ramp_pure(acc, trade, now, market_data, excluded_map, eng.DAILY_LOSS_5ERS_REAL,
                                    eng.BREAK_DD_PCT, state, ramp_risk, ramp_n, target_risk, cost_override=cost_now)

        for acc in growth:
            just_funded = process_trade_ramp_pure(acc, trade, now, market_data, excluded_map, eng.DAILY_LOSS_GROWTH,
                                                  eng.BREAK_DD_PCT, state, ramp_risk, ramp_n, target_risk)
            if just_funded and state["fivers_activated_at"] is None:
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

        eng.process_growth_upgrade(growth, state)

    while mark_idx < len(marks_sorted):
        snapshots.append((marks_sorted[mark_idx], combined_net(), state["real_cash_paid"], state["total_breaks"]))
        mark_idx += 1
    return snapshots


def run_variant_ramp(trades, slot_arrivals, blocks, block_seconds, target_duration, mark_seconds_list,
                     market_data, excluded_map, ramp_risk, ramp_n, target_risk, n_sims=2000, seed=42):
    rng = random.Random(seed)
    rows = []
    for _ in range(n_sims):
        raw_trades, raw_slots = eng.build_full_block_bootstrap_sequence(blocks, block_seconds, rng, target_duration)
        order = list(range(len(raw_trades)))
        snaps = run_one_ramp(raw_trades, raw_slots, market_data, excluded_map, order, mark_seconds_list,
                             ramp_risk, ramp_n, target_risk)
        rows.append({"year1_net": snaps[0][1], "year1_cash": snaps[0][2], "year1_breaks": snaps[0][3],
                     "final_net": snaps[1][1], "final_cash": snaps[1][2], "final_breaks": snaps[1][3]})
    return pd.DataFrame(rows)


def summarize(df, label, extra=None):
    row = dict(label=label, profit_final_mean=df["final_net"].mean(), cash_worst=df["final_cash"].max(),
               p_year1_negatif=(df["year1_net"] < 0).mean() * 100, casses_final=df["final_breaks"].mean())
    if extra:
        row.update(extra)
    return row


def main():
    t_start = time.time()
    pop = eng.build_population_with_trailing("fixed", 0.2, verbose=False)
    market_data, excluded_map = eng.prep_common(pop)
    rows = []

    print("=" * 100 + "\nRAMPE (corrigee -- remplace entierement le ramp interne 0.5%/12 trades)\n" + "=" * 100)
    for wr_label, wr_target, suffix in [("37.29%", None, "37_29pct"), ("32%", 0.32, "32pct")]:
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_target, 1.0, False, random.Random(POP_CONSTRUCT_SEED))
        total_h, marks, block_s, blocks = build_ctx(trades, slot_arrivals)

        # reference : pas de rampe custom (ramp interne standard 0.5%/12 -> 2.5%)
        df_ref = eng.run_variant(trades, slot_arrivals, blocks, block_s, total_h, marks, market_data, excluded_map,
                                 TARGET_RISK, TARGET_RISK, "event", None, 2000, 42)
        row_ref = summarize(df_ref, "reference_ramp_standard_0.5pct_12", {"winrate": wr_label})
        rows.append(row_ref)
        print(f"  [{wr_label}] REFERENCE (rampe standard 0.5%/12) : profit {row_ref['profit_final_mean']:+,.0f}$ | "
              f"cash pire cas {row_ref['cash_worst']:,.0f}$ | P(an1<0) {row_ref['p_year1_negatif']:.2f}%")

        for ramp_risk in [1.0, 1.5, 2.0]:
            for ramp_n in [5, 10, 15]:
                t0 = time.time()
                df = run_variant_ramp(trades, slot_arrivals, blocks, block_s, total_h, marks, market_data,
                                      excluded_map, ramp_risk, ramp_n, TARGET_RISK)
                df.to_csv(f"point3a_rampfixed_{ramp_risk}_{ramp_n}_{suffix}.csv", index=False)
                row = summarize(df, f"ramp{ramp_risk}x{ramp_n}", {"winrate": wr_label, "ramp_risk": ramp_risk, "ramp_n": ramp_n})
                rows.append(row)
                print(f"  [{wr_label}] rampe {ramp_risk}% x{ramp_n} trades : profit {row['profit_final_mean']:+,.0f}$ | "
                      f"cash pire cas {row['cash_worst']:,.0f}$ | P(an1<0) {row['p_year1_negatif']:.2f}% ({time.time()-t0:.0f}s)")
        pd.DataFrame(rows).to_csv("point3a_rampfixed_summary_partial.csv", index=False)

    pd.DataFrame(rows).to_csv("point3a_rampfixed_summary_final.csv", index=False)
    print(f"\nTerminé en {time.time()-t_start:.0f}s.")


if __name__ == "__main__":
    main()
