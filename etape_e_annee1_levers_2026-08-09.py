"""
Etape E, suite du diagnostic annee1<0 (08/09) : recherche de leviers separes
pour les deux composantes du probleme (voir etape_e_diagnostic_annee1_
2026-08-09.md) :

  - VOLET PRE-DEBLOCAGE (57% des cas annee1<0) : deux leviers 08/08 jamais
    retestes sous le moteur integre actuel (eval=1,00%/flotte=1,90%) :
      (a) seuil de deblocage FTMO encore reduit (deja tres bas a 1000$ dans
          le REF actuel -- teste des valeurs plus basses)
      (b) etalement calendaire minimal entre ouvertures successives de
          groupe (1-4 semaines), independant du seuil de reserve -- pour
          eviter que plusieurs comptes fraichement ouverts (sans historique)
          se retrouvent actifs simultanement.

  - VOLET POST-DEBLOCAGE (43% des cas, mode d'echec nouveau) : caracterise
    d'abord (quelle firm casse un compte deja finance, apres le mois de
    structure complete, dans les runs annee1<0 post-deblocage), puis teste
    une rampe de risque recalibree (RAMP_RISK < 1,90%, valeurs 1,50/1,70%)
    appliquee UNIQUEMENT lors d'un restart post-financement (pas en eval
    initiale) -- contrairement a la rampe globale du 08/09 (RAMP_RISK=2,0%,
    invalidee car appliquee partout et superieure au risque flotte courant).

Copie de etape_e_fleet_integration.run_one (comme etape_e_cascade_check.py),
augmentee d'une instrumentation supplementaire. N'importe pas run_one
directement pour eviter de modifier ce fichier ou etape_e_fleet_integration.py.
"""
import random
import time
from collections import defaultdict

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
            min_gap_seconds=0.0, ramp_risk=None, ramp_n=5):
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
            a["_ever_funded_before"] = False
            a["_pending_restart_ramp"] = False
            a["_ramp_active"] = False
            a["_ramp_count"] = 0
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
             "tax_breach_concurrent_with_repurchase": 0, "tax_breach_events": [],
             "last_group_open_time": 0.0}
    pending_group_trigger = [(names, trig, thresh, final) for names, trig, thresh, final in seq_grouped if trig != "day0"]
    pending_reopen = []
    pending_group_open = []

    # Marque directement "funded" les formats instant funding actifs des le
    # jour 0 (deja finance a la creation, aucune transition detectable).
    for gname in _init_own_funded:
        for a in accounts_by_group[gname]:
            a["_ever_funded_before"] = True

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

    def reopen_account(acc, cost, fmt, was_funded_before_break):
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
        if downgrade_active() and acc.get("_gname") == ei.STARTER:
            acc["palier"] = acc["base_palier"]
            acc["cost"] = acc["base_cost"]
        if ramp_risk is not None and was_funded_before_break:
            if not fmt["phases"]:
                acc["_ramp_active"] = True
                acc["_ramp_count"] = 0
            else:
                acc["_pending_restart_ramp"] = True

    def open_group(gname, is_final):
        state["last_group_open_time"] = state["_now"]
        for a in accounts_by_group[gname]:
            a["active"] = True
            a["total_fees_paid"] = a["cost"]
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
            reopen_account(bb_acc, cost, fmt_by_firm[ei.STARTER], was_funded_before_break=bb_acc["_ever_funded_before"])
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
                new_acc["base_palier"] = unit_palier
                new_acc["base_cost"] = extra_cost
                new_acc["_ever_funded_before"] = False
                new_acc["_pending_restart_ramp"] = False
                new_acc["_ramp_active"] = False
                new_acc["_ramp_count"] = 0
                accs.append(new_acc)
                state["extra_accounts_opened"][gname] += 1

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
    post_unlock_funded_breaks_by_firm = defaultdict(int)
    state["_now"] = 0.0

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
                if acc["phase"] == "funded":
                    r = ramp_risk if (ramp_risk is not None and acc["_ramp_active"]) else fleet_risk
                else:
                    r = base_risk
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

                acc_became_funded = fmt["phases"] and phase_before == "challenge" and acc["phase"] == "funded"

                if acc["_ramp_active"]:
                    acc["_ramp_count"] += 1
                    if acc["_ramp_count"] >= ramp_n:
                        acc["_ramp_active"] = False

                if broke:
                    state["total_breaks"] += 1
                    if was_funded and full_structure_month is not None and now / MONTH_SECONDS > 12:
                        post_unlock_funded_breaks_by_firm[gname] += 1
                    if downgrade_active() and gname == ei.STARTER:
                        cost = acc["base_cost"]
                    else:
                        cost = ei.price_for(format_by_firm[gname], acc["palier"])
                    acc["active"] = False
                    was_funded_before_break = acc["_ever_funded_before"]
                    acc["_ramp_active"] = False
                    acc["_pending_restart_ramp"] = False
                    handle_cost_hybrid(cost, pending_reopen, id(acc),
                                        lambda a=acc, c=cost, f=fmt, wf=was_funded_before_break:
                                        reopen_account(a, c, f, wf))
                else:
                    if acc["phase"] == "funded":
                        acc["_ever_funded_before"] = True
                    if acc_became_funded and acc["_pending_restart_ramp"]:
                        acc["_pending_restart_ramp"] = False
                        acc["_ramp_active"] = True
                        acc["_ramp_count"] = 0
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
            gap_ok = (now - state["last_group_open_time"]) >= min_gap_seconds
            if state["group_funded_count"] >= n_req and state["reserve"] >= thresh and gap_ok:
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

    row = {"final_net_split": combined_net(), "is_paid_cum": state["is_paid_cum"],
           "year1_net_split": year1_net_split, "total_breaks": state["total_breaks"],
           "full_structure_month": full_structure_month}
    for g in FIRMS:
        row[f"post_unlock_funded_breaks_{g}"] = post_unlock_funded_breaks_by_firm.get(g, 0)
    return row


