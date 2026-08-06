"""
Suite du 06/08 : points 2 (declencheur 5ers par seuil de reserve) et 3 (rampe
de risque au demarrage + premier compte croissance reduit 25k), sur la
structure verrouillee (FTMO corrige, immunite globale, 5ers retarde, risque
2,5% uniforme).
"""
import random
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
from real_cash_risk_year1_block_bootstrap import DAYS_PER_MONTH

POP_CONSTRUCT_SEED = 123
RISK = 2.5


def build_ctx(trades, slot_arrivals):
    total_horizon_seconds = slot_arrivals[-1]
    mark_seconds_list = [eng.YEAR_SECONDS, total_horizon_seconds]
    block_seconds = eng.BLOCK_MONTHS * DAYS_PER_MONTH * 86400
    blocks = eng.build_blocks(trades, slot_arrivals, block_seconds)
    return total_horizon_seconds, mark_seconds_list, block_seconds, blocks


# ---- Point 2 : declencheur par seuil de reserve ----

def run_one_reserve_threshold(trades, slot_arrivals, market_data, excluded_map, order, mark_seconds_list,
                              risk, reserve_threshold):
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

    def activate_fivers():
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

        if state["fivers_activated_at"] is None and state["reserve"] >= reserve_threshold:
            activate_fivers()

        for acc in fivers:
            cost_now = eng.SUMMER_COST if now < eng.PRICE_CUTOFF_SECONDS else eng.POST_SUMMER_COST_REAL
            eng.process_trade(acc, trade, now, market_data, excluded_map, eng.DAILY_LOSS_5ERS_REAL, eng.BREAK_DD_PCT,
                              state, risk, cost_override=cost_now)

        for acc in growth:
            eng.process_trade(acc, trade, now, market_data, excluded_map, eng.DAILY_LOSS_GROWTH, eng.BREAK_DD_PCT,
                              state, risk)

        eng.process_growth_upgrade(growth, state)

    while mark_idx < len(marks_sorted):
        snapshots.append((marks_sorted[mark_idx], combined_net(), state["real_cash_paid"], state["total_breaks"]))
        mark_idx += 1

    return snapshots, state["fivers_activated_at"]


def run_variant_reserve_threshold(trades, slot_arrivals, blocks, block_seconds, target_duration, mark_seconds_list,
                                  market_data, excluded_map, risk, reserve_threshold, n_sims=2000, seed=42):
    rng = random.Random(seed)
    rows = []
    for _ in range(n_sims):
        raw_trades, raw_slots = eng.build_full_block_bootstrap_sequence(blocks, block_seconds, rng, target_duration)
        order = list(range(len(raw_trades)))
        snaps, activated_at = run_one_reserve_threshold(raw_trades, raw_slots, market_data, excluded_map, order,
                                                        mark_seconds_list, risk, reserve_threshold)
        rows.append({
            "year1_net": snaps[0][1], "year1_cash": snaps[0][2], "year1_breaks": snaps[0][3],
            "final_net": snaps[1][1], "final_cash": snaps[1][2], "final_breaks": snaps[1][3],
            "fivers_activated_days": (activated_at / 86400) if activated_at is not None else None,
        })
    return pd.DataFrame(rows)


# ---- Point 3a : rampe de risque au demarrage (N premiers trades a risque reduit) ----

