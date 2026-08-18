"""
Etape H (08/10 nuit) : implementation de la fongibilite inter-firm, suite du
scoping (project_slot_fungibility_scoping_2026-08-09) et du ratio EV/$
regenere (project_etape_c_corrigee_ev_par_dollar_2026-08-09 --
etape_c_solo_comparison_corrige_2026-08-09.py).

EV_PER_DOLLAR (firm/format REF actuel, source Etape C corrigee) :
    FundedNext=953.68 > Fivers=783.39 > GFT=638.57 > Blueberry=615.67 > FTMO=578.03

===========================================================================
CE QUI CHANGE (fongible=True) vs baseline (fongible=False, reproduit
etape_e_final_lock_bbreset_2026-08-09.py a l'identique) :
===========================================================================
1. QUEUE GENERIQUE -- une casse "normale" (hors reset Blueberry) ne
   declenche plus handle_cost_hybrid() immediatement a l'identite du compte
   casse (acc bound au moment de la casse). Le compte est juste marque
   inactif ; il devient un CANDIDAT parmi d'autres dans la competition
   unifiee ci-dessous, evaluee a chaque slot.
2. COMPETITION UNIFIEE (allocate_capital(), remplace process_extra_account)
   -- a chaque slot, la liste de TOUS les candidats eligibles (comptes
   casses en attente de relance + opportunites d'extra-compte dont le seuil
   3x est atteint) est triee par EV_PER_DOLLAR[firm] decroissant, puis
   financee glouton dans cet ordre tant que la reserve (et, pour les
   relances seulement, le plafond de cash) le permet. Un slot moins cher
   peut donc passer devant un meilleur EV/$ si la reserve ne couvre que lui
   -- pas un ratio statique applique aveuglement, une vraie competition sous
   contrainte de tresorerie a chaque instant.
3. CE QUI RESTE HORS DE LA COMPETITION (deliberement, voir revalidation
   plus bas) :
   - Le RESET BLUEBERRY reste un chemin dedie, gere EXACTEMENT comme avant
     (handle_cost_hybrid immediat, lie au meme compte, skip_to_funded=True)
     -- le rediriger ailleurs annulerait le benefice meme du mecanisme
     (sauter l'evaluation sur CE compte precis).
   - Le DEBLOCAGE INITIAL PAR FIRM (pending_group_trigger / open_group)
     reste totalement intact -- ce n'est PAS un candidat de la competition,
     son propre seuil de reserve par firm continue de gater l'ouverture
     initiale exactement comme avant. Seuls des comptes DEJA ouverts au
     moins une fois (last_open_time is not None) entrent dans le pool de
     relance.

===========================================================================
POINT 3 -- le slot abandonne redevient-il eligible ? Avec quelle priorite ?
===========================================================================
OUI, TOUJOURS eligible, POUR TOUJOURS -- rien n'est jamais retire
definitivement du roster de la flotte. Il re-concourt a CHAQUE slot avec
exactement le score EV/$ statique de sa firm, ni plus ni moins (pas de
mecanisme d'anciennete/equite qui le remonterait apres avoir ete court-
circuite plusieurs fois). Consequence ASSUMEE et documentee : une firm dont
l'EV/$ est structurellement bas (FTMO=578,03, le plus bas des 5) peut voir
ses relances/extra-comptes systematiquement passer apres ceux des firms
mieux classees quand la reserve est disputee -- pas un bug, une consequence
du choix de priorite pure. Instrumente ci-dessous (pct_zero_active_end_*)
pour verifier empiriquement si une firm finit structurellement absente.

===========================================================================
POINT 4 -- revalidation des 4 mecanismes "meme compte revient"
===========================================================================
- Reset Blueberry : chemin dedie inchange (voir point 2 ci-dessus) --
  jamais touche par la competition. Teste avec bb reset toujours actif
  (comme la reference actuelle).
- Rabais FTMO -10% : le cout de relance FTMO calcule dans la competition
  applique le meme facteur ftmo_discount que l'ancien code (meme fonction
  restart_cost()) -- fonctionne identiquement, teste explicitement avec
  ftmo_discount=True en plus du sweep principal (qui reste sur la config
  adoptee actuelle, sans FTMO-10/Goat Guard, pour comparer a la meme
  reference que Etape F/G).
- Goat Guard GFT : AUCUNE interaction possible par construction -- le test
  use_goat_guard s'evalue AVANT que la branche "broke" ne soit meme
  atteinte (l'annule completement, cf. process_trade_mf / le bloc principal
  ci-dessous, inchange). Un compte GFT en soft-breach reste actif, n'entre
  jamais dans le pool de candidats. Teste explicitement avec
  gft_goat_guard=True en plus du sweep principal.
- Deblocage echelonne (group_funded_count) : EXCLU de la competition par
  construction (point 3 du design ci-dessus) -- verifie par lecture de code
  (allocate_capital() ne touche jamais pending_group_trigger/open_group) ET
  empiriquement via full_structure_month (temps pour completer les 5 firms)
  qui ne doit pas se degrader anormalement dans les resultats.

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

from engine_multiformat import FORMATS, make_acc_mf, process_trade_mf
import etape_e_fleet_integration as ei

YEAR_SECONDS = 365.25 * DAY_SECONDS
MONTH_SECONDS = DAYS_PER_MONTH * DAY_SECONDS
SIX_MONTHS_SECONDS = 6 * MONTH_SECONDS
FIRMS = ("Blueberry", "FTMO", "Fivers", "GFT", "FundedNext")

FTMO_DISCOUNT_FACTOR = 0.90
GOAT_GUARD_SPLIT_DAYS = 30
GOAT_GUARD_SPLIT_FLAT = 0.50

EV_PER_DOLLAR = {"FundedNext": 953.68, "Fivers": 783.39, "GFT": 638.57,
                  "Blueberry": 615.67, "FTMO": 578.03}


def run_one(trades, slot_arrivals, market_data, excluded_map, order, ceiling, seq_grouped, format_by_firm,
            emergency_capital, eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult,
            fongible=False, ftmo_discount=False, gft_goat_guard=False):
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
        accounts_by_group[gname] = accs
        if is_day0:
            active0_cost += sum(a["cost"] for a in accs)

    fleet_unlocked = False
    _init_own_funded = {g for g in ("Blueberry",) if not fmt_by_firm[g]["phases"]}
    state = {"reserve": 0.0, "ever_funded": False, "real_cash_paid": active0_cost, "total_breaks": 0,
             "group_funded_count": len(_init_own_funded), "group_own_funded": set(_init_own_funded),
             "hit_ceiling": False, "emergency_remaining": emergency_capital, "is_paid_cum": 0.0,
             "extra_accounts_opened": {g: 0 for g in ei.GROWTH_FIRMS_EXTRA},
             "tax_breach_count": 0, "tax_breach_total": 0.0, "tax_breach_max": 0.0,
             "tax_breach_concurrent_with_repurchase": 0, "tax_breach_events": [], "_now": 0.0,
             "total_opens": sum(1 for accs in accounts_by_group.values() for a in accs if a["last_open_time"] == 0.0),
             "breaks_within_30d": 0, "breaks_within_60d": 0, "blueberry_resets_used": 0, "gft_soft_breaches": 0}
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
        state["total_opens"] += 1
        if downgrade_active() and acc.get("_gname") == ei.STARTER:
            acc["palier"] = acc["base_palier"]
            acc["cost"] = acc["base_cost"]

    def open_group(gname, is_final):
        for a in accounts_by_group[gname]:
            a["active"] = True
            a["total_fees_paid"] = a["cost"]
            a["last_open_time"] = state["_now"]
            a["_gg_triggered_count"] = 0
            a["_gg_split_until"] = None
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

    def restart_cost(acc, gname):
        if downgrade_active() and gname == ei.STARTER:
            return acc["base_cost"]
        cost = ei.price_for(format_by_firm[gname], acc["palier"])
        if ftmo_discount and gname == "FTMO":
            cost *= FTMO_DISCOUNT_FACTOR
        return cost

    def extra_account_eligible(gname):
        accs = accounts_by_group[gname]
        max_acc = ei.FIRM_MAX_ACCOUNTS.get(gname)
        if max_acc is not None and len(accs) >= max_acc:
            return None
        unit_palier = BASE_PALIER[gname] * ei.EXTRA_ACCOUNT_MULT
        current_capital = sum(a["palier"] for a in accs)
        if current_capital + unit_palier > ei.FIRM_CAPITAL_CAP[gname]:
            return None
        extra_cost = ei.price_for(format_by_firm[gname], unit_palier)
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
        new_acc["_gg_triggered_count"] = 0
        new_acc["_gg_split_until"] = None
        accounts_by_group[gname].append(new_acc)
        state["extra_accounts_opened"][gname] += 1
        state["total_opens"] += 1

    def process_extra_account_baseline(now):
        """Comportement d'origine (ordre fixe par firm) -- utilise seulement si fongible=False."""
        if not fleet_unlocked:
            return
        for gname in ei.GROWTH_FIRMS_EXTRA:
            elig = extra_account_eligible(gname)
            if elig is not None:
                unit_palier, extra_cost = elig
                open_extra_account(gname, unit_palier, extra_cost, now)

    def allocate_capital(now):
        """Competition unifiee (relances + extra-comptes), triee EV/$ decroissant. fongible=True uniquement."""
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
    reserve_min_after_unlock = float("inf")

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]
        state["_now"] = now

        if now <= SIX_MONTHS_SECONDS:
            reserve_min_6mo = min(reserve_min_6mo, state["reserve"])
            if state["total_opens"] > 1:
                reserve_min_after_unlock = min(reserve_min_after_unlock, state["reserve"])

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
            for acc in list(accs):
                if not acc["active"]:
                    continue
                r = fleet_risk if acc["phase"] == "funded" else base_risk
                split_this = GOAT_GUARD_SPLIT_FLAT if (gft_goat_guard and gname == "GFT"
                                                        and acc["_gg_split_until"] is not None
                                                        and now < acc["_gg_split_until"]) else 0.80
                was_challenge = acc["active"] and acc["phase"] == "challenge"
                was_funded = acc["active"] and acc["phase"] == "funded"
                phase_before, idx_before = acc["phase"], acc["phase_index"]
                just_funded = process_trade_mf(acc, trade, now, fmt, state, r, market_data, excluded_map,
                                                split_flat=split_this, reserve_share=reserve_share, cost_override=0.0)

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
                    acc["phase"] = "funded"  # annule le passage en "challenge" fait par process_trade_mf
                    state["gft_soft_breaches"] += 1
                elif broke:
                    state["total_breaks"] += 1
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
                            cost = restart_cost(acc, gname)
                            handle_cost_hybrid(cost, pending_reopen, id(acc),
                                                lambda a=acc, c=cost, f=fmt: reopen_account(a, c, f, skip_to_funded=False))
                        # si fongible=True : ne rien faire ici -- le compte devient un
                        # candidat de allocate_capital(), appele plus bas ce meme slot.
                else:
                    if was_challenge and just_funded and gname not in state["group_own_funded"]:
                        state["group_own_funded"].add(gname)
                        state["group_funded_count"] += 1

        if fongible:
            allocate_capital(now)
        else:
            process_extra_account_baseline(now)
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
              "gft_soft_breaches": state["gft_soft_breaches"],
              "reserve_min_6mo": reserve_min_6mo if reserve_min_6mo != float("inf") else 0.0,
              "reserve_min_after_unlock": (reserve_min_after_unlock if reserve_min_after_unlock != float("inf") else None),
              "final_reserve": state["reserve"],
              "full_structure_month": full_structure_month if full_structure_month is not None else float("nan")}
    for g in FIRMS:
        result[f"active_end_{g}"] = sum(1 for a in accounts_by_group[g] if a["active"])
    return result


