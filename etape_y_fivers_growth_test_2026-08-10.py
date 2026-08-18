"""
Etape Y (08/10 nuit, suite 9) : test d'ajout de Fivers (The5%ers) au
mecanisme "compte supplementaire" (GROWTH_FIRMS_EXTRA), dont les valeurs
FIRM_CAPITAL_CAP["Fivers"]=500000/FIRM_MAX_ACCOUNTS["Fivers"]=5 existent
deja dans etape_e_fleet_integration.py mais n'ont jamais ete utilisees
(Fivers absent de GROWTH_FIRMS_EXTRA=("Blueberry","FTMO","GFT")).

Contexte (recherche memoire, 1 phrase) : The5%ers concentrait ~75% du
risque de tresorerie personnelle pire-cas pre-immunite dans l'ancien
moteur (DD journalier 3% plus strict que FTMO/Blueberry 5%,
project_preimmunity_5ers_delay_2026-08-06) -- insight generalise depuis
dans le deblocage echelonne actuel (Fivers debloque a reserve>=15000$,
apres FTMO/Blueberry). Copytrade deja verifie non-bloquant (confirme
utilisateur), pas resouleve ici.

IMPORTANT -- gap d'implementation decouvert en ecrivant ce test : le
palier de base de Fivers n'est PAS dans BASE_PALIER (dict cle par firm,
n'a pas d'entree "Fivers" -- corrected_scaling_mechanism.py:56), il vit
dans FIVERS_PALIER (cle par FORMAT, etape_e_fleet_integration.py:133).
process_extra_account() generique aurait leve un KeyError tel quel --
gere ici par un cas special local (extra_unit_palier()), copie de la
logique deja utilisee par base_palier_cost() dans ce meme fichier pour
l'ouverture initiale.

Cette meme special-case revele un fait arithmetique simple avant meme de
lancer une simulation : capital initial Fivers = 4 comptes x 100 000$
(High Stakes) = 400 000$, cap agrege = 500 000$ -> marge = 100 000$.
Unite d'extra-compte (meme convention 2x que Blueberry/FTMO/GFT) =
2x100 000$ = 200 000$ > 100 000$ de marge -> le cap CAPITAL a lui seul
bloque tout extra-compte Fivers, quelle que soit la reserve disponible.
Le cap NOMBRE (5, donc 4+1 max) est encore plus restrictif dans l'absolu
mais n'est meme pas la contrainte active. A verifier empiriquement
plutot que supposer (ci-dessous), mais l'arithmetique seule predit un
effet nul ou quasi nul.

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
            b_entry_frac=None, b_reduction=None, pre_unlock_only=False,
            ftmo_discount=False, gft_goat_guard=False, growth_firms=("Blueberry", "FTMO", "GFT")):
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

    def extra_unit_palier(gname):
        if gname == "Fivers":
            return ei.FIVERS_PALIER[format_by_firm["Fivers"]] * ei.EXTRA_ACCOUNT_MULT
        return BASE_PALIER[gname] * ei.EXTRA_ACCOUNT_MULT

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
        accounts_by_group[gname] = accs
        if is_day0:
            active0_cost += sum(a["cost"] for a in accs)

    fleet_unlocked = False
    _init_own_funded = {g for g in ("Blueberry",) if not fmt_by_firm[g]["phases"]}
    state = {"reserve": 0.0, "ever_funded": False, "real_cash_paid": active0_cost, "total_breaks": 0,
             "group_funded_count": len(_init_own_funded), "group_own_funded": set(_init_own_funded),
             "hit_ceiling": False, "emergency_remaining": emergency_capital, "is_paid_cum": 0.0,
             "extra_accounts_opened": {g: 0 for g in growth_firms},
             "tax_breach_count": 0, "tax_breach_total": 0.0, "tax_breach_max": 0.0,
             "tax_breach_concurrent_with_repurchase": 0, "tax_breach_events": [], "_now": 0.0,
             "total_opens": sum(1 for accs in accounts_by_group.values() for a in accs if a["last_open_time"] == 0.0),
             "breaks_within_30d": 0, "breaks_within_60d": 0, "blueberry_resets_used": 0,
             "dd_reduced_obs": 0, "dd_total_obs": 0, "funding_delays": [], "gft_soft_breaches": 0,
             "breaks_fivers": 0, "reserve_min_ever": 0.0}
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
        for gname in growth_firms:
            accs = accounts_by_group[gname]
            max_acc = ei.FIRM_MAX_ACCOUNTS.get(gname)
            if max_acc is not None and len(accs) >= max_acc:
                continue
            unit_palier = extra_unit_palier(gname)
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

    full_structure_month = None
    year1_net_split = None
    reserve_min_6mo = float("inf")

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]
        state["_now"] = now

        if now <= SIX_MONTHS_SECONDS:
            reserve_min_6mo = min(reserve_min_6mo, state["reserve"])
        state["reserve_min_ever"] = min(state["reserve_min_ever"], state["reserve"])

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
                base_r = fleet_risk if acc["phase"] == "funded" else base_risk
                pdef = _current_phase(fmt, acc)
                r = effective_risk(acc, pdef, base_r)
                was_challenge = acc["active"] and acc["phase"] == "challenge"
                was_funded = acc["active"] and acc["phase"] == "funded"
                phase_before, idx_before = acc["phase"], acc["phase_index"]
                split_this = GOAT_GUARD_SPLIT_FLAT if (gft_goat_guard and gname == "GFT"
                                                        and acc["_gg_split_until"] is not None
                                                        and now < acc["_gg_split_until"]) else 0.80
                just_funded = process_trade_mf(acc, trade, now, fmt, state, r, market_data, excluded_map,
                                                split_flat=split_this, reserve_share=reserve_share, cost_override=0.0)

                if just_funded and acc["last_open_time"] is not None:
                    state["funding_delays"].append((now - acc["last_open_time"]) / 86400.0)

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
                    if gname == "Fivers":
                        state["breaks_fivers"] += 1
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
              "reserve_min_ever": state["reserve_min_ever"],
              "final_reserve": state["reserve"],
              "breaks_fivers": state["breaks_fivers"],
              "fivers_extra_opened": state["extra_accounts_opened"].get("Fivers", 0)}
    return result


def run_propagated(pop, market_data, excluded_map, ceiling, seq_grouped, format_by_firm, emergency,
                    eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult, n_sims, seed,
                    b_entry_frac=None, b_reduction=None, pre_unlock_only=False,
                    ftmo_discount=False, gft_goat_guard=False, growth_firms=("Blueberry", "FTMO", "GFT")):
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
                      b_entry_frac=b_entry_frac, b_reduction=b_reduction, pre_unlock_only=pre_unlock_only,
                      ftmo_discount=ftmo_discount, gft_goat_guard=gft_goat_guard, growth_firms=growth_firms)
        rows.append(res)
    return pd.DataFrame(rows)


def summarize(df, label, ceiling):
    net = df["final_net_split"] - df["is_paid_cum"]
    ruine_mask = net < 0
    year1_neg = df["year1_net_split"] < 0
    pre_mask = df["pre_deblocage"]
    n_pre = (year1_neg & pre_mask).sum()
    n_post = (year1_neg & ~pre_mask).sum()
    break_rate_30d = df["breaks_within_30d"].sum() / df["total_opens"].sum() * 100
    quasi_frozen = (df["final_reserve"] < 100).mean() * 100
    n_ruin = ruine_mask.sum()
    fivers_in_ruin = ((df["breaks_fivers"] > 0) & ruine_mask).sum()
    pct_ruin_with_fivers_break = (fivers_in_ruin / n_ruin * 100) if n_ruin else float("nan")
    return dict(config=label, ceiling=ceiling, n=len(df), profit=net.mean(), ruine=ruine_mask.mean() * 100,
                annee1_neg=year1_neg.mean() * 100, annee1_neg_pre=n_pre / len(df) * 100,
                annee1_neg_post=n_post / len(df) * 100, break_rate_30d_pct=break_rate_30d,
                quasi_frozen_pct=quasi_frozen,
                reserve_min_6mo_worst=df["reserve_min_6mo"].min(),
                reserve_min_ever_worst=df["reserve_min_ever"].min(),
                mean_fivers_extra=df["fivers_extra_opened"].mean(),
                pct_ruin_with_fivers_break=pct_ruin_with_fivers_break,
                n_ruin=n_ruin)


if __name__ == "__main__":
    t_start = time.time()
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    ceilings_arg = [float(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [1000.0, 3000.0]

    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)
    seq = ei.seq_grouped_multi(1000, 15000, 25000, 25000)
    config = ei.CONFIG_REF
    EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK = 1.25, 1.90, 1.75

    configs = [
        ("REF_V2_combine (baseline, sans Fivers extra)", ("Blueberry", "FTMO", "GFT")),
        ("REF_V2_combine + Fivers extra", ("Blueberry", "FTMO", "GFT", "Fivers")),
    ]

    rows = []
    for label, growth_firms in configs:
        for ceiling in ceilings_arg:
            t0 = time.time()
            df = run_propagated(pop, market_data, excluded_map, ceiling, seq, config, ei.DEFAULT_EMERGENCY,
                                 EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                                 ei.EXTRA_THRESHOLD_MULT, n_sims=n_sims, seed=9999,
                                 b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True,
                                 ftmo_discount=True, gft_goat_guard=True, growth_firms=growth_firms)
            row = summarize(df, label, ceiling)
            rows.append(row)
            print(f"[{label:38s} plafond={ceiling:.0f}$] profit={row['profit']:+,.0f}$ ruine={row['ruine']:.2f}% "
                  f"annee1<0={row['annee1_neg']:.2f}% (pre={row['annee1_neg_pre']:.2f}%) "
                  f"casse<=30j={row['break_rate_30d_pct']:.2f}% "
                  f"fivers_extra_moy={row['mean_fivers_extra']:.2f} "
                  f"pct_ruine_avec_casse_fivers={row['pct_ruin_with_fivers_break']:.1f}% (n_ruine={row['n_ruin']}) "
                  f"reserve_min_ever(pire)={row['reserve_min_ever_worst']:,.0f}$ "
                  f"({time.time()-t0:.0f}s)")
            pd.DataFrame(rows).to_csv(f"etape_y_fivers_growth_n{n_sims}.csv", index=False)

    print(f"\nTermine en {time.time()-t_start:.0f}s.")
