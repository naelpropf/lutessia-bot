"""
Cascade RR1.35+corr0.80, Section 3 (08/12) : RAFRAICHIT les valeurs absolues
des options B et C du chantier cluster Blueberry (ci-dessous, docstring
original conserve) sous la nouvelle base RR>=1,35 + correlation 0,80
(registre_parametres_projet.md §2.62), MAINTENANT ADOPTEE comme reference
officielle du projet. Copie exacte de blueberry_cluster_options_2026-08-12
.py, SEULS 2 parametres changes : min_rr 1.25->1.35, seuil de correlation
CORR_TH(0.6)->0.80. Option A n'est PAS re-executee ici non plus (toujours
mecaniquement identique a Run C/Run F, desormais etape_aq_run_c_rr135_
corr080_2026-08-12.py / etape_ar_run_f_rr135_corr080_2026-08-12.py).
Objectif explicite : verifier que le verdict qualitatif (A domine B et C)
tient toujours sous la nouvelle base, pas seulement rafraichir les chiffres.

--- Docstring original conserve ci-dessous pour tracabilite ---

Chantier cluster Blueberry 1,5% (session 08/12, reprise apres interruption
08/12) : le compte Blueberry reellement souscrit en live est confirme par
l'utilisateur comme etant le "2-Step Challenge" standard (10%/5%, DD 5%/10%),
PAS Prime -- et la regle de budget de risque cluster FX Majors (toutes les
positions FX Majors simultanees sur un meme compte partagent un seul budget
de risque de 1,5%, jamais 1,5% par position) s'applique specifiquement a ce
format Standard, PAS a Prime.

Consequence importante decouverte en reprenant ce chantier : CONFIG_REF
(etape_e_fleet_integration.py:123-125), utilise par TOUTE la reference
officielle du projet (§1.8 du registre, Run C/Run F), utilisait jusqu'ici
Blueberry_Prime2Step -- donc toute la reference officielle actuelle simule
en realite le MAUVAIS produit Blueberry (Prime, moins cher, JAMAIS soumis au
cluster) au lieu du produit reellement trade (Standard, plus cher, soumis au
cluster). Ce script compare 3 options pour resoudre cet ecart :

- Option A (bascule reelle vers Prime) : mecaniquement IDENTIQUE a CONFIG_REF
  actuel (Blueberry_Prime2Step deja code, prix 165$@25k deja confirme par
  recherche web 08/12 -- source propfirmmatch.com, prix regulier 165$/promo
  99$, matche exactement la note de confiance deja presente dans le code).
  PAS RE-EXECUTE ICI : les chiffres Run C deja produits n=600+cascade
  (§1.8 du registre) sont directement reutilisables tels quels, seed et
  config strictement identiques.
- Option B (rester en Standard, modeliser le vrai cluster) : nouveau, ce
  script. Blueberry_2StepStandard (prix 25k=170$, corrige 08/12, source
  tradingpilot.com) + limiteur de risque cluster FX Majors (budget partage
  1,5%, implemente ci-dessous en parallele de process_trade_mf sans modifier
  le moteur partage).
- Option C (retirer Blueberry, GFT reprend le role de starter jour 0) :
  nouveau, ce script. GFT est le moins cher des starters alternatifs
  (50k=288$ vs FTMO 345$ vs Fivers 545$ vs FundedNext ~799$, deja etabli
  decision #19 du registre) -- flotte reduite a 4 firms.

Toutes les options tournent sous les MEMES parametres que Run C (V2 DD-
distance sizing, FTMO -10%, GFT Goat Guard, payout cycle actif, population
721, seed=9999) -- PAS Run F (Blueberry 7j) pour rester isole de ce levier
deja tranche separement et eviter de confondre les deux chantiers. Precision
explicite : ceci compare la reference "Run C" aux deux plafonds, PAS Run F a
3000$ (l'asymetrie officielle par plafond ne s'applique pas a ce chantier).

N'importe pas ce script directement (convention du projet).
"""
import random
import sys
import time

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

