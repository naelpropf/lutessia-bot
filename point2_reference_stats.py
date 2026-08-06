"""
Point 2 (07/08) : recalcul complet des statistiques de reference sous la
meilleure config identifiee au point 1 (RR>=1,25/trailing 0,15xSL, + les
leviers gagnants maxpos=2/corr=0,7 et rampe 2,0%/5 trades si confirmes
meilleurs par point1_combined_optimization.py).

Ajoute par rapport aux moteurs precedents :
- Snapshots MENSUELS (pas seulement annee1/final) -> trajectoire mediane +
  enveloppe P10-P90 du profit cumule
- Suivi du palier final de CHAQUE compte croissance (FTMO x2, Blueberry x1)
  par run -> P(atteindre chaque palier), percentiles
- P(cash > seuils cles), P(annee1 negative) -- deja fait ailleurs, recalcule
  ici pour coherence avec la nouvelle population
- Rendement mensuel moyen en phase MATURE (definie ici : mois 13+, apres
  immunite acquise dans la quasi-totalite des runs)
"""
import random
import time

import numpy as np
import pandas as pd

import robustness_5ers_risk_challenge as eng
import point3a_ramp_fixed as ramp_eng
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from trailing_payoff_population import build_population_with_trailing, build_trades_trailing
from monte_carlo_simulation import precompute_correlation_pairs

POP_CONSTRUCT_SEED = 123
TARGET_RISK = 2.5
RAMP_RISK, RAMP_N = 2.0, 5
# CORRECTION : point1_combined_optimization.py montre que maxpos=2/corr=0.7 DEGRADE
# la performance sous la population RR>=1.25/trail0.15 (plus de trades disponibles ->
# restreindre maxpos coute plus cher). La meilleure config reelle est "c" (RR1.25/
# trail0.15 + rampe2.0%/5 SEULE, maxpos/corr standard 3/0.6), pas "d" (tout combine).
MAXPOS, CORR_TH = 3, 0.6
DAY_SECONDS = 86400
MONTH_SECONDS = DAYS_PER_MONTH * DAY_SECONDS
N_SIMULATIONS = 2000


def run_one_tracked(trades, slot_arrivals, market_data, excluded_map, order, month_marks):
    fivers = [eng.make_acc(eng.PALIER_5ERS, eng.SUMMER_COST, active=False) for _ in range(eng.N_5ERS)]
    growth = [eng.make_acc(eng.TIER_SEQUENCE_BY_FIRM[f][0], eng.CHALLENGE_COST_BY_FIRM[f][eng.TIER_SEQUENCE_BY_FIRM[f][0]])
              for f in eng.GROWTH_FIRMS]
    growth_cost0 = sum(a["cost"] for a in growth)
    state = {"reserve": 0.0, "ever_funded": False, "real_cash_paid": growth_cost0,
             "total_breaks": 0, "fivers_activated_at": None}
    fivers_cost0 = eng.SUMMER_COST * eng.N_5ERS

    marks_sorted = sorted(month_marks)
    mark_idx = 0
    monthly_net, monthly_cash, monthly_breaks = [], [], []

    def combined_net():
        return sum(a["total_funded_pnl"] - a["total_fees_paid"] for a in fivers + growth)

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]
        while mark_idx < len(marks_sorted) and now > marks_sorted[mark_idx]:
            monthly_net.append(combined_net())
            monthly_cash.append(state["real_cash_paid"])
            monthly_breaks.append(state["total_breaks"])
            mark_idx += 1

        for acc in fivers:
            cost_now = eng.SUMMER_COST if now < eng.PRICE_CUTOFF_SECONDS else eng.POST_SUMMER_COST_REAL
            ramp_eng.process_trade_ramp_pure(acc, trade, now, market_data, excluded_map, eng.DAILY_LOSS_5ERS_REAL,
                                             eng.BREAK_DD_PCT, state, RAMP_RISK, RAMP_N, TARGET_RISK,
                                             cost_override=cost_now)

        for acc in growth:
            just_funded = ramp_eng.process_trade_ramp_pure(acc, trade, now, market_data, excluded_map,
                                                            eng.DAILY_LOSS_GROWTH, eng.BREAK_DD_PCT, state,
                                                            RAMP_RISK, RAMP_N, TARGET_RISK)
            if just_funded and state["fivers_activated_at"] is None:
                state["fivers_activated_at"] = now
                cost = fivers_cost0
                if state["reserve"] >= cost:
                    state["reserve"] -= cost
                else:
                    shortfall = cost - state["reserve"]
                    state["reserve"] = 0.0
                    if not state["ever_funded"]:
                        state["real_cash_paid"] += shortfall
                for a in fivers:
                    a["active"] = True
                    a["total_fees_paid"] = a["cost"]

        eng.process_growth_upgrade(growth, state)

    while mark_idx < len(marks_sorted):
        monthly_net.append(combined_net())
        monthly_cash.append(state["real_cash_paid"])
        monthly_breaks.append(state["total_breaks"])
        mark_idx += 1

    final_tiers = {}
    for i, acc in enumerate(growth):
        key = f"{eng.GROWTH_FIRMS[i]}_{i}"
        final_tiers[key] = acc["palier"]

    return monthly_net, monthly_cash, monthly_breaks, final_tiers


