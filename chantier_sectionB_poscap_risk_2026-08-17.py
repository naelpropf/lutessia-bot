"""
Section A (reouverture, boost+downsizing PERMANENT) - 2026-08-17.

Etape 0 (chantier_A_rr_sizing_diagnostic2_2026-08-17.py, granularite fine
decile/ventile/largeur-fixe) : **0/10 deciles, 0/20 ventiles a EV
REELLEMENT NEGATIVE** (les 2 seules tranches negatives sont a n=1, bruit).
Donc PAS de segment veritablement negatif meme a granularite fine -- dit
explicitement, sans reformuler. Cible utilisee ici = segments SOUS LA
MOYENNE globale (+0.893R), distinction assumee et signalee (pas des
segments negatifs).

Contribution aux PERTES (Question 2, meme diagnostic) : perte moyenne=
perte max=-1.000R pour TOUS les deciles (chaque trade perdant sort
exactement a -1R, mecanisme de stop plein -- aucune variation de magnitude
possible entre segments par construction). Ratio contribution-aux-pertes/
poids-population entre 0.85 et 1.14 pour tous les deciles -- AUCUNE
surrepresentation notable (seuil >1.2 jamais atteint). Le rationnel
"segment faible = surrepresente dans les pertes/casses" ne tient donc PAS
empiriquement -- ce candidat teste une redistribution EV pure (deplacer du
risque des segments sous-moyenne vers le seuil deja valide >=8), pas une
reduction de frequence/magnitude de pertes.

2 familles de segments "faibles" testees (5 sous la moyenne au niveau
decile, mais SCATTERED/non-contigus -- signale explicitement, la
non-contiguite est elle-meme un signe de bruit plutot qu'un vrai segment
structurel) :
  A4_worst_decile : SEUL le decile le plus faible, rr_tp2 in [3.0,3.5)
                    (EV=+0.266R, sous l'IC95%% bas), candidat le plus
                    conservateur/le moins expose au bruit de decoupage.
  A5_below_mean   : TOUS les deciles sous la moyenne globale, rr_tp2 in
                    [1.734,3.5) U [3.944,5.083) U [5.663,6.455) (5 deciles
                    sur 10, EV 0.266-0.562R), candidat plus large mais
                    plus expose au risque de surajustement au bruit
                    (deciles non contigus).
Chaque famille testee a x0.5 ET x0.8 (ancrages demandes). Boost x1.6 sur
rr_tp2>=8 MAINTENU (deja valide S2.35). REF recalculee dans le MEME
script/seed.
"""
import random
import sys
import time

import numpy as np
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

from engine_multiformat import FORMATS, make_acc_mf, process_trade_mf, _current_phase
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
PAYOUT_CYCLE_DAYS_FIRST = {"Blueberry": 14, "GFT": 3, "Fivers": 14}
PAYOUT_CYCLE_DAYS_SUBSEQUENT = {"Blueberry": 14, "GFT": 1.5, "Fivers": 14}

BB_CLASSIC_KEY = "Blueberry_Prime2Step"
BB_INSTANT_KEY = "Blueberry_InstantElite"
MIN_RR_NEW, CORR_TH_NEW = 1.35, 0.80
EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK = 1.25, 1.90, 1.75

BB_PAYOUT_ADDON_MULT = 1.20
BB_PAYOUT_7J_CEILINGS = {3000.0}


def price_for_bb(fmt_key, palier, ceiling):
    price = ei.price_for(fmt_key, palier)
    bb_7j_active = (fmt_key == BB_CLASSIC_KEY and ceiling in BB_PAYOUT_7J_CEILINGS)
    return price * BB_PAYOUT_ADDON_MULT if bb_7j_active else price


def bb_payout_days(fmt_key, ceiling, first_payout_done):
    if fmt_key == BB_CLASSIC_KEY and ceiling in BB_PAYOUT_7J_CEILINGS:
        return 7
    table = PAYOUT_CYCLE_DAYS_SUBSEQUENT if first_payout_done else PAYOUT_CYCLE_DAYS_FIRST
    return table["Blueberry"]


