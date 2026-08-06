"""
Test de sensibilité de l'edge : recalcule le pool de trades pour des winrates DÉGRADÉS
artificiellement (35/30/25/20/15/13/10%), en gardant la distribution des RR des gains
INCHANGÉE (les trades qui restent gagnants gardent leur R réel, r_trailing) -- seule la
PROPORTION gagnants/perdants change, via un tirage aléatoire de trades gagnants à
"retourner" en perdants (R=-1.0). Toutes les autres propriétés du trade (ticker,
sl_distance, hold_seconds, date d'arrivée réelle) restent inchangées -- donc le plafond
de 3 positions/compte, la corrélation 0.6+JPY et la faisabilité marge/lots continuent de
s'appliquer exactement comme sur la population réelle.

Config de référence VERROUILLÉE (paramètres imposés) : copytrade 3 comptes/3 firms,
risque 2%/compte, seuil rr_tp1>=1.5, payoff réaliste + trailing 0.2xSL, scaling
50k->200k->500k (financé +8%/4j min, réserve 80%), faisabilité incluse, résultat flotte
combinée. Réutilise TEL QUEL le moteur déjà validé
(copytrade_simulation_test.run_copytrade_one / summarize_copytrade), aucune nouvelle
logique de simulation -- seule la construction du pool de trades change.

Limite assumée : le hold_seconds de chaque trade "retourné" en perdant reste celui
calculé sur son résultat RÉEL d'origine (souvent un délai jusqu'à TP1, potentiellement
différent d'un vrai délai jusqu'au SL) -- approximation mineure pour un test de
sensibilité théorique, sans impact matériel sur les plafonds de position vu la durée de
détention courte (~7h40 médiane) par rapport à l'espacement entre signaux.
"""
import random

import pandas as pd

from scaling_simulation import CORR_THRESHOLD, load_market_data
from monte_carlo_simulation import precompute_correlation_pairs, N_SIMULATIONS
from trailing_payoff_population import build_population_with_trailing
from copytrade_simulation_test import run_copytrade_one, summarize_copytrade

RISK_PCT = 2.0
TARGET_WINRATES = [0.35, 0.30, 0.25, 0.20, 0.15, 0.13, 0.10]
DEGRADE_SEED = 123


def build_degraded_trades(pop, target_winrate, rng):
    sub = pop.sort_values("date_creation").reset_index(drop=True)
    n = len(sub)
    is_win = (sub["statut_final"] == "OBJECTIF ATTEINT").to_numpy()
    current_n_win = int(is_win.sum())
    target_n_win = round(target_winrate * n)

    win_idx = list(sub.index[is_win])
    flip_to_loss = set()
    if target_n_win < current_n_win:
        flip_to_loss = set(rng.sample(win_idx, current_n_win - target_n_win))
    # (aucun des niveaux demandés ne dépasse le winrate actuel ~37.3%, donc pas de cas
    # "retourner un perdant en gagnant" à gérer ici)

    t0 = sub["date_creation"].iloc[0]
    slot_arrivals = [(d - t0).total_seconds() for d in sub["date_creation"]]
    trades = []
    for idx, row in sub.iterrows():
        hold_seconds = (row["resolution_time_est"] - row["date_creation"]).total_seconds()
        sl_distance = abs(row["prix_entree"] - row["stop_loss_init"])
        if idx in flip_to_loss:
            outcome_r = -1.0
        else:
            outcome_r = row["r_trailing"] if row["statut_final"] == "OBJECTIF ATTEINT" else -1.0
        trades.append({
            "ticker": row["ticker"], "outcome_r": outcome_r, "sl_distance": sl_distance,
            "hold_seconds": hold_seconds, "date": row["date_creation"],
        })

    actual_n_win = current_n_win - len(flip_to_loss)
    return sub, trades, slot_arrivals, actual_n_win / n


