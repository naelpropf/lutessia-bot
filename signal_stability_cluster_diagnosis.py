"""
Verifie l'hypothese jamais mesuree directement : les casses groupees de la
categorie 2 (flotte activee puis figee) surviennent-elles parce que tous les
comptes recoivent LE MEME signal Lutessia simultanement (copytrade -- meme
trade_idx synthetique, meme tick de la boucle principale), ou par coincidence
de sequences independantes convergeant par hasard vers la meme fenetre ?

Architecture testee : groupee + reserve 30k$ (meilleure config retenue).
Chaque break est journalise avec (slot_idx, now, ticker, outcome_r, account_id)
-- slot_idx = identifiant EXACT du signal synthetique dans la sequence
bootstrappee (deux comptes qui cassent au meme slot_idx ont, par construction
de la boucle principale, traite EXACTEMENT le meme signal au meme instant).
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
BEST_RESERVE_THRESHOLD = 30000.0
COLLAPSE_WINDOW_DAYS = 14  # fenetre finale analysee pour le cluster de casses


def run_one(trades, slot_arrivals, market_data, excluded_map, order, ceiling, min_reserve_for_unlock):
    seq_map = build_group_seq_map(SEQ_GROUPED, {STARTER: 25000})
    accounts_by_group = {}
    active0_cost = 0.0
    for group_names, trigger in SEQ_GROUPED:
        for gname in group_names:
            gdef = GROUP_DEFS[gname]
            is_day0 = trigger == "day0"
            accs = make_accounts_for_group(gname, gdef, active=is_day0, seq_map=seq_map)
            for i, a in enumerate(accs):
                a["uid"] = f"{gname}_{i+1}"
            accounts_by_group[gname] = accs
            if is_day0:
                active0_cost += sum(a["cost"] for a in accs)

    state = {"reserve": 0.0, "ever_funded": False, "real_cash_paid": active0_cost, "total_breaks": 0,
             "group_funded_count": 0, "group_own_funded": set(), "hit_ceiling": False,
             "group_funded_count_ever_ge1": False}
    pending_group_trigger = [(names, trig) for names, trig in SEQ_GROUPED if trig != "day0"]
    pending_reopen = []
    pending_group_open = []
    break_log = []  # (slot_idx, now, ticker, outcome_r, rr_tp1, account_uid)

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

    def process_trade(acc, trade, now, daily_loss_pct, slot_idx, cost_override=None):
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
            break_log.append((slot_idx, now, trade["ticker"], trade["outcome_r"], acc["uid"]))
            cost = cost_override if cost_override is not None else acc["cost"]
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
                process_trade(acc, trade, now, gdef["dd"], slot_idx, cost_override=cost_now)
                if was_challenge and acc["phase"] == "funded" and gname not in state["group_own_funded"]:
                    state["group_own_funded"].add(gname)
                    state["group_funded_count"] += 1
                    state["group_funded_count_ever_ge1"] = True

        process_growth_upgrade()
        process_pending(pending_reopen)
        process_pending(pending_group_open)

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

    return {"final_net": combined_net(), "group_funded_count_ever_ge1": state["group_funded_count_ever_ge1"],
            "frozen_at_end": n_active_accounts() == 0, "break_log": break_log}


def analyze_run(res):
    """Pour un run categorie 2 (active puis fige) : isole le cluster de
    casses des COLLAPSE_WINDOW_DAYS avant la derniere casse, et mesure la
    part de signaux partages (meme slot_idx entre au moins 2 comptes)."""
    log = res["break_log"]
    if not log:
        return None
    last_time = max(e[1] for e in log)
    window_start = last_time - COLLAPSE_WINDOW_DAYS * DAY_SECONDS
    cluster = [e for e in log if e[1] >= window_start]
    if len(cluster) < 2:
        return None
    slot_idxs = [e[0] for e in cluster]
    n_events = len(cluster)
    n_unique_signals = len(set(slot_idxs))
    from collections import Counter
    counts = Counter(slot_idxs)
    n_events_sharing_signal = sum(c for c in counts.values() if c >= 2)
    tickers = [e[2] for e in cluster]
    outcomes = [e[3] for e in cluster]
    times_sorted = sorted(e[1] for e in cluster)
    gaps_days = [(times_sorted[i + 1] - times_sorted[i]) / DAY_SECONDS for i in range(len(times_sorted) - 1)]
    return dict(n_events=n_events, n_unique_signals=n_unique_signals,
                pct_events_same_signal=n_events_sharing_signal / n_events * 100,
                mean_outcome_r_in_cluster=np.mean(outcomes), tickers=tickers,
                mean_gap_days=np.mean(gaps_days) if gaps_days else None,
                span_days=(times_sorted[-1] - times_sorted[0]) / DAY_SECONDS)


def run_propagated(pop, market_data, excluded_map, ceiling, min_reserve, n_sims, seed):
    rng_wr = random.Random(seed)
    rng_boot = random.Random(seed + 1)
    results = []
    for _ in range(n_sims):
        wr_draw = rng_wr.betavariate(ALPHA_POST, BETA_POST)
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_draw, 1.0, False, random.Random(rng_wr.random()))
        block_seconds = 2 * DAYS_PER_MONTH * DAY_SECONDS
        blocks = build_blocks(trades, slot_arrivals, block_seconds)
        target_duration = slot_arrivals[-1]
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot, target_duration)
        order = list(range(len(raw_trades)))
        res = run_one(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, min_reserve)
        results.append(res)
    return results


if __name__ == "__main__":
    import sys
    t_start = time.time()
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 600

    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers_all = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers_all, corr_matrix, CORR_TH)

    all_cluster_stats = []
    for ceiling in (1000.0, 3000.0):
        print(f"\n{'='*100}\nPLAFOND {ceiling:.0f}$\n{'='*100}")
        results = run_propagated(pop, market_data, excluded_map, ceiling, BEST_RESERVE_THRESHOLD, n_sims, seed=900)
        n_neg = sum(1 for r in results if r["final_net"] < 0)
        cat2_frozen = [r for r in results if r["final_net"] < 0 and r["group_funded_count_ever_ge1"] and r["frozen_at_end"]]
        print(f"Runs negatifs : {n_neg}/{len(results)} | categorie 2 (fleet activee, figee a la fin) : {len(cat2_frozen)}")

        stats = [analyze_run(r) for r in cat2_frozen]
        stats = [s for s in stats if s is not None]
        print(f"Clusters analysables (>=2 casses dans les {COLLAPSE_WINDOW_DAYS}j finaux) : {len(stats)}/{len(cat2_frozen)}")

        if stats:
            df_stats = pd.DataFrame(stats)
            df_stats.to_csv(f"cluster_diagnosis_detail_ceiling{int(ceiling)}.csv", index=False)
            pct_same_signal_mean = df_stats["pct_events_same_signal"].mean()
            pct_same_signal_median = df_stats["pct_events_same_signal"].median()
            avg_events = df_stats["n_events"].mean()
            avg_unique = df_stats["n_unique_signals"].mean()
            print(f"\n=== RESULTAT CLE ===")
            print(f"Nb moyen de casses dans le cluster final : {avg_events:.2f}")
            print(f"Nb moyen de SIGNAUX DISTINCTS impliques : {avg_unique:.2f}")
            print(f"Part des casses qui PARTAGENT le meme signal qu'au moins une autre (meme slot_idx) : "
                  f"moyenne={pct_same_signal_mean:.1f}% | mediane={pct_same_signal_median:.1f}%")
            print(f"R moyen des trades du cluster (vs population generale ~+0.97R) : {df_stats['mean_outcome_r_in_cluster'].mean():+.3f}")
            print(f"Ecart temporel moyen entre casses consecutives (independantes) : {df_stats['mean_gap_days'].mean():.2f}j | "
                  f"etalement moyen du cluster : {df_stats['span_days'].mean():.2f}j")
            all_tickers = [t for row in df_stats["tickers"] for t in row]
            from collections import Counter
            print(f"Tickers les plus frequents dans les clusters : {Counter(all_tickers).most_common(8)}")

        all_cluster_stats.append(dict(ceiling=ceiling, n_negatif=n_neg, n_cat2_frozen=len(cat2_frozen),
                                       n_clusters_analysables=len(stats),
                                       pct_same_signal_mean=(pd.DataFrame(stats)["pct_events_same_signal"].mean() if stats else None)))

    pd.DataFrame(all_cluster_stats).to_csv("cluster_diagnosis_summary.csv", index=False)
    print(f"\nTermine en {time.time()-t_start:.0f}s.")
