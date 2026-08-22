"""chantier_piste3_volgate_2026-08-23.py

Piste 3 (session du 23/08) : gate de sizing conditionne a la volatilite
realisee, teste sur les 3 chocs ou Strategie B a montre une vraie
degradation cette session (SVB, israel_hamas, carry-unwind JPY/Sahm --
[[project_omicron_detail_et_carry_unwind_2026-08-23]]).

ETAPE 1 -- proxy de volatilite par ticker :
- ATR H1 (moyenne mobile du TrueRange) fenetres 20/40 barres
- ecart-type des rendements log H1, fenetres 20/40 barres
Normalise par PERCENTILE PROPRE A CHAQUE TICKER (pas de seuil absolu
partage) -- rang de chaque observation dans la distribution COMPLETE de ce
ticker (pas walk-forward -- "P90 historique" au sens plat du terme, usage
diagnostic ici, pas encore un gate temps reel).

Sources H1 : forex/indices via tp_sequence_analysis.fetch_h1_history
(meme mecanisme que tout le reste du projet) ; metaux via lecture directe
des CSV MT5 backfill (memes symboles que chantier_bloc2_metaux_synthese_
mt5_2026-08-21.py::DIRECT_SYMBOL/CROSS_SYMBOL, PAS resynthetise).
"""
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
import tp_sequence_analysis as tpsa

MT5_DIR = "data/mt5_h1_backfill"
MT5_DATE = "2026-08-21"

METAL_SYMBOL = {
    "GOLD - USD": "XAUUSD.pi", "GOLD - EUR": "XAUEUR.pi", "GOLD - GBP": "XAUGBP.pi", "GOLD - AUD": "XAUAUD.pi",
    "SILVER - USD": "XAGUSD.pi", "SILVER - EUR": "XAGEUR.pi", "SILVER - AUD": "XAGAUD.pi",
    "PALLADIUM": "XPDUSD.pi", "PLATINUM": "XPTUSD.pi",
}
INDEX_MT5_SYMBOL = {
    "DAX40 FULL0926": "GER40.p", "DAX40 PERF INDEX": "GER40.p",
    "NASDAQ100 - MINI NASDAQ100 FULL0926": "NAS100.p", "NASDAQ100 INDEX": "NAS100.p",
    "S&P500 - MINI S&P500 FULL0926": "SP500.p",
}


def load_h1_for_ticker(ticker, start_dt, end_dt):
    if ticker in METAL_SYMBOL:
        path = f"{MT5_DIR}/mt5_h1_backfill_{METAL_SYMBOL[ticker]}_{MT5_DATE}.csv"
        df = pd.read_csv(path, usecols=["datetime", "open", "high", "low", "close"])
        df["datetime"] = pd.to_datetime(df["datetime"])
        return df[(df["datetime"] >= start_dt) & (df["datetime"] <= end_dt)].reset_index(drop=True)
    if ticker in INDEX_MT5_SYMBOL:
        path = f"{MT5_DIR}/mt5_h1_backfill_{INDEX_MT5_SYMBOL[ticker]}_{MT5_DATE}.csv"
        df = pd.read_csv(path, usecols=["datetime", "open", "high", "low", "close"])
        df["datetime"] = pd.to_datetime(df["datetime"])
        return df[(df["datetime"] >= start_dt) & (df["datetime"] <= end_dt)].reset_index(drop=True)
    symbol = tpsa.ticker_to_yahoo_symbol(ticker)
    if symbol is None:
        return None
    return tpsa.fetch_h1_history(symbol, start_dt, end_dt)


def compute_vol_proxies(df, windows=(20, 40)):
    """ATR et std(log-return) H1, fenetres glissantes. Retourne le df avec
    colonnes ajoutees atr_W, retstd_W (W in windows)."""
    df = df.sort_values("datetime").reset_index(drop=True)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"] - df["close"].shift()).abs(),
    ], axis=1).max(axis=1)
    logret = np.log(df["close"] / df["close"].shift())
    for w in windows:
        df[f"atr_{w}"] = tr.rolling(w).mean()
        df[f"retstd_{w}"] = logret.rolling(w).std()
    return df


def percentile_rank_series(s):
    """Rang percentile de chaque valeur dans la distribution COMPLETE de la
    serie (pas walk-forward) -- usage diagnostic."""
    return s.rank(pct=True) * 100


def stability_check(df, windows=(20, 40)):
    """Stabilite du signal : previent des faux positifs de haute frequence --
    compte le nombre de franchissements P90->sous-P90->P90 (flip-flop) sur
    fenetre 20 vs 40, la fenetre la PLUS STABLE (moins de flips) est retenue."""
    out = {}
    for w in windows:
        for metric in ("atr", "retstd"):
            col = f"{metric}_{w}"
            if col not in df or df[col].isna().all():
                continue
            pct = percentile_rank_series(df[col].dropna())
            above = (pct >= 90).astype(int)
            flips = (above.diff().abs() == 1).sum()
            out[f"{metric}_{w}"] = dict(n_obs=len(pct), n_above_p90=int(above.sum()), flips=int(flips),
                                          flip_rate=flips / max(1, len(pct)))
    return out


if __name__ == "__main__":
    import json
    pop_b = pd.read_csv("chantier_gold_silver_pop_B_tradable_pgp_2026-08-20.csv")
    tickers = sorted(pop_b["ticker"].unique())
    print(f"[verif] {len(tickers)} tickers B_tradable_pgp : {tickers}", flush=True)

    # <<< CORRECTIF : 2021-01-01 est ANTERIEUR a la couverture reelle du
    # backfill MT5 pour la plupart des paires forex/index (qui commence
    # 2022-01-02, sauf EURUSD/GBPUSD/AUDUSD/USDCAD 2021-03-25) -- avec un
    # start_dt trop precoce, tp_sequence_analysis.fetch_h1_history() bascule
    # a tort sur le cache Yahoo (fenetre glissante 729j depuis "now", ne
    # couvre PAS 2023) au lieu d'utiliser le backfill MT5 disponible.
    start_dt = pd.Timestamp("2022-01-01")
    end_dt = pd.Timestamp("2025-12-31")

    stability_summary = {}
    for ticker in tickers:
        df = load_h1_for_ticker(ticker, start_dt, end_dt)
        if df is None or df.empty:
            print(f"  {ticker} : AUCUNE donnee H1 disponible", flush=True)
            continue
        df = compute_vol_proxies(df)
        stab = stability_check(df)
        stability_summary[ticker] = stab
        print(f"  {ticker} : n={len(df)} candles, stabilite={stab}", flush=True)
        df.to_parquet(f"piste3_h1vol_{re.sub(r'[^A-Za-z0-9]', '_', ticker)}_2026-08-23.parquet") if False else None
        df.to_csv(f"piste3_h1vol_{re.sub(r'[^A-Za-z0-9]', '_', ticker)}_2026-08-23.csv", index=False)

    with open("piste3_stability_summary_2026-08-23.json", "w") as f:
        json.dump(stability_summary, f, indent=2, default=str)
