"""
Session 08/08 (suite, jour 4) -- Objectifs 2 et 3 : caracterisation fine du
P(annee1<0) residuel ET de la ruine residuelle sous la config finale
(echelonne FTMO=1k/Fivers=15k/GFT=25k/FundedNext=30k$).

Ajoute a l'instrumentation categorie A/B existante :
- un log brut des evenements de casse (time, firm, etait_finance_avant) par
  run, pour reconstituer apres-coup (en pandas, hors boucle de simulation)
  la repartition par firm/mois/etc. des runs annee1<0 et des runs ruines.
- des snapshots de profit a 18 et 24 mois (en plus du snapshot 12 mois deja
  existant) pour mesurer le delai de rattrapage precis du sous-groupe
  annee1<0 residuel.
- un flag "frozen_at_end" (n_active_accounts()==0 au tout dernier pas de
  temps simule) -- proxy operationnel du "gel definitif" de la flotte
  identifie dans le diagnostic de ruine de la session du 08/08 (§4.2,
  memoire project_ruin_risk_and_mitigation_2026-08-07).
- des snapshots total_breaks/temps au moment du deblocage complet
  (fleet_unlocked=True) et au moment du gel definitif (si applicable), pour
  mesurer le nombre de casses independantes et l'ecart de temps moyen entre
  elles menant a la ruine.
- un flag d'utilisation de l'amorcage protege (300$) par run.
"""
import random
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
from point123_startingfirm_optimization import GROUP_DEFS
from point_liquidity_rules import RAMP_RISK, RAMP_N, TARGET_RISK, CORR_TH, DAY_SECONDS
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from split_tax_model import compute_is, handle_tax_payment, IS_THRESHOLD_ACOMPTE, Q_OFFSETS_DAYS, \
    SOLDE_OFFSET_DAYS, ACOMPTE_FRACTION
from corrected_scaling_mechanism import FEE_RATIO, BASE_PALIER
from extra_account_v4_multi import (STARTER, DEFAULT_RESERVE, DEFAULT_EMERGENCY, SPLIT_FLAT, FINAL_RESERVE_SHARE,
                                     FINAL_EVAL_RISK, FINAL_FLEET_RISK, FINAL_GFT_EVAL_RISK, GROWTH_FIRMS_EXTRA,
                                     FUNDEDNEXT_FIXED_PALIER, FUNDEDNEXT_FIXED_COST, EXTRA_THRESHOLD_MULT,
                                     FIRM_CAPITAL_CAP, FIRM_MAX_ACCOUNTS, EXTRA_UNIT_PALIER, make_growth_acc,
                                     cost_for_extra)

ALPHA_POST, BETA_POST = 260, 388
YEAR_SECONDS = 365.25 * DAY_SECONDS
MONTH_SECONDS = DAYS_PER_MONTH * DAY_SECONDS
DEFAULT_RESERVE_FINAL = 30000.0


def seq_grouped_multi(t_ftmo, t_fivers, t_gft, t_fundednext):
    # (group_names, trigger, reserve_threshold, sets_fleet_unlocked)
    return [
        ((STARTER,), "day0", None, False),
        (("FTMO",), ("after_count", 1), t_ftmo, False),
        (("Fivers",), ("after_count", 1), t_fivers, False),
        (("GFT",), ("after_count", 1), t_gft, False),
        (("FundedNext",), ("after_count", 1), t_fundednext, True),
    ]