# ============================================================
# <<< CHANTIER A : 3 candidats de sizing + reference, tous bornes a x1.6
# ============================================================
DAILY_DD_STRICT = 4.0  # % (Blueberry_Prime2Step/GFT_2Step_GOAT/FundedNext_StellarLite)
FLEET_RISK_BASE = 1.90  # % (funded, cas le plus contraignant)


def margin_pct(mult):
    max_risk = FLEET_RISK_BASE * mult
    return (DAILY_DD_STRICT - max_risk) / DAILY_DD_STRICT * 100


def make_size_func_tail(mult, threshold=8.0):
    def f(rr_tp2):
        return mult if rr_tp2 >= threshold else 1.0
    return f


def make_size_func_step2(low_mult=1.3, high_mult=1.6, low_th=6.5, high_th=8.0):
    def f(rr_tp2):
        if rr_tp2 >= high_th:
            return high_mult
        if rr_tp2 >= low_th:
            return low_mult
        return 1.0
    return f


def make_size_func_ramp(start=6.0, end=15.0, max_mult=1.6):
    def f(rr_tp2):
        if rr_tp2 <= start:
            return 1.0
        if rr_tp2 >= end:
            return max_mult
        frac = (rr_tp2 - start) / (end - start)
        return 1.0 + (max_mult - 1.0) * frac
    return f


def make_size_func_decile_full(pop, max_mult=1.6):
    edges = pop["rr_tp2"].quantile([i / 10 for i in range(1, 10)]).to_numpy()
    mults = np.linspace(1.0, max_mult, 10)

    def f(rr_tp2):
        idx = int(np.searchsorted(edges, rr_tp2, side="right"))
        idx = min(idx, 9)
        return float(mults[idx])
    return f


def make_size_func_downsize(low_ranges, low_mult, tail_mult=1.6, tail_th=8.0):
    def f(rr_tp2):
        if rr_tp2 >= tail_th:
            return tail_mult
        for lo, hi in low_ranges:
            if lo <= rr_tp2 < hi:
                return low_mult
        return 1.0
    return f


WORST_DECILE_RANGE = [(3.0, 3.5)]  # decile le plus faible seul (EV=+0.266R, sous IC95% bas)
BELOW_MEAN_RANGES = [(1.734, 3.5), (3.944, 5.083), (5.663, 6.455)]  # 5 deciles sous la moyenne (scattered)


def payout_cycle_days(gname, first_payout_done):
    table = PAYOUT_CYCLE_DAYS_SUBSEQUENT if first_payout_done else PAYOUT_CYCLE_DAYS_FIRST
    return table[gname]


def build_flexible_population_with_rr(pop, target_winrate, rr_stress_factor, use_slippage, rng):
    trades, slot_arrivals = eng.build_flexible_population(pop, target_winrate, rr_stress_factor, use_slippage, rng)
    sub = pop.sort_values("date_creation").reset_index(drop=True)
    assert len(sub) == len(trades), "desynchronisation build_flexible_population_with_rr"
    for t, rr1, rr2 in zip(trades, sub["rr_tp1"], sub["rr_tp2"]):
        t["rr_tp1"] = float(rr1)
        t["rr_tp2"] = float(rr2)
    return trades, slot_arrivals