HYSTERESIS = 0.10
FTMO_DISCOUNT_FACTOR = 0.90
GOAT_GUARD_SPLIT_DAYS = 30
GOAT_GUARD_SPLIT_FLAT = 0.50
PAYOUT_CYCLE_FIRMS = ("Blueberry", "GFT", "Fivers")
PAYOUT_CYCLE_DAYS_FIRST = {"Blueberry": 14, "GFT": 3, "Fivers": 14}
PAYOUT_CYCLE_DAYS_SUBSEQUENT = {"Blueberry": 14, "GFT": 1.5, "Fivers": 14}

# 7 paires FX Majors standard (toutes contiennent USD sauf... non, convention
# habituelle : les 7 paires majeures usuelles vs USD). Cluster Blueberry
# 1,5% = budget de risque total PARTAGE entre positions FX Majors simultanees
# ouvertes sur le MEME compte (confirme par l'utilisateur 08/12) -- ne
# concerne que Blueberry_2StepStandard (PAS Prime, confirme separement).
FX_MAJORS = {"EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "USD/CAD", "AUD/USD", "NZD/USD"}
CLUSTER_BUDGET_PCT = 1.5


def cluster_adjusted_risk(acc, trade, now, base_r):
    """Reduit (sans jamais annuler) le risque cible d'une position FX Major
    sur un compte Blueberry Standard, pour respecter le budget de risque
    cluster PARTAGE de 1,5% entre toutes les positions FX Majors simultanees
    deja ouvertes sur ce compte. Tracking PARALLELE a acc["open_positions"]
    (pas de modification du moteur partage process_trade_mf) : une liste
    dediee acc["_fx_major_open"] de (close_time, risque_pct_alloue), purgee
    des positions deja fermees a chaque appel, meme logique de peremption que
    process_trade_mf:317."""
    if trade["ticker"] not in FX_MAJORS:
        return base_r
    lst = acc.setdefault("_fx_major_open", [])
    lst[:] = [(c, r) for (c, r) in lst if c > now]
    committed = sum(r for (_, r) in lst)
    remaining = max(0.0, CLUSTER_BUDGET_PCT - committed)
    r = min(base_r, remaining)
    close_time = now + trade["hold_seconds"]
    lst.append((close_time, r))
    return r


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


def run_one(trades, slot_arrivals, market_data, excluded_map, order, ceiling, seq_grouped, format_by_firm,
            emergency_capital, eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult,
            firms, starter, growth_firms_extra,
            b_entry_frac=None, b_reduction=None, pre_unlock_only=False,
            ftmo_discount=False, gft_goat_guard=False, payout_cycle=False, cluster_mode=False):
    fmt_by_firm = {g: FORMATS[k] for g, k in format_by_firm.items()}

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
    n_accounts_day0 = dict(ei.N_ACCOUNTS_DAY0)
    for gname in firms:
        is_day0 = (gname == starter)
        n0 = n_accounts_day0.get(gname, 1) if is_day0 else n_accounts_day0.get(gname, 1)
        palier, cost = base_palier_cost(gname)
        fmt = fmt_by_firm[gname]
        accs = [make_acc_mf(fmt, palier, cost=cost, active=is_day0) for _ in range(n0)]
        for a in accs:
            a["_gname"] = gname
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
    _init_own_funded = {g for g in ("Blueberry",) if g in firms and not fmt_by_firm[g]["phases"]}
    state = {"reserve": 0.0, "ever_funded": False, "real_cash_paid": active0_cost, "total_breaks": 0,
             "group_funded_count": len(_init_own_funded), "group_own_funded": set(_init_own_funded),
             "hit_ceiling": False, "emergency_remaining": emergency_capital, "is_paid_cum": 0.0,
             "extra_accounts_opened": {g: 0 for g in growth_firms_extra},
             "tax_breach_count": 0, "tax_breach_total": 0.0, "tax_breach_max": 0.0,
             "tax_breach_concurrent_with_repurchase": 0, "tax_breach_events": [], "_now": 0.0,
             "total_opens": sum(1 for accs in accounts_by_group.values() for a in accs if a["last_open_time"] == 0.0),
             "breaks_within_30d": 0, "breaks_within_60d": 0, "blueberry_resets_used": 0,
             "dd_reduced_obs": 0, "dd_total_obs": 0, "funding_delays": [], "gft_soft_breaches": 0,
             "forfeited_pre": {g: 0.0 for g in PAYOUT_CYCLE_FIRMS if g in firms},
             "forfeited_post": {g: 0.0 for g in PAYOUT_CYCLE_FIRMS if g in firms},
             "forfeit_events_pre": {g: 0 for g in PAYOUT_CYCLE_FIRMS if g in firms},
             "forfeit_events_post": {g: 0 for g in PAYOUT_CYCLE_FIRMS if g in firms}}
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
        acc["_fx_major_open"] = []
        state["total_opens"] += 1
        if downgrade_active() and acc.get("_gname") == starter:
            acc["palier"] = acc["base_palier"]
            acc["cost"] = acc["base_cost"]

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
            a["_fx_major_open"] = []
            state["total_opens"] += 1
        if not fmt_by_firm[gname]["phases"]:
            mark_group_funded_if_needed(gname)

    def try_emergency_bootstrap():
        if n_active_accounts() != 0 or emergency_capital <= 0 or state["emergency_remaining"] <= 0:
            return
        s_acc = accounts_by_group[starter][0]
        cost = s_acc["base_cost"] if downgrade_active() else s_acc["cost"]
        if state["emergency_remaining"] >= cost:
            state["emergency_remaining"] -= cost
            reopen_account(s_acc, cost, fmt_by_firm[starter])
            pending_reopen[:] = [p for p in pending_reopen if p["key"] != id(s_acc)]

    def process_extra_account(now):
        if not fleet_unlocked:
            return
        for gname in growth_firms_extra:
            accs = accounts_by_group[gname]
            max_acc = ei.FIRM_MAX_ACCOUNTS.get(gname)
            if max_acc is not None and len(accs) >= max_acc:
                continue
            unit_palier = BASE_PALIER[gname] * ei.EXTRA_ACCOUNT_MULT
            current_capital = sum(a["palier"] for a in accs)
            if current_capital + unit_palier > ei.FIRM_CAPITAL_CAP[gname]:
                continue
            extra_cost = ei.price_for(format_by_firm[gname], unit_palier)
            if state["reserve"] >= extra_threshold_mult * extra_cost:
                state["reserve"] -= extra_cost
                new_acc = make_acc_mf(fmt_by_firm[gname], unit_palier, cost=extra_cost, active=True)
                new_acc["total_fees_paid"] = extra_cost
                new_acc["_gname"] = gname
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
                new_acc["_fx_major_open"] = []
                accs.append(new_acc)
                state["extra_accounts_opened"][gname] += 1
                state["total_opens"] += 1

    def structure_complete():
        for g in firms:
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
            fmt = fmt_by_firm[gname]
            base_risk = gft_eval_risk if gname == "GFT" else eval_risk
            use_payout_cycle = payout_cycle and gname in PAYOUT_CYCLE_FIRMS
            use_cluster = cluster_mode and gname == "Blueberry" and format_by_firm.get("Blueberry") == "Blueberry_2StepStandard"
            for acc in list(accs):
                if not acc["active"]:
                    continue
                base_r = fleet_risk if acc["phase"] == "funded" else base_risk
                pdef = _current_phase(fmt, acc)
                r = effective_risk(acc, pdef, base_r)
                if use_cluster:
                    r = cluster_adjusted_risk(acc, trade, now, r)
                was_challenge = acc["active"] and acc["phase"] == "challenge"
                was_funded = acc["active"] and acc["phase"] == "funded"
                phase_before, idx_before = acc["phase"], acc["phase_index"]
                split_this = GOAT_GUARD_SPLIT_FLAT if (gft_goat_guard and gname == "GFT"
                                                        and acc["_gg_split_until"] is not None
                                                        and now < acc["_gg_split_until"]) else 0.80

                funded_pnl_before = acc["total_funded_pnl"] if was_funded else None
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
                        and now - acc["last_payout_time"] >= payout_cycle_days(gname, acc["_first_payout_done"]) * 86400:
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
                    use_bb_reset = (gname == "Blueberry" and was_funded and not acc["_reset_used"])
                    if use_bb_reset:
                        cost = 2.0 * acc["base_cost"]
                        acc["active"] = False
                        acc["_reset_used"] = True
                        state["blueberry_resets_used"] += 1
                        handle_cost_hybrid(cost, pending_reopen, id(acc),
                                            lambda a=acc, c=cost, f=fmt: reopen_account(a, c, f, skip_to_funded=True))
                    else:
                        if downgrade_active() and gname == starter:
                            cost = acc["base_cost"]
                        else:
                            cost = ei.price_for(format_by_firm[gname], acc["palier"])
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
              "total_opens": state["total_opens"], "breaks_within_30d": state["breaks_within_30d"],
              "breaks_within_60d": state["breaks_within_60d"], "blueberry_resets_used": state["blueberry_resets_used"],
              "reserve_min_6mo": reserve_min_6mo if reserve_min_6mo != float("inf") else 0.0,
              "final_reserve": state["reserve"], "hit_ceiling": state["hit_ceiling"]}
    return result