def run_one(trades, slot_arrivals, market_data, excluded_map, order, ceiling, seq_grouped,
            emergency_capital, target_risk_override, eval_risk_override, gft_eval_risk_override,
            reserve_share, extra_threshold_mult):
    accounts_by_group = {}
    active0_cost = 0.0
    for group_names, trigger, _thresh, _final in seq_grouped:
        for gname in group_names:
            gdef = GROUP_DEFS[gname]
            is_day0 = trigger == "day0"
            if gdef["kind"] == "fivers":
                accs = [eng.make_acc(eng.PALIER_5ERS, eng.SUMMER_COST, active=is_day0) for _ in range(gdef["n_accounts"])]
            elif gname == "FundedNext":
                accs = [make_growth_acc(FUNDEDNEXT_FIXED_PALIER, FUNDEDNEXT_FIXED_COST, active=is_day0)]
            else:
                accs = [make_growth_acc(BASE_PALIER[gname], round(BASE_PALIER[gname] * FEE_RATIO), active=is_day0)
                        for _ in range(gdef["n_accounts"])]
            for a in accs:
                a["_gname"] = gname
                a["ever_funded_self"] = False
            accounts_by_group[gname] = accs
            if is_day0:
                active0_cost += sum(a["cost"] for a in accs)

    extra_growth_firms = list(GROWTH_FIRMS_EXTRA)
    target_risk = target_risk_override if target_risk_override is not None else TARGET_RISK
    fleet_unlocked = False
    state = {"reserve": 0.0, "ever_funded": False, "real_cash_paid": active0_cost, "total_breaks": 0,
             "group_funded_count": 0, "group_own_funded": set(), "hit_ceiling": False,
             "emergency_remaining": emergency_capital, "is_paid_cum": 0.0,
             "tax_breach_count": 0, "tax_breach_total": 0.0, "tax_breach_max": 0.0,
             "tax_breach_concurrent_with_repurchase": 0, "tax_breach_events": [],
             "extra_accounts_opened": {g: 0 for g in extra_growth_firms},
             "starter_prefund_fees": 0.0, "fleet_unlock_cost": 0.0, "extra_account_open_cost": 0.0,
             "postfund_break_net_cost": 0.0,
             # --- tracking Objectifs 2/3 (session 08/08 jour 4) ---
             "break_log": [], "emergency_used_count": 0, "unlock_time": None, "total_breaks_at_unlock": None}
    pending_group_trigger = [(names, trig, thresh, final) for names, trig, thresh, final in seq_grouped if trig != "day0"]
    pending_reopen = []
    pending_group_open = []

    def combined_net():
        return sum(a["total_funded_pnl"] - a["total_fees_paid"] for accs in accounts_by_group.values() for a in accs)

    def n_active_accounts():
        return sum(1 for accs in accounts_by_group.values() for a in accs if a["active"])

    def downgrade_active():
        return not fleet_unlocked

    def cost_for_palier(gname, palier):
        if gname == "Fivers":
            return None
        if gname == "FundedNext":
            return FUNDEDNEXT_FIXED_COST
        return round(palier * FEE_RATIO)

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
        if downgrade_active() and acc.get("_gname") == STARTER:
            acc["palier"] = acc["base_palier"]
            acc["cost"] = acc["base_cost"]

    def open_group(gname, is_final):
        cost0 = sum(a["cost"] for a in accounts_by_group[gname])
        if gname != STARTER:
            state["fleet_unlock_cost"] += cost0
        for a in accounts_by_group[gname]:
            a["active"] = True
            a["total_fees_paid"] = a["cost"]

    def try_emergency_bootstrap():
        if n_active_accounts() != 0 or emergency_capital <= 0 or state["emergency_remaining"] <= 0:
            return
        bb_acc = accounts_by_group[STARTER][0]
        cost = bb_acc["base_cost"] if downgrade_active() else bb_acc["cost"]
        if state["emergency_remaining"] >= cost:
            state["emergency_remaining"] -= cost
            state["emergency_used_count"] += 1
            reopen_account(bb_acc, cost)
            pending_reopen[:] = [p for p in pending_reopen if p["key"] != id(bb_acc)]

    def process_trade(acc, trade, now, daily_loss_pct, gname, cost_override=None):
        if not acc["active"]:
            return False
        close_time = now + trade["hold_seconds"]
        acc["open_positions"] = [(t, c) for (t, c) in acc["open_positions"] if c > now]
        if len(acc["open_positions"]) >= eng.MAX_POSITIONS:
            return False
        if any(t in excluded_map[trade["ticker"]] for (t, _) in acc["open_positions"]):
            return False

        if acc["phase"] == "challenge":
            if gname == "GFT" and gft_eval_risk_override is not None:
                current_risk = gft_eval_risk_override
            elif eval_risk_override is not None:
                current_risk = eval_risk_override
            else:
                current_risk = RAMP_RISK if acc["trades_taken"] < RAMP_N else target_risk
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
            net_pnl = pnl * SPLIT_FLAT if pnl > 0 else pnl
            acc["total_funded_pnl"] += net_pnl
            if net_pnl > 0:
                state["reserve"] += net_pnl * reserve_share

        trailing_dd = acc["peak_since_reset"] - acc["cumulative_since_reset"]
        daily_dd = -acc["daily_pnl"][close_day]
        broke = (trailing_dd >= eng.BREAK_DD_PCT / 100 * acc["palier"] or daily_dd >= daily_loss_pct / 100 * acc["palier"])

        if broke:
            state["total_breaks"] += 1
            state["break_log"].append((now, gname, acc["ever_funded_self"]))
            if downgrade_active() and gname == STARTER:
                cost = acc["base_cost"]
            elif gname == "Fivers":
                cost = cost_override
            elif gname in ("FTMO", "GFT"):
                cost = cost_for_extra(gname, acc["palier"]) if acc["palier"] == 100000 else cost_for_palier(gname, acc["palier"])
            else:
                cost = cost_for_palier(gname, acc["palier"])
            if gname == STARTER and not acc["ever_funded_self"]:
                state["starter_prefund_fees"] += cost
            if acc["ever_funded_self"]:
                net_before = acc["total_funded_pnl"] - acc["total_fees_paid"]
                state["postfund_break_net_cost"] += max(0.0, cost - max(0.0, net_before))
            acc["active"] = False
            handle_cost_hybrid(cost, pending_reopen, id(acc), lambda a=acc, c=cost: reopen_account(a, c))
            return False

        if (acc["phase"] == "challenge" and acc["cumulative_since_reset"] >= eng.CHALLENGE_TARGET_PCT / 100 * acc["palier"]
                and len(acc["trading_days_since_reset"]) >= eng.MIN_TRADING_DAYS):
            acc["phase"] = "funded"
            state["ever_funded"] = True
            acc["ever_funded_self"] = True
            acc["cumulative_since_reset"] = 0.0
            acc["peak_since_reset"] = 0.0
            acc["trading_days_since_reset"] = set()
            return True
        return False

    def process_extra_account(now):
        if not fleet_unlocked:
            return
        for gname in extra_growth_firms:
            accs = accounts_by_group[gname]
            max_acc = FIRM_MAX_ACCOUNTS.get(gname)
            if max_acc is not None and len(accs) >= max_acc:
                continue
            unit_palier = EXTRA_UNIT_PALIER[gname]
            current_capital = sum(a["palier"] for a in accs)
            if current_capital + unit_palier > FIRM_CAPITAL_CAP[gname]:
                continue
            if gname in ("FTMO", "GFT"):
                extra_cost = cost_for_extra(gname, unit_palier)
            else:
                extra_cost = round(unit_palier * FEE_RATIO)
            if state["reserve"] >= extra_threshold_mult * extra_cost:
                state["reserve"] -= extra_cost
                state["extra_account_open_cost"] += extra_cost
                new_acc = make_growth_acc(unit_palier, extra_cost, active=True)
                new_acc["total_fees_paid"] = extra_cost
                new_acc["_gname"] = gname
                new_acc["ever_funded_self"] = False
                accs.append(new_acc)
                state["extra_accounts_opened"][gname] += 1

    def structure_complete():
        for g in ("Blueberry", "FTMO", "Fivers", "GFT", "FundedNext"):
            if not accounts_by_group[g][0]["active"]:
                return False
        return True

    fy_start_net = {0: 0.0}
    acomptes_paid_by_year = {}
    next_fy_to_close = 0
    tax_events = []

    def close_fiscal_year(y):
        profit_y = combined_net() - fy_start_net.get(y, 0.0)
        is_y = compute_is(profit_y)
        fy_start_net[y + 1] = combined_net()
        acomptes_y = acomptes_paid_by_year.get(y, 0.0)
        solde = max(0.0, is_y - acomptes_y)
        solde_time = (y + 1) * YEAR_SECONDS + SOLDE_OFFSET_DAYS * DAY_SECONDS
        tax_events.append((solde_time, solde))
        if is_y > IS_THRESHOLD_ACOMPTE:
            for q_off in Q_OFFSETS_DAYS:
                t_acompte = (y + 1) * YEAR_SECONDS + q_off * DAY_SECONDS
                amt = ACOMPTE_FRACTION * is_y
                tax_events.append((t_acompte, amt))
                acomptes_paid_by_year[y + 1] = acomptes_paid_by_year.get(y + 1, 0.0) + amt
        tax_events.sort(key=lambda e: e[0])

    full_structure_month = None
    year1_net_split = None
    year1_snapshot = {}
    catchup_month = None
    net_18mo = None
    net_24mo = None
    last_now = 0.0
    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]
        last_now = now

        if year1_net_split is None and now >= YEAR_SECONDS:
            year1_net_split = combined_net()
            year1_snapshot = dict(n_active=n_active_accounts(), fleet_unlocked=fleet_unlocked,
                                   reserve=state["reserve"], starter_prefund_fees=state["starter_prefund_fees"],
                                   fleet_unlock_cost=state["fleet_unlock_cost"],
                                   extra_account_open_cost=state["extra_account_open_cost"],
                                   postfund_break_net_cost=state["postfund_break_net_cost"])
        if year1_net_split is not None and catchup_month is None and now >= YEAR_SECONDS and combined_net() >= 0:
            catchup_month = now / MONTH_SECONDS
        if net_18mo is None and now >= 18 * MONTH_SECONDS:
            net_18mo = combined_net()
        if net_24mo is None and now >= 24 * MONTH_SECONDS:
            net_24mo = combined_net()

        while (next_fy_to_close + 1) * YEAR_SECONDS <= now:
            close_fiscal_year(next_fy_to_close)
            next_fy_to_close += 1

        i = 0
        while i < len(tax_events):
            t_ev, amt = tax_events[i]
            if t_ev > now:
                i += 1
                continue
            tax_events.pop(i)
            handle_tax_payment(amt, state, ceiling, now, pending_reopen, pending_group_open)
            state["is_paid_cum"] += amt

        for gname, accs in list(accounts_by_group.items()):
            gdef = GROUP_DEFS[gname]
            for acc in list(accs):
                cost_now = None
                if gdef["kind"] == "fivers":
                    cost_now = eng.SUMMER_COST if now < eng.PRICE_CUTOFF_SECONDS else eng.POST_SUMMER_COST_REAL
                was_challenge = acc["active"] and acc["phase"] == "challenge"
                just_funded = process_trade(acc, trade, now, gdef["dd"], gname, cost_override=cost_now)
                if was_challenge and just_funded and gname not in state["group_own_funded"]:
                    state["group_own_funded"].add(gname)
                    state["group_funded_count"] += 1

        process_extra_account(now)
        process_pending(pending_reopen)
        process_pending(pending_group_open)
        try_emergency_bootstrap()

        still_pending = []
        for group_names, trig, thresh, is_final in pending_group_trigger:
            _, n_req = trig
            if state["group_funded_count"] >= n_req and state["reserve"] >= thresh:
                for gname in group_names:
                    cost0 = sum(a["cost"] for a in accounts_by_group[gname])
                    handle_cost_hybrid(cost0, pending_group_open, gname, lambda g=gname, f=is_final: open_group(g, f))
                if is_final:
                    fleet_unlocked = True
                    state["unlock_time"] = now
                    state["total_breaks_at_unlock"] = state["total_breaks"]
            else:
                still_pending.append((group_names, trig, thresh, is_final))
        pending_group_trigger = still_pending

        if full_structure_month is None and structure_complete():
            full_structure_month = now / MONTH_SECONDS

    if year1_net_split is None:
        year1_net_split = combined_net()
        year1_snapshot = dict(n_active=n_active_accounts(), fleet_unlocked=fleet_unlocked,
                               reserve=state["reserve"], starter_prefund_fees=state["starter_prefund_fees"],
                               fleet_unlock_cost=state["fleet_unlock_cost"],
                               extra_account_open_cost=state["extra_account_open_cost"],
                               postfund_break_net_cost=state["postfund_break_net_cost"])
    if net_18mo is None:
        net_18mo = combined_net()
    if net_24mo is None:
        net_24mo = combined_net()

    frozen_at_end = n_active_accounts() == 0

    return {
        "final_net_split": combined_net(),
        "is_paid_cum": state["is_paid_cum"],
        "year1_net_split": year1_net_split,
        "year1_n_active": year1_snapshot["n_active"],
        "year1_fleet_unlocked": year1_snapshot["fleet_unlocked"],
        "year1_reserve": year1_snapshot["reserve"],
        "year1_starter_prefund_fees": year1_snapshot["starter_prefund_fees"],
        "year1_fleet_unlock_cost": year1_snapshot["fleet_unlock_cost"],
        "year1_extra_account_open_cost": year1_snapshot["extra_account_open_cost"],
        "year1_postfund_break_net_cost": year1_snapshot["postfund_break_net_cost"],
        "catchup_month": catchup_month,
        "net_18mo": net_18mo,
        "net_24mo": net_24mo,
        "frozen_at_end": frozen_at_end,
        "horizon_end_time": last_now,
        "unlock_time": state["unlock_time"],
        "total_breaks_at_unlock": state["total_breaks_at_unlock"],
        "total_breaks_final": state["total_breaks"],
        "emergency_used_count": state["emergency_used_count"],
        "break_log": state["break_log"],
    }