def process_trade_corr_swap_rr(acc, trade, now, fmt, state, risk_pct, market_data, excluded_map,
                                split_flat=0.80, reserve_share=0.95, cost_override=None, routing_field="rr_tp1"):
    if not acc["active"]:
        return False

    acc["open_positions"] = [(t, c) for (t, c) in acc["open_positions"] if c > now]
    acc["_open_meta_rr"] = [m for m in acc.get("_open_meta_rr", []) if m["close_time"] > now]

    new_ticker = trade["ticker"]
    new_rr = trade[routing_field]
    at_cap = len(acc["open_positions"]) >= eng.MAX_POSITIONS
    evicted_this_call = False
    if not at_cap:
        conflicts = [m for m in acc["_open_meta_rr"] if m["ticker"] in excluded_map[new_ticker]]
        if len(conflicts) == 1:
            occ = conflicts[0]
            if new_rr > occ["rr"]:
                acc["open_positions"] = [p for p in acc["open_positions"]
                                          if not (p[0] == occ["ticker"] and p[1] == occ["close_time"])]
                acc["_open_meta_rr"] = [m for m in acc["_open_meta_rr"] if m is not occ]
                state["corr_swap_evictions"] = state.get("corr_swap_evictions", 0) + 1
                evicted_this_call = True

    n_before = len(acc["open_positions"])
    result = process_trade_mf(acc, trade, now, fmt, state, risk_pct, market_data, excluded_map,
                               split_flat=split_flat, reserve_share=reserve_share, cost_override=cost_override)
    if len(acc["open_positions"]) > n_before:
        new_t, new_c = acc["open_positions"][-1]
        acc.setdefault("_open_meta_rr", []).append({"ticker": new_t, "close_time": new_c, "rr": new_rr})
        if evicted_this_call:
            state["corr_swap_admits"] = state.get("corr_swap_admits", 0) + 1
    return result


# ============================================================
# Moteur de flotte complet (copie chantier_rrtp2_sizing_2026-08-16.py, inchange)
# ============================================================

