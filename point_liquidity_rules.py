"""
Remplace l'hypothese silencieuse (shortfall de reserve absorbe sans jamais
etre verifie ni facture au-dela de l'immunite) par 2 regles operationnelles
reelles, sur la structure optimisee (Blueberry 25k seule day0, reste de la
flotte ensemble au 1er financement) :

  RULE "wait"    : rachat/ouverture RETARDE jusqu'a ce que la reserve ait
                   accumule le montant necessaire. Le compte reste ferme
                   entre-temps (flotte tourne avec un compte de moins). Aucune
                   depense personnelle au-dela de l'annee 1 pre-immunite.
  RULE "advance" : le manque de reserve est paye IMMEDIATEMENT par le trader,
                   TOUJOURS (meme apres immunite) -- pas de retard, mais le
                   cash pire cas peut reaugmenter indefiniment.
  RULE "old"     : hypothese silencieuse actuelle (reference, pour comparaison
                   uniquement) -- shortfall absorbe sans etre facture des que
                   ever_funded=True, jamais verifie.
"""
import random
import time

import numpy as np
import pandas as pd

import robustness_5ers_risk_challenge as eng
from point123_startingfirm_optimization import GROUP_DEFS, build_group_seq_map, make_accounts_for_group
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs

POP_CONSTRUCT_SEED = 123
TARGET_RISK = 2.5
RAMP_RISK, RAMP_N = 2.0, 5
CORR_TH = 0.6
DAY_SECONDS = 86400
MONTH_SECONDS = DAYS_PER_MONTH * DAY_SECONDS
N_SIMULATIONS = 2000

STARTER = "Blueberry"
FIRST_TIER_OVERRIDES = {"Blueberry": 25000}
REST_GROUPS = ("FTMO", "Fivers", "GFT", "FundedNext")
SEQUENCE = [((STARTER,), "day0"), (REST_GROUPS, ("after_count", 1))]


def handle_cost(cost, state, rule, pending_list, pending_key, on_success):
    """Gere le paiement d'un cout (rachat de challenge ou ouverture de groupe)
    selon la regle de liquidite choisie. on_success() est appele immediatement
    si le paiement peut avoir lieu tout de suite (cash suffisant OU regle
    'advance')."""
    if state["reserve"] >= cost:
        state["reserve"] -= cost
        on_success()
        return
    if rule == "wait":
        shortfall = cost - state["reserve"]
        state["reserve"] = 0.0
        pending_list.append({"key": pending_key, "cost_remaining": shortfall, "on_success": on_success})
    elif rule == "advance":
        shortfall = cost - state["reserve"]
        state["reserve"] = 0.0
        state["real_cash_paid"] += shortfall
        on_success()
    elif rule == "old":
        shortfall = cost - state["reserve"]
        state["reserve"] = 0.0
        if not state["ever_funded"]:
            state["real_cash_paid"] += shortfall
        on_success()
    else:
        raise ValueError(rule)


def process_pending(state, pending_list):
    """Regle 'wait' : verse a la reserve tout paiement en attente des que
    possible, FIFO, jusqu'a ce que la reserve ne suffise plus."""
    i = 0
    while i < len(pending_list):
        item = pending_list[i]
        if state["reserve"] >= item["cost_remaining"]:
            state["reserve"] -= item["cost_remaining"]
            item["on_success"]()
            pending_list.pop(i)
        else:
            i += 1


