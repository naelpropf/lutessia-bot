"""Mapping Yahoo Finance pour les 14 tickers GOLD/SILVER x devise trouves dans le
pilote or/argent (chantier_or_argent_pilote_2026-08-19.py). Necessaire car
tp_sequence_analysis.ticker_to_yahoo_symbol (tp_sequence_analysis.py:52-60) ne gere
QUE le forex (regex XXX/XXX) et 3 indices -- aucun mapping pour "GOLD - USD" etc.

Verification empirique (2026-08-19, requetes directes a l'API Yahoo chart, meme
mecanisme que tp_sequence_analysis.fetch_h1_history) : SEULS GC=F (futures or) et
SI=F (futures argent) repondent -- tous les tickers XAUxxx=X/XAGxxx=X testes (8
devises chacun) retournent "Not Found". GC=F verifie coherent avec nos donnees
scrapees (close=4545,00 le 2026-08-19 vs prix_entree scrapes 4398-4600 sur la
meme periode pour GOLD - USD).

Pour les 12 croisements devise restants (GOLD/SILVER x EUR/GBP/CHF/CAD/AUD/NZD) :
reconstruction par TAUX CROISE avec les paires forex majeures deja en cache
(scrapees/utilisees ailleurs dans le projet ce soir) :
  - EUR/USD, GBP/USD, AUD/USD, NZD/USD cotees "1 base = X USD" -> prix_devise =
    prix_USD / taux (diviser)
  - USD/CHF, USD/CAD cotees "1 USD = X quote" -> prix_devise = prix_USD * taux
    (multiplier)
Verifie (2026-08-19) : GOLD-EUR reconstruit vs prix scrape reel au 2026-08-12 ~04h
-- ecart 2,1% (candles pas exactement synchronisees en cache a la 1re verification,
methode confirmee correcte sur l'ordre de grandeur et la direction).
"""
import re
from pathlib import Path

import pandas as pd

import tp_sequence_analysis as tpseq

CACHE_DIR = Path("yfinance_cache")

USD_LEG = {"GOLD": "GC=F", "SILVER": "SI=F"}

# (yahoo_fx_symbol, "divide" ou "multiply")
FX_LEG = {
    "EUR": ("EURUSD=X", "divide"),
    "GBP": ("GBPUSD=X", "divide"),
    "AUD": ("AUDUSD=X", "divide"),
    "NZD": ("NZDUSD=X", "divide"),
    "CHF": ("USDCHF=X", "multiply"),
    "CAD": ("USDCAD=X", "multiply"),
}

TICKER_RE = re.compile(r"^(GOLD|SILVER) - (USD|EUR|GBP|CHF|CAD|AUD|NZD)$")


def synth_symbol(ticker):
    m = TICKER_RE.match(ticker)
    if not m:
        return None
    metal, ccy = m.groups()
    if ccy == "USD":
        return USD_LEG[metal]
    return f"{metal}_{ccy}_SYNTH"


def _cache_path(symbol):
    return CACHE_DIR / (re.sub(r"[^A-Za-z0-9]", "_", symbol) + ".csv")


def build_synthetic_candles(ticker, start_dt, end_dt, force_rebuild=False):
    """Construit (et met en cache, meme convention que tp_sequence_analysis.
    fetch_h1_history) les bougies H1 synthetiques d'un croisement devise GOLD/SILVER,
    par calcul de taux croise a partir de la jambe USD (GC=F/SI=F) et de la paire
    forex majeure correspondante -- les DEUX deja recuperees/mises en cache via
    tpseq.fetch_h1_history (reutilisation totale, aucune nouvelle logique reseau)."""
    m = TICKER_RE.match(ticker)
    if not m:
        return None
    metal, ccy = m.groups()
    if ccy == "USD":
        return tpseq.fetch_h1_history(USD_LEG[metal], start_dt, end_dt)

    symbol = synth_symbol(ticker)
    cache_file = _cache_path(symbol)
    if cache_file.exists() and not force_rebuild:
        df = pd.read_csv(cache_file, parse_dates=["datetime"])
        if not df.empty and df["datetime"].min() <= start_dt + pd.Timedelta(days=2):
            print(f"  {symbol} : cache local suffisant ({len(df)} bougies, depuis {df['datetime'].min()})")
            return df

    usd_candles = tpseq.fetch_h1_history(USD_LEG[metal], start_dt, end_dt)
    fx_symbol, op = FX_LEG[ccy]
    fx_candles = tpseq.fetch_h1_history(fx_symbol, start_dt, end_dt)
    if usd_candles is None or usd_candles.empty or fx_candles is None or fx_candles.empty:
        print(f"  {symbol} : jambe USD ou FX indisponible, synthese impossible")
        return None

    merged = pd.merge(usd_candles, fx_candles, on="datetime", suffixes=("_usd", "_fx"), how="inner")
    if merged.empty:
        print(f"  {symbol} : aucune bougie horodatee en commun entre les 2 jambes")
        return None

    for col in ["open", "high", "low", "close"]:
        if op == "divide":
            merged[col] = merged[f"{col}_usd"] / merged[f"{col}_fx"]
        else:
            merged[col] = merged[f"{col}_usd"] * merged[f"{col}_fx"]

    out = merged[["datetime", "open", "high", "low", "close"]].sort_values("datetime").reset_index(drop=True)
    CACHE_DIR.mkdir(exist_ok=True)
    out.to_csv(cache_file, index=False)
    print(f"  {symbol} : {len(out)} bougies synthetiques ({fx_symbol} {op}) construites et mises en cache")
    return out


def or_argent_ticker_to_symbol(ticker):
    return synth_symbol(ticker)


if __name__ == "__main__":
    import datetime as dt
    end = dt.datetime.utcnow()
    start = end - dt.timedelta(days=729)
    tickers = [f"{m} - {c}" for m in ("GOLD", "SILVER") for c in ("USD", "EUR", "GBP", "CHF", "CAD", "AUD", "NZD")]
    for t in tickers:
        c = build_synthetic_candles(t, start, end)
        if c is not None and not c.empty:
            print(f"[verif] {t:15s} n={len(c):5d}  last={c['datetime'].max()}  last_close={c['close'].iloc[-1]:.4f}")
        else:
            print(f"[verif] {t:15s} ECHEC")
