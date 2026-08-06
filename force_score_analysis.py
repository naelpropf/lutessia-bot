"""
Analyse du score "Force" de Lutessia (capturé via le rescraping rétroactif terminé
cette nuit, historique_lutessia_15k_force.csv) sur la population de référence
(rr_tp1>=1.5, payoff réaliste + trailing, trailing_realistic_payoff_detail.csv,
472 trades) : corrélation brute, segmentation par tranche, test de filtre
supplémentaire, test de pondérateur de taille de position (Monte Carlo fleet).
"""
import math

import numpy as np
import pandas as pd

FORCE_PATH = "historique_lutessia_15k_force.csv"
POP_PATH = "trailing_realistic_payoff_detail.csv"
WIN_STATUS = "OBJECTIF ATTEINT"
MIN_SAMPLE_SIZE = 50


def load_population_with_force():
    pop = pd.read_csv(POP_PATH)
    force = pd.read_csv(FORCE_PATH)[["ticker", "date_creation", "score_force"]]
    merged = pop.merge(force, on=["ticker", "date_creation"], how="left")
    missing = merged["score_force"].isna().sum()
    print(f"Population de référence : {len(merged)} trades | Force manquant : {missing}")
    return merged.dropna(subset=["score_force"])


def pearson(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    return float(np.corrcoef(x, y)[0, 1])


def section1(df):
    print("\n" + "=" * 100)
    print("1. PRÉSENCE ET PLAGE DE FORCE")
    print("=" * 100)
    print(df["score_force"].describe())


def section2(df):
    print("\n" + "=" * 100)
    print("2. CORRÉLATION BRUTE")
    print("=" * 100)
    win = (df["statut_final"] == WIN_STATUS).astype(int)
    r_win = pearson(df["score_force"], win)
    r_r = pearson(df["score_force"], df["r_realiste"])
    n = len(df)
    # test de significativité (t-test sur r de Pearson)
    def sig(r, n):
        if abs(r) >= 1:
            return float("inf")
        t = r * math.sqrt((n - 2) / (1 - r ** 2))
        return t
    t_win = sig(r_win, n)
    t_r = sig(r_r, n)
    print(f"Corrélation Force <-> victoire (OBJECTIF ATTEINT, point-bisériale) : r = {r_win:+.4f} | t = {t_win:+.2f} (n={n})")
    print(f"Corrélation Force <-> R réaliste (r_realiste)                     : r = {r_r:+.4f} | t = {t_r:+.2f} (n={n})")
    print("(|t| > ~1.96 -> significatif à 5% avec n grand ; |t| > ~2.58 -> significatif à 1%)")
    return r_win, r_r


def section3(df):
    print("\n" + "=" * 100)
    print("3. SEGMENTATION PAR TRANCHE DE FORCE")
    print("=" * 100)
    bins = [-np.inf, 7, 8, 9, np.inf]
    labels = ["<7", "7-8", "8-9", ">9"]
    df = df.copy()
    df["force_bin"] = pd.cut(df["score_force"], bins=bins, labels=labels, right=False)

    rows = []
    for label in labels:
        seg = df[df["force_bin"] == label]
        n = len(seg)
        if n == 0:
            continue
        wins = (seg["statut_final"] == WIN_STATUS).sum()
        winrate = wins / n
        avg_rr_wins = seg[seg["statut_final"] == WIN_STATUS]["r_realiste"].mean() if wins > 0 else None
        ev = seg["r_realiste"].mean()  # EV réaliste = moyenne directe de r_realiste (déjà -1 pour perdants)
        warn = " [AVERTISSEMENT n<50]" if n < MIN_SAMPLE_SIZE else ""
        print(f"Force {label:<5} : n={n:<4} | winrate {winrate*100:5.1f}% | EV réaliste {ev:+.3f}R{warn}")
        rows.append({"force_bin": label, "n": n, "winrate": winrate, "ev_realiste": ev})
    return pd.DataFrame(rows)


def section4(df_all_candidates):
    print("\n" + "=" * 100)
    print("4. TEST DE FILTRE SUPPLÉMENTAIRE (Force >= seuil, en plus de rr_tp1>=1.5)")
    print("=" * 100)
    baseline_n = len(df_all_candidates)
    baseline_ev = df_all_candidates["r_realiste"].mean()
    baseline_winrate = (df_all_candidates["statut_final"] == WIN_STATUS).mean()
    print(f"Baseline (rr_tp1>=1.5 seul)        : n={baseline_n} | winrate {baseline_winrate*100:.2f}% | EV {baseline_ev:+.3f}R")

    for thresh in [7.0, 7.5, 8.0, 8.5]:
        seg = df_all_candidates[df_all_candidates["score_force"] >= thresh]
        n = len(seg)
        if n == 0:
            print(f"Force >= {thresh} : aucun trade capturé")
            continue
        winrate = (seg["statut_final"] == WIN_STATUS).mean()
        ev = seg["r_realiste"].mean()
        pct_capture = n / baseline_n * 100
        warn = " [AVERTISSEMENT n<50]" if n < MIN_SAMPLE_SIZE else ""
        print(f"Force >= {thresh} : n={n:<4} ({pct_capture:5.1f}% du volume) | winrate {winrate*100:5.2f}% | "
              f"EV {ev:+.3f}R (delta vs baseline {ev-baseline_ev:+.3f}R){warn}")


def main():
    df = load_population_with_force()
    section1(df)
    section2(df)
    seg_df = section3(df)
    seg_df.to_csv("force_score_segments.csv", index=False)
    section4(df)
    df.to_csv("population_with_force.csv", index=False)
    print(f"\nPopulation fusionnée (avec Force) enregistrée dans population_with_force.csv")


if __name__ == "__main__":
    main()
