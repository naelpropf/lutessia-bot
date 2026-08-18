"""
Suite de ramp_tightening_and_collapse.py : la Partie C precedente a montre que
87-100% des runs negatifs viennent d'un effondrement TOTAL simultane de toute
la flotte 1,5-2,5 mois apres l'ouverture GROUPEE du reste des firms (FTMO+
Fivers+GFT+FundedNext d'un coup, ~3500$ de cout ponctuel, 9 comptes actifs
avec un seul historique). Teste 2 leviers pour etaler/conditionner cette
ouverture :

1. RESERVE MINIMALE avant deblocage groupe : ajoute une condition
   supplementaire (state["reserve"] >= seuil) au declencheur "after_count"
   existant -- ne touche pas au principe evenementiel deja tranche, ajoute
   juste une 2e condition evenementielle.
2. OUVERTURE ETALEE : au lieu d'un seul palier ("after_count",1) qui debloque
   les 4 firms d'un coup, une sequence de paliers ("after_count",1/2/3/4) qui
   ouvre un firm a la fois, chacun conditionne au financement du precedent --
   reutilise TEL QUEL le mecanisme pending_group_trigger deja existant (aucun
   nouveau code de declenchement necessaire, juste une SEQUENCE differente).
   Ordre choisi : FTMO, GFT, FundedNext (moins chers, ~333-666$) avant Fivers
   (le plus cher ~2180$ et le DD le plus serre 3%, ouvert en dernier).
3. Combinaison des deux.
4. Recaracterise Categorie 1 vs Categorie 2 sous la meilleure config.
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
QUARTER_MARKS = [i * 0.25 for i in range(1, 17)]

SEQ_GROUPED = [((STARTER,), "day0"), (("FTMO", "Fivers", "GFT", "FundedNext"), ("after_count", 1))]
SEQ_STAGGERED = [((STARTER,), "day0"), (("FTMO",), ("after_count", 1)), (("GFT",), ("after_count", 2)),
                 (("FundedNext",), ("after_count", 3)), (("Fivers",), ("after_count", 4))]


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


def run_one(trades, slot_arrivals, market_data, excluded_map, order, ceiling, sequence, min_reserve_for_unlock):
    first_tier_overrides = {STARTER: 25000}
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
             "full_structure_month": None, "group_funded_count_ever_ge1": False,
             "group_funded_first_month": None}
    pending_group_trigger = [(names, trig) for names, trig in sequence if trig != "day0"]
    pending_reopen = []
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
            snapshots.append((marks_sorted[mark_idx], combined_net(), state["total_breaks"], n_active_accounts()))
            mark_idx += 1

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
                    if not state["group_funded_count_ever_ge1"]:
                        state["group_funded_count_ever_ge1"] = True
                        state["group_funded_first_month"] = now / MONTH_SECONDS

        process_growth_upgrade()
        process_pending(state, pending_reopen)
        process_pending(state, pending_group_open)

        still_pending = []
        for group_names, trig in pending_group_trigger:
            _, n_req = trig
            if state["group_funded_count"] >= n_req and state["reserve"] >= min_reserve_for_unlock:
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
        snapshots.append((marks_sorted[mark_idx], combined_net(), state["total_breaks"], n_active_accounts()))
        mark_idx += 1

    return {
        "final_net": snapshots[-1][1], "real_cash_paid": state["real_cash_paid"], "hit_ceiling": state["hit_ceiling"],
        "group_funded_count_ever_ge1": state["group_funded_count_ever_ge1"],
        "group_funded_first_month": state["group_funded_first_month"], "full_structure_month": state["full_structure_month"],
        "snapshots": snapshots,
    }


def run_propagated(pop, market_data, excluded_map, ceiling, sequence, min_reserve_for_unlock, n_sims, seed):
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
        res = run_one(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, sequence, min_reserve_for_unlock)
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
        ("baseline_groupe", SEQ_GROUPED, 0.0),
        ("reserve500", SEQ_GROUPED, 500.0),
        ("reserve1000", SEQ_GROUPED, 1000.0),
        ("reserve2000", SEQ_GROUPED, 2000.0),
        ("reserve17500_5xcout", SEQ_GROUPED, 17500.0),
        ("etale_seul", SEQ_STAGGERED, 0.0),
        ("etale_plus_reserve_best", SEQ_STAGGERED, None),  # rempli apres coup avec le meilleur seuil de la partie 1
    ]

    all_summary = []
    best_snaps = {}
    for ceiling in (1000.0, 3000.0):
        print(f"\n{'='*100}\nPLAFOND {ceiling:.0f}$\n{'='*100}")
        best_reserve_for_ceiling = None
        best_ruine = 999.0
        results_this_ceiling = {}
        for label, sequence, min_reserve in configs:
            if min_reserve is None:
                min_reserve = best_reserve_for_ceiling
            t0 = time.time()
            df, snaps = run_propagated(pop, market_data, excluded_map, ceiling, sequence, min_reserve, n_sims, seed=400)
            df.to_csv(f"staggered_ramp_{label}_ceiling{int(ceiling)}.csv", index=False)
            p5 = df["final_net"].quantile(0.05)
            n_neg = (df["final_net"] < 0).sum()
            p_ruine = n_neg / len(df) * 100
            row = dict(ceiling=ceiling, config=label, min_reserve=min_reserve, n=len(df),
                       profit_final_mean=df["final_net"].mean(), p5=p5, p_ruine_pct=p_ruine,
                       full_structure_month_median=df["full_structure_month"].median(),
                       p_never_full_structure_pct=df["full_structure_month"].isna().mean() * 100)
            all_summary.append(row)
            print(f"[{label}] profit final moy={row['profit_final_mean']:+,.0f}$ | P5={p5:+,.0f}$ | "
                  f"P(ruine)={p_ruine:.2f}% | delai structure complete median={row['full_structure_month_median']} mois | "
                  f"P(jamais complet)={row['p_never_full_structure_pct']:.1f}% ({time.time()-t0:.0f}s)")
            results_this_ceiling[label] = (df, snaps)
            if label.startswith("reserve") and p_ruine < best_ruine:
                best_ruine = p_ruine
                best_reserve_for_ceiling = min_reserve

        pd.DataFrame(all_summary).to_csv("staggered_ramp_summary.csv", index=False)

        # meilleure config globale pour ce plafond = min p_ruine parmi toutes testees
        best_label = min(results_this_ceiling, key=lambda l: (results_this_ceiling[l][0]["final_net"] < 0).mean())
        best_snaps[ceiling] = (best_label, results_this_ceiling[best_label])

    pd.DataFrame(all_summary).to_csv("staggered_ramp_summary.csv", index=False)

    # ---- Partie 4 : redecomposition categorie 1 vs 2 sous la meilleure config ----
    print(f"\n{'='*100}\nRE-DECOMPOSITION CATEGORIE 1 vs 2 SOUS LA MEILLEURE CONFIG PAR PLAFOND\n{'='*100}")
    c_rows = []
    for ceiling, (best_label, (df, snaps)) in best_snaps.items():
        print(f"\n--- Plafond {ceiling:.0f}$ -- meilleure config = {best_label} ---")
        neg_idx = df[df["final_net"] < 0].index.tolist()
        cat1 = [i for i in neg_idx if not df.loc[i, "group_funded_count_ever_ge1"]]
        cat2 = [i for i in neg_idx if df.loc[i, "group_funded_count_ever_ge1"]]
        n_neg = len(neg_idx)
        print(f"  N negatifs={n_neg} ({n_neg/len(df)*100:.2f}%)")
        print(f"  Categorie 1 (Blueberry jamais finance) : {len(cat1)} ({len(cat1)/max(1,n_neg)*100:.1f}%)")
        print(f"  Categorie 2 (flotte activee puis figee) : {len(cat2)} ({len(cat2)/max(1,n_neg)*100:.1f}%)")
        if cat2:
            freeze_months = []
            n_active_at_freeze = []
            for i in cat2:
                snap = snaps[i]
                breaks_series = [s[2] for s in snap]
                last_change_idx = 0
                for qi in range(1, len(breaks_series)):
                    if breaks_series[qi] != breaks_series[qi - 1]:
                        last_change_idx = qi
                freeze_months.append(QUARTER_MARKS[last_change_idx] * 12)
                n_active_at_freeze.append(snap[last_change_idx][3])
            print(f"  Categorie 2 -- mois de gel : moyenne={np.mean(freeze_months):.1f} median={np.median(freeze_months):.1f} | "
                  f"n_comptes_actifs_au_gel moy={np.mean(n_active_at_freeze):.2f}")
        c_rows.append(dict(ceiling=ceiling, best_config=best_label, n_negatif=n_neg,
                            n_cat1=len(cat1), n_cat2=len(cat2)))
    pd.DataFrame(c_rows).to_csv("staggered_ramp_recategorization.csv", index=False)

    print(f"\nTermine en {time.time()-t_start:.0f}s.")
