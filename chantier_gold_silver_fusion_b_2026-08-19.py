"""Construit les 3 scenarios de fusion GOLD/SILVER dans Strategie B (chantier
2026-08-19) : merge population or/argent (or_argent_population_2026-08-19.py,
payoff realiste + trailing 0.10x) dans B (chantier_b6_montecarlo_2026-08-19.
build_pop_B_variant, 571 trades), + rythme mensuel compare a A.

Colonnes communes B / or-argent : date_creation, ticker, rr_tp1, rr_tp2,
statut_final, r_trailing, resolution_time_est, prix_entree, stop_loss_init
(memes noms des 2 cotes, verifie).
"""
import importlib.util

import pandas as pd

from trailing_payoff_population import build_population_with_trailing

_spec = importlib.util.spec_from_file_location("b6", "chantier_b6_montecarlo_2026-08-19.py")
b6 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(b6)

_spec2 = importlib.util.spec_from_file_location("oa", "or_argent_population_2026-08-19.py")
oa = importlib.util.module_from_spec(_spec2)
_spec2.loader.exec_module(oa)

KEEP_COLS = ["date_creation", "ticker", "rr_tp1", "rr_tp2", "statut_final", "r_trailing", "resolution_time_est"]

SCENARIOS_FILE = "chantier_gold_silver_etape0_scenarios_2026-08-19.txt"


def load_scenarios():
    scenarios = {}
    with open(SCENARIOS_FILE, encoding="utf-8") as f:
        for line in f:
            key, val = line.strip().split("=", 1)
            scenarios[key] = eval(val)
    return scenarios


def monthly_rate(pop):
    span_days = (pop["date_creation"].max() - pop["date_creation"].min()).days
    return len(pop) / (span_days / 30.44)


def main():
    print("Chargement A (reference rythme)...")
    pop_A = build_population_with_trailing("fixed", 0.15, min_rr=1.35, verbose=False)
    rate_A = monthly_rate(pop_A)

    print("Chargement B (571 trades)...")
    pop_B = b6.build_pop_B_variant(trailing_factor=0.10)
    rate_B = monthly_rate(pop_B)
    print(f"B seul (571) : {rate_B:.2f} trades/mois, ratio B/A = {rate_B/rate_A*100:.1f}%")

    print("\nChargement or/argent (payoff realiste + trailing)...")
    pop_oa = pd.read_csv("or_argent_population_trailing_2026-08-19.csv")
    pop_oa["date_creation"] = pd.to_datetime(pop_oa["date_creation"])
    pop_oa["resolution_time_est"] = pd.to_datetime(pop_oa["resolution_time_est"])

    scenarios = load_scenarios()
    print(f"\nScenarios charges : A={len(scenarios['A'])} tickers, B={len(scenarios['B'])} tickers, "
          f"C={len(scenarios['C'])} tickers")

    results = {}
    for name, tickers in scenarios.items():
        sub_oa = pop_oa[pop_oa["ticker"].isin(tickers)][KEEP_COLS].copy()
        merged = pd.concat([pop_B[KEEP_COLS], sub_oa], ignore_index=True)
        merged = merged.sort_values("date_creation").reset_index(drop=True)
        rate = monthly_rate(merged)
        ev = merged["r_trailing"].mean()
        results[name] = merged
        merged.to_csv(f"chantier_gold_silver_pop_B_scenario_{name}_2026-08-19.csv", index=False)
        print(f"\nScenario {name} : B(571) + or/argent({len(sub_oa)}) = {len(merged)} trades")
        print(f"  EV poolee (r_trailing) = {ev:+.4f}R")
        print(f"  Rythme mensuel = {rate:.2f} trades/mois, ratio vs A = {rate/rate_A*100:.1f}% "
              f"(B seul = {rate_B/rate_A*100:.1f}%, delta = {(rate-rate_B*len(pop_B)/len(pop_B)):+.2f})")

    print(f"\nSauvegarde : chantier_gold_silver_pop_B_scenario_{{A,B,C}}_2026-08-19.csv")


if __name__ == "__main__":
    main()
