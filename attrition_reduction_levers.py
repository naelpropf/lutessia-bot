"""
Suite du diagnostic d'attrition independante cumulative (0,0% de casses
groupees sur le meme signal, ~7-9j d'ecart moyen). Teste 3 leviers separement
puis combines, sur la config de reference (groupee + reserve + amorcage
300$) :

1. Tampon de reserve etendu (50k/75k/100k/150k$), au-dela du plateau apparent
   a 35k$.
2. Decomposition des casses par phase (evaluation/challenge vs post-
   financement) -- cash net perdu par categorie.
3a. Risque flotte entiere reduit une fois finance (2,5%->2,0%/1,75%).
3b. Risque reduit SPECIFIQUEMENT pendant la phase d'evaluation (1,5%/1,75%/
    2,0%, remplace la rampe existante pendant le challenge, cible : moins de
    casses seches a 100% de perte, au prix d'un temps d'evaluation plus long).
"""
import random
import time

import numpy as np
import pandas as pd

import robustness_5ers_risk_challenge as eng
from point123_startingfirm_optimization import GROUP_DEFS, build_group_seq_map, make_accounts_for_group
from point_liquidity_rules import RAMP_RISK, RAMP_N, TARGET_RISK, CORR_TH, DAY_SECONDS
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence

ALPHA_POST, BETA_POST = 260, 388
YEAR_SECONDS = 365.25 * DAY_SECONDS
MONTH_SECONDS = DAYS_PER_MONTH * DAY_SECONDS
STARTER = "Blueberry"
SEQ_GROUPED = [((STARTER,), "day0"), (("FTMO", "Fivers", "GFT", "FundedNext"), ("after_count", 1))]
DEFAULT_RESERVE = 30000.0
DEFAULT_EMERGENCY = 300.0


