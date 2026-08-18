"""
Etape E, annee1<0, round 3 (08/09) -- famille jamais testee : l'EXPOSITION
SIMULTANEE elle-meme (nombre de comptes supplementaires actifs en meme
temps), pas le risque/seuil/calendrier-ponctuel/cout-unitaire (3 familles
deja epuisees, cf. etape_e_annee1_levers.py et etape_e_annee1_levers2.py --
6 leviers testes, tous neutres ou negatifs, y compris le redemarrage moins
cher qui a AGGRAVE le probleme de +21,5% en accelerant le cycle
casse-restart -- signe que c'est un probleme de VOLUME, pas de cout).

  POINT 2 (plafond dur sur le nombre de comptes supplementaires) : reduit
  le nombre max de comptes SUPPLEMENTAIRES simultanes par firm (FTMO/GFT --
  Blueberry a deja un plafond reel de 3 comptes totaux, non touche ici),
  en dessous du niveau actuel (limite seulement par le plafond de capital
  reel par firm). Teste plusieurs niveaux, PAS de recherche d'un point
  gagnant -- objectif : montrer la frontiere profit/risque complete.

  POINT 3 (cadencement continu) : delai minimum entre deux OUVERTURES de
  comptes supplementaires successives pour une meme firm, applique en
  CONTINU sur toute la duree de la simulation (contrairement a l'etalement
  deja teste, qui ne concernait que le deblocage initial ponctuel).

Copie de etape_e_fleet_integration.run_one, augmentee. N'importe pas
run_one directement.
"""
import random
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
WEEK_SECONDS = 7 * DAY_SECONDS
FIRMS = ("Blueberry", "FTMO", "Fivers", "GFT", "FundedNext")


