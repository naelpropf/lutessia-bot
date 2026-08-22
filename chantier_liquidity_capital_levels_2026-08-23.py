"""chantier_liquidity_capital_levels_2026-08-23.py

Suite a chantier_liquidity_capacity_2026-08-23.py (n=600 confirme) et a la
demande utilisateur : enumerer le capital atteint chaque annee (1-4) et le
% gagne cette annee-la, en partant de 200k, 100k, 20k, 1k, et 100 euros --
PAS en reappliquant le tableau de taux mensuel §3.1 du document (qui serait
FAUX pour un capital de depart different : les seuils de plafonnement de
liquidite sont ancres sur le capital ABSOLU atteint, pas sur le temps
ecoule -- un depart a 100€ passe d'abord par une longue phase NON plafonnee
avant d'atteindre les memes seuils que le depart 200k$ atteint des le
mois 0). Reutilise TEL QUEL le moteur (simulate_one/run_scenario,
desormais parametres par start_capital) plutot que d'approximer par un
decalage temporel.

Plafond retenu : 1% ADV (le plus strict des 3 testes dans le chantier
principal, coherent avec l'usage "estimation a la louche" demande). n=300
(exploration rapide, comme demande -- "a la louche"), 48 mois.
"""
import sys

import numpy as np
import pandas as pd

import importlib.util
_spec = importlib.util.spec_from_file_location("lc", "chantier_liquidity_capacity_2026-08-23.py")
lc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lc)

START_CAPITALS = [200_000.0, 100_000.0, 20_000.0, 1_000.0, 100.0]
CAP_PCT = 0.01
N_SIMS = 300
SEED = 24680
DURATION_DAYS = 365 * 4


def main():
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else N_SIMS

    rows = []
    for start_capital in START_CAPITALS:
        row = lc.run_scenario(n_sims, SEED, DURATION_DAYS, CAP_PCT, f"cap1pct_{start_capital:.0f}",
                               start_capital=start_capital)
        traj = np.array(row["median_trajectory"])
        print(f"\n=== Depart {start_capital:,.0f}$ (plafond 1% ADV, n={n_sims}) ===", flush=True)
        prev = start_capital
        for year in range(1, 5):
            m = year * 12 - 1
            if m >= len(traj):
                break
            bal = traj[m]
            gain_pct = (bal / prev - 1) * 100
            print(f"  Annee {year} : {bal:>18,.0f}$  ({gain_pct:+,.0f}% sur l'annee)", flush=True)
            prev = bal
        rows.append(dict(start_capital=start_capital, **{f"year{y}": traj[y*12-1] for y in range(1, 5) if y*12-1 < len(traj)}))

    pd.DataFrame(rows).to_csv("chantier_liquidity_capital_levels_2026-08-23_summary.csv", index=False)


if __name__ == "__main__":
    main()