def run_propagated(pop, market_data, excluded_map, ceiling, seq_grouped, emergency, target_risk_ov, eval_risk_ov,
                    gft_eval_risk_ov, reserve_share, extra_threshold_mult, n_sims, seed):
    rng_wr = random.Random(seed)
    rng_boot = random.Random(seed + 1)
    rows = []
    for _ in range(n_sims):
        wr_draw = rng_wr.betavariate(ALPHA_POST, BETA_POST)
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_draw, 1.0, False, random.Random(rng_wr.random()))
        block_seconds = 2 * DAYS_PER_MONTH * DAY_SECONDS
        blocks = build_blocks(trades, slot_arrivals, block_seconds)
        target_duration = slot_arrivals[-1]
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot, target_duration)
        order = list(range(len(raw_trades)))
        res = run_one(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, seq_grouped, emergency,
                       target_risk_ov, eval_risk_ov, gft_eval_risk_ov, reserve_share, extra_threshold_mult)
        rows.append(res)
    return pd.DataFrame(rows)


THREE_MONTHS_SECONDS = 3 * MONTH_SECONDS
FIRMS = ("Blueberry", "FTMO", "Fivers", "GFT", "FundedNext")


def breaks_in_window(break_log, t_lo, t_hi):
    return [(t, g, f) for (t, g, f) in break_log if t_lo <= t < t_hi]


