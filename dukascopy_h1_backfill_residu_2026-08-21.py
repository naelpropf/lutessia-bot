"""dukascopy_h1_backfill_residu_2026-08-21.py (v2, parallelise)

Backfill H1 via Dukascopy (ticks bid/ask -> OHLC par heure, prix mid) pour les 3
legs FX (EURUSD/GBPUSD/AUDUSD) utilisees par la synthese metaux, sur la fenetre
residuelle ou meme le backfill MT5 manque (2021-04->2022-01). v1 sequentiel etait
beaucoup trop lent dans cet environnement (connectivite Dukascopy flaky, retries
en cascade) -- v2 parallelise avec ThreadPoolExecutor, chaque heure ecrit son
propre fichier de cache (dukascopy_ticks.fetch_ticks_hour), donc pas de conflit
d'ecriture entre threads.

Sortie : etend les fichiers data/mt5_h1_backfill/mt5_h1_backfill_{SYMBOL}.pi_
2026-08-21.csv existants avec les bougies Dukascopy plus anciennes (prefixees),
meme schema exact. Backup de l'original conserve avant ecrasement."""
import datetime as dt
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

import dukascopy_ticks as dk

MT5_DIR = Path("data/mt5_h1_backfill")
DATE_TAG = "2026-08-21"

SYMBOLS = {
    "EURUSD.pi": ("EUR/USD", "EUR/USD"),
    "GBPUSD.pi": ("GBP/USD", "GBP/USD"),
    "AUDUSD.pi": ("AUD/USD", "AUD/USD"),
}

START = dt.datetime(2021, 3, 25, 0)
END = dt.datetime(2022, 1, 3, 0)
N_WORKERS = 6


def _fetch_one(dukascopy_ticker, hour, max_retries=3):
    for attempt in range(max_retries):
        df = dk.fetch_ticks_hour(dukascopy_ticker, hour)
        if not df.empty:
            return hour, df
        cache_file = dk.CACHE_DIR / dk._dukascopy_symbol(dukascopy_ticker) / f"{hour:%Y-%m-%d_%Hh}.csv"
        if cache_file.exists():
            return hour, df  # vide et mis en cache -> vraie fermeture de marche
        time.sleep(2 * (attempt + 1))
    return hour, df


def build_h1_from_ticks(dukascopy_ticker, start, end):
    hours = []
    h = start
    while h < end:
        hours.append(h)
        h += dt.timedelta(hours=1)

    rows = []
    done = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=N_WORKERS) as ex:
        futures = {ex.submit(_fetch_one, dukascopy_ticker, h): h for h in hours}
        for fut in as_completed(futures):
            hour, df = fut.result()
            done += 1
            if not df.empty:
                mid = (df["ask"] + df["bid"]) / 2
                rows.append({
                    "datetime": hour,
                    "open": mid.iloc[0], "high": mid.max(), "low": mid.min(), "close": mid.iloc[-1],
                    "tick_volume": len(df),
                })
            if done % 300 == 0:
                elapsed = time.time() - t0
                rate = done / elapsed
                eta_min = (len(hours) - done) / rate / 60 if rate > 0 else float("nan")
                print(f"    ... {done}/{len(hours)} heures traitees, {len(rows)} bougies non-vides, "
                      f"{rate:.1f} h/s, ETA {eta_min:.1f} min", flush=True)
    return pd.DataFrame(rows)


def main():
    for mt5_symbol, (ticker_lutessia, dukascopy_ticker) in SYMBOLS.items():
        print(f"\n{'='*90}\n{mt5_symbol} : backfill Dukascopy {START:%Y-%m-%d} -> {END:%Y-%m-%d}\n{'='*90}", flush=True)
        ext = build_h1_from_ticks(dukascopy_ticker, START, END)
        ext["ticker_lutessia"] = ticker_lutessia
        ext["symbole_mt5"] = mt5_symbol
        ext = ext[["ticker_lutessia", "symbole_mt5", "datetime", "open", "high", "low", "close", "tick_volume"]]
        ext = ext.sort_values("datetime").reset_index(drop=True)
        print(f"  {mt5_symbol} : {len(ext)} bougies Dukascopy construites "
              f"({ext['datetime'].min()} -> {ext['datetime'].max()})", flush=True)

        path = MT5_DIR / f"mt5_h1_backfill_{mt5_symbol}_{DATE_TAG}.csv"
        backup_path = MT5_DIR / f"mt5_h1_backfill_{mt5_symbol}_{DATE_TAG}.pre_dukascopy_backup.csv"
        if not backup_path.exists():
            shutil.copy(path, backup_path)
            print(f"  backup original conserve : {backup_path}", flush=True)

        existing = pd.read_csv(backup_path)
        existing["datetime"] = pd.to_datetime(existing["datetime"])
        ext["datetime"] = pd.to_datetime(ext["datetime"])
        combined = pd.concat([ext, existing], ignore_index=True)
        combined = combined.drop_duplicates(subset="datetime", keep="last").sort_values("datetime").reset_index(drop=True)
        combined.to_csv(path, index=False)
        print(f"  {mt5_symbol} : fichier etendu ecrit, {len(combined)} bougies au total "
              f"(depuis {combined['datetime'].min()})", flush=True)


if __name__ == "__main__":
    main()
