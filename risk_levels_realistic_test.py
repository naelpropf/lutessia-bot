"""
Refait le tableau de comparaison des niveaux de risque par trade (0.5%, 1%, 1.5%, 2%,
3%) -- déjà produit ce matin avec le payoff rr_tp1 (copytrade_risk_levels_summary.csv)
-- mais avec le payoff TP2 RÉALISTE (tp2_realistic_payoff.py : rr_tp2 si continuation
TP1->TP2 vérifiée, rr_tp1 sinon), sur la config de référence : COPYTRADE 3 comptes,
seuil rr_tp1 >= 1.5, plafond 3 positions/compte, corrélation 0.6+JPY, scaling
50k->200k->500k (+8%/-10%, 4 jours min, réserve 80%, upgrades 1000€/3000€), faisabilité
marge(1:30)/100 lots. Résultat toujours FLOTTE COMBINÉE (3 comptes).
"""
import random

import pandas as pd

from scaling_simulation import CORR_THRESHOLD, load_market_data
from monte_carlo_simulation import precompute_correlation_pairs, N_SIMULATIONS
from copytrade_simulation_test import run_copytrade_one, summarize_copytrade, build_block_bootstrap_order, BLOCK_MONTHS
from copytrade_risk_levels_test import run_deterministic_monthly_std
from tp2_realistic_payoff import build_realistic_payoff_population, build_trades_realistic
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH

RISK_LEVELS = [0.5, 1.0, 1.5, 2.0, 3.0]
MIN_RR_TP1 = 1.5

OLD_RR_TP1_SUMMARY = "copytrade_risk_levels_summary.csv"


def main():
    pop, _ = build_realistic_payoff_population(min_rr=MIN_RR_TP1, verbose=True)
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)

    sub, trades, slot_arrivals = build_trades_realistic(pop)
    tickers = sorted(set(t["ticker"] for t in trades))
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    start_date = sub["date_creation"].iloc[0]
    date_min = sub["date_creation"].min()
    date_max = sub["date_creation"].max()
    span_years = (date_max - date_min).days / 365.25

    old_df = None
    try:
        old_df = pd.read_csv(OLD_RR_TP1_SUMMARY)
    except FileNotFoundError:
        pass

    print(f"\nCOPYTRADE {3} comptes, seuil rr_tp1 >= {MIN_RR_TP1}, payoff TP2 RÉALISTE")
    print(f"Période couverte : {date_min} -> {date_max} ({span_years:.2f} ans réels)")
    print(f"Pool de signaux disponibles : {len(sub)}\n")

    block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
    blocks = build_blocks(trades, slot_arrivals, block_seconds)
    total_horizon_seconds = slot_arrivals[-1]

    rows = []
    for risk_pct in RISK_LEVELS:
        rng = random.Random(42)
        results = []
        for _ in range(N_SIMULATIONS):
            trades_run, slots_run, order = build_block_bootstrap_order(
                trades, slot_arrivals, blocks, block_seconds, rng, total_horizon_seconds
            )
            results.append(run_copytrade_one(trades_run, slots_run, risk_pct, market_data, excluded_map, order))
        mc = summarize_copytrade(results)

        combined_net_det, monthly_std, monthly_mean, n_months, cum_net = run_deterministic_monthly_std(
            trades, slot_arrivals, risk_pct, market_data, excluded_map, start_date
        )

        row = {"risk_pct_per_account": risk_pct, "span_years": span_years, **mc,
               "monthly_std_pct": monthly_std, "monthly_mean_pct": monthly_mean,
               "net_profit_deterministic": combined_net_det}

        if old_df is not None:
            old_row = old_df[old_df["risk_pct_per_account"] == risk_pct]
            if not old_row.empty:
                old_mean = old_row["mean_profit"].iloc[0]
                row["ancien_mean_profit_rr_tp1"] = old_mean
                row["ratio_vs_ancien"] = mc["mean_profit"] / old_mean if old_mean else float("nan")

        rows.append(row)

        print("=" * 100)
        print(f"RISQUE {risk_pct}% PAR COMPTE — COPYTRADE — TP2 RÉALISTE — {N_SIMULATIONS} simulations")
        print("=" * 100)
        print(f"Profit net combiné moyen (total cumulé sur {span_years:.2f} ans)  : {mc['mean_profit']:+,.0f}€")
        print(f"Profit net combiné médian                                        : {mc['median_profit']:+,.0f}€")
        print(f"5e percentile                                                    : {mc['p5_profit']:+,.0f}€")
        print(f"P(perte nette)                                                   : {mc['pct_loss']:.1f}%")
        print(f"Casses combinées (moyenne, 3 comptes)                            : {mc['mean_broken_count']:.2f}")
        print(f"Écart-type mensuel du rendement combiné                          : {monthly_std:.2f}%")
        if "ancien_mean_profit_rr_tp1" in row:
            print(f"--- Comparaison ancienne convention rr_tp1 (ce matin) ---")
            print(f"Ancien profit net moyen (rr_tp1)                                 : {row['ancien_mean_profit_rr_tp1']:+,.0f}€")
            print(f"Ratio TP2 réaliste / rr_tp1                                      : x{row['ratio_vs_ancien']:.2f}")
        print()

    summary_df = pd.DataFrame(rows)
    summary_df.to_csv("risk_levels_realistic_summary.csv", index=False)

    print("=" * 100)
    print("TABLEAU COMPARATIF FINAL")
    print("=" * 100)
    cols = ["risk_pct_per_account", "mean_profit", "median_profit", "p5_profit",
            "mean_broken_count", "monthly_std_pct"]
    if "ancien_mean_profit_rr_tp1" in summary_df.columns:
        cols += ["ancien_mean_profit_rr_tp1", "ratio_vs_ancien"]
    print(summary_df[cols].to_string(index=False))
    print("\nRésumé enregistré dans risk_levels_realistic_summary.csv")
    return summary_df


if __name__ == "__main__":
    main()
