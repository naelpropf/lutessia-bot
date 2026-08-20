"""Etend correlation_matrix.csv (33x33, FX+indices+GOLD/SILVER) a
PALLADIUM/PLATINUM (2026-08-20) -- decouvert manquant en tentant de lancer
le moteur cascade officiel sur la population pgp (n=1248,
chantier_ab_metaux_tradable_pgp_2026-08-20.py) : precompute_correlation_
pairs plante en KeyError('PALLADIUM'), la matrice n'avait jamais ete
etendue pour ces 2 tickers (l'integration VPS s'est arretee a la
construction population+prior, sans executer le moteur complet -- hors
scope de ce chantier-la).

Meme methode EXACTE que extend_correlation_matrix_gold_silver_2026-08-19.py
(Pearson sur les rendements H1, closes.pct_change().corr()) -- recalcule
la matrice COMPLETE (pas de "coller" une sous-matrice) sur les memes
fichiers cache d'origine + PA_F.csv/PL_F.csv (deja recuperes lors de la
verification Yahoo du 20/08, tp_sequence_analysis.fetch_h1_history).

Remplace correlation_matrix.csv en place -- backup conserve."""
import shutil
from pathlib import Path

import pandas as pd

CACHE_DIR = Path("yfinance_cache")
OUTPUT_PATH = "correlation_matrix.csv"
BACKUP_PATH = "correlation_matrix_pre_pgp_backup_2026-08-20.csv"
CORR_THRESHOLD = 0.80

PGP_LABEL_TO_FILE = {
    "PALLADIUM": "PA_F.csv",
    "PLATINUM": "PL_F.csv",
}


def main():
    existing = pd.read_csv(OUTPUT_PATH, index_col=0)
    shutil.copy(OUTPUT_PATH, BACKUP_PATH)
    print(f"Backup de correlation_matrix.csv (pre pgp, {existing.shape}) -> {BACKUP_PATH}")

    existing_label_to_file = {
        "AUD/JPY": "AUDJPY_X.csv", "AUD/USD": "AUDUSD_X.csv", "CHF/JPY": "CHFJPY_X.csv",
        "EUR/CHF": "EURCHF_X.csv", "EUR/GBP": "EURGBP_X.csv", "EUR/JPY": "EURJPY_X.csv",
        "EUR/USD": "EURUSD_X.csv", "GBP/CHF": "GBPCHF_X.csv", "GBP/JPY": "GBPJPY_X.csv",
        "GBP/USD": "GBPUSD_X.csv", "NZD/USD": "NZDUSD_X.csv", "USD/CAD": "USDCAD_X.csv",
        "USD/CHF": "USDCHF_X.csv", "USD/JPY": "USDJPY_X.csv",
        "DAX40 FULL0926": "_GDAXI.csv", "DAX40 PERF INDEX": "_GDAXI.csv",
        "NASDAQ100 - MINI NASDAQ100 FULL0926": "_NDX.csv", "NASDAQ100 INDEX": "_NDX.csv",
        "S&P500 - MINI S&P500 FULL0926": "_GSPC.csv",
        "GOLD - USD": "GC_F.csv", "SILVER - USD": "SI_F.csv",
        "GOLD - EUR": "GOLD_EUR_SYNTH.csv", "GOLD - GBP": "GOLD_GBP_SYNTH.csv",
        "GOLD - CHF": "GOLD_CHF_SYNTH.csv", "GOLD - CAD": "GOLD_CAD_SYNTH.csv",
        "GOLD - AUD": "GOLD_AUD_SYNTH.csv", "GOLD - NZD": "GOLD_NZD_SYNTH.csv",
        "SILVER - EUR": "SILVER_EUR_SYNTH.csv", "SILVER - GBP": "SILVER_GBP_SYNTH.csv",
        "SILVER - CHF": "SILVER_CHF_SYNTH.csv", "SILVER - CAD": "SILVER_CAD_SYNTH.csv",
        "SILVER - AUD": "SILVER_AUD_SYNTH.csv", "SILVER - NZD": "SILVER_NZD_SYNTH.csv",
    }

    closes = {}
    missing = []
    for label, fname in {**existing_label_to_file, **PGP_LABEL_TO_FILE}.items():
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

    print(f"\nMatrice etendue : {existing.shape[0]} labels existants + {len(PGP_LABEL_TO_FILE)} "
          f"pgp = {len(corr)} au total")
    print(f"Calculee sur {len(returns)} bougies H1 (union de toutes les series)")
    print(f"Enregistree dans {OUTPUT_PATH}")

    pgp_labels = list(PGP_LABEL_TO_FILE.keys())
    print(f"\n[Correlations PALLADIUM/PLATINUM <-> reste (tout B), seuil {CORR_THRESHOLD}] :")
    other_labels = [l for l in corr.columns if l not in pgp_labels]
    pairs_cross = []
    for a in pgp_labels:
        for b in other_labels:
            pairs_cross.append((a, b, corr.loc[a, b]))
    pairs_cross.sort(key=lambda x: abs(x[2]), reverse=True)
    n_over_cross = sum(1 for _, _, r in pairs_cross if abs(r) > CORR_THRESHOLD)
    for a, b, r in pairs_cross[:15]:
        flag = "  <-- BLOCAGE" if abs(r) > CORR_THRESHOLD else ""
        print(f"  {a:<15} / {b:<40} : {r:+.3f}{flag}")
    print(f"  Total paires PALLADIUM/PLATINUM<->reste > seuil : {n_over_cross}/{len(pairs_cross)}")

    print(f"\n[Correlation PALLADIUM <-> PLATINUM] : {corr.loc['PALLADIUM', 'PLATINUM']:+.3f}")


if __name__ == "__main__":
    main()