def firm_counts(events):
    counts = {g: 0 for g in FIRMS}
    for _, g, _ in events:
        counts[g] += 1
    return counts


def analyze_firm_weight(df, label):
    print(f"\n{'-'*100}\nOBJECTIF 3 (diagnostic) -- repartition par firm des casses, TOUS runs -- {label}\n{'-'*100}")
    all_events_y1 = [e for lst in df["break_log"].apply(lambda lg: breaks_in_window(lg, 0, YEAR_SECONDS)) for e in lst]
    counts = firm_counts(all_events_y1)
    total_ev = max(sum(counts.values()), 1)
    print(f"  Repartition par firm des casses (0-12 mois), TOUS les {len(df)} runs confondus (n_events={total_ev}) :")
    for g in FIRMS:
        print(f"      {g:12s} : {counts[g]:5d} ({counts[g]/total_ev*100:.1f}%)")
    print("  (a comparer a la repartition ci-dessus restreinte aux runs annee1<0 -- si proches, pas d'anomalie")
    print("   specifique aux runs malchanceux, juste le poids structurel de chaque firm dans la flotte)")


def analyze_year1_negative(df, label):
    print(f"\n{'-'*100}\nOBJECTIF 2 -- caracterisation P(annee1<0) residuel -- {label}\n{'-'*100}")
    neg = df[df["year1_net_split"] < 0]
    n_neg = len(neg)
    print(f"n runs annee1<0 = {n_neg}/{len(df)} ({n_neg/len(df)*100:.2f}%)")
    if n_neg == 0:
        return

    # point 1 : casses dans les 3 premiers mois, negatifs vs global
    neg_breaks_3mo = neg["break_log"].apply(lambda lg: len(breaks_in_window(lg, 0, THREE_MONTHS_SECONDS)))
    all_breaks_3mo = df["break_log"].apply(lambda lg: len(breaks_in_window(lg, 0, THREE_MONTHS_SECONDS)))
    print(f"\n  [1] Casses dans les 3 premiers mois : moy runs annee1<0={neg_breaks_3mo.mean():.2f} "
          f"| moy TOUS runs={all_breaks_3mo.mean():.2f} | ratio={neg_breaks_3mo.mean()/max(all_breaks_3mo.mean(),1e-9):.2f}x")

    # point 2 : firms impliquees dans les casses (jusqu'a 12 mois) des runs negatifs
    neg_breaks_y1 = neg["break_log"].apply(lambda lg: breaks_in_window(lg, 0, YEAR_SECONDS))
    all_events = [e for lst in neg_breaks_y1 for e in lst]
    counts = firm_counts(all_events)
    total_ev = max(sum(counts.values()), 1)
    print(f"\n  [2] Repartition par firm des casses (0-12 mois) des runs annee1<0 (n_events={total_ev}) :")
    for g in FIRMS:
        print(f"      {g:12s} : {counts[g]:4d} ({counts[g]/total_ev*100:.1f}%)")

    # point 3 : repartition temporelle (mois) des casses de ces runs
    months = [t / MONTH_SECONDS for (t, g, f) in all_events]
    if months:
        import numpy as np
        hist, edges = np.histogram(months, bins=[0, 2, 4, 6, 8, 10, 12])
        print(f"\n  [3] Repartition temporelle des casses (0-12 mois, bins de 2 mois) :")
        for i in range(len(hist)):
            print(f"      mois {edges[i]:.0f}-{edges[i+1]:.0f} : {hist[i]} ({hist[i]/len(months)*100:.1f}%)")

    # point 4 : rattrapage a 18/24 mois
    n_catchup_18 = (neg["net_18mo"] >= 0).sum()
    n_catchup_24 = (neg["net_24mo"] >= 0).sum()
    n_catchup_final = (neg["final_net_split"] - neg["is_paid_cum"] >= 0).sum()
    print(f"\n  [4] Rattrapage parmi les runs annee1<0 :")
    print(f"      >=0 a 18 mois : {n_catchup_18}/{n_neg} ({n_catchup_18/n_neg*100:.1f}%)")
    print(f"      >=0 a 24 mois : {n_catchup_24}/{n_neg} ({n_catchup_24/n_neg*100:.1f}%)")
    print(f"      >=0 a l'horizon final (~3.96 ans) : {n_catchup_final}/{n_neg} ({n_catchup_final/n_neg*100:.1f}%)")

    # point 5 : sous-groupe qui ne se rattrape jamais
    never_net = neg["final_net_split"] - neg["is_paid_cum"]
    never = neg[never_net < 0]
    rest_net = df["final_net_split"] - df["is_paid_cum"]
    rest = df.loc[~df.index.isin(never.index)]
    rest_net_only = rest["final_net_split"] - rest["is_paid_cum"]
    print(f"\n  [5] Sous-groupe annee1<0 qui NE se rattrape JAMAIS (ruine finale) : "
          f"{len(never)}/{n_neg} ({len(never)/n_neg*100:.1f}% des annee1<0, {len(never)/len(df)*100:.2f}% de tous les runs)")
    if len(never) > 0:
        never_final = never["final_net_split"] - never["is_paid_cum"]
        print(f"      Profit final moyen de ce sous-groupe : {never_final.mean():+,.0f}$ "
              f"(vs {rest_net_only.mean():+,.0f}$ pour le reste de la flotte)")


