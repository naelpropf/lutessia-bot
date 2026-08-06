"""
Regle hybride : avance personnelle immediate jusqu'a un PLAFOND defini (real_
cash_paid ne depasse jamais ce plafond, par construction), puis bascule vers
la regle "attente" (rachat/ouverture retarde) pour tout ce qui depasserait le
plafond. Balaye le plafond sur {500,1000,2000,3000,5000,7500,10000}$.

Reprend la structure de point_liquidity_rules.py (Blueberry 25k seule day0,
reste ensemble au 1er financement), meme moteur de compte/upgrade.
"""
import random
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
from point123_startingfirm_optimization import GROUP_DEFS, build_group_seq_map, make_accounts_for_group
from point_liquidity_rules import STARTER, FIRST_TIER_OVERRIDES, REST_GROUPS, SEQUENCE, build_ctx, RAMP_RISK, RAMP_N, TARGET_RISK, CORR_TH
from real_cash_risk_year1_block_bootstrap import DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs

POP_CONSTRUCT_SEED = 123
CEILINGS = [500, 1000, 2000, 3000, 5000, 7500, 10000]
DAY_SECONDS = 86400
MONTH_SECONDS = DAYS_PER_MONTH * DAY_SECONDS


def handle_cost_hybrid(cost, state, ceiling, pending_list, pending_key, on_success):
    """Avance perso immediate tant que real_cash_paid + montant <= plafond ;
    au-dela, la portion excedentaire est mise en attente (regle 'wait') --
    real_cash_paid ne peut donc JAMAIS depasser le plafond par construction."""
    if state["reserve"] >= cost:
        state["reserve"] -= cost
        on_success()
        return
    shortfall = cost - state["reserve"]
    state["reserve"] = 0.0
    room = max(0.0, ceiling - state["real_cash_paid"])
    if shortfall <= room:
        state["real_cash_paid"] += shortfall
        on_success()
    else:
        paid_now = room
        remaining = shortfall - room
        state["real_cash_paid"] += paid_now
        state["hit_ceiling"] = True
        pending_list.append({"key": pending_key, "cost_remaining": remaining, "on_success": on_success})


def process_pending(state, pending_list):
    i = 0
    while i < len(pending_list):
        item = pending_list[i]
        if state["reserve"] >= item["cost_remaining"]:
            state["reserve"] -= item["cost_remaining"]
            item["on_success"]()
            pending_list.pop(i)
        else:
            i += 1


