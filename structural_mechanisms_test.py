"""
Parties B/D/E (suite reserve_threshold_sweep.py) : mecanismes structurels
au-dela du seul seuil de reserve, testes seuls puis combines au meilleur
seuil de reserve (17500$, deja valide).

B. CAPITAL D'AMORCAGE PROTEGE : une somme fixe (200/300/500$) HORS plafond
   normal, reservee exclusivement a rouvrir le compte le moins cher (Blueberry,
   son cout courant) SI ET SEULEMENT SI tous les comptes de la flotte sont
   simultanement casses (etat absorbant). Ne rentre jamais dans le calcul de
   real_cash_paid/ceiling normal -- un budget d'urgence a part.

D. RACHAT PRIORISE PAR COUT CROISSANT : au lieu de payer chaque casse des
   qu'elle survient (ordre chronologique, gaspille le cash sur le 1er compte
   casse rencontre meme si un autre moins cher casse juste apres), la file
   d'attente de rachat est triee par cout croissant a chaque tick avant tout
   paiement -- priorise systematiquement le moins cher quand le cash est
   contraint (version simplifiee de la fenetre de cluster 7j explicite, mais
   qui capture le meme objectif : ne pas epuiser le cash sur un rachat cher
   pendant qu'un moins cher attend).

E. COOLDOWN APRES CLUSTER : si 2+ casses surviennent dans une fenetre de 7j,
   tout rachat (reserve OU cash perso) est gele jusqu'a cooldown_days apres
   la derniere casse du cluster -- evite de racheter en pleine continuation
   d'une mauvaise sequence.
"""
import random
import time

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
CLUSTER_WINDOW_DAYS = 7
BEST_RESERVE_THRESHOLD = 17500.0


def run_one(trades, slot_arrivals, market_data, excluded_map, order, ceiling, min_reserve_for_unlock,
            emergency_capital, priority_repurchase, cooldown_days):
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

    state = {"reserve": 0.0, "ever_funded": False, "real_cash_paid": active0_cost, "total_breaks": 0,
             "group_funded_count": 0, "group_own_funded": set(), "hit_ceiling": False, "full_structure_month": None,
             "emergency_remaining": emergency_capital, "emergency_uses": 0,
             "recent_break_times": [], "cooldown_until": 0.0,
             "was_ever_fully_frozen": False, "recovered_after_full_freeze": False}
    pending_group_trigger = [(names, trig) for names, trig in SEQ_GROUPED if trig != "day0"]
    pending_reopen = []  # list of dict(acc, cost, on_success)
    pending_group_open = []

    def combined_net():
        return sum(a["total_funded_pnl"] - a["total_fees_paid"] for accs in accounts_by_group.values() for a in accs)

    def n_active_accounts():
        return sum(1 for accs in accounts_by_group.values() for a in accs if a["active"])

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

    def handle_cost_hybrid(cost, pending_list, pending_key, on_success, now):
        if now < state["cooldown_until"]:
            pending_list.append({"key": pending_key, "cost_remaining": cost, "on_success": on_success})
            return
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

    def process_pending(pending_list, now):
        if now < state["cooldown_until"]:
            return
        if priority_repurchase:
            pending_list.sort(key=lambda item: item["cost_remaining"])
        i = 0
        while i < len(pending_list):
            item = pending_list[i]
            if state["reserve"] >= item["cost_remaining"]:
                state["reserve"] -= item["cost_remaining"]
                item["on_success"]()
                pending_list.pop(i)
            else:
                i += 1

    def try_emergency_bootstrap(now):
        if n_active_accounts() != 0:
            return
        state["was_ever_fully_frozen"] = True
        if emergency_capital <= 0 or state["emergency_remaining"] <= 0:
            return
        bb_acc = accounts_by_group[STARTER][0]
        cost = bb_acc["cost"]
        if state["emergency_remaining"] >= cost:
            state["emergency_remaining"] -= cost
            state["emergency_uses"] += 1
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

        current_risk = RAMP_RISK if acc["trades_taken"] < RAMP_N else TARGET_RISK
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
            state["recent_break_times"] = [t for t in state["recent_break_times"] if now - t <= CLUSTER_WINDOW_DAYS * DAY_SECONDS]
            state["recent_break_times"].append(now)
            if cooldown_days > 0 and len(state["recent_break_times"]) >= 2:
                state["cooldown_until"] = max(state["cooldown_until"], now + cooldown_days * DAY_SECONDS)
            cost = cost_override if cost_override is not None else acc["cost"]
            acc["active"] = False
            handle_cost_hybrid(cost, pending_reopen, id(acc), lambda a=acc, c=cost: reopen_account(a, c), now)
            return False

        if (acc["phase"] == "challenge" and acc["cumulative_since_reset"] >= eng.CHALLENGE_TARGET_PCT / 100 * acc["palier"]
                and len(acc["trading_days_since_reset"]) >= eng.MIN_TRADING_DAYS):
            acc["phase"] = "funded"
            just_funded_own = True
            state["ever_funded"] = True
            acc["cumulative_since_reset"] = 0.0
            acc["peak_since_reset"] = 0.0
            acc["trading_days_since_reset"] = set()
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
        process_pending(pending_reopen, now)
        process_pending(pending_group_open, now)
        try_emergency_bootstrap(now)

        still_pending = []
        for group_names, trig in pending_group_trigger:
            _, n_req = trig
            if state["group_funded_count"] >= n_req and state["reserve"] >= min_reserve_for_unlock:
                for gname in group_names:
                    cost0 = sum(a["cost"] for a in accounts_by_group[gname])
                    handle_cost_hybrid(cost0, pending_group_open, gname, lambda g=gname: open_group(g), now)
            else:
                still_pending.append((group_names, trig))
        pending_group_trigger = still_pending

        if state["full_structure_month"] is None and structure_complete():
            state["full_structure_month"] = now / MONTH_SECONDS

    final_net = combined_net()
    return {"final_net": final_net, "full_structure_month": state["full_structure_month"],
            "was_ever_fully_frozen": state["was_ever_fully_frozen"],
            "frozen_at_end": n_active_accounts() == 0, "emergency_uses": state["emergency_uses"]}