def run_propagated(pop, market_data, excluded_map, ceiling, seq_grouped, format_by_firm, emergency,
                    eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult, n_sims, seed,
                    min_gap_seconds=0.0, ramp_risk=None, ramp_n=5):
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
                      min_gap_seconds=min_gap_seconds, ramp_risk=ramp_risk, ramp_n=ramp_n)
        rows.append(res)
    return pd.DataFrame(rows)


def classify_pre_post(df):
    pre = (df["full_structure_month"].isna()) | (df["full_structure_month"] > 12)
    return pre


def summarize(df, label):
    net = df["final_net_split"] - df["is_paid_cum"]
    year1_neg = df["year1_net_split"] < 0
    pre_mask = classify_pre_post(df)
    n_year1_neg = year1_neg.sum()
    n_pre = (year1_neg & pre_mask).sum()
    n_post = (year1_neg & ~pre_mask).sum()
    row = dict(config=label, n=len(df), profit=net.mean(), ruine=(net < 0).mean() * 100,
               annee1_neg_pct=year1_neg.mean() * 100,
               annee1_neg_pre_pct=n_pre / len(df) * 100,
               annee1_neg_post_pct=n_post / len(df) * 100,
               mean_breaks=df["total_breaks"].mean())
    return row


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

    if part in ("1", "all"):
        print(f"\n{'='*100}\nVOLET 1 -- PRE-DEBLOCAGE (n={n_sims})\n{'='*100}")
        rows = []
        variants = [("baseline (ftmo=1000$, gap=0)", 1000.0, 0.0)]
        for t in (500.0, 250.0, 0.0):
            variants.append((f"ftmo_threshold={t:.0f}$", t, 0.0))
        for w in (1, 2, 4):
            variants.append((f"gap={w}sem", 1000.0, w * WEEK_SECONDS))
        for label, ftmo_thresh, gap in variants:
            seq = ei.seq_grouped_multi(ftmo_thresh, 15000, 25000, 25000)
            t0 = time.time()
            df = run_propagated(pop, market_data, excluded_map, CEILING, seq, config, ei.DEFAULT_EMERGENCY,
                                 EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                                 ei.EXTRA_THRESHOLD_MULT, n_sims=n_sims, seed=5000, min_gap_seconds=gap)
            row = summarize(df, label)
            rows.append(row)
            print(f"[{label:28s}] profit={row['profit']:+,.0f}$ ruine={row['ruine']:.2f}% "
                  f"annee1<0={row['annee1_neg_pct']:.2f}% (pre={row['annee1_neg_pre_pct']:.2f}% "
                  f"post={row['annee1_neg_post_pct']:.2f}%) breaks={row['mean_breaks']:.0f} "
                  f"({time.time()-t0:.0f}s)")
            pd.DataFrame(rows).to_csv("etape_e_annee1_levers_volet1.csv", index=False)

    if part in ("2char", "all"):
        print(f"\n{'='*100}\nVOLET 2 -- CARACTERISATION POST-DEBLOCAGE (baseline, n={n_sims})\n{'='*100}")
        seq = ei.seq_grouped_multi(1000, 15000, 25000, 25000)
        t0 = time.time()
        df = run_propagated(pop, market_data, excluded_map, CEILING, seq, config, ei.DEFAULT_EMERGENCY,
                             EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                             ei.EXTRA_THRESHOLD_MULT, n_sims=n_sims, seed=5000, min_gap_seconds=0.0, ramp_risk=None)
        df.to_csv("etape_e_annee1_levers_volet2_baseline_raw.csv", index=False)
        year1_neg = df["year1_net_split"] < 0
        pre_mask = classify_pre_post(df)
        post_neg = df[year1_neg & ~pre_mask]
        print(f"n annee1<0 post-deblocage = {len(post_neg)} / {len(df)} ({len(post_neg)/len(df)*100:.2f}%)")
        for g in FIRMS:
            col = f"post_unlock_funded_breaks_{g}"
            n_runs_with_break = (post_neg[col] > 0).sum()
            total_breaks = post_neg[col].sum()
            print(f"  {g:12s} : {n_runs_with_break}/{len(post_neg)} runs post-deblocage-negatifs ont >=1 casse "
                  f"financee post-structure ({n_runs_with_break/max(1,len(post_neg))*100:.1f}%), "
                  f"total casses={total_breaks}")
        print(f"({time.time()-t0:.0f}s)")

    if part in ("2lever", "all"):
        print(f"\n{'='*100}\nVOLET 2 -- LEVIER RAMPE CIBLEE RESTART (n={n_sims})\n{'='*100}")
        seq = ei.seq_grouped_multi(1000, 15000, 25000, 25000)
        rows = []
        for label, ramp_risk in [("baseline (aucune rampe)", None), ("ramp_risk=1.50%", 1.50), ("ramp_risk=1.70%", 1.70)]:
            t0 = time.time()
            df = run_propagated(pop, market_data, excluded_map, CEILING, seq, config, ei.DEFAULT_EMERGENCY,
                                 EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                                 ei.EXTRA_THRESHOLD_MULT, n_sims=n_sims, seed=5000, min_gap_seconds=0.0,
                                 ramp_risk=ramp_risk, ramp_n=5)
            row = summarize(df, label)
            rows.append(row)
            print(f"[{label:28s}] profit={row['profit']:+,.0f}$ ruine={row['ruine']:.2f}% "
                  f"annee1<0={row['annee1_neg_pct']:.2f}% (pre={row['annee1_neg_pre_pct']:.2f}% "
                  f"post={row['annee1_neg_post_pct']:.2f}%) breaks={row['mean_breaks']:.0f} "
                  f"({time.time()-t0:.0f}s)")
            pd.DataFrame(rows).to_csv("etape_e_annee1_levers_volet2_lever.csv", index=False)

    print(f"\nTermine en {time.time()-t_start:.0f}s.")
