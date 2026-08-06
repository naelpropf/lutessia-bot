"""
Construit un payoff TP2 RÉALISTE (pas une simple substitution rr_tp1 -> rr_tp2) en
étendant au dataset ACTUEL complet (historique_lutessia_15k.csv, seuil rr_tp1 >= 1.5)
la vérification de continuation TP1->TP2 que tp_sequence_analysis.py avait faite sur
l'ancien cut à 288 trades / seuil 2.0.

rr_threshold_test.build_extended_population() calcule DÉJÀ cette classification comme
sous-produit du calcul des durées réelles (elle appelle tp_sequence_analysis.analyze_trade
sur chaque trade pour vérifier tp1_time/tp2_time/sl_time via les bougies H1) -- ce module
ne fait que r��utiliser la colonne "case" déjà produite, pas relancer un scraping/calcul
séparé.

Pour un trade OBJECTIF ATTEINT (= TP1 touché, cf. le docstring de tp_sequence_analysis.py),
la valeur "case" retournée par analyze_trade se répartit en :
  - "tp1_avant_tp2"                : le prix a AUSSI touché TP2 après TP1 (continuation confirmée)
  - "meme_bougie"                  : TP1 ET TP2 touchés dans la même bougie H1 (ordre ambigu,
                                     mais le niveau TP2 a bien été atteint -> continuation confirmée)
  - "tp2_non_atteint_dans_fenetre" : données disponibles, TP2 vérifié NON atteint -> pas de continuation
  - "tp1_non_detecte"              : TP1 lui-même introuvable dans les bougies malgré le statut
                                     (anomalie de données rare) -> continuation NON confirmée (on ne
                                     peut même pas confirmer TP1, donc certainement pas TP2)
  - "hors_couverture_historique"   : trade antérieur à la fenêtre H1 Yahoo disponible (~730 jours)
                                     -> continuation NON VÉRIFIABLE (traité en NON confirmée, par
                                     prudence -- PAS une preuve que TP2 n'a pas été atteint, juste
                                     une absence de données)

Règle de payoff réaliste retenue :
  - Trade OBJECTIF ATTEINT, continuation confirmée (tp1_avant_tp2 / meme_bougie) : R = rr_tp2
  - Trade OBJECTIF ATTEINT, tout le reste (non confirmée OU hors couverture)     : R = rr_tp1
  - Trade INVALIDÉE                                                              : R = -1.0

Ce choix est délibérément CONSERVATEUR sur le bloc "hors couverture" (38.6% des gains dans
l'échantillon seuil 1.5, cf. plus bas) : on n'assume PAS que ces trades non vérifiables se
comportent comme les trades vérifiés (où ~90% continuent effectivement jusqu'à TP2) -- on leur
applique le payoff le plus prudent (rr_tp1) faute de preuve directe.
"""
import pandas as pd

import rr_threshold_test as rrt

MIN_RR_TP1 = 1.5

CONTINUATION_CONFIRMED_CASES = {"tp1_avant_tp2", "meme_bougie"}
CONTINUATION_NOT_CONFIRMED_CASES = {"tp2_non_atteint_dans_fenetre", "tp1_non_detecte"}
OUT_OF_COVERAGE_CASES = {"hors_couverture_historique", "pas_de_donnees"}


