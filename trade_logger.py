"""
Journalise chaque trade réellement exécuté sur MT5 dans trades_reels.csv (mêmes
colonnes que historique_lutessia.csv, plus compte_id/date_execution/mt5_ticket/
prix_cloture), et met à jour leur statut_final en interrogeant MT5 périodiquement.
"""
import csv
import json
import os
import time

import pandas as pd

import app_mt5

TRADES_REELS_PATH = "trades_reels.csv"
TRAILING_STATE_PATH = "trailing_stop_state.json"
TRAILING_LOG_PATH = "trailing_stop.log"
# Fraction de la distance SL initiale utilisée comme distance de trailing une fois
# tp2_init dépassé (ex: SL initial à 40 pips de l'entrée -> trailing à 6 pips du
# plus haut/bas atteint). Aligné sur la config verrouillée par simulation (commit
# 03fda00, session du 06-07/08/2026) : 0.15x dominant sous Monte Carlo flotte
# complète (était 0.2x).
TRAILING_STOP_FACTOR = 0.15
# Tolérance pour la comparaison "candidate_sl plus favorable que le SL actuel" :
# sans elle, une imprécision flottante (ex: 1.2620 - 0.0010 = 1.2610000000000001)
# peut déclencher un ajustement "fantôme" pile à l'identique du SL déjà en place
# (observé en test : un retracement exact au SL courant repoussait quand même un
# ordre TRADE_ACTION_SLTP inutile). 1e-6 est trois ordres de grandeur sous le pip
# le plus fin couramment coté (5 décimales forex), donc sans impact réel.
TRAILING_EPSILON = 1e-6

# --- Polling adaptatif (provisoire, cf. get_next_poll_delay_seconds) ---------
NORMAL_POLL_INTERVAL_SECONDS = 3600  # doit rester égal à STATUS_CHECK_INTERVAL_SECONDS (app.py)
FAST_POLL_INTERVAL_SECONDS = 120  # 2 min -- choisi dans la fourchette 1-5 min demandée
FAST_POLL_PROXIMITY_FRACTION = 0.20  # derniers 20% du chemin entrée -> tp2_init

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
    "score_force",
]