def run_one(trades, slot_arrivals, market_data, excluded_map, order, ceiling, seq_grouped, format_by_firm,
            emergency_capital, eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult,
            b_entry_frac=None, b_reduction=None, pre_unlock_only=False,
            ftmo_discount=False, gft_goat_guard=False, payout_cycle=False,
            bb_threshold=float("inf"), use_any_rr=False, size_func=None, routing_field="rr_tp1"):
    fmt_by_firm = {g: FORMATS[k] for g, k in format_by_firm.items()}

    def bb_choose_fmt_key():
        return BB_INSTANT_KEY if state["reserve"] >= bb_threshold else BB_CLASSIC_KEY

    def base_palier_cost(gname):
        if gname == "FundedNext":
            fmt_key = format_by_firm["FundedNext"]
            return ei.FUNDEDNEXT_PALIER, ei.price_for(fmt_key, ei.FUNDEDNEXT_PALIER)
        if gname == "Fivers":
            fmt_key = format_by_firm["Fivers"]
            palier = ei.FIVERS_PALIER[fmt_key]
            return palier, ei.price_for(fmt_key, palier)
        palier = BASE_PALIER[gname]
        return palier, ei.price_for(format_by_firm[gname], palier)

    accounts_by_group = {}
    active0_cost = 0.0
    state = {"reserve": 0.0}
    for gname in FIRMS:
        is_day0 = (gname == ei.STARTER)
        if gname == "Blueberry":
            fmt_key = bb_choose_fmt_key() if is_day0 else BB_CLASSIC_KEY
            fmt = FORMATS[fmt_key]
            palier = BASE_PALIER["Blueberry"]
            cost = price_for_bb(fmt_key, palier, ceiling)
        else:
            fmt_key = format_by_firm[gname]
            palier, cost = base_palier_cost(gname)
            fmt = fmt_by_firm[gname]
        accs = [make_acc_mf(fmt, palier, cost=cost, active=is_day0) for _ in range(ei.N_ACCOUNTS_DAY0[gname])]
        for a in accs:
            a["_gname"] = gname
            a["_fmt_key"] = fmt_key
            a["base_palier"] = palier
            a["base_cost"] = cost
            a["_reset_used"] = False
            a["last_open_time"] = 0.0 if is_day0 else None
            a["_dd_reduced"] = False
            a["_dd_oscillations"] = 0
            a["_gg_triggered_count"] = 0
            a["_gg_split_until"] = None
            a["pending_payout"] = 0.0
            a["last_payout_time"] = 0.0 if is_day0 else None
            a["_first_payout_done"] = False
        accounts_by_group[gname] = accs
        if is_day0:
            active0_cost += sum(a["cost"] for a in accs)

    fleet_unlocked = False
    _init_own_funded = {g for g in ("Blueberry",) if not FORMATS[accounts_by_group[g][0]["_fmt_key"]]["phases"]}
    state.update({"ever_funded": False, "real_cash_paid": active0_cost, "total_breaks": 0,
             "group_funded_count": len(_init_own_funded), "group_own_funded": set(_init_own_funded),
             "hit_ceiling": False, "emergency_remaining": emergency_capital, "is_paid_cum": 0.0,
             "extra_accounts_opened": {g: 0 for g in ei.GROWTH_FIRMS_EXTRA},
             "tax_breach_count": 0, "tax_breach_total": 0.0, "tax_breach_max": 0.0,
             "tax_breach_concurrent_with_repurchase": 0, "tax_breach_events": [], "_now": 0.0,
             "total_opens": sum(1 for accs in accounts_by_group.values() for a in accs if a["last_open_time"] == 0.0),
             "breaks_within_30d": 0, "breaks_within_60d": 0, "blueberry_resets_used": 0,
             "dd_reduced_obs": 0, "dd_total_obs": 0, "funding_delays": [], "gft_soft_breaches": 0,
             "forfeited_pre": {g: 0.0 for g in PAYOUT_CYCLE_FIRMS}, "forfeited_post": {g: 0.0 for g in PAYOUT_CYCLE_FIRMS},
             "forfeit_events_pre": {g: 0 for g in PAYOUT_CYCLE_FIRMS}, "forfeit_events_post": {g: 0 for g in PAYOUT_CYCLE_FIRMS},
             "bb_instant_opens": 0, "bb_classic_opens": 0,
             "corr_swap_evictions": 0, "corr_swap_admits": 0})
    pending_group_trigger = [(names, trig, thresh, final) for names, trig, thresh, final in seq_grouped if trig != "day0"]
    pending_reopen = []
    pending_group_open = []

    def mark_group_funded_if_needed(gname):
        if gname not in state["group_own_funded"]:
            state["group_own_funded"].add(gname)
            state["group_funded_count"] += 1

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
        acc["cost"] = cost
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
        if downgrade_active() and acc.get("_gname") == ei.STARTER and acc.get("_fmt_key") == BB_CLASSIC_KEY:
            acc["palier"] = acc["base_palier"]

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
        if not fmt_by_firm[gname]["phases"]:
            mark_group_funded_if_needed(gname)

    def try_emergency_bootstrap():
        if n_active_accounts() != 0 or emergency_capital <= 0 or state["emergency_remaining"] <= 0:
            return
        bb_acc = accounts_by_group[ei.STARTER][0]
        cost = bb_acc["base_cost"] if downgrade_active() else bb_acc["cost"]
        if state["emergency_remaining"] >= cost:
            state["emergency_remaining"] -= cost
            reopen_account(bb_acc, cost, FORMATS[bb_acc["_fmt_key"]])
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
            if gname == "Blueberry":
                extra_fmt_key = bb_choose_fmt_key()
                extra_fmt = FORMATS[extra_fmt_key]
                extra_cost = price_for_bb(extra_fmt_key, unit_palier, ceiling)
            else:
                extra_fmt_key = format_by_firm[gname]
                extra_fmt = fmt_by_firm[gname]
                extra_cost = ei.price_for(extra_fmt_key, unit_palier)
            if state["reserve"] >= extra_threshold_mult * extra_cost:
                state["reserve"] -= extra_cost
                new_acc = make_acc_mf(extra_fmt, unit_palier, cost=extra_cost, active=True)
                new_acc["total_fees_paid"] = extra_cost
                new_acc["_gname"] = gname
                new_acc["_fmt_key"] = extra_fmt_key
                new_acc["base_palier"] = unit_palier
                new_acc["base_cost"] = extra_cost
                new_acc["_reset_used"] = False
                new_acc["last_open_time"] = now
                new_acc["_dd_reduced"] = False
                new_acc["_dd_oscillations"] = 0
                new_acc["_gg_triggered_count"] = 0
                new_acc["_gg_split_until"] = None
                new_acc["pending_payout"] = 0.0
                new_acc["last_payout_time"] = now
                new_acc["_first_payout_done"] = False
                accs.append(new_acc)
                state["extra_accounts_opened"][gname] += 1
                state["total_opens"] += 1
                if gname == "Blueberry":
                    if extra_fmt_key == BB_INSTANT_KEY:
                        state["bb_instant_opens"] += 1
                    else:
                        state["bb_classic_opens"] += 1

    def structure_complete():
        for g in FIRMS:
            if not accounts_by_group[g][0]["active"]:
                return False
        return True

    def effective_risk(acc, pdef, base_r):
        if b_entry_frac is None:
            return base_r
        if pre_unlock_only and fleet_unlocked:
            return base_r
        dd_max = pdef["dd_max_pct"]
        if dd_max is None:
            return base_r
        distance = dd_distance_pct(acc, pdef)
        frac = distance / dd_max if dd_max > 0 else 1.0
        state["dd_total_obs"] += 1
        was_reduced = acc["_dd_reduced"]
        if not was_reduced and frac <= b_entry_frac:
            acc["_dd_reduced"] = True
            acc["_dd_oscillations"] += 1
        elif was_reduced and frac >= b_entry_frac + HYSTERESIS:
            acc["_dd_reduced"] = False
        mult = b_reduction if acc["_dd_reduced"] else 1.0
        if mult < 1.0:
            state["dd_reduced_obs"] += 1
        return base_r * mult

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
    reserve_min_6mo = float("inf")

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]
        state["_now"] = now

        if now <= SIX_MONTHS_SECONDS:
            reserve_min_6mo = min(reserve_min_6mo, state["reserve"])

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
            base_risk = gft_eval_risk if gname == "GFT" else eval_risk
            use_payout_cycle = payout_cycle and gname in PAYOUT_CYCLE_FIRMS
            for acc in list(accs):
                if not acc["active"]:
                    continue
                fmt = FORMATS[acc["_fmt_key"]]
                base_r = fleet_risk if acc["phase"] == "funded" else base_risk
                pdef = _current_phase(fmt, acc)
                r = effective_risk(acc, pdef, base_r)
                if size_func is not None:
                    r = r * size_func(trade["rr_tp2"])
                was_challenge = acc["active"] and acc["phase"] == "challenge"
                was_funded = acc["active"] and acc["phase"] == "funded"
                phase_before, idx_before = acc["phase"], acc["phase_index"]
                split_this = GOAT_GUARD_SPLIT_FLAT if (gft_goat_guard and gname == "GFT"
                                                        and acc["_gg_split_until"] is not None
                                                        and now < acc["_gg_split_until"]) else 0.80

                funded_pnl_before = acc["total_funded_pnl"] if was_funded else None
                if use_any_rr:
                    just_funded = process_trade_corr_swap_rr(acc, trade, now, fmt, state, r, market_data,
                                                              excluded_map, split_flat=split_this,
                                                              reserve_share=reserve_share, cost_override=0.0,
                                                              routing_field=routing_field)
                else:
                    just_funded = process_trade_mf(acc, trade, now, fmt, state, r, market_data, excluded_map,
                                                    split_flat=split_this, reserve_share=reserve_share,
                                                    cost_override=0.0)

                if use_payout_cycle and was_funded:
                    delta = acc["total_funded_pnl"] - funded_pnl_before
                    if delta > 0:
                        acc["total_funded_pnl"] -= delta
                        state["reserve"] -= delta * reserve_share
                        acc["pending_payout"] += delta

                if just_funded and acc["last_open_time"] is not None:
                    state["funding_delays"].append((now - acc["last_open_time"]) / 86400.0)

                if use_payout_cycle and acc["active"] and acc["last_payout_time"] is not None \
                        and now - acc["last_payout_time"] >= (bb_payout_days(acc["_fmt_key"], ceiling, acc["_first_payout_done"])
                                                                if gname == "Blueberry" else
                                                                payout_cycle_days(gname, acc["_first_payout_done"])) * 86400:
                    acc["total_funded_pnl"] += acc["pending_payout"]
                    if acc["pending_payout"] > 0:
                        state["reserve"] += acc["pending_payout"] * reserve_share
                    acc["pending_payout"] = 0.0
                    acc["last_payout_time"] = now
                    acc["_first_payout_done"] = True

                progressed = (fmt["phases"] and (
                    (acc["phase"] == "challenge" and acc["phase_index"] == idx_before + 1) or
                    (acc["phase"] == "funded" and phase_before == "challenge")))
                reset_happened = (acc["cumulative_since_reset"] == 0.0 and acc["peak_since_reset"] == 0.0
                                  and len(acc["trading_days_since_reset"]) == 0)
                broke = reset_happened and not progressed

                use_goat_guard = (broke and gft_goat_guard and gname == "GFT" and was_funded
                                  and acc["_gg_triggered_count"] < 1)
                if use_goat_guard:
                    acc["_gg_triggered_count"] += 1
                    acc["_gg_split_until"] = now + GOAT_GUARD_SPLIT_DAYS * 86400
                    acc["phase"] = "funded"
                    state["gft_soft_breaches"] += 1
                elif broke:
                    state["total_breaks"] += 1
                    if use_payout_cycle and acc["pending_payout"] != 0.0:
                        forfeited = max(0.0, acc["pending_payout"])
                        bucket = state["forfeited_post"] if fleet_unlocked else state["forfeited_pre"]
                        events = state["forfeit_events_post"] if fleet_unlocked else state["forfeit_events_pre"]
                        if forfeited > 0:
                            bucket[gname] += forfeited
                            events[gname] += 1
                        acc["pending_payout"] = 0.0
                    t_since_open = now - acc["last_open_time"] if acc["last_open_time"] is not None else None
                    if t_since_open is not None:
                        if t_since_open <= 30 * 86400:
                            state["breaks_within_30d"] += 1
                        if t_since_open <= 60 * 86400:
                            state["breaks_within_60d"] += 1
                    use_bb_reset = (gname == "Blueberry" and was_funded and not acc["_reset_used"]
                                     and acc["_fmt_key"] == BB_CLASSIC_KEY)
                    if use_bb_reset:
                        cost = 2.0 * acc["base_cost"]
                        acc["active"] = False
                        acc["_reset_used"] = True
                        state["blueberry_resets_used"] += 1
                        handle_cost_hybrid(cost, pending_reopen, id(acc),
                                            lambda a=acc, c=cost, f=fmt: reopen_account(a, c, f, skip_to_funded=True))
                    else:
                        if gname == "Blueberry":
                            new_fmt_key = bb_choose_fmt_key()
                            acc["_fmt_key"] = new_fmt_key
                            new_fmt = FORMATS[new_fmt_key]
                            palier_for_cost = acc["base_palier"] if downgrade_active() else acc["palier"]
                            cost = price_for_bb(new_fmt_key, palier_for_cost, ceiling)
                            if new_fmt_key == BB_INSTANT_KEY:
                                state["bb_instant_opens"] += 1
                            else:
                                state["bb_classic_opens"] += 1
                        elif downgrade_active() and gname == ei.STARTER:
                            new_fmt = fmt
                            cost = acc["base_cost"]
                        else:
                            new_fmt = fmt
                            cost = ei.price_for(format_by_firm[gname], acc["palier"])
                            if ftmo_discount and gname == "FTMO":
                                cost *= FTMO_DISCOUNT_FACTOR
                        acc["active"] = False
                        handle_cost_hybrid(cost, pending_reopen, id(acc),
                                            lambda a=acc, c=cost, f=new_fmt: reopen_account(a, c, f, skip_to_funded=False))
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
              "total_opens": state["total_opens"], "breaks_within_30d": state["breaks_within_30d"],
              "breaks_within_60d": state["breaks_within_60d"], "blueberry_resets_used": state["blueberry_resets_used"],
              "reserve_min_6mo": reserve_min_6mo if reserve_min_6mo != float("inf") else 0.0,
              "final_reserve": state["reserve"], "hit_ceiling": state["hit_ceiling"],
              "bb_instant_opens": state["bb_instant_opens"], "bb_classic_opens": state["bb_classic_opens"],
              "corr_swap_evictions": state["corr_swap_evictions"], "corr_swap_admits": state["corr_swap_admits"]}
    for g in PAYOUT_CYCLE_FIRMS:
        result[f"forfeited_pre_{g}"] = state["forfeited_pre"][g]
        result[f"forfeited_post_{g}"] = state["forfeited_post"][g]
        result[f"forfeit_events_pre_{g}"] = state["forfeit_events_pre"][g]
        result[f"forfeit_events_post_{g}"] = state["forfeit_events_post"][g]
    return result


