"""
Mesure du slippage à l'exécution : prix du signal Lutessia (prix_entree extrait de
la fiche) vs prix de remplissage réel MT5, latence email->exécution, session horaire.

Pas de rejet ni de blocage automatique -- pure mesure, écrite dans un fichier dédié
(slippage_log.csv), pour collecter des données réelles avant l'ouverture des 3
comptes principaux (cf. compte de test 5k€). Appelé depuis app.executer_signal_reel()
juste après un fill réussi.
"""
import csv
import os
from datetime import datetime, timezone

SLIPPAGE_LOG_PATH = "slippage_log.csv"

FIELDNAMES = [
    "date_execution", "ticker", "direction", "account_id", "ticket",
    "signal_price", "fill_price", "slippage_pips", "slippage_pct",
    "email_sent_at", "latency_seconds", "session",
]


def _pip_size(ticker):
    return 0.01 if "JPY" in ticker else 0.0001


def _session_horaire(dt_utc):
    """Découpage simple par heure UTC (chevauchements réels ignorés, juste une
    étiquette indicative pour repérer des patterns de slippage par session) :
    Asie 00-07h, Londres 07-13h, chevauchement Londres/NY 13-16h, New York 16-21h,
    creux 21-00h."""
    hour = dt_utc.hour
    if 0 <= hour < 7:
        return "asie"
    if 7 <= hour < 13:
        return "londres"
    if 13 <= hour < 16:
        return "londres_ny"
    if 16 <= hour < 21:
        return "new_york"
    return "creux"


def log_slippage(ticker, direction, account_id, ticket, signal_price, fill_price,
                  email_sent_at=None, date_execution=None):
    """signal_price : prix_entree extrait de la fiche Lutessia au moment du parsing.
    fill_price : prix réel de remplissage renvoyé par MT5 (place_market_order).
    email_sent_at : datetime (tz-aware si possible) tirée du header Date de l'email
    Lutessia -- None si indisponible (n'empêche pas le log, latency_seconds sera
    vide). date_execution : datetime de l'exécution MT5, now() UTC si omis."""
    if date_execution is None:
        date_execution = datetime.now(timezone.utc)

    pip = _pip_size(ticker)
    signed = fill_price - signal_price
    slippage_pips = (signed if direction == "buy" else -signed) / pip
    slippage_pct = (signed / signal_price) * 100 if signal_price else None

    latency_seconds = None
    if email_sent_at is not None:
        latency_seconds = (date_execution - email_sent_at).total_seconds()

    session = _session_horaire(date_execution if date_execution.tzinfo else date_execution.replace(tzinfo=timezone.utc))

    row = {
        "date_execution": date_execution.isoformat(),
        "ticker": ticker,
        "direction": direction,
        "account_id": account_id,
        "ticket": ticket,
        "signal_price": signal_price,
        "fill_price": fill_price,
        "slippage_pips": round(slippage_pips, 2),
        "slippage_pct": round(slippage_pct, 5) if slippage_pct is not None else None,
        "email_sent_at": email_sent_at.isoformat() if email_sent_at is not None else None,
        "latency_seconds": round(latency_seconds, 1) if latency_seconds is not None else None,
        "session": session,
    }

    file_exists = os.path.isfile(SLIPPAGE_LOG_PATH)
    with open(SLIPPAGE_LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

    return row
