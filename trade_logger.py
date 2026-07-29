"""
Journalise chaque trade réellement exécuté sur MT5 dans trades_reels.csv (mêmes
colonnes que historique_lutessia.csv, plus compte_id/date_execution/mt5_ticket/
prix_cloture), et met à jour leur statut_final en interrogeant MT5 périodiquement.
"""
import csv
import os

import pandas as pd

import app_mt5

TRADES_REELS_PATH = "trades_reels.csv"

CSV_COLUMNS = [
    "date_creation",
    "ticker",
    "asset_class",
    "timeframe",
    "prix_entree",
    "stop_loss_init",
    "tp1_init",
    "tp2_init",
    "rr_tp1",
    "rr_tp2",
    "statut_final",
    "compte_id",
    "date_execution",
    "mt5_ticket",
    "prix_cloture",
]


def _ensure_csv_exists():
    if not os.path.exists(TRADES_REELS_PATH):
        with open(TRADES_REELS_PATH, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(CSV_COLUMNS)


def log_trade_execution(date_creation, ticker, asset_class, timeframe, prix_entree,
                         stop_loss_init, tp1_init, tp2_init, rr_tp1, rr_tp2,
                         compte_id, date_execution, mt5_ticket):
    """Ajoute une ligne pour un trade qui vient d'être exécuté sur MT5.
    prix_entree doit être le prix de remplissage réel (retourné par
    app_mt5.place_market_order), pas le prix indiqué dans l'email du signal.
    statut_final et prix_cloture restent vides jusqu'à résolution."""
    _ensure_csv_exists()
    with open(TRADES_REELS_PATH, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            date_creation, ticker, asset_class, timeframe, prix_entree,
            stop_loss_init, tp1_init, tp2_init, rr_tp1, rr_tp2,
            "", compte_id, date_execution, mt5_ticket, "",
        ])


def update_open_trades():
    """Interroge MT5 pour chaque trade encore ouvert (statut_final vide) et met à
    jour statut_final + prix_cloture s'il est désormais clos. À appeler périodiquement
    (ex: toutes les heures, cf. app.py)."""
    _ensure_csv_exists()
    df = pd.read_csv(TRADES_REELS_PATH, dtype={"mt5_ticket": "Int64"})
    if df.empty:
        return

    open_mask = df["statut_final"].isna() | (df["statut_final"] == "")
    if not open_mask.any():
        return

    accounts = {a.account_id: a for a in app_mt5.load_accounts()}
    updated = 0

    for idx in df[open_mask].index:
        row = df.loc[idx]
        account = accounts.get(row["compte_id"])
        ticket = row["mt5_ticket"]
        if account is None or pd.isna(ticket):
            continue

        if not app_mt5.connect(account):
            continue
        try:
            statut, close_price = app_mt5.get_position_status(int(ticket))
        finally:
            app_mt5.disconnect()

        if statut in ("OBJECTIF ATTEINT", "INVALIDÉE"):
            df.loc[idx, "statut_final"] = statut
            df.loc[idx, "prix_cloture"] = close_price
            updated += 1

    if updated:
        df.to_csv(TRADES_REELS_PATH, index=False)
        print(f"[trade_logger] {updated} trade(s) mis à jour dans {TRADES_REELS_PATH}.")