def run_propagated(pop, market_data, excluded_map, ceiling, min_reserve, emergency_capital, priority_repurchase,
                    cooldown_days, n_sims, seed):
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
        rows.append(run_one(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, min_reserve,
                             emergency_capital, priority_repurchase, cooldown_days))
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

    # (label, min_reserve, emergency_capital, priority_repurchase, cooldown_days)
    configs = [
        ("baseline_pure_res0", 0.0, 0.0, False, 0),
        ("baseline_res17500", BEST_RESERVE_THRESHOLD, 0.0, False, 0),
        ("B_emergency200_alone", 0.0, 200.0, False, 0),
        ("B_emergency300_alone", 0.0, 300.0, False, 0),
        ("B_emergency500_alone", 0.0, 500.0, False, 0),
        ("B_emergency300_plus_res17500", BEST_RESERVE_THRESHOLD, 300.0, False, 0),
        ("D_priority_alone", 0.0, 0.0, True, 0),
        ("D_priority_plus_res17500", BEST_RESERVE_THRESHOLD, 0.0, True, 0),
        ("E_cooldown7_alone", 0.0, 0.0, False, 7),
        ("E_cooldown14_alone", 0.0, 0.0, False, 14),
        ("E_cooldown30_alone", 0.0, 0.0, False, 30),
        ("E_cooldown14_plus_res17500", BEST_RESERVE_THRESHOLD, 0.0, False, 14),
        ("BDE_combined_best_guess", BEST_RESERVE_THRESHOLD, 300.0, True, 14),
    ]

    all_rows = []
    for ceiling in (1000.0, 3000.0):
        print(f"\n{'='*100}\nPLAFOND {ceiling:.0f}$\n{'='*100}")
        for label, min_reserve, emerg, prio, cooldown in configs:
            t0 = time.time()
            df = run_propagated(pop, market_data, excluded_map, ceiling, min_reserve, emerg, prio, cooldown,
                                 n_sims, seed=700)
            df.to_csv(f"structural_{label}_ceiling{int(ceiling)}.csv", index=False)
            p5 = df["final_net"].quantile(0.05)
            n_neg = (df["final_net"] < 0).sum()
            n_frozen = df["was_ever_fully_frozen"].sum()
            n_frozen_end = df["frozen_at_end"].sum()
            row = dict(ceiling=ceiling, config=label, n=len(df), profit_final_mean=df["final_net"].mean(), p5=p5,
                       p_ruine_pct=n_neg / len(df) * 100,
                       full_structure_month_median=df["full_structure_month"].median(),
                       n_ever_fully_frozen=n_frozen, n_frozen_at_end=n_frozen_end,
                       recovery_rate_pct=(1 - n_frozen_end / max(1, n_frozen)) * 100)
            all_rows.append(row)
            print(f"[{label}] profit final moy={row['profit_final_mean']:+,.0f}$ | P5={p5:+,.0f}$ | "
                  f"P(ruine)={row['p_ruine_pct']:.2f}% | delai median={row['full_structure_month_median']} mois | "
                  f"gel total au moins 1 fois={n_frozen}/{len(df)} | gel a la fin={n_frozen_end}/{len(df)} | "
                  f"taux de recuperation post-gel-total={row['recovery_rate_pct']:.1f}% ({time.time()-t0:.0f}s)")
            pd.DataFrame(all_rows).to_csv("structural_mechanisms_summary.csv", index=False)

    pd.DataFrame(all_rows).to_csv("structural_mechanisms_summary.csv", index=False)
    print(f"\nTermine en {time.time()-t_start:.0f}s.")
