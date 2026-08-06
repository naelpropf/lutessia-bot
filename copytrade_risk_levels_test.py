"""
Teste si répartir le risque agrégé en dollars (même exposition totale par signal)
sur un risque PLUS FAIBLE par compte, en mode COPYTRADE (3 comptes/firms, même
signal répliqué, chacun filtre indépendamment selon ses propres positions/plafond),
améliore la résilience sans sacrifier le rendement.

Niveaux testés : 0.67%, 1%, 1.5%, 2% (référence déjà connue : 1 333 357€ moyen).

Réutilise copytrade_simulation_test.py (run_copytrade_one pour le Monte Carlo,
simulate_account_with_events pour la trajectoire déterministe mensuelle/annuelle) —
seul le niveau de risque par compte change, tous les autres paramètres (seuil 1.5,
plafond 3 positions/compte, corrélation 0.6+JPY, scaling 50k->200k->500k, 4 jours
min, faisabilité marge/lots) restent identiques à la config validée.
"""
import random

import pandas as pd

from scaling_simulation import load_market_data, CORR_THRESHOLD
from monte_carlo_simulation import precompute_correlation_pairs, N_SIMULATIONS
from rr_threshold_test import build_extended_population
from fleet_simulation_test import build_trades
from copytrade_simulation_test import (
    run_copytrade_one, summarize_copytrade, simulate_account_with_events, N_ACCOUNTS,
)

THRESHOLD = 1.5
RISK_LEVELS = [0.67, 1.0, 1.5, 2.0]


def run_deterministic_monthly_std(trades, slot_arrivals, risk_pct, market_data, excluded_map, start_date):
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

    return combined_net_det, monthly_pct.std(), monthly_pct.mean(), n_months, monthly_net.cumsum()


def main():
    pop_full, _ = build_extended_population()
    pop = pop_full[pop_full["rr_tp1"] >= THRESHOLD].copy()
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)

    sub, trades, slot_arrivals = build_trades(pop)
    start_date = sub["date_creation"].iloc[0]
    end_date = sub["date_creation"].iloc[-1] if False else None
    tickers = sorted(set(t["ticker"] for t in trades))
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    date_min = sub["date_creation"].min()
    date_max = sub["date_creation"].max()
    span_years = (date_max - date_min).days / 365.25

    print(f"Seuil rr_tp1 >= {THRESHOLD}, mode COPYTRADE ({N_ACCOUNTS} comptes/firms), plafond 3 positions/compte, "
          f"corrélation 0.6+JPY, scaling complet")
    print(f"Période couverte : {date_min} -> {date_max} ({span_years:.2f} ans réels)")
    print(f"Pool de signaux disponibles : {len(sub)}\n")

    rows = []
    for risk_pct in RISK_LEVELS:
        rng = random.Random(42)
        results = [run_copytrade_one(trades, slot_arrivals, risk_pct, market_data, excluded_map, rng) for _ in range(N_SIMULATIONS)]
        mc = summarize_copytrade(results)

        combined_net_det, monthly_std, monthly_mean, n_months, cum_net = run_deterministic_monthly_std(
            trades, slot_arrivals, risk_pct, market_data, excluded_map, start_date
        )

        row = {"risk_pct_per_account": risk_pct, "span_years": span_years, **mc,
               "monthly_std_pct": monthly_std, "monthly_mean_pct": monthly_mean,
               "net_profit_deterministic": combined_net_det}
        rows.append(row)

        print("=" * 100)
        print(f"RISQUE {risk_pct}% PAR COMPTE — COPYTRADE — {N_SIMULATIONS} simulations — période {span_years:.2f} ans réels")
        print("=" * 100)
        print(f"Profit net combiné moyen (total cumulé sur {span_years:.2f} ans, PAS annuel)  : {mc['mean_profit']:+,.0f}€")
        print(f"Profit net combiné médian (total cumulé)                                       : {mc['median_profit']:+,.0f}€")
        print(f"5e percentile (total cumulé)                                                   : {mc['p5_profit']:+,.0f}€")
        print(f"Pire cas observé (total cumulé)                                                 : {mc['worst_profit']:+,.0f}€")
        print(f"P(perte nette)                                                                  : {mc['pct_loss']:.1f}%")
        print(f"Casses combinées (moyenne, 3 comptes)                                           : {mc['mean_broken_count']:.2f}")
        print(f"Écart-type mensuel du rendement combiné                                         : {monthly_std:.2f}%")
        print()

    summary_df = pd.DataFrame(rows)
    summary_df.to_csv("copytrade_risk_levels_summary.csv", index=False)
    print("Résumé enregistré dans copytrade_risk_levels_summary.csv")
    return summary_df


if __name__ == "__main__":
    main()