def run_one(trades, slot_arrivals, market_data, excluded_map, order, ceiling, min_reserve_for_unlock,
            emergency_capital, target_risk_override, eval_risk_override, log_breaks=False):
    seq_map = build_group_seq_map(SEQ_GROUPED, {STARTER: 25000})
    accounts_by_group = {}
    active0_cost = 0.0
    for group_names, trigger in SEQ_GROUPED:
        for gname in group_names:
            gdef = GROUP_DEFS[gname]
            is_day0 = trigger == "day0"
            accs = make_accounts_for_group(gname, gdef, active=is_day0, seq_map=seq_map)
            accounts_by_group[gname] = accs
            if is_day0:
                active0_cost += sum(a["cost"] for a in accs)

    target_risk = target_risk_override if target_risk_override is not None else TARGET_RISK
    state = {"reserve": 0.0, "ever_funded": False, "real_cash_paid": active0_cost, "total_breaks": 0,
             "group_funded_count": 0, "group_own_funded": set(), "hit_ceiling": False,
             "emergency_remaining": emergency_capital}
    pending_group_trigger = [(names, trig) for names, trig in SEQ_GROUPED if trig != "day0"]
    pending_reopen = []
    pending_group_open = []
    break_log = []  # (phase_at_break, cost, funded_pnl_before_break)
    funding_months = []

    def combined_net():
        return sum(a["total_funded_pnl"] - a["total_fees_paid"] for accs in accounts_by_group.values() for a in accs)

    def n_active_accounts():
        return sum(1 for accs in accounts_by_group.values() for a in accs if a["active"])

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

    def open_group(gname):
        for a in accounts_by_group[gname]:
            a["active"] = True
            a["total_fees_paid"] = a["cost"]

    def try_emergency_bootstrap():
        if n_active_accounts() != 0 or emergency_capital <= 0 or state["emergency_remaining"] <= 0:
            return
        bb_acc = accounts_by_group[STARTER][0]
        cost = bb_acc["cost"]
        if state["emergency_remaining"] >= cost:
            state["emergency_remaining"] -= cost
            reopen_account(bb_acc, cost)
            pending_reopen[:] = [p for p in pending_reopen if p["key"] != id(bb_acc)]

    def process_trade(acc, trade, now, daily_loss_pct, cost_override=None):
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
            acc["total_funded_pnl"] += pnl
            if pnl > 0:
                state["reserve"] += pnl * eng.RESERVE_SHARE

        trailing_dd = acc["peak_since_reset"] - acc["cumulative_since_reset"]
        daily_dd = -acc["daily_pnl"][close_day]
        broke = (trailing_dd >= eng.BREAK_DD_PCT / 100 * acc["palier"] or daily_dd >= daily_loss_pct / 100 * acc["palier"])

        just_funded_own = False
        if broke:
            state["total_breaks"] += 1
            cost = cost_override if cost_override is not None else acc["cost"]
            if log_breaks:
                break_log.append((acc["phase"], cost, acc["total_funded_pnl"]))
            acc["active"] = False
            handle_cost_hybrid(cost, pending_reopen, id(acc), lambda a=acc, c=cost: reopen_account(a, c))
            return False

        if (acc["phase"] == "challenge" and acc["cumulative_since_reset"] >= eng.CHALLENGE_TARGET_PCT / 100 * acc["palier"]
                and len(acc["trading_days_since_reset"]) >= eng.MIN_TRADING_DAYS):
            acc["phase"] = "funded"
            just_funded_own = True
            state["ever_funded"] = True
            acc["cumulative_since_reset"] = 0.0
            acc["peak_since_reset"] = 0.0
            acc["trading_days_since_reset"] = set()
            if log_breaks:
                funding_months.append((now - acc.get("challenge_start", now)) / MONTH_SECONDS)
        return just_funded_own

    def process_growth_upgrade():
        for gname, accs in accounts_by_group.items():
            gdef = GROUP_DEFS[gname]
            if gdef["kind"] != "growth":
                continue
            seq, cost_map, upgrade_map, cap = seq_map[gname]

            def combined(exclude_idx=None, accs=accs):
                return sum(a["palier"] for i, a in enumerate(accs) if i != exclude_idx and a["active"])

            for i, acc in enumerate(accs):
                if not acc["active"] or acc["phase"] != "funded":
                    continue
                idx = seq.index(acc["palier"])
                if idx + 1 >= len(seq):
                    continue
                next_tier = seq[idx + 1]
                ucost = upgrade_map[next_tier]
                would_be = combined(exclude_idx=i) + next_tier
                if would_be > cap:
                    continue
                if state["reserve"] >= ucost:
                    state["reserve"] -= ucost
                    acc["total_fees_paid"] += ucost
                    acc["palier"] = next_tier
                    acc["cost"] = cost_map[next_tier]
                    acc["phase"] = "challenge"
                    acc["cumulative_since_reset"] = 0.0
                    acc["peak_since_reset"] = 0.0
                    acc["trading_days_since_reset"] = set()

    def structure_complete():
        for g in ("Blueberry", "FTMO", "Fivers", "GFT", "FundedNext"):
            if not accounts_by_group[g][0]["active"]:
                return False
        return True

    full_structure_month = None
    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]

        for gname, accs in accounts_by_group.items():
            gdef = GROUP_DEFS[gname]
            for acc in accs:
                cost_now = None
                if gdef["kind"] == "fivers":
                    cost_now = eng.SUMMER_COST if now < eng.PRICE_CUTOFF_SECONDS else eng.POST_SUMMER_COST_REAL
                was_challenge = acc["active"] and acc["phase"] == "challenge"
                process_trade(acc, trade, now, gdef["dd"], cost_override=cost_now)
                if was_challenge and acc["phase"] == "funded" and gname not in state["group_own_funded"]:
                    state["group_own_funded"].add(gname)
                    state["group_funded_count"] += 1

        process_growth_upgrade()
        process_pending(pending_reopen)
        process_pending(pending_group_open)
        try_emergency_bootstrap()

        still_pending = []
        for group_names, trig in pending_group_trigger:
            _, n_req = trig
            if state["group_funded_count"] >= n_req and state["reserve"] >= min_reserve_for_unlock:
                for gname in group_names:
                    cost0 = sum(a["cost"] for a in accounts_by_group[gname])
                    handle_cost_hybrid(cost0, pending_group_open, gname, lambda g=gname: open_group(g))
            else:
                still_pending.append((group_names, trig))
        pending_group_trigger = still_pending

        if full_structure_month is None and structure_complete():
            full_structure_month = now / MONTH_SECONDS

    return {"final_net": combined_net(), "full_structure_month": full_structure_month, "break_log": break_log}


