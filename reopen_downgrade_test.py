"""
Suite immediate de ruin_plateau_and_scenario_b.py (07/08 soir) : l'exemple de
trace caracteristique du mecanisme "Blueberry seul bloque" montre qu'apres un
premier scaling reussi (25k->200k via upgrade a 1000$), un compte qui casse
est RACHETE AU PALIER OU IL A CASSE (200k, cout 1000$) au lieu d'etre rachete
au palier de base (25k, cout 166$) -- ce qui draine la reserve/le cash reel
6x plus vite exactement dans la phase la plus fragile (compte seul, avant
deblocage du reste de la flotte).

Levier teste ici : au rachat (reopen), le compte est TOUJOURS reouvert a son
PALIER DE BASE (25k/166$ pour Blueberry, palier initial de sequence pour les
autres groupes "growth"), quel que soit le palier ou il a casse -- il regrandit
ensuite normalement via process_growth_upgrade si la reserve le permet. Compare
avec le comportement actuel (rachat au palier de casse) sur la config de
reference (reserve 30k + amorcage 300$ + split 80% flat) ET sur le meilleur
point scenario B deja trouve (eval=1,25%/flotte=2,0%).
"""
import random
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
from point123_startingfirm_optimization import GROUP_DEFS, build_group_seq_map, make_accounts_for_group
from point_liquidity_rules import RAMP_RISK, RAMP_N, TARGET_RISK, CORR_TH, DAY_SECONDS
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence

ALPHA_POST, BETA_POST = 260, 388
YEAR_SECONDS = 365.25 * DAY_SECONDS
MONTH_SECONDS = DAYS_PER_MONTH * DAY_SECONDS
STARTER = "Blueberry"
SEQ_GROUPED = [((STARTER,), "day0"), (("FTMO", "Fivers", "GFT", "FundedNext"), ("after_count", 1))]
DEFAULT_RESERVE = 30000.0
DEFAULT_EMERGENCY = 300.0
SPLIT_FLAT = 0.80