def run_propagated(pop, market_data, excluded_map, ceiling, seq_grouped, format_by_firm, emergency,
                    eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult, n_sims, seed,
                    fongible=False, ftmo_discount=False, gft_goat_guard=False):
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
                      fongible=fongible, ftmo_discount=ftmo_discount, gft_goat_guard=gft_goat_guard)
        rows.append(res)
    return pd.DataFrame(rows)


def summarize(df, label, ceiling):
    net = df["final_net_split"] - df["is_paid_cum"]
    year1_neg = df["year1_net_split"] < 0
    pre_mask = df["pre_deblocage"]
    n_pre = (year1_neg & pre_mask).sum()
    n_post = (year1_neg & ~pre_mask).sum()
    break_rate_30d = df["breaks_within_30d"].sum() / df["total_opens"].sum() * 100
    break_rate_60d = df["breaks_within_60d"].sum() / df["total_opens"].sum() * 100
    quasi_frozen = (df["final_reserve"] < 100).mean() * 100
    out = dict(config=label, ceiling=ceiling, n=len(df), profit=net.mean(), ruine=(net < 0).mean() * 100,
               annee1_neg=year1_neg.mean() * 100, annee1_neg_pre=n_pre / len(df) * 100,
               annee1_neg_post=n_post / len(df) * 100, mean_breaks=df["total_breaks"].mean(),
               mean_bb_resets=df["blueberry_resets_used"].mean(),
               break_rate_30d_pct=break_rate_30d, break_rate_60d_pct=break_rate_60d,
               reserve_min_6mo_worst=df["reserve_min_6mo"].min(),
               mean_full_structure_month=df["full_structure_month"].dropna().mean(),
               quasi_frozen_pct=quasi_frozen)
    for g in FIRMS:
        out[f"pct_zero_active_end_{g}"] = (df[f"active_end_{g}"] == 0).mean() * 100
    return out