def payout_cycle_days(gname, first_payout_done):
    table = PAYOUT_CYCLE_DAYS_SUBSEQUENT if first_payout_done else PAYOUT_CYCLE_DAYS_FIRST
    return table[gname]


def run_propagated(pop, market_data, excluded_map, ceiling, seq_grouped, format_by_firm, emergency,
                    eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult, n_sims, seed,
                    firms, starter, growth_firms_extra,
                    b_entry_frac=None, b_reduction=None, pre_unlock_only=False,
                    ftmo_discount=False, gft_goat_guard=False, payout_cycle=False, cluster_mode=False):
    rng_wr = random.Random(seed)
    rng_boot = random.Random(seed + 1)
    rows = []
    for _ in range(n_sims):
        wr_draw = rng_wr.betavariate(ei.ALPHA_POST, ei.BETA_POST)
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_draw, 1.0, False, random.Random(rng_boot.random()))
        block_seconds = 2 * 30 * DAY_SECONDS
        blocks = build_blocks(trades, slot_arrivals, block_seconds)
        target_duration = slot_arrivals[-1]
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot, target_duration)
        order = list(range(len(raw_trades)))
        res = run_one(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, seq_grouped, format_by_firm,
                      emergency, eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult,
                      firms, starter, growth_firms_extra,
                      b_entry_frac=b_entry_frac, b_reduction=b_reduction, pre_unlock_only=pre_unlock_only,
                      ftmo_discount=ftmo_discount, gft_goat_guard=gft_goat_guard, payout_cycle=payout_cycle,
                      cluster_mode=cluster_mode)
        rows.append(res)
    return pd.DataFrame(rows)


