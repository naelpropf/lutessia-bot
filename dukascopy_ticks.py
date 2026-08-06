"""
Récupération de ticks bid/ask Dukascopy (gratuit, pas d'auth, historique remontant à
au moins 2010 testé) -- remplace yfinance pour l'analyse de slippage, dont la
résolution (H1 max sur 730 jours) était insuffisante pour comparer le prix Lutessia
au prix réellement disponible au moment du signal.

Format des fichiers .bi5 (documenté/rétro-ingénieré, largement utilisé pour le
backtest retail) : un fichier par paire/heure, compressé LZMA, 20 octets/tick
(big-endian) : ms écoulés depuis le début de l'heure (I), ask*point_factor (I),
bid*point_factor (I), volume ask (f), volume bid (f). point_factor = 1e3 pour les
paires cotées en JPY, 1e5 sinon (vérifié empiriquement : EURUSD ~102644 -> 1.02644).

Cache local par heure (comme tp_sequence_analysis.fetch_h1_history pour le H1) --
ne re-télécharge jamais une heure déjà en cache.
"""
import datetime as dt
import lzma
import struct
import time
from pathlib import Path

import pandas as pd
import requests

CACHE_DIR = Path("dukascopy_cache")
BASE_URL = "https://datafeed.dukascopy.com/datafeed"
REQUEST_DELAY_SECONDS = 0.3  # anti-429 : Dukascopy limite le débit sans en-tête Retry-After
MAX_RETRIES_429 = 5


def _dukascopy_symbol(ticker):
    """'EUR/USD' -> 'EURUSD'"""
    return ticker.replace("/", "")


def _point_factor(ticker):
    return 1e3 if ticker.endswith("/JPY") else 1e5


def fetch_ticks_hour(ticker, hour_dt):
    """hour_dt : datetime naïf UTC, tronqué à l'heure. Retourne un DataFrame
    [datetime, ask, bid] (prix réels, déjà divisés par point_factor) ou vide si
    marché fermé (week-end/férié -- fichier existe mais 0 octet)."""
    symbol = _dukascopy_symbol(ticker)
    hour_dt = hour_dt.replace(minute=0, second=0, microsecond=0)

    symbol_dir = CACHE_DIR / symbol
    symbol_dir.mkdir(parents=True, exist_ok=True)
    cache_file = symbol_dir / f"{hour_dt:%Y-%m-%d_%Hh}.csv"

    if cache_file.exists():
        if cache_file.stat().st_size == 0:
            return pd.DataFrame(columns=["datetime", "ask", "bid"])
        return pd.read_csv(cache_file, parse_dates=["datetime"])

    month_0indexed = hour_dt.month - 1
    url = (f"{BASE_URL}/{symbol}/{hour_dt.year}/{month_0indexed:02d}/"
           f"{hour_dt.day:02d}/{hour_dt.hour:02d}h_ticks.bi5")

    r = None
    for attempt in range(MAX_RETRIES_429):
        try:
            r = requests.get(url, timeout=20)
        except requests.RequestException as e:
            print(f"  [dukascopy] échec réseau {symbol} {hour_dt} : {e}")
            return pd.DataFrame(columns=["datetime", "ask", "bid"])
        if r.status_code == 429:
            time.sleep(2 * (attempt + 1))  # backoff -- pas de Retry-After fourni par Dukascopy
            continue
        break
    time.sleep(REQUEST_DELAY_SECONDS)

    if r.status_code == 429:
        print(f"  [dukascopy] 429 persistant sur {symbol} {hour_dt} après {MAX_RETRIES_429} tentatives -- "
              f"NON mis en cache, à retenter plus tard.")
        return pd.DataFrame(columns=["datetime", "ask", "bid"])

    if r.status_code != 200 or len(r.content) == 0:
        cache_file.touch()  # marque "vide" en cache (marché fermé) pour ne pas retenter
        return pd.DataFrame(columns=["datetime", "ask", "bid"])

    try:
        raw = lzma.decompress(r.content)
    except lzma.LZMAError:
        cache_file.touch()
        return pd.DataFrame(columns=["datetime", "ask", "bid"])

    point_factor = _point_factor(ticker)
    n_ticks = len(raw) // 20
    rows = []
    for i in range(n_ticks):
        ms, ask_raw, bid_raw, _, _ = struct.unpack(">IIIff", raw[i * 20:(i + 1) * 20])
        rows.append((hour_dt + dt.timedelta(milliseconds=ms), ask_raw / point_factor, bid_raw / point_factor))

    df = pd.DataFrame(rows, columns=["datetime", "ask", "bid"])
    df.to_csv(cache_file, index=False)
    return df


def fetch_nearest_tick(ticker, target_dt, max_search_hours=2):
    """Cherche le tick le plus proche de target_dt (datetime naïf UTC), en élargissant
    la recherche heure par heure (avant ET après) jusqu'à max_search_hours si l'heure
    exacte est vide (marché fermé pile à ce moment, rare mais possible en bordure de
    session). Retourne (tick_datetime, ask, bid, delta_secondes) ou None."""
    target_hour = target_dt.replace(minute=0, second=0, microsecond=0)
    for offset in range(0, max_search_hours + 1):
        for sign in ([0] if offset == 0 else [-1, 1]):
            hour = target_hour + dt.timedelta(hours=sign * offset)
            df = fetch_ticks_hour(ticker, hour)
            if df.empty:
                continue
            deltas = (df["datetime"] - target_dt).abs()
            idx = deltas.idxmin()
            return df.loc[idx, "datetime"], df.loc[idx, "ask"], df.loc[idx, "bid"], deltas.loc[idx].total_seconds()
    return None
