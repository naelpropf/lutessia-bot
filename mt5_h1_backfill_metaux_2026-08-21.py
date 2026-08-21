"""mt5_h1_backfill_metaux_2026-08-21.py

Suite de mt5_h1_backfill_2026-08-21.py (forex+indices) -- backfill H1 des
metaux (or/argent x4 devises + palladium/platine) via MT5, compte BlueBerry
Prime Phase 1 (login 5104059, BlueberryMarketsSVG-Live), pour combler le
trou Yahoo Finance (~730j max) sur 2021-2024.

Meme correctif fuseau horaire que le backfill precedent (verifie et
documente la, pas rereverifie ici -- offset serveur fixe +3h, pas de DST) :
toutes les colonnes datetime sont en UTC REEL (server_time - 3h).

CONSTAT AVANT COLLECTE (verifie par sondage direct, cf. conversation) :
seuls XAUUSD.pi (depuis 2020-08-11), XAGUSD.pi (2020-08-10) et XPTUSD.pi
(2020-03-16) remontent avant la date demandee (2021-04-01). Les 6 autres
symboles (XAUGBP/XAUEUR/XAUAUD/XAGAUD/XAGEUR/XPDUSD) ne demarrent TOUS que
le 2023-01-20 sur ce compte -- limite reelle du broker sur ces
paires croisees/palladium, PAS un bug de collecte. Signale explicitement
dans le rapport plutot que force une conclusion optimiste.
"""
import time as time_mod
from datetime import datetime, timezone

import MetaTrader5 as mt5
import pandas as pd

SERVER_UTC_OFFSET_HOURS = 3  # verifie dans mt5_h1_backfill_2026-08-21.py, fixe (pas de DST cote serveur)

START = datetime(2021, 4, 1, tzinfo=timezone.utc)
END = datetime(2026, 8, 21, tzinfo=timezone.utc)

METAL_MAP = {
    "GOLD-USD": "XAUUSD.pi", "GOLD-GBP": "XAUGBP.pi", "GOLD-EUR": "XAUEUR.pi", "GOLD-AUD": "XAUAUD.pi",
    "SILVER-AUD": "XAGAUD.pi", "SILVER-EUR": "XAGEUR.pi", "SILVER-USD": "XAGUSD.pi",
    "Palladium": "XPDUSD.pi", "Platinum": "XPTUSD.pi",
}

OUT_DIR = "data/mt5_h1_backfill"


def fetch_symbol(symbol):
    ok = mt5.symbol_select(symbol, True)
    if not ok:
        return None, f"symbol_select a echoue ({mt5.last_error()})"
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H1, START, END)
    if rates is None or len(rates) == 0:
        return None, f"copy_rates_range vide ({mt5.last_error()})"
    df = pd.DataFrame(rates)
    df["datetime"] = pd.to_datetime(df["time"], unit="s", utc=True) - pd.Timedelta(hours=SERVER_UTC_OFFSET_HOURS)
    df = df[["datetime", "open", "high", "low", "close", "tick_volume"]].sort_values("datetime").reset_index(drop=True)
    return df, None


def detect_gaps(df, threshold_days=4):
    deltas = df["datetime"].diff().dropna()
    big = deltas[deltas > pd.Timedelta(days=threshold_days)]
    gaps = []
    for idx in big.index:
        gaps.append((df.loc[idx - 1, "datetime"], df.loc[idx, "datetime"], deltas.loc[idx]))
    return gaps


def main():
    ok = mt5.initialize()
    assert ok, f"mt5.initialize() a echoue: {mt5.last_error()}"
    acc = mt5.account_info()
    print(f"Connecte : login={acc.login} server={acc.server} company={acc.company}")

    report_rows = []
    for ticker_lutessia, symbol in METAL_MAP.items():
        t0 = time_mod.time()
        df, err = fetch_symbol(symbol)
        if err:
            print(f"[ECHEC] {ticker_lutessia} -> {symbol} : {err}")
            report_rows.append(dict(ticker_lutessia=ticker_lutessia, symbole_mt5=symbol,
                                     n_bougies=0, date_min=None, date_max=None,
                                     n_gaps_gt4j=None, couvre_2021_04_01="N/A", statut=f"ECHEC: {err}"))
            continue

        gaps = detect_gaps(df)
        out_path = f"{OUT_DIR}/mt5_h1_backfill_{symbol}_2026-08-21.csv"
        out = df.copy()
        out.insert(0, "symbole_mt5", symbol)
        out.insert(0, "ticker_lutessia", ticker_lutessia)
        out["datetime"] = out["datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")
        out.to_csv(out_path, index=False)

        date_min = df["datetime"].min()
        couvre = "OUI" if date_min <= START + pd.Timedelta(days=3) else f"NON -- demarre {date_min.date()}"
        print(f"[OK] {ticker_lutessia} -> {symbol} : n={len(df)} "
              f"[{date_min} -> {df['datetime'].max()}] gaps>4j={len(gaps)} "
              f"couvre_2021_04_01={couvre} ({time_mod.time()-t0:.1f}s)")
        for g in gaps:
            print(f"      gap : {g[0]} -> {g[1]} ({g[2]})")

        report_rows.append(dict(ticker_lutessia=ticker_lutessia, symbole_mt5=symbol,
                                 n_bougies=len(df), date_min=date_min, date_max=df["datetime"].max(),
                                 n_gaps_gt4j=len(gaps), couvre_2021_04_01=couvre, statut="OK"))

    report_df = pd.DataFrame(report_rows)
    report_df.to_csv(f"{OUT_DIR}/rapport_backfill_metaux_2026-08-21.csv", index=False)
    print("\n" + "=" * 100)
    print(report_df.to_string(index=False))
    mt5.shutdown()


if __name__ == "__main__":
    main()
