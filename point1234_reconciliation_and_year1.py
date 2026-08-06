"""
Suite du 07/08 (2e relance) : reconciliation cash pire cas vs creux mensuel,
correction du winrate mal etiquete, rendement mensuel %, et analyse fine
annee 1 -- TOUT sous la config FINALE verrouillee (RR>=1,25/trail0,15xSL/
maxpos=3/corr=0,6/rampe 2,0%x5 trades/The5%ers retardee evenementiel).

RECONCILIATION (point 1) : "cash pire cas" (13 986$/18 981$, deja rapporte)
mesure `real_cash_paid` -- argent REELLEMENT sorti de la poche, monotone
croissant, PLAFONNE des qu'un compte quelconque de la flotte finance une
premiere fois (immunite globale) et que la reserve poolee (80% des gains
finances) peut absorber les couts de casse/upgrade suivants. Le fichier de
trajectoire mensuelle precedent tracait `combined_net` -- le P&L NET cumule
(profit finance moins TOUTES les commissions de challenge/casse/upgrade
payees, y compris celles couvertes par la reserve) -- une mesure de
performance comptable, PAS un besoin de cash reel. combined_net peut plonger
loin en negatif tot dans l'horizon (accumulation de couts de challenge avant
le premier financement) sans que cela corresponde a un seul dollar reellement
sorti de la poche au-dela de real_cash_paid, PARCE QUE la reserve poolee
absorbe une grande partie de ces couts des que le POOL existe (meme avant
l'immunite complete -- le pool peut deja contenir des gains d'un compte
finance plus tot). CE N'EST PAS UN BUG : deux metriques legitimement
differentes, functionnellement non comparables sans clarification. Ce script
sort desormais LES DEUX, mensuellement, avec des noms explicites.

CORRECTION WINRATE (point 2) : le winrate reel de la population RR>=1,25/
trail0,15 est 40,09% (n=646, wins=259) -- le prochain fichier etait
mal-etiquete "37,29%" (constante recopiee de l'ancienne population RR>=1,5,
n=472) alors que le code utilisait bien wr_target=None (= winrate reel actuel
de la population chargee, donc 40,09% en pratique -- calcul deja correct,
SEULE l'etiquette etait fausse). Le "32% P10 bayesien" etait lui aussi
reconduit tel quel de l'ancien echantillon (n=472) -- recalibre ici sur
n=646 : posterior Beta(1+wins, 1+pertes) avec prior uniforme Beta(1,1),
methode verifiee par reproduction de l'IC95% historique connu sur l'ancien
echantillon ([33,04%,41,74%] retrouve vs [32,9%,41,7%] documente -- coherent).
Nouveau P10 bayesien (n=646) = 37,66% (PAS 32%).
"""
import random
import time

import numpy as np
import pandas as pd

import robustness_5ers_risk_challenge as eng
import point3a_ramp_fixed as ramp_eng
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs

POP_CONSTRUCT_SEED = 123
TARGET_RISK = 2.5
RAMP_RISK, RAMP_N = 2.0, 5
MAXPOS, CORR_TH = 3, 0.6
DAY_SECONDS = 86400
MONTH_SECONDS = DAYS_PER_MONTH * DAY_SECONDS
N_SIMULATIONS = 2000
YEAR1_SECONDS = 365.25 * DAY_SECONDS

REAL_WINRATE = None          # 40.09% (population reelle, pas de degradation)
BAYESIAN_P10_WINRATE = 0.3766  # recalibre sur n=646, cf. docstring