def main():
    t_start = time.time()
    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

    # --- Winrate/EV bruts de la population RR>=1.25/trail0.15 (pas de MC ici) ---
    outcome_r = np.where(pop["statut_final"] == "OBJECTIF ATTEINT", pop["r_trailing"], -1.0)
    winrate_raw = (pop["statut_final"] == "OBJECTIF ATTEINT").mean() * 100
    print(f"Population RR>=1.25/trail0.15 : n={len(pop)}, winrate={winrate_raw:.2f}%, EV moyen={outcome_r.mean():+.4f}R, "
          f"RR moyen gagnants={outcome_r[outcome_r>0].mean():.3f}")

    summary_rows = []
    for wr_label, wr_target, suffix in [("37.29%(reel_RR1.25)", None, "37_29pct"), ("32%(P10 bayesien)", 0.32, "32pct")]:
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_target, 1.0, False, random.Random(POP_CONSTRUCT_SEED))
        total_horizon = slot_arrivals[-1]
        n_months = int(total_horizon // MONTH_SECONDS) + 2
        month_marks = [m * MONTH_SECONDS for m in range(1, n_months)]
        block_seconds = eng.BLOCK_MONTHS * DAYS_PER_MONTH * 86400
        blocks = build_blocks(trades, slot_arrivals, block_seconds)

        orig_maxpos = eng.MAX_POSITIONS
        eng.MAX_POSITIONS = MAXPOS

        rng = random.Random(42)
        all_monthly_net, all_monthly_cash = [], []
        all_final_tiers = {f"{f}_{i}": [] for i, f in enumerate(eng.GROWTH_FIRMS)}
        year1_net_list, final_net_list, final_cash_list, final_breaks_list = [], [], [], []

        print(f"\n{wr_label} : {N_SIMULATIONS} runs, {len(month_marks)} points mensuels...")
        t0 = time.time()
        for sim_i in range(N_SIMULATIONS):
            raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, total_horizon)
            order = list(range(len(raw_trades)))
            monthly_net, monthly_cash, monthly_breaks, final_tiers = run_one_tracked(
                raw_trades, raw_slots, market_data, excluded_map, order, month_marks)
            all_monthly_net.append(monthly_net)
            all_monthly_cash.append(monthly_cash)
            for k, v in final_tiers.items():
                all_final_tiers[k].append(v)
            idx_year1 = min(11, len(monthly_net) - 1)
            year1_net_list.append(monthly_net[idx_year1])
            final_net_list.append(monthly_net[-1])
            final_cash_list.append(monthly_cash[-1])
            final_breaks_list.append(monthly_breaks[-1])

        eng.MAX_POSITIONS = orig_maxpos
        print(f"  ({time.time()-t0:.0f}s)")

        monthly_arr = np.array(all_monthly_net)
        cash_arr_monthly = np.array(all_monthly_cash)
        traj_rows = []
        for m in range(monthly_arr.shape[1]):
            col = monthly_arr[:, m]
            traj_rows.append({"mois": m + 1, "p10": np.percentile(col, 10), "p50_median": np.percentile(col, 50),
                              "p90": np.percentile(col, 90), "mean": col.mean()})
        traj_df = pd.DataFrame(traj_rows)
        traj_df.to_csv(f"point2_monthly_trajectory_{suffix}.csv", index=False)

        final_cash = np.array(final_cash_list)
        final_net = np.array(final_net_list)
        year1_net = np.array(year1_net_list)

        p_reach = {}
        for k, tiers in all_final_tiers.items():
            arr = np.array(tiers)
            p_reach[k] = {t: (arr >= t).mean() * 100 for t in sorted(set(arr))}

        rendement_mature = None
        if monthly_arr.shape[1] > 13:
            mature_growth = monthly_arr[:, 12:] - monthly_arr[:, 11:-1]
            rendement_mature = mature_growth.mean()

        row = {
            "winrate": wr_label,
            "profit_year1_median": np.median(year1_net), "profit_year1_p10": np.percentile(year1_net, 10),
            "profit_year1_p90": np.percentile(year1_net, 90),
            "profit_final_median": np.median(final_net), "profit_final_p10": np.percentile(final_net, 10),
            "profit_final_p90": np.percentile(final_net, 90), "profit_final_mean": final_net.mean(),
            "p_year1_negatif": (year1_net < 0).mean() * 100,
            "cash_worst": final_cash.max(), "cash_median": np.median(final_cash),
            "p_cash_gt_3000": (final_cash > 3000).mean() * 100,
            "p_cash_gt_10000": (final_cash > 10000).mean() * 100,
            "p_cash_gt_20000": (final_cash > 20000).mean() * 100,
            "rendement_mensuel_mature_moyen": rendement_mature,
            "casses_final_mean": np.mean(final_breaks_list),
        }
        for k, d in p_reach.items():
            for tier, pct in d.items():
                row[f"p_reach_{k}_{tier}"] = pct
        summary_rows.append(row)

        print(f"  Profit final : mediane {row['profit_final_median']:+,.0f}$ (P10 {row['profit_final_p10']:+,.0f}$ / "
              f"P90 {row['profit_final_p90']:+,.0f}$)")
        print(f"  Cash pire cas {row['cash_worst']:,.0f}$ | median {row['cash_median']:,.0f}$")
        print(f"  P(cash>3000$) {row['p_cash_gt_3000']:.1f}% | P(cash>10000$) {row['p_cash_gt_10000']:.1f}% | "
              f"P(cash>20000$) {row['p_cash_gt_20000']:.1f}%")
        print(f"  P(an1<0) {row['p_year1_negatif']:.2f}%")
        if rendement_mature is not None:
            print(f"  Rendement mensuel moyen phase mature (mois 13+) : {rendement_mature:+,.0f}$/mois")
        for k, d in p_reach.items():
            print(f"  P(palier {k}) : " + ", ".join(f"{t}$={p:.1f}%" for t, p in d.items()))

    pd.DataFrame(summary_rows).to_csv("point2_reference_stats_summary.csv", index=False)
    print(f"\nTerminé en {time.time()-t_start:.0f}s.")


if __name__ == "__main__":
    main()
