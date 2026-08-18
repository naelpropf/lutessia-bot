"""
Etape "edge_circuit_breaker_v2" (08/11) : REOUVERTURE de la piste
coupe-circuit reactif (§2.7 registre_parametres_projet.md, REJETEE
08/09-08/10 -- "signal de mauvaise passe recente = bruit statistique
pur"). Reouverte suite a une preuve concrete nouvelle (pas une
supposition, conforme a la condition de reouverture du §2.7 : "seulement
si un signal MOINS bruite est propose") : §2.37 registre_parametres_
projet.md a identifie une vraie fenetre historique creuse (2022-11-01 ->
2023-01-20, winrate 17,5%/EV -0,466R vs 40,4%/+0,890R global, VERIFIEE
sur donnees reelles, pas un artefact) derriere les 2 runs "effondrement
flotte mature".

Copie de etape_am_deep_dive_negative_runs_2026-08-11.py (moteur
cadence-corrigee identique), UN ajout : `compute_pause_mask()` +
`pause_mask` optionnel dans `run_one()` -- coupe-circuit fleet-wide sur
winrate glissant (meme convention §2.7 : un seul flux de trades brut,
copie par tous les comptes), entree si winrate glissant sur N trades <
X_entry, sortie apres M_recover trades (delai fixe). Pendant la pause,
AUCUN compte ne prend de nouveau trade (bloc de prise de risque saute),
mais flush payout deja du/reouvertures en attente/deblocage de groupe
continuent normalement.

Deux changements herites de etape_am (inchanges) :

1. process_trade_mf_logged() -- COPIE LOCALE de engine_multiformat.
   process_trade_mf (le module partage n'est PAS modifie), seul ajout :
   renvoie aussi le type de breach ("daily"/"max"/None) qui n'etait pas
   expose par la fonction originale. Reutilise directement les helpers
   partages _reset_trackers/_dd_max_breached (purs, aucun risque a les
   reutiliser tels quels).

2. Chaque compte a un identifiant stable acc["_acc_id"] (ex: "GFT_2",
   "Blueberry_extra3"). run_one(..., log_events=True) accumule un
   journal d'evenements (ouverture_challenge/passage_phase/financement/
   casse/flush_payout/reouverture/hit_ceiling_touche) avec solde compte/
   reserve/hit_ceiling/phase pre-post-deblocage a chaque evenement, plus
   pour les casses : ticker, R realise, type de DD franchi, jours depuis
   le dernier flush de CE compte, pending_payout perdu.

⚠️ BUG NOTE (trouve en explorant engine_multiformat.py pour cette tache,
PAS demande explicitement mais signale) : state["total_breaks"] est
incremente DEUX FOIS par casse reelle -- une fois a l'interieur de
process_trade_mf (ligne ~350, inconditionnellement des qu'un breach est
detecte, meme si cost_override=0.0 neutralise son effet cash) ET une
seconde fois au niveau driver dans le bloc `elif broke:`. Les deux
increments correspondent au MEME evenement de casse (reset_happened est
directement cause par le meme appel process_trade_mf). Consequence :
tout chiffre "nombre de casses" derive de state["total_breaks"]/
result["total_breaks"] dans TOUS les scripts du projet (y compris
etape_ac_breaks_by_firm, §2.24 du registre) est gonfle ~2x. N'affecte
AUCUN chiffre economique (profit/reserve/ruine) -- cost_override=0.0
neutralise le volet cash du doublon, seul le compteur brut est faux. Ce
script compte les casses reelles via les EVENEMENTS "casse" du journal
(un par appel process_trade_mf_logged qui detecte un breach), pas via
total_breaks.

N'importe pas ce script directement (convention du projet).
"""
import json
import os
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
PAYOUT_CYCLE_DAYS_FIRST = {"Blueberry": 14, "GFT": 3, "Fivers": 14}
PAYOUT_CYCLE_DAYS_SUBSEQUENT = {"Blueberry": 14, "GFT": 1.5, "Fivers": 14}

LOG_DIR = "deep_dive_logs"


def payout_cycle_days(gname, first_payout_done):
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
    """Copie de engine_multiformat.process_trade_mf -- logique rigoureusement
    identique, seul ajout : renvoie (just_funded, breach_type) au lieu de
    just_funded seul. Ne modifie PAS le module partage."""
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


