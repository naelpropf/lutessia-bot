import pandas as pd

TERMINAL_STATUSES = ["OBJECTIF ATTEINT", "INVALIDÉE"]
WIN_STATUS = "OBJECTIF ATTEINT"
MIN_SAMPLE_SIZE = 50
MIN_RR = 2.0


def _compute_metrics(group, rr_column):
    count = len(group)
    wins_df = group[group["statut_final"] == WIN_STATUS]
    wins = len(wins_df)
    winrate = wins / count if count > 0 else 0.0

    avg_rr_wins = wins_df[rr_column].mean() if wins > 0 else None
    std_rr_wins = wins_df[rr_column].std() if wins > 1 else None
    ev = winrate * avg_rr_wins - (1 - winrate) if avg_rr_wins is not None else None

    return {
        "count": count,
        "wins": wins,
        "winrate": winrate,
        "avg_rr_wins": avg_rr_wins,
        "std_rr_wins": std_rr_wins,
        "ev": ev,
    }


def _print_metrics(metrics):
    count = metrics["count"]
    print(f" - Occurrences trouvées : {count}")
    print(f" - Winrate : {metrics['winrate'] * 100:.2f}% ({metrics['wins']}/{count})")

    avg_rr_wins = metrics["avg_rr_wins"]
    print(f" - RR moyen des gains : {avg_rr_wins:.2f}" if avg_rr_wins is not None else " - RR moyen des gains : n/a (aucun trade gagnant)")

    std_rr_wins = metrics["std_rr_wins"]
    print(f" - Écart-type RR des gains : {std_rr_wins:.2f}" if std_rr_wins is not None else " - Écart-type RR des gains : n/a")

    ev = metrics["ev"]
    print(f" - EV : {ev:+.3f} R" if ev is not None else " - EV : n/a")

    if count < MIN_SAMPLE_SIZE:
        print(
            f"   [AVERTISSEMENT STATISTIQUE] Échantillon trop faible (< {MIN_SAMPLE_SIZE}). "
            "Marge d'erreur trop élevée pour valider la stratégie."
        )


def _analyze_rr_segment(df_clean, rr_column, label):
    print(f"\n--- Analyse par Segment (R:R {label} & Actif) ---")
    filtered_df = df_clean[df_clean[rr_column] >= MIN_RR]

    print(f"\nGlobal ({label}, RR >= {MIN_RR}) :")
    _print_metrics(_compute_metrics(filtered_df, rr_column))

    if "asset_class" not in filtered_df.columns or "timeframe" not in filtered_df.columns:
        return

    segments = filtered_df.groupby(["asset_class", "timeframe"])

    for name, group in segments:
        asset_cls, tf = name
        print(f"\nSegment -> Classe : {asset_cls} | Timeframe : {tf}")
        _print_metrics(_compute_metrics(group, rr_column))


def analyze_backtest(csv_path="historique_lutessia.csv"):
    print("Chargement des données d'historique...")
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"Erreur : Le fichier {csv_path} est introuvable.")
        return

    df_clean = df[df["statut_final"].isin(TERMINAL_STATUSES)]

    print(f"Total brut : {len(df)} trades | Cours valides : {len(df_clean)}")

    total_trades = len(df_clean)
    if total_trades == 0:
        print("Aucun trade terminé disponible pour l'analyse.")
        return

    wins = len(df_clean[df_clean["statut_final"] == WIN_STATUS])
    global_winrate = (wins / total_trades) * 100
    print(f"\nWinrate Global : {global_winrate:.2f}% ({wins}/{total_trades})")

    _analyze_rr_segment(df_clean, "rr_tp1", "TP1")
    _analyze_rr_segment(df_clean, "rr_tp2", "TP2")


if __name__ == "__main__":
    analyze_backtest()
