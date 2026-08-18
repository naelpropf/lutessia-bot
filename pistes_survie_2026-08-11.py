"""
5 pistes de survie face aux series de casses (08/11, prompt utilisateur) --
aucune ne predit une mauvaise periode (chantier precurseur ferme, 10
pistes rejetees, registre_strategie_trading.md §2.16-2.26) : toutes
reagissent a des faits DEJA REALISES (casses survenues) ou changent la
structure elle-meme. Base engine = etape_ao_run_f_cout_reel_2026-08-11.py
(config officielle par plafond deja adoptee, decision #16 registre_
parametres_projet.md §1.8/§2.35bis -- Run C/BB14j a 1000$, Run F/BB7j a
3000$), etendu avec 5 mecanismes optionnels (jamais combines entre eux
sauf p5 qui EST p3+decorrelation) :

- p1_emergency   : fonds d'urgence reactif (skim % de chaque credit
  reserve positif vers un bucket verrouille, deverse d'un coup des que
  N casses surviennent dans une fenetre de W jours).
- p2_postbreak    : sizing reduit temporairement sur un compte QUI VIENT
  DE CASSER (peu importe la cause), orthogonal a V2 (multiplie, ne
  remplace pas).
- p3_dual_starter : 2e firm active des le jour 0 (capital ajoute, pas
  "divise" au sens litteral -- les paliers de challenge sont des tiers
  fixes par firm, indivisibles ; deviation documentee vs le libelle du
  prompt, mais MEME convention que le bootstrap parallele BB+GFT deja
  teste §2.6 registre_parametres_projet.md, ici applique a un candidat
  jamais teste (FundedNext) et reteste sous la config actuelle).
- p4_fongibilite  : port du mecanisme deja teste/rejete
  (etape_h_fongibilite_slots_2026-08-10.py, EV_PER_DOLLAR-sorted), REJOUE
  sous la config actuelle (cadence payout par firm, population 721,
  cap Blueberry corrige) -- rejet original date du 08/10 nuit, avant ces
  3 corrections, principe de fraicheur applique.
- p5_decorrelated : p3_dual_starter(second_starter="GFT") + le flux de
  trades du 2e starter est un ORDRE INDEPENDANT (permutation propre) de
  la MEME population plutot que le flux partage copytrade -- isole
  l'effet de correlation copytrade de l'effet de liquidite en rafale
  dans le rejet de "Piste A"/bootstrap parallele a 1000$.

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
FIRMS = ("Blueberry", "FTMO", "Fivers", "GFT", "FundedNext")

HYSTERESIS = 0.10
FTMO_DISCOUNT_FACTOR = 0.90
GOAT_GUARD_SPLIT_DAYS = 30
GOAT_GUARD_SPLIT_FLAT = 0.50
PAYOUT_CYCLE_FIRMS = ("Blueberry", "GFT", "Fivers")

# Decision #16 (08/11, registre_parametres_projet.md §1.8/§2.35bis) : cadence
# Blueberry conditionnelle au plafond -- meme convention partout dans ce script.
BB_PAYOUT_7J_CEILINGS = {3000.0}
PAYOUT_CYCLE_DAYS_FIRST = {"Blueberry": 14, "GFT": 3, "Fivers": 14}
PAYOUT_CYCLE_DAYS_SUBSEQUENT = {"Blueberry": 14, "GFT": 1.5, "Fivers": 14}
BB_PAYOUT_ADDON_MULT = 1.20

# Piste 4 : EV/$ (source Etape C corrigee, meme table que etape_h_fongibilite_
# slots_2026-08-10.py -- reprise telle quelle, c'est un ordre relatif entre
# firms, pas un chiffre affecte par les corrections cadence/population).
EV_PER_DOLLAR = {"FundedNext": 953.68, "Fivers": 783.39, "GFT": 638.57,
                  "Blueberry": 615.67, "FTMO": 578.03}


def price_for_bb(gname, fmt_key, palier, ceiling):
    price = ei.price_for(fmt_key, palier)
    bb_7j_active = ceiling in BB_PAYOUT_7J_CEILINGS
    return price * BB_PAYOUT_ADDON_MULT if (gname == "Blueberry" and bb_7j_active) else price


def payout_cycle_days(gname, first_payout_done, ceiling):
    if gname == "Blueberry" and ceiling in BB_PAYOUT_7J_CEILINGS:
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


def seq_grouped_dual_starter(second_starter, t_ftmo, t_fivers, t_gft, t_fundednext):
    """Comme ei.seq_grouped_multi, sauf que second_starter est day0 (retire
    de son entree after_count normale)."""
    entries = [
        ((ei.STARTER,), "day0", None, False),
        ((second_starter,), "day0", None, False),
        (("FTMO",), ("after_count", 1), t_ftmo, False),
        (("Fivers",), ("after_count", 1), t_fivers, False),
        (("GFT",), ("after_count", 1), t_gft, False),
        (("FundedNext",), ("after_count", 1), t_fundednext, True),
    ]
    return [e for e in entries if not (e[1] == ("after_count", 1) and e[0] == (second_starter,))]


def run_one(trades, slot_arrivals, market_data, excluded_map, order, ceiling, seq_grouped, format_by_firm,
            emergency_capital, eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult,
            b_entry_frac=None, b_reduction=None, pre_unlock_only=False,
            ftmo_discount=False, gft_goat_guard=False, payout_cycle=False,
            piste=None, p1_emergency_pct=None, p1_window_days=None, p1_break_trigger=None,
            p2_sizing_reduction=None, p2_duration_days=None,
            p3_second_starter=None, decorr_order=None):
    fmt_by_firm = {g: FORMATS[k] for g, k in format_by_firm.items()}
    dual_starter = piste in ("p3_dual_starter", "p5_decorrelated") and p3_second_starter is not None
    fongible = (piste == "p4_fongibilite")

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
        is_day0 = (gname == ei.STARTER) or (dual_starter and gname == p3_second_starter)
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
            a["_p2_until"] = None
        accounts_by_group[gname] = accs
        if is_day0:
            active0_cost += sum(a["cost"] for a in accs)

    fleet_unlocked = False
    _init_own_funded = {g for g in FIRMS if accounts_by_group[g][0]["active"] and not fmt_by_firm[g]["phases"]}
    state = {"reserve": 0.0, "reserve_emergency": 0.0, "ever_funded": False, "real_cash_paid": active0_cost,
             "total_breaks": 0,
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
             "break_times": [], "p1_unlocks": 0}
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

    def extra_account_eligible(gname):
        accs = accounts_by_group[gname]
        max_acc = ei.FIRM_MAX_ACCOUNTS.get(gname)
        if max_acc is not None and len(accs) >= max_acc:
            return None
        unit_palier = BASE_PALIER[gname] * ei.EXTRA_ACCOUNT_MULT
        current_capital = sum(a["palier"] for a in accs)
        if current_capital + unit_palier > ei.FIRM_CAPITAL_CAP[gname]:
            return None
        extra_cost = price_for_bb(gname, format_by_firm[gname], unit_palier, ceiling)
        if state["reserve"] >= extra_threshold_mult * extra_cost:
            return unit_palier, extra_cost
        return None

    def open_extra_account(gname, unit_palier, extra_cost, now):
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
        new_acc["_p2_until"] = None
        accounts_by_group[gname].append(new_acc)
        state["extra_accounts_opened"][gname] += 1
        state["total_opens"] += 1

    def process_extra_account(now):
        if not fleet_unlocked:
            return
        for gname in ei.GROWTH_FIRMS_EXTRA:
            elig = extra_account_eligible(gname)
            if elig is not None:
                unit_palier, extra_cost = elig
                open_extra_account(gname, unit_palier, extra_cost, now)

    def restart_cost(acc, gname):
        if downgrade_active() and gname == ei.STARTER:
            return acc["base_cost"]
        cost = price_for_bb(gname, format_by_firm[gname], acc["palier"], ceiling)
        if ftmo_discount and gname == "FTMO":
            cost *= FTMO_DISCOUNT_FACTOR
        return cost

    def allocate_capital(now):
        """Piste 4 : competition unifiee (relances + extra-comptes) triee
        EV/$ decroissant -- port de etape_h_fongibilite_slots_2026-08-10.py."""
        pending_ids = {p["key"] for p in pending_reopen}
        candidates = []
        for gname, accs in accounts_by_group.items():
            for acc in accs:
                if acc["active"] or acc["last_open_time"] is None or id(acc) in pending_ids:
                    continue
                cost = restart_cost(acc, gname)
                candidates.append((EV_PER_DOLLAR[gname], "restart", gname, cost, acc))
        if fleet_unlocked:
            for gname in ei.GROWTH_FIRMS_EXTRA:
                elig = extra_account_eligible(gname)
                if elig is not None:
                    unit_palier, extra_cost = elig
                    candidates.append((EV_PER_DOLLAR[gname], "extra", gname, extra_cost, unit_palier))
        candidates.sort(key=lambda c: -c[0])
        for ev, kind, gname, cost, payload in candidates:
            if kind == "restart":
                acc = payload
                handle_cost_hybrid(cost, pending_reopen, id(acc),
                                    lambda a=acc, c=cost, f=fmt_by_firm[gname]: reopen_account(a, c, f, skip_to_funded=False))
            else:
                unit_palier = payload
                elig_now = extra_account_eligible(gname)
                if elig_now is not None:
                    open_extra_account(gname, unit_palier, elig_now[1], now)

    def structure_complete():
        for g in FIRMS:
            if not accounts_by_group[g][0]["active"]:
                return False
        return True

    def effective_risk(acc, pdef, base_r):
        r = base_r
        if b_entry_frac is not None and not (pre_unlock_only and fleet_unlocked):
            dd_max = pdef["dd_max_pct"]
            if dd_max is not None:
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
                r = r * mult
        if piste == "p2_postbreak" and acc.get("_p2_until") is not None and state["_now"] < acc["_p2_until"]:
            r = r * (1.0 - p2_sizing_reduction)
        return r

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

                trade_use = trade
                if piste == "p5_decorrelated" and dual_starter and gname == p3_second_starter and decorr_order is not None:
                    trade_use = trades[decorr_order[slot_idx]]

                funded_pnl_before = acc["total_funded_pnl"] if was_funded else None
                reserve_before = state["reserve"]
                just_funded = process_trade_mf(acc, trade_use, now, fmt, state, r, market_data, excluded_map,
                                                split_flat=split_this, reserve_share=reserve_share,
                                                cost_override=0.0)

                if piste == "p1_emergency":
                    delta_credit = state["reserve"] - reserve_before
                    if delta_credit > 0:
                        skim = delta_credit * p1_emergency_pct
                        state["reserve"] -= skim
                        state["reserve_emergency"] += skim

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

                    if piste == "p1_emergency":
                        bt = state["break_times"]
                        bt.append(now)
                        cutoff = now - p1_window_days * 86400
                        state["break_times"] = [t for t in bt if t >= cutoff]
                        if len(state["break_times"]) >= p1_break_trigger and state["reserve_emergency"] > 0:
                            state["reserve"] += state["reserve_emergency"]
                            state["reserve_emergency"] = 0.0
                            state["break_times"] = []
                            state["p1_unlocks"] += 1

                    if piste == "p2_postbreak":
                        acc["_p2_until"] = now + p2_duration_days * 86400

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
                        acc["active"] = False
                        if not fongible:
                            if downgrade_active() and gname == ei.STARTER:
                                cost = acc["base_cost"]
                            else:
                                cost = restart_cost(acc, gname)
                            handle_cost_hybrid(cost, pending_reopen, id(acc),
                                                lambda a=acc, c=cost, f=fmt: reopen_account(a, c, f, skip_to_funded=False))
                        # sinon (fongible=True) : rien ici, allocate_capital() plus bas ce meme slot.
                else:
                    if was_challenge and just_funded and gname not in state["group_own_funded"]:
                        state["group_own_funded"].add(gname)
                        state["group_funded_count"] += 1

        if fongible:
            allocate_capital(now)
        else:
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
              "p1_unlocks": state["p1_unlocks"],
              "full_structure_month": full_structure_month if full_structure_month is not None else float("nan")}
    for g in PAYOUT_CYCLE_FIRMS:
        result[f"forfeited_pre_{g}"] = state["forfeited_pre"][g]
        result[f"forfeited_post_{g}"] = state["forfeited_post"][g]
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


EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK = 1.25, 1.90, 1.75
COMMON_KW = dict(b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True,
                  ftmo_discount=True, gft_goat_guard=True, payout_cycle=True)


def run_sweep(n_sims, ceilings, configs, seq_by_config=None, seed=9999, out_tag="survie"):
    """configs : liste de (label, piste, extra_kwargs_dict). seq_by_config
    permet de fournir un seq_grouped different par config (Piste 3/5,
    dual starter) -- sinon seq baseline utilisee."""
    pop, market_data, excluded_map, seq_baseline, config = _common_setup()
    rows = []
    for ceiling in ceilings:
        for label, piste, kw in configs:
            seq = (seq_by_config or {}).get(label, seq_baseline)
            rng_wr = random.Random(seed)
            rng_boot = random.Random(seed + 1)
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
                decorr_order = None
                if piste == "p5_decorrelated":
                    decorr_order = list(range(len(raw_trades)))
                    random.Random(rng_boot.random()).shuffle(decorr_order)
                res = run_one(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, seq, config,
                              ei.DEFAULT_EMERGENCY, EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                              ei.EXTRA_THRESHOLD_MULT, piste=piste, decorr_order=decorr_order, **COMMON_KW, **kw)
                recs.append(res)
            df = pd.DataFrame(recs)
            net = df["final_net_split"] - df["is_paid_cum"]
            year1_neg = df["year1_net_split"] < 0
            row = dict(ceiling=ceiling, config=label, n=len(df),
                       profit_moyen=net.mean(), profit_median=net.median(),
                       solde_negatif_annee4=(net < 0).mean() * 100, hit_ceiling_pct=df["hit_ceiling"].mean() * 100,
                       annee1_neg=year1_neg.mean() * 100,
                       full_structure_month_median=df["full_structure_month"].median())
            if "p1_unlocks" in df.columns:
                row["p1_unlocks_moy"] = df["p1_unlocks"].mean()
            rows.append(row)
            print(f"[ceiling={ceiling:.0f}$ config={label:20s}] profit_moyen={row['profit_moyen']:+,.0f}$ "
                  f"profit_median={row['profit_median']:+,.0f}$ solde_negatif_annee4={row['solde_negatif_annee4']:.2f}% "
                  f"hit_ceiling={row['hit_ceiling_pct']:.2f}% annee1<0={row['annee1_neg']:.2f}% "
                  f"deblocage_median={row['full_structure_month_median']:.1f}mois ({time.time()-t0:.0f}s)")
            pd.DataFrame(rows).to_csv(f"pistes_{out_tag}_n{n_sims}.csv", index=False)
    return pd.DataFrame(rows)


def replay_run202(ceiling, piste, kw, seq=None, seed=9999):
    """Rejoue exactement run_idx=202 (RNG avance sequentiellement 0..201
    sans capture, 202 capture) -- meme technique que mode_point2
    (edge_circuit_breaker_v2). Utilise pour Piste 2 (runs catastrophiques
    deja identifies ceiling1000_run202/ceiling3000_run202)."""
    pop, market_data, excluded_map, seq_baseline, config = _common_setup()
    seq = seq or seq_baseline
    rng_wr = random.Random(seed)
    rng_boot = random.Random(seed + 1)
    raw_trades = raw_slots = None
    for run_idx in range(203):
        wr_draw = rng_wr.betavariate(ei.ALPHA_POST, ei.BETA_POST)
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_draw, 1.0, False, random.Random(rng_boot.random()))
        block_seconds = 2 * 30 * DAY_SECONDS
        blocks = build_blocks(trades, slot_arrivals, block_seconds)
        target_duration = slot_arrivals[-1]
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot, target_duration)
    order = list(range(len(raw_trades)))
    res = run_one(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, seq, config,
                  ei.DEFAULT_EMERGENCY, EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                  ei.EXTRA_THRESHOLD_MULT, piste=piste, **COMMON_KW, **kw)
    net = res["final_net_split"] - res["is_paid_cum"]
    print(f"[run202 replay, ceiling={ceiling:.0f}$, piste={piste}] net_final={net:+,.0f}$ "
          f"total_breaks={res['total_breaks']} hit_ceiling={res['hit_ceiling']}")
    return res


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "p1"
    n_sims = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    t_start = time.time()
    import rr_threshold_test as rrt
    print(f"[verif] HIST_PATH = {rrt.HIST_PATH}, FIRM_MAX_ACCOUNTS Blueberry = {ei.FIRM_MAX_ACCOUNTS['Blueberry']}")

    if mode == "p1":
        # Grille reduite (6 combos, pas les 18 du produit cartesien complet) pour
        # rester dans un temps de calcul raisonnable a n=300 -- couvre les bornes
        # (10%/20%) et les 3 fenetres (7/14/30j) avec N=2 ou 3 selon le cas.
        configs = [("baseline", None, {})]
        for pct, W, N in ((0.10, 7, 2), (0.10, 14, 3), (0.10, 30, 2),
                          (0.20, 7, 2), (0.20, 14, 3), (0.20, 30, 2)):
            configs.append((f"p1_pct{int(pct*100)}_W{W}_N{N}", "p1_emergency",
                             dict(p1_emergency_pct=pct, p1_window_days=W, p1_break_trigger=N)))
        run_sweep(n_sims, (1000.0, 3000.0), configs, out_tag="p1")

    elif mode == "p2":
        configs = [("baseline", None, {})]
        for red in (0.25, 0.50):
            for dur in (5, 10, 15):
                configs.append((f"p2_red{int(red*100)}_dur{dur}d", "p2_postbreak",
                                 dict(p2_sizing_reduction=red, p2_duration_days=dur)))
        run_sweep(n_sims, (1000.0, 3000.0), configs, out_tag="p2")

    elif mode == "p2_run202":
        for ceiling in (1000.0, 3000.0):
            replay_run202(ceiling, None, {})
            for red in (0.25, 0.50):
                for dur in (5, 10, 15):
                    replay_run202(ceiling, "p2_postbreak", dict(p2_sizing_reduction=red, p2_duration_days=dur))

    elif mode == "p3":
        seq_by_config = {}
        configs = [("baseline", None, {})]
        for second in ("GFT", "FundedNext"):
            label = f"p3_dual_{second}"
            configs.append((label, "p3_dual_starter", dict(p3_second_starter=second)))
            seq_by_config[label] = seq_grouped_dual_starter(second, 1000, 15000, 25000, 25000)
        run_sweep(n_sims, (1000.0, 3000.0), configs, seq_by_config=seq_by_config, out_tag="p3")

    elif mode == "p4":
        configs = [("baseline", None, {}), ("p4_fongibilite", "p4_fongibilite", {})]
        run_sweep(n_sims, (1000.0, 3000.0), configs, out_tag="p4")

    elif mode == "p5":
        seq5 = seq_grouped_dual_starter("GFT", 1000, 15000, 25000, 25000)
        configs = [
            ("baseline", None, {}),
            ("p5_correlated_BB_GFT", "p3_dual_starter", dict(p3_second_starter="GFT")),
            ("p5_decorrelated_BB_GFT", "p5_decorrelated", dict(p3_second_starter="GFT")),
        ]
        seq_by_config = {"p5_correlated_BB_GFT": seq5, "p5_decorrelated_BB_GFT": seq5}
        run_sweep(n_sims, (1000.0,), configs, seq_by_config=seq_by_config, out_tag="p5")

    print(f"\nTermine en {time.time()-t_start:.0f}s.")
