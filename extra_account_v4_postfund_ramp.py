"""
Session 08/08 (suite) -- Etape 2 de la demande : retester le fix
trades_taken (rampe post-financement dediee, RAMP_N trades a RAMP_RISK
apres CHAQUE evenement de financement, initial ou apres reouverture) sous
la config finale v4 VERROUILLEE (extra_account_v4_multi.py : mecanisme
"compte supplementaire" deplafonne, flotte=2.75%, eval=2.25%/GFT=1.75%).

Meme logique de rampe que postfunding_ramp_test.py (trades_since_funding
reinitialise a 0 a chaque passage en phase "funded", RAMP_RISK applique
tant que trades_since_funding < RAMP_N, sinon risque flotte normal), sur
l'ancienne base (flotte=2.5%, 1 extra/firm) -- ici reportee sur le moteur
v4 (deplafonne, flotte=2.75%). Garde aussi l'instrumentation diagnostique
de l'Etape 1 (extra_account_v4_year1_diagnosis.py) pour mesurer l'effet
specifique sur le deficit moyen de la categorie A.
"""
import random
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
from point123_startingfirm_optimization import GROUP_DEFS
from point_liquidity_rules import RAMP_RISK, RAMP_N, TARGET_RISK, CORR_TH, DAY_SECONDS
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from split_tax_model import compute_is, handle_tax_payment, IS_THRESHOLD_ACOMPTE, Q_OFFSETS_DAYS, \
    SOLDE_OFFSET_DAYS, ACOMPTE_FRACTION
from corrected_scaling_mechanism import FEE_RATIO, BASE_PALIER
from scaling_simulation import CHALLENGE_COST_FTMO
from extra_account_v4_multi import (SEQ_GROUPED, STARTER, DEFAULT_RESERVE, DEFAULT_EMERGENCY, SPLIT_FLAT,
                                     FINAL_RESERVE_SHARE, FINAL_EVAL_RISK, FINAL_FLEET_RISK, FINAL_GFT_EVAL_RISK,
                                     GROWTH_FIRMS_EXTRA, FUNDEDNEXT_FIXED_PALIER, FUNDEDNEXT_FIXED_COST,
                                     EXTRA_THRESHOLD_MULT, FIRM_CAPITAL_CAP, FIRM_MAX_ACCOUNTS, EXTRA_UNIT_PALIER,
                                     make_growth_acc, cost_for_extra)

ALPHA_POST, BETA_POST = 260, 388
YEAR_SECONDS = 365.25 * DAY_SECONDS
MONTH_SECONDS = DAYS_PER_MONTH * DAY_SECONDS


