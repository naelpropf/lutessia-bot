"""
Parties A + C (suite p5_negative_diagnosis.py) :

A. Teste 2 leviers de resserrement du goulot pre-premier-financement :
   1. Palier Blueberry reduit (10000$ au lieu de 25000$) -- cout par tentative
      plus bas.
   2. Deblocage force de REST_GROUPS apres N casses de Blueberry SANS jamais
      avoir finance -- escape hatch specifique a la phase pre-financement
      uniquement (ne touche pas au declencheur evenementiel apres le 1er
      financement, deja tranche).
   + combinaison des deux.

C. Sur le run baseline (BB_TIER=25000, pas de deblocage force -- config
   actuellement verrouillee), decompose les runs negatifs en :
   - Categorie 1 : group_funded_count JAMAIS >= 1 (Blueberry n'a jamais
     finance) -- echec au tout premier goulot.
   - Categorie 2 : group_funded_count >= 1 atteint (flotte activee) mais figee
     plus tard quand meme -- effondrement apres demarrage.
   Marques trimestrielles (16 marques sur ~4 ans) pour localiser le mois de gel.
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
REST_GROUPS = ("FTMO", "Fivers", "GFT", "FundedNext")
QUARTER_MARKS = [i * 0.25 for i in range(1, 17)]  # 0.25 an ... 4.0 ans


def handle_cost_hybrid(cost, state, ceiling, pending_list, pending_key, on_success):
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


def process_pending(state, pending_list):
    i = 0
    while i < len(pending_list):
        item = pending_list[i]
        if state["reserve"] >= item["cost_remaining"]:
            state["reserve"] -= item["cost_remaining"]
            item["on_success"]()
            pending_list.pop(i)
        else:
            i += 1


def run_one(trades, slot_arrivals, market_data, excluded_map, order, ceiling, bb_tier, force_unlock_n):
    sequence = [((STARTER,), "day0"), (REST_GROUPS, ("after_count", 1))]
    first_tier_overrides = {STARTER: bb_tier}
    seq_map = build_group_seq_map(sequence, first_tier_overrides)
    accounts_by_group = {}
    active0_cost = 0.0
    for group_names, trigger in sequence:
        for gname in group_names:
            gdef = GROUP_DEFS[gname]
            is_day0 = trigger == "day0"
            accs = make_accounts_for_group(gname, gdef, active=is_day0, seq_map=seq_map)
            accounts_by_group[gname] = accs
            if is_day0:
                active0_cost += sum(a["cost"] for a in accs)

    state = {"reserve": 0.0, "ever_funded": False, "real_cash_paid": active0_cost, "total_breaks": 0,
             "group_funded_count": 0, "group_own_funded": set(), "hit_ceiling": False,
             "full_structure_month": None, "blueberry_breaks_pre_funding": 0,
             "group_funded_count_ever_ge1": False, "group_funded_first_month": None,
             "force_unlocked": False}
    pending_group_trigger = [(names, trig) for names, trig in sequence if trig != "day0"]
    pending_reopen = []
    pending_group_open = []

    def combined_net():
        return sum(a["total_funded_pnl"] - a["total_fees_paid"] for accs in accounts_by_group.values() for a in accs)

    def n_active_accounts():
        return sum(1 for accs in accounts_by_group.values() for a in accs if a["active"])

    def n_groups_with_active():
        return sum(1 for accs in accounts_by_group.values() if any(a["active"] for a in accs))

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

    def process_trade(acc, trade, now, daily_loss_pct, gname, cost_override=None):
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
            if gname == STARTER and not state["group_funded_count_ever_ge1"]:
                state["blueberry_breaks_pre_funding"] += 1
            cost = cost_override if cost_override is not None else acc["cost"]
            acc["active"] = False
            handle_cost_hybrid(cost, state, ceiling, pending_reopen, id(acc), lambda a=acc, c=cost: reopen_account(a, c))
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

    marks_sorted = [m * YEAR_SECONDS for m in QUARTER_MARKS]
    mark_idx = 0
    snapshots = []

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]

        while mark_idx < len(marks_sorted) and now > marks_sorted[mark_idx]:
            snapshots.append((marks_sorted[mark_idx], combined_net(), state["real_cash_paid"], state["total_breaks"],
                               n_active_accounts(), n_groups_with_active(), state["group_funded_count"]))
            mark_idx += 1

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
                    if not state["group_funded_count_ever_ge1"]:
                        state["group_funded_count_ever_ge1"] = True
                        state["group_funded_first_month"] = now / MONTH_SECONDS

        process_growth_upgrade()
        process_pending(state, pending_reopen)
        process_pending(state, pending_group_open)

        if (force_unlock_n is not None and not state["force_unlocked"] and state["group_funded_count"] == 0
                and state["blueberry_breaks_pre_funding"] >= force_unlock_n):
            state["force_unlocked"] = True
            for gname in REST_GROUPS:
                cost0 = sum(a["cost"] for a in accounts_by_group[gname])
                handle_cost_hybrid(cost0, state, ceiling, pending_group_open, gname,
                                   lambda g=gname: open_group(g))

        still_pending = []
        for group_names, trig in pending_group_trigger:
            _, n_req = trig
            if state["group_funded_count"] >= n_req:
                for gname in group_names:
                    cost0 = sum(a["cost"] for a in accounts_by_group[gname])
                    handle_cost_hybrid(cost0, state, ceiling, pending_group_open, gname,
                                       lambda g=gname: open_group(g))
            else:
                still_pending.append((group_names, trig))
        pending_group_trigger = still_pending

        if state["full_structure_month"] is None and structure_complete():
            state["full_structure_month"] = now / MONTH_SECONDS

    while mark_idx < len(marks_sorted):
        snapshots.append((marks_sorted[mark_idx], combined_net(), state["real_cash_paid"], state["total_breaks"],
                           n_active_accounts(), n_groups_with_active(), state["group_funded_count"]))
        mark_idx += 1

    return {
        "final_net": snapshots[-1][1], "real_cash_paid": state["real_cash_paid"], "hit_ceiling": state["hit_ceiling"],
        "group_funded_count_final": state["group_funded_count"], "group_funded_count_ever_ge1": state["group_funded_count_ever_ge1"],
        "group_funded_first_month": state["group_funded_first_month"], "full_structure_month": state["full_structure_month"],
        "snapshots": snapshots,
    }


def run_propagated(pop, market_data, excluded_map, ceiling, bb_tier, force_unlock_n, n_sims, seed):
    rng_wr = random.Random(seed)
    rng_boot = random.Random(seed + 1)
    rows = []
    all_snaps = []
    for _ in range(n_sims):
        wr_draw = rng_wr.betavariate(ALPHA_POST, BETA_POST)
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_draw, 1.0, False, random.Random(rng_wr.random()))
        block_seconds = 2 * DAYS_PER_MONTH * DAY_SECONDS
        blocks = build_blocks(trades, slot_arrivals, block_seconds)
        target_duration = slot_arrivals[-1]
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot, target_duration)
        order = list(range(len(raw_trades)))
        res = run_one(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, bb_tier, force_unlock_n)
        res["wr_draw"] = wr_draw
        all_snaps.append(res.pop("snapshots"))
        rows.append(res)
    return pd.DataFrame(rows), all_snaps


if __name__ == "__main__":
    import sys
    t_start = time.time()
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 600

    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

    configs = [
        ("baseline_25k_noUnlock", 25000, None),
        ("bb10k_noUnlock", 10000, None),
        ("bb25k_unlock4", 25000, 4),
        ("bb10k_unlock4", 10000, 4),
    ]

    all_summary = []
    baseline_snaps_by_ceiling = {}
    for ceiling in (1000.0, 3000.0):
        print(f"\n{'='*100}\nPLAFOND {ceiling:.0f}$\n{'='*100}")
        for label, bb_tier, unlock_n in configs:
            t0 = time.time()
            df, snaps = run_propagated(pop, market_data, excluded_map, ceiling, bb_tier, unlock_n, n_sims, seed=300)
            df.to_csv(f"ramp_tighten_{label}_ceiling{int(ceiling)}.csv", index=False)
            p5 = df["final_net"].quantile(0.05)
            n_neg = (df["final_net"] < 0).sum()
            row = dict(ceiling=ceiling, config=label, bb_tier=bb_tier, unlock_n=unlock_n, n=len(df),
                       profit_final_mean=df["final_net"].mean(), p5=p5, p_ruine_pct=n_neg / len(df) * 100)
            all_summary.append(row)
            print(f"[{label}] profit final moy={row['profit_final_mean']:+,.0f}$ | P5={p5:+,.0f}$ | "
                  f"P(ruine)={row['p_ruine_pct']:.2f}% ({time.time()-t0:.0f}s)")
            if label == "baseline_25k_noUnlock":
                baseline_snaps_by_ceiling[ceiling] = (df, snaps)

        pd.DataFrame(all_summary).to_csv("ramp_tighten_summary.csv", index=False)

    pd.DataFrame(all_summary).to_csv("ramp_tighten_summary.csv", index=False)

    # ---- Partie C : decomposition categorie 1 vs categorie 2 sur le baseline ----
    print(f"\n{'='*100}\nPARTIE C -- DECOMPOSITION DES RUNS NEGATIFS (baseline 25k, pas de deblocage force)\n{'='*100}")
    c_rows = []
    for ceiling, (df, snaps) in baseline_snaps_by_ceiling.items():
        neg_mask = df["final_net"] < 0
        neg_idx = df[neg_mask].index.tolist()
        cat1 = [i for i in neg_idx if not df.loc[i, "group_funded_count_ever_ge1"]]
        cat2 = [i for i in neg_idx if df.loc[i, "group_funded_count_ever_ge1"]]
        print(f"\n--- Plafond {ceiling:.0f}$ : {len(neg_idx)} runs negatifs ---")
        print(f"  Categorie 1 (Blueberry jamais finance) : {len(cat1)} ({len(cat1)/max(1,len(neg_idx))*100:.1f}%) | "
              f"profit final moy={df.loc[cat1,'final_net'].mean() if cat1 else float('nan'):+,.0f}$")
        print(f"  Categorie 2 (flotte activee puis figee) : {len(cat2)} ({len(cat2)/max(1,len(neg_idx))*100:.1f}%) | "
              f"profit final moy={df.loc[cat2,'final_net'].mean() if cat2 else float('nan'):+,.0f}$")
        if cat2:
            print(f"  Categorie 2 -- mois de 1er financement (moy)={df.loc[cat2,'group_funded_first_month'].mean():.2f} | "
                  f"structure complete atteinte : {df.loc[cat2,'full_structure_month'].notna().mean()*100:.1f}%")
            # localise le mois de gel : dernier quart ou breaks augmente encore
            freeze_months = []
            n_active_at_freeze = []
            for i in cat2:
                snap = snaps[i]
                breaks_series = [s[3] for s in snap]
                last_change_idx = 0
                for qi in range(1, len(breaks_series)):
                    if breaks_series[qi] != breaks_series[qi - 1]:
                        last_change_idx = qi
                freeze_months.append(QUARTER_MARKS[last_change_idx] * 12)
                n_active_at_freeze.append(snap[last_change_idx][4])
            print(f"  Categorie 2 -- mois de gel (dernier changement de casses) : moyenne={np.mean(freeze_months):.1f} | "
                  f"median={np.median(freeze_months):.1f} | n_comptes_actifs_au_gel moy={np.mean(n_active_at_freeze):.1f}")
        c_rows.append(dict(ceiling=ceiling, n_negatif=len(neg_idx), n_cat1=len(cat1), n_cat2=len(cat2),
                            cat1_pct=len(cat1) / max(1, len(neg_idx)) * 100, cat2_pct=len(cat2) / max(1, len(neg_idx)) * 100))
    pd.DataFrame(c_rows).to_csv("collapse_decomposition_summary.csv", index=False)

    print(f"\nTermine en {time.time()-t_start:.0f}s.")
