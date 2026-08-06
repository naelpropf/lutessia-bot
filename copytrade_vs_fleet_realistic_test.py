"""
Compare COPYTRADE (même signal répliqué sur 3 comptes/firms, cf. copytrade_simulation_test.py)
vs FLOTTE DIVERSIFIÉE (un signal va au compte le moins chargé parmi les 3, cf.
fleet_simulation_test.py -- routage account_router.select_account()), avec le payoff TP2
RÉALISTE (tp2_realistic_payoff.py), à la config de référence : seuil rr_tp1 >= 1.5,
risque 2%/compte, plafond 3 positions/compte, corrélation 0.6+JPY, scaling complet.

Différence structurelle : en copytrade, l'admission d'un signal est identique sur les 3
comptes (même filtre plafond/corrélation appliqué indépendamment mais sur le même flux
temporel -> même trades pris partout, cf. vérifié précédemment), donc chaque signal pris
expose 3x le risque total (une fois par compte). En flotte diversifiée, un signal ne va
qu'À UN SEUL compte (le moins chargé), donc le risque total par signal est 1x, mais le
système peut capturer PLUS de signaux au total (3 comptes = 3 fois plus de "slots"
disponibles pour des signaux différents).
"""
import random

import pandas as pd

import rr_threshold_test as rrt
from scaling_simulation import CORR_THRESHOLD, load_market_data
from monte_carlo_simulation import precompute_correlation_pairs, N_SIMULATIONS
from copytrade_simulation_test import (
    run_copytrade_one, summarize_copytrade, simulate_account_with_events, N_ACCOUNTS,
    build_block_bootstrap_order, BLOCK_MONTHS,
)
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from fleet_simulation_test import (
    run_fleet_one, summarize_fleet, run_fleet_deterministic, CORR_THRESHOLD_FLEET,
)
from tp2_realistic_payoff import build_realistic_payoff_population, build_trades_realistic

MIN_RR_TP1 = 1.5
RISK_PCT = 2.0


def deterministic_copytrade_monthly(trades, slot_arrivals, risk_pct, market_data, excluded_map, start_date):
    natural_order = list(range(len(trades)))
    account_runs = [
        simulate_account_with_events(trades, slot_arrivals, natural_order, risk_pct, market_data, excluded_map, start_date)
        for _ in range(N_ACCOUNTS)
    ]
    combined_net_det = sum(r["net_profit"] for r in account_runs)

    all_events = []
    for r in account_runs:
        all_events.extend(r["events"])
    ev_df = pd.DataFrame(all_events, columns=["date", "net", "palier"])
    ev_df["month_index"] = ev_df["date"].apply(lambda d: (d.year - start_date.year) * 12 + (d.month - start_date.month))
    n_months = ev_df["month_index"].max() + 1

    palier_by_month = {}
    for i, r in enumerate(account_runs):
        acc_ev = pd.DataFrame(r["events"], columns=["date", "net", "palier"])
        acc_ev["month_index"] = acc_ev["date"].apply(lambda d: (d.year - start_date.year) * 12 + (d.month - start_date.month))
        palier_by_month[i] = acc_ev.groupby("month_index")["palier"].last().reindex(range(n_months)).ffill().bfill()

    combined_palier_by_month = sum(palier_by_month.values())
    monthly_net = ev_df.groupby("month_index")["net"].sum().reindex(range(n_months), fill_value=0.0)
    monthly_pct = monthly_net / combined_palier_by_month * 100
    return combined_net_det, monthly_pct.std(), monthly_pct.mean(), n_months, [r["broken_count"] for r in account_runs]


def deterministic_fleet_monthly(trades, slot_arrivals, risk_pct, market_data, excluded_map, start_date):
    accounts, events, n_taken_det, net_profit_det = run_fleet_deterministic(
        trades, slot_arrivals, risk_pct, market_data, excluded_map
    )
    ev_df = pd.DataFrame(events, columns=["date", "net", "combined_palier"])
    ev_df["month_index"] = ev_df["date"].apply(lambda d: (d.year - start_date.year) * 12 + (d.month - start_date.month))
    n_months = ev_df["month_index"].max() + 1

    monthly = ev_df.groupby("month_index").agg(net=("net", "sum"), palier_ref=("combined_palier", "last")).reindex(range(n_months))
    monthly["palier_ref"] = monthly["palier_ref"].ffill().bfill()
    monthly["net"] = monthly["net"].fillna(0.0)
    monthly_pct = monthly["net"] / monthly["palier_ref"] * 100
    return net_profit_det, monthly_pct.std(), monthly_pct.mean(), n_months, n_taken_det, [a["broken_count"] for a in accounts]