def compute_pause_mask(raw_trades, N, X_entry, M_recover):
    """Coupe-circuit fleet-wide sur le signal brut (meme convention que
    l'ancien §2.7 : un seul flux de trades, copie par tous les comptes).
    Fenetre glissante des N derniers outcome_r (sans lookahead -- winrate
    calcule sur trades[i-N:i], jamais sur le trade i lui-meme). Entree :
    winrate glissant < X_entry. Sortie : M_recover trades ecoules depuis
    l'entree (delai fixe, pas de condition de winrate au retour -- variante
    la plus simple des deux conditions disjonctives evoquees)."""
    n = len(raw_trades)
    is_win = [1 if t["outcome_r"] > 0 else 0 for t in raw_trades]
    paused = [False] * n
    state_paused = False
    exit_at = None
    episodes = []
    ep_start = None
    for i in range(n):
        if not state_paused and i >= N:
            wr = sum(is_win[i - N:i]) / N
            if wr < X_entry:
                state_paused = True
                exit_at = i + M_recover
                ep_start = i
        if state_paused:
            paused[i] = True
            if i + 1 >= exit_at:
                state_paused = False
                episodes.append((ep_start, i))
    if state_paused:
        episodes.append((ep_start, n - 1))
    return paused, episodes


def run_one(trades, slot_arrivals, market_data, excluded_map, order, ceiling, seq_grouped, format_by_firm,
            emergency_capital, eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult,
            b_entry_frac=None, b_reduction=None, pre_unlock_only=False,
            ftmo_discount=False, gft_goat_guard=False, payout_cycle=False, log_events=False, pause_mask=None):
    fmt_by_firm = {g: FORMATS[k] for g, k in format_by_firm.items()}
    event_log = [] if log_events else None
    acc_id_counter = {g: 0 for g in FIRMS}

    def next_acc_id(gname):
        i = acc_id_counter[gname]
        acc_id_counter[gname] += 1
        return f"{gname}_{i}"

    def acc_balance(acc):
        return acc["palier"] + acc.get("cumulative_since_reset", 0.0)

    def log_event(now, gname, acc, ev_type, extra=None):
        if event_log is None:
            return
        rec = {"jour_simulation": round(now / 86400.0, 2), "firm": gname,
               "compte_id": acc.get("_acc_id", "?"), "type_evenement": ev_type,
               "solde_compte": round(acc_balance(acc), 2), "reserve": round(state["reserve"], 2),
               "hit_ceiling": state["hit_ceiling"], "phase_deblocage": "post" if fleet_unlocked else "pre"}
        if extra:
            rec.update(extra)
        event_log.append(rec)

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
            a["_acc_id"] = next_acc_id(gname)
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
             "forfeit_events_pre": {g: 0 for g in PAYOUT_CYCLE_FIRMS}, "forfeit_events_post": {g: 0 for g in PAYOUT_CYCLE_FIRMS}}

    for gname in FIRMS:
        if accounts_by_group[gname][0]["active"]:
            for a in accounts_by_group[gname]:
                log_event(0.0, gname, a, "financement" if not fmt_by_firm[gname]["phases"] else "ouverture_challenge")

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
            if not state["hit_ceiling"] and event_log is not None:
                event_log.append({"jour_simulation": round(state["_now"] / 86400.0, 2), "firm": None,
                                   "compte_id": None, "type_evenement": "hit_ceiling_touche",
                                   "solde_compte": None, "reserve": round(state["reserve"], 2),
                                   "hit_ceiling": True, "phase_deblocage": "post" if fleet_unlocked else "pre"})
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
            extra_cost = ei.price_for(format_by_firm[gname], unit_palier)
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
                new_acc["_dd_oscillations"] = 0
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

        if pause_mask is not None and pause_mask[slot_idx]:
            # Coupe-circuit actif : ce trade n'est pris par AUCUN compte
            # (pause fleet-wide) -- saute le bloc de prise de risque, mais
            # laisse le reste (flush payout deja du, reouvertures en
            # attente, deblocage de groupe) suivre son cours normalement.
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
            continue

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
                    state["funding_delays"].append((now - acc["last_open_time"]) / 86400.0)
                    log_event(now, gname, acc, "financement")

                if use_payout_cycle and acc["active"] and acc["last_payout_time"] is not None \
                        and now - acc["last_payout_time"] >= payout_cycle_days(gname, acc["_first_payout_done"]) * 86400:
                    flushed_amount = acc["pending_payout"]
                    acc["total_funded_pnl"] += acc["pending_payout"]
                    if acc["pending_payout"] > 0:
                        state["reserve"] += acc["pending_payout"] * reserve_share
                        log_event(now, gname, acc, "flush_payout", {"montant_verse": round(flushed_amount, 2)})
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
                    state["gft_soft_breaches"] += 1
                elif broke:
                    state["total_breaks"] += 1
                    jours_depuis_flush = ((now - acc["last_payout_time"]) / 86400.0
                                           if acc["last_payout_time"] is not None else None)
                    pending_avant_casse = acc["pending_payout"]
                    forfeited = 0.0
                    if use_payout_cycle and acc["pending_payout"] != 0.0:
                        forfeited = max(0.0, acc["pending_payout"])
                        bucket = state["forfeited_post"] if fleet_unlocked else state["forfeited_pre"]
                        events = state["forfeit_events_post"] if fleet_unlocked else state["forfeit_events_pre"]
                        if forfeited > 0:
                            bucket[gname] += forfeited
                            events[gname] += 1
                        acc["pending_payout"] = 0.0
                    log_event(now, gname, acc, "casse", {
                        "ticker": trade.get("ticker"), "r_realise": round(trade.get("outcome_r", 0.0), 3),
                        "type_dd": breach_type, "jours_depuis_dernier_flush": round(jours_depuis_flush, 2)
                        if jours_depuis_flush is not None else None,
                        "pending_payout_perdu": round(forfeited, 2), "pending_payout_avant_casse": round(pending_avant_casse, 2)})
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
                        if downgrade_active() and gname == ei.STARTER:
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
              "final_reserve": state["reserve"], "hit_ceiling": state["hit_ceiling"], "event_log": event_log}
    for g in PAYOUT_CYCLE_FIRMS:
        result[f"forfeited_pre_{g}"] = state["forfeited_pre"][g]
        result[f"forfeited_post_{g}"] = state["forfeited_post"][g]
        result[f"forfeit_events_pre_{g}"] = state["forfeit_events_pre"][g]
        result[f"forfeit_events_post_{g}"] = state["forfeit_events_post"][g]
    return result


