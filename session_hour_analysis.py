"""
Segmente le winrate et l'EV par tranche horaire (session de liquidité) de
date_creation, sur la population déjà filtrée à rr_tp1 >= 1.5 (seuil de
production actuel), avec le plafond de 3 positions et la règle de
corrélation 0.6 + JPY déjà en place (cf. scaling_simulation.py /
rr_threshold_test.py), sur les VRAIES durées de trade (bougies H1 en
cache, mêmes tickers/méthodologie que tp_sequence_analysis.py).

Fuseau horaire de date_creation : VÉRIFIÉ UTC (et non heure de Paris). Le
JS source de CentralCharts (tools.min.js, fonction getElapsedTime) parse la
valeur brute de l'attribut data-date — exactement la donnée copiée telle
quelle dans date_creation par scraper.py — via dayjs.utc(t), donc le site
lui-même traite cet horodatage comme de l'UTC pour son propre affichage
"il y a Xh". Aucune conversion de fuseau n'est donc nécessaire ici, ce qui
est cohérent avec le reste du dépôt (aucune conversion appliquée nulle
part, y compris dans tp_sequence_analysis.py qui compare directement
date_creation aux bougies H1 Yahoo Finance en UTC).

EV calculée sur rr_tp2 (sortie visée = TP2, stratégie de production actuelle) :
  rr_tp2 si statut_final == 'OBJECTIF ATTEINT', sinon -1.
"""
import re

import numpy as np
import pandas as pd

import rr_threshold_test as rrt
from scaling_simulation import CORR_THRESHOLD  # noqa: F401 (documentation)

MIN_RR_TP1 = 1.5
MIN_SAMPLE_WARN = 50

SESSIONS = [
    ("Asiatique",            0, 8),
    ("Londres",               8, 13),
    ("Chevauchement LDN/NY",  13, 16),
    ("US seule",              16, 22),
    ("Nuit creuse",           22, 24),
]


def session_label(hour):
    for label, start, end in SESSIONS:
        if start <= hour < end:
            return label
    raise AssertionError(hour)


def ev_tp2(sub):
    n = len(sub)
    wins = sub[sub["statut_final"] == "OBJECTIF ATTEINT"]
    losses = sub[sub["statut_final"] == "INVALIDÉE"]
    winrate = len(wins) / n if n else float("nan")
    avg_rr_tp2_wins = wins["rr_tp2"].mean() if len(wins) else float("nan")
    ev = winrate * avg_rr_tp2_wins - (1 - winrate) if len(wins) else float("nan")
    sum_r_tp2 = wins["rr_tp2"].sum() - len(losses)
    return {
        "n": n, "wins": len(wins), "losses": len(losses),
        "winrate_pct": winrate * 100, "avg_rr_tp2_wins": avg_rr_tp2_wins,
        "ev_tp2": ev, "sum_r_tp2": sum_r_tp2,
    }


def main():
    pop_full, median_duration = rrt.build_extended_population(min_rr=MIN_RR_TP1)
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)

    pop = pop_full[pop_full["rr_tp1"] >= MIN_RR_TP1].copy()
    print(f"\nPopulation brute (rr_tp1 >= {MIN_RR_TP1}, forex, terminaux) : {len(pop)} trades")

    taken = rrt.taken_trades(pop, corr_matrix)
    print(f"Trades PRIS (après plafond 3 positions + corrélation 0.6/JPY) : {len(taken)} "
          f"({len(taken)/len(pop)*100:.1f}% de la population brute)")

    taken = taken.copy()
    taken["hour_utc"] = pd.to_datetime(taken["date_creation"]).dt.hour
    taken["session"] = taken["hour_utc"].apply(session_label)

    print("\n" + "=" * 100)
    print("EV PAR TRANCHE HORAIRE (trades PRIS, EV calculée sur rr_tp2, cible = TP2)")
    print("=" * 100)

    rows = []
    for label, start, end in SESSIONS:
        sub = taken[taken["session"] == label]
        stats = ev_tp2(sub)
        rows.append({"session": label, "plage_utc": f"{start:02d}h-{end:02d}h", **stats})

    summary_df = pd.DataFrame(rows)

    global_stats = ev_tp2(taken)
    print(f"\nGlobal (toutes sessions, trades PRIS) : N={global_stats['n']} | "
          f"Winrate={global_stats['winrate_pct']:.1f}% | EV(TP2)={global_stats['ev_tp2']:+.3f} R | "
          f"Somme des R(TP2)={global_stats['sum_r_tp2']:+.1f}")

    for _, r in summary_df.iterrows():
        print(f"\n--- {r['session']} ({r['plage_utc']} UTC) ---")
        print(f"  N={r['n']} (gagnants={r['wins']}, perdants={r['losses']})")
        if r["n"] > 0:
            print(f"  Winrate={r['winrate_pct']:.1f}% | RR TP2 moyen des gains={r['avg_rr_tp2_wins']:.2f} | "
                  f"EV(TP2)={r['ev_tp2']:+.3f} R | Somme des R(TP2)={r['sum_r_tp2']:+.1f}")
        else:
            print("  Aucun trade dans cette tranche.")
        if r["n"] < MIN_SAMPLE_WARN:
            print(f"  [AVERTISSEMENT STATISTIQUE] Échantillon < {MIN_SAMPLE_WARN} trades — "
                  "peu fiable, ne pas sur-interpréter cette tranche isolément.")

    print("\n" + "=" * 100)
    print("SIGNAL : sessions dont l'EV(TP2) s'écarte notablement de l'EV globale")
    print("=" * 100)
    global_ev = global_stats["ev_tp2"]
    for _, r in summary_df.iterrows():
        if r["n"] == 0 or pd.isna(r["ev_tp2"]):
            continue
        delta = r["ev_tp2"] - global_ev
        flag = abs(delta) >= 0.15
        marker = " <-- ÉCART NOTABLE" if flag else ""
        reliability = "peu fiable (n<50)" if r["n"] < MIN_SAMPLE_WARN else "échantillon correct"
        print(f"  {r['session']:22s} EV={r['ev_tp2']:+.3f} R (delta vs global {delta:+.3f}) "
              f"[{reliability}]{marker}")

    summary_df.to_csv("session_hour_summary.csv", index=False)
    print("\nRésumé enregistré dans session_hour_summary.csv")
    return summary_df


if __name__ == "__main__":
    main()