def analyze_ruin(df, label):
    print(f"\n{'-'*100}\nOBJECTIF 3 -- decomposition ruine residuelle -- {label}\n{'-'*100}")
    net = df["final_net_split"] - df["is_paid_cum"]
    ruined = df[net < 0]
    n_ruin = len(ruined)
    print(f"n runs ruines = {n_ruin}/{len(df)} ({n_ruin/len(df)*100:.2f}%)")
    if n_ruin == 0:
        return

    pct_frozen = ruined["frozen_at_end"].mean() * 100
    print(f"\n  [1] % des runs ruines avec flotte gelee (0 compte actif) a la fin de l'horizon : {pct_frozen:.1f}%")

    has_unlock = ruined[ruined["unlock_time"].notna()]
    print(f"      Runs ruines ayant atteint le deblocage complet : {len(has_unlock)}/{n_ruin} "
          f"({len(has_unlock)/n_ruin*100:.1f}%) -- le reste n'a jamais debloque le reste de la flotte")

    if len(has_unlock) > 0:
        n_breaks_post_unlock = has_unlock["total_breaks_final"] - has_unlock["total_breaks_at_unlock"]
        time_post_unlock_months = (has_unlock["horizon_end_time"] - has_unlock["unlock_time"]) / MONTH_SECONDS
        print(f"\n  [2] Casses independantes apres deblocage complet jusqu'a la fin : "
              f"moy={n_breaks_post_unlock.mean():.2f} | median={n_breaks_post_unlock.median():.1f}")
        gaps = []
        for lg, ut, het in zip(has_unlock["break_log"], has_unlock["unlock_time"], has_unlock["horizon_end_time"]):
            evs = sorted(t for (t, g, f) in lg if ut <= t <= het)
            if len(evs) >= 2:
                gaps.extend([(evs[i+1] - evs[i]) / 86400 for i in range(len(evs) - 1)])
        if gaps:
            import numpy as np
            print(f"      Ecart moyen entre casses consecutives post-deblocage : {np.mean(gaps):.1f} jours "
                  f"(median={np.median(gaps):.1f}j, n_gaps={len(gaps)})")

        # point 3 : firms impliquees
        post_unlock_events = []
        for lg, ut, het in zip(has_unlock["break_log"], has_unlock["unlock_time"], has_unlock["horizon_end_time"]):
            post_unlock_events.extend([(t, g, f) for (t, g, f) in lg if ut <= t <= het])
        counts = firm_counts(post_unlock_events)
        total_ev = max(sum(counts.values()), 1)
        print(f"\n  [3] Repartition par firm des casses post-deblocage menant a la ruine (n_events={total_ev}) :")
        for g in FIRMS:
            print(f"      {g:12s} : {counts[g]:4d} ({counts[g]/total_ev*100:.1f}%)")

        # point 4 : fenetre temporelle (mois depuis le deblocage jusqu'a la derniere casse / gel)
        print(f"\n  [4] Delai deblocage -> gel definitif (fin d'horizon) : "
              f"moy={time_post_unlock_months.mean():.2f} mois | median={time_post_unlock_months.median():.2f} mois")
        last_break_delay = []
        for lg, ut in zip(has_unlock["break_log"], has_unlock["unlock_time"]):
            evs = [t for (t, g, f) in lg if t >= ut]
            if evs:
                last_break_delay.append((max(evs) - ut) / MONTH_SECONDS)
        if last_break_delay:
            import numpy as np
            print(f"      Delai deblocage -> DERNIERE casse observee : moy={np.mean(last_break_delay):.2f} mois "
                  f"| median={np.median(last_break_delay):.2f} mois")

    # point 5 : amorcage protege
    n_emergency_used = (ruined["emergency_used_count"] > 0).sum()
    print(f"\n  [5] Runs ruines ou l'amorcage protege (300$) a ete utilise au moins une fois : "
          f"{n_emergency_used}/{n_ruin} ({n_emergency_used/n_ruin*100:.1f}%)")
    print(f"      (utilisation moyenne : {ruined['emergency_used_count'].mean():.2f} fois par run ruine)")