def run_and_extract(pop, market_data, excluded_map, ceiling, seq_grouped, format_by_firm, emergency,
                     eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult, n_sims, seed,
                     b_entry_frac=None, b_reduction=None, pre_unlock_only=False,
                     ftmo_discount=False, gft_goat_guard=False, payout_cycle=False):
    """Comme run_propagated, mais n'accumule PAS 600 journaux en memoire --
    decide au fil de l'eau si le run est negatif et ecrit son journal sur
    disque immediatement, sinon le jette."""
    rng_wr = random.Random(seed)
    rng_boot = random.Random(seed + 1)
    rows = []
    n_negative = 0
    for run_idx in range(n_sims):
        wr_draw = rng_wr.betavariate(ei.ALPHA_POST, ei.BETA_POST)
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_draw, 1.0, False, random.Random(rng_boot.random()))
        block_seconds = 2 * 30 * DAY_SECONDS
        blocks = build_blocks(trades, slot_arrivals, block_seconds)
        target_duration = slot_arrivals[-1]
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot, target_duration)
        order = list(range(len(raw_trades)))
        res = run_one(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, seq_grouped, format_by_firm,
                      emergency, eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult,
                      b_entry_frac=b_entry_frac, b_reduction=b_reduction, pre_unlock_only=pre_unlock_only,
                      ftmo_discount=ftmo_discount, gft_goat_guard=gft_goat_guard, payout_cycle=payout_cycle,
                      log_events=True)
        net = res["final_net_split"] - res["is_paid_cum"]
        event_log = res.pop("event_log")
        if net < 0:
            n_negative += 1
            run_id = f"ceiling{int(ceiling)}_run{run_idx}"
            os.makedirs(LOG_DIR, exist_ok=True)
            with open(os.path.join(LOG_DIR, f"{run_id}.json"), "w", encoding="utf-8") as fh:
                json.dump({"run_id": run_id, "ceiling": ceiling, "net_final": net, "events": event_log}, fh,
                          ensure_ascii=False, indent=1)
        rows.append(res)
    print(f"[extraction] plafond={ceiling:.0f}$ : {n_negative}/{n_sims} runs negatifs, journaux ecrits dans {LOG_DIR}/")
    return pd.DataFrame(rows)