def run_one(trades, slot_arrivals, market_data, excluded_map, order, ceiling, min_reserve_for_unlock,
            emergency_capital, target_risk_override, eval_risk_override, gft_eval_risk_override,
            reserve_share, extra_threshold_mult, postfund_ramp):
    accounts_by_group = {}
    active0_cost = 0.0
    for group_names, trigger in SEQ_GROUPED:
        for gname in group_names:
            gdef = GROUP_DEFS[gname]
            is_day0 = trigger == "day0"
            if gdef["kind"] == "fivers":
                accs = [eng.make_acc(eng.PALIER_5ERS, eng.SUMMER_COST, active=is_day0) for _ in range(gdef["n_accounts"])]
            elif gname == "FundedNext":
                accs = [make_growth_acc(FUNDEDNEXT_FIXED_PALIER, FUNDEDNEXT_FIXED_COST, active=is_day0)]
            else:
                accs = [make_growth_acc(BASE_PALIER[gname], round(BASE_PALIER[gname] * FEE_RATIO), active=is_day0)
                        for _ in range(gdef["n_accounts"])]
            for a in accs:
                a["_gname"] = gname
                a["ever_funded_self"] = False
                a["trades_since_funding"] = 10**9  # jamais finance -> pas de rampe post-financement
            accounts_by_group[gname] = accs
            if is_day0:
                active0_cost += sum(a["cost"] for a in accs)

    extra_growth_firms = list(GROWTH_FIRMS_EXTRA)
    target_risk = target_risk_override if target_risk_override is not None else TARGET_RISK
    fleet_unlocked = False
    state = {"reserve": 0.0, "ever_funded": False, "real_cash_paid": active0_cost, "total_breaks": 0,
             "group_funded_count": 0, "group_own_funded": set(), "hit_ceiling": False,
             "emergency_remaining": emergency_capital, "is_paid_cum": 0.0,
             "tax_breach_count": 0, "tax_breach_total": 0.0, "tax_breach_max": 0.0,
             "tax_breach_concurrent_with_repurchase": 0, "tax_breach_events": [],
             "extra_accounts_opened": {g: 0 for g in extra_growth_firms},
             # --- tracking diagnostic Etape 1 ---
             "starter_prefund_fees": 0.0, "fleet_unlock_cost": 0.0, "extra_account_open_cost": 0.0,
             "postfund_break_net_cost": 0.0}
    pending_group_trigger = [(names, trig) for names, trig in SEQ_GROUPED if trig != "day0"]
    pending_reopen = []
    pending_group_open = []

    def combined_net():
        return sum(a["total_funded_pnl"] - a["total_fees_paid"] for accs in accounts_by_group.values() for a in accs)

    def n_active_accounts():
        return sum(1 for accs in accounts_by_group.values() for a in accs if a["active"])

    def downgrade_active():
        return not fleet_unlocked

    def cost_for_palier(gname, palier):
        if gname == "Fivers":
            return None
        if gname == "FundedNext":
            return FUNDEDNEXT_FIXED_COST
        return round(palier * FEE_RATIO)

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

    def reopen_account(acc, cost):
        acc["active"] = True
        acc["total_fees_paid"] += cost
        acc["phase"] = "challenge"
        acc["cumulative_since_reset"] = 0.0
        acc["peak_since_reset"] = 0.0
        acc["trading_days_since_reset"] = set()
        acc["daily_pnl"] = {}
        if downgrade_active() and acc.get("_gname") == STARTER:
            acc["palier"] = acc["base_palier"]
            acc["cost"] = acc["base_cost"]

    def open_group(gname):
        cost0 = sum(a["cost"] for a in accounts_by_group[gname])
        state["fleet_unlock_cost"] += cost0
        for a in accounts_by_group[gname]:
            a["active"] = True
            a["total_fees_paid"] = a["cost"]

    def try_emergency_bootstrap():
        if n_active_accounts() != 0 or emergency_capital <= 0 or state["emergency_remaining"] <= 0:
            return
        bb_acc = accounts_by_group[STARTER][0]
        cost = bb_acc["base_cost"] if downgrade_active() else bb_acc["cost"]
        if state["emergency_remaining"] >= cost:
            state["emergency_remaining"] -= cost
            reopen_account(bb_acc, cost)
            pending_reopen[:] = [p for p in pending_reopen if p["key"] != id(bb_acc)]

    def process_trade(acc, trade, now, daily_loss_pct, gname, cost_override=None):
        if not acc["active"]:
            return False
        close_time = now + trade["hold_seconds"]
        acc["open_positions"] = [(t, c) for (t, c) in acc["open_positions"] if c > now]
        if len(acc["open_positions"]) >= eng.MAX_POSITIONS:
            return False
        if any(t in excluded_map[trade["ticker"]] for (t, _) in acc["open_positions"]):
            return False

        if acc["phase"] == "challenge":
            if gname == "GFT" and gft_eval_risk_override is not None:
                current_risk = gft_eval_risk_override
            elif eval_risk_override is not None:
                current_risk = eval_risk_override
            else:
                current_risk = RAMP_RISK if acc["trades_taken"] < RAMP_N else target_risk
        else:
            if postfund_ramp and acc["trades_since_funding"] < RAMP_N:
                current_risk = RAMP_RISK
            else:
                current_risk = RAMP_RISK if acc["trades_taken"] < RAMP_N else target_risk
        eff_risk, _ = eng.feasible_risk_pct(trade["ticker"], trade["sl_distance"], acc["palier"], current_risk, market_data)
        risk_amount = eff_risk / 100 * acc["palier"]
        pnl = trade["outcome_r"] * risk_amount

        acc["open_positions"].append((trade["ticker"], close_time))
        acc["cumulative_since_reset"] += pnl
        acc["peak_since_reset"] = max(acc["peak_since_reset"], acc["cumulative_since_reset"])
        acc["trading_days_since_reset"].add(int(now // 86400))
        acc["trades_taken"] += 1
        if acc["phase"] == "funded":
            acc["trades_since_funding"] += 1
        close_day = int(close_time // 86400)
        acc["daily_pnl"][close_day] = acc["daily_pnl"].get(close_day, 0.0) + pnl

        if acc["phase"] == "funded":
            net_pnl = pnl * SPLIT_FLAT if pnl > 0 else pnl
            acc["total_funded_pnl"] += net_pnl
            if net_pnl > 0:
                state["reserve"] += net_pnl * reserve_share

        trailing_dd = acc["peak_since_reset"] - acc["cumulative_since_reset"]
        daily_dd = -acc["daily_pnl"][close_day]
        broke = (trailing_dd >= eng.BREAK_DD_PCT / 100 * acc["palier"] or daily_dd >= daily_loss_pct / 100 * acc["palier"])

        if broke:
            state["total_breaks"] += 1
            if downgrade_active() and gname == STARTER:
                cost = acc["base_cost"]
            elif gname == "Fivers":
                cost = cost_override
            elif gname in ("FTMO", "GFT"):
                cost = cost_for_extra(gname, acc["palier"]) if acc["palier"] == 100000 else cost_for_palier(gname, acc["palier"])
            else:
                cost = cost_for_palier(gname, acc["palier"])
            if gname == STARTER and not acc["ever_funded_self"]:
                state["starter_prefund_fees"] += cost
            if acc["ever_funded_self"]:
                net_before = acc["total_funded_pnl"] - acc["total_fees_paid"]
                state["postfund_break_net_cost"] += max(0.0, cost - max(0.0, net_before))
            acc["active"] = False
            handle_cost_hybrid(cost, pending_reopen, id(acc), lambda a=acc, c=cost: reopen_account(a, c))
            return False

        if (acc["phase"] == "challenge" and acc["cumulative_since_reset"] >= eng.CHALLENGE_TARGET_PCT / 100 * acc["palier"]
                and len(acc["trading_days_since_reset"]) >= eng.MIN_TRADING_DAYS):
            acc["phase"] = "funded"
            acc["trades_since_funding"] = 0
            state["ever_funded"] = True
            acc["ever_funded_self"] = True
            acc["cumulative_since_reset"] = 0.0
            acc["peak_since_reset"] = 0.0
            acc["trading_days_since_reset"] = set()
            return True
        return False

    def process_extra_account(now):
        if not fleet_unlocked:
            return
        for gname in extra_growth_firms:
            accs = accounts_by_group[gname]
            max_acc = FIRM_MAX_ACCOUNTS.get(gname)
            if max_acc is not None and len(accs) >= max_acc:
                continue
            unit_palier = EXTRA_UNIT_PALIER[gname]
            current_capital = sum(a["palier"] for a in accs)
            if current_capital + unit_palier > FIRM_CAPITAL_CAP[gname]:
                continue
            if gname in ("FTMO", "GFT"):
                extra_cost = cost_for_extra(gname, unit_palier)
            else:
                extra_cost = round(unit_palier * FEE_RATIO)
            if state["reserve"] >= extra_threshold_mult * extra_cost:
                state["reserve"] -= extra_cost
                state["extra_account_open_cost"] += extra_cost
                new_acc = make_growth_acc(unit_palier, extra_cost, active=True)
                new_acc["total_fees_paid"] = extra_cost
                new_acc["_gname"] = gname
                new_acc["ever_funded_self"] = False
                new_acc["trades_since_funding"] = 10**9
                accs.append(new_acc)
                state["extra_accounts_opened"][gname] += 1

    def structure_complete():
        for g in ("Blueberry", "FTMO", "Fivers", "GFT", "FundedNext"):
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
    reserve_hit_30k_month = None
    year1_net_split = None
    year1_snapshot = {}
    catchup_month = None
    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]

        if year1_net_split is None and now >= YEAR_SECONDS:
            year1_net_split = combined_net()
            year1_snapshot = dict(n_active=n_active_accounts(), fleet_unlocked=fleet_unlocked,
                                   reserve=state["reserve"], starter_prefund_fees=state["starter_prefund_fees"],
                                   fleet_unlock_cost=state["fleet_unlock_cost"],
                                   extra_account_open_cost=state["extra_account_open_cost"],
                                   postfund_break_net_cost=state["postfund_break_net_cost"])
        if year1_net_split is not None and catchup_month is None and now >= YEAR_SECONDS and combined_net() >= 0:
            catchup_month = now / MONTH_SECONDS

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
            gdef = GROUP_DEFS[gname]
            for acc in list(accs):
                cost_now = None
                if gdef["kind"] == "fivers":
                    cost_now = eng.SUMMER_COST if now < eng.PRICE_CUTOFF_SECONDS else eng.POST_SUMMER_COST_REAL
                was_challenge = acc["active"] and acc["phase"] == "challenge"
                just_funded = process_trade(acc, trade, now, gdef["dd"], gname, cost_override=cost_now)
                if was_challenge and just_funded and gname not in state["group_own_funded"]:
                    state["group_own_funded"].add(gname)
                    state["group_funded_count"] += 1

        process_extra_account(now)
        process_pending(pending_reopen)
        process_pending(pending_group_open)
        try_emergency_bootstrap()

        if reserve_hit_30k_month is None and state["reserve"] >= min_reserve_for_unlock:
            reserve_hit_30k_month = now / MONTH_SECONDS

        still_pending = []
        for group_names, trig in pending_group_trigger:
            _, n_req = trig
            if state["group_funded_count"] >= n_req and state["reserve"] >= min_reserve_for_unlock:
                for gname in group_names:
                    cost0 = sum(a["cost"] for a in accounts_by_group[gname])
                    handle_cost_hybrid(cost0, pending_group_open, gname, lambda g=gname: open_group(g))
                fleet_unlocked = True
            else:
                still_pending.append((group_names, trig))
        pending_group_trigger = still_pending

        if full_structure_month is None and structure_complete():
            full_structure_month = now / MONTH_SECONDS

    if year1_net_split is None:
        year1_net_split = combined_net()
        year1_snapshot = dict(n_active=n_active_accounts(), fleet_unlocked=fleet_unlocked,
                               reserve=state["reserve"], starter_prefund_fees=state["starter_prefund_fees"],
                               fleet_unlock_cost=state["fleet_unlock_cost"],
                               extra_account_open_cost=state["extra_account_open_cost"],
                               postfund_break_net_cost=state["postfund_break_net_cost"])

    return {
        "final_net_split": combined_net(),
        "is_paid_cum": state["is_paid_cum"],
        "year1_net_split": year1_net_split,
        "year1_n_active": year1_snapshot["n_active"],
        "year1_fleet_unlocked": year1_snapshot["fleet_unlocked"],
        "year1_reserve": year1_snapshot["reserve"],
        "year1_starter_prefund_fees": year1_snapshot["starter_prefund_fees"],
        "year1_fleet_unlock_cost": year1_snapshot["fleet_unlock_cost"],
        "year1_extra_account_open_cost": year1_snapshot["extra_account_open_cost"],
        "year1_postfund_break_net_cost": year1_snapshot["postfund_break_net_cost"],
        "catchup_month": catchup_month,
        "reserve_hit_30k_month": reserve_hit_30k_month,
    }


def run_propagated(pop, market_data, excluded_map, ceiling, min_reserve, emergency, target_risk_ov, eval_risk_ov,
                    gft_eval_risk_ov, reserve_share, extra_threshold_mult, postfund_ramp, n_sims, seed):
    rng_wr = random.Random(seed)
    rng_boot = random.Random(seed + 1)
    rows = []
    for _ in range(n_sims):
        wr_draw = rng_wr.betavariate(ALPHA_POST, BETA_POST)
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_draw, 1.0, False, random.Random(rng_wr.random()))
        block_seconds = 2 * DAYS_PER_MONTH * DAY_SECONDS
        blocks = build_blocks(trades, slot_arrivals, block_seconds)
        target_duration = slot_arrivals[-1]
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot, target_duration)
        order = list(range(len(raw_trades)))
        res = run_one(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, min_reserve, emergency,
                       target_risk_ov, eval_risk_ov, gft_eval_risk_ov, reserve_share, extra_threshold_mult,
                       postfund_ramp)
        rows.append(res)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    import sys
    t_start = time.time()
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 600

    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

    rows_summary = []
    for ceiling in (1000.0, 3000.0):
        print("\n" + "=" * 100 +
              f"\nFIX trades_taken v4 -- eval={FINAL_EVAL_RISK}%(GFT={FINAL_GFT_EVAL_RISK}%)/flotte={FINAL_FLEET_RISK}% "
              f"| mecanisme deplafonne | plafond {ceiling:.0f}$ (n={n_sims})\n" + "=" * 100)
        for label, ramp in (("SANS rampe post-financement (actuel v4)", False), ("AVEC rampe post-financement", True)):
            t0 = time.time()
            df = run_propagated(pop, market_data, excluded_map, ceiling, DEFAULT_RESERVE, DEFAULT_EMERGENCY,
                                 FINAL_FLEET_RISK, FINAL_EVAL_RISK, FINAL_GFT_EVAL_RISK, FINAL_RESERVE_SHARE,
                                 EXTRA_THRESHOLD_MULT, ramp, n_sims, seed=4000)
            df.to_csv(f"extra_account_v4_postfund_ramp_ceiling{int(ceiling)}_{'with' if ramp else 'without'}.csv",
                      index=False)
            net = df["final_net_split"] - df["is_paid_cum"]
            n_ruin = (net < 0).sum()
            n_y1 = (df["year1_net_split"] < 0).sum()
            neg = df[df["year1_net_split"] < 0]
            cat_a = neg[neg["year1_fleet_unlocked"]]
            cat_a_deficit = cat_a["year1_net_split"].mean() if len(cat_a) else float("nan")
            cat_a_postfund_cost = cat_a["year1_postfund_break_net_cost"].mean() if len(cat_a) else float("nan")
            row = dict(ceiling=ceiling, label=label, profit=net.mean(), ruine=n_ruin/len(df)*100,
                       annee1_neg=n_y1/len(df)*100, cat_a_n=len(cat_a), cat_a_deficit_moyen=cat_a_deficit,
                       cat_a_postfund_cost_moyen=cat_a_postfund_cost)
            rows_summary.append(row)
            print(f"[{label}] profit={row['profit']:+,.0f}$ | ruine={row['ruine']:.2f}% | "
                  f"P(annee1<0)={row['annee1_neg']:.2f}% | cat.A n={row['cat_a_n']} deficit_moy={cat_a_deficit:,.0f}$ "
                  f"postfund_cost_moy={cat_a_postfund_cost:,.0f}$ ({time.time()-t0:.0f}s)")

    pd.DataFrame(rows_summary).to_csv("extra_account_v4_postfund_ramp_summary.csv", index=False)
    print(f"\nTermine en {time.time()-t_start:.0f}s.")