def main():
    pop, _ = build_realistic_payoff_population(min_rr=MIN_RR_TP1, verbose=True)
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)

    sub, trades, slot_arrivals = build_trades_realistic(pop)
    tickers = sorted(set(t["ticker"] for t in trades))
    excluded_map_copytrade = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)
    excluded_map_fleet = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD_FLEET)

    start_date = sub["date_creation"].iloc[0]
    date_min, date_max = sub["date_creation"].min(), sub["date_creation"].max()
    span_years = (date_max - date_min).days / 365.25

    print(f"\nSeuil rr_tp1 >= {MIN_RR_TP1}, risque {RISK_PCT}%/compte, payoff TP2 RÉALISTE, {span_years:.2f} ans réels")
    print(f"Pool de signaux disponibles : {len(sub)}\n")

    # --- COPYTRADE ---
    block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
    blocks = build_blocks(trades, slot_arrivals, block_seconds)
    total_horizon_seconds = slot_arrivals[-1]

    rng = random.Random(42)
    copytrade_results = []
    for _ in range(N_SIMULATIONS):
        trades_run, slots_run, order = build_block_bootstrap_order(
            trades, slot_arrivals, blocks, block_seconds, rng, total_horizon_seconds
        )
        copytrade_results.append(run_copytrade_one(trades_run, slots_run, RISK_PCT, market_data, excluded_map_copytrade, order))
    mc_copytrade = summarize_copytrade(copytrade_results)
    net_det_ct, std_ct, mean_ct, n_months_ct, broken_ct = deterministic_copytrade_monthly(
        trades, slot_arrivals, RISK_PCT, market_data, excluded_map_copytrade, start_date
    )

    taken_copytrade = rrt.taken_trades(pop, corr_matrix)
    pct_captes_copytrade = len(taken_copytrade) / len(sub) * 100

    print("=" * 100)
    print(f"COPYTRADE (3 comptes, même signal répliqué) — {N_SIMULATIONS} simulations")
    print("=" * 100)
    print(f"Signaux pris PAR COMPTE (identiques sur les 3 -- admission ne dépend que du temps/ticker, "
          f"pas de l'état P&L du compte) : {len(taken_copytrade)}/{len(sub)} ({pct_captes_copytrade:.1f}%)")
    print(f"Profit net combiné moyen   : {mc_copytrade['mean_profit']:+,.0f}€")
    print(f"Profit net combiné médian  : {mc_copytrade['median_profit']:+,.0f}€")
    print(f"5e percentile combiné      : {mc_copytrade['p5_profit']:+,.0f}€")
    print(f"P(perte nette)             : {mc_copytrade['pct_loss']:.1f}%")
    print(f"Casses combinées (moyenne) : {mc_copytrade['mean_broken_count']:.2f}")
    print(f"Écart-type mensuel combiné : {std_ct:.2f}%")
    print(f"Casses par compte (déterministe) : {broken_ct}")
    print()

    # --- FLOTTE DIVERSIFIÉE ---
    rng = random.Random(42)
    fleet_results = [run_fleet_one(trades, slot_arrivals, RISK_PCT, market_data, excluded_map_fleet, rng)
                      for _ in range(N_SIMULATIONS)]
    mc_fleet = summarize_fleet(fleet_results)
    mean_n_taken_fleet = sum(r["n_taken"] for r in fleet_results) / len(fleet_results)
    net_det_fl, std_fl, mean_fl, n_months_fl, n_taken_det_fl, broken_fl = deterministic_fleet_monthly(
        trades, slot_arrivals, RISK_PCT, market_data, excluded_map_fleet, start_date
    )

    print("=" * 100)
    print(f"FLOTTE DIVERSIFIÉE (3 comptes, 1 signal -> 1 compte le moins chargé) — {N_SIMULATIONS} simulations")
    print("=" * 100)
    print(f"Signaux pris en moyenne (MC) : {mean_n_taken_fleet:.1f}/{len(sub)} ({mean_n_taken_fleet/len(sub)*100:.1f}%)")
    print(f"Signaux pris (déterministe)  : {n_taken_det_fl}/{len(sub)} ({n_taken_det_fl/len(sub)*100:.1f}%)")
    print(f"Profit net combiné moyen   : {mc_fleet['mean_profit']:+,.0f}€")
    print(f"Profit net combiné médian  : {mc_fleet['median_profit']:+,.0f}€")
    print(f"5e percentile combiné      : {mc_fleet['p5_profit']:+,.0f}€")
    print(f"P(perte nette)             : {mc_fleet['pct_loss']:.1f}%")
    print(f"Casses combinées (moyenne) : {mc_fleet['mean_broken_count']:.2f}")
    print(f"Écart-type mensuel combiné : {std_fl:.2f}%")
    print(f"Casses par compte (déterministe) : {broken_fl}")
    print()

    print("=" * 100)
    print("TABLEAU COMPARATIF — COPYTRADE vs FLOTTE DIVERSIFIÉE (payoff TP2 réaliste)")
    print("=" * 100)
    comp_df = pd.DataFrame([
        {"structure": "copytrade", "mean_profit": mc_copytrade["mean_profit"], "median_profit": mc_copytrade["median_profit"],
         "p5_profit": mc_copytrade["p5_profit"], "mean_broken_count": mc_copytrade["mean_broken_count"],
         "monthly_std_pct": std_ct, "pct_signaux_captes": pct_captes_copytrade},
        {"structure": "flotte_diversifiee", "mean_profit": mc_fleet["mean_profit"], "median_profit": mc_fleet["median_profit"],
         "p5_profit": mc_fleet["p5_profit"], "mean_broken_count": mc_fleet["mean_broken_count"],
         "monthly_std_pct": std_fl, "pct_signaux_captes": mean_n_taken_fleet / len(sub) * 100},
    ])
    print(comp_df.to_string(index=False))
    comp_df.to_csv("copytrade_vs_fleet_realistic_summary.csv", index=False)
    print("\nRésumé enregistré dans copytrade_vs_fleet_realistic_summary.csv")
    return comp_df


if __name__ == "__main__":
    main()