def _common_setup():
    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)
    seq = ei.seq_grouped_multi(1000, 15000, 25000, 25000)
    config = ei.CONFIG_REF
    return pop, market_data, excluded_map, seq, config


CB_GRID = [
    # (N, X_entry winrate, M_recover trades)
    (15, 0.15, 10), (15, 0.15, 20), (15, 0.20, 10), (15, 0.20, 20),
    (20, 0.18, 10), (20, 0.18, 20), (20, 0.25, 10), (20, 0.25, 20),
]
BAD_WINDOW_START = pd.Timestamp("2022-11-01")
BAD_WINDOW_END = pd.Timestamp("2023-01-20")


def mode_point2(ceiling):
    """Point 2 : rejoue run_idx=202 (meme technique que deep_dive_replay --
    RNG avance sequentiellement, iterations 0..201 sans capture, iteration
    202 capturee) et teste la grille CB_GRID dessus."""
    pop, market_data, excluded_map, seq, config = _common_setup()
    EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK = 1.25, 1.90, 1.75
    rng_wr = random.Random(9999)
    rng_boot = random.Random(9999 + 1)
    raw_trades = raw_slots = None
    for run_idx in range(203):
        wr_draw = rng_wr.betavariate(ei.ALPHA_POST, ei.BETA_POST)
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_draw, 1.0, False, random.Random(rng_boot.random()))
        block_seconds = 2 * 30 * DAY_SECONDS
        blocks = build_blocks(trades, slot_arrivals, block_seconds)
        target_duration = slot_arrivals[-1]
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot, target_duration)

    order = list(range(len(raw_trades)))

    def run_with_mask(mask):
        return run_one(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, seq, config,
                        ei.DEFAULT_EMERGENCY, EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                        ei.EXTRA_THRESHOLD_MULT, b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True,
                        ftmo_discount=True, gft_goat_guard=True, payout_cycle=True, log_events=True, pause_mask=mask)

    baseline = run_with_mask(None)
    base_casses = sum(1 for e in baseline["event_log"] if e["type_evenement"] == "casse")
    print(f"[baseline, ceiling={ceiling:.0f}$] casses={base_casses} net_final={baseline['final_net_split']-baseline['is_paid_cum']:+.0f}$")

    rows = []
    for N, X, M in CB_GRID:
        mask, episodes = compute_pause_mask(raw_trades, N, X, M)
        n_paused_trades = sum(mask)
        # episode overlaps the real bad window if ANY trade inside it has a
        # historical date within [BAD_WINDOW_START, BAD_WINDOW_END]
        n_true_positive_ep, n_false_positive_ep = 0, 0
        for (s, e) in episodes:
            dates = [raw_trades[j]["date"] for j in range(s, e + 1)]
            overlaps = any(BAD_WINDOW_START <= d <= BAD_WINDOW_END for d in dates)
            if overlaps:
                n_true_positive_ep += 1
            else:
                n_false_positive_ep += 1
        res = run_with_mask(mask)
        n_casses = sum(1 for ev in res["event_log"] if ev["type_evenement"] == "casse")
        net = res["final_net_split"] - res["is_paid_cum"]
        row = dict(N=N, X_entry=X, M_recover=M, n_episodes=len(episodes), n_tp_episodes=n_true_positive_ep,
                   n_fp_episodes=n_false_positive_ep, n_trades_skipped=n_paused_trades,
                   casses_run202=n_casses, casses_evitees=base_casses - n_casses, net_final=net)
        rows.append(row)
        print(f"N={N:2d} X={X:.2f} M={M:2d} : episodes={len(episodes)} (TP={n_true_positive_ep}/FP={n_false_positive_ep}) "
              f"trades_skippes={n_paused_trades} casses={n_casses} (evitees={base_casses-n_casses}) net_final={net:+.0f}$")

    out = pd.DataFrame(rows)
    out.to_csv(f"edge_circuit_breaker_run202_ceiling{int(ceiling)}.csv", index=False)
    return out


