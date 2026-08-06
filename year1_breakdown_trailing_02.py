"""
Décomposition annuelle du profit net FLOTTE COMBINÉE (copytrade 3 comptes, 2%/compte),
config de référence complète + trailing stop distance fixe 0.2xSL (confirmé meilleure
config, cf. trailing_02_full_test.py) :
  - Trajectoire déterministe (chronologie réelle, PAS Monte Carlo) : profit cumulé à
    la fin de chaque année (12/24/36/~47.5 mois), + palier atteint par compte à la fin
    de l'année 1.
  - Monte Carlo (2000 runs, block bootstrap 2 mois) restreint à l'année 1 seule :
    moyenne/médiane/5e percentile du profit net combiné après 12 mois.

CORRECTIF (2026-08-01) : `run_one_with_year1_snapshot` comptait AVANT cette date tout
le P&L de trading (y compris en phase "challenge") comme profit réel -- même bug
identifié et corrigé le même soir dans sizing_fleet_test.py, jamais propagé ici (cf.
monte_carlo_simulation.py / copytrade_simulation_test.py, même date). Réécrit pour
réutiliser le moteur pooled+immune+999€-fix de copytrade_simulation_test.py, avec
séquence bootstrap PAR BLOC de 2 mois (au lieu de la permutation simple) pour l'année 1
Monte Carlo. year1_breakdown_trailing_02_summary.csv généré avant cette date surestimait
le profit net d'environ 30-40% -- régénéré.
"""
import random

import pandas as pd

from scaling_simulation import CORR_THRESHOLD, TIER_SEQUENCE, load_market_data
from monte_carlo_simulation import precompute_correlation_pairs, N_SIMULATIONS
from copytrade_simulation_test import (
    simulate_account_with_events, run_copytrade_one, N_ACCOUNTS,
    build_block_bootstrap_order, BLOCK_MONTHS,
)
from trailing_payoff_population import build_population_with_trailing, build_trades_trailing
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH

RISK_PCT = 2.0
YEAR_SECONDS = 365.25 * 86400


def main():
    pop = build_population_with_trailing("fixed", 0.2, verbose=True)
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    sub, trades, slot_arrivals = build_trades_trailing(pop)
    tickers = sorted(set(t["ticker"] for t in trades))
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)
    start_date = sub["date_creation"].iloc[0]

    # --- Trajectoire déterministe (chronologie réelle) ---
    natural_order = list(range(len(trades)))
    account_runs = [
        simulate_account_with_events(trades, slot_arrivals, natural_order, RISK_PCT, market_data, excluded_map, start_date)
        for _ in range(N_ACCOUNTS)
    ]

    all_events = []
    for i, r in enumerate(account_runs):
        for (date, net, palier) in r["events"]:
            all_events.append({"account": i, "date": date, "net": net, "palier": palier})
    ev_df = pd.DataFrame(all_events)
    ev_df["day_index"] = (ev_df["date"] - start_date).dt.days

    print("\n" + "=" * 100)
    print("TRAJECTOIRE DÉTERMINISTE (chronologie réelle) — profit net combiné cumulé par fin d'année")
    print("=" * 100)
    milestones = [("Fin année 1", 365), ("Fin année 2", 730), ("Fin année 3", 1095), ("Fin période (~47.5 mois)", 999999)]
    for label, day_cutoff in milestones:
        cum = ev_df[ev_df["day_index"] <= day_cutoff]["net"].sum()
        print(f"  {label:28s} : profit net combiné cumulé = {cum:+,.0f}€")

    print("\nPalier atteint PAR COMPTE à la fin de l'année 1 (jour 365) :")
    for i in range(N_ACCOUNTS):
        acc_ev = ev_df[(ev_df["account"] == i) & (ev_df["day_index"] <= 365)]
        palier_y1 = acc_ev["palier"].iloc[-1] if not acc_ev.empty else TIER_SEQUENCE[0]
        net_y1 = acc_ev["net"].sum()
        print(f"  Compte {i+1} : palier = {palier_y1:,}€ | net cumulé année 1 = {net_y1:+,.0f}€")

    # --- Monte Carlo restreint à l'année 1 (block bootstrap 2 mois) ---
    print("\n" + "=" * 100)
    print(f"MONTE CARLO — ANNÉE 1 SEULE ({N_SIMULATIONS} runs, block bootstrap {BLOCK_MONTHS} mois)")
    print("=" * 100)
    block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
    blocks = build_blocks(trades, slot_arrivals, block_seconds)

    rng = random.Random(42)
    year1_profits = []
    year1_breaks = []
    year1_cash = []
    for _ in range(N_SIMULATIONS):
        trades_run, slots_run, order = build_block_bootstrap_order(trades, slot_arrivals, blocks, block_seconds, rng, YEAR_SECONDS)
        r = run_copytrade_one(trades_run, slots_run, RISK_PCT, market_data, excluded_map, order)
        year1_profits.append(r["net_profit"])
        year1_breaks.append(r["broken_count"])
        year1_cash.append(r["real_cash_paid"])

    year1_profits_sorted = sorted(year1_profits)
    n = len(year1_profits_sorted)
    mean_y1 = sum(year1_profits_sorted) / n
    median_y1 = year1_profits_sorted[n // 2]
    p5_y1 = year1_profits_sorted[int(0.05 * n)]
    pct_loss_y1 = sum(1 for p in year1_profits_sorted if p < 0) / n * 100
    mean_broken_y1 = sum(year1_breaks) / n
    cash_sorted = sorted(year1_cash)

    print(f"Profit net combiné moyen après 12 mois   : {mean_y1:+,.0f}€")
    print(f"Profit net combiné médian après 12 mois  : {median_y1:+,.0f}€")
    print(f"5e percentile après 12 mois              : {p5_y1:+,.0f}€")
    print(f"P(perte nette) après 12 mois              : {pct_loss_y1:.1f}%")
    print(f"Casses moyennes (3 comptes) après 12 mois : {mean_broken_y1:.2f}")
    print(f"Trésorerie perso -- moyenne {sum(cash_sorted)/n:,.0f}€ | pire cas {cash_sorted[-1]:,.0f}€")

    det_year1 = ev_df[ev_df["day_index"] <= 365]["net"].sum()
    print(f"\n[Rappel] Trajectoire déterministe (UN seul historique réel, pas une moyenne) : {det_year1:+,.0f}€")

    pd.DataFrame([{
        "mean_profit_year1": mean_y1, "median_profit_year1": median_y1, "p5_profit_year1": p5_y1,
        "pct_loss_year1": pct_loss_y1, "mean_broken_year1": mean_broken_y1,
        "mean_real_cash_year1": sum(cash_sorted) / n, "worst_real_cash_year1": cash_sorted[-1],
        "deterministic_year1": det_year1,
    }]).to_csv("year1_breakdown_trailing_02_summary.csv", index=False)
    print("\nRésumé enregistré dans year1_breakdown_trailing_02_summary.csv")


if __name__ == "__main__":
    main()