def summarize(df, label, ceiling):
    net = df["final_net_split"] - df["is_paid_cum"]
    year1_neg = df["year1_net_split"] < 0
    pre_mask = df["pre_deblocage"]
    n_pre = (year1_neg & pre_mask).sum()
    n_post = (year1_neg & ~pre_mask).sum()
    solde_neg_mask = net < 0
    hc_mask = df["hit_ceiling"]
    row = dict(config=label, ceiling=ceiling, n=len(df),
               profit_moyen=net.mean(), profit_median=net.median(),
               solde_negatif_annee4=solde_neg_mask.mean() * 100,
               hit_ceiling_pct=hc_mask.mean() * 100,
               annee1_neg=year1_neg.mean() * 100, annee1_neg_pre=n_pre / len(df) * 100,
               annee1_neg_post=n_post / len(df) * 100)
    return row


FIRMS_FULL = ("Blueberry", "FTMO", "Fivers", "GFT", "FundedNext")
FIRMS_NO_BB = ("FTMO", "Fivers", "GFT", "FundedNext")

CONFIG_B = dict(FTMO="FTMO_2Step_Swing", Fivers="Fivers_HighStakes",
                Blueberry="Blueberry_2StepStandard", GFT="GFT_2Step_GOAT",
                FundedNext="FundedNext_StellarLite")
