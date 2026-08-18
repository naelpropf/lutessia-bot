"""
Volet 1c (demande 08/08) : la fonction eng.feasible_risk_pct() est deja
appelee sur CHAQUE trade dans extra_account_v3_gft_risk.py (process_trade),
donc le cap broker 100 lots ET la contrainte de marge sont deja pris en
compte dans tous les chiffres de profit actuels -- pas de correction de
modele necessaire. Ce script mesure juste l'ampleur reelle de cette
contrainte sur les tailles de compte visees par le deplafonnement (200k-
500k$), a risque flotte final (2.5%), pour verifier qu'elle reste marginale
(sinon le profit deja calcule serait deja trop optimiste malgre l'application
du cap, si le point de reduction se produisait tres frequemment).
"""
import random

import pandas as pd

import robustness_5ers_risk_challenge as eng
from scaling_simulation import feasible_risk_pct
from trailing_payoff_population import build_population_with_trailing

TARGET_RISK = 2.5
PALIERS = [25000, 50000, 75000, 100000, 150000, 200000, 300000, 400000, 500000]

pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
market_data = eng.load_market_data()
trades, _ = eng.build_flexible_population(pop, 0.5, 1.0, False, random.Random(42))

rows = []
for palier in PALIERS:
    n_reduced = 0
    total_shortfall_r = 0.0
    n = len(trades)
    for t in trades:
        eff_risk, was_reduced = feasible_risk_pct(t["ticker"], t["sl_distance"], palier, TARGET_RISK, market_data)
        if was_reduced:
            n_reduced += 1
            total_shortfall_r += (TARGET_RISK - eff_risk) / TARGET_RISK
    rows.append(dict(palier=palier, pct_trades_reduced=n_reduced / n * 100,
                      avg_shortfall_pct_when_reduced=(total_shortfall_r / n_reduced * 100) if n_reduced else 0.0,
                      avg_shortfall_pct_all_trades=total_shortfall_r / n * 100))

df = pd.DataFrame(rows)
pd.set_option("display.float_format", lambda x: f"{x:,.3f}")
print(df.to_string(index=False))
df.to_csv("lotcap_feasibility_check.csv", index=False)
