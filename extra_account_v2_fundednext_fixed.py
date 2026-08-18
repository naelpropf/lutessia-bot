"""
Suite de extra_account_vs_scaling.py, deux corrections demandees le 08/08 :

1. FundedNext verifie (web + doc projet, coherent) : plafond MONO-COMPTE reel
   = 200 000$ (Stellar Lite/2-Step) -- deja documente dans contexte_projet_
   lutessia_2026-08-07-v3.md:166 et deja code comme cap=200000 pour ce
   groupe. FundedNext est desormais FIXE a 1 seul compte, ouvert directement
   au palier 200 000$ (cout de challenge repris du modele FTMO deja utilise
   partout dans le projet pour cette firm : CHALLENGE_COST_FTMO[200000]=
   1000$), PAS de mecanisme "compte supplementaire" chez cette firm.

2. Diagnostic instrumente de l'ecart observe (3,47M$ vs 5,76M$ ancien
   mecanisme bugge) : pour chaque compte supplementaire ouvert (Blueberry/
   FTMO/GFT), track le nombre de casses en EVALUATION avant le premier
   financement (ou jamais finance dans l'horizon), et le cout net cumule de
   ces echecs -- poste totalement absent de l'ancien mecanisme A2 (upgrade
   garanti sans risque d'echec).
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

ALPHA_POST, BETA_POST = 260, 388
YEAR_SECONDS = 365.25 * DAY_SECONDS
MONTH_SECONDS = DAYS_PER_MONTH * DAY_SECONDS
STARTER = "Blueberry"
SEQ_GROUPED = [((STARTER,), "day0"), (("FTMO", "Fivers", "GFT", "FundedNext"), ("after_count", 1))]
DEFAULT_RESERVE = 30000.0
DEFAULT_EMERGENCY = 300.0
SPLIT_FLAT = 0.80
FINAL_RESERVE_SHARE = 0.95
FINAL_EVAL_RISK = 2.25
FINAL_FLEET_RISK = 2.5
GROWTH_FIRMS_EXTRA = ("Blueberry", "FTMO", "GFT")  # FundedNext EXCLU -- fixe a 200k mono-compte
FUNDEDNEXT_FIXED_PALIER = 200000.0
FUNDEDNEXT_FIXED_COST = CHALLENGE_COST_FTMO[200000]  # 1000$, modele FTMO deja utilise pour cette firm
EXTRA_ACCOUNT_MULT = 2.0
EXTRA_THRESHOLD_MULT = 3.0


def make_growth_acc(palier, cost, active=False):
    a = eng.make_acc(palier, cost, active=active)
    a["base_palier"] = palier
    a["base_cost"] = cost
    return a


def run_one(trades, slot_arrivals, market_data, excluded_map, order, ceiling, min_reserve_for_unlock,
            emergency_capital, target_risk_override, eval_risk_override, reserve_share,
            growth_mode, extra_threshold_mult, log_extra_diag=False):
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
            accounts_by_group[gname] = accs
            if is_day0:
                active0_cost += sum(a["cost"] for a in accs)

    extra_opened = {g: False for g in GROWTH_FIRMS_EXTRA}
    extra_acc_ref = {}  # gname -> account dict, pour tracker le diagnostic
    extra_diag = {}  # gname -> dict(n_challenge_breaks, cash_lost_before_funded, funded)
    target_risk = target_risk_override if target_risk_override is not None else TARGET_RISK
    fleet_unlocked = False
    state = {"reserve": 0.0, "ever_funded": False, "real_cash_paid": active0_cost, "total_breaks": 0,
             "group_funded_count": 0, "group_own_funded": set(), "hit_ceiling": False,
             "emergency_remaining": emergency_capital, "is_paid_cum": 0.0,
             "tax_breach_count": 0, "tax_breach_total": 0.0, "tax_breach_max": 0.0,
             "tax_breach_concurrent_with_repurchase": 0, "tax_breach_events": []}
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
            current_risk = eval_risk_override if eval_risk_override is not None else (
                RAMP_RISK if acc["trades_taken"] < RAMP_N else target_risk)
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
            else:
                cost = cost_for_palier(gname, acc["palier"])
            was_challenge = acc["phase"] == "challenge"
            if log_extra_diag and id(acc) in extra_diag and was_challenge:
                extra_diag[id(acc)]["n_challenge_breaks"] += 1
                extra_diag[id(acc)]["cash_lost_before_funded"] += cost
            acc["active"] = False
            handle_cost_hybrid(cost, pending_reopen, id(acc), lambda a=acc, c=cost: reopen_account(a, c))
            return False

        if (acc["phase"] == "challenge" and acc["cumulative_since_reset"] >= eng.CHALLENGE_TARGET_PCT / 100 * acc["palier"]
                and len(acc["trading_days_since_reset"]) >= eng.MIN_TRADING_DAYS):
            acc["phase"] = "funded"
            state["ever_funded"] = True
            acc["cumulative_since_reset"] = 0.0
            acc["peak_since_reset"] = 0.0
            acc["trading_days_since_reset"] = set()
            if log_extra_diag and id(acc) in extra_diag and not extra_diag[id(acc)]["funded"]:
                extra_diag[id(acc)]["funded"] = True
                extra_diag[id(acc)]["month_funded"] = now / MONTH_SECONDS
            return True
        return False

    def process_extra_account(now):
        if growth_mode != "extra_account" or not fleet_unlocked:
            return
        for gname in GROWTH_FIRMS_EXTRA:
            if extra_opened[gname]:
                continue
            extra_palier = BASE_PALIER[gname] * EXTRA_ACCOUNT_MULT
            extra_cost = cost_for_palier(gname, extra_palier)
            if state["reserve"] >= extra_threshold_mult * extra_cost:
                state["reserve"] -= extra_cost
                new_acc = make_growth_acc(extra_palier, extra_cost, active=True)
                new_acc["total_fees_paid"] = extra_cost
                new_acc["_gname"] = gname
                accounts_by_group[gname].append(new_acc)
                extra_opened[gname] = True
                if log_extra_diag:
                    extra_diag[id(new_acc)] = dict(gname=gname, n_challenge_breaks=0,
                                                    cash_lost_before_funded=0.0, funded=False,
                                                    month_opened=now / MONTH_SECONDS, month_funded=None)

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
    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]

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

    return {
        "final_net_split": combined_net(),
        "is_paid_cum": state["is_paid_cum"],
        "year1_net_split": year1_net_split,
        "reserve_hit_30k_month": reserve_hit_30k_month,
        "extra_diag": list(extra_diag.values()),
    }


def run_propagated(pop, market_data, excluded_map, ceiling, min_reserve, emergency, target_risk_ov, eval_risk_ov,
                    reserve_share, growth_mode, extra_threshold_mult, n_sims, seed, log_extra_diag=False):
    rng_wr = random.Random(seed)
    rng_boot = random.Random(seed + 1)
    rows = []
    all_diag = []
    for _ in range(n_sims):
        wr_draw = rng_wr.betavariate(ALPHA_POST, BETA_POST)
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_draw, 1.0, False, random.Random(rng_wr.random()))
        block_seconds = 2 * DAYS_PER_MONTH * DAY_SECONDS
        blocks = build_blocks(trades, slot_arrivals, block_seconds)
        target_duration = slot_arrivals[-1]
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot, target_duration)
        order = list(range(len(raw_trades)))
        res = run_one(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, min_reserve, emergency,
                       target_risk_ov, eval_risk_ov, reserve_share, growth_mode, extra_threshold_mult,
                       log_extra_diag=log_extra_diag)
        all_diag.extend(res.pop("extra_diag"))
        rows.append(res)
    return pd.DataFrame(rows), all_diag


if __name__ == "__main__":
    import sys
    t_start = time.time()
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 600

    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

    rows = []
    all_diag_rows = []
    for ceiling in (1000.0, 3000.0):
        print(f"\n{'='*100}\nPlafond {ceiling:.0f}$ -- FundedNext fixe 200k$ mono-compte\n{'='*100}")
        t0 = time.time()
        df, diag = run_propagated(pop, market_data, excluded_map, ceiling, DEFAULT_RESERVE, DEFAULT_EMERGENCY,
                                   FINAL_FLEET_RISK, FINAL_EVAL_RISK, FINAL_RESERVE_SHARE, "extra_account",
                                   EXTRA_THRESHOLD_MULT, n_sims, seed=4000, log_extra_diag=True)
        net = df["final_net_split"] - df["is_paid_cum"]
        row = dict(ceiling=ceiling, profit=net.mean(), ruine=(net < 0).sum() / len(df) * 100,
                   annee1_neg=(df["year1_net_split"] < 0).sum() / len(df) * 100)
        rows.append(row)
        print(f"[extra_account + FundedNext fixe] profit={row['profit']:+,.0f}$ | ruine={row['ruine']:.2f}% | "
              f"P(annee1<0)={row['annee1_neg']:.2f}% ({time.time()-t0:.0f}s)")

        diag_df = pd.DataFrame(diag)
        diag_df["ceiling"] = ceiling
        all_diag_rows.append(diag_df)
        for gname in ("Blueberry", "FTMO", "GFT"):
            sub = diag_df[diag_df["gname"] == gname]
            if len(sub) == 0:
                continue
            p_funded = sub["funded"].mean() * 100
            print(f"  [{gname}] compte supplementaire ouvert {len(sub)}/{n_sims} runs | "
                  f"P(finance avant fin horizon)={p_funded:.1f}% | "
                  f"casses moy. en eval avant financement={sub['n_challenge_breaks'].mean():.2f} | "
                  f"cout net moy. des echecs={sub['cash_lost_before_funded'].mean():,.0f}$")

    pd.DataFrame(rows).to_csv("extra_account_v2_results.csv", index=False)
    pd.concat(all_diag_rows, ignore_index=True).to_csv("extra_account_v2_diag.csv", index=False)
    print(f"\nTermine en {time.time()-t_start:.0f}s.")