def build_realistic_payoff_population(min_rr=MIN_RR_TP1, verbose=True):
    pop_full, median_duration = rrt.build_extended_population(min_rr=min_rr)
    pop = pop_full[pop_full["rr_tp1"] >= min_rr].copy()

    wins_mask = pop["statut_final"] == "OBJECTIF ATTEINT"

    def classify(case):
        if case in CONTINUATION_CONFIRMED_CASES:
            return "continuation_confirmee"
        if case in CONTINUATION_NOT_CONFIRMED_CASES:
            return "continuation_non_confirmee"
        if case in OUT_OF_COVERAGE_CASES:
            return "hors_couverture"
        return "autre"  # ex: tp2_avant_tp1, non observé sur ce dataset mais couvert par sécurité

    pop["payoff_bucket"] = None
    pop.loc[wins_mask, "payoff_bucket"] = pop.loc[wins_mask, "case"].apply(classify)

    def realistic_r(row):
        if row["statut_final"] != "OBJECTIF ATTEINT":
            return -1.0
        if row["payoff_bucket"] == "continuation_confirmee":
            return row["rr_tp2"]
        return row["rr_tp1"]

    pop["r_realiste"] = pop.apply(realistic_r, axis=1)

    if verbose:
        wins = pop[wins_mask]
        n_wins = len(wins)
        print("\n" + "=" * 100)
        print(f"VÉRIFICATION CONTINUATION TP1->TP2 (seuil rr_tp1 >= {min_rr}, dataset actuel complet)")
        print("=" * 100)
        print(f"Trades OBJECTIF ATTEINT (= TP1 touché) : {n_wins}")
        counts = wins["case"].value_counts()
        for case, n in counts.items():
            print(f"  {case:32s} : {n:4d} ({n/n_wins*100:5.1f}%)")

        bucket_counts = wins["payoff_bucket"].value_counts()
        print(f"\nRegroupement en 3 catégories (règle de payoff) :")
        for bucket in ["continuation_confirmee", "continuation_non_confirmee", "hors_couverture"]:
            n = bucket_counts.get(bucket, 0)
            print(f"  {bucket:28s} : {n:4d} ({n/n_wins*100:5.1f}%)")
        print("\n[AVERTISSEMENT] Le bloc 'hors_couverture' (trades antérieurs à la fenêtre H1 Yahoo, ~730 jours) est "
              "traité en payoff rr_tp1 PAR PRUDENCE, faute de preuve -- ce n'est PAS une vérification "
              "que TP2 n'a pas été atteint. Sur les cas où la donnée EST disponible, le taux de "
              "continuation réel vers TP2 est nettement plus élevé (cf. tableau ci-dessus).")

        ev_r_tp1 = (wins["rr_tp1"].mean() * n_wins - (len(pop) - n_wins)) / len(pop)
        ev_r_tp2 = (wins["rr_tp2"].mean() * n_wins - (len(pop) - n_wins)) / len(pop)
        ev_realiste = pop["r_realiste"].mean()
        print(f"\nEV sur POPULATION BRUTE ({len(pop)} trades, avant plafond/corrélation) :")
        print(f"  Payoff rr_tp1 systématique (ancienne convention)   : {ev_r_tp1:+.3f} R")
        print(f"  Payoff rr_tp2 systématique (substitution naïve)    : {ev_r_tp2:+.3f} R")
        print(f"  Payoff RÉALISTE (ce module)                        : {ev_realiste:+.3f} R")

    return pop, median_duration


def build_trades_realistic(pop, multiplier_fn=None):
    """Construit trades/slot_arrivals avec outcome_r = r_realiste (payoff TP2 réaliste),
    au format générique attendu par monte_carlo_simulation.run_one, scaling_simulation,
    fleet_simulation_test et copytrade_simulation_test (tous consomment trade["outcome_r"]
    tel quel, sans se soucier de sa provenance)."""
    sub = pop.sort_values("date_creation").reset_index(drop=True)
    t0 = sub["date_creation"].iloc[0]
    slot_arrivals = [(d - t0).total_seconds() for d in sub["date_creation"]]

    trades = []
    for _, row in sub.iterrows():
        hold_seconds = (row["resolution_time_est"] - row["date_creation"]).total_seconds()
        sl_distance = abs(row["prix_entree"] - row["stop_loss_init"])
        trade = {
            "ticker": row["ticker"],
            "outcome_r": row["r_realiste"],
            "sl_distance": sl_distance,
            "hold_seconds": hold_seconds,
            "date": row["date_creation"],
        }
        if multiplier_fn is not None:
            trade["risk_multiplier"] = multiplier_fn(row)
        trades.append(trade)
    return sub, trades, slot_arrivals


if __name__ == "__main__":
    pop, _ = build_realistic_payoff_population()
    pop.to_csv("tp2_realistic_payoff_detail.csv", index=False)
    print("\nDétail par trade enregistré dans tp2_realistic_payoff_detail.csv")
