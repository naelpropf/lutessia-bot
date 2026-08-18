"""
Chantier 2, suite (08/09) : Blueberry-adaptatif avait ete rejete (ruine
bloquee a 14,00% au plafond 1000$, cf. etape_e_chantier2_adaptive_format_
2026-08-09.md) a cause d'un desequilibre economique reel -- le reopen d'un
compte Instant Elite coute 800$ (prix reel, verifie ligne 94-101 et 355-
367 de etape_e_adaptive_format_2026-08-09.py, AUCUN bug : le mauvais cout
2-step 165/330$ n'a jamais ete utilise) contre 165-330$ pour un compte
2-step (downgrade-on-reopen ou reset Blueberry). Le risque flotte actuel
(1,90%) a ete calibre sur l'hypothese implicite que la plupart des casses
sont bon marche a reparer -- pas vrai pour l'instant funding.

3 variantes de protection testees separement (parametres representatifs,
pas un sous-balayage exhaustif -- si un signal apparait, affiner le
sous-parametre serait une etape naturelle avant confirmation n=600) :

  (a) EVAL SYNTHETIQUE : risque reduit a eval_risk (1,25%) pendant les 20
      premiers trades OU les 4 premieres semaines du compte Instant Elite
      (protection levee des que l'UN des deux seuils est atteint).
  (b) RISQUE REDUIT A VIE : 1,50% (au lieu de 1,90%) en permanence pour
      tout compte Blueberry en format instant, pas seulement au demarrage.
  (c) COMBINAISON : (a) pendant la fenetre initiale, puis (b) en
      permanence au lieu de revenir a 1,90%.

Seul Blueberry est concerne (FTMO/GFT/FundedNext restent adaptatifs sans
changement, comme dans le Chantier 2 original). Meme criblage de seuils
{10k/20k/30k/50k/75k/100k$}, n=300.

Copie de etape_e_adaptive_format_2026-08-09.run_one, augmentee. N'importe
pas ce script directement.
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
WEEK_SECONDS = 7 * DAY_SECONDS
FIRMS = ("Blueberry", "FTMO", "Fivers", "GFT", "FundedNext")

SLOW_FMT = ei.CONFIG_REF
FAST_FMT = {"Blueberry": "Blueberry_InstantElite", "FTMO": "FTMO_1Step",
            "GFT": "GFT_InstantGOAT", "FundedNext": "FundedNext_Stellar1Step"}
FIVERS_FIXED_PALIER = ei.FIVERS_PALIER["Fivers_HighStakes"]

N_TRADES_PROTECT = 20
W_WEEKS_PROTECT = 4
INSTANT_LIFETIME_RISK = 1.50


def base_palier(gname):
    if gname == "FundedNext":
        return ei.FUNDEDNEXT_PALIER
    if gname == "Fivers":
        return FIVERS_FIXED_PALIER
    return BASE_PALIER[gname]


def choose_format_key(gname, reserve, blueberry_adaptive, switch_threshold):
    if gname == "Fivers":
        return SLOW_FMT["Fivers"]
    if gname == "Blueberry" and not blueberry_adaptive:
        return SLOW_FMT["Blueberry"]
    return SLOW_FMT[gname] if reserve >= switch_threshold else FAST_FMT[gname]


def run_one(trades, slot_arrivals, market_data, excluded_map, order, ceiling, seq_grouped,
            emergency_capital, eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult,
            blueberry_adaptive, switch_threshold, protection_variant):
    """protection_variant in (None, 'a', 'b', 'c')."""
    accounts_by_group = {g: [] for g in FIRMS}
    active0_cost = 0.0

    bb_fmt_key = choose_format_key("Blueberry", 0.0, blueberry_adaptive, switch_threshold)
    bb_palier = base_palier("Blueberry")
    bb_cost = ei.price_for(bb_fmt_key, bb_palier)
    bb_acc = make_acc_mf(FORMATS[bb_fmt_key], bb_palier, cost=bb_cost, active=True)
    bb_acc["_gname"] = "Blueberry"
    bb_acc["_fmt_key"] = bb_fmt_key
    bb_acc["base_palier"] = bb_palier
    bb_acc["base_cost"] = bb_cost
    bb_acc["_reset_used"] = False
    bb_acc["last_open_time"] = 0.0
    bb_acc["_trades_since_open"] = 0
    accounts_by_group["Blueberry"] = [bb_acc]
    active0_cost += bb_cost

    for gname in ("FTMO", "Fivers", "GFT", "FundedNext"):
        n = ei.N_ACCOUNTS_DAY0[gname]
        accs = []
        for _ in range(n):
            a = make_acc_mf(FORMATS[SLOW_FMT[gname]], base_palier(gname), cost=0.0, active=False)
            a["_gname"] = gname
            a["_fmt_key"] = None
            a["base_palier"] = None
            a["base_cost"] = None
            a["_reset_used"] = False
            a["last_open_time"] = None
            a["_trades_since_open"] = 0
            accs.append(a)
        accounts_by_group[gname] = accs

    fleet_unlocked = False
    state = {"reserve": 0.0, "ever_funded": False, "real_cash_paid": active0_cost, "total_breaks": 0,
             "group_funded_count": 0, "group_own_funded": set(), "hit_ceiling": False,
             "emergency_remaining": emergency_capital, "is_paid_cum": 0.0,
             "extra_accounts_opened": {g: 0 for g in ei.GROWTH_FIRMS_EXTRA},
             "tax_breach_count": 0, "tax_breach_total": 0.0, "tax_breach_max": 0.0,
             "tax_breach_concurrent_with_repurchase": 0, "tax_breach_events": [], "_now": 0.0,
             "total_opens": 1, "breaks_within_30d": 0, "breaks_within_60d": 0, "blueberry_resets_used": 0}
    if not FORMATS[bb_fmt_key]["phases"]:
        state["group_own_funded"].add("Blueberry")
        state["group_funded_count"] += 1
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

    def instant_risk_override(acc, gname, fmt):
        """Retourne le risque a utiliser pour un compte Blueberry en
        format instant sous protection ; None si non concerne (autre
        firm, ou Blueberry en format phase, ou pas de protection)."""
        if gname != "Blueberry" or fmt["phases"] or protection_variant is None:
            return None
        in_window = (acc["_trades_since_open"] < N_TRADES_PROTECT
                     or (state["_now"] - acc["last_open_time"]) < W_WEEKS_PROTECT * WEEK_SECONDS)
        if protection_variant == "a":
            return eval_risk if in_window else fleet_risk
        if protection_variant == "b":
            return INSTANT_LIFETIME_RISK
        if protection_variant == "c":
            return eval_risk if in_window else INSTANT_LIFETIME_RISK
        return None

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

    def reopen_account(acc, cost, skip_to_funded=False):
        fmt = FORMATS[acc["_fmt_key"]]
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
        acc["_trades_since_open"] = 0
        state["total_opens"] += 1
        if downgrade_active() and acc.get("_gname") == "Blueberry":
            acc["palier"] = acc["base_palier"]
            acc["cost"] = acc["base_cost"]

    def open_group(gname, is_final, fmt_key, palier, cost):
        fmt = FORMATS[fmt_key]
        for a in accounts_by_group[gname]:
            a["_fmt_key"] = fmt_key
            a["palier"] = palier
            a["cost"] = cost
            a["base_palier"] = palier
            a["base_cost"] = cost
            a["active"] = True
            a["total_fees_paid"] = cost
            a["phase"] = "funded" if not fmt["phases"] else "challenge"
            a["phase_index"] = 0
            a["cumulative_since_reset"] = 0.0
            a["peak_since_reset"] = 0.0
            a["trading_days_since_reset"] = set()
            a["daily_pnl"] = {}
            a["locked_peak"] = None
            a["eod_peak"] = 0.0
            a["last_day_seen"] = None
            a["last_open_time"] = state["_now"]
            a["_trades_since_open"] = 0
            state["total_opens"] += 1
        if not fmt["phases"]:
            mark_group_funded_if_needed(gname)

    def try_emergency_bootstrap():
        if n_active_accounts() != 0 or emergency_capital <= 0 or state["emergency_remaining"] <= 0:
            return
        bb = accounts_by_group["Blueberry"][0]
        cost = bb["base_cost"] if downgrade_active() else bb["cost"]
        if state["emergency_remaining"] >= cost:
            state["emergency_remaining"] -= cost
            reopen_account(bb, cost)
            pending_reopen[:] = [p for p in pending_reopen if p["key"] != id(bb)]

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
            fmt_key = choose_format_key(gname, state["reserve"], blueberry_adaptive, switch_threshold)
            extra_cost = ei.price_for(fmt_key, unit_palier)
            if state["reserve"] >= extra_threshold_mult * extra_cost:
                state["reserve"] -= extra_cost
                new_acc = make_acc_mf(FORMATS[fmt_key], unit_palier, cost=extra_cost, active=True)
                new_acc["total_fees_paid"] = extra_cost
                new_acc["_gname"] = gname
                new_acc["_fmt_key"] = fmt_key
                new_acc["base_palier"] = unit_palier
                new_acc["base_cost"] = extra_cost
                new_acc["_reset_used"] = False
                new_acc["last_open_time"] = now
                new_acc["_trades_since_open"] = 0
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
            base_risk = gft_eval_risk if gname == "GFT" else eval_risk
            for acc in list(accs):
                if not acc["active"]:
                    continue
                fmt = FORMATS[acc["_fmt_key"]]
                override = instant_risk_override(acc, gname, fmt)
                if override is not None:
                    r = override
                else:
                    r = fleet_risk if acc["phase"] == "funded" else base_risk
                was_challenge = acc["active"] and acc["phase"] == "challenge"
                was_funded = acc["active"] and acc["phase"] == "funded"
                phase_before, idx_before = acc["phase"], acc["phase_index"]
                just_funded = process_trade_mf(acc, trade, now, fmt, state, r, market_data, excluded_map,
                                                split_flat=0.80, reserve_share=reserve_share, cost_override=0.0)
                acc["_trades_since_open"] += 1

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
                    use_bb_reset = (gname == "Blueberry" and was_funded and not acc["_reset_used"] and fmt["phases"])
                    if use_bb_reset:
                        cost = 2.0 * acc["base_cost"]
                        acc["active"] = False
                        acc["_reset_used"] = True
                        state["blueberry_resets_used"] += 1
                        handle_cost_hybrid(cost, pending_reopen, id(acc),
                                            lambda a=acc, c=cost: reopen_account(a, c, skip_to_funded=True))
                    else:
                        if downgrade_active() and gname == "Blueberry":
                            cost = acc["base_cost"]
                        else:
                            cost = ei.price_for(acc["_fmt_key"], acc["palier"])
                        acc["active"] = False
                        handle_cost_hybrid(cost, pending_reopen, id(acc),
                                            lambda a=acc, c=cost: reopen_account(a, c, skip_to_funded=False))
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
                    fmt_key = choose_format_key(gname, state["reserve"], blueberry_adaptive, switch_threshold)
                    palier = base_palier(gname)
                    cost_per_acc = ei.price_for(fmt_key, palier)
                    cost0 = cost_per_acc * len(accounts_by_group[gname])
                    handle_cost_hybrid(cost0, pending_group_open, gname,
                                        lambda g=gname, f=is_final, fk=fmt_key, p=palier, c=cost_per_acc:
                                        open_group(g, f, fk, p, c))
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
            "final_reserve": state["reserve"]}


def run_propagated(pop, market_data, excluded_map, ceiling, seq_grouped, emergency,
                    eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult, n_sims, seed,
                    blueberry_adaptive, switch_threshold, protection_variant):
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
        res = run_one(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, seq_grouped,
                      emergency, eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult,
                      blueberry_adaptive, switch_threshold, protection_variant)
        rows.append(res)
    return pd.DataFrame(rows)


def summarize(df, label):
    net = df["final_net_split"] - df["is_paid_cum"]
    year1_neg = df["year1_net_split"] < 0
    pre_mask = df["pre_deblocage"]
    n_pre = (year1_neg & pre_mask).sum()
    n_post = (year1_neg & ~pre_mask).sum()
    break_rate_30d = df["breaks_within_30d"].sum() / df["total_opens"].sum() * 100
    break_rate_60d = df["breaks_within_60d"].sum() / df["total_opens"].sum() * 100
    quasi_frozen = (df["final_reserve"] < 100).mean() * 100
    return dict(config=label, n=len(df), profit=net.mean(), ruine=(net < 0).mean() * 100,
                annee1_neg=year1_neg.mean() * 100, annee1_neg_pre=n_pre / len(df) * 100,
                annee1_neg_post=n_post / len(df) * 100, mean_breaks=df["total_breaks"].mean(),
                mean_bb_resets=df["blueberry_resets_used"].mean(),
                break_rate_30d_pct=break_rate_30d, break_rate_60d_pct=break_rate_60d,
                quasi_frozen_pct=quasi_frozen)


if __name__ == "__main__":
    t_start = time.time()
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300

    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)
    seq = ei.seq_grouped_multi(1000, 15000, 25000, 25000)
    EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK = 1.25, 1.90, 1.75
    THRESHOLDS = [10000.0, 20000.0, 30000.0, 50000.0, 75000.0, 100000.0]

    rows = []
    for variant, vlabel in [("a", "eval synth (20tr/4sem)"), ("b", f"vie {INSTANT_LIFETIME_RISK}%"),
                             ("c", "combine")]:
        for thresh in THRESHOLDS:
            label = f"variant={vlabel} seuil={thresh/1000:.0f}k"
            for ceiling in (1000.0, 3000.0):
                t0 = time.time()
                df = run_propagated(pop, market_data, excluded_map, ceiling, seq, ei.DEFAULT_EMERGENCY,
                                     EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                                     ei.EXTRA_THRESHOLD_MULT, n_sims=n_sims, seed=13000,
                                     blueberry_adaptive=True, switch_threshold=thresh, protection_variant=variant)
                row = summarize(df, label)
                row["ceiling"] = ceiling
                row["switch_threshold"] = thresh
                row["variant"] = variant
                rows.append(row)
                print(f"[{label} plafond={ceiling:.0f}$] profit={row['profit']:+,.0f}$ ruine={row['ruine']:.2f}% "
                      f"annee1<0={row['annee1_neg']:.2f}% (pre={row['annee1_neg_pre']:.2f}% "
                      f"post={row['annee1_neg_post']:.2f}%) bb_resets={row['mean_bb_resets']:.2f} "
                      f"casse<=30j={row['break_rate_30d_pct']:.2f}% quasi_gele={row['quasi_frozen_pct']:.1f}% "
                      f"({time.time()-t0:.0f}s)")
                pd.DataFrame(rows).to_csv("etape_e_bb_instant_protection_screen.csv", index=False)

    print(f"\nTermine en {time.time()-t_start:.0f}s.")
