"""
Calcul complet (5 niveaux de risque + copytrade vs diversifié) pour le trailing stop
distance fixe 0.2x la distance SL initiale -- nouveau leader après correction du bug
d'ancrage de l'extremum (cf. trailing_stop_variants.py) et confirmation de robustesse
(sous-périodes, sensibilité aux outliers, pire cas individuel -- tous meilleurs que le
0.5x précédemment testé). Réutilise directement les fonctions déjà écrites pour
0.5x/retracement (risk_levels_trailing_test.py, copytrade_vs_fleet_trailing_test.py)
sans dupliquer le calcul déjà fait sur ces 2 autres configs.
"""
import pandas as pd

from scaling_simulation import load_market_data
from risk_levels_trailing_test import run_for_config as run_risk_levels_for_config
from copytrade_vs_fleet_trailing_test import run_for_config as run_copytrade_fleet_for_config

LABEL = "trailing_distance_fixe_0.2x"
KIND, PARAM = "fixed", 0.2


def main():
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)

    try:
        baseline_df = pd.read_csv("risk_levels_realistic_summary.csv")
    except FileNotFoundError:
        baseline_df = pd.DataFrame(columns=["risk_pct_per_account", "mean_profit"])

    print("\n" + "#" * 100)
    print("PARTIE 1 : NIVEAUX DE RISQUE (0.5/1/1.5/2/3%), COPYTRADE 3 COMPTES")
    print("#" * 100)
    risk_df = run_risk_levels_for_config(LABEL, KIND, PARAM, market_data, corr_matrix, baseline_df)
    risk_df.to_csv("risk_levels_trailing_02_summary.csv", index=False)

    print("\n" + "#" * 100)
    print("PARTIE 2 : COPYTRADE vs FLOTTE DIVERSIFIÉE (2%/compte)")
    print("#" * 100)
    fleet_df = run_copytrade_fleet_for_config(LABEL, KIND, PARAM, market_data, corr_matrix)
    fleet_df.to_csv("copytrade_vs_fleet_trailing_02_summary.csv", index=False)

    print("\n" + "=" * 100)
    print("TABLEAU COMPARATIF FINAL -- baseline réaliste vs 0.5x vs retracement 10% vs 0.2x (nouveau)")
    print("=" * 100)
    try:
        prev_risk = pd.read_csv("risk_levels_trailing_summary.csv")
        all_risk = pd.concat([prev_risk, risk_df], ignore_index=True)
    except FileNotFoundError:
        all_risk = risk_df
    cols = ["config", "risk_pct_per_account", "mean_profit", "median_profit", "p5_profit",
            "mean_broken_count", "monthly_std_pct", "ratio_vs_baseline"]
    print(all_risk[cols].to_string(index=False))

    print()
    try:
        prev_fleet = pd.read_csv("copytrade_vs_fleet_trailing_summary.csv")
        baseline_fleet = pd.read_csv("copytrade_vs_fleet_realistic_summary.csv")
        baseline_fleet["config"] = "baseline_realiste_sans_trailing"
        all_fleet = pd.concat([baseline_fleet, prev_fleet, fleet_df], ignore_index=True)
    except FileNotFoundError:
        all_fleet = fleet_df
    print(all_fleet.to_string(index=False))

    return risk_df, fleet_df


if __name__ == "__main__":
    main()
