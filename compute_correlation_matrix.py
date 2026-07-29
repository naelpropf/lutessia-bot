"""
Calcule la matrice de corrélation entre les 14 paires forex à partir des rendements
H1 (bougies déjà en cache dans yfinance_cache/, cf. tp_sequence_analysis.py) et
l'enregistre dans correlation_matrix.csv, utilisée par account_router.py pour éviter
d'ouvrir des positions corrélées sur des comptes distincts.
"""
import re
from pathlib import Path

import pandas as pd

CACHE_DIR = Path("yfinance_cache")
OUTPUT_PATH = "correlation_matrix.csv"

FOREX_CACHE_FILES = [
    f for f in CACHE_DIR.glob("*.csv")
    if re.match(r"^[A-Z]{6}_X\.csv$", f.name)
]


def yahoo_cache_symbol_to_ticker(filename):
    base = filename.stem.replace("_X", "")
    return f"{base[:3]}/{base[3:]}"


def main():
    if not FOREX_CACHE_FILES:
        print("Aucun fichier de cache forex trouvé dans yfinance_cache/.")
        return

    closes = {}
    for f in FOREX_CACHE_FILES:
        ticker = yahoo_cache_symbol_to_ticker(f)
        df = pd.read_csv(f, parse_dates=["datetime"])
        closes[ticker] = df.set_index("datetime")["close"]

    price_df = pd.DataFrame(closes).sort_index()
    returns = price_df.pct_change().dropna(how="all")

    corr = returns.corr()
    corr.to_csv(OUTPUT_PATH)

    print(f"Matrice de corrélation calculée sur {len(returns)} bougies H1, {len(corr)} paires.")
    print(f"Enregistrée dans {OUTPUT_PATH}\n")

    pairs = []
    tickers = list(corr.columns)
    for i, a in enumerate(tickers):
        for b in tickers[i + 1:]:
            pairs.append((a, b, corr.loc[a, b]))
    pairs.sort(key=lambda x: abs(x[2]), reverse=True)

    print("Top 15 paires les plus corrélées (en valeur absolue) :")
    for a, b, r in pairs[:15]:
        print(f"  {a:<8} / {b:<8} : {r:+.3f}")


if __name__ == "__main__":
    main()
