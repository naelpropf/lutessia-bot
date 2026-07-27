import pandas as pd


def analyze_backtest(csv_path="historique_lutessia.csv"):
  print("Chargement des données d'historique...")
  try:
    df = pd.read_csv(csv_path)
  except FileNotFoundError:
    print(f"Erreur : Le fichier {csv_path} est introuvable.")
    return

  # 1. Nettoyage strict : Exclure les trades "en cours" ou "seuil préservé" sans statut terminal
  # Seuls les statuts finaux clairs (ex: Objectif atteint / Invalidée) sont pris en compte
  terminal_statuses = ["OBJECTIF_ATTEINT", "INVALIDEE"]
  df_clean = df[df["statut_final"].isin(terminal_statuses)].copy()

  print(
      f"Total brut : {len(df)} trades | Total après exclusion des trades en"
      f" cours : {len(df_clean)}"
  )

  total_trades = len(df_clean)
  if total_trades == 0:
    print("Aucun trade terminé disponible pour le calcul.")
    return

  # 2. Calcul du Winrate Global
  wins = len(df_clean[df_clean["statut_final"] == "OBJECTIF_ATTEINT"])
  global_winrate = (wins / total_trades) * 100
  print(f"\nWinrate Global : {global_winrate:.2f}% ({wins}/{total_trades})")

  # 3. Segmentation multi-dimensionnelle et contrôle de la taille d'échantillon
  print("\n--- Analyse par Segment (R:R >= 2.0) ---")

  min_rr = 2.0
  filtered_df = df_clean[df_clean["rr_theorique"] >= min_rr]

  # Groupement par classe d'actif et unité de temps
  segments = filtered_df.groupby(["asset_class", "timeframe"])

  for name, group in segments:
    count = len(group)
    group_wins = len(group[group["statut_final"] == "OBJECTIF_ATTEINT"])
    segment_winrate = (group_wins / count * 100) if count > 0 else 0

    asset_cls, tf = name
    print(f"\nSegment -> Classe : {asset_cls} | Timeframe : {tf}")
    print(f"  - Occurrences trouvées : {count}")

    # Contrôle de robustesse statistique (seuil minimal recommandé : 50 occurrences)
    if count < 50:
      print(
          "  [AVERTISSEMENT STATISTIQUE] Échantillon inférieur à 50 trades."
          " Marge d'erreur trop élevée pour valider une règle."
      )
    else:
      print(
          f"  - Winrate validé sur ce segment : {segment_winrate:.2f}%"
          f" ({group_wins}/{count})"
      )


if __name__ == "__main__":
  analyze_backtest()
