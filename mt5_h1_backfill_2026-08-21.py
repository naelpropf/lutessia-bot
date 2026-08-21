"""mt5_h1_backfill_2026-08-21.py

Backfill H1 via MT5 (compte BlueBerry Prime Phase 1, login 5104059, serveur
BlueberryMarketsSVG-Live) pour combler le trou Yahoo Finance (~730j max,
cf. session_handoff_2026-08-21_mt5_h1_backfill_request.md) sur la periode
2022-01-01 -> aujourd'hui, demande venant du projet de simulation (autre
poste).

CORRECTIF FUSEAU HORAIRE (verifie avant toute collecte, cf. memoire
feedback_index_alignment_bug_pattern citee dans le handoff) : le champ
`time` retourne par mt5.copy_rates_range() est un epoch Unix representant
l'heure SERVEUR du broker, PAS l'UTC reel. Verifie ici par 2 methodes
independantes :
  1. Tick live EURUSD.pi vs horloge systeme UTC au moment du run : offset
     mesure = +3h00 (2026-08-21T06:18:52 serveur vs 03:18:53 UTC systeme).
  2. Stabilite hors-DST : heure de cloture hebdomadaire (dernier bar
     vendredi) verifiee IDENTIQUE en jan/juil/dec 2023 (23:00 serveur dans
     les 3 cas) -- confirme un offset FIXE (pas d'observance DST cote
     serveur), donc une correction constante -3h est valide sur tout
     l'historique, pas seulement au moment du run.
Toutes les colonnes `datetime` de ce backfill sont donc en UTC REEL
(server_time - 3h), PAS l'heure serveur brute -- a ne pas confondre avec
une eventuelle future collecte sur un autre broker/compte (offset non
garanti identique, a reverifier).

Symboles indices : ce compte n'expose PAS les futures dates demandes
(DAX40 FULL0926 / S&P500 MINI FULL0926 / NASDAQ100 MINI FULL0926) --
seuls des CFD continus existent (GER30.p/GER40.p, SP500.p, NAS100.p).
Signale explicitement dans le rapport, PAS suppose equivalent (rollover/
spread potentiellement different d'un future date). DAX : GER30.p couvre
2020-01-02->2024-11-22 puis s'arrete (plus de donnees, probablement
remplace par GER40.p qui demarre 2025-01-02 sur ce compte) -- GAP REEL de
~40j entre les deux ET changement d'indice sous-jacent (30 vs 40 valeurs),
pas une simple continuation techniquement identique.
"""
import time as time_mod
from datetime import datetime, timezone

import MetaTrader5 as mt5
import pandas as pd

SERVER_UTC_OFFSET_HOURS = 3  # verifie ci-dessus, fixe (pas de DST cote serveur)

START = datetime(2022, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 8, 21, tzinfo=timezone.utc)

# ticker_lutessia -> symbole MT5 (compte BlueBerry, suffixe .pi pour le forex,
# cf. app_mt5.py:MT5Account.to_mt5_symbol -- meme convention que le bot live)
FOREX_MAP = {
    "AUD/JPY": "AUDJPY.pi", "AUD/USD": "AUDUSD.pi", "CHF/JPY": "CHFJPY.pi",
    "EUR/CHF": "EURCHF.pi", "EUR/GBP": "EURGBP.pi", "EUR/JPY": "EURJPY.pi",
    "EUR/USD": "EURUSD.pi", "GBP/CHF": "GBPCHF.pi", "GBP/JPY": "GBPJPY.pi",
    "GBP/USD": "GBPUSD.pi", "NZD/USD": "NZDUSD.pi", "USD/CAD": "USDCAD.pi",
    "USD/CHF": "USDCHF.pi", "USD/JPY": "USDJPY.pi",
}

# indices : CFD continu (PAS le future date demande), 2 symboles pour le DAX
# (rollover 30->40 constate sur ce compte, cf. docstring)
INDEX_MAP = {
    "GER30.p": ("DAX40 FULL0926|DAX40 PERF INDEX", "CFD continu GER30 -- PAS le future date. "
                "Arrete le 2024-11-22 sur ce compte (probable rollover vers GER40.p)."),
    "GER40.p": ("DAX40 FULL0926|DAX40 PERF INDEX", "CFD continu GER40 -- PAS le future date. "
                "Demarre le 2025-01-02 sur ce compte (probable suite de GER30.p, gap ~40j)."),
    "SP500.p": ("S&P500 - MINI S&P500 FULL0926", "CFD continu SP500 -- PAS le future date."),
    "NAS100.p": ("NASDAQ100 - MINI NASDAQ100 FULL0926|NASDAQ100 INDEX", "CFD continu NAS100 -- PAS le future date."),
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
    all_tickers = list(FOREX_MAP.items()) + [(v[0], k) for k, v in INDEX_MAP.items()]
    # all_tickers ici : (ticker_lutessia_ou_labels, symbole_mt5)

    for ticker_lutessia, symbol in all_tickers:
        t0 = time_mod.time()
        df, err = fetch_symbol(symbol)
        if err:
            print(f"[ECHEC] {ticker_lutessia} -> {symbol} : {err}")
            report_rows.append(dict(ticker_lutessia=ticker_lutessia, symbole_mt5=symbol,
                                     n_bougies=0, date_min=None, date_max=None,
                                     n_gaps_gt4j=None, statut=f"ECHEC: {err}"))
            continue

        gaps = detect_gaps(df)
        out_path = f"{OUT_DIR}/mt5_h1_backfill_{symbol}_2026-08-21.csv"
        out = df.copy()
        out.insert(0, "symbole_mt5", symbol)
        out.insert(0, "ticker_lutessia", ticker_lutessia)
        out["datetime"] = out["datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")
        out.to_csv(out_path, index=False)

        note = INDEX_MAP.get(symbol, ("", ""))[1] if symbol in INDEX_MAP else ""
        print(f"[OK] {ticker_lutessia} -> {symbol} : n={len(df)} "
              f"[{df['datetime'].min()} -> {df['datetime'].max()}] gaps>4j={len(gaps)} "
              f"({time_mod.time()-t0:.1f}s) {note}")
        for g in gaps:
            print(f"      gap : {g[0]} -> {g[1]} ({g[2]})")

        report_rows.append(dict(ticker_lutessia=ticker_lutessia, symbole_mt5=symbol,
                                 n_bougies=len(df), date_min=df["datetime"].min(), date_max=df["datetime"].max(),
                                 n_gaps_gt4j=len(gaps), statut="OK" + (f" -- {note}" if note else "")))

    report_df = pd.DataFrame(report_rows)
    report_df.to_csv(f"{OUT_DIR}/rapport_backfill_2026-08-21.csv", index=False)
    print("\n" + "=" * 100)
    print(report_df.to_string(index=False))
    mt5.shutdown()


if __name__ == "__main__":
    main()