def main():
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)

    pop = build_population_with_trailing("fixed", 0.2, verbose=True)
    current_winrate = (pop["statut_final"] == "OBJECTIF ATTEINT").mean()
    avg_win_r = pop.loc[pop["statut_final"] == "OBJECTIF ATTEINT", "r_trailing"].mean()
    print(f"\nWinrate ACTUEL (population réelle, non dégradée) : {current_winrate*100:.2f}%")
    print(f"RR moyen des gains (r_trailing) : {avg_win_r:.3f}")
    print(f"Seuil de rentabilité THÉORIQUE (EV brute = 0, formule p = 1/(1+RR), "
          f"sans frais/casses) : {1/(1+avg_win_r)*100:.2f}%")

    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    rows = []
    for target in TARGET_WINRATES:
        degrade_rng = random.Random(DEGRADE_SEED)
        sub, trades, slot_arrivals, actual_winrate = build_degraded_trades(pop, target, degrade_rng)

        mc_rng = random.Random(42)
        results = [run_copytrade_one(trades, slot_arrivals, RISK_PCT, market_data, excluded_map, mc_rng)
                   for _ in range(N_SIMULATIONS)]
        mc = summarize_copytrade(results)

        print(f"\n{'='*100}")
        print(f"WINRATE CIBLE {target*100:.0f}% (réalisé : {actual_winrate*100:.2f}%)")
        print(f"{'='*100}")
        print(f"Profit net moyen : {mc['mean_profit']:+,.0f}€ | médian : {mc['median_profit']:+,.0f}€")
        print(f"P(perte nette) : {mc['pct_loss']:.1f}%")
        print(f"Casses moyennes (flotte) : {mc['mean_broken_count']:.2f}")

        rows.append({
            "target_winrate_pct": target * 100, "actual_winrate_pct": actual_winrate * 100,
            "mean_profit": mc["mean_profit"], "median_profit": mc["median_profit"],
            "p5_profit": mc["p5_profit"], "pct_loss": mc["pct_loss"],
            "mean_broken_count": mc["mean_broken_count"],
            "mean_max_consecutive_breaks": mc["mean_max_consecutive_breaks"],
        })

    summary_df = pd.DataFrame(rows)
    summary_df.to_csv("winrate_sensitivity_summary.csv", index=False)

    print("\n" + "=" * 100)
    print("TABLEAU COMPARATIF FINAL -- sensibilité du profit net au winrate")
    print("=" * 100)
    print(summary_df.to_string(index=False))

    # Localise le point de rupture EMPIRIQUE (Monte Carlo, frais/casses inclus) par
    # interpolation linéaire entre les 2 niveaux testés qui encadrent le changement de signe.
    print("\n" + "=" * 100)
    print("POINT DE RUPTURE (Monte Carlo, interpolation entre les niveaux testés)")
    print("=" * 100)
    crossed = False
    for i in range(len(rows) - 1):
        a, b = rows[i], rows[i + 1]
        if a["mean_profit"] >= 0 > b["mean_profit"]:
            wa, wb = a["actual_winrate_pct"], b["actual_winrate_pct"]
            pa, pb = a["mean_profit"], b["mean_profit"]
            breakeven_w = wa + (0 - pa) * (wb - wa) / (pb - pa)
            print(f"Le profit net moyen passe de positif ({a['target_winrate_pct']:.0f}% -> "
                  f"{pa:+,.0f}€) à négatif ({b['target_winrate_pct']:.0f}% -> {pb:+,.0f}€).")
            print(f"Point de rupture interpolé (Monte Carlo, frais/casses inclus) : ~{breakeven_w:.1f}% de winrate")
            crossed = True
            break
    if not crossed:
        print("Le profit net moyen reste positif sur TOUS les niveaux testés (10% à 35%) -- "
              "le point de rupture empirique est SOUS 10%, à explorer avec des niveaux plus bas si besoin.")

    return summary_df


if __name__ == "__main__":
    main()
