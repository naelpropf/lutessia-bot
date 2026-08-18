"""
Correction du mecanisme de scaling (decouverte 08/08, verifiee par recherche
web) : l'ancien process_growth_upgrade modelisait un ACHAT direct de palier
(reserve>=cout -> upgrade instantane), qui ne correspond a AUCUN produit reel
chez FTMO ou Blueberry Funded. Verifie :
  - FTMO : scaling GRATUIT, +25% tous les 4 mois, si >=10% de profit sur les
    4 derniers mois (approx : 2/4 mois positifs non modelise separement,
    condition profit consideree suffisante -- simplification documentee).
  - Blueberry Funded : scaling GRATUIT, +25% tous les 3 mois, si >=10% de
    profit net sur 3 mois consecutifs (condition "4 payouts sur la periode"
    non modelisee separement, meme simplification -- un compte assez
    profitable pour +10%/3mois demanderait quasi-automatiquement ses
    payouts), plafonne a 2M$ (mais le vrai plafond structurant ici reste le
    cap combine par firm deja utilise : 400k FTMO/Blueberry/GFT, 200k
    FundedNext).

Remplace process_growth_upgrade : palier continu (pas de TIER_SEQUENCE
discrete), +25% multiplicatif a chaque fenetre glissante (3 mois Blueberry,
4 mois FTMO/GFT/FundedNext -- ces 2 dernieres modelisees "sur le modele
FTMO" comme deja le cas pour leurs couts dans le reste du projet) ou le
profit net cumule sur la fenetre >= 10% du palier courant. Fenetre reinitialisee
a CHAQUE evenement de financement (initial ou apres reouverture) -- le
compteur repart de zero, comme un vrai cycle d'evaluation. Cout de rachat
apres casse : proportionnel au palier courant (ratio 333$/50000$=0,666%,
le seul ratio reellement source dans le projet), pas un tarif fixe par
palier discret puisque le palier n'est plus discret.
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

FEE_RATIO = 333.0 / 50000.0  # seul ratio cout/palier reellement source dans le projet
BASE_PALIER = {"Blueberry": 25000.0, "FTMO": 50000.0, "GFT": 50000.0, "FundedNext": 50000.0}
SCALING_WINDOW_MONTHS = {"Blueberry": 3.0, "FTMO": 4.0, "GFT": 4.0, "FundedNext": 4.0}
SCALING_PROFIT_THRESHOLD_PCT = 10.0
SCALING_MULT = 1.25


def run_one(trades, slot_arrivals, market_data, excluded_map, order, ceiling, min_reserve_for_unlock,
            emergency_capital, target_risk_override, eval_risk_override, reserve_share):
    accounts_by_group = {}
    active0_cost = 0.0
    for group_names, trigger in SEQ_GROUPED:
        for gname in group_names:
            gdef = GROUP_DEFS[gname]
            is_day0 = trigger == "day0"
            n_acc = gdef["n_accounts"] if gdef["kind"] == "fivers" else gdef["n_accounts"]
            if gdef["kind"] == "fivers":
                accs = [eng.make_acc(eng.PALIER_5ERS, eng.SUMMER_COST, active=is_day0) for _ in range(n_acc)]
            else:
                base_p = BASE_PALIER[gname]
                fee0 = round(base_p * FEE_RATIO)
                accs = [eng.make_acc(base_p, fee0, active=is_day0) for _ in range(n_acc)]
                for a in accs:
                    a["base_palier"] = base_p
                    a["base_cost"] = fee0
                    a["scaling_window_start"] = 0.0
                    a["scaling_window_pnl"] = 0.0
            accounts_by_group[gname] = accs
            if is_day0:
                active0_cost += sum(a["cost"] for a in accs)

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

    def reopen_account(acc, cost, now):
        acc["active"] = True
        acc["total_fees_paid"] += cost
        acc["phase"] = "challenge"
        acc["cumulative_since_reset"] = 0.0
        acc["peak_since_reset"] = 0.0
        acc["trading_days_since_reset"] = set()
        acc["daily_pnl"] = {}
        if downgrade_active() and "base_palier" in acc:
            acc["palier"] = acc["base_palier"]
            acc["cost"] = acc["base_cost"]

    def open_group(gname):
        for a in accounts_by_group[gname]:
            a["active"] = True
            a["total_fees_paid"] = a["cost"]

    def try_emergency_bootstrap(now):
        if n_active_accounts() != 0 or emergency_capital <= 0 or state["emergency_remaining"] <= 0:
            return
        bb_acc = accounts_by_group[STARTER][0]
        cost = bb_acc["base_cost"] if downgrade_active() and "base_palier" in bb_acc else bb_acc["cost"]
        if state["emergency_remaining"] >= cost:
            state["emergency_remaining"] -= cost
            reopen_account(bb_acc, cost, now)
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
            if pnl > 0:
                net_pnl = pnl * SPLIT_FLAT
            else:
                net_pnl = pnl
            acc["total_funded_pnl"] += net_pnl
            if gname != "Fivers":
                acc["scaling_window_pnl"] += net_pnl
            if net_pnl > 0:
                state["reserve"] += net_pnl * reserve_share

        trailing_dd = acc["peak_since_reset"] - acc["cumulative_since_reset"]
        daily_dd = -acc["daily_pnl"][close_day]
        broke = (trailing_dd >= eng.BREAK_DD_PCT / 100 * acc["palier"] or daily_dd >= daily_loss_pct / 100 * acc["palier"])

        just_funded_own = False
        if broke:
            state["total_breaks"] += 1
            if downgrade_active() and "base_palier" in acc:
                cost = acc["base_cost"]
            elif gname == "Fivers":
                cost = cost_override
            else:
                cost = cost_for_palier(gname, acc["palier"])
            acc["active"] = False
            handle_cost_hybrid(cost, pending_reopen, id(acc), lambda a=acc, c=cost, n=now: reopen_account(a, c, n))
            return False

        if (acc["phase"] == "challenge" and acc["cumulative_since_reset"] >= eng.CHALLENGE_TARGET_PCT / 100 * acc["palier"]
                and len(acc["trading_days_since_reset"]) >= eng.MIN_TRADING_DAYS):
            acc["phase"] = "funded"
            just_funded_own = True
            state["ever_funded"] = True
            acc["cumulative_since_reset"] = 0.0
            acc["peak_since_reset"] = 0.0
            acc["trading_days_since_reset"] = set()
            if gname != "Fivers":
                acc["scaling_window_start"] = now
                acc["scaling_window_pnl"] = 0.0
        return just_funded_own

    def process_scaling(now):
        for gname, accs in accounts_by_group.items():
            gdef = GROUP_DEFS[gname]
            if gdef["kind"] != "growth":
                continue
            cap = gdef["cap"]
            window_seconds = SCALING_WINDOW_MONTHS[gname] * MONTH_SECONDS

            def combined(exclude_idx=None, accs=accs):
                return sum(a["palier"] for i, a in enumerate(accs) if i != exclude_idx and a["active"])

            for i, acc in enumerate(accs):
                if not acc["active"] or acc["phase"] != "funded":
                    continue
                if now - acc["scaling_window_start"] < window_seconds:
                    continue
                threshold = SCALING_PROFIT_THRESHOLD_PCT / 100 * acc["palier"]
                if acc["scaling_window_pnl"] >= threshold:
                    room = max(0.0, cap - combined(exclude_idx=i))
                    new_palier = min(acc["palier"] * SCALING_MULT, acc["palier"] + room)
                    if new_palier > acc["palier"]:
                        acc["palier"] = new_palier
                        acc["cost"] = cost_for_palier(gname, new_palier)
                acc["scaling_window_start"] = now
                acc["scaling_window_pnl"] = 0.0

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

        for gname, accs in accounts_by_group.items():
            gdef = GROUP_DEFS[gname]
            for acc in accs:
                cost_now = None
                if gdef["kind"] == "fivers":
                    cost_now = eng.SUMMER_COST if now < eng.PRICE_CUTOFF_SECONDS else eng.POST_SUMMER_COST_REAL
                was_challenge = acc["active"] and acc["phase"] == "challenge"
                process_trade(acc, trade, now, gdef["dd"], gname, cost_override=cost_now)
                if was_challenge and acc["phase"] == "funded" and gname not in state["group_own_funded"]:
                    state["group_own_funded"].add(gname)
                    state["group_funded_count"] += 1

        process_scaling(now)
        process_pending(pending_reopen)
        process_pending(pending_group_open)
        try_emergency_bootstrap(now)

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
        "full_structure_month": full_structure_month,
    }


def run_propagated(pop, market_data, excluded_map, ceiling, min_reserve, emergency, target_risk_ov, eval_risk_ov,
                    reserve_share, n_sims, seed):
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
                       target_risk_ov, eval_risk_ov, reserve_share)
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

    print("\n" + "=" * 100 + f"\nSCALING CORRIGE (gratuit, +25%/cycle, gate duree+profit) -- config finale eval="
          f"{FINAL_EVAL_RISK}%/flotte={FINAL_FLEET_RISK}% (n={n_sims})\n" + "=" * 100)
    rows = []
    for ceiling in (1000.0, 3000.0):
        t0 = time.time()
        df = run_propagated(pop, market_data, excluded_map, ceiling, DEFAULT_RESERVE, DEFAULT_EMERGENCY,
                             FINAL_FLEET_RISK, FINAL_EVAL_RISK, FINAL_RESERVE_SHARE, n_sims, seed=4000)
        net = df["final_net_split"] - df["is_paid_cum"]
        n_ruin = (net < 0).sum()
        n_y1 = (df["year1_net_split"] < 0).sum()
        row = dict(ceiling=ceiling, profit_mean=net.mean(), p_ruine_pct=n_ruin / len(df) * 100,
                   p_annee1_neg_pct=n_y1 / len(df) * 100,
                   delai_deblocage_median=df["reserve_hit_30k_month"].median(),
                   delai_structure_complete_median=df["full_structure_month"].median())
        rows.append(row)
        print(f"[plafond={ceiling:.0f}$] profit={row['profit_mean']:+,.0f}$ | ruine={row['p_ruine_pct']:.2f}% | "
              f"P(annee1<0)={row['p_annee1_neg_pct']:.2f}% | deblocage_median={row['delai_deblocage_median']:.2f}mois | "
              f"structure_complete_median={row['delai_structure_complete_median']} ({time.time()-t0:.0f}s)")
    pd.DataFrame(rows).to_csv("corrected_scaling_results.csv", index=False)

    print(f"\nTermine en {time.time()-t_start:.0f}s.")