def run_propagated(pop, market_data, excluded_map, ceiling, seq_grouped, format_by_firm, emergency,
                    eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult, n_sims, seed,
                    b_entry_frac=None, b_reduction=None, pre_unlock_only=False,
                    ftmo_discount=False, gft_goat_guard=False, payout_cycle=False,
                    bb_threshold=float("inf"), use_any_rr=False, size_func=None, routing_field="rr_tp1"):
    rng_wr = random.Random(seed)
    rng_boot = random.Random(seed + 1)
    rows = []
    for _ in range(n_sims):
        wr_draw = rng_wr.betavariate(ei.ALPHA_POST, ei.BETA_POST)
        trades, slot_arrivals = build_flexible_population_with_rr(pop, wr_draw, 1.0, False, random.Random(rng_boot.random()))
        block_seconds = 2 * 30 * DAY_SECONDS
        blocks = build_blocks(trades, slot_arrivals, block_seconds)
        target_duration = slot_arrivals[-1]
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot, target_duration)
        order = list(range(len(raw_trades)))
        res = run_one(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, seq_grouped, format_by_firm,
                      emergency, eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult,
                      b_entry_frac=b_entry_frac, b_reduction=b_reduction, pre_unlock_only=pre_unlock_only,
                      ftmo_discount=ftmo_discount, gft_goat_guard=gft_goat_guard, payout_cycle=payout_cycle,
                      bb_threshold=bb_threshold, use_any_rr=use_any_rr, size_func=size_func, routing_field=routing_field)
        rows.append(res)
    return pd.DataFrame(rows)