def run_one_full_tracking(trades, slot_arrivals, market_data, excluded_map, order, month_marks):
    fivers = [eng.make_acc(eng.PALIER_5ERS, eng.SUMMER_COST, active=False) for _ in range(eng.N_5ERS)]
    growth = [eng.make_acc(eng.TIER_SEQUENCE_BY_FIRM[f][0], eng.CHALLENGE_COST_BY_FIRM[f][eng.TIER_SEQUENCE_BY_FIRM[f][0]])
              for f in eng.GROWTH_FIRMS]
    growth_cost0 = sum(a["cost"] for a in growth)
    state = {"reserve": 0.0, "ever_funded": False, "real_cash_paid": growth_cost0,
             "total_breaks": 0, "fivers_activated_at": None}
    fivers_cost0 = eng.SUMMER_COST * eng.N_5ERS

    marks_sorted = sorted(month_marks)
    mark_idx = 0
    monthly_net, monthly_cash, monthly_capital = [], [], []

    running_min_year1 = 0.0
    year1_dipped_below_5000 = False
    year1_negative_months = 0  # nb de marques mensuelles (<=12) ou combined_net<0
    consecutive_negative = 0
    max_consecutive_negative = 0

    def combined_net():
        return sum(a["total_funded_pnl"] - a["total_fees_paid"] for a in fivers + growth)

    def capital_deployed():
        # CORRECTION : gater sur phase=="funded" cree un artefact d'alternance
        # (un compte qui vient d'upgrader repasse brievement en "challenge", et cette
        # transition se synchronise avec les marques mensuelles -> capital_deploye
        # oscille artificiellement entre 0 et plusieurs centaines de milliers$ d'un
        # mois sur l'autre). Le palier nominal d'un compte ACTIF (funded OU en
        # challenge sur ce palier) represente deja le capital reellement engage/risque
        # -- pas de gate sur la phase.
        return sum(a["palier"] for a in fivers + growth if a["active"])

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]

        while mark_idx < len(marks_sorted) and now > marks_sorted[mark_idx]:
            net_now = combined_net()
            monthly_net.append(net_now)
            monthly_cash.append(state["real_cash_paid"])
            monthly_capital.append(capital_deployed())
            if mark_idx < 12:
                if net_now < 0:
                    consecutive_negative += 1
                    max_consecutive_negative = max(max_consecutive_negative, consecutive_negative)
                    year1_negative_months += 1
                else:
                    consecutive_negative = 0
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

        if now <= YEAR1_SECONDS:
            net_now = combined_net()
            running_min_year1 = min(running_min_year1, net_now)
            if net_now <= -5000:
                year1_dipped_below_5000 = True

    while mark_idx < len(marks_sorted):
        net_now = combined_net()
        monthly_net.append(net_now)
        monthly_cash.append(state["real_cash_paid"])
        monthly_capital.append(capital_deployed())
        if mark_idx < 12:
            if net_now < 0:
                consecutive_negative += 1
                max_consecutive_negative = max(max_consecutive_negative, consecutive_negative)
                year1_negative_months += 1
            else:
                consecutive_negative = 0
        mark_idx += 1

    return {
        "monthly_net": monthly_net, "monthly_cash": monthly_cash, "monthly_capital": monthly_capital,
        "running_min_year1": running_min_year1, "year1_dipped_below_5000": year1_dipped_below_5000,
        "year1_negative_months_count": year1_negative_months, "max_consecutive_negative_year1": max_consecutive_negative,
        "final_breaks": state["total_breaks"],
    }