def mode_point3(best_configs, n_sims=300):
    """Point 3 : reteste les configs les plus prometteuses (issues du point 2)
    sur l'ENSEMBLE n=300, deux plafonds, cout EV vs Run C (baseline sans
    coupe-circuit, deja mesuree : 32,67%/32,67% annee1<0)."""
    pop, market_data, excluded_map, seq, config = _common_setup()
    EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK = 1.25, 1.90, 1.75
    rows = []
    for ceiling in (1000.0, 3000.0):
        for (N, X, M) in best_configs:
            rng_wr = random.Random(9999)
            rng_boot = random.Random(9999 + 1)
            recs = []
            t0 = time.time()
            for run_idx in range(n_sims):
                wr_draw = rng_wr.betavariate(ei.ALPHA_POST, ei.BETA_POST)
                trades, slot_arrivals = eng.build_flexible_population(pop, wr_draw, 1.0, False, random.Random(rng_boot.random()))
                block_seconds = 2 * 30 * DAY_SECONDS
                blocks = build_blocks(trades, slot_arrivals, block_seconds)
                target_duration = slot_arrivals[-1]
                raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot, target_duration)
                mask, _ = compute_pause_mask(raw_trades, N, X, M)
                order = list(range(len(raw_trades)))
                res = run_one(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, seq, config,
                              ei.DEFAULT_EMERGENCY, EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                              ei.EXTRA_THRESHOLD_MULT, b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True,
                              ftmo_discount=True, gft_goat_guard=True, payout_cycle=True, log_events=False, pause_mask=mask)
                recs.append(res)
            df = pd.DataFrame(recs)
            net = df["final_net_split"] - df["is_paid_cum"]
            year1_neg = df["year1_net_split"] < 0
            row = dict(ceiling=ceiling, N=N, X_entry=X, M_recover=M, n=len(df),
                       profit_moyen=net.mean(), profit_median=net.median(),
                       solde_negatif_annee4=(net < 0).mean() * 100, hit_ceiling_pct=df["hit_ceiling"].mean() * 100,
                       annee1_neg=year1_neg.mean() * 100)
            rows.append(row)
            print(f"[ceiling={ceiling:.0f}$ N={N} X={X:.2f} M={M}] profit_moyen={row['profit_moyen']:+,.0f}$ "
                  f"solde_negatif_annee4={row['solde_negatif_annee4']:.2f}% hit_ceiling={row['hit_ceiling_pct']:.2f}% "
                  f"annee1<0={row['annee1_neg']:.2f}% ({time.time()-t0:.0f}s)")
    out = pd.DataFrame(rows)
    out.to_csv(f"edge_circuit_breaker_fleet_n{n_sims}.csv", index=False)
    return out


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "point2"
    t_start = time.time()
    import rr_threshold_test as rrt
    print(f"[verif] HIST_PATH (rr_threshold_test) = {rrt.HIST_PATH}")
    print(f"[verif] FIRM_MAX_ACCOUNTS Blueberry = {ei.FIRM_MAX_ACCOUNTS['Blueberry']}, "
          f"FIRM_CAPITAL_CAP Blueberry = {ei.FIRM_CAPITAL_CAP['Blueberry']:,.0f}$")

    if mode == "point2":
        ceiling = float(sys.argv[2]) if len(sys.argv) > 2 else 1000.0
        mode_point2(ceiling)
    elif mode == "point3":
        # configs par defaut, a ecraser via argv si besoin : "N,X,M;N,X,M;..."
        if len(sys.argv) > 2:
            best_configs = [tuple(float(x) if i > 0 else int(x) for i, x in enumerate(c.split(",")))
                             for c in sys.argv[2].split(";")]
        else:
            best_configs = [(20, 0.18, 20)]
        n_sims = int(sys.argv[3]) if len(sys.argv) > 3 else 300
        mode_point3(best_configs, n_sims=n_sims)

    print(f"\nTermine en {time.time()-t_start:.0f}s.")
