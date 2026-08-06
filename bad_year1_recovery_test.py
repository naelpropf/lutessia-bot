"""
Parmi les 2000 runs Monte Carlo (block bootstrap 2 mois, régime 0.5%->2%@5000€,
copytrade 3 comptes), isole le sous-ensemble des runs où l'année 1 finit en perte
nette financée, et regarde CE SOUS-ENSEMBLE SEUL à l'horizon 4 ans :
  1. Profit net cumulé moyen/médian à la fin de l'année 4, pour ces runs.
  2. Proportion de ces runs "négatifs en année 1" qui finit positive en année 4.
  3. Trésorerie personnelle réelle CUMULÉE sur 4 ans (pas juste année 1) pour ces
     mêmes runs : moyenne, pire cas, P(>1000/2000/3000€).

Le block bootstrap permet de générer une trajectoire synthétique de 4 ans même si
l'historique réel ne couvre que 3.96 ans (les blocs de 2 mois sont rééchantillonnés
avec remise indéfiniment, cf. real_cash_risk_year1_block_bootstrap.py) -- donc
target_duration=4 ans est un choix explicite, pas une extrapolation cachée.
"""
import random

import pandas as pd

from scaling_simulation import CORR_THRESHOLD, load_market_data
from monte_carlo_simulation import precompute_correlation_pairs, N_SIMULATIONS
from trailing_payoff_population import build_population_with_trailing, build_trades_trailing
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence, run_one_hybrid_funded

N_ACCOUNTS = 3
YEAR_SECONDS = 365.25 * 86400
BLOCK_MONTHS = 2
TARGET_YEARS = 4


def run_fleet_multi_mark(blocks, block_seconds, market_data, excluded_map, rng, year_marks_seconds, target_duration):
    synthetic_trades, synthetic_slots = build_full_block_bootstrap_sequence(
        blocks, block_seconds, rng, target_duration
    )
    identity_order = list(range(len(synthetic_trades)))

    combined_net = [0.0] * len(year_marks_seconds)
    combined_cash = [0.0] * len(year_marks_seconds)
    for _ in range(N_ACCOUNTS):
        snaps, _, _ = run_one_hybrid_funded(
            synthetic_trades, synthetic_slots, market_data, excluded_map, identity_order, year_marks_seconds
        )
        for i, (_, net_p, cash_p) in enumerate(snaps):
            combined_net[i] += net_p
            combined_cash[i] += cash_p

    return combined_net, combined_cash


def main():
    pop = build_population_with_trailing("fixed", 0.2, verbose=False)
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    sub, trades, slot_arrivals = build_trades_trailing(pop)
    tickers = sorted(set(t["ticker"] for t in trades))
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
    blocks = build_blocks(trades, slot_arrivals, block_seconds)

    year_marks_seconds = [YEAR_SECONDS, TARGET_YEARS * YEAR_SECONDS]
    target_duration = TARGET_YEARS * YEAR_SECONDS

    rng = random.Random(42)
    rows = []
    for _ in range(N_SIMULATIONS):
        combined_net, combined_cash = run_fleet_multi_mark(
            blocks, block_seconds, market_data, excluded_map, rng, year_marks_seconds, target_duration
        )
        rows.append({
            "year1_net": combined_net[0], "year4_net": combined_net[1],
            "year1_cash": combined_cash[0], "year4_cash": combined_cash[1],
        })

    df = pd.DataFrame(rows)
    df.to_csv("bad_year1_recovery_detail.csv", index=False)

    n = len(df)
    bad_year1 = df[df["year1_net"] < 0]
    nb = len(bad_year1)

    print("=" * 100)
    print(f"SOUS-ENSEMBLE 'ANNÉE 1 EN PERTE' -- {nb}/{n} runs ({nb/n*100:.1f}%)")
    print("=" * 100)

    print("\n--- 1. Profit net cumulé à fin année 4 (sous-ensemble seul) ---")
    print(f"Moyenne : {bad_year1['year4_net'].mean():+,.0f}€")
    print(f"Médiane : {bad_year1['year4_net'].median():+,.0f}€")
    print(f"P5      : {bad_year1['year4_net'].quantile(0.05):+,.0f}€")
    print(f"P95     : {bad_year1['year4_net'].quantile(0.95):+,.0f}€")

    print("\n--- 2. Proportion qui redevient positive en année 4 ---")
    pct_recovered = (bad_year1["year4_net"] > 0).sum() / nb * 100
    print(f"{pct_recovered:.1f}% ({(bad_year1['year4_net'] > 0).sum()}/{nb})")

    print("\n--- 3. Trésorerie personnelle réelle CUMULÉE sur 4 ans (sous-ensemble seul) ---")
    cash = bad_year1["year4_cash"].sort_values()
    nc = len(cash)
    print(f"Moyenne  : {cash.mean():,.0f}€")
    print(f"Médiane  : {cash.median():,.0f}€")
    print(f"Pire cas : {cash.max():,.0f}€")
    for t in (1000, 2000, 3000, 5000):
        pct = (cash > t).sum() / nc * 100
        print(f"P(>{t}€)  : {pct:.2f}%")

    print("\n--- Comparaison : moyenne globale (tous runs, pas seulement 'année 1 en perte') ---")
    print(f"Profit net moyen année 4, TOUS runs : {df['year4_net'].mean():+,.0f}€")
    print(f"Trésorerie perso moyenne 4 ans, TOUS runs : {df['year4_cash'].mean():,.0f}€")

    print("\nDétail (2000 runs) enregistré dans bad_year1_recovery_detail.csv")


if __name__ == "__main__":
    main()