if __name__ == "__main__":
    import sys
    t_start = time.time()
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 600

    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

    # combo unique passable en CLI : "1-15-25-30" (FTMO-Fivers-GFT-FundedNext, en k$)
    if len(sys.argv) > 2:
        t_f, t_v, t_g, t_n = [float(x) * 1000 for x in sys.argv[2].split("-")]
        combo = (t_f, t_v, t_g, t_n)
    else:
        combo = (1000., 15000., 25000., 30000.)
    label = f"echelonne {combo[0]/1000:.1f}/{combo[1]/1000:.1f}/{combo[2]/1000:.1f}/{combo[3]/1000:.1f}k"

    for ceiling in (1000.0, 3000.0):
        print(f"\n{'='*100}\nPlafond {ceiling:.0f}$ (n={n_sims}) -- config finale {label}\n{'='*100}")
        seq = seq_grouped_multi(*combo)
        t0 = time.time()
        df = run_propagated(pop, market_data, excluded_map, ceiling, seq, DEFAULT_EMERGENCY,
                             FINAL_FLEET_RISK, FINAL_EVAL_RISK, FINAL_GFT_EVAL_RISK, FINAL_RESERVE_SHARE,
                             EXTRA_THRESHOLD_MULT, n_sims, seed=4000)
        net = df["final_net_split"] - df["is_paid_cum"]
        print(f"profit={net.mean():+,.0f}$ | ruine={(net < 0).sum()/len(df)*100:.2f}% | "
              f"P(annee1<0)={(df['year1_net_split'] < 0).sum()/len(df)*100:.2f}% ({time.time()-t0:.0f}s)")

        scalar_cols = [c for c in df.columns if c != "break_log"]
        df[scalar_cols].to_csv(f"extra_account_v4_full_diagnosis_ceiling{int(ceiling)}.csv", index=False)

        analyze_firm_weight(df, label)
        analyze_year1_negative(df, label)
        analyze_ruin(df, label)

    print(f"\nTermine en {time.time()-t_start:.0f}s.")
