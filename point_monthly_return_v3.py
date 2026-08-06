"""
Correction v3 du rendement mensuel (08/08) : la v2 gatait le NUMERATEUR
(combined_net, funded uniquement) mais pas systematiquement le DENOMINATEUR
(capital de tous les comptes actifs, funded OU en challenge) de la meme
facon d'un mois a l'autre -- des mois avec beaucoup de comptes en challenge
(capital compte, PnL funded quasi nul) alternaient avec des mois ou ces
comptes refinancent (capital identique, PnL funded qui rattrape d'un coup) ->
faux signal de volatilite ~27-29pt d'ecart-type.

Deux corrections :
1. "rendement_portefeuille_pct" : denominateur = capital FUNDED UNIQUEMENT
   (coherent avec le numerateur combined_net, qui ne compte que le PnL
   funded), mais MOYENNE sur tous les points d'echantillonnage a chaque
   trade du mois (pas un point-sample unique en fin de mois) -- lisse
   l'artefact de synchronisation challenge/funded.
2. "ev_pure_pct" (NOUVELLE metrique demandee) : moyenne de (r_trade x
   risque%_applique) sur TOUS les trades pris par TOUS les comptes actifs ce
   mois-la, quel que soit leur statut challenge/funded -- independante du
   capital deploye et du nombre de comptes, isole la performance du signal
   de trading pur de l'effet de compounding/scaling de la structure.
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
N_MONTHS_REPORT = 24


def process_trade_tracked(acc, trade, now, market_data, excluded_map, daily_loss_pct, max_dd_pct, state,
                          ramp_risk, ramp_n, target_risk, month_log, cost_override=None):
    """Identique a process_trade_ramp_pure mais journalise (r, risque%) de CHAQUE trade
    reellement pris (position ouverte) dans month_log[month_index], pour la metrique
    ev_pure_pct -- et suit aussi le capital funded a CHAQUE trade pour la moyenne."""
    if not acc["active"]:
        return False, False
    close_time = now + trade["hold_seconds"]
    acc["open_positions"] = [(t, c) for (t, c) in acc["open_positions"] if c > now]
    if len(acc["open_positions"]) >= eng.MAX_POSITIONS:
        return False, False
    if any(t in excluded_map[trade["ticker"]] for (t, _) in acc["open_positions"]):
        return False, False

    current_risk = ramp_risk if acc["trades_taken"] < ramp_n else target_risk
    eff_risk, _ = eng.feasible_risk_pct(trade["ticker"], trade["sl_distance"], acc["palier"], current_risk, market_data)
    risk_amount = eff_risk / 100 * acc["palier"]
    pnl = trade["outcome_r"] * risk_amount

    month_idx = int(now // MONTH_SECONDS)
    month_log.setdefault(month_idx, []).append((trade["outcome_r"], eff_risk))

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
    broke = (trailing_dd >= max_dd_pct / 100 * acc["palier"] or daily_dd >= daily_loss_pct / 100 * acc["palier"])

    just_funded = False
    if broke:
        state["total_breaks"] += 1
        cost = cost_override if cost_override is not None else acc["cost"]
        if state["reserve"] >= cost:
            state["reserve"] -= cost
        else:
            shortfall = cost - state["reserve"]
            state["reserve"] = 0.0
            if not state["ever_funded"]:
                state["real_cash_paid"] += shortfall
        acc["total_fees_paid"] += cost
        acc["phase"] = "challenge"
        acc["cumulative_since_reset"] = 0.0
        acc["peak_since_reset"] = 0.0
        acc["trading_days_since_reset"] = set()
        acc["daily_pnl"] = {}
        return False, True

    if (acc["phase"] == "challenge" and acc["cumulative_since_reset"] >= eng.CHALLENGE_TARGET_PCT / 100 * acc["palier"]
            and len(acc["trading_days_since_reset"]) >= eng.MIN_TRADING_DAYS):
        acc["phase"] = "funded"
        if not state["ever_funded"]:
            just_funded = True
        state["ever_funded"] = True
        acc["cumulative_since_reset"] = 0.0
        acc["peak_since_reset"] = 0.0
        acc["trading_days_since_reset"] = set()
    return just_funded, True


def run_one(trades, slot_arrivals, market_data, excluded_map, order, n_months_target):
    fivers = [eng.make_acc(eng.PALIER_5ERS, eng.SUMMER_COST, active=False) for _ in range(eng.N_5ERS)]
    growth = [eng.make_acc(eng.TIER_SEQUENCE_BY_FIRM[f][0], eng.CHALLENGE_COST_BY_FIRM[f][eng.TIER_SEQUENCE_BY_FIRM[f][0]])
              for f in eng.GROWTH_FIRMS]
    growth_cost0 = sum(a["cost"] for a in growth)
    state = {"reserve": 0.0, "ever_funded": False, "real_cash_paid": growth_cost0,
             "total_breaks": 0, "fivers_activated_at": None}
    fivers_cost0 = eng.SUMMER_COST * eng.N_5ERS

    month_log = {}
    # funded_capital_samples[m] : liste des capitaux FUNDED echantillonnes a chaque trade du mois m
    funded_capital_samples = {}
    monthly_combined_net_at_boundary = {}  # combined_net juste avant que le mois change (pour delta $)

    def combined_net():
        return sum(a["total_funded_pnl"] - a["total_fees_paid"] for a in fivers + growth)

    def capital_funded_now():
        return sum(a["palier"] for a in fivers + growth if a["active"] and a["phase"] == "funded")

    last_month_idx = -1
    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]
        month_idx = int(now // MONTH_SECONDS)
        if month_idx > last_month_idx:
            monthly_combined_net_at_boundary[month_idx] = combined_net()
            last_month_idx = month_idx
        if month_idx >= n_months_target:
            break

        for acc in fivers:
            cost_now = eng.SUMMER_COST if now < eng.PRICE_CUTOFF_SECONDS else eng.POST_SUMMER_COST_REAL
            _, taken = process_trade_tracked(acc, trade, now, market_data, excluded_map, eng.DAILY_LOSS_5ERS_REAL,
                                             eng.BREAK_DD_PCT, state, RAMP_RISK, RAMP_N, TARGET_RISK, month_log,
                                             cost_override=cost_now)
            if taken:
                funded_capital_samples.setdefault(month_idx, []).append(capital_funded_now())

        for acc in growth:
            just_funded, taken = process_trade_tracked(acc, trade, now, market_data, excluded_map,
                                                        eng.DAILY_LOSS_GROWTH, eng.BREAK_DD_PCT, state,
                                                        RAMP_RISK, RAMP_N, TARGET_RISK, month_log)
            if taken:
                funded_capital_samples.setdefault(month_idx, []).append(capital_funded_now())
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

    monthly_combined_net_at_boundary[last_month_idx + 1] = combined_net()

    return month_log, funded_capital_samples, monthly_combined_net_at_boundary


def main():
    t_start = time.time()
    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

    for wr_label, wr_target, suffix in [("40.09%_reel", None, "40_09pct"), ("37.66%_P10bayesien", 0.3766, "37_66pct")]:
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_target, 1.0, False, random.Random(POP_CONSTRUCT_SEED))
        total_horizon = slot_arrivals[-1]
        block_seconds = eng.BLOCK_MONTHS * DAYS_PER_MONTH * 86400
        blocks = build_blocks(trades, slot_arrivals, block_seconds)

        print(f"\n{wr_label} : {N_SIMULATIONS} runs...")
        t0 = time.time()
        rng = random.Random(42)
        # accumulateurs par mois (0..N_MONTHS_REPORT-1)
        ev_pure_runs = [[] for _ in range(N_MONTHS_REPORT)]
        portfolio_pct_runs = [[] for _ in range(N_MONTHS_REPORT)]

        for _ in range(N_SIMULATIONS):
            raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, total_horizon)
            order = list(range(len(raw_trades)))
            month_log, funded_cap_samples, net_boundary = run_one(raw_trades, raw_slots, market_data, excluded_map,
                                                                   order, N_MONTHS_REPORT)
            for m in range(N_MONTHS_REPORT):
                trades_m = month_log.get(m, [])
                if trades_m:
                    ev_pure = np.mean([r * (risk / 100) for r, risk in trades_m]) * 100
                    ev_pure_runs[m].append(ev_pure)
                cap_samples = funded_cap_samples.get(m, [])
                avg_cap = np.mean(cap_samples) if cap_samples else 0.0
                if avg_cap > 0 and m in net_boundary and (m + 1) in net_boundary:
                    gain = net_boundary[m + 1] - net_boundary[m]
                    portfolio_pct_runs[m].append(gain / avg_cap * 100)

        print(f"  ({time.time()-t0:.0f}s)")

        rows = []
        for m in range(N_MONTHS_REPORT):
            ev_arr = np.array(ev_pure_runs[m]) if ev_pure_runs[m] else np.array([np.nan])
            pf_arr = np.array(portfolio_pct_runs[m]) if portfolio_pct_runs[m] else np.array([np.nan])
            rows.append({
                "mois": m + 1,
                "ev_pure_pct_mean": np.nanmean(ev_arr), "ev_pure_pct_std": np.nanstd(ev_arr),
                "ev_pure_pct_p10": np.nanpercentile(ev_arr, 10), "ev_pure_pct_median": np.nanpercentile(ev_arr, 50),
                "ev_pure_pct_p90": np.nanpercentile(ev_arr, 90),
                "n_runs_avec_trades_ce_mois": len(ev_pure_runs[m]),
                "portefeuille_pct_mean": np.nanmean(pf_arr), "portefeuille_pct_std": np.nanstd(pf_arr),
                "portefeuille_pct_p10": np.nanpercentile(pf_arr, 10), "portefeuille_pct_median": np.nanpercentile(pf_arr, 50),
                "portefeuille_pct_p90": np.nanpercentile(pf_arr, 90),
                "n_runs_capital_funded_positif": len(portfolio_pct_runs[m]),
            })
        out = pd.DataFrame(rows)
        out.to_csv(f"point_monthly_return_v3_{suffix}.csv", index=False)
        print(out[["mois", "ev_pure_pct_mean", "ev_pure_pct_std", "portefeuille_pct_mean", "portefeuille_pct_std"]].head(24).to_string(index=False))

    print(f"\nTerminé en {time.time()-t_start:.0f}s.")


if __name__ == "__main__":
    main()
