"""
Chantier "remise en question structurelle" (08/11, prompt utilisateur) : teste
si des changements de STRUCTURE (pas de reglage fin) peuvent casser le
mecanisme de correlation copytrade identifie comme cause racine du rejet de
Piste A/BB+GFT a 1000$ (Piste 5, registre_parametres_projet.md §2.43 : 13,0%
vs 32,7% d'annee1<0 si on decorrele artificiellement). Base = etape_ao_run_f_
cout_reel_2026-08-11.py (config officielle par plafond, decision #16 §1.8/
§2.35bis), n=300, TOUTES les configs sont du SCREENING -- aucune adoption
sans confirmation n=600+cascade.

- Section A : repartition des 14 paires forex en 2 groupes (FTMO+Blueberry
  vs GFT+Fivers), FundedNext garde acces complet. Groupes construits par un
  algorithme glouton equilibre en frequence historique (721 trades), en
  essayant d'eviter de regrouper 2 membres du meme cluster de correlation
  (cf. correlation_matrix.csv) dans le meme groupe -- meilleur effort, pas
  une optimisation exhaustive, documente comme tel.
- Section B : parite temporelle -- FTMO+GFT ne prennent que les signaux de
  rang impair (1er, 3e...) dans le flux simule REELLEMENT EXECUTE (indice de
  slot dans la sequence bootstrap, PAS le rang dans l'historique brut non
  reechantillonne -- deviation documentee, le bootstrap melange deja l'ordre
  brut donc la parite du flux simule est la notion operationnellement
  pertinente), Blueberry+Fivers+FundedNext prennent les rangs pairs.
- Section C : compte contrarian dedie, trade EXCLUSIVEMENT la bande
  0,75<=rr_tp1<1,25 (jamais tradee par le reste de la flotte). Flux
  independant, fusionne par le temps avec le flux principal (2 populations
  bootstrappees separement, evenements merges et tries chronologiquement).
- Section D : balayage du plafond personnel {1000,2000,3000,5000,7500,10000},
  config reference SANS changement structurel (Run C sous 3000$, Run F a
  3000$ et au-dela -- generalise le seuil exact {3000.0} en seuil >=3000).

N'importe pas ce script directement (convention du projet).
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

# Decision #16 (08/11, §1.8/§2.35bis) : generalise en SEUIL (>=3000$) au lieu
# du set exact {3000.0} -- necessaire pour le balayage Section D qui teste
# des plafonds intermediaires (2000$, 5000$, 7500$, 10000$) jamais couverts
# par la decision originale (tranchee seulement pour 1000$/3000$). Choix
# explicite : au-dela de 3000$, la logique "hit_ceiling neutre a ce palier"
# qui justifiait Run F a 3000$ est encore plus vraie (plus de marge), donc
# le seuil >=3000$ est une extrapolation raisonnable, pas une nouvelle
# decision -- a noter si jamais un plafond intermediaire est adopte formellement.
BB_7J_CEILING_THRESHOLD = 3000.0
PAYOUT_CYCLE_DAYS_FIRST = {"Blueberry": 14, "GFT": 3, "Fivers": 14}
PAYOUT_CYCLE_DAYS_SUBSEQUENT = {"Blueberry": 14, "GFT": 1.5, "Fivers": 14}
BB_PAYOUT_ADDON_MULT = 1.20


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


# --- Section A : groupes de paires (frequence 721 trades, cf. docstring pour
# la methode de construction -- glouton equilibre + separation best-effort
# des clusters de correlation) ---
PAIR_GROUP_1 = {"NZD/USD", "GBP/JPY", "USD/CAD", "USD/JPY", "USD/CHF", "EUR/JPY", "GBP/CHF"}  # FTMO+Blueberry, n=358/721
PAIR_GROUP_2 = {"AUD/JPY", "AUD/USD", "EUR/GBP", "CHF/JPY", "EUR/USD", "GBP/USD", "EUR/CHF"}  # GFT+Fivers, n=363/721
ALLOWED_TICKERS_A = {"FTMO": PAIR_GROUP_1, "Blueberry": PAIR_GROUP_1,
                      "GFT": PAIR_GROUP_2, "Fivers": PAIR_GROUP_2,
                      "FundedNext": None}  # None = acces complet (14 paires)

# --- Section B : parite temporelle (indice de slot dans le flux simule) ---
PARITY_B = {"FTMO": "odd", "GFT": "odd",
            "Blueberry": "even", "Fivers": "even", "FundedNext": "even"}


def ticker_allowed(gname, ticker, section):
    if section != "A":
        return True
    allowed = ALLOWED_TICKERS_A.get(gname)
    return allowed is None or ticker in allowed


def parity_allowed(gname, slot_idx, section):
    if section != "B":
        return True
    parity = PARITY_B.get(gname)
    if parity is None:
        return True
    # rang 1-based = slot_idx+1 ; rang impair <=> slot_idx pair (0-based)
    is_odd_rank = (slot_idx % 2 == 0)
    return is_odd_rank if parity == "odd" else not is_odd_rank


def run_one(trades, slot_arrivals, market_data, excluded_map, order, ceiling, seq_grouped, format_by_firm,
            emergency_capital, eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult,
            b_entry_frac=None, b_reduction=None, pre_unlock_only=False,
            ftmo_discount=False, gft_goat_guard=False, payout_cycle=False,
            section=None, contrarian_trades=None, contrarian_slots=None):
    fmt_by_firm = {g: FORMATS[k] for g, k in format_by_firm.items()}
    has_contrarian = section == "C" and contrarian_trades is not None

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

    # Section C : compte contrarian, meme format/palier que Blueberry (le plus
    # petit disponible), actif des le jour 0 en parallele du starter normal.
    contrarian_acc = None
    if has_contrarian:
        c_fmt = fmt_by_firm["Blueberry"]
        c_palier = BASE_PALIER["Blueberry"]
        c_cost = price_for_bb("Blueberry", format_by_firm["Blueberry"], c_palier, ceiling)
        contrarian_acc = make_acc_mf(c_fmt, c_palier, cost=c_cost, active=True)
        contrarian_acc.update(_gname="Blueberry_contrarian", base_palier=c_palier, base_cost=c_cost,
                               _reset_used=False, last_open_time=0.0, _dd_reduced=False, _dd_oscillations=0,
                               _gg_triggered_count=0, _gg_split_until=None, pending_payout=0.0,
                               last_payout_time=0.0, _first_payout_done=False)
        active0_cost += c_cost

    fleet_unlocked = False
    _init_own_funded = {g for g in ("Blueberry",) if not fmt_by_firm[g]["phases"]}
    state = {"reserve": 0.0, "ever_funded": False, "real_cash_paid": active0_cost, "total_breaks": 0,
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
             "break_days": []}
    pending_group_trigger = [(names, trig, thresh, final) for names, trig, thresh, final in seq_grouped if trig != "day0"]
    pending_reopen = []
    pending_group_open = []

    def mark_group_funded_if_needed(gname):
        if gname not in state["group_own_funded"]:
            state["group_own_funded"].add(gname)
            state["group_funded_count"] += 1

    def combined_net():
        total = sum(a["total_funded_pnl"] - a["total_fees_paid"] for accs in accounts_by_group.values() for a in accs)
        if contrarian_acc is not None:
            total += contrarian_acc["total_funded_pnl"] - contrarian_acc["total_fees_paid"]
        return total

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
        state["total_opens"] += 1
        if downgrade_active() and acc.get("_gname") == ei.STARTER:
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

    def process_one_account(gname, acc, fmt, trade, now, base_risk_for_group):
        """Corps de traitement d'UN compte pour UN trade -- extrait pour etre
        reutilisable a la fois par la boucle flotte normale ET par le compte
        contrarian (Section C), qui suit exactement la meme mecanique de
        casse/reouverture/payout mais sur son propre flux de trades."""
        if not acc["active"]:
            return
        base_r = fleet_risk if acc["phase"] == "funded" else base_risk_for_group
        pdef = _current_phase(fmt, acc)
        r = effective_risk(acc, pdef, base_r)
        was_challenge = acc["active"] and acc["phase"] == "challenge"
        was_funded = acc["active"] and acc["phase"] == "funded"
        phase_before, idx_before = acc["phase"], acc["phase_index"]
        split_this = GOAT_GUARD_SPLIT_FLAT if (gft_goat_guard and gname == "GFT"
                                                and acc["_gg_split_until"] is not None
                                                and now < acc["_gg_split_until"]) else 0.80

        use_payout_cycle = payout_cycle and gname in PAYOUT_CYCLE_FIRMS
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
            state["break_days"].append(int(now // 86400))
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
            use_bb_reset = (gname in ("Blueberry", "Blueberry_contrarian") and was_funded and not acc["_reset_used"])
            if use_bb_reset:
                cost = 2.0 * acc["base_cost"]
                acc["active"] = False
                acc["_reset_used"] = True
                state["blueberry_resets_used"] += 1
                handle_cost_hybrid(cost, pending_reopen, id(acc),
                                    lambda a=acc, c=cost, f=fmt: reopen_account(a, c, f, skip_to_funded=True))
            else:
                if downgrade_active() and gname == ei.STARTER:
                    cost = acc["base_cost"]
                elif gname == "Blueberry_contrarian":
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

    def advance_shared_state(now):
        if now <= SIX_MONTHS_SECONDS:
            advance_shared_state.reserve_min_6mo = min(advance_shared_state.reserve_min_6mo, state["reserve"])
        while (advance_shared_state.next_fy[0] + 1) * YEAR_SECONDS <= now:
            close_fiscal_year(advance_shared_state.next_fy[0])
            advance_shared_state.next_fy[0] += 1
        i = 0
        while i < len(tax_events):
            t_ev, amt = tax_events[i]
            if t_ev > now:
                i += 1
                continue
            tax_events.pop(i)
            handle_tax_payment(amt, state, ceiling, now, pending_reopen, pending_group_open)
            state["is_paid_cum"] += amt
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
                    advance_shared_state.fleet_unlocked_flag[0] = True
            else:
                still_pending.append((group_names, trig, thresh, is_final))
        pending_group_trigger[:] = still_pending

    advance_shared_state.reserve_min_6mo = float("inf")
    advance_shared_state.next_fy = [0]
    advance_shared_state.fleet_unlocked_flag = [False]

    full_structure_month = None
    year1_net_split = None

    # --- Construction de la liste d'evenements a parcourir ---
    if has_contrarian:
        main_events = [(slot_arrivals[i], "main", i) for i in range(len(order))]
        contra_events = [(contrarian_slots[i], "contrarian", i) for i in range(len(contrarian_trades))]
        events = sorted(main_events + contra_events, key=lambda e: e[0])
    else:
        events = [(slot_arrivals[i], "main", trade_idx) for i, trade_idx in enumerate(order)]

    for now, source, idx in events:
        state["_now"] = now

        if year1_net_split is None and now >= YEAR_SECONDS:
            year1_net_split = combined_net()

        advance_shared_state(now)
        # fleet_unlocked est lu par plusieurs closures (effective_risk,
        # downgrade_active...) par fermeture -- resynchronise depuis le flag
        # partage apres chaque appel a advance_shared_state (seul endroit ou
        # il peut changer, dans le bloc pending_group_trigger/is_final).
        fleet_unlocked = advance_shared_state.fleet_unlocked_flag[0]

        if source == "main":
            trade = trades[idx]
            for gname, accs in list(accounts_by_group.items()):
                fmt = fmt_by_firm[gname]
                base_risk = gft_eval_risk if gname == "GFT" else eval_risk
                for acc in list(accs):
                    if not acc["active"]:
                        continue
                    if not ticker_allowed(gname, trade["ticker"], section):
                        continue
                    if not parity_allowed(gname, idx, section):
                        continue
                    process_one_account(gname, acc, fmt, trade, now, base_risk)
        else:  # contrarian
            trade = contrarian_trades[idx]
            process_one_account("Blueberry_contrarian", contrarian_acc, fmt_by_firm["Blueberry"], trade, now,
                                 eval_risk)

        if full_structure_month is None and structure_complete():
            full_structure_month = now / MONTH_SECONDS

    if year1_net_split is None:
        year1_net_split = combined_net()

    pre = full_structure_month is None or full_structure_month > 12
    n_breaks = len(state["break_days"])
    clustered = 0
    if n_breaks:
        from collections import Counter
        day_counts = Counter(state["break_days"])
        clustered = sum(1 for d in state["break_days"] if day_counts[d] > 1)
    result = {"final_net_split": combined_net(), "is_paid_cum": state["is_paid_cum"],
              "year1_net_split": year1_net_split, "total_breaks": state["total_breaks"], "pre_deblocage": pre,
              "total_opens": state["total_opens"],
              "reserve_min_6mo": advance_shared_state.reserve_min_6mo if advance_shared_state.reserve_min_6mo != float("inf") else 0.0,
              "final_reserve": state["reserve"], "hit_ceiling": state["hit_ceiling"],
              "n_breaks": n_breaks, "n_breaks_clustered": clustered}
    if contrarian_acc is not None:
        result["contrarian_net"] = contrarian_acc["total_funded_pnl"] - contrarian_acc["total_fees_paid"]
    return result


def _common_setup():
    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)
    seq_baseline = ei.seq_grouped_multi(1000, 15000, 25000, 25000)
    config = ei.CONFIG_REF
    return pop, market_data, excluded_map, seq_baseline, config


def _contrarian_population():
    pop = build_population_with_trailing("fixed", 0.15, min_rr=0.75, verbose=False)
    band = pop[(pop["rr_tp1"] >= 0.75) & (pop["rr_tp1"] < 1.25)].copy()
    return band.reset_index(drop=True)


EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK = 1.25, 1.90, 1.75
COMMON_KW = dict(b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True,
                  ftmo_discount=True, gft_goat_guard=True, payout_cycle=True)


def run_sweep(n_sims, ceilings, configs, out_tag, seed=9999, contrarian_pop=None):
    """configs : liste de (label, section). Pour section='C', bootstrappe un
    2e flux (contrarian_pop) independant a chaque iteration."""
    pop, market_data, excluded_map, seq, config = _common_setup()
    rows = []
    for ceiling in ceilings:
        for label, section in configs:
            rng_wr = random.Random(seed)
            rng_boot = random.Random(seed + 1)
            rng_wr_c = random.Random(seed + 2)
            rng_boot_c = random.Random(seed + 3)
            recs = []
            t0 = time.time()
            for run_idx in range(n_sims):
                wr_draw = rng_wr.betavariate(ei.ALPHA_POST, ei.BETA_POST)
                trades, slot_arrivals = eng.build_flexible_population(pop, wr_draw, 1.0, False, random.Random(rng_boot.random()))
                block_seconds = 2 * 30 * DAY_SECONDS
                blocks = build_blocks(trades, slot_arrivals, block_seconds)
                target_duration = slot_arrivals[-1]
                raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot, target_duration)
                order = list(range(len(raw_trades)))

                contrarian_trades = contrarian_slots = None
                if section == "C":
                    wr_draw_c = rng_wr_c.betavariate(ei.ALPHA_POST, ei.BETA_POST)
                    trades_c, slots_c = eng.build_flexible_population(contrarian_pop, wr_draw_c, 1.0, False,
                                                                        random.Random(rng_boot_c.random()))
                    blocks_c = build_blocks(trades_c, slots_c, block_seconds)
                    raw_trades_c, raw_slots_c = build_full_block_bootstrap_sequence(blocks_c, block_seconds, rng_boot_c, target_duration)
                    contrarian_trades, contrarian_slots = raw_trades_c, raw_slots_c

                res = run_one(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, seq, config,
                              ei.DEFAULT_EMERGENCY, EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                              ei.EXTRA_THRESHOLD_MULT, section=section,
                              contrarian_trades=contrarian_trades, contrarian_slots=contrarian_slots, **COMMON_KW)
                recs.append(res)
            df = pd.DataFrame(recs)
            net = df["final_net_split"] - df["is_paid_cum"]
            year1_neg = df["year1_net_split"] < 0
            total_breaks_pool = df["n_breaks"].sum()
            clustered_pool = df["n_breaks_clustered"].sum()
            row = dict(ceiling=ceiling, config=label, n=len(df),
                       profit_moyen=net.mean(), profit_median=net.median(),
                       solde_negatif_annee4=(net < 0).mean() * 100, hit_ceiling_pct=df["hit_ceiling"].mean() * 100,
                       annee1_neg=year1_neg.mean() * 100,
                       clustering_pct=(clustered_pool / total_breaks_pool * 100) if total_breaks_pool else None,
                       n_breaks_total=int(total_breaks_pool))
            if "contrarian_net" in df.columns:
                row["contrarian_net_moyen"] = df["contrarian_net"].mean()
            rows.append(row)
            print(f"[ceiling={ceiling:.0f}$ config={label:12s}] profit_moyen={row['profit_moyen']:+,.0f}$ "
                  f"profit_median={row['profit_median']:+,.0f}$ solde_negatif_annee4={row['solde_negatif_annee4']:.2f}% "
                  f"hit_ceiling={row['hit_ceiling_pct']:.2f}% annee1<0={row['annee1_neg']:.2f}% "
                  f"clustering={row['clustering_pct']:.1f}% (n_breaks={row['n_breaks_total']}) ({time.time()-t0:.0f}s)")
            pd.DataFrame(rows).to_csv(f"structure_{out_tag}_n{n_sims}.csv", index=False)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "AB"
    n_sims = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    t_start = time.time()
    import rr_threshold_test as rrt
    print(f"[verif] HIST_PATH = {rrt.HIST_PATH}, FIRM_MAX_ACCOUNTS Blueberry = {ei.FIRM_MAX_ACCOUNTS['Blueberry']}")

    if mode == "AB":
        configs = [("baseline", None), ("section_A", "A"), ("section_B", "B")]
        run_sweep(n_sims, (1000.0, 3000.0), configs, out_tag="AB")

    elif mode == "C":
        cpop = _contrarian_population()
        print(f"[verif] population contrarian (0.75<=rr_tp1<1.25) : {len(cpop)} trades, "
              f"winrate={(cpop['r_trailing']>0).mean():.3f} EV={cpop['r_trailing'].mean():+.3f}R")
        configs = [("baseline", None), ("section_C", "C")]
        run_sweep(n_sims, (1000.0, 3000.0), configs, out_tag="C", contrarian_pop=cpop)

    elif mode == "D":
        configs = [("baseline", None)]
        ceilings = (1000.0, 2000.0, 3000.0, 5000.0, 7500.0, 10000.0)
        run_sweep(n_sims, ceilings, configs, out_tag="D")

    print(f"\nTermine en {time.time()-t_start:.0f}s.")