CONFIG_C = dict(FTMO="FTMO_2Step_Swing", Fivers="Fivers_HighStakes",
                 GFT="GFT_2Step_GOAT", FundedNext="FundedNext_StellarLite")

if __name__ == "__main__":
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    ceilings_arg = [float(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [1000.0, 3000.0]

    t_start = time.time()
    import rr_threshold_test as rrt
    print(f"[verif] HIST_PATH (rr_threshold_test) = {rrt.HIST_PATH}")

    MIN_RR_NEW = 1.35
    CORR_TH_NEW = 0.80
    pop = build_population_with_trailing("fixed", 0.15, min_rr=MIN_RR_NEW, verbose=False)
    print(f"[verif] population construite (RR>={MIN_RR_NEW}) : {len(pop)} trades (attendu 631)")
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH_NEW)
    EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK = 1.25, 1.90, 1.75

    seq_B = ei.seq_grouped_multi(1000, 15000, 25000, 25000)
    seq_C = [
        (("GFT",), "day0", None, False),
        (("FTMO",), ("after_count", 1), 1000, False),
        (("Fivers",), ("after_count", 1), 15000, False),
        (("FundedNext",), ("after_count", 1), 25000, True),
    ]

    scenarios = [
        dict(name="OptionB_Standard_cluster", firms=FIRMS_FULL, starter="Blueberry",
             growth_extra=("Blueberry", "FTMO", "GFT"), seq=seq_B, config=CONFIG_B, cluster_mode=True),
        dict(name="OptionC_dropBB_GFTstarter", firms=FIRMS_NO_BB, starter="GFT",
             growth_extra=("FTMO", "GFT"), seq=seq_C, config=CONFIG_C, cluster_mode=False),
    ]

    rows = []
    for sc in scenarios:
        for ceiling in ceilings_arg:
            t0 = time.time()
            df = run_propagated(pop, market_data, excluded_map, ceiling, sc["seq"], sc["config"],
                                 ei.DEFAULT_EMERGENCY, EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK,
                                 ei.FINAL_RESERVE_SHARE, ei.EXTRA_THRESHOLD_MULT, n_sims=n_sims, seed=9999,
                                 firms=sc["firms"], starter=sc["starter"], growth_firms_extra=sc["growth_extra"],
                                 b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True,
                                 ftmo_discount=True, gft_goat_guard=True, payout_cycle=True,
                                 cluster_mode=sc["cluster_mode"])
            row = summarize(df, sc["name"], ceiling)
            rows.append(row)
            print(f"[{sc['name']} plafond={ceiling:.0f}$] profit_moyen={row['profit_moyen']:+,.0f}$ "
                  f"profit_median={row['profit_median']:+,.0f}$ "
                  f"solde_negatif_annee4={row['solde_negatif_annee4']:.2f}% "
                  f"hit_ceiling_pct={row['hit_ceiling_pct']:.2f}% "
                  f"annee1<0={row['annee1_neg']:.2f}% ({time.time()-t0:.0f}s)")
            pd.DataFrame(rows).to_csv(f"blueberry_cluster_options_rr135_corr080_n{n_sims}.csv", index=False)

    print(f"\nTermine en {time.time()-t_start:.0f}s.")