def summarize(df, label, ceiling):
    net = df["final_net_split"] - df["is_paid_cum"]
    year1_neg = df["year1_net_split"] < 0
    solde_neg_mask = net < 0
    hc_mask = df["hit_ceiling"]
    return dict(config=label, ceiling=ceiling, n=len(df),
                profit_moyen=net.mean(), profit_median=net.median(),
                solde_negatif_annee4=solde_neg_mask.mean() * 100,
                hit_ceiling_pct=hc_mask.mean() * 100,
                annee1_neg=year1_neg.mean() * 100)


def load_common(min_rr=MIN_RR_NEW, corr_th=CORR_TH_NEW):
    pop = build_population_with_trailing("fixed", 0.15, min_rr=min_rr, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, corr_th)
    return pop, market_data, excluded_map


if __name__ == "__main__":
    # <<< SECTION B (2026-08-17) : grille plafond de positions x risque par
    # trade, a risque total simultane pire-cas CONSTANT (~3,75-3,76%,
    # REF=3x1,25% jusqu'a 6x0,625%). eng.MAX_POSITIONS monkeypatche par
    # variante (meme convention que chantier_gft_instant_exploration_2026-
    # 08-15.py). eval_risk/fleet_risk/gft_eval_risk RE-ECHELONNES par le
    # MEME ratio que la variante (ex. 4 positions -> ratio 0,94/1,25=0,752,
    # applique aux 3 taux) pour preserver le meme risque agrege pire-cas a
    # TOUTE phase (eval ET funded), pas seulement en eval.
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    ceilings_arg = [float(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [960.0, 1000.0, 3000.0, 5000.0]

    t_start = time.time()
    pop, market_data, excluded_map = load_common()
    print(f"[verif] population construite (RR>={MIN_RR_NEW}) : {len(pop)} trades")
    seq = ei.seq_grouped_multi(1000, 15000, 25000, 25000)
    config = ei.CONFIG_REF

    ref_size_func = make_size_func_tail(1.6, threshold=8.0)

    VARIANTS = {
        "REF_3pos_1.25pct": (3, 1.0),
        "V1_4pos_0.94pct": (4, 0.94 / 1.25),
        "V2_5pos_0.75pct": (5, 0.75 / 1.25),
        "V3_6pos_0.625pct": (6, 0.625 / 1.25),
    }
    print("[verif marge] risque agrege pire-cas (N positions x risque_eval) vs DD journalier 4,0% :")
    for name, (n_pos, ratio) in VARIANTS.items():
        eval_r = EVAL_RISK * ratio
        worst = n_pos * eval_r
        marge = (4.0 - worst) / 4.0 * 100
        print(f"  {name} : {n_pos}x{eval_r:.3f}% = {worst:.2f}% pire-cas -> marge={marge:.1f}% vs DD 4,0% "
              f"(reference: REF a deja seulement ~6%% de marge sur ce calcul agrege N-way -- "
              f"pas le meme type de contrainte que le sizing par-trade S2.35 [>=30%], "
              f"la question ici est de savoir si les variantes AGGRAVENT ce pire-cas deja existant : NON, il reste ~constant)")

    common_kwargs = dict(emergency=ei.DEFAULT_EMERGENCY, reserve_share=ei.FINAL_RESERVE_SHARE,
                          extra_threshold_mult=ei.EXTRA_THRESHOLD_MULT, n_sims=n_sims, seed=9999,
                          b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True,
                          ftmo_discount=True, gft_goat_guard=True, payout_cycle=True,
                          use_any_rr=True, routing_field="rr_tp2", size_func=ref_size_func)

    BB_THRESHOLD_BY_CEILING = {960.0: 5000.0, 1000.0: 5000.0, 3000.0: 0.0, 5000.0: 0.0}

    rows = []
    for ceiling in ceilings_arg:
        bb_th = BB_THRESHOLD_BY_CEILING[ceiling]
        for name, (n_pos, ratio) in VARIANTS.items():
            t0 = time.time()
            orig_max_pos = eng.MAX_POSITIONS
            eng.MAX_POSITIONS = n_pos
            try:
                df = run_propagated(pop, market_data, excluded_map, ceiling, seq, config,
                                     bb_threshold=bb_th, eval_risk=EVAL_RISK * ratio,
                                     fleet_risk=FLEET_RISK * ratio, gft_eval_risk=GFT_EVAL_RISK * ratio,
                                     **common_kwargs)
            finally:
                eng.MAX_POSITIONS = orig_max_pos
            row = summarize(df, name, ceiling)
            rows.append(row)
            print(f"[{name} plafond={ceiling:.0f}$] profit_moy={row['profit_moyen']:+,.0f}$ "
                  f"solde_neg={row['solde_negatif_annee4']:.2f}% hit_ceiling={row['hit_ceiling_pct']:.2f}% "
                  f"annee1<0={row['annee1_neg']:.2f}% ({time.time()-t0:.0f}s)")
            pd.DataFrame(rows).to_csv(f"chantier_sectionB_poscap_risk_n{n_sims}_2026-08-17.csv", index=False)

    print(f"\nTermine en {time.time()-t_start:.0f}s.")