def _ensure_csv_exists():
    if not os.path.exists(TRADES_REELS_PATH):
        with open(TRADES_REELS_PATH, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(CSV_COLUMNS)


def log_trade_execution(date_creation, ticker, asset_class, timeframe, prix_entree,
                         stop_loss_init, tp1_init, tp2_init, rr_tp1, rr_tp2,
                         compte_id, date_execution, mt5_ticket, score_force=None):
    """Ajoute une ligne pour un trade qui vient d'être exécuté sur MT5.
    prix_entree doit être le prix de remplissage réel (retourné par
    app_mt5.place_market_order), pas le prix indiqué dans l'email du signal.
    statut_final et prix_cloture restent vides jusqu'à résolution. score_force (0-10,
    cf. scraper.py) est capturé pour usage futur uniquement -- accumulé à partir de
    maintenant, aucune donnée rétroactive ; None si absent de la fiche du signal."""
    _ensure_csv_exists()
    with open(TRADES_REELS_PATH, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            date_creation, ticker, asset_class, timeframe, prix_entree,
            stop_loss_init, tp1_init, tp2_init, rr_tp1, rr_tp2,
            "", compte_id, date_execution, mt5_ticket, "", score_force,
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


# --- Trailing stop post-TP2 --------------------------------------------------
#
# ATTENTION — conflit d'architecture non résolu, à trancher avant tout déploiement
# réel : app.py.executer_signal_reel() envoie désormais tp2_init comme TP FIXE au
# broker dès l'ouverture (correctif du 31/07). Or ce module ne peut détecter "le
# prix a dépassé tp2_init" que lors de son polling -- et si le TP fixe est encore
# actif à ce moment-là, MT5 aura déjà fermé la position toute seule, en temps réel,
# bien avant le prochain passage de manage_trailing_stops(). Tel quel, avec le
# polling horaire actuel (STATUS_CHECK_INTERVAL_SECONDS dans app.py), ce trailing
# stop n'aura quasiment jamais l'occasion de s'armer en conditions réelles. Pour
# qu'il fonctionne vraiment il faudra soit : (a) ne plus poser tp2_init comme TP
# dur à l'ouverture et laisser ce module piloter toute la sortie au-delà d'un
# certain seuil, soit (b) appeler manage_trailing_stops() à une fréquence bien
# plus élevée que 1h pour avoir une chance de désarmer le TP fixe avant qu'il ne
# se déclenche. Décision à prendre avant la mise en prod -- l'algorithme ci-dessous
# est correct et testé en isolation (mock), mais pas encore câblé dans app.py.

def _load_trailing_state():
    if os.path.exists(TRAILING_STATE_PATH):
        with open(TRAILING_STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_trailing_state(state):
    with open(TRAILING_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def _log_trailing_adjustment(ticket, old_sl, new_sl, price):
    line = (
        f"{time.strftime('%Y-%m-%dT%H:%M:%S')} ticket={ticket} "
        f"old_sl={old_sl} new_sl={new_sl} price={price}\n"
    )
    with open(TRAILING_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line)
    print(f"[trailing] ticket={ticket} SL {old_sl} -> {new_sl} (prix={price})")


def manage_trailing_stops():
    """Pour chaque trade encore ouvert (statut_final vide) dont le prix a atteint ou
    dépassé tp2_init, arme (si pas déjà fait) puis resserre un trailing stop réel sur
    MT5, à TRAILING_STOP_FACTOR × distance_SL_initiale du plus haut (achat) / plus
    bas (vente) atteint depuis l'armement -- ne resserre JAMAIS dans le sens
    défavorable. État (extremum atteint, dernier SL pushé) persisté dans
    TRAILING_STATE_PATH pour survivre aux redémarrages/cycles de polling. À l'armement,
    annule le TP fixe (modify_position_sltp(..., tp=0.0)) : voir l'avertissement
    d'architecture ci-dessus, non résolu."""
    _ensure_csv_exists()
    df = pd.read_csv(TRADES_REELS_PATH, dtype={"mt5_ticket": "Int64"})
    if df.empty:
        return

    open_mask = df["statut_final"].isna() | (df["statut_final"] == "")
    if not open_mask.any():
        return

    accounts = {a.account_id: a for a in app_mt5.load_accounts()}
    state = _load_trailing_state()

    for idx in df[open_mask].index:
        row = df.loc[idx]
        account = accounts.get(row["compte_id"])
        ticket = row["mt5_ticket"]
        if account is None or pd.isna(ticket):
            continue
        ticket = int(ticket)
        ticket_key = str(ticket)

        if not app_mt5.connect(account):
            continue
        try:
            position = app_mt5.get_open_position_raw(ticket)
            if position is None:
                # Position déjà fermée (TP/SL touché ou clôture manuelle) : rien à
                # ajuster, on nettoie un éventuel état de trailing orphelin.
                state.pop(ticket_key, None)
                continue

            tp2_init = float(row["tp2_init"])
            sl_initial_distance = abs(float(row["prix_entree"]) - float(row["stop_loss_init"]))
            if sl_initial_distance == 0:
                continue
            is_buy = position.type == app_mt5.POSITION_TYPE_BUY
            price = position.price_current
            trailing_distance = TRAILING_STOP_FACTOR * sl_initial_distance

            entry = state.get(ticket_key)
            beyond_tp2 = price >= tp2_init if is_buy else price <= tp2_init
            if entry is None and not beyond_tp2:
                continue  # pas encore atteint tp2_init : rien à faire

            if entry is None:
                # Armement : première fois que ce ticket dépasse tp2_init.
                entry = {"extremum": price, "last_sl": position.sl, "activated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
            else:
                entry["extremum"] = max(entry["extremum"], price) if is_buy else min(entry["extremum"], price)

            candidate_sl = (
                entry["extremum"] - trailing_distance if is_buy
                else entry["extremum"] + trailing_distance
            )
            favorable = (
                candidate_sl > position.sl + TRAILING_EPSILON if is_buy
                else candidate_sl < position.sl - TRAILING_EPSILON
            )

            if favorable:
                # tp=0.0 annule le TP fixe : à partir de l'armement, la sortie est
                # intégralement pilotée par ce SL suiveur (cf. avertissement en tête
                # de section).
                success = app_mt5.modify_position_sltp(ticket, position.symbol, candidate_sl, 0.0)
                if success:
                    _log_trailing_adjustment(ticket, position.sl, candidate_sl, price)
                    entry["last_sl"] = candidate_sl

            state[ticket_key] = entry
        finally:
            app_mt5.disconnect()

    _save_trailing_state(state)


def get_next_poll_delay_seconds():
    """Délai (en secondes) avant le prochain polling MT5 des trades ouverts :
    NORMAL_POLL_INTERVAL_SECONDS par défaut, ou FAST_POLL_INTERVAL_SECONDS dès qu'AU
    MOINS UN trade ouvert est dans les derniers FAST_POLL_PROXIMITY_FRACTION du
    chemin entrée -> tp2_init (ou l'a déjà dépassé sans être encore fermé) --
    solution PROVISOIRE pour donner au trailing stop post-TP2
    (manage_trailing_stops) une chance réelle de s'armer avant que le TP fixe posé
    à l'ouverture (executer_signal_reel) ne ferme la position de son côté, en
    remplacement d'un simple polling horaire trop grossier pour ça (cf.
    l'avertissement d'architecture en tête de section trailing stop).

    SEUIL DE DÉCLENCHEMENT (20% DU CHEMIN) ET FRÉQUENCE RAPIDE (2 MIN, DANS LA
    FOURCHETTE 1-5 MIN DEMANDÉE) CHOISIS PROVISOIREMENT CE SOIR (31/07), PAS ENCORE
    VALIDÉS PAR DES DONNÉES RÉELLES DE VITESSE DE MOUVEMENT DE PRIX -- À REVALIDER
    (voir session du lendemain pour la validation empirique : à quelle vitesse le
    prix parcourt-il typiquement les derniers 20% vers TP2 sur nos paires, pour
    confirmer que ni le seuil ni la fréquence de 2 min ne risquent de rater un
    franchissement entre deux cycles).

    Coût vérifié négligeable pour un polling plus fréquent : connexion MT5 locale
    (IPC, pas un appel réseau externe comme CentralCharts) mesurée à ~7ms par cycle
    connect+requête+disconnect sur ce VPS, zéro erreur sur 30 appels rapprochés --
    aucun risque de rate-limit comparable à l'incident CentralCharts du 29/07 (qui
    concernait un site tiers derrière Cloudflare, pas MT5 en local)."""
    _ensure_csv_exists()
    df = pd.read_csv(TRADES_REELS_PATH, dtype={"mt5_ticket": "Int64"})
    if df.empty:
        return NORMAL_POLL_INTERVAL_SECONDS

    open_mask = df["statut_final"].isna() | (df["statut_final"] == "")
    if not open_mask.any():
        return NORMAL_POLL_INTERVAL_SECONDS

    accounts = {a.account_id: a for a in app_mt5.load_accounts()}

    for idx in df[open_mask].index:
        row = df.loc[idx]
        account = accounts.get(row["compte_id"])
        ticket = row["mt5_ticket"]
        if account is None or pd.isna(ticket):
            continue
        ticket = int(ticket)

        if not app_mt5.connect(account):
            continue
        try:
            position = app_mt5.get_open_position_raw(ticket)
            if position is None:
                continue  # fermée : ne contribue pas à accélérer le polling

            prix_entree = float(row["prix_entree"])
            tp2_init = float(row["tp2_init"])
            total_distance = abs(tp2_init - prix_entree)
            if total_distance == 0:
                continue

            is_buy = position.type == app_mt5.POSITION_TYPE_BUY
            remaining = (tp2_init - position.price_current) if is_buy else (position.price_current - tp2_init)
            remaining_fraction = remaining / total_distance

            # remaining_fraction <= 0 : tp2_init déjà dépassé (trailing potentiellement
            # armé, ou en passe de l'être) -- reste en polling rapide tant que la
            # position n'est pas fermée, pour bien suivre le trailing en cours.
            if remaining_fraction <= FAST_POLL_PROXIMITY_FRACTION:
                return FAST_POLL_INTERVAL_SECONDS
        finally:
            app_mt5.disconnect()

    return NORMAL_POLL_INTERVAL_SECONDS