def run_one(trades, slot_arrivals, market_data, excluded_map, order, ceiling, seq_grouped, format_by_firm,
            emergency_capital, eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult,
            extra_cap_per_firm=None, min_gap_extra_seconds=0.0):
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

    def effective_max_accounts(gname):
        real_cap = ei.FIRM_MAX_ACCOUNTS.get(gname)
        if extra_cap_per_firm is None:
            return real_cap
        computed = ei.N_ACCOUNTS_DAY0[gname] + extra_cap_per_firm
        return computed if real_cap is None else min(real_cap, computed)

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
            a["_ever_funded_before"] = False
            a["last_open_time"] = 0.0 if is_day0 else None
        accounts_by_group[gname] = accs
        if is_day0:
            active0_cost += sum(a["cost"] for a in accs)

    fleet_unlocked = False
    _init_own_funded = {g for g in ("Blueberry",) if not fmt_by_firm[g]["phases"]}
    for gname in _init_own_funded:
        for a in accounts_by_group[gname]:
            a["_ever_funded_before"] = True
    state = {"reserve": 0.0, "ever_funded": False, "real_cash_paid": active0_cost, "total_breaks": 0,
             "group_funded_count": len(_init_own_funded), "group_own_funded": set(_init_own_funded),
             "hit_ceiling": False, "emergency_remaining": emergency_capital, "is_paid_cum": 0.0,
             "extra_accounts_opened": {g: 0 for g in ei.GROWTH_FIRMS_EXTRA},
             "tax_breach_count": 0, "tax_breach_total": 0.0, "tax_breach_max": 0.0,
             "tax_breach_concurrent_with_repurchase": 0, "tax_breach_events": [],
             "_now": 0.0, "total_opens": sum(1 for accs in accounts_by_group.values() for a in accs if a["last_open_time"] == 0.0),
             "breaks_within_30d": 0, "breaks_within_60d": 0,
             "last_extra_open_by_firm": {g: None for g in ei.GROWTH_FIRMS_EXTRA}}
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

    def reopen_account(acc, cost, fmt):
        acc["active"] = True
        acc["total_fees_paid"] += cost
        acc["phase"] = "funded" if not fmt["phases"] else "challenge"
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
            state["total_opens"] += 1
        if not fmt_by_firm[gname]["phases"]:
            mark_group_funded_if_needed(gname)
            for a in accounts_by_group[gname]:
                a["_ever_funded_before"] = True

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
            max_acc = effective_max_accounts(gname)
            if max_acc is not None and len(accs) >= max_acc:
                continue
            last_open = state["last_extra_open_by_firm"][gname]
            if last_open is not None and (now - last_open) < min_gap_extra_seconds:
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
                new_acc["_ever_funded_before"] = False
                new_acc["last_open_time"] = now
                accs.append(new_acc)
                state["extra_accounts_opened"][gname] += 1
                state["total_opens"] += 1
                state["last_extra_open_by_firm"][gname] = now

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
    post_unlock_breaks = 0

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
            for acc in list(accs):
                if not acc["active"]:
                    continue
                r = fleet_risk if acc["phase"] == "funded" else base_risk
                was_challenge = acc["active"] and acc["phase"] == "challenge"
                was_funded = acc["active"] and acc["phase"] == "funded"
                phase_before, idx_before = acc["phase"], acc["phase_index"]
                just_funded = process_trade_mf(acc, trade, now, fmt, state, r, market_data, excluded_map,
                                                split_flat=0.80, reserve_share=reserve_share, cost_override=0.0)

                progressed = (fmt["phases"] and (
                    (acc["phase"] == "challenge" and acc["phase_index"] == idx_before + 1) or
                    (acc["phase"] == "funded" and phase_before == "challenge")))
                reset_happened = (acc["cumulative_since_reset"] == 0.0 and acc["peak_since_reset"] == 0.0
                                  and len(acc["trading_days_since_reset"]) == 0)
                broke = reset_happened and not progressed

                if broke:
                    state["total_breaks"] += 1
                    if was_funded and full_structure_month is not None and now / MONTH_SECONDS > 12:
                        post_unlock_breaks += 1
                    t_since_open = now - acc["last_open_time"] if acc["last_open_time"] is not None else None
                    if t_since_open is not None:
                        if t_since_open <= 30 * 86400:
                            state["breaks_within_30d"] += 1
                        if t_since_open <= 60 * 86400:
                            state["breaks_within_60d"] += 1
                    if downgrade_active() and gname == ei.STARTER:
                        cost = acc["base_cost"]
                    else:
                        cost = ei.price_for(format_by_firm[gname], acc["palier"])
                    acc["active"] = False
                    handle_cost_hybrid(cost, pending_reopen, id(acc), lambda a=acc, c=cost, f=fmt: reopen_account(a, c, f))
                else:
                    if acc["phase"] == "funded":
                        acc["_ever_funded_before"] = True
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

    n_extra_final = sum(state["extra_accounts_opened"].values())

    return {"final_net_split": combined_net(), "is_paid_cum": state["is_paid_cum"],
            "year1_net_split": year1_net_split, "total_breaks": state["total_breaks"],
            "full_structure_month": full_structure_month, "post_unlock_breaks": post_unlock_breaks,
            "total_opens": state["total_opens"], "breaks_within_30d": state["breaks_within_30d"],
            "breaks_within_60d": state["breaks_within_60d"], "n_extra_accounts_opened": n_extra_final}


def run_propagated(pop, market_data, excluded_map, ceiling, seq_grouped, format_by_firm, emergency,
                    eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult, n_sims, seed,
                    extra_cap_per_firm=None, min_gap_extra_seconds=0.0):
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
                      extra_cap_per_firm=extra_cap_per_firm, min_gap_extra_seconds=min_gap_extra_seconds)
        rows.append(res)
    return pd.DataFrame(rows)


def classify_pre_post(df):
    pre = (df["full_structure_month"].isna()) | (df["full_structure_month"] > 12)
    return pre


def summarize(df, label):
    net = df["final_net_split"] - df["is_paid_cum"]
    year1_neg = df["year1_net_split"] < 0
    pre_mask = classify_pre_post(df)
    n_pre = (year1_neg & pre_mask).sum()
    n_post = (year1_neg & ~pre_mask).sum()
    break_rate_30d = df["breaks_within_30d"].sum() / df["total_opens"].sum() * 100
    break_rate_60d = df["breaks_within_60d"].sum() / df["total_opens"].sum() * 100
    return dict(config=label, n=len(df), profit=net.mean(), ruine=(net < 0).mean() * 100,
                annee1_neg_pct=year1_neg.mean() * 100, annee1_neg_pre_pct=n_pre / len(df) * 100,
                annee1_neg_post_pct=n_post / len(df) * 100, mean_breaks=df["total_breaks"].mean(),
                mean_post_unlock_breaks=df["post_unlock_breaks"].mean(),
                mean_n_extra=df["n_extra_accounts_opened"].mean(),
                break_rate_30d_pct=break_rate_30d, break_rate_60d_pct=break_rate_60d)


