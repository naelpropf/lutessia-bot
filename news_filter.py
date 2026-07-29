"""
Filtre news sur les NOUVELLES ENTRÉES uniquement (jamais les positions déjà ouvertes) :
si un signal validé arrive dans une fenêtre de +/- NEWS_WINDOW_MINUTES autour d'une
news à fort impact (NFP, CPI, décisions de taux des banques centrales majeures) sur
une devise de l'actif concerné, retarde l'exécution jusqu'à la fin de la fenêtre —
ne l'annule et ne le rejette jamais.

Source : le flux JSON public utilisé par le widget calendrier de ForexFactory
(nfs.faireconomy.media/ff_calendar_thisweek.json), gratuit, sans clé, robots.txt
l'autorise explicitement. Mis en cache localement pour ne pas le requêter à chaque
signal (CACHE_MAX_AGE_HOURS).
"""
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

# Évite un crash sur les emojis/accents si la console Windows est en cp1252
# (cf. app.py — nécessaire aussi ici si ce module est utilisé/testé seul).
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
CACHE_PATH = Path("ff_calendar_cache.json")
CACHE_MAX_AGE_HOURS = 6

NEWS_WINDOW_MINUTES = 2
DELAY_LOG_PATH = "news_filter.log"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

FOREX_PATTERN = re.compile(r"^([A-Z]{3})/([A-Z]{3})$")

# Actifs non-forex de notre univers filtré : devise(s) dont dépend leur risque news.
INDEX_CURRENCY_MAP = [
    ("DAX40", ["EUR"]),
    ("DJ30", ["USD"]),
    ("NASDAQ100", ["USD"]),
    ("S&P500", ["USD"]),
    ("FTSE100", ["GBP"]),
]


def extract_currencies(ticker):
    """Devises dont une news à fort impact doit retarder l'exécution sur ce ticker."""
    m = FOREX_PATTERN.match(ticker)
    if m:
        return [m.group(1), m.group(2)]
    upper = ticker.upper()
    if "BTC/USD" in upper or "ETH/USD" in upper:
        return ["USD"]
    for keyword, currencies in INDEX_CURRENCY_MAP:
        if keyword in upper:
            return currencies
    return []


def _parse_event_datetime(raw_date):
    # Format ForexFactory : "2026-07-29T14:00:00-04:00" (offset explicite, converti en UTC).
    dt = datetime.fromisoformat(raw_date)
    return dt.astimezone(timezone.utc)


def _fetch_calendar():
    response = requests.get(CALENDAR_URL, headers=HEADERS, timeout=15)
    response.raise_for_status()
    raw_events = response.json()

    events = []
    for e in raw_events:
        if e.get("impact") != "High" or not e.get("date"):
            continue
        try:
            event_dt = _parse_event_datetime(e["date"])
        except ValueError:
            continue
        events.append({"datetime_utc": event_dt, "currency": e.get("country", ""), "title": e.get("title", "")})
    return events


def _load_cached_calendar():
    if CACHE_PATH.exists():
        age_hours = (time.time() - CACHE_PATH.stat().st_mtime) / 3600
        if age_hours < CACHE_MAX_AGE_HOURS:
            with open(CACHE_PATH, encoding="utf-8") as f:
                cached = json.load(f)
            return [
                {"datetime_utc": datetime.fromisoformat(e["datetime_utc"]), "currency": e["currency"], "title": e["title"]}
                for e in cached
            ]

    try:
        events = _fetch_calendar()
    except (requests.RequestException, ValueError) as e:
        print(f"⚠️ [news_filter] Échec de récupération du calendrier économique : {e}")
        return []

    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump([{**e, "datetime_utc": e["datetime_utc"].isoformat()} for e in events], f)
    return events


def find_blocking_event(ticker, now_utc=None):
    """Retourne l'événement High impact qui bloque actuellement une NOUVELLE entrée sur
    ce ticker (now_utc dans sa fenêtre +/- NEWS_WINDOW_MINUTES), ou None si aucun."""
    now_utc = now_utc or datetime.now(timezone.utc)
    currencies = extract_currencies(ticker)
    if not currencies:
        return None

    for event in _load_cached_calendar():
        if event["currency"] not in currencies:
            continue
        window_start = event["datetime_utc"] - timedelta(minutes=NEWS_WINDOW_MINUTES)
        window_end = event["datetime_utc"] + timedelta(minutes=NEWS_WINDOW_MINUTES)
        if window_start <= now_utc <= window_end:
            return event

    return None


def _log_delay(ticker, event, delay_seconds):
    line = (
        f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} | "
        f"signal={ticker} | news={event['currency']} {event['title']} "
        f"@ {event['datetime_utc'].isoformat(timespec='seconds')} | "
        f"delai={delay_seconds:.0f}s\n"
    )
    with open(DELAY_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line)
    print(f"⏳ [news_filter] Exécution retardée pour {ticker} ({delay_seconds:.0f}s, news : {event['title']})")


def apply_news_delay(ticker):
    """À appeler juste avant l'exécution d'une NOUVELLE entrée (jamais sur une position
    déjà ouverte). Bloque (time.sleep) jusqu'à la fin de la fenêtre si une news à fort
    impact concerne l'actif — ne retourne qu'une fois l'exécution possible, ne rejette
    et n'annule jamais le signal."""
    event = find_blocking_event(ticker)
    if event is None:
        return

    window_end = event["datetime_utc"] + timedelta(minutes=NEWS_WINDOW_MINUTES)
    delay_seconds = (window_end - datetime.now(timezone.utc)).total_seconds()
    if delay_seconds <= 0:
        return

    _log_delay(ticker, event, delay_seconds)
    time.sleep(delay_seconds)
