"""
Section 2 (08/11, prompt utilisateur) : diagnostic du residu ~1% hit_ceiling
sur la flotte SIMPLE a 10 000$ (chantier structurel precedent,
structure_pistes_2026-08-11.py mode D -- hit_ceiling_pct plafonne exactement
a 1,00% de 5000$ a 10000$, ne descend plus). Objectif : extraire les journaux
complets des runs qui touchent hit_ceiling a 10000$ (n=300, seed=9999,
IDENTIQUE au sweep D precedent -- meme RNG, memes tirages, reproductible),
verifier si le mecanisme correspond au mode deja identifie "effondrement
flotte mature" (§2.36-2.37 registre_parametres_projet.md -- clusters de 3-11
casses en <=3j touchant 2-4 firms, retombant sur une vraie fenetre de creux
d'edge type nov2022-jan2023), et mesurer sa probabilite empirique sur
l'ENSEMBLE n=300 (pas seulement les runs extremes).

Copie de edge_circuit_breaker_v2_2026-08-11.py pour le mecanisme de journal
d'evenements (process_trade_mf_logged/log_event), MOINS le coupe-circuit
(pause_mask retire, hors sujet ici) ; PLUS le seuil BB7j generalise en
>=3000$ (structure_pistes_2026-08-11.py, decision #16 §1.8/§2.35bis) --
edge_circuit_breaker_v2 datait d'avant cette decision et n'a jamais ce seuil.

N'importe pas ce script directement (convention du projet).
"""
import json
import os
import random
import sys
import time
from collections import Counter

import pandas as pd

import robustness_5ers_risk_challenge as eng
from point_liquidity_rules import CORR_TH, DAY_SECONDS
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from split_tax_model import compute_is, handle_tax_payment, IS_THRESHOLD_ACOMPTE, Q_OFFSETS_DAYS, \
    SOLDE_OFFSET_DAYS, ACOMPTE_FRACTION
from corrected_scaling_mechanism import BASE_PALIER

from engine_multiformat import FORMATS, make_acc_mf, _current_phase, _reset_trackers, _dd_max_breached
import etape_e_fleet_integration as ei

YEAR_SECONDS = 365.25 * DAY_SECONDS
MONTH_SECONDS = DAYS_PER_MONTH * DAY_SECONDS
SIX_MONTHS_SECONDS = 6 * MONTH_SECONDS
FIRMS = ("Blueberry", "FTMO", "Fivers", "GFT", "FundedNext")

HYSTERESIS = 0.10
FTMO_DISCOUNT_FACTOR = 0.90
GOAT_GUARD_SPLIT_DAYS = 30
GOAT_GUARD_SPLIT_FLAT = 0.50
PAYOUT_CYCLE_FIRMS = ("Blueberry", "GFT", "Fivers")
BB_7J_CEILING_THRESHOLD = 3000.0
PAYOUT_CYCLE_DAYS_FIRST = {"Blueberry": 14, "GFT": 3, "Fivers": 14}
PAYOUT_CYCLE_DAYS_SUBSEQUENT = {"Blueberry": 14, "GFT": 1.5, "Fivers": 14}
BB_PAYOUT_ADDON_MULT = 1.20

LOG_DIR = "structure_section2_logs"

# Mode "effondrement flotte mature" (§2.36-2.37 registre_parametres_projet.md) :
# fenetre historique creuse verifiee sur donnees reelles.
BAD_WINDOW_START = pd.Timestamp("2022-11-01")
BAD_WINDOW_END = pd.Timestamp("2023-01-20")


def price_for_bb(gname, fmt_key, palier, ceiling):
    price = ei.price_for(fmt_key, palier)
    bb_7j_active = ceiling >= BB_7J_CEILING_THRESHOLD
    return price * BB_PAYOUT_ADDON_MULT if (gname == "Blueberry" and bb_7j_active) else price


def payout_cycle_days(gname, first_payout_done, ceiling):
    if gname == "Blueberry" and ceiling >= BB_7J_CEILING_THRESHOLD:
        return 7
    table = PAYOUT_CYCLE_DAYS_SUBSEQUENT if first_payout_done else PAYOUT_CYCLE_DAYS_FIRST
    return table[gname]