if __name__ == "__main__":
    import sys
    t_start = time.time()
    part = sys.argv[1] if len(sys.argv) > 1 else "all"
    n_sims = int(sys.argv[2]) if len(sys.argv) > 2 else 300

    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

    CEILING = 1000.0
    EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK = 1.00, 1.90, 1.75
    config = ei.CONFIG_REF
    seq = ei.seq_grouped_multi(1000, 15000, 25000, 25000)

    if part in ("2", "all"):
        print(f"\n{'='*100}\nPOINT 2 -- PLAFOND COMPTES SUPPLEMENTAIRES (n={n_sims})\n{'='*100}")
        rows = []
        for label, cap in [("baseline (non plafonne, cap capital seul)", None),
                            ("cap=4 extra/firm", 4), ("cap=2 extra/firm", 2), ("cap=1 extra/firm", 1)]:
            t0 = time.time()
            df = run_propagated(pop, market_data, excluded_map, CEILING, seq, config, ei.DEFAULT_EMERGENCY,
                                 EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                                 ei.EXTRA_THRESHOLD_MULT, n_sims=n_sims, seed=7000, extra_cap_per_firm=cap)
            row = summarize(df, label)
            rows.append(row)
            print(f"[{label:42s}] profit={row['profit']:+,.0f}$ ruine={row['ruine']:.2f}% "
                  f"annee1<0={row['annee1_neg_pct']:.2f}% (pre={row['annee1_neg_pre_pct']:.2f}% "
                  f"post={row['annee1_neg_post_pct']:.2f}%) n_extra_moy={row['mean_n_extra']:.2f} "
                  f"post_unlock_breaks={row['mean_post_unlock_breaks']:.1f} "
                  f"casse<=30j={row['break_rate_30d_pct']:.2f}% casse<=60j={row['break_rate_60d_pct']:.2f}% "
                  f"({time.time()-t0:.0f}s)")
            pd.DataFrame(rows).to_csv("etape_e_annee1_levers3_point2.csv", index=False)

    if part in ("3", "all"):
        print(f"\n{'='*100}\nPOINT 3 -- CADENCEMENT CONTINU OUVERTURES EXTRA (n={n_sims})\n{'='*100}")
        rows = []
        for label, gap_w in [("baseline (gap=0)", 0), ("gap=1sem", 1), ("gap=2sem", 2), ("gap=3sem", 3)]:
            t0 = time.time()
            df = run_propagated(pop, market_data, excluded_map, CEILING, seq, config, ei.DEFAULT_EMERGENCY,
                                 EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                                 ei.EXTRA_THRESHOLD_MULT, n_sims=n_sims, seed=7000,
                                 min_gap_extra_seconds=gap_w * WEEK_SECONDS)
            row = summarize(df, label)
            rows.append(row)
            print(f"[{label:20s}] profit={row['profit']:+,.0f}$ ruine={row['ruine']:.2f}% "
                  f"annee1<0={row['annee1_neg_pct']:.2f}% (pre={row['annee1_neg_pre_pct']:.2f}% "
                  f"post={row['annee1_neg_post_pct']:.2f}%) n_extra_moy={row['mean_n_extra']:.2f} "
                  f"post_unlock_breaks={row['mean_post_unlock_breaks']:.1f} "
                  f"casse<=30j={row['break_rate_30d_pct']:.2f}% casse<=60j={row['break_rate_60d_pct']:.2f}% "
                  f"({time.time()-t0:.0f}s)")
            pd.DataFrame(rows).to_csv("etape_e_annee1_levers3_point3.csv", index=False)

    print(f"\nTermine en {time.time()-t_start:.0f}s.")