def run_one(trades, slot_arrivals, market_data, excluded_map, order, ceiling, min_reserve_for_unlock,
            emergency_capital, target_risk_override, eval_risk_override, apply_split=True,
            downgrade_on_reopen=False, log_breaks=False):
    seq_map = build_group_seq_map(SEQ_GROUPED, {STARTER: 25000})
    accounts_by_group = {}
    active0_cost = 0.0
    for group_names, trigger in SEQ_GROUPED:
        for gname in group_names:
            gdef = GROUP_DEFS[gname]
            is_day0 = trigger == "day0"
            accs = make_accounts_for_group(gname, gdef, active=is_day0, seq_map=seq_map)
            if gdef["kind"] == "growth" and gname == STARTER:
                # Downgrade-on-reopen scope limite au compte de demarrage (Blueberry) --
                # c'est le seul touche par le mecanisme "seul, bloque, rachat de plus
                # en plus cher" diagnostique dans ruin_plateau_and_scenario_b.py. Les
                # comptes du reste de la flotte (FTMO/GFT/FundedNext), une fois scales,
                # gardent leur palier au rachat -- perdre leur taille a chaque casse
                # couterait bien plus cher en profit que ce que ca gagnerait en cash.
                base_seq, base_cost_map, _, _ = seq_map[gname]
                for a in accs:
                    a["base_palier"] = base_seq[0]
                    a["base_cost"] = base_cost_map[base_seq[0]]
            accounts_by_group[gname] = accs
            if is_day0:
                active0_cost += sum(a["cost"] for a in accs)

    target_risk = target_risk_override if target_risk_override is not None else TARGET_RISK
    state = {"reserve": 0.0, "ever_funded": False, "real_cash_paid": active0_cost, "total_breaks": 0,
             "group_funded_count": 0, "group_own_funded": set(), "hit_ceiling": False,
             "emergency_remaining": emergency_capital}
    pending_group_trigger = [(names, trig) for names, trig in SEQ_GROUPED if trig != "day0"]
    pending_reopen = []
    pending_group_open = []
    break_log = []

    def combined_net():
        return sum(a["total_funded_pnl"] - a["total_fees_paid"] for accs in accounts_by_group.values() for a in accs)

    def n_active_accounts():
        return sum(1 for accs in accounts_by_group.values() for a in accs if a["active"])

    def handle_cost_hybrid(cost, pending_list, pending_key, on_success):
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
            remaining = shortfall - paid_now
            state["real_cash_paid"] += paid_now
            state["hit_ceiling"] = True
            pending_list.append({"key": pending_key, "cost_remaining": remaining, "on_success": on_success})

    def process_pending(pending_list):
        i = 0
        while i < len(pending_list):
            item = pending_list[i]
            if state["reserve"] >= item["cost_remaining"]:
                state["reserve"] -= item["cost_remaining"]
                item["on_success"]()
                pending_list.pop(i)
            else:
                i += 1

    def reopen_account(acc, cost):
        acc["active"] = True
        acc["total_fees_paid"] += cost
        acc["phase"] = "challenge"
        acc["cumulative_since_reset"] = 0.0
        acc["peak_since_reset"] = 0.0
        acc["trading_days_since_reset"] = set()
        acc["daily_pnl"] = {}
        if downgrade_on_reopen and "base_palier" in acc:
            acc["palier"] = acc["base_palier"]
            acc["cost"] = acc["base_cost"]

    def open_group(gname):
        for a in accounts_by_group[gname]:
            a["active"] = True
            a["total_fees_paid"] = a["cost"]

    def try_emergency_bootstrap():
        if n_active_accounts() != 0 or emergency_capital <= 0 or state["emergency_remaining"] <= 0:
            return
        bb_acc = accounts_by_group[STARTER][0]
        cost = bb_acc["base_cost"] if downgrade_on_reopen and "base_palier" in bb_acc else bb_acc["cost"]
        if state["emergency_remaining"] >= cost:
            state["emergency_remaining"] -= cost
            reopen_account(bb_acc, cost)
            pending_reopen[:] = [p for p in pending_reopen if p["key"] != id(bb_acc)]

    def process_trade(acc, trade, now, daily_loss_pct, cost_override=None):
        if not acc["active"]:
            return False
        close_time = now + trade["hold_seconds"]
        acc["open_positions"] = [(t, c) for (t, c) in acc["open_positions"] if c > now]
        if len(acc["open_positions"]) >= eng.MAX_POSITIONS:
            return False
        if any(t in excluded_map[trade["ticker"]] for (t, _) in acc["open_positions"]):
            return False

        if acc["phase"] == "challenge":
            current_risk = eval_risk_override if eval_risk_override is not None else (
                RAMP_RISK if acc["trades_taken"] < RAMP_N else target_risk)
        else:
            current_risk = RAMP_RISK if acc["trades_taken"] < RAMP_N else target_risk
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
            if apply_split and pnl > 0:
                net_pnl = pnl * SPLIT_FLAT
            else:
                net_pnl = pnl
            acc["total_funded_pnl"] += net_pnl
            if net_pnl > 0:
                state["reserve"] += net_pnl * eng.RESERVE_SHARE

        trailing_dd = acc["peak_since_reset"] - acc["cumulative_since_reset"]
        daily_dd = -acc["daily_pnl"][close_day]
        broke = (trailing_dd >= eng.BREAK_DD_PCT / 100 * acc["palier"] or daily_dd >= daily_loss_pct / 100 * acc["palier"])

        just_funded_own = False
        if broke:
            state["total_breaks"] += 1
            if downgrade_on_reopen and "base_palier" in acc:
                cost = acc["base_cost"]
            else:
                cost = cost_override if cost_override is not None else acc["cost"]
            if log_breaks:
                break_log.append((now / MONTH_SECONDS, acc["phase"], cost, acc["total_funded_pnl"],
                                   state["reserve"], n_active_accounts()))
            acc["active"] = False
            handle_cost_hybrid(cost, pending_reopen, id(acc), lambda a=acc, c=cost: reopen_account(a, c))
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

    full_structure_month = None
    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]

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
        process_pending(pending_reopen)
        process_pending(pending_group_open)
        try_emergency_bootstrap()

        still_pending = []
        for group_names, trig in pending_group_trigger:
            _, n_req = trig
            if state["group_funded_count"] >= n_req and state["reserve"] >= min_reserve_for_unlock:
                for gname in group_names:
                    cost0 = sum(a["cost"] for a in accounts_by_group[gname])
                    handle_cost_hybrid(cost0, pending_group_open, gname, lambda g=gname: open_group(g))
            else:
                still_pending.append((group_names, trig))
        pending_group_trigger = still_pending

        if full_structure_month is None and structure_complete():
            full_structure_month = now / MONTH_SECONDS

    return {"final_net": combined_net(), "full_structure_month": full_structure_month, "break_log": break_log}