def run_one(trades, slot_arrivals, market_data, excluded_map, order, mark_seconds_list, rule):
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
             "group_funded_count": 0, "group_own_funded": set()}
    pending_group_trigger = [(names, trig) for names, trig in SEQUENCE if trig != "day0"]
    pending_reopen = []  # regle "wait" : comptes casses en attente de reouverture
    pending_group_open = []  # regle "wait" : groupes en attente d'ouverture faute de reserve

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
        accs = accounts_by_group[gname]
        for a in accs:
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
            handle_cost(cost, state, rule, pending_reopen, id(acc), lambda a=acc, c=cost: reopen_account(a, c))
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
                # upgrades : jamais retardes de force (rule "wait" ne s'applique
                # qu'aux rachats de casse et aux ouvertures de groupe -- un
                # upgrade non finance attend juste le prochain trade, comportement
                # deja identique dans toutes les versions precedentes)

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

        if rule == "wait":
            process_pending(state, pending_reopen)
            process_pending(state, pending_group_open)

        still_pending = []
        for group_names, trig in pending_group_trigger:
            _, n_req = trig
            if state["group_funded_count"] >= n_req:
                for gname in group_names:
                    cost0 = sum(a["cost"] for a in accounts_by_group[gname])
                    handle_cost(cost0, state, rule, pending_group_open, gname,
                               lambda g=gname: open_group(g))
            else:
                still_pending.append((group_names, trig))
        pending_group_trigger = still_pending

    while mark_idx < len(marks_sorted):
        snapshots.append((marks_sorted[mark_idx], combined_net(), state["real_cash_paid"], state["total_breaks"]))
        mark_idx += 1

    all_active = all(accounts_by_group[g][0]["active"] for g in ("FTMO", "Fivers", "GFT", "FundedNext")) and \
                 accounts_by_group["Blueberry"][0]["active"]
    return snapshots


def build_ctx(trades, slot_arrivals):
    total_horizon_seconds = slot_arrivals[-1]
    year_seconds = 365.25 * DAY_SECONDS
    mark_seconds_list = [year_seconds, total_horizon_seconds]
    block_seconds = eng.BLOCK_MONTHS * DAYS_PER_MONTH * 86400
    blocks = build_blocks(trades, slot_arrivals, block_seconds)
    return total_horizon_seconds, mark_seconds_list, block_seconds, blocks


def run_variant(trades, slot_arrivals, blocks, block_seconds, target_duration, mark_seconds_list,
               market_data, excluded_map, rule, n_sims=2000, seed=42):
    rng = random.Random(seed)
    rows = []
    for _ in range(n_sims):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, target_duration)
        order = list(range(len(raw_trades)))
        snaps = run_one(raw_trades, raw_slots, market_data, excluded_map, order, mark_seconds_list, rule)
        rows.append({"year1_net": snaps[0][1], "year1_cash": snaps[0][2], "year1_breaks": snaps[0][3],
                     "final_net": snaps[1][1], "final_cash": snaps[1][2], "final_breaks": snaps[1][3]})
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

        for rule in ["old", "wait", "advance"]:
            t0 = time.time()
            df = run_variant(trades, slot_arrivals, blocks, block_s, total_h, marks, market_data, excluded_map,
                             rule, n_sims=2000, seed=42)
            df.to_csv(f"point_liquidity_{rule}_{suffix}.csv", index=False)
            year1_cash = df["year1_cash"]
            row = dict(winrate=wr_label, rule=rule,
                      profit_year1_median=df["year1_net"].median(), profit_final_mean=df["final_net"].mean(),
                      cash_year1_median=year1_cash.median(), cash_year1_p90=year1_cash.quantile(0.9),
                      cash_year1_p95=year1_cash.quantile(0.95), cash_year1_p99=year1_cash.quantile(0.99),
                      cash_year1_max=year1_cash.max(), cash_final_max=df["final_cash"].max(),
                      casses_final=df["final_breaks"].mean())
            rows.append(row)
            print(f"  [{rule}] profit an1 median {row['profit_year1_median']:+,.0f}$ | profit final moyen {row['profit_final_mean']:+,.0f}$ | "
                  f"cash an1 median={row['cash_year1_median']:.0f}$ P90={row['cash_year1_p90']:.0f}$ P95={row['cash_year1_p95']:.0f}$ "
                  f"P99={row['cash_year1_p99']:.0f}$ MAX={row['cash_year1_max']:.0f}$ | cash pire cas horizon complet={row['cash_final_max']:.0f}$ "
                  f"({time.time()-t0:.0f}s)")
        pd.DataFrame(rows).to_csv("point_liquidity_summary_partial.csv", index=False)

    pd.DataFrame(rows).to_csv("point_liquidity_summary_final.csv", index=False)
    print(f"\nTerminé en {time.time()-t_start:.0f}s.")


if __name__ == "__main__":
    main()
