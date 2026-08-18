"""
Cascade RR1.35+corr0.80, Section 0 (08/12) : verification rapide (SOLO, pas
flotte) de l'economie de la bande Strategie B avant/apres l'elargissement
0.75-1.25 -> 0.75-1.35 (dual_trader_2026-08-11.py, MIN_RR_T1 desormais la
reference partagee T1/T2). Compare frequence (n) et EV (r_trailing) des deux
bandes sur la population complete, payoff trailing 0.15xSL actuel.

N'importe pas ce script directement (convention du projet).
"""
import pandas as pd

from trailing_payoff_population import build_population_with_trailing

pop = build_population_with_trailing("fixed", 0.15, min_rr=0.75, verbose=False)

for label, low, high in [("ANCIENNE bande 0.75-1.25", 0.75, 1.25), ("NOUVELLE bande 0.75-1.35", 0.75, 1.35)]:
    band = pop[(pop["rr_tp1"] >= low) & (pop["rr_tp1"] < high)]
    n = len(band)
    winrate = (band["r_trailing"] > 0).mean() * 100
    ev = band["r_trailing"].mean()
    sum_r = band["r_trailing"].sum()
    print(f"{label} : n={n} winrate={winrate:.1f}% EV={ev:+.4f}R sommeR={sum_r:+.1f}")

added = pop[(pop["rr_tp1"] >= 1.25) & (pop["rr_tp1"] < 1.35)]
print(f"\n[delta] trades ajoutes par l'elargissement (1.25<=rr_tp1<1.35) : n={len(added)}, "
      f"winrate={(added['r_trailing']>0).mean()*100:.1f}%, EV={added['r_trailing'].mean():+.4f}R "
      f"(ces trades etaient AVANT dans la zone morte T1/T2 -- ni pris par T1 [>=1.35 desormais], "
      f"ni par T2 [<1.25 avant elargissement])")