def run_propagated(pop, market_data, excluded_map, ceiling, min_reserve, emergency, target_risk_ov, eval_risk_ov,
                    n_sims, seed, apply_split=True, downgrade_on_reopen=False, log_breaks=False):
    rng_wr = random.Random(seed)
    rng_boot = random.Random(seed + 1)
    rows = []
    all_breaks = []
    for _ in range(n_sims):
        wr_draw = rng_wr.betavariate(ALPHA_POST, BETA_POST)
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_draw, 1.0, False, random.Random(rng_wr.random()))
        block_seconds = 2 * DAYS_PER_MONTH * DAY_SECONDS
        blocks = build_blocks(trades, slot_arrivals, block_seconds)
        target_duration = slot_arrivals[-1]
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot, target_duration)
        order = list(range(len(raw_trades)))
        res = run_one(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, min_reserve, emergency,
                       target_risk_ov, eval_risk_ov, apply_split=apply_split,
                       downgrade_on_reopen=downgrade_on_reopen, log_breaks=log_breaks)
        all_breaks.append(res.pop("break_log"))
        rows.append(res)
    return pd.DataFrame(rows), all_breaks


if __name__ == "__main__":
    import sys
    t_start = time.time()
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 600

    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

    # configs testees : baseline (eval/flotte actuels) + meilleur point scenario B deja trouve (eval1.25/flotte2.0)
    configs = [
        ("baseline_2.5x2.5", None, None),
        ("scenarioB_eval1.25_fleet2.0", 2.0, 1.25),
    ]

    rows = []
    for ceiling in (1000.0, 3000.0):
        print(f"\n{'='*100}\nPLAFOND {ceiling:.0f}$\n{'='*100}")
        for label, fleet_ov, eval_ov in configs:
            for downgrade in (False, True):
                t0 = time.time()
                df, _ = run_propagated(pop, market_data, excluded_map, ceiling, DEFAULT_RESERVE, DEFAULT_EMERGENCY,
                                        fleet_ov, eval_ov, n_sims, seed=2000, apply_split=True,
                                        downgrade_on_reopen=downgrade)
                p5 = df["final_net"].quantile(0.05)
                n_neg = (df["final_net"] < 0).sum()
                row = dict(ceiling=ceiling, config=label, downgrade_on_reopen=downgrade,
                           profit_final_mean=df["final_net"].mean(), p5=p5,
                           p_ruine_pct=n_neg / len(df) * 100, delai_median=df["full_structure_month"].median())
                rows.append(row)
                tag = "AVEC downgrade" if downgrade else "SANS (actuel)"
                print(f"[{label} | {tag}] profit={row['profit_final_mean']:+,.0f}$ | P5={p5:+,.0f}$ | "
                      f"ruine={row['p_ruine_pct']:.2f}% | delai={row['delai_median']:.2f}mois ({time.time()-t0:.0f}s)")
        pd.DataFrame(rows).to_csv("reopen_downgrade_test.csv", index=False)

    pd.DataFrame(rows).to_csv("reopen_downgrade_test.csv", index=False)
    print(f"\nTermine en {time.time()-t_start:.0f}s.")