def run_propagated(pop, market_data, excluded_map, ceiling, min_reserve, emergency, target_risk_ov, eval_risk_ov,
                    n_sims, seed, log_breaks=False):
    rng_wr = random.Random(seed)
    rng_boot = random.Random(seed + 1)
    rows = []
    all_breaks = []
    for _ in range(n_sims):
        wr_draw = rng_wr.betavariate(ALPHA_POST, BETA_POST)
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_draw, 1.0, False, random.Random(rng_wr.random()))
        block_seconds = 2 * DAYS_PER_MONTH * DAY_SECONDS
        blocks = build_blocks(trades, slot_arrivals, block_seconds)
        target_duration = slot_arrivals[-1]
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot, target_duration)
        order = list(range(len(raw_trades)))
        res = run_one(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, min_reserve, emergency,
                       target_risk_ov, eval_risk_ov, log_breaks=log_breaks)
        all_breaks.extend(res.pop("break_log"))
        rows.append(res)
    return pd.DataFrame(rows), all_breaks


if __name__ == "__main__":
    import sys
    t_start = time.time()
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 600

    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

    # ===== PARTIE 1 : tampon etendu (avec amorcage 300$) =====
    print("\n" + "=" * 100 + "\nPARTIE 1 -- TAMPON DE RESERVE ETENDU (+ amorcage 300$)\n" + "=" * 100)
    thresholds = [30000.0, 50000.0, 75000.0, 100000.0, 150000.0]
    rows1 = []
    for ceiling in (1000.0, 3000.0):
        print(f"\n--- Plafond {ceiling:.0f}$ ---")
        for th in thresholds:
            t0 = time.time()
            df, _ = run_propagated(pop, market_data, excluded_map, ceiling, th, DEFAULT_EMERGENCY, None, None,
                                    n_sims, seed=1000)
            p5 = df["final_net"].quantile(0.05)
            n_neg = (df["final_net"] < 0).sum()
            row = dict(ceiling=ceiling, threshold=th, profit_final_mean=df["final_net"].mean(), p5=p5,
                       p_ruine_pct=n_neg / len(df) * 100, delai_median=df["full_structure_month"].median())
            rows1.append(row)
            print(f"[seuil={th:.0f}$] profit={row['profit_final_mean']:+,.0f}$ | P5={p5:+,.0f}$ | "
                  f"ruine={row['p_ruine_pct']:.2f}% | delai={row['delai_median']:.2f}mois ({time.time()-t0:.0f}s)")
    pd.DataFrame(rows1).to_csv("attrition_part1_reserve_extended.csv", index=False)

    # ===== PARTIE 2 : decomposition casses par phase (config ref 30k+300$) =====
    print("\n" + "=" * 100 + "\nPARTIE 2 -- CASSES PAR PHASE (config reference 30k$+300$)\n" + "=" * 100)
    rows2 = []
    for ceiling in (1000.0, 3000.0):
        df, breaks = run_propagated(pop, market_data, excluded_map, ceiling, DEFAULT_RESERVE, DEFAULT_EMERGENCY,
                                     None, None, n_sims, seed=1000, log_breaks=True)
        challenge_breaks = [b for b in breaks if b[0] == "challenge"]
        funded_breaks = [b for b in breaks if b[0] == "funded"]
        n_total = len(breaks)
        cost_challenge = sum(b[1] for b in challenge_breaks)
        cost_funded = sum(b[1] for b in funded_breaks)
        pnl_banked_before_funded_breaks = sum(b[2] for b in funded_breaks)
        print(f"\n--- Plafond {ceiling:.0f}$ : {n_total} casses totales sur {len(df)} runs ---")
        print(f"  Casses en EVALUATION (challenge, perte seche) : {len(challenge_breaks)} ({len(challenge_breaks)/max(1,n_total)*100:.1f}%) "
              f"| cout total rachat={cost_challenge:,.0f}$")
        print(f"  Casses POST-FINANCEMENT (profit deja extrait) : {len(funded_breaks)} ({len(funded_breaks)/max(1,n_total)*100:.1f}%) "
              f"| cout total rachat={cost_funded:,.0f}$ | profit deja banque avant ces casses={pnl_banked_before_funded_breaks:,.0f}$")
        rows2.append(dict(ceiling=ceiling, n_total=n_total, n_challenge=len(challenge_breaks), n_funded=len(funded_breaks),
                           cost_challenge=cost_challenge, cost_funded=cost_funded,
                           pnl_banked_before_funded_breaks=pnl_banked_before_funded_breaks))
    pd.DataFrame(rows2).to_csv("attrition_part2_phase_breakdown.csv", index=False)

    # ===== PARTIE 3a : risque flotte entiere reduit =====
    print("\n" + "=" * 100 + "\nPARTIE 3a -- RISQUE FLOTTE ENTIERE REDUIT (config ref 30k+300$)\n" + "=" * 100)
    rows3a = []
    for ceiling in (1000.0, 3000.0):
        print(f"\n--- Plafond {ceiling:.0f}$ ---")
        for tr in [2.5, 2.0, 1.75]:
            t0 = time.time()
            df, _ = run_propagated(pop, market_data, excluded_map, ceiling, DEFAULT_RESERVE, DEFAULT_EMERGENCY,
                                    tr, None, n_sims, seed=1000)
            p5 = df["final_net"].quantile(0.05)
            n_neg = (df["final_net"] < 0).sum()
            row = dict(ceiling=ceiling, target_risk=tr, profit_final_mean=df["final_net"].mean(), p5=p5,
                       p_ruine_pct=n_neg / len(df) * 100, delai_median=df["full_structure_month"].median())
            rows3a.append(row)
            print(f"[risque flotte={tr}%] profit={row['profit_final_mean']:+,.0f}$ | P5={p5:+,.0f}$ | "
                  f"ruine={row['p_ruine_pct']:.2f}% ({time.time()-t0:.0f}s)")
    pd.DataFrame(rows3a).to_csv("attrition_part3a_fleet_risk.csv", index=False)

    # ===== PARTIE 3b : risque evaluation reduit =====
    print("\n" + "=" * 100 + "\nPARTIE 3b -- RISQUE EVALUATION REDUIT (config ref 30k+300$)\n" + "=" * 100)
    rows3b = []
    for ceiling in (1000.0, 3000.0):
        print(f"\n--- Plafond {ceiling:.0f}$ ---")
        for er in [2.0, 1.75, 1.5]:
            t0 = time.time()
            df, _ = run_propagated(pop, market_data, excluded_map, ceiling, DEFAULT_RESERVE, DEFAULT_EMERGENCY,
                                    None, er, n_sims, seed=1000)
            p5 = df["final_net"].quantile(0.05)
            n_neg = (df["final_net"] < 0).sum()
            row = dict(ceiling=ceiling, eval_risk=er, profit_final_mean=df["final_net"].mean(), p5=p5,
                       p_ruine_pct=n_neg / len(df) * 100, delai_median=df["full_structure_month"].median())
            rows3b.append(row)
            print(f"[risque eval={er}%] profit={row['profit_final_mean']:+,.0f}$ | P5={p5:+,.0f}$ | "
                  f"ruine={row['p_ruine_pct']:.2f}% ({time.time()-t0:.0f}s)")
    pd.DataFrame(rows3b).to_csv("attrition_part3b_eval_risk.csv", index=False)

    print(f"\nTermine en {time.time()-t_start:.0f}s.")
