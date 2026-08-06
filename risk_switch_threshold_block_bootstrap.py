"""
Refait risk_switch_threshold_test.py (seuil de bascule 0.5%->2%, 5 déclencheurs) avec
le BLOCK BOOTSTRAP à 2 mois (real_cash_risk_year1_block_bootstrap.py) au lieu du
bootstrap par permutation -- celui qui a montré l'effet de queue le plus marqué sur le
risque de trésorerie réelle (pire cas x2.5, P(>3000€) +8.6 points vs permutation).

Réutilise TEL QUEL risk_switch_threshold_test.run_one_hybrid (logique de compte
inchangée : bascule irréversible au déclencheur, upgrade gaté par réserve, casse
couverte par la réserve en priorité) -- seule la construction de la séquence de
trades change (blocs de 2 mois rééchantillonnés avec remise, cf.
real_cash_risk_year1_block_bootstrap.py), exactement comme pour la trésorerie seule.
"""
import random

import pandas as pd

from scaling_simulation import CORR_THRESHOLD, load_market_data
from monte_carlo_simulation import precompute_correlation_pairs, N_SIMULATIONS
from trailing_payoff_population import build_population_with_trailing, build_trades_trailing
from risk_switch_threshold_test import run_one_hybrid, TRIGGERS as _BASE_TRIGGERS, N_ACCOUNTS, YEAR_SECONDS
from real_cash_risk_year1_block_bootstrap import build_blocks, build_block_bootstrap_sequence, DAYS_PER_MONTH

BLOCK_MONTHS = 2  # effet le plus marqué parmi 1/2/3 mois testés précédemment

# Étendu avec 7000€/10000€ (demandé après coup : à 5000€, P(>3000€) reste à 8.7% en
# block bootstrap, contre 3.45% en permutation -- teste si la queue continue à
# s'aplatir au-delà de 5000€, et à quel coût en profit).
TRIGGERS = dict(_BASE_TRIGGERS)
TRIGGERS["6. Réserve >= 7000€"] = 7000
TRIGGERS["7. Réserve >= 10000€"] = 10000


def run_copytrade_hybrid_year1_block(blocks, block_seconds, reserve_threshold, market_data, excluded_map, rng):
    synthetic_trades, synthetic_slots = build_block_bootstrap_sequence(blocks, block_seconds, rng)
    identity_order = list(range(len(synthetic_trades)))
    per_account = [
        run_one_hybrid(synthetic_trades, synthetic_slots, reserve_threshold, market_data, excluded_map,
                        rng=None, order=identity_order)
        for _ in range(N_ACCOUNTS)
    ]
    combined_real_cash = sum(r[0] for r in per_account)
    combined_net_profit = sum(r[1] for r in per_account)
    switch_time = per_account[0][2]  # identique sur les 3 comptes (même séquence synthétique)
    return combined_real_cash, combined_net_profit, switch_time


def main():
    pop = build_population_with_trailing("fixed", 0.2, verbose=False)
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    sub, trades, slot_arrivals = build_trades_trailing(pop)
    tickers = sorted(set(t["ticker"] for t in trades))
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
    blocks = build_blocks(trades, slot_arrivals, block_seconds)

    print(f"Copytrade {N_ACCOUNTS} comptes -- BLOCK BOOTSTRAP {BLOCK_MONTHS} mois "
          f"({len(blocks)} blocs), payoff TP2 réaliste + trailing 0.2xSL\n")

    rows = []
    for label, threshold in TRIGGERS.items():
        rng = random.Random(42)
        results = [run_copytrade_hybrid_year1_block(blocks, block_seconds, threshold, market_data, excluded_map, rng)
                   for _ in range(N_SIMULATIONS)]

        real_cash_vals = sorted(r[0] for r in results)
        net_profit_vals = [r[1] for r in results]
        switch_times = [r[2] for r in results if r[2] is not None]

        n = len(real_cash_vals)
        mean_cash = sum(real_cash_vals) / n
        median_cash = real_cash_vals[n // 2]
        worst_cash = real_cash_vals[-1]

        mean_net_profit = sum(net_profit_vals) / len(net_profit_vals)

        pct_switched_year1 = sum(1 for r in results if r[2] is not None and r[2] <= YEAR_SECONDS) / n * 100
        delays_year1 = [t / 86400 / 30.44 for t in switch_times if t <= YEAR_SECONDS]
        mean_delay_months = sum(delays_year1) / len(delays_year1) if delays_year1 else float("nan")

        row = {"trigger": label, "reserve_threshold": threshold,
               "mean_real_cash": mean_cash, "median_real_cash": median_cash, "worst_real_cash": worst_cash,
               "pct_gt_1000": sum(1 for r in real_cash_vals if r > 1000) / n * 100,
               "pct_gt_2000": sum(1 for r in real_cash_vals if r > 2000) / n * 100,
               "pct_gt_3000": sum(1 for r in real_cash_vals if r > 3000) / n * 100,
               "mean_net_profit_year1": mean_net_profit,
               "pct_switched_within_year1": pct_switched_year1,
               "mean_delay_months": mean_delay_months}
        rows.append(row)

        print("=" * 100)
        print(f"DÉCLENCHEUR : {label}")
        print("=" * 100)
        print(f"Trésorerie réelle -- moyenne {mean_cash:,.0f}€ | médiane {median_cash:,.0f}€ | pire cas {worst_cash:,.0f}€")
        print(f"P(>1000€) {row['pct_gt_1000']:.2f}% | P(>2000€) {row['pct_gt_2000']:.2f}% | P(>3000€) {row['pct_gt_3000']:.2f}%")
        print(f"Profit net moyen année 1 (flotte) : {mean_net_profit:+,.0f}€")
        print(f"Bascule atteinte pendant l'année 1 : {pct_switched_year1:.1f}% des runs "
              f"(délai moyen quand atteint : {mean_delay_months:.2f} mois)")
        print()

    summary_df = pd.DataFrame(rows)
    summary_df.to_csv("risk_switch_threshold_block_bootstrap_summary.csv", index=False)

    print("=" * 100)
    print("TABLEAU COMPARATIF FINAL (BLOCK BOOTSTRAP 2 MOIS)")
    print("=" * 100)
    print(summary_df.to_string(index=False))

    try:
        ref_df = pd.read_csv("risk_switch_threshold_summary.csv")
        print("\n" + "=" * 100)
        print("RAPPEL -- ancien tableau (bootstrap PERMUTATION, déjà calculé)")
        print("=" * 100)
        print(ref_df.to_string(index=False))
    except FileNotFoundError:
        pass

    print("\nRésumé enregistré dans risk_switch_threshold_block_bootstrap_summary.csv")
    return summary_df


if __name__ == "__main__":
    main()
