"""
Chantier "capital combine, deux traders" (08/11, prompt utilisateur). Section 1
(replication identique) + Section 1bis (specialisation par segment de signal).
Base = etape_ao_run_f_cout_reel_2026-08-11.py / structure_pistes_2026-08-11.py
(config officielle par plafond, decision #16 §1.8/§2.35bis, seuil BB7j
generalise en >=3000$). n=300, screening -- rien n'est adopte sans n=600+
cascade check.

Contexte plafonds combines (confirme par les 3 firms, cf. prompt) :
- FTMO/GFT : 400k$ PAR TRADER. Un associe reel (VPS, comptes, decisions
  distincts) EST un trader distinct au sens FTMO/GFT -- chaque trader a son
  PROPRE plafond 400k$ independant sur ces 2 firms. Pas de coordination
  necessaire -- 2 fleets FTMO/GFT independantes.
- Blueberry : 400k$ "per trader OR HOUSEHOLD", ambiguite associe-societe non
  resolue -- traite ici comme NON-DOUBLABLE (capital combine 400k$ PARTAGE
  entre les 2 traders), 2 sous-variantes testees :
  (a) "solo1" -- Trader 1 recoit toute la croissance Blueberry (comptes
      extra), Trader 2 garde uniquement son palier de demarrage jour 0
      (aucune croissance Blueberry).
  (b) "split" -- capacite de croissance Blueberry partagee au fil de l'eau
      (compteur unique decrement par le premier arrive), plafonnee a 400k$
      combines pour les 2 traders.
- Fivers/FundedNext : statut plafond combine multi-trader NON VERIFIE --
  traites PAR DEFAUT comme FTMO/GFT (plafond par trader, independant),
  hypothese explicitement signalee non confirmee.

N'importe pas ce script directement (convention du projet).
"""
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

from engine_multiformat import FORMATS, make_acc_mf, process_trade_mf, _current_phase
import etape_e_fleet_integration as ei

# Groupes de paires (Section 1bis, variante "pairs") -- meme partition que
# Section A du chantier structurel precedent (structure_pistes_2026-08-11.py,
# PAIR_GROUP_1/2), copiee ici plutot qu'importee : les scripts dates
# "N'importe pas ce script directement" ne sont pas concus pour l'import
# (nom de fichier avec tirets, convention du projet -- chaque script date
# est un point d'entree standalone).
PAIR_GROUP_1 = {"NZD/USD", "GBP/JPY", "USD/CAD", "USD/JPY", "USD/CHF", "EUR/JPY", "GBP/CHF"}
PAIR_GROUP_2 = {"AUD/JPY", "AUD/USD", "EUR/GBP", "CHF/JPY", "EUR/USD", "GBP/USD", "EUR/CHF"}

YEAR_SECONDS = 365.25 * DAY_SECONDS
MONTH_SECONDS = DAYS_PER_MONTH * DAY_SECONDS
SIX_MONTHS_SECONDS = 6 * MONTH_SECONDS
FIRMS = ("Blueberry", "FTMO", "Fivers", "GFT", "FundedNext")
TRADERS = ("T1", "T2")

HYSTERESIS = 0.10
FTMO_DISCOUNT_FACTOR = 0.90
GOAT_GUARD_SPLIT_DAYS = 30
GOAT_GUARD_SPLIT_FLAT = 0.50
PAYOUT_CYCLE_FIRMS = ("Blueberry", "GFT", "Fivers")
BB_7J_CEILING_THRESHOLD = 3000.0
PAYOUT_CYCLE_DAYS_FIRST = {"Blueberry": 14, "GFT": 3, "Fivers": 14}
PAYOUT_CYCLE_DAYS_SUBSEQUENT = {"Blueberry": 14, "GFT": 1.5, "Fivers": 14}
BB_PAYOUT_ADDON_MULT = 1.20
BB_COMBINED_CAP = 400000.0


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


def ticker_allowed(tid, gname, ticker, spec_variant):
    if spec_variant != "pairs":
        return True
    group = PAIR_GROUP_1 if tid == "T1" else PAIR_GROUP_2
    return ticker in group