def run_one(trades, slot_arrivals, market_data, excluded_map, order, mark_seconds_list, ceiling):
    seq_map = build_group_seq_map(SEQUENCE, FIRST_TIER_OVERRIDES)
    accounts_by_group = {}
    active0_cost = 0.0
    for group_names, trigger in SEQUENCE:
        for gname in group_names:
            gdef = GROUP_DEFS[gname]
            is_day0 = trigger == "day0"
            accs = make_accounts_for_group(gname, gdef, active=is_day0, seq_map=seq_map)
            accounts_by_group[gname] = accs
            if is_day0:
                active0_cost += sum(a["cost"] for a in accs)

    state = {"reserve": 0.0, "ever_funded": False, "real_cash_paid": active0_cost, "total_breaks": 0,
             "group_funded_count": 0, "group_own_funded": set(), "hit_ceiling": False,
             "full_structure_month": None}
    pending_group_trigger = [(names, trig) for names, trig in SEQUENCE if trig != "day0"]
    pending_reopen = []
    pending_group_open = []

    def combined_net():
        return sum(a["total_funded_pnl"] - a["total_fees_paid"] for accs in accounts_by_group.values() for a in accs)

    def reopen_account(acc, cost):
        acc["active"] = True
        acc["total_fees_paid"] += cost
        acc["phase"] = "challenge"
        acc["cumulative_since_reset"] = 0.0
        acc["peak_since_reset"] = 0.0
        acc["trading_days_since_reset"] = set()
        acc["daily_pnl"] = {}

    def open_group(gname):
        for a in accounts_by_group[gname]:
            a["active"] = True
            a["total_fees_paid"] = a["cost"]

    def process_trade(acc, trade, now, daily_loss_pct, cost_override=None):
        if not acc["active"]:
            return False
        close_time = now + trade["hold_seconds"]
        acc["open_positions"] = [(t, c) for (t, c) in acc["open_positions"] if c > now]
        if len(acc["open_positions"]) >= eng.MAX_POSITIONS:
            return False
        if any(t in excluded_map[trade["ticker"]] for (t, _) in acc["open_positions"]):
            return False

        current_risk = RAMP_RISK if acc["trades_taken"] < RAMP_N else TARGET_RISK
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
        broke = (trailing_dd >= eng.BREAK_DD_PCT / 100 * acc["palier"] or daily_dd >= daily_loss_pct / 100 * acc["palier"])

        just_funded_own = False
        if broke:
            state["total_breaks"] += 1
            cost = cost_override if cost_override is not None else acc["cost"]
            acc["active"] = False
            handle_cost_hybrid(cost, state, ceiling, pending_reopen, id(acc), lambda a=acc, c=cost: reopen_account(a, c))
            return False

        if (acc["phase"] == "challenge" and acc["cumulative_since_reset"] >= eng.CHALLENGE_TARGET_PCT / 100 * acc["palier"]
                and len(acc["trading_days_since_reset"]) >= eng.MIN_TRADING_DAYS):
            acc["phase"] = "funded"
            just_funded_own = True
            state["ever_funded"] = True
            acc["cumulative_since_reset"] = 0.0
            acc["peak_since_reset"] = 0.0
            acc["trading_days_since_reset"] = set()
        return just_funded_own

    def process_growth_upgrade():
        for gname, accs in accounts_by_group.items():
            gdef = GROUP_DEFS[gname]
            if gdef["kind"] != "growth":
                continue
            seq, cost_map, upgrade_map, cap = seq_map[gname]

            def combined(exclude_idx=None, accs=accs):
                return sum(a["palier"] for i, a in enumerate(accs) if i != exclude_idx and a["active"])

            for i, acc in enumerate(accs):
                if not acc["active"] or acc["phase"] != "funded":
                    continue
                idx = seq.index(acc["palier"])
                if idx + 1 >= len(seq):
                    continue
                next_tier = seq[idx + 1]
                ucost = upgrade_map[next_tier]
                would_be = combined(exclude_idx=i) + next_tier
                if would_be > cap:
                    continue
                if state["reserve"] >= ucost:
                    state["reserve"] -= ucost
                    acc["total_fees_paid"] += ucost
                    acc["palier"] = next_tier
                    acc["cost"] = cost_map[next_tier]
                    acc["phase"] = "challenge"
                    acc["cumulative_since_reset"] = 0.0
                    acc["peak_since_reset"] = 0.0
                    acc["trading_days_since_reset"] = set()

    def structure_complete():
        for g in ("Blueberry", "FTMO", "Fivers", "GFT", "FundedNext"):
            if not accounts_by_group[g][0]["active"]:
                return False
        return True

    marks_sorted = sorted(mark_seconds_list)
    mark_idx = 0
    snapshots = []

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]

        while mark_idx < len(marks_sorted) and now > marks_sorted[mark_idx]:
            snapshots.append((marks_sorted[mark_idx], combined_net(), state["real_cash_paid"], state["total_breaks"]))
            mark_idx += 1

        for gname, accs in accounts_by_group.items():
            gdef = GROUP_DEFS[gname]
            for acc in accs:
                cost_now = None
                if gdef["kind"] == "fivers":
                    cost_now = eng.SUMMER_COST if now < eng.PRICE_CUTOFF_SECONDS else eng.POST_SUMMER_COST_REAL
                was_challenge = acc["active"] and acc["phase"] == "challenge"
                process_trade(acc, trade, now, gdef["dd"], cost_override=cost_now)
                if was_challenge and acc["phase"] == "funded" and gname not in state["group_own_funded"]:
                    state["group_own_funded"].add(gname)
                    state["group_funded_count"] += 1

        process_growth_upgrade()
        process_pending(state, pending_reopen)
        process_pending(state, pending_group_open)

        still_pending = []
        for group_names, trig in pending_group_trigger:
            _, n_req = trig
            if state["group_funded_count"] >= n_req:
                for gname in group_names:
                    cost0 = sum(a["cost"] for a in accounts_by_group[gname])
                    handle_cost_hybrid(cost0, state, ceiling, pending_group_open, gname,
                                       lambda g=gname: open_group(g))
            else:
                still_pending.append((group_names, trig))
        pending_group_trigger = still_pending

        if state["full_structure_month"] is None and structure_complete():
            state["full_structure_month"] = now / MONTH_SECONDS

    while mark_idx < len(marks_sorted):
        snapshots.append((marks_sorted[mark_idx], combined_net(), state["real_cash_paid"], state["total_breaks"]))
        mark_idx += 1

    return snapshots, state["hit_ceiling"], state["full_structure_month"]