if __name__ == "__main__":
    t_start = time.time()
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    ceilings_arg = [float(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [1000.0, 3000.0]
    mode = sys.argv[3] if len(sys.argv) > 3 else "screen"  # screen | interaction

    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)
    seq = ei.seq_grouped_multi(1000, 15000, 25000, 25000)
    config = ei.CONFIG_REF
    EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK = 1.25, 1.90, 1.75

    rows = []
    if mode == "screen":
        configs = [("baseline REF (non-fongible)", False, False, False),
                   ("fongible (competition EV/$)", True, False, False)]
    else:  # interaction : verifie FTMO-10/Goat Guard combines a la fongibilite, une seule fois, plafond=1000
        configs = [("fongible + ftmo_discount", True, True, False),
                   ("fongible + gft_goat_guard", True, False, True),
                   ("fongible + ftmo_discount + gft_goat_guard", True, True, True)]
        ceilings_arg = [1000.0]

    for label, fong, ftmo_disc, gg in configs:
        for ceiling in ceilings_arg:
            t0 = time.time()
            df = run_propagated(pop, market_data, excluded_map, ceiling, seq, config, ei.DEFAULT_EMERGENCY,
                                 EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                                 ei.EXTRA_THRESHOLD_MULT, n_sims=n_sims, seed=9999,
                                 fongible=fong, ftmo_discount=ftmo_disc, gft_goat_guard=gg)
            row = summarize(df, label, ceiling)
            rows.append(row)
            zero_str = " ".join(f"{g}={row[f'pct_zero_active_end_{g}']:.1f}%" for g in FIRMS)
            print(f"[{label:35s} plafond={ceiling:.0f}$] profit={row['profit']:+,.0f}$ ruine={row['ruine']:.2f}% "
                  f"annee1<0={row['annee1_neg']:.2f}% (pre={row['annee1_neg_pre']:.2f}% post={row['annee1_neg_post']:.2f}%) "
                  f"casse<=30j={row['break_rate_30d_pct']:.2f}% struct_complete={row['mean_full_structure_month']:.1f}mo "
                  f"quasi_gele={row['quasi_frozen_pct']:.1f}% zero_actif_fin[{zero_str}] ({time.time()-t0:.0f}s)")
            pd.DataFrame(rows).to_csv(f"etape_h_fongibilite_slots_n{n_sims}_{mode}.csv", index=False)

    print(f"\nTermine en {time.time()-t_start:.0f}s.")
