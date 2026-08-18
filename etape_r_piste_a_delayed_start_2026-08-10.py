"""
Etape R (08/10 nuit) : test du seuil de demarrage differe du 2e starter,
cible directement le mecanisme de ruine BB+GFT jour 0 confirme par trace a
l'Etape O (registre 2.11) -- epuisement de marge de tresorerie initiale
(BB+GFT depense 2,5x plus avant le 1er financement, 4,67% des runs ne
financent jamais, 96,9% des ruines n'ont jamais complete la structure a 5
firms).

IDEE TESTEE : au lieu d'ouvrir GFT en parallele de Blueberry DES le jour 0
(cout jour 0 cumule 453$, cf etape_f), attendre un petit signal de stabilite
du 1er compte (Blueberry) avant d'engager le cout du 2e -- soit une duree de
survie sans casse (7/14/21j), soit un montant de reserve deja accumule
(100/250/500$). Objectif : recuperer une partie du benefice de
diversification de l'Etape F (BB+GFT bat solo a 3000$) sans payer le meme
cout jour 0 qui, sous plafond serre, epuise trop vite la marge de
tresorerie partagee.

Copie de etape_f_bootstrap_parallele_2026-08-09.py, generalise avec un
"active_starters" MUTABLE (au lieu du tuple STARTERS fixe) : Blueberry
demarre toujours actif au jour 0 ; GFT demarre soit (a) au jour 0 aussi
(mode "day0", = combo BB_GFT de l'Etape F, recalcule ici pour instrumentation
identique), (b) jamais en starter, uniquement via le declenchement normal du
palier de reserve 25000$ deja existant dans seq_grouped_multi (mode "none",
= solo_BB de l'Etape F), ou (c) des qu'un declencheur DEDIE et bien plus bas
se declenche (mode "days"/X ou "reserve"/Y) -- ce declencheur est SEPARE du
palier normal GFT 25000$ (qui reste actif en parallele et devient un no-op
une fois GFT deja actif, comportement deja verifie a l'Etape F).

Instrumentation ajoutee (mêmes metriques que etape_o_ruin_mechanism, pour
comparaison directe du verrou de tresorerie) :
- cash_at_fleet_first_funded : real_cash_paid au moment du tout premier
  financement de la flotte (n'importe quelle firm).
- ever_funded : la flotte a-t-elle finance ne serait-ce qu'un compte sur
  toute la duree du run (depuis engine_multiformat.state["ever_funded"]).

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
FIRST_STARTER = "Blueberry"
SECOND_STARTER = "GFT"

# trigger modes: ("none",) -> jamais en starter dedie (solo_BB) ; None -> jour0 (combo BB_GFT)
# ("days", X) -> declenche apres X jours de survie sans casse de Blueberry
# ("reserve", Y) -> declenche des que state["reserve"] >= Y$
TRIGGER_CONFIGS = {
    "solo_BB": ("none",),
    "BB_GFT_day0": None,
    "delay_7j": ("days", 7),
    "delay_14j": ("days", 14),
    "delay_21j": ("days", 21),
    "delay_100usd": ("reserve", 100.0),
    "delay_250usd": ("reserve", 250.0),
    "delay_500usd": ("reserve", 500.0),
}


def run_one(trades, slot_arrivals, market_data, excluded_map, order, ceiling, seq_grouped, format_by_firm,
            emergency_capital, eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult,
            trigger=None):
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

    day0_starters = {FIRST_STARTER}
    if trigger is None:
        day0_starters.add(SECOND_STARTER)
    active_starters = set(day0_starters)
    delayed_pending = (trigger is not None and trigger[0] in ("days", "reserve"))
    delayed_triggered = not delayed_pending

    accounts_by_group = {}
    active0_cost = 0.0
    for gname in FIRMS:
        is_starter = gname in day0_starters
        palier, cost = base_palier_cost(gname)
        fmt = fmt_by_firm[gname]
        n_accs = ei.N_ACCOUNTS_DAY0[gname]
        accs = []
        for i in range(n_accs):
            active_i = is_starter and i == 0
            acc = make_acc_mf(fmt, palier, cost=cost, active=active_i)
            acc["_gname"] = gname
            acc["base_palier"] = palier
            acc["base_cost"] = cost
            acc["_reset_used"] = False
            acc["last_open_time"] = 0.0 if active_i else None
            accs.append(acc)
        accounts_by_group[gname] = accs
        if is_starter:
            active0_cost += accs[0]["cost"]

    fleet_unlocked = False
    _init_own_funded = {g for g in day0_starters if not fmt_by_firm[g]["phases"]}
    state = {"reserve": 0.0, "ever_funded": False, "real_cash_paid": active0_cost, "total_breaks": 0,
             "group_funded_count": len(_init_own_funded), "group_own_funded": set(_init_own_funded),
             "hit_ceiling": False, "emergency_remaining": emergency_capital, "is_paid_cum": 0.0,
             "extra_accounts_opened": {g: 0 for g in ei.GROWTH_FIRMS_EXTRA},
             "tax_breach_count": 0, "tax_breach_total": 0.0, "tax_breach_max": 0.0,
             "tax_breach_concurrent_with_repurchase": 0, "tax_breach_events": [], "_now": 0.0,
             "total_opens": sum(1 for accs in accounts_by_group.values() for a in accs if a["last_open_time"] == 0.0),
             "breaks_within_30d": 0, "breaks_within_60d": 0, "blueberry_resets_used": 0,
             "cash_at_fleet_first_funded": None}
    pending_group_trigger = [(names, trig, thresh, final) for names, trig, thresh, final in seq_grouped if trig != "day0"]
    pending_reopen = []
    pending_group_open = []
    pending_delayed = []

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
        if downgrade_active() and acc.get("_gname") in active_starters:
            acc["palier"] = acc["base_palier"]
            acc["cost"] = acc["base_cost"]

    def open_group(gname, is_final):
        for a in accounts_by_group[gname]:
            if a["active"]:
                continue
            a["active"] = True
            a["total_fees_paid"] = a["cost"]
            a["last_open_time"] = state["_now"]
            state["total_opens"] += 1
        if not fmt_by_firm[gname]["phases"]:
            mark_group_funded_if_needed(gname)

    def try_emergency_bootstrap():
        if n_active_accounts() != 0 or emergency_capital <= 0 or state["emergency_remaining"] <= 0:
            return
        candidates = [accounts_by_group[g][0] for g in active_starters if not accounts_by_group[g][0]["active"]]
        candidates.sort(key=lambda a: a["base_cost"] if downgrade_active() else a["cost"])
        for acc in candidates:
            cost = acc["base_cost"] if downgrade_active() else acc["cost"]
            if state["emergency_remaining"] < cost:
                break
            state["emergency_remaining"] -= cost
            reopen_account(acc, cost, fmt_by_firm[acc["_gname"]])
            pending_reopen[:] = [p for p in pending_reopen if p["key"] != id(acc)]

    def try_delayed_trigger(now):
        nonlocal delayed_triggered
        if delayed_triggered:
            return
        kind, val = trigger
        fired = False
        if kind == "days":
            bb_acc0 = accounts_by_group[FIRST_STARTER][0]
            if bb_acc0["active"] and bb_acc0["last_open_time"] is not None and \
                    (now - bb_acc0["last_open_time"]) >= val * DAY_SECONDS:
                fired = True
        elif kind == "reserve":
            if state["reserve"] >= val:
                fired = True
        if not fired:
            return
        delayed_triggered = True
        gft_acc0 = accounts_by_group[SECOND_STARTER][0]

        def _activate():
            gft_acc0["active"] = True
            gft_acc0["total_fees_paid"] = gft_acc0["cost"]
            gft_acc0["last_open_time"] = state["_now"]
            state["total_opens"] += 1
            active_starters.add(SECOND_STARTER)

        handle_cost_hybrid(gft_acc0["cost"], pending_delayed, "gft_delayed_start", _activate)

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
                new_acc["base_palier"] = unit_palier
                new_acc["base_cost"] = extra_cost
                new_acc["_reset_used"] = False
                new_acc["last_open_time"] = now
                accs.append(new_acc)
                state["extra_accounts_opened"][gname] += 1
                state["total_opens"] += 1

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
                was_challenge = acc["active"] and acc["phase"] == "challenge"
                was_funded = acc["active"] and acc["phase"] == "funded"
                phase_before, idx_before = acc["phase"], acc["phase_index"]
                just_funded = process_trade_mf(acc, trade, now, fmt, state, r, market_data, excluded_map,
                                                split_flat=0.80, reserve_share=reserve_share, cost_override=0.0)

                if just_funded and state["cash_at_fleet_first_funded"] is None:
                    state["cash_at_fleet_first_funded"] = state["real_cash_paid"]

                progressed = (fmt["phases"] and (
                    (acc["phase"] == "challenge" and acc["phase_index"] == idx_before + 1) or
                    (acc["phase"] == "funded" and phase_before == "challenge")))
                reset_happened = (acc["cumulative_since_reset"] == 0.0 and acc["peak_since_reset"] == 0.0
                                  and len(acc["trading_days_since_reset"]) == 0)
                broke = reset_happened and not progressed

                if broke:
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
                        if downgrade_active() and gname in active_starters:
                            cost = acc["base_cost"]
                        else:
                            cost = ei.price_for(format_by_firm[gname], acc["palier"])
                        acc["active"] = False
                        handle_cost_hybrid(cost, pending_reopen, id(acc),
                                            lambda a=acc, c=cost, f=fmt: reopen_account(a, c, f, skip_to_funded=False))
                else:
                    if was_challenge and just_funded and gname not in state["group_own_funded"]:
                        state["group_own_funded"].add(gname)
                        state["group_funded_count"] += 1

        if delayed_pending:
            try_delayed_trigger(now)
        process_extra_account(now)
        process_pending(pending_reopen)
        process_pending(pending_group_open)
        process_pending(pending_delayed)
        try_emergency_bootstrap()

        still_pending = []
        for group_names, trig, thresh, is_final in pending_group_trigger:
            _, n_req = trig
            if state["group_funded_count"] >= n_req and state["reserve"] >= thresh:
                for gname in group_names:
                    cost0 = sum(a["cost"] for a in accounts_by_group[gname] if not a["active"])
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
    return {"final_net_split": combined_net(), "is_paid_cum": state["is_paid_cum"],
            "year1_net_split": year1_net_split, "total_breaks": state["total_breaks"], "pre_deblocage": pre,
            "total_opens": state["total_opens"], "breaks_within_30d": state["breaks_within_30d"],
            "breaks_within_60d": state["breaks_within_60d"], "blueberry_resets_used": state["blueberry_resets_used"],
            "reserve_min_6mo": reserve_min_6mo if reserve_min_6mo != float("inf") else 0.0,
            "reserve_min_after_unlock": (reserve_min_after_unlock if reserve_min_after_unlock != float("inf") else None),
            "final_reserve": state["reserve"],
            "full_structure_month": full_structure_month if full_structure_month is not None else float("nan"),
            "active0_cost": active0_cost,
            "cash_at_fleet_first_funded": (state["cash_at_fleet_first_funded"]
                                            if state["cash_at_fleet_first_funded"] is not None else float("nan")),
            "ever_funded": state["ever_funded"]}


def run_propagated(pop, market_data, excluded_map, ceiling, seq_grouped, format_by_firm, emergency,
                    eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult, n_sims, seed,
                    trigger=None):
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
                      trigger=trigger)
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
    never_funded = (~df["ever_funded"]).mean() * 100
    return dict(config=label, ceiling=ceiling, n=len(df), active0_cost=df["active0_cost"].iloc[0],
                profit=net.mean(), ruine=(net < 0).mean() * 100,
                annee1_neg=year1_neg.mean() * 100, annee1_neg_pre=n_pre / len(df) * 100,
                annee1_neg_post=n_post / len(df) * 100, mean_breaks=df["total_breaks"].mean(),
                mean_bb_resets=df["blueberry_resets_used"].mean(),
                break_rate_30d_pct=break_rate_30d, break_rate_60d_pct=break_rate_60d,
                reserve_min_6mo_worst=df["reserve_min_6mo"].min(),
                mean_full_structure_month=df["full_structure_month"].dropna().mean(),
                quasi_frozen_pct=quasi_frozen,
                cash_at_first_funded_mean=df["cash_at_fleet_first_funded"].dropna().mean(),
                never_funded_pct=never_funded)


if __name__ == "__main__":
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    combos_arg = sys.argv[2].split(",") if len(sys.argv) > 2 else list(TRIGGER_CONFIGS.keys())
    ceilings_arg = [float(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else [1000.0, 3000.0]

    t_start = time.time()
    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)
    seq = ei.seq_grouped_multi(1000, 15000, 25000, 25000)
    config = ei.CONFIG_REF
    EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK = 1.25, 1.90, 1.75

    rows = []
    for combo_name in combos_arg:
        trigger = TRIGGER_CONFIGS[combo_name]
        for ceiling in ceilings_arg:
            t0 = time.time()
            df = run_propagated(pop, market_data, excluded_map, ceiling, seq, config, ei.DEFAULT_EMERGENCY,
                                 EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                                 ei.EXTRA_THRESHOLD_MULT, n_sims=n_sims, seed=9999, trigger=trigger)
            row = summarize(df, combo_name, ceiling)
            rows.append(row)
            print(f"[{combo_name:14s} plafond={ceiling:.0f}$ cout_j0={row['active0_cost']:.0f}$] "
                  f"profit={row['profit']:+,.0f}$ ruine={row['ruine']:.2f}% "
                  f"annee1<0={row['annee1_neg']:.2f}% (pre={row['annee1_neg_pre']:.2f}% post={row['annee1_neg_post']:.2f}%) "
                  f"casse<=30j={row['break_rate_30d_pct']:.2f}% struct_complete={row['mean_full_structure_month']:.1f}mo "
                  f"jamais_finance={row['never_funded_pct']:.2f}% cash@1erfin={row['cash_at_first_funded_mean']:.0f}$ "
                  f"quasi_gele={row['quasi_frozen_pct']:.1f}% "
                  f"({time.time()-t0:.0f}s)")
            pd.DataFrame(rows).to_csv(f"etape_r_piste_a_delayed_start_n{n_sims}.csv", index=False)

    print(f"\nTermine en {time.time()-t_start:.0f}s.")
