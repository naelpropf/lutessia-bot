import pandas as pd

def analyze_backtest(csv_path="historique_lutessia.csv"):
    print("Chargement des données d'historique...")
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"Erreur : Le fichier {csv_path} est introuvable.")
        return

    terminal_statuses = ["OBJECTIF_ATTEINT", "STOP_LOSS_touche"]
    df_clean = df[df["statut_final"].isin(terminal_statuses)]

    print(
        f"Total brut : {len(df(df)) if 'df' in locals() else len(df)} trades | "
        f"Cours valides : {len(df_clean)}"
    )

    total_trades = len(df_clean)
    if total_trades == 0:
        print("Aucun trade terminé disponible pour l'analyse.")
        return

    wins = len(df_clean[df_clean["statut_final"] == "OBJECTIF_ATTEINT"])
    global_winrate = (wins / total_trades) * 100
    print(f"\nWinrate Global : {global_winrate:.2f}% ({wins}/{total_trades})")

    print("\n--- Analyse par Segment (R:R & Actif) ---")
    min_rr = 2.0
    filtered_df = df_clean[df_clean["rr_theorique"] >= min_rr]

    if "asset_class" in filtered_df.columns and "timeframe" in filtered_df.columns:
        segments = filtered_df.groupby(["asset_class", "timeframe"])

        for name, group in segments:
            count = len(group)
            group_wins = len(group[group["statut_final"] == "OBJECTIF_ATTEINT"])
            segment_winrate = (group_wins / count) * 100 if count > 0 else 0

            asset_cls, tf = name
            print(f"\nSegment -> Classe : {asset_cls} | Timeframe : {tf}")
            print(f" - Occurrences trouvées : {count}")

            if count < 50:
                print(
                    "   [AVERTISSEMENT STATISTIQUE] Échantillon trop faible (< 50). "
                    "Marge d'erreur trop élevée pour valider la stratégie."
                )
            else:
                print(
                    f" - Winrate validé sur ce segment : {segment_winrate:.2f}% "
                    f"({group_wins}/{count})"
                )

if __name__ == "__main__":
    analyze_backtest()
