"""Etend correlation_matrix.csv (19x19, FX+indices, extend_correlation_matrix_
indices_2026-08-18.py) aux 14 labels GOLD/SILVER x devise du pilote or/argent
(chantier fusion dans Strategie B, 2026-08-19). Meme methode EXACTE que
l'extension indices du 08-18 : correlation de Pearson sur les RENDEMENTS H1
(pct_change), pas les prix bruts -- closes.pct_change().corr().

Sources de prix : yfinance_cache/GC_F.csv, SI_F.csv (jambes USD directes) et
les 12 fichiers *_SYNTH.csv construits par gold_silver_yahoo_mapping_2026-08-
19.py (taux croises).

Remplace correlation_matrix.csv en place -- backup conserve
(correlation_matrix_pre_gold_silver_backup_2026-08-19.csv).
"""
import shutil
from pathlib import Path

import pandas as pd

CACHE_DIR = Path("yfinance_cache")
OUTPUT_PATH = "correlation_matrix.csv"
BACKUP_PATH = "correlation_matrix_pre_gold_silver_backup_2026-08-19.csv"
CORR_THRESHOLD = 0.80

GOLD_SILVER_LABEL_TO_FILE = {
    "GOLD - USD": "GC_F.csv",
    "SILVER - USD": "SI_F.csv",
    "GOLD - EUR": "GOLD_EUR_SYNTH.csv",
    "GOLD - GBP": "GOLD_GBP_SYNTH.csv",
    "GOLD - CHF": "GOLD_CHF_SYNTH.csv",
    "GOLD - CAD": "GOLD_CAD_SYNTH.csv",
    "GOLD - AUD": "GOLD_AUD_SYNTH.csv",
    "GOLD - NZD": "GOLD_NZD_SYNTH.csv",
    "SILVER - EUR": "SILVER_EUR_SYNTH.csv",
    "SILVER - GBP": "SILVER_GBP_SYNTH.csv",
    "SILVER - CHF": "SILVER_CHF_SYNTH.csv",
    "SILVER - CAD": "SILVER_CAD_SYNTH.csv",
    "SILVER - AUD": "SILVER_AUD_SYNTH.csv",
    "SILVER - NZD": "SILVER_NZD_SYNTH.csv",
}


def main():
    existing = pd.read_csv(OUTPUT_PATH, index_col=0)
    shutil.copy(OUTPUT_PATH, BACKUP_PATH)
    print(f"Backup de correlation_matrix.csv (pre gold/silver, {existing.shape}) -> {BACKUP_PATH}")

    # Reconstruit les series de rendements des colonnes EXISTANTES depuis leurs
    # fichiers cache d'origine (meme fichiers que extend_correlation_matrix_
    # indices_2026-08-18.py utilisait) pour recalculer la matrice complete sur
    # une base de rendements homogene -- pas de "coller" une sous-matrice deja
    # calculee a une nouvelle (les fenetres temporelles de cache diffèrent).
    existing_label_to_file = {
        "AUD/JPY": "AUDJPY_X.csv", "AUD/USD": "AUDUSD_X.csv", "CHF/JPY": "CHFJPY_X.csv",
        "EUR/CHF": "EURCHF_X.csv", "EUR/GBP": "EURGBP_X.csv", "EUR/JPY": "EURJPY_X.csv",
        "EUR/USD": "EURUSD_X.csv", "GBP/CHF": "GBPCHF_X.csv", "GBP/JPY": "GBPJPY_X.csv",
        "GBP/USD": "GBPUSD_X.csv", "NZD/USD": "NZDUSD_X.csv", "USD/CAD": "USDCAD_X.csv",
        "USD/CHF": "USDCHF_X.csv", "USD/JPY": "USDJPY_X.csv",
        "DAX40 FULL0926": "_GDAXI.csv", "DAX40 PERF INDEX": "_GDAXI.csv",
        "NASDAQ100 - MINI NASDAQ100 FULL0926": "_NDX.csv", "NASDAQ100 INDEX": "_NDX.csv",
        "S&P500 - MINI S&P500 FULL0926": "_GSPC.csv",
    }

    closes = {}
    missing = []
    for label, fname in {**existing_label_to_file, **GOLD_SILVER_LABEL_TO_FILE}.items():
        f = CACHE_DIR / fname
        if not f.exists():
            missing.append((label, fname))
            continue
        df = pd.read_csv(f, parse_dates=["datetime"])
        closes[label] = df.set_index("datetime")["close"]

    if missing:
        print(f"[MANQUANT] {missing}")

    price_df = pd.DataFrame(closes).sort_index()
    returns = price_df.pct_change().dropna(how="all")
    corr = returns.corr()
    corr.to_csv(OUTPUT_PATH)

    print(f"\nMatrice etendue : {existing.shape[0]} labels existants + {len(GOLD_SILVER_LABEL_TO_FILE)} "
          f"gold/silver = {len(corr)} au total")
    print(f"Calculee sur {len(returns)} bougies H1 (union de toutes les series)")
    print(f"Enregistree dans {OUTPUT_PATH}")

    print(f"\n[Verification labels meme sous-jacent, doit etre 1,000] :")
    print(f"  DAX40 FULL0926 / DAX40 PERF INDEX = {corr.loc['DAX40 FULL0926', 'DAX40 PERF INDEX']:.4f}")

    gs_labels = list(GOLD_SILVER_LABEL_TO_FILE.keys())

    print(f"\n[Correlations GOLD/SILVER <-> GOLD/SILVER, seuil {CORR_THRESHOLD}] :")
    pairs_gs = []
    for i, a in enumerate(gs_labels):
        for b in gs_labels[i + 1:]:
            pairs_gs.append((a, b, corr.loc[a, b]))
    pairs_gs.sort(key=lambda x: abs(x[2]), reverse=True)
    n_over_gs = sum(1 for _, _, r in pairs_gs if abs(r) > CORR_THRESHOLD)
    for a, b, r in pairs_gs[:15]:
        flag = "  <-- BLOCAGE" if abs(r) > CORR_THRESHOLD else ""
        print(f"  {a:<15} / {b:<15} : {r:+.3f}{flag}")
    print(f"  Total paires GOLD/SILVER<->GOLD/SILVER > seuil : {n_over_gs}/{len(pairs_gs)}")

    print(f"\n[Correlations GOLD/SILVER <-> reste de B (forex+indices existants), seuil {CORR_THRESHOLD}] :")
    other_labels = [l for l in corr.columns if l not in gs_labels]
    pairs_cross = []
    for a in gs_labels:
        for b in other_labels:
            pairs_cross.append((a, b, corr.loc[a, b]))
    pairs_cross.sort(key=lambda x: abs(x[2]), reverse=True)
    n_over_cross = sum(1 for _, _, r in pairs_cross if abs(r) > CORR_THRESHOLD)
    for a, b, r in pairs_cross[:15]:
        flag = "  <-- BLOCAGE" if abs(r) > CORR_THRESHOLD else ""
        print(f"  {a:<15} / {b:<40} : {r:+.3f}{flag}")
    print(f"  Total paires GOLD/SILVER<->reste > seuil : {n_over_cross}/{len(pairs_cross)}")


if __name__ == "__main__":
    main()