def run_variant(trades, slot_arrivals, blocks, block_seconds, target_duration, mark_seconds_list,
               market_data, excluded_map, ceiling, n_sims=2000, seed=42):
    rng = random.Random(seed)
    rows = []
    for _ in range(n_sims):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, target_duration)
        order = list(range(len(raw_trades)))
        snaps, hit_ceiling, full_month = run_one(raw_trades, raw_slots, market_data, excluded_map, order,
                                                  mark_seconds_list, ceiling)
        rows.append({"year1_net": snaps[0][1], "year1_cash": snaps[0][2], "year1_breaks": snaps[0][3],
                     "final_net": snaps[1][1], "final_cash": snaps[1][2], "final_breaks": snaps[1][3],
                     "hit_ceiling": hit_ceiling, "full_structure_month": full_month})
    return pd.DataFrame(rows)


def main():
    t_start = time.time()
    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

    rows = []
    for wr_label, wr_target, suffix in [("40.09%_reel", None, "40_09pct"), ("37.66%_P10bayesien", 0.3766, "37_66pct")]:
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_target, 1.0, False, random.Random(POP_CONSTRUCT_SEED))
        total_h, marks, block_s, blocks = build_ctx(trades, slot_arrivals)
        print(f"\n{'='*100}\nWINRATE {wr_label}\n{'='*100}")

        for ceiling in CEILINGS:
            t0 = time.time()
            df = run_variant(trades, slot_arrivals, blocks, block_s, total_h, marks, market_data, excluded_map,
                             ceiling, n_sims=2000, seed=42)
            df.to_csv(f"point_liquidity_hybrid_{ceiling}_{suffix}.csv", index=False)
            year1_cash = df["year1_cash"]
            row = dict(winrate=wr_label, ceiling=ceiling,
                      profit_year1_median=df["year1_net"].median(), profit_final_mean=df["final_net"].mean(),
                      cash_year1_median=year1_cash.median(), cash_year1_p90=year1_cash.quantile(0.9),
                      cash_year1_p95=year1_cash.quantile(0.95), cash_year1_p99=year1_cash.quantile(0.99),
                      cash_year1_max=year1_cash.max(), cash_final_max=df["final_cash"].max(),
                      p_hit_ceiling=df["hit_ceiling"].mean() * 100,
                      full_structure_month_median=df["full_structure_month"].median())
            rows.append(row)
            print(f"  [plafond={ceiling}$] profit an1 median {row['profit_year1_median']:+,.0f}$ | profit final moyen {row['profit_final_mean']:+,.0f}$ | "
                  f"cash an1: med={row['cash_year1_median']:.0f}$ P90={row['cash_year1_p90']:.0f}$ P95={row['cash_year1_p95']:.0f}$ "
                  f"P99={row['cash_year1_p99']:.0f}$ MAX={row['cash_year1_max']:.0f}$ | cash pire cas final={row['cash_final_max']:.0f}$ | "
                  f"P(plafond atteint)={row['p_hit_ceiling']:.1f}% | structure complete mois median={row['full_structure_month_median']:.1f} ({time.time()-t0:.0f}s)")
        pd.DataFrame(rows).to_csv("point_liquidity_hybrid_summary_partial.csv", index=False)

    pd.DataFrame(rows).to_csv("point_liquidity_hybrid_summary_final.csv", index=False)
    print(f"\nTerminé en {time.time()-t_start:.0f}s.")


if __name__ == "__main__":
    main()
