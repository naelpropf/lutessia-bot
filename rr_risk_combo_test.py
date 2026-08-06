"""
Teste la combinaison seuil rr_tp1 >= 1.5 (au lieu de 2.0) avec deux schémas de
risque, et compare aux deux résultats déjà connus :

1. Seuil 1.5, risque 2% FIXE dès le début (dès le palier 50k).
2. Seuil 1.5, risque PROGRESSIF : 0.5% tant que le compte est au palier 50k (phase
   de validation), puis 2% dès que scalé à 200k ou plus.
3. Référence : seuil 2.0/risque 2% fixe, et seuil 1.5/risque 0.5% fixe (déjà
   documentés) — recalculés ici avec exactement la même population/méthodologie
   pour une comparaison apples-to-apples (durées réelles, plafond 3 positions,
   corrélation 0.6+JPY, scaling 50k->200k->500k avec 4 jours min, contrainte de
   faisabilité marge/lots).

Réutilise la population à durées réelles déjà construite dans rr_threshold_test.py
(build_extended_population, superset MIN_RR=1.0) — pas de nouveau scraping/fetch.
"""
import pandas as pd

from scaling_simulation import load_market_data, TIER_SEQUENCE
from rr_threshold_test import build_extended_population, run_mc_for_threshold, N_SIMULATIONS

SCENARIOS = [
    {"name": "Seuil 1.5, risque 2% fixe dès le début", "threshold": 1.5, "risk": 2.0},
    {"name": "Seuil 1.5, risque progressif (0.5% @ 50k -> 2% @ 200k+)", "threshold": 1.5,
     "risk": lambda palier: 0.5 if palier == TIER_SEQUENCE[0] else 2.0},
    {"name": "[Référence] Seuil 2.0, risque 2% fixe", "threshold": 2.0, "risk": 2.0},
    {"name": "[Référence] Seuil 1.5, risque 0.5% fixe", "threshold": 1.5, "risk": 0.5},
]


def main():
    pop, _ = build_extended_population()
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)

    rows = []
    for scenario in SCENARIOS:
        sub, mc = run_mc_for_threshold(pop, scenario["threshold"], market_data, corr_matrix, risk_pct=scenario["risk"])
        rows.append({"scenario": scenario["name"], "threshold": scenario["threshold"], **mc})

        print("=" * 100)
        print(f"{scenario['name']} — {N_SIMULATIONS} simulations")
        print("=" * 100)
        print(f"Pool de signaux disponibles (avant permutation/filtre plafond) : {len(sub)}")
        print(f"Profit net moyen   : {mc['mean_profit']:+,.0f}€")
        print(f"Profit net médian  : {mc['median_profit']:+,.0f}€")
        print(f"P(perte nette)     : {mc['pct_loss']:.1f}%")
        print(f"5e percentile      : {mc['p5_profit']:+,.0f}€")
        print(f"Pire cas observé   : {mc['worst_profit']:+,.0f}€")
        print(f"Meilleur cas       : {mc['best_profit']:+,.0f}€")
        print(f"Casses moyen       : {mc['mean_broken_count']:.2f}")
        print(f"Max casses consécutives : {mc['max_max_consecutive_breaks']} (moyenne {mc['mean_max_consecutive_breaks']:.2f})")
        print(f"Palier final : 500k {mc['pct_final_500k']:.1f}% | 200k {mc['pct_final_200k']:.1f}% | 50k {mc['pct_final_50k']:.1f}%")
        print()

    summary_df = pd.DataFrame(rows)
    summary_df.to_csv("rr_risk_combo_summary.csv", index=False)
    print("Résumé enregistré dans rr_risk_combo_summary.csv")
    return summary_df


if __name__ == "__main__":
    main()