def main():
    t_start = time.time()
    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

    n = len(pop)
    wins = int((pop["statut_final"] == "OBJECTIF ATTEINT").sum())
    print(f"Population RR>=1.25/trail0.15 : n={n}, wins={wins}, winrate REEL = {wins/n*100:.2f}%")

    summary_rows = []
    for wr_label, wr_target, suffix in [("40.09%_reel", REAL_WINRATE, "40_09pct"),
                                        ("37.66%_P10bayesien_recalibre", BAYESIAN_P10_WINRATE, "37_66pct")]:
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_target, 1.0, False, random.Random(POP_CONSTRUCT_SEED))
        total_horizon = slot_arrivals[-1]
        n_months = int(total_horizon // MONTH_SECONDS) + 2
        month_marks = [m * MONTH_SECONDS for m in range(1, n_months)]
        block_seconds = eng.BLOCK_MONTHS * DAYS_PER_MONTH * 86400
        blocks = build_blocks(trades, slot_arrivals, block_seconds)

        rng = random.Random(42)
        all_monthly_net, all_monthly_cash, all_monthly_capital = [], [], []
        running_mins, dipped_flags, neg_months_counts, max_consec_list = [], [], [], []
        year1_net_list, final_net_list, final_cash_list = [], [], []

        print(f"\n{wr_label} : {N_SIMULATIONS} runs, {len(month_marks)} points mensuels...")
        t0 = time.time()
        for _ in range(N_SIMULATIONS):
            raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, total_horizon)
            order = list(range(len(raw_trades)))
            res = run_one_full_tracking(raw_trades, raw_slots, market_data, excluded_map, order, month_marks)
            all_monthly_net.append(res["monthly_net"])
            all_monthly_cash.append(res["monthly_cash"])
            all_monthly_capital.append(res["monthly_capital"])
            running_mins.append(res["running_min_year1"])
            dipped_flags.append(res["year1_dipped_below_5000"])
            neg_months_counts.append(res["year1_negative_months_count"])
            max_consec_list.append(res["max_consecutive_negative_year1"])
            idx_year1 = min(11, len(res["monthly_net"]) - 1)
            year1_net_list.append(res["monthly_net"][idx_year1])
            final_net_list.append(res["monthly_net"][-1])
            final_cash_list.append(res["monthly_cash"][-1])
        print(f"  ({time.time()-t0:.0f}s)")

        monthly_net_arr = np.array(all_monthly_net)
        monthly_cash_arr = np.array(all_monthly_cash)
        monthly_capital_arr = np.array(all_monthly_capital)

        traj_rows = []
        for m in range(monthly_net_arr.shape[1]):
            col_net = monthly_net_arr[:, m]
            col_cash = monthly_cash_arr[:, m]
            col_cap = monthly_capital_arr[:, m]
            prev_col_net = monthly_net_arr[:, m - 1] if m > 0 else np.zeros(len(col_net))
            monthly_gain = col_net - prev_col_net
            with np.errstate(divide="ignore", invalid="ignore"):
                monthly_return_pct = np.where(col_cap > 0, monthly_gain / col_cap * 100, np.nan)
            traj_rows.append({
                "mois": m + 1,
                "net_p10": np.percentile(col_net, 10), "net_median": np.percentile(col_net, 50),
                "net_p90": np.percentile(col_net, 90), "net_mean": col_net.mean(),
                "cash_p10": np.percentile(col_cash, 10), "cash_median": np.percentile(col_cash, 50),
                "cash_p90": np.percentile(col_cash, 90), "cash_max": col_cash.max(),
                "p_net_negatif": (col_net < 0).mean() * 100,
                "capital_deploye_median": np.percentile(col_cap, 50),
                "rendement_pct_mean": np.nanmean(monthly_return_pct),
                "rendement_pct_std": np.nanstd(monthly_return_pct),
                "rendement_pct_p10": np.nanpercentile(monthly_return_pct, 10) if not np.all(np.isnan(monthly_return_pct)) else np.nan,
                "rendement_pct_median": np.nanpercentile(monthly_return_pct, 50) if not np.all(np.isnan(monthly_return_pct)) else np.nan,
                "rendement_pct_p90": np.nanpercentile(monthly_return_pct, 90) if not np.all(np.isnan(monthly_return_pct)) else np.nan,
            })
        traj_df = pd.DataFrame(traj_rows)
        traj_df.to_csv(f"point1234_monthly_trajectory_{suffix}.csv", index=False)

        running_mins_arr = np.array(running_mins)
        year1_net_arr = np.array(year1_net_list)
        final_net_arr = np.array(final_net_list)
        final_cash_arr = np.array(final_cash_list)

        row = {
            "winrate": wr_label,
            "cash_pire_cas_final": final_cash_arr.max(),
            "creux_min_year1_p10": np.percentile(running_mins_arr, 10),
            "creux_min_year1_median": np.percentile(running_mins_arr, 50),
            "creux_min_year1_p90": np.percentile(running_mins_arr, 90),
            "creux_min_year1_worst": running_mins_arr.min(),
            "p_year1_negatif_fin_annee": (year1_net_arr < 0).mean() * 100,
            "p_dipped_below_5000_year1": np.mean(dipped_flags) * 100,
            "p_dipped_below_5000_ET_finit_positif": np.mean([d and (y >= 0) for d, y in zip(dipped_flags, year1_net_arr)]) * 100,
            "neg_months_count_median": np.median(neg_months_counts),
            "neg_months_count_p90": np.percentile(neg_months_counts, 90),
            "max_consecutive_negative_median": np.median(max_consec_list),
            "max_consecutive_negative_p90": np.percentile(max_consec_list, 90),
            "profit_final_median": np.median(final_net_arr),
        }
        summary_rows.append(row)

        print(f"  Cash pire cas (real_cash_paid, fin d'horizon) : {row['cash_pire_cas_final']:,.0f}$")
        print(f"  Creux MIN combined_net pendant annee1 (continu, pas juste mensuel) : "
              f"P10={row['creux_min_year1_p10']:,.0f}$ | median={row['creux_min_year1_median']:,.0f}$ | "
              f"P90={row['creux_min_year1_p90']:,.0f}$ | pire={row['creux_min_year1_worst']:,.0f}$")
        print(f"  P(annee1 negative, fin d'annee) : {row['p_year1_negatif_fin_annee']:.2f}%")
        print(f"  P(creux > 5000$ sous zero pendant annee1) : {row['p_dipped_below_5000_year1']:.2f}%")
        print(f"  ... dont finissent quand meme positifs en fin d'annee1 : "
              f"{row['p_dipped_below_5000_ET_finit_positif']:.2f}%")
        print(f"  Mois negatifs (sur 12) : mediane {row['neg_months_count_median']:.0f} | P90 {row['neg_months_count_p90']:.0f}")
        print(f"  Sequence max de mois consecutifs negatifs : mediane {row['max_consecutive_negative_median']:.0f} | "
              f"P90 {row['max_consecutive_negative_p90']:.0f}")

    pd.DataFrame(summary_rows).to_csv("point1234_summary.csv", index=False)
    print(f"\nTerminé en {time.time()-t_start:.0f}s.")


if __name__ == "__main__":
    main()
