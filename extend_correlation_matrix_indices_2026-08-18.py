"""
TACHE 2 (2026-08-18) : etend correlation_matrix.csv (14 paires FX
uniquement jusqu'ici, compute_correlation_matrix.py) aux 3 indices
mappables (DAX40/S&P500/NASDAQ100) -- indices<->indices ET
indices<->forex. Necessaire pour que any-RR (coeur de S1.8,
`precompute_correlation_pairs`, monte_carlo_simulation.py:74-86) puisse
router correctement les trades indices dans une vraie simulation flotte
-- ce mecanisme fait un lookup `corr_matrix.loc[a, b]` pour CHAQUE paire
de tickers presents dans la population, et leve une KeyError si un
ticker est absent de la matrice.

Un meme indice sous-jacent (ex. DAX40) apparait sous PLUSIEURS labels
Lutessia distincts dans la population brute ("DAX40 FULL0926", "DAX40
PERF INDEX") -- le moteur indexe par le ticker BRUT exact (pop["ticker"]),
donc chaque label doit avoir sa propre ligne/colonne dans la matrice.
Assigne a chaque label la MEME serie de prix que son instrument
sous-jacent (bougies H1 deja en cache, tp_sequence_analysis.
ticker_to_yahoo_symbol) -- la correlation entre 2 labels du meme
sous-jacent sort donc naturellement a 1,000 (pas approxime, calcule).

DJ30 reste hors-perimetre (INDEX_KEYWORD_MAP ne le couvre pas, rr_tp1
deja NaN dans la source -- non ajoute ici, coherent avec la portee deja
etablie dans les taches precedentes).

Remplace correlation_matrix.csv en place -- backup de l'ancien fichier
conserve (correlation_matrix_forex_only_backup_2026-08-18.csv).
"""
import re
import shutil
from pathlib import Path

import pandas as pd

CACHE_DIR = Path("yfinance_cache")
OUTPUT_PATH = "correlation_matrix.csv"
BACKUP_PATH = "correlation_matrix_forex_only_backup_2026-08-18.csv"

INDEX_LABEL_TO_SYMBOL = {
    "DAX40 FULL0926": "_GDAXI",
    "DAX40 PERF INDEX": "_GDAXI",
    "NASDAQ100 - MINI NASDAQ100 FULL0926": "_NDX",
    "NASDAQ100 INDEX": "_NDX",
    "S&P500 - MINI S&P500 FULL0926": "_GSPC",
}

FOREX_CACHE_FILES = [
    f for f in CACHE_DIR.glob("*.csv")
    if re.match(r"^[A-Z]{6}_X\.csv$", f.name)
]


def yahoo_cache_symbol_to_ticker(filename):
    base = filename.stem.replace("_X", "")
    return f"{base[:3]}/{base[3:]}"


def main():
    shutil.copy(OUTPUT_PATH, BACKUP_PATH)
    print(f"Backup de l'ancien correlation_matrix.csv (forex seul) -> {BACKUP_PATH}")

    closes = {}
    for f in FOREX_CACHE_FILES:
        ticker = yahoo_cache_symbol_to_ticker(f)
        df = pd.read_csv(f, parse_dates=["datetime"])
        closes[ticker] = df.set_index("datetime")["close"]

    for label, symbol_stem in INDEX_LABEL_TO_SYMBOL.items():
        cache_file = CACHE_DIR / f"{symbol_stem}.csv"
        if not cache_file.exists():
            print(f"[MANQUANT] {cache_file} -- {label} non ajoute (a fetcher d'abord)")
            continue
        df = pd.read_csv(cache_file, parse_dates=["datetime"])
        closes[label] = df.set_index("datetime")["close"]

    price_df = pd.DataFrame(closes).sort_index()
    returns = price_df.pct_change().dropna(how="all")
    corr = returns.corr()
    corr.to_csv(OUTPUT_PATH)

    n_fx = len(FOREX_CACHE_FILES)
    n_idx = len([k for k in INDEX_LABEL_TO_SYMBOL if k in closes])
    print(f"\nMatrice etendue : {n_fx} paires FX + {n_idx} labels indices = {len(corr)} au total")
    print(f"Calculee sur {len(returns)} bougies H1 (union FX+indices)")
    print(f"Enregistree dans {OUTPUT_PATH}")

    print("\n[Verification] correlation entre labels du meme sous-jacent (doit etre 1,000) :")
    print(f"  DAX40 FULL0926 / DAX40 PERF INDEX = {corr.loc['DAX40 FULL0926', 'DAX40 PERF INDEX']:.4f}")
    print(f"  NASDAQ100 - MINI NASDAQ100 FULL0926 / NASDAQ100 INDEX = "
          f"{corr.loc['NASDAQ100 - MINI NASDAQ100 FULL0926', 'NASDAQ100 INDEX']:.4f}")

    print("\n[Correlations indices<->forex les plus fortes (|r|)] :")
    idx_labels = list(INDEX_LABEL_TO_SYMBOL.keys())
    fx_labels = [yahoo_cache_symbol_to_ticker(f) for f in FOREX_CACHE_FILES]
    pairs = []
    for i in idx_labels:
        if i not in corr.columns:
            continue
        for f in fx_labels:
            pairs.append((i, f, corr.loc[i, f]))
    pairs.sort(key=lambda x: abs(x[2]), reverse=True)
    for a, b, r in pairs[:10]:
        print(f"  {a:<40} / {b:<8} : {r:+.3f}")

    print("\n[Correlations indices<->indices (sous-jacents distincts)] :")
    print(f"  DAX40 (^GDAXI) / NASDAQ100 (^NDX) = {corr.loc['DAX40 FULL0926', 'NASDAQ100 INDEX']:+.3f}")
    print(f"  DAX40 (^GDAXI) / S&P500 (^GSPC)   = {corr.loc['DAX40 FULL0926', 'S&P500 - MINI S&P500 FULL0926']:+.3f}" if 'S&P500 - MINI S&P500 FULL0926' in corr.columns else "  S&P500 manquant")
    print(f"  NASDAQ100 (^NDX) / S&P500 (^GSPC) = {corr.loc['NASDAQ100 INDEX', 'S&P500 - MINI S&P500 FULL0926']:+.3f}" if 'S&P500 - MINI S&P500 FULL0926' in corr.columns else "  S&P500 manquant")


if __name__ == "__main__":
    main()