def process_trade_ramp(acc, trade, now, market_data, excluded_map, daily_loss_pct, max_dd_pct, state,
                       ramp_risk, ramp_n, target_risk, cost_override=None):
    if not acc["active"]:
        return False
    current_risk = ramp_risk if acc["trades_taken"] < ramp_n else target_risk
    # reutilise le corps de eng.process_trade en injectant current_risk directement
    return eng.process_trade(acc, trade, now, market_data, excluded_map, daily_loss_pct, max_dd_pct, state,
                             current_risk, cost_override=cost_override)


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
            process_trade_ramp(acc, trade, now, market_data, excluded_map, eng.DAILY_LOSS_5ERS_REAL, eng.BREAK_DD_PCT,
                               state, ramp_risk, ramp_n, target_risk, cost_override=cost_now)

        for acc in growth:
            just_funded = process_trade_ramp(acc, trade, now, market_data, excluded_map, eng.DAILY_LOSS_GROWTH,
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
        rows.append({
            "year1_net": snaps[0][1], "year1_cash": snaps[0][2], "year1_breaks": snaps[0][3],
            "final_net": snaps[1][1], "final_cash": snaps[1][2], "final_breaks": snaps[1][3],
        })
    return pd.DataFrame(rows)


# ---- Point 3b : premier palier croissance reduit (25k au lieu de 50k) ----

def run_variant_small_first_tier(trades, slot_arrivals, blocks, block_seconds, target_duration, mark_seconds_list,
                                 market_data, excluded_map, risk, first_tier_25k_firms, n_sims=2000, seed=42):
    """first_tier_25k_firms: set des firms ('FTMO','Blueberry') dont le PREMIER palier
    est 25k (cout challenge estime proportionnellement, ~166$ vs 333$ a 50k) au lieu de
    50k -- le palier suivant reste 50k (insere un palier de plus dans la sequence)."""
    tier_seq_by_firm = {}
    cost_by_firm = {}
    upgrade_by_firm = {}
    for firm in ["FTMO", "Blueberry"]:
        base_seq = eng.TIER_SEQUENCE_BY_FIRM[firm]
        base_cost = eng.CHALLENGE_COST_BY_FIRM[firm]
        base_upgrade = eng.UPGRADE_COST_BY_FIRM[firm]
        if firm in first_tier_25k_firms:
            seq = [25000] + base_seq
            cost = dict(base_cost)
            cost[25000] = 166  # proportionnel a 333$/50k
            upgrade = dict(base_upgrade)
            upgrade[base_seq[0]] = 166  # upgrade 25k->50k ~ meme cout que challenge 50k initial
            tier_seq_by_firm[firm] = seq
            cost_by_firm[firm] = cost
            upgrade_by_firm[firm] = upgrade
        else:
            tier_seq_by_firm[firm] = base_seq
            cost_by_firm[firm] = base_cost
            upgrade_by_firm[firm] = base_upgrade

    def process_growth_upgrade_custom(accounts, state):
        def firm_combined(firm, exclude_idx=None):
            return sum(a["palier"] for i, a in enumerate(accounts)
                       if eng.GROWTH_FIRMS[i] == firm and i != exclude_idx and a["active"])
        for i, acc in enumerate(accounts):
            if not acc["active"] or acc["phase"] != "funded":
                continue
            firm = eng.GROWTH_FIRMS[i]
            seq = tier_seq_by_firm[firm]
            idx = seq.index(acc["palier"])
            if idx + 1 >= len(seq):
                continue
            next_tier = seq[idx + 1]
            cost = upgrade_by_firm[firm][next_tier]
            would_be = firm_combined(firm, exclude_idx=i) + next_tier
            if state["reserve"] >= cost and would_be <= eng.FIRM_CAP[firm]:
                state["reserve"] -= cost
                acc["total_fees_paid"] += cost
                acc["palier"] = next_tier
                acc["cost"] = cost_by_firm[firm][next_tier]
                acc["phase"] = "challenge"
                acc["cumulative_since_reset"] = 0.0
                acc["peak_since_reset"] = 0.0
                acc["trading_days_since_reset"] = set()

    def run_one(trades, slot_arrivals, order):
        fivers = [eng.make_acc(eng.PALIER_5ERS, eng.SUMMER_COST, active=False) for _ in range(eng.N_5ERS)]
        growth = [eng.make_acc(tier_seq_by_firm[f][0], cost_by_firm[f][tier_seq_by_firm[f][0]])
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
                eng.process_trade(acc, trade, now, market_data, excluded_map, eng.DAILY_LOSS_5ERS_REAL, eng.BREAK_DD_PCT,
                                  state, risk, cost_override=cost_now)

            for acc in growth:
                just_funded = eng.process_trade(acc, trade, now, market_data, excluded_map, eng.DAILY_LOSS_GROWTH,
                                                eng.BREAK_DD_PCT, state, risk)
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

            process_growth_upgrade_custom(growth, state)

        while mark_idx < len(marks_sorted):
            snapshots.append((marks_sorted[mark_idx], combined_net(), state["real_cash_paid"], state["total_breaks"]))
            mark_idx += 1
        return snapshots

    rng = random.Random(seed)
    rows = []
    for _ in range(n_sims):
        raw_trades, raw_slots = eng.build_full_block_bootstrap_sequence(blocks, block_seconds, rng, target_duration)
        order = list(range(len(raw_trades)))
        snaps = run_one(raw_trades, raw_slots, order)
        rows.append({
            "year1_net": snaps[0][1], "year1_cash": snaps[0][2], "year1_breaks": snaps[0][3],
            "final_net": snaps[1][1], "final_cash": snaps[1][2], "final_breaks": snaps[1][3],
        })
    return pd.DataFrame(rows)


def summarize(df, label, extra=None):
    row = dict(label=label, profit_final_mean=df["final_net"].mean(), cash_worst=df["final_cash"].max(),
               p_year1_negatif=(df["year1_net"] < 0).mean() * 100, casses_final=df["final_breaks"].mean())
    if "fivers_activated_days" in df:
        row["fivers_delay_median"] = df["fivers_activated_days"].median()
        row["never_activated_pct"] = df["fivers_activated_days"].isna().mean() * 100
    if extra:
        row.update(extra)
    return row


def main():
    t_start = time.time()
    pop = eng.build_population_with_trailing("fixed", 0.2, verbose=False)
    market_data, excluded_map = eng.prep_common(pop)
    all_rows = []

    print("\n" + "#" * 100 + "\nPART 2 -- DECLENCHEUR PAR SEUIL DE RESERVE\n" + "#" * 100)
    for wr_label, wr_target, suffix in [("37.29%", None, "37_29pct"), ("32%", 0.32, "32pct")]:
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_target, 1.0, False, random.Random(POP_CONSTRUCT_SEED))
        total_h, marks, block_s, blocks = build_ctx(trades, slot_arrivals)
        for threshold in [3000, 5000, 10000, 15000]:
            t0 = time.time()
            df = run_variant_reserve_threshold(trades, slot_arrivals, blocks, block_s, total_h, marks,
                                               market_data, excluded_map, RISK, threshold)
            df.to_csv(f"part2_reservethresh_{threshold}_{suffix}.csv", index=False)
            row = summarize(df, f"reserve{threshold}", {"winrate": wr_label, "reserve_threshold": threshold})
            all_rows.append(row)
            print(f"  [{wr_label}] seuil reserve={threshold}$ : profit {row['profit_final_mean']:+,.0f}$ | "
                  f"cash pire cas {row['cash_worst']:,.0f}$ | P(an1<0) {row['p_year1_negatif']:.2f}% | "
                  f"delai median 5ers {row['fivers_delay_median']:.0f}j | jamais active {row['never_activated_pct']:.1f}% ({time.time()-t0:.0f}s)")
        pd.DataFrame(all_rows).to_csv("part2_3_summary_partial.csv", index=False)

    print("\n" + "#" * 100 + "\nPART 3a -- RAMPE DE RISQUE AU DEMARRAGE\n" + "#" * 100)
    for wr_label, wr_target, suffix in [("37.29%", None, "37_29pct"), ("32%", 0.32, "32pct")]:
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_target, 1.0, False, random.Random(POP_CONSTRUCT_SEED))
        total_h, marks, block_s, blocks = build_ctx(trades, slot_arrivals)
        for ramp_risk in [1.0, 1.5, 2.0]:
            for ramp_n in [5, 10, 15]:
                t0 = time.time()
                df = run_variant_ramp(trades, slot_arrivals, blocks, block_s, total_h, marks, market_data,
                                      excluded_map, ramp_risk, ramp_n, RISK)
                df.to_csv(f"part3a_ramp_{ramp_risk}_{ramp_n}_{suffix}.csv", index=False)
                row = summarize(df, f"ramp{ramp_risk}x{ramp_n}", {"winrate": wr_label, "ramp_risk": ramp_risk, "ramp_n": ramp_n})
                all_rows.append(row)
                print(f"  [{wr_label}] rampe {ramp_risk}% x{ramp_n} trades : profit {row['profit_final_mean']:+,.0f}$ | "
                      f"cash pire cas {row['cash_worst']:,.0f}$ | P(an1<0) {row['p_year1_negatif']:.2f}% ({time.time()-t0:.0f}s)")
        pd.DataFrame(all_rows).to_csv("part2_3_summary_partial.csv", index=False)

    print("\n" + "#" * 100 + "\nPART 3b -- PREMIER PALIER CROISSANCE REDUIT (25k)\n" + "#" * 100)
    for wr_label, wr_target, suffix in [("37.29%", None, "37_29pct"), ("32%", 0.32, "32pct")]:
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_target, 1.0, False, random.Random(POP_CONSTRUCT_SEED))
        total_h, marks, block_s, blocks = build_ctx(trades, slot_arrivals)
        for label, firms in [("FTMO_seul", {"FTMO"}), ("FTMO_BB", {"FTMO", "Blueberry"})]:
            t0 = time.time()
            df = run_variant_small_first_tier(trades, slot_arrivals, blocks, block_s, total_h, marks,
                                              market_data, excluded_map, RISK, firms)
            df.to_csv(f"part3b_smalltier_{label}_{suffix}.csv", index=False)
            row = summarize(df, f"smalltier_{label}", {"winrate": wr_label, "firms_25k": label})
            all_rows.append(row)
            print(f"  [{wr_label}] 1er palier 25k ({label}) : profit {row['profit_final_mean']:+,.0f}$ | "
                  f"cash pire cas {row['cash_worst']:,.0f}$ | P(an1<0) {row['p_year1_negatif']:.2f}% ({time.time()-t0:.0f}s)")
        pd.DataFrame(all_rows).to_csv("part2_3_summary_partial.csv", index=False)

    pd.DataFrame(all_rows).to_csv("part2_3_summary_final.csv", index=False)
    print(f"\nTerminé en {time.time()-t_start:.0f}s ({(time.time()-t_start)/60:.1f} min).")


if __name__ == "__main__":
    main()