def run_dual(trades, slot_arrivals, market_data, excluded_map, order, seq_grouped, format_by_firm,
             emergency_capital, eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult,
             ceiling_combined, reserve_pooled, bb_variant, spec_variant="replication",
             contrarian_trades=None, contrarian_slots=None, log_events=False):
    """CORRECTION METHODOLOGIQUE (08/12) : ceiling_combined est un SEUL
    plafond personnel (le filet de securite -- argent sorti de la poche en
    dernier recours), PARTAGE entre les 2 traders (1000$ ou 3000$ TOTAL, pas
    par trader). Consomme par le premier des deux qui en a besoin. A NE PAS
    CONFONDRE avec state["reserve"] (tresorerie de trading, profits
    reinvestis) qui reste separee par trader sous l'architecture "separee"
    (reserve_pooled=False, gagnante en n=300, §2.50 registre_parametres_
    projet.md). reserve_pooled : bool (concerne UNIQUEMENT reserve, pas le
    plafond personnel qui est TOUJOURS combine desormais). bb_variant :
    "solo1"|"split". spec_variant : "replication" (meme flux, meme
    population) | "pairs" (T1=PAIR_GROUP_1, T2=PAIR_GROUP_2, meme
    population) | "rr_band" (T1=population standard, T2=flux contrarian
    independant fourni via contrarian_trades/contrarian_slots).
    log_events=True : accumule un journal complet."""
    fmt_by_firm = {g: FORMATS[k] for g, k in format_by_firm.items()}
    event_log = [] if log_events else None

    def log_event(now, tid, gname, ev_type, extra=None):
        if event_log is None:
            return
        rec = {"jour_simulation": round(now / 86400.0, 2), "trader": tid, "firm": gname,
               "type_evenement": ev_type, "bb_used_shared_combined": round(bb_used_shared[0], 2)}
        if extra:
            rec.update(extra)
        event_log.append(rec)

    def base_palier_cost(gname, ceiling):
        if gname == "FundedNext":
            fmt_key = format_by_firm["FundedNext"]
            return ei.FUNDEDNEXT_PALIER, price_for_bb(gname, fmt_key, ei.FUNDEDNEXT_PALIER, ceiling)
        if gname == "Fivers":
            fmt_key = format_by_firm["Fivers"]
            palier = ei.FIVERS_PALIER[fmt_key]
            return palier, price_for_bb(gname, fmt_key, palier, ceiling)
        palier = BASE_PALIER[gname]
        return palier, price_for_bb(gname, format_by_firm[gname], palier, ceiling)

    accounts = {tid: {} for tid in TRADERS}
    active0_cost = {tid: 0.0 for tid in TRADERS}
    for tid in TRADERS:
        ceiling = ceiling_combined
        for gname in FIRMS:
            is_day0 = (gname == ei.STARTER)
            palier, cost = base_palier_cost(gname, ceiling)
            fmt = fmt_by_firm[gname]
            accs = [make_acc_mf(fmt, palier, cost=cost, active=is_day0) for _ in range(ei.N_ACCOUNTS_DAY0[gname])]
            for a in accs:
                a["_gname"] = gname
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
            accounts[tid][gname] = accs
            if is_day0:
                active0_cost[tid] += sum(a["cost"] for a in accs)

    pool_reserve = [0.0]  # architecture B (partagee, PAS le plafond personnel)
    # Plafond personnel COMBINE (correction 08/12) : un SEUL filet de securite
    # partage entre les 2 traders, 1000$ ou 3000$ TOTAL -- consomme par le
    # premier des deux qui en a besoin, distinct de state["reserve"] (garde
    # separee par trader sous architecture A). active0_cost des 2 traders
    # s'additionne des le depart puisque les 2 flottes demarrent
    # SIMULTANEMENT au jour 0 (verifie -- is_day0 identique pour T1/T2 dans
    # la boucle ci-dessus, aucun decalage de calendrier).
    combined_cash = {"real_cash_paid": active0_cost["T1"] + active0_cost["T2"], "hit_ceiling": False}
    st = {}
    for tid in TRADERS:
        _init_own_funded = {g for g in ("Blueberry",) if not fmt_by_firm[g]["phases"]}
        st[tid] = {"reserve": 0.0, "total_breaks": 0,
                   "group_funded_count": len(_init_own_funded), "group_own_funded": set(_init_own_funded),
                   "emergency_remaining": emergency_capital, "is_paid_cum": 0.0, "ever_funded": False,
                   "extra_accounts_opened": {g: 0 for g in ei.GROWTH_FIRMS_EXTRA},
                   "_now": 0.0,
                   "total_opens": sum(1 for accs in accounts[tid].values() for a in accs if a["last_open_time"] == 0.0),
                   "forfeited_pre": {g: 0.0 for g in PAYOUT_CYCLE_FIRMS}, "forfeited_post": {g: 0.0 for g in PAYOUT_CYCLE_FIRMS},
                   "forfeit_events_pre": {g: 0 for g in PAYOUT_CYCLE_FIRMS}, "forfeit_events_post": {g: 0 for g in PAYOUT_CYCLE_FIRMS},
                   "break_days": [], "fleet_unlocked": False,
                   "pending_group_trigger": [(names, trig, thresh, final) for names, trig, thresh, final in seq_grouped if trig != "day0"],
                   "pending_reopen": [], "pending_group_open": [],
                   "fy_start_net": {0: 0.0}, "acomptes_paid_by_year": {}, "next_fy_to_close": 0, "tax_events": [],
                   "full_structure_month": None, "year1_net_split": None, "reserve_min_6mo": float("inf")}
    bb_used_shared = [sum(a["palier"] for a in accounts["T1"]["Blueberry"]) +
                      sum(a["palier"] for a in accounts["T2"]["Blueberry"])]
    for tid in TRADERS:
        for a in accounts[tid]["Blueberry"]:
            log_event(0.0, tid, "Blueberry", "jour0_creation", {"palier": a["palier"], "cost": round(a["cost"], 2)})

    def get_reserve(tid):
        return pool_reserve[0] if reserve_pooled else st[tid]["reserve"]

    def add_reserve(tid, amt):
        if reserve_pooled:
            pool_reserve[0] += amt
        else:
            st[tid]["reserve"] += amt

    def sub_reserve(tid, amt):
        add_reserve(tid, -amt)

    def combined_net_all():
        total = 0.0
        for tid in TRADERS:
            total += sum(a["total_funded_pnl"] - a["total_fees_paid"] for accs in accounts[tid].values() for a in accs)
        return total

    def combined_net_trader(tid):
        return sum(a["total_funded_pnl"] - a["total_fees_paid"] for accs in accounts[tid].values() for a in accs)

    def n_active_accounts(tid):
        return sum(1 for accs in accounts[tid].values() for a in accs if a["active"])

    def downgrade_active(tid):
        return not st[tid]["fleet_unlocked"]

    def handle_cost_hybrid(tid, cost, pending_list, pending_key, on_success):
        # Plafond personnel COMBINE (correction 08/12) : "room" est calcule
        # sur le pool partage combined_cash, PAS sur un plafond par trader --
        # le premier des deux qui a besoin de puiser dans le filet de
        # securite personnel consomme la MEME reserve que l'autre.
        if get_reserve(tid) >= cost:
            sub_reserve(tid, cost)
            on_success()
            return
        shortfall = cost - get_reserve(tid)
        sub_reserve(tid, get_reserve(tid))
        room = max(0.0, ceiling_combined - combined_cash["real_cash_paid"])
        if shortfall <= room:
            combined_cash["real_cash_paid"] += shortfall
            on_success()
        else:
            paid_now = room
            remaining = shortfall - paid_now
            combined_cash["real_cash_paid"] += paid_now
            if not combined_cash["hit_ceiling"]:
                log_event(st[tid]["_now"], tid, None, "hit_ceiling_touche",
                          {"real_cash_paid_combined": round(combined_cash["real_cash_paid"], 2),
                           "ceiling_combined": ceiling_combined})
            combined_cash["hit_ceiling"] = True
            pending_list.append({"key": pending_key, "cost_remaining": remaining, "on_success": on_success})

    def process_pending(tid, pending_list):
        i = 0
        while i < len(pending_list):
            item = pending_list[i]
            if get_reserve(tid) >= item["cost_remaining"]:
                sub_reserve(tid, item["cost_remaining"])
                item["on_success"]()
                pending_list.pop(i)
            else:
                i += 1

    def reopen_account(tid, acc, cost, fmt, skip_to_funded=False):
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
        acc["last_open_time"] = st[tid]["_now"]
        acc["_dd_reduced"] = False
        acc["_gg_triggered_count"] = 0
        acc["_gg_split_until"] = None
        acc["pending_payout"] = 0.0
        acc["last_payout_time"] = st[tid]["_now"]
        acc["_first_payout_done"] = False
        st[tid]["total_opens"] += 1
        if downgrade_active(tid) and acc.get("_gname") == ei.STARTER:
            acc["palier"] = acc["base_palier"]
            acc["cost"] = acc["base_cost"]

    def open_group(tid, gname, is_final):
        for a in accounts[tid][gname]:
            a["active"] = True
            a["total_fees_paid"] = a["cost"]
            a["last_open_time"] = st[tid]["_now"]
            a["_dd_reduced"] = False
            a["_gg_triggered_count"] = 0
            a["_gg_split_until"] = None
            a["pending_payout"] = 0.0
            a["last_payout_time"] = st[tid]["_now"]
            a["_first_payout_done"] = False
            st[tid]["total_opens"] += 1
        if not fmt_by_firm[gname]["phases"]:
            if gname not in st[tid]["group_own_funded"]:
                st[tid]["group_own_funded"].add(gname)
                st[tid]["group_funded_count"] += 1

    def try_emergency_bootstrap(tid):
        s = st[tid]
        if n_active_accounts(tid) != 0 or emergency_capital <= 0 or s["emergency_remaining"] <= 0:
            return
        bb_acc = accounts[tid][ei.STARTER][0]
        cost = bb_acc["base_cost"] if downgrade_active(tid) else bb_acc["cost"]
        if s["emergency_remaining"] >= cost:
            s["emergency_remaining"] -= cost
            reopen_account(tid, bb_acc, cost, fmt_by_firm[ei.STARTER])
            s["pending_reopen"][:] = [p for p in s["pending_reopen"] if p["key"] != id(bb_acc)]

    def blueberry_extra_allowed(tid):
        if bb_variant == "solo1":
            return tid == "T1"
        return True  # "split" : autorise pour les deux, plafonne par capacite partagee

    def process_extra_account(tid, now):
        if not st[tid]["fleet_unlocked"]:
            return
        for gname in ei.GROWTH_FIRMS_EXTRA:
            accs = accounts[tid][gname]
            max_acc = ei.FIRM_MAX_ACCOUNTS.get(gname)
            if max_acc is not None and len(accs) >= max_acc:
                continue
            unit_palier = BASE_PALIER[gname] * ei.EXTRA_ACCOUNT_MULT
            if gname == "Blueberry":
                if not blueberry_extra_allowed(tid):
                    continue
                if bb_used_shared[0] + unit_palier > BB_COMBINED_CAP:
                    continue
            else:
                current_capital = sum(a["palier"] for a in accs)
                if current_capital + unit_palier > ei.FIRM_CAPITAL_CAP[gname]:
                    continue
            extra_cost = price_for_bb(gname, format_by_firm[gname], unit_palier, ceiling_combined)
            if get_reserve(tid) >= extra_threshold_mult * extra_cost:
                sub_reserve(tid, extra_cost)
                new_acc = make_acc_mf(fmt_by_firm[gname], unit_palier, cost=extra_cost, active=True)
                new_acc["total_fees_paid"] = extra_cost
                new_acc["_gname"] = gname
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
                st[tid]["extra_accounts_opened"][gname] += 1
                st[tid]["total_opens"] += 1
                if gname == "Blueberry":
                    bb_used_shared[0] += unit_palier
                log_event(now, tid, gname, "compte_extra_ouvert", {"palier": unit_palier, "cost": round(extra_cost, 2)})

    def structure_complete(tid):
        for g in FIRMS:
            if not accounts[tid][g][0]["active"]:
                return False
        return True

    def effective_risk(acc, pdef, base_r):
        dd_max = pdef["dd_max_pct"]
        if dd_max is None:
            return base_r
        distance = dd_distance_pct(acc, pdef)
        frac = distance / dd_max if dd_max > 0 else 1.0
        was_reduced = acc["_dd_reduced"]
        if not was_reduced and frac <= 0.20:
            acc["_dd_reduced"] = True
        elif was_reduced and frac >= 0.20 + HYSTERESIS:
            acc["_dd_reduced"] = False
        mult = 0.5 if acc["_dd_reduced"] else 1.0
        return base_r * mult

    def close_fiscal_year(tid, y):
        s = st[tid]
        profit_y = combined_net_trader(tid) - s["fy_start_net"].get(y, 0.0)
        is_y = compute_is(profit_y)
        s["fy_start_net"][y + 1] = combined_net_trader(tid)
        acomptes_y = s["acomptes_paid_by_year"].get(y, 0.0)
        solde = max(0.0, is_y - acomptes_y)
        solde_time = (y + 1) * YEAR_SECONDS + SOLDE_OFFSET_DAYS * DAY_SECONDS
        s["tax_events"].append((solde_time, solde))
        if is_y > IS_THRESHOLD_ACOMPTE:
            for q_off in Q_OFFSETS_DAYS:
                t_acompte = (y + 1) * YEAR_SECONDS + q_off * DAY_SECONDS
                amt = ACOMPTE_FRACTION * is_y
                s["tax_events"].append((t_acompte, amt))
                s["acomptes_paid_by_year"][y + 1] = s["acomptes_paid_by_year"].get(y + 1, 0.0) + amt
        s["tax_events"].sort(key=lambda e: e[0])

    def process_one_account(tid, gname, acc, fmt, trade, now):
        s = st[tid]
        if not acc["active"]:
            return
        pre_unlock = not s["fleet_unlocked"]
        # eval_risk/fleet_risk : float (partage T1/T2) OU dict {"T1":..,"T2":..}
        # (Section 2, 08/12 -- risque optimise par trader, ex. T2 sur Strategie
        # B a un optimum eval_risk different de T1).
        tid_eval_risk = eval_risk[tid] if isinstance(eval_risk, dict) else eval_risk
        tid_fleet_risk = fleet_risk[tid] if isinstance(fleet_risk, dict) else fleet_risk
        base_risk = gft_eval_risk if gname == "GFT" else tid_eval_risk
        base_r = tid_fleet_risk if acc["phase"] == "funded" else base_risk
        pdef = _current_phase(fmt, acc)
        r = effective_risk(acc, pdef, base_r) if pre_unlock else base_r
        was_challenge = acc["active"] and acc["phase"] == "challenge"
        was_funded = acc["active"] and acc["phase"] == "funded"
        phase_before, idx_before = acc["phase"], acc["phase_index"]
        split_this = GOAT_GUARD_SPLIT_FLAT if (gname == "GFT" and acc["_gg_split_until"] is not None
                                                and now < acc["_gg_split_until"]) else 0.80

        use_payout_cycle = gname in PAYOUT_CYCLE_FIRMS
        funded_pnl_before = acc["total_funded_pnl"] if was_funded else None

        # proxy minimal pour reutiliser process_trade_mf (module partage) sans
        # le modifier -- "total_breaks" est un puits jetable (compte reel tenu
        # via s["total_breaks"] dans process_one_account, meme convention que
        # tous les autres scripts du projet, cost_override=0.0 neutralise
        # l'effet cash du doublon interne connu, cf. edge_circuit_breaker_v2
        # docstring). "ever_funded" DOIT refleter le vrai etat par trader
        # (persiste dans s["ever_funded"]) -- process_trade_mf s'en sert pour
        # determiner just_funded (1er financement JAMAIS de ce trader), qui
        # pilote a son tour le deblocage de groupe (group_funded_count) plus
        # bas. Un ever_funded fige a True aurait bloque just_funded a False en
        # permanence et gele le deblocage de toute la flotte (bug trouve et
        # corrige en debug avant le premier run n=300).
        proxy = {"reserve": get_reserve(tid), "ever_funded": s["ever_funded"], "total_breaks": 0}
        just_funded = process_trade_mf(acc, trade, now, fmt, proxy, r, market_data, excluded_map,
                                        split_flat=split_this, reserve_share=reserve_share,
                                        cost_override=0.0)
        s["ever_funded"] = proxy["ever_funded"]
        delta_reserve = proxy["reserve"] - get_reserve(tid)
        if delta_reserve != 0:
            add_reserve(tid, delta_reserve)

        if use_payout_cycle and was_funded:
            delta = acc["total_funded_pnl"] - funded_pnl_before
            if delta > 0:
                acc["total_funded_pnl"] -= delta
                sub_reserve(tid, delta * reserve_share)
                acc["pending_payout"] += delta

        if just_funded and acc["last_open_time"] is not None:
            pass

        if use_payout_cycle and acc["active"] and acc["last_payout_time"] is not None \
                and now - acc["last_payout_time"] >= payout_cycle_days(gname, acc["_first_payout_done"], ceiling_combined) * 86400:
            acc["total_funded_pnl"] += acc["pending_payout"]
            if acc["pending_payout"] > 0:
                add_reserve(tid, acc["pending_payout"] * reserve_share)
            acc["pending_payout"] = 0.0
            acc["last_payout_time"] = now
            acc["_first_payout_done"] = True

        progressed = (fmt["phases"] and (
            (acc["phase"] == "challenge" and acc["phase_index"] == idx_before + 1) or
            (acc["phase"] == "funded" and phase_before == "challenge")))
        reset_happened = (acc["cumulative_since_reset"] == 0.0 and acc["peak_since_reset"] == 0.0
                          and len(acc["trading_days_since_reset"]) == 0)
        broke = reset_happened and not progressed

        use_goat_guard = (broke and gname == "GFT" and was_funded and acc["_gg_triggered_count"] < 1)
        if use_goat_guard:
            acc["_gg_triggered_count"] += 1
            acc["_gg_split_until"] = now + GOAT_GUARD_SPLIT_DAYS * 86400
            acc["phase"] = "funded"
        elif broke:
            s["total_breaks"] += 1
            s["break_days"].append(int(now // 86400))
            log_event(now, tid, gname, "casse", {"ticker": trade.get("ticker"),
                                                   "r_realise": round(trade.get("outcome_r", 0.0), 3)})
            if use_payout_cycle and acc["pending_payout"] != 0.0:
                forfeited = max(0.0, acc["pending_payout"])
                bucket = s["forfeited_post"] if s["fleet_unlocked"] else s["forfeited_pre"]
                events = s["forfeit_events_post"] if s["fleet_unlocked"] else s["forfeit_events_pre"]
                if forfeited > 0:
                    bucket[gname] += forfeited
                    events[gname] += 1
                acc["pending_payout"] = 0.0
            use_bb_reset = (gname == "Blueberry" and was_funded and not acc["_reset_used"])
            if use_bb_reset:
                cost = 2.0 * acc["base_cost"]
                acc["active"] = False
                acc["_reset_used"] = True
                handle_cost_hybrid(tid, cost, s["pending_reopen"], id(acc),
                                    lambda a=acc, c=cost, f=fmt: reopen_account(tid, a, c, f, skip_to_funded=True))
            else:
                if downgrade_active(tid) and gname == ei.STARTER:
                    cost = acc["base_cost"]
                else:
                    cost = price_for_bb(gname, format_by_firm[gname], acc["palier"], ceiling_combined)
                    if gname == "FTMO":
                        cost *= FTMO_DISCOUNT_FACTOR
                acc["active"] = False
                handle_cost_hybrid(tid, cost, s["pending_reopen"], id(acc),
                                    lambda a=acc, c=cost, f=fmt: reopen_account(tid, a, c, f, skip_to_funded=False))
        else:
            if was_challenge and just_funded and gname not in s["group_own_funded"]:
                s["group_own_funded"].add(gname)
                s["group_funded_count"] += 1

    def advance_trader(tid, now):
        s = st[tid]
        if now <= SIX_MONTHS_SECONDS:
            s["reserve_min_6mo"] = min(s["reserve_min_6mo"], get_reserve(tid))
        s["reserve_min_full"] = min(s.get("reserve_min_full", float("inf")), get_reserve(tid))
        while (s["next_fy_to_close"] + 1) * YEAR_SECONDS <= now:
            close_fiscal_year(tid, s["next_fy_to_close"])
            s["next_fy_to_close"] += 1
        i = 0
        while i < len(s["tax_events"]):
            t_ev, amt = s["tax_events"][i]
            if t_ev > now:
                i += 1
                continue
            s["tax_events"].pop(i)
            # proxy complet (real_cash_paid lu/ecrit sur le pool COMBINE --
            # correction 08/12, l'impot d'un trader peut aussi puiser dans le
            # meme filet de securite personnel partage ; compteurs
            # tax_breach_* jetables, non rapportes par ce script) pour
            # reutiliser handle_tax_payment (module partage) sans le modifier.
            proxy = {"reserve": get_reserve(tid), "real_cash_paid": combined_cash["real_cash_paid"],
                     "tax_breach_count": 0, "tax_breach_total": 0.0, "tax_breach_max": 0.0,
                     "tax_breach_concurrent_with_repurchase": 0, "tax_breach_events": []}
            handle_tax_payment(amt, proxy, ceiling_combined, now, s["pending_reopen"], s["pending_group_open"])
            add_reserve(tid, proxy["reserve"] - get_reserve(tid))
            combined_cash["real_cash_paid"] = proxy["real_cash_paid"]
            s["is_paid_cum"] += amt
        process_extra_account(tid, now)
        process_pending(tid, s["pending_reopen"])
        process_pending(tid, s["pending_group_open"])
        try_emergency_bootstrap(tid)
        still_pending = []
        for group_names, trig, thresh, is_final in s["pending_group_trigger"]:
            _, n_req = trig
            if s["group_funded_count"] >= n_req and get_reserve(tid) >= thresh:
                for gname in group_names:
                    cost0 = sum(a["cost"] for a in accounts[tid][gname])
                    handle_cost_hybrid(tid, cost0, s["pending_group_open"], gname,
                                        lambda g=gname, f=is_final: open_group(tid, g, f))
                if is_final:
                    s["fleet_unlocked"] = True
            else:
                still_pending.append((group_names, trig, thresh, is_final))
        s["pending_group_trigger"] = still_pending
        if s["full_structure_month"] is None and structure_complete(tid):
            s["full_structure_month"] = now / MONTH_SECONDS

    # --- boucle principale ---
    if spec_variant == "rr_band" and contrarian_trades is not None:
        main_events = [(slot_arrivals[i], "main", i) for i in range(len(order))]
        t2_events = [(contrarian_slots[i], "t2", i) for i in range(len(contrarian_trades))]
        events = sorted(main_events + t2_events, key=lambda e: e[0])
    else:
        events = [(slot_arrivals[i], "main", trade_idx) for i, trade_idx in enumerate(order)]

    for now, source, idx in events:
        for tid in TRADERS:
            st[tid]["_now"] = now
        if st["T1"]["year1_net_split"] is None and now >= YEAR_SECONDS:
            st["T1"]["year1_net_split"] = combined_net_trader("T1")
        if st["T2"]["year1_net_split"] is None and now >= YEAR_SECONDS:
            st["T2"]["year1_net_split"] = combined_net_trader("T2")

        advance_trader("T1", now)
        advance_trader("T2", now)

        if spec_variant == "rr_band":
            active_traders = ("T1",) if source == "main" else ("T2",)
            trade = trades[idx] if source == "main" else contrarian_trades[idx]
        else:
            active_traders = TRADERS
            trade = trades[idx]

        for tid in active_traders:
            for gname, accs in accounts[tid].items():
                fmt = fmt_by_firm[gname]
                for acc in list(accs):
                    if not acc["active"]:
                        continue
                    if not ticker_allowed(tid, gname, trade["ticker"], spec_variant):
                        continue
                    process_one_account(tid, gname, acc, fmt, trade, now)

    for tid in TRADERS:
        if st[tid]["year1_net_split"] is None:
            st[tid]["year1_net_split"] = combined_net_trader(tid)

    result = {}
    for tid in TRADERS:
        s = st[tid]
        pre = s["full_structure_month"] is None or s["full_structure_month"] > 12
        result[f"{tid}_net"] = combined_net_trader(tid)
        result[f"{tid}_is_paid"] = s["is_paid_cum"]
        result[f"{tid}_year1_net"] = s["year1_net_split"]
        result[f"{tid}_total_breaks"] = s["total_breaks"]
        result[f"{tid}_reserve_min_full"] = s.get("reserve_min_full", 0.0) if s.get("reserve_min_full", float("inf")) != float("inf") else 0.0
        result[f"{tid}_break_days"] = s["break_days"]
    result["combined_net"] = combined_net_all()
    result["combined_is_paid"] = st["T1"]["is_paid_cum"] + st["T2"]["is_paid_cum"]
    result["combined_year1_net"] = st["T1"]["year1_net_split"] + st["T2"]["year1_net_split"]
    # Plafond personnel combine (correction 08/12) : UN SEUL flag, pas de
    # notion de "T1 vs T2" separee -- le pool est partage, donc "hit_ceiling"
    # n'a de sens qu'au niveau combine desormais.
    result["combined_hit_ceiling"] = combined_cash["hit_ceiling"]
    result["combined_real_cash_paid_final"] = combined_cash["real_cash_paid"]
    result["bb_used_shared_final"] = bb_used_shared[0]
    result["bb_T1_palier_sum"] = sum(a["palier"] for a in accounts["T1"]["Blueberry"])
    result["bb_T2_palier_sum"] = sum(a["palier"] for a in accounts["T2"]["Blueberry"])
    result["bb_T1_n_accounts"] = len(accounts["T1"]["Blueberry"])
    result["bb_T2_n_accounts"] = len(accounts["T2"]["Blueberry"])
    if log_events:
        result["event_log"] = event_log
    return result


# MAJ 08/12 (cascade RR1.35+corr0.80, registre_parametres_projet.md §2.62) :
# MIN_RR_T1 est desormais LA reference partagee entre le filtre d'entree de
# T1 et la borne haute de la bande contrarian de T2 -- les deux etaient
# codes en litteral duplique (1.25 chacun, independamment), ce qui a cree
# une zone morte potentielle (trades rr_tp1 in [1.25,1.35) ni pris par T1
# ni par T2) au moment de faire passer T1 seul de 1.25 a 1.35. Toute
# evolution future du seuil RR de T1 doit changer CETTE seule constante --
# la bande T2 (0.75 <= rr_tp1 < MIN_RR_T1) suit automatiquement, preservant
# sa semantique d'origine ("tout ce que T1 rejette, jusqu'a 0.75").
MIN_RR_T1 = 1.35
CORR_TH_ADOPTED = 0.80
CONTRARIAN_BAND_LOW = 0.75


def _common_setup():
    pop = build_population_with_trailing("fixed", 0.15, min_rr=MIN_RR_T1, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH_ADOPTED)
    seq = ei.seq_grouped_multi(1000, 15000, 25000, 25000)
    config = ei.CONFIG_REF
    return pop, market_data, excluded_map, seq, config


def _contrarian_population():
    pop = build_population_with_trailing("fixed", 0.15, min_rr=CONTRARIAN_BAND_LOW, verbose=False)
    band = pop[(pop["rr_tp1"] >= CONTRARIAN_BAND_LOW) & (pop["rr_tp1"] < MIN_RR_T1)].copy()
    return band.reset_index(drop=True)


EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK = 1.25, 1.90, 1.75


def clustering_pct(rows):
    """% de casses (pooles sur toutes les runs, T1+T2 confondus) tombant le
    meme jour calendaire qu'au moins une AUTRE casse (T1 ou T2) -- meme
    convention que le run202 (92,4%) et structure_pistes_2026-08-11.py."""
    total, clustered = 0, 0
    for r in rows:
        days = list(r["T1_break_days"]) + list(r["T2_break_days"])
        c = Counter(days)
        total += len(days)
        clustered += sum(1 for d in days if c[d] > 1)
    return (clustered / total * 100) if total else None


def run_sweep(n_sims, configs, out_tag, contrarian_pop=None, seed=9999):
    """configs : liste de (label, ceiling_combined, reserve_pooled,
    bb_variant, spec_variant). ceiling_combined : UN SEUL plafond personnel
    total, partage entre les 2 traders (correction 08/12)."""
    pop, market_data, excluded_map, seq, config = _common_setup()
    rows = []
    for label, ceiling_combined, reserve_pooled, bb_variant, spec_variant in configs:
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
            if spec_variant == "rr_band":
                wr_draw_c = rng_wr_c.betavariate(ei.ALPHA_POST, ei.BETA_POST)
                trades_c, slots_c = eng.build_flexible_population(contrarian_pop, wr_draw_c, 1.0, False,
                                                                    random.Random(rng_boot_c.random()))
                blocks_c = build_blocks(trades_c, slots_c, block_seconds)
                raw_trades_c, raw_slots_c = build_full_block_bootstrap_sequence(blocks_c, block_seconds, rng_boot_c, target_duration)
                contrarian_trades, contrarian_slots = raw_trades_c, raw_slots_c

            res = run_dual(raw_trades, raw_slots, market_data, excluded_map, order, seq, config,
                            ei.DEFAULT_EMERGENCY, EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                            ei.EXTRA_THRESHOLD_MULT, ceiling_combined=ceiling_combined, reserve_pooled=reserve_pooled,
                            bb_variant=bb_variant, spec_variant=spec_variant,
                            contrarian_trades=contrarian_trades, contrarian_slots=contrarian_slots)
            recs.append(res)

        df = pd.DataFrame(recs)
        combined_net = df["combined_net"] - df["combined_is_paid"]
        year1_neg = df["combined_year1_net"] < 0
        row = dict(config=label, ceiling_combined=ceiling_combined,
                   reserve_pooled=reserve_pooled, bb_variant=bb_variant, spec_variant=spec_variant, n=len(df),
                   profit_moyen=combined_net.mean(), profit_median=combined_net.median(),
                   solde_negatif_annee4=(combined_net < 0).mean() * 100,
                   hit_ceiling_pct=df["combined_hit_ceiling"].mean() * 100,
                   annee1_neg=year1_neg.mean() * 100,
                   clustering_pct=clustering_pct(recs))
        rows.append(row)
        print(f"[{label:40s}] profit_moyen={row['profit_moyen']:+,.0f}$ profit_median={row['profit_median']:+,.0f}$ "
              f"solde_negatif_annee4={row['solde_negatif_annee4']:.2f}% hit_ceiling_combine={row['hit_ceiling_pct']:.2f}% "
              f"annee1<0={row['annee1_neg']:.2f}% clustering={row['clustering_pct']:.1f}% ({time.time()-t0:.0f}s)")
        pd.DataFrame(rows).to_csv(f"dual_trader_{out_tag}_n{n_sims}.csv", index=False)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "screen"
    n_sims = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    t_start = time.time()
    import rr_threshold_test as rrt
    print(f"[verif] HIST_PATH = {rrt.HIST_PATH}, FIRM_MAX_ACCOUNTS Blueberry = {ei.FIRM_MAX_ACCOUNTS['Blueberry']}")

    if mode == "screen":
        # Etape 1 (PERIMEE depuis la correction 08/12 -- plafond combine, pas
        # par trader ; gardee pour reference/reexecution eventuelle uniquement).
        # screening a 3000$ combine -- 2 architectures x 2 variantes Blueberry.
        configs = []
        for pooled in (False, True):
            for bbv in ("solo1", "split"):
                label = f"{'pooled' if pooled else 'separe'}_BB-{bbv}_combined3000"
                configs.append((label, 3000.0, pooled, bbv, "replication"))
        run_sweep(n_sims, configs, out_tag="screen")

    elif mode == "combined":
        # CORRECTION METHODOLOGIQUE (08/12, prompt utilisateur) : plafond
        # personnel COMBINE (1000$ ou 3000$ TOTAL, partage entre T1/T2, pas
        # double). Architecture separee (reserve, gagnante n=300 §2.50) + BB
        # split (gagnant n=300) -- config par defaut, ecrasable en argv3/4.
        pooled = bool(int(sys.argv[3])) if len(sys.argv) > 3 else False
        bbv = sys.argv[4] if len(sys.argv) > 4 else "split"
        configs = []
        for c in (1000.0, 3000.0):
            label = f"{'pooled' if pooled else 'separe'}_BB-{bbv}_combined{int(c)}"
            configs.append((label, c, pooled, bbv, "replication"))
        run_sweep(n_sims, configs, out_tag="combined")

    elif mode == "spec":
        # Section 1bis (PERIMEE depuis la correction 08/12 -- utilisait
        # encore l'ancien plafond par trader ; gardee pour reference).
        pooled = bool(int(sys.argv[3])) if len(sys.argv) > 3 else False
        bbv = sys.argv[4] if len(sys.argv) > 4 else "split"
        cpop = _contrarian_population()
        print(f"[verif] population contrarian (0.75<=rr_tp1<{MIN_RR_T1}) : {len(cpop)} trades, "
              f"winrate={(cpop['r_trailing']>0).mean():.3f} EV={cpop['r_trailing'].mean():+.3f}R")
        configs = [
            (f"1bis_replication_{'pooled' if pooled else 'separe'}", 3000.0, pooled, bbv, "replication"),
            (f"1bis_rr_band_{'pooled' if pooled else 'separe'}", 3000.0, pooled, bbv, "rr_band"),
            (f"1bis_pairs_{'pooled' if pooled else 'separe'}", 3000.0, pooled, bbv, "pairs"),
        ]
        run_sweep(n_sims, configs, out_tag="spec", contrarian_pop=cpop)

    elif mode == "matrix":
        # Chantier "meme vs different strategie x reserve separee vs commune"
        # (08/12, prompt utilisateur) -- 4 configs, plafond personnel combine
        # (correction deja appliquee), architecture BB "split" (gagnante).
        # ceiling_combined en argv3 (defaut 3000.0, un seul niveau a la fois
        # comme demande).
        ceiling_combined = float(sys.argv[3]) if len(sys.argv) > 3 else 3000.0
        bbv = sys.argv[4] if len(sys.argv) > 4 else "split"
        cpop = _contrarian_population()
        print(f"[verif] population contrarian (0.75<=rr_tp1<{MIN_RR_T1}) : {len(cpop)} trades, "
              f"winrate={(cpop['r_trailing']>0).mean():.3f} EV={cpop['r_trailing'].mean():+.3f}R")
        configs = [
            (f"1_meme_strategie_reserve_separee_c{int(ceiling_combined)}", ceiling_combined, False, bbv, "replication"),
            (f"2_meme_strategie_reserve_commune_c{int(ceiling_combined)}", ceiling_combined, True, bbv, "replication"),
            (f"3_AB_reserve_separee_c{int(ceiling_combined)}", ceiling_combined, False, bbv, "rr_band"),
            (f"4_AB_reserve_commune_c{int(ceiling_combined)}", ceiling_combined, True, bbv, "rr_band"),
        ]
        run_sweep(n_sims, configs, out_tag=f"matrix_c{int(ceiling_combined)}", contrarian_pop=cpop)

    elif mode == "confirm":
        # Confirmation n=600+cascade (08/12, prompt utilisateur) -- SEULEMENT
        # config 1 (meme strategie, reserves separees) et config 4 (A/B,
        # reserve commune), les 2 candidats retenus a l'issue du screening
        # n=300 (§2.52 registre_parametres_projet.md). ceiling_combined en
        # argv3 (1000 ou 3000, une valeur a la fois).
        ceiling_combined = float(sys.argv[3]) if len(sys.argv) > 3 else 3000.0
        bbv = sys.argv[4] if len(sys.argv) > 4 else "split"
        cpop = _contrarian_population()
        print(f"[verif] population contrarian (0.75<=rr_tp1<{MIN_RR_T1}) : {len(cpop)} trades, "
              f"winrate={(cpop['r_trailing']>0).mean():.3f} EV={cpop['r_trailing'].mean():+.3f}R")
        configs = [
            (f"1_meme_strategie_reserve_separee_c{int(ceiling_combined)}", ceiling_combined, False, bbv, "replication"),
            (f"4_AB_reserve_commune_c{int(ceiling_combined)}", ceiling_combined, True, bbv, "rr_band"),
        ]
        run_sweep(n_sims, configs, out_tag=f"confirm_c{int(ceiling_combined)}", contrarian_pop=cpop)

    print(f"\nTermine en {time.time()-t_start:.0f}s.")