def dd_distance_pct(acc, pdef):
    if pdef["dd_max_pct"] is None:
        return float("inf")
    if pdef["dd_max_mode"] == "static":
        current_dd = max(0.0, -acc["cumulative_since_reset"])
    elif pdef["dd_max_mode"] == "trailing_peak":
        ref = acc["locked_peak"] if acc["locked_peak"] is not None else acc["peak_since_reset"]
        current_dd = max(0.0, ref - acc["cumulative_since_reset"])
    else:
        current_dd = max(0.0, acc["eod_peak"] - acc["cumulative_since_reset"])
    return max(0.0, pdef["dd_max_pct"] - current_dd / acc["palier"] * 100)


def process_trade_mf_logged(acc, trade, now, fmt, state, risk_pct, market_data, excluded_map,
                             split_flat=0.80, reserve_share=0.95, cost_override=None):
    """Copie de engine_multiformat.process_trade_mf -- ajoute juste le type
    de breach ("daily"/"max"/None) en retour, comme edge_circuit_breaker_v2."""
    if not acc["active"]:
        return False, None
    close_time = now + trade["hold_seconds"]
    acc["open_positions"] = [(t, c) for (t, c) in acc["open_positions"] if c > now]
    if len(acc["open_positions"]) >= eng.MAX_POSITIONS:
        return False, None
    if any(t in excluded_map[trade["ticker"]] for (t, _) in acc["open_positions"]):
        return False, None

    eff_risk, _ = eng.feasible_risk_pct(trade["ticker"], trade["sl_distance"], acc["palier"], risk_pct, market_data)
    risk_amount = eff_risk / 100 * acc["palier"]
    pnl = trade["outcome_r"] * risk_amount

    acc["open_positions"].append((trade["ticker"], close_time))
    acc["cumulative_since_reset"] += pnl
    acc["peak_since_reset"] = max(acc["peak_since_reset"], acc["cumulative_since_reset"])
    acc["trading_days_since_reset"].add(int(now // DAY_SECONDS))
    acc["trades_taken"] += 1
    close_day = int(close_time // DAY_SECONDS)
    acc["daily_pnl"][close_day] = acc["daily_pnl"].get(close_day, 0.0) + pnl

    pdef = _current_phase(fmt, acc)

    if acc["phase"] == "funded":
        net_pnl = pnl * split_flat if pnl > 0 else pnl
        acc["total_funded_pnl"] += net_pnl
        if net_pnl > 0:
            state["reserve"] += net_pnl * reserve_share

    daily_broke = False
    if pdef["dd_daily_pct"] is not None:
        daily_dd = -acc["daily_pnl"][close_day]
        daily_broke = daily_dd >= pdef["dd_daily_pct"] / 100 * acc["palier"]
    max_broke = _dd_max_breached(acc, pdef, close_day)

    if daily_broke or max_broke:
        breach_type = "daily" if daily_broke else "max"
        cost = cost_override if cost_override is not None else acc["cost"]
        if state["reserve"] >= cost:
            state["reserve"] -= cost
        else:
            shortfall = cost - state["reserve"]
            state["reserve"] = 0.0
            if not state.get("ever_funded"):
                state["real_cash_paid"] = state.get("real_cash_paid", 0.0) + shortfall
        acc["total_fees_paid"] += cost
        if fmt["phases"]:
            acc["phase"] = "challenge"
            acc["phase_index"] = 0
        _reset_trackers(acc)
        return False, breach_type

    if acc["phase"] == "challenge" and pdef["target_pct"] is not None:
        days_ok = pdef["min_days"] is None or len(acc["trading_days_since_reset"]) >= pdef["min_days"]
        if acc["cumulative_since_reset"] >= pdef["target_pct"] / 100 * acc["palier"] and days_ok:
            just_funded = False
            if acc["phase_index"] + 1 < len(fmt["phases"]):
                acc["phase_index"] += 1
                _reset_trackers(acc)
            else:
                acc["phase"] = "funded"
                if not state.get("ever_funded"):
                    just_funded = True
                state["ever_funded"] = True
                _reset_trackers(acc)
            return just_funded, None

    return False, None


def run_one(trades, slot_arrivals, market_data, excluded_map, order, ceiling, seq_grouped, format_by_firm,
            emergency_capital, eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult,
            b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True,
            ftmo_discount=True, gft_goat_guard=True, payout_cycle=True, log_events=False):
    fmt_by_firm = {g: FORMATS[k] for g, k in format_by_firm.items()}
    event_log = [] if log_events else None
    acc_id_counter = {g: 0 for g in FIRMS}

    def next_acc_id(gname):
        i = acc_id_counter[gname]
        acc_id_counter[gname] += 1
        return f"{gname}_{i}"

    def log_event(now, gname, acc, ev_type, extra=None):
        if event_log is None:
            return
        rec = {"jour_simulation": round(now / 86400.0, 2), "firm": gname,
               "compte_id": acc.get("_acc_id", "?"), "type_evenement": ev_type,
               "reserve": round(state["reserve"], 2), "hit_ceiling": state["hit_ceiling"],
               "phase_deblocage": "post" if fleet_unlocked else "pre"}
        if extra:
            rec.update(extra)
        event_log.append(rec)

    def base_palier_cost(gname):
        if gname == "FundedNext":
            fmt_key = format_by_firm["FundedNext"]
            return ei.FUNDEDNEXT_PALIER, price_for_bb(gname, fmt_key, ei.FUNDEDNEXT_PALIER, ceiling)
        if gname == "Fivers":
            fmt_key = format_by_firm["Fivers"]
            palier = ei.FIVERS_PALIER[fmt_key]
            return palier, price_for_bb(gname, fmt_key, palier, ceiling)
        palier = BASE_PALIER[gname]
        return palier, price_for_bb(gname, format_by_firm[gname], palier, ceiling)

    accounts_by_group = {}
    active0_cost = 0.0
    for gname in FIRMS:
        is_day0 = (gname == ei.STARTER)
        palier, cost = base_palier_cost(gname)
        fmt = fmt_by_firm[gname]
        accs = [make_acc_mf(fmt, palier, cost=cost, active=is_day0) for _ in range(ei.N_ACCOUNTS_DAY0[gname])]
        for a in accs:
            a["_gname"] = gname
            a["_acc_id"] = next_acc_id(gname)
            a["base_palier"] = palier
            a["base_cost"] = cost
            a["_reset_used"] = False
            a["last_open_time"] = 0.0 if is_day0 else None
            a["_dd_reduced"] = False
            a["_gg_triggered_count"] = 0
            a["_gg_split_until"] = None
            a["pending_payout"] = 0.0
            a["last_payout_time"] = 0.0 if is_day0 else None
            a["_first_payout_done"] = False
        accounts_by_group[gname] = accs
        if is_day0:
            active0_cost += sum(a["cost"] for a in accs)

    fleet_unlocked = False
    _init_own_funded = {g for g in ("Blueberry",) if not fmt_by_firm[g]["phases"]}
    state = {"reserve": 0.0, "ever_funded": False, "real_cash_paid": active0_cost, "total_breaks": 0,
             "group_funded_count": len(_init_own_funded), "group_own_funded": set(_init_own_funded),
             "hit_ceiling": False, "emergency_remaining": emergency_capital, "is_paid_cum": 0.0,
             "extra_accounts_opened": {g: 0 for g in ei.GROWTH_FIRMS_EXTRA}, "_now": 0.0,
             "total_opens": sum(1 for accs in accounts_by_group.values() for a in accs if a["last_open_time"] == 0.0),
             "forfeited_pre": {g: 0.0 for g in PAYOUT_CYCLE_FIRMS}, "forfeited_post": {g: 0.0 for g in PAYOUT_CYCLE_FIRMS}}
    pending_group_trigger = [(names, trig, thresh, final) for names, trig, thresh, final in seq_grouped if trig != "day0"]
    pending_reopen = []
    pending_group_open = []

    def combined_net():
        return sum(a["total_funded_pnl"] - a["total_fees_paid"] for accs in accounts_by_group.values() for a in accs)

    def n_active_accounts():
        return sum(1 for accs in accounts_by_group.values() for a in accs if a["active"])

    def downgrade_active():
        return not fleet_unlocked

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
            if not state["hit_ceiling"]:
                log_event(state["_now"], None, {}, "hit_ceiling_touche")
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

    def reopen_account(acc, cost, fmt, skip_to_funded=False):
        acc["active"] = True
        acc["total_fees_paid"] += cost
        acc["phase"] = "funded" if (skip_to_funded or not fmt["phases"]) else "challenge"
        acc["phase_index"] = 0
        acc["cumulative_since_reset"] = 0.0
        acc["peak_since_reset"] = 0.0
        acc["trading_days_since_reset"] = set()
        acc["daily_pnl"] = {}
        acc["locked_peak"] = None
        acc["eod_peak"] = 0.0
        acc["last_day_seen"] = None
        acc["last_open_time"] = state["_now"]
        acc["_dd_reduced"] = False
        acc["_gg_triggered_count"] = 0
        acc["_gg_split_until"] = None
        acc["pending_payout"] = 0.0
        acc["last_payout_time"] = state["_now"]
        acc["_first_payout_done"] = False
        state["total_opens"] += 1
        if downgrade_active() and acc.get("_gname") == ei.STARTER:
            acc["palier"] = acc["base_palier"]
            acc["cost"] = acc["base_cost"]
        log_event(state["_now"], acc["_gname"], acc, "reouverture")

    def open_group(gname, is_final):
        for a in accounts_by_group[gname]:
            a["active"] = True
            a["total_fees_paid"] = a["cost"]
            a["last_open_time"] = state["_now"]
            a["_dd_reduced"] = False
            a["_gg_triggered_count"] = 0
            a["_gg_split_until"] = None
            a["pending_payout"] = 0.0
            a["last_payout_time"] = state["_now"]
            a["_first_payout_done"] = False
            state["total_opens"] += 1
            log_event(state["_now"], gname, a, "financement" if not fmt_by_firm[gname]["phases"] else "ouverture_challenge")
        if not fmt_by_firm[gname]["phases"]:
            if gname not in state["group_own_funded"]:
                state["group_own_funded"].add(gname)
                state["group_funded_count"] += 1

    def try_emergency_bootstrap():
        if n_active_accounts() != 0 or emergency_capital <= 0 or state["emergency_remaining"] <= 0:
            return
        bb_acc = accounts_by_group[ei.STARTER][0]
        cost = bb_acc["base_cost"] if downgrade_active() else bb_acc["cost"]
        if state["emergency_remaining"] >= cost:
            state["emergency_remaining"] -= cost
            reopen_account(bb_acc, cost, fmt_by_firm[ei.STARTER])
            pending_reopen[:] = [p for p in pending_reopen if p["key"] != id(bb_acc)]

    def process_extra_account(now):
        if not fleet_unlocked:
            return
        for gname in ei.GROWTH_FIRMS_EXTRA:
            accs = accounts_by_group[gname]
            max_acc = ei.FIRM_MAX_ACCOUNTS.get(gname)
            if max_acc is not None and len(accs) >= max_acc:
                continue
            unit_palier = BASE_PALIER[gname] * ei.EXTRA_ACCOUNT_MULT
            current_capital = sum(a["palier"] for a in accs)
            if current_capital + unit_palier > ei.FIRM_CAPITAL_CAP[gname]:
                continue
            extra_cost = price_for_bb(gname, format_by_firm[gname], unit_palier, ceiling)
            if state["reserve"] >= extra_threshold_mult * extra_cost:
                state["reserve"] -= extra_cost
                new_acc = make_acc_mf(fmt_by_firm[gname], unit_palier, cost=extra_cost, active=True)
                new_acc["total_fees_paid"] = extra_cost
                new_acc["_gname"] = gname
                new_acc["_acc_id"] = next_acc_id(gname)
                new_acc["base_palier"] = unit_palier
                new_acc["base_cost"] = extra_cost
                new_acc["_reset_used"] = False
                new_acc["last_open_time"] = now
                new_acc["_dd_reduced"] = False
                new_acc["_gg_triggered_count"] = 0
                new_acc["_gg_split_until"] = None
                new_acc["pending_payout"] = 0.0
                new_acc["last_payout_time"] = now
                new_acc["_first_payout_done"] = False
                accs.append(new_acc)
                state["extra_accounts_opened"][gname] += 1
                state["total_opens"] += 1
                log_event(now, gname, new_acc, "financement" if not fmt_by_firm[gname]["phases"] else "ouverture_challenge")

    def structure_complete():
        for g in FIRMS:
            if not accounts_by_group[g][0]["active"]:
                return False
        return True

    def effective_risk(acc, pdef, base_r):
        if pre_unlock_only and fleet_unlocked:
            return base_r
        dd_max = pdef["dd_max_pct"]
        if dd_max is None:
            return base_r
        distance = dd_distance_pct(acc, pdef)
        frac = distance / dd_max if dd_max > 0 else 1.0
        was_reduced = acc["_dd_reduced"]
        if not was_reduced and frac <= b_entry_frac:
            acc["_dd_reduced"] = True
        elif was_reduced and frac >= b_entry_frac + HYSTERESIS:
            acc["_dd_reduced"] = False
        mult = b_reduction if acc["_dd_reduced"] else 1.0
        return base_r * mult

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

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]
        state["_now"] = now

        if year1_net_split is None and now >= YEAR_SECONDS:
            year1_net_split = combined_net()

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
            fmt = fmt_by_firm[gname]
            base_risk = gft_eval_risk if gname == "GFT" else eval_risk
            use_payout_cycle = payout_cycle and gname in PAYOUT_CYCLE_FIRMS
            for acc in list(accs):
                if not acc["active"]:
                    continue
                base_r = fleet_risk if acc["phase"] == "funded" else base_risk
                pdef = _current_phase(fmt, acc)
                r = effective_risk(acc, pdef, base_r)
                was_challenge = acc["active"] and acc["phase"] == "challenge"
                was_funded = acc["active"] and acc["phase"] == "funded"
                phase_before, idx_before = acc["phase"], acc["phase_index"]
                split_this = GOAT_GUARD_SPLIT_FLAT if (gft_goat_guard and gname == "GFT"
                                                        and acc["_gg_split_until"] is not None
                                                        and now < acc["_gg_split_until"]) else 0.80

                funded_pnl_before = acc["total_funded_pnl"] if was_funded else None
                just_funded, breach_type = process_trade_mf_logged(
                    acc, trade, now, fmt, state, r, market_data, excluded_map,
                    split_flat=split_this, reserve_share=reserve_share, cost_override=0.0)

                if use_payout_cycle and was_funded:
                    delta = acc["total_funded_pnl"] - funded_pnl_before
                    if delta > 0:
                        acc["total_funded_pnl"] -= delta
                        state["reserve"] -= delta * reserve_share
                        acc["pending_payout"] += delta

                if just_funded and acc["last_open_time"] is not None:
                    log_event(now, gname, acc, "financement")

                if use_payout_cycle and acc["active"] and acc["last_payout_time"] is not None \
                        and now - acc["last_payout_time"] >= payout_cycle_days(gname, acc["_first_payout_done"], ceiling) * 86400:
                    acc["total_funded_pnl"] += acc["pending_payout"]
                    if acc["pending_payout"] > 0:
                        state["reserve"] += acc["pending_payout"] * reserve_share
                    acc["pending_payout"] = 0.0
                    acc["last_payout_time"] = now
                    acc["_first_payout_done"] = True

                progressed = (fmt["phases"] and (
                    (acc["phase"] == "challenge" and acc["phase_index"] == idx_before + 1) or
                    (acc["phase"] == "funded" and phase_before == "challenge")))
                if progressed and not (just_funded and acc["last_open_time"] is not None):
                    log_event(now, gname, acc, "passage_phase")
                reset_happened = (acc["cumulative_since_reset"] == 0.0 and acc["peak_since_reset"] == 0.0
                                  and len(acc["trading_days_since_reset"]) == 0)
                broke = reset_happened and not progressed

                use_goat_guard = (broke and gft_goat_guard and gname == "GFT" and was_funded
                                  and acc["_gg_triggered_count"] < 1)
                if use_goat_guard:
                    acc["_gg_triggered_count"] += 1
                    acc["_gg_split_until"] = now + GOAT_GUARD_SPLIT_DAYS * 86400
                    acc["phase"] = "funded"
                elif broke:
                    state["total_breaks"] += 1
                    if use_payout_cycle and acc["pending_payout"] != 0.0:
                        forfeited = max(0.0, acc["pending_payout"])
                        bucket = state["forfeited_post"] if fleet_unlocked else state["forfeited_pre"]
                        if forfeited > 0:
                            bucket[gname] += forfeited
                        acc["pending_payout"] = 0.0
                    log_event(now, gname, acc, "casse", {
                        "ticker": trade.get("ticker"), "r_realise": round(trade.get("outcome_r", 0.0), 3),
                        "type_dd": breach_type, "date_historique": str(trade.get("date"))})
                    use_bb_reset = (gname == "Blueberry" and was_funded and not acc["_reset_used"])
                    if use_bb_reset:
                        cost = 2.0 * acc["base_cost"]
                        acc["active"] = False
                        acc["_reset_used"] = True
                        handle_cost_hybrid(cost, pending_reopen, id(acc),
                                            lambda a=acc, c=cost, f=fmt: reopen_account(a, c, f, skip_to_funded=True))
                    else:
                        if downgrade_active() and gname == ei.STARTER:
                            cost = acc["base_cost"]
                        else:
                            cost = price_for_bb(gname, format_by_firm[gname], acc["palier"], ceiling)
                            if ftmo_discount and gname == "FTMO":
                                cost *= FTMO_DISCOUNT_FACTOR
                        acc["active"] = False
                        handle_cost_hybrid(cost, pending_reopen, id(acc),
                                            lambda a=acc, c=cost, f=fmt: reopen_account(a, c, f, skip_to_funded=False))
                else:
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
            else:
                still_pending.append((group_names, trig, thresh, is_final))
        pending_group_trigger = still_pending

        if full_structure_month is None and structure_complete():
            full_structure_month = now / MONTH_SECONDS

    if year1_net_split is None:
        year1_net_split = combined_net()

    pre = full_structure_month is None or full_structure_month > 12
    result = {"final_net_split": combined_net(), "is_paid_cum": state["is_paid_cum"],
              "year1_net_split": year1_net_split, "total_breaks": state["total_breaks"], "pre_deblocage": pre,
              "hit_ceiling": state["hit_ceiling"], "event_log": event_log}
    return result


def detect_cluster_mode(event_log):
    """Detecte le mode 'effondrement flotte mature' : clusters de 3-11
    casses en fenetre <=3 jours de simulation, touchant >=2 firms distinctes,
    ET dont les trades impliques tombent (au moins en partie) dans la vraie
    fenetre de creux d'edge nov2022-jan2023 (BAD_WINDOW). Meme grille que
    §2.36-2.37 registre_parametres_projet.md."""
    casses = [e for e in event_log if e["type_evenement"] == "casse"]
    if not casses:
        return False, []
    casses.sort(key=lambda e: e["jour_simulation"])
    clusters = []
    i = 0
    while i < len(casses):
        j = i
        firms_in_cluster = {casses[i]["firm"]}
        while j + 1 < len(casses) and casses[j + 1]["jour_simulation"] - casses[i]["jour_simulation"] <= 3:
            j += 1
            firms_in_cluster.add(casses[j]["firm"])
        size = j - i + 1
        if 3 <= size <= 11 and len(firms_in_cluster) >= 2:
            dates = [pd.Timestamp(casses[k]["date_historique"]) for k in range(i, j + 1)
                     if casses[k].get("date_historique") not in (None, "None", "NaT")]
            overlaps_bad_window = any(BAD_WINDOW_START <= d <= BAD_WINDOW_END for d in dates)
            clusters.append({"start_day": casses[i]["jour_simulation"], "size": size,
                              "n_firms": len(firms_in_cluster), "overlaps_bad_window": overlaps_bad_window})
        i = j + 1
    matches = [c for c in clusters if c["overlaps_bad_window"]]
    return len(matches) > 0, clusters


def main(n_sims, ceiling, seed=9999):
    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)
    seq = ei.seq_grouped_multi(1000, 15000, 25000, 25000)
    config = ei.CONFIG_REF
    EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK = 1.25, 1.90, 1.75

    rng_wr = random.Random(seed)
    rng_boot = random.Random(seed + 1)
    os.makedirs(LOG_DIR, exist_ok=True)

    n_hit_ceiling = 0
    n_matching_mode = 0
    all_cluster_summaries = []

    for run_idx in range(n_sims):
        wr_draw = rng_wr.betavariate(ei.ALPHA_POST, ei.BETA_POST)
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_draw, 1.0, False, random.Random(rng_boot.random()))
        block_seconds = 2 * 30 * DAY_SECONDS
        blocks = build_blocks(trades, slot_arrivals, block_seconds)
        target_duration = slot_arrivals[-1]
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot, target_duration)
        order = list(range(len(raw_trades)))

        res = run_one(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, seq, config,
                      ei.DEFAULT_EMERGENCY, EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                      ei.EXTRA_THRESHOLD_MULT, log_events=True)
        event_log = res.pop("event_log")
        matches_mode, clusters = detect_cluster_mode(event_log)
        if matches_mode:
            n_matching_mode += 1
        all_cluster_summaries.append({"run_idx": run_idx, "hit_ceiling": res["hit_ceiling"],
                                       "net_final": res["final_net_split"] - res["is_paid_cum"],
                                       "matches_mode": matches_mode, "n_clusters": len(clusters),
                                       "clusters": clusters})

        if res["hit_ceiling"]:
            n_hit_ceiling += 1
            run_id = f"ceiling{int(ceiling)}_run{run_idx}"
            with open(os.path.join(LOG_DIR, f"{run_id}.json"), "w", encoding="utf-8") as fh:
                json.dump({"run_id": run_id, "ceiling": ceiling, "net_final": res["final_net_split"] - res["is_paid_cum"],
                           "matches_effondrement_mode": matches_mode, "clusters": clusters,
                           "events": event_log}, fh, ensure_ascii=False, indent=1)
            print(f"[hit_ceiling run={run_idx}] net_final={res['final_net_split']-res['is_paid_cum']:+,.0f}$ "
                  f"matches_mode_effondrement={matches_mode} n_clusters_3-11_2firms={len(clusters)} "
                  f"journal -> {LOG_DIR}/{run_id}.json")

    print(f"\n[bilan n={n_sims}, ceiling={ceiling:.0f}$] hit_ceiling: {n_hit_ceiling}/{n_sims} "
          f"({n_hit_ceiling/n_sims*100:.2f}%) -- dont mode 'effondrement flotte mature' confirme (chevauche "
          f"nov22-jan23): {n_matching_mode}/{n_sims} ({n_matching_mode/n_sims*100:.2f}%)")
    pd.DataFrame([{k: v for k, v in d.items() if k != "clusters"} for d in all_cluster_summaries]).to_csv(
        f"structure_section2_diagnostic_n{n_sims}_ceiling{int(ceiling)}.csv", index=False)


if __name__ == "__main__":
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    ceiling = float(sys.argv[2]) if len(sys.argv) > 2 else 10000.0
    t_start = time.time()
    import rr_threshold_test as rrt
    print(f"[verif] HIST_PATH = {rrt.HIST_PATH}, FIRM_MAX_ACCOUNTS Blueberry = {ei.FIRM_MAX_ACCOUNTS['Blueberry']}")
    main(n_sims, ceiling)
    print(f"\nTermine en {time.time()-t_start:.0f}s.")
