"""
Analyse croisée : pour chaque run individuel des 2000 simulations MC (régimes A et B,
winrates 37.29% et 32%), croise la trésorerie personnelle sortie (year1_cash) avec le
résultat net de fin d'année 1 (year1_net), pour répondre à : "quand je sors beaucoup de
cash de secours, est-ce que je finis quand même l'année en positif ?"

Utilise les CSV per-run déjà générés par regime_abc_comparison.py
(regime_abc_{winrate}_{regime}.csv), colonnes year1_net / year1_cash.
"""
import pandas as pd

THRESHOLDS = [3000, 5000, 10000]

DATASETS = [
    ("37.29% (réel)", "A", "regime_abc_37_29pct_A.csv"),
    ("37.29% (réel)", "B", "regime_abc_37_29pct_B.csv"),
    ("32% (bayésien P10)", "A", "regime_abc_32pct_A.csv"),
    ("32% (bayésien P10)", "B", "regime_abc_32pct_B.csv"),
]


def crosstab_positive_rate(df):
    rows = []
    n = len(df)
    rows.append({
        "palier": "tous runs", "n_runs": n,
        "pct_runs": 100.0,
        "pct_positive": (df["year1_net"] > 0).mean() * 100,
    })
    for t in THRESHOLDS:
        sub = df[df["year1_cash"] > t]
        rows.append({
            "palier": f">{t}€",
            "n_runs": len(sub),
            "pct_runs": len(sub) / n * 100,
            "pct_positive": (sub["year1_net"] > 0).mean() * 100 if len(sub) else float("nan"),
        })
    return pd.DataFrame(rows)


def negative_runs_cash_stats(df):
    neg = df[df["year1_net"] < 0]
    if len(neg) == 0:
        return None
    corr = df["year1_cash"].corr(df["year1_net"])
    worst5_by_loss = neg.nsmallest(5, "year1_net")[["year1_net", "year1_cash"]]
    worst5_by_cash = df.nlargest(5, "year1_cash")[["year1_net", "year1_cash"]]
    return {
        "n_neg": len(neg),
        "pct_neg": len(neg) / len(df) * 100,
        "cash_mean_neg": neg["year1_cash"].mean(),
        "cash_median_neg": neg["year1_cash"].median(),
        "cash_worst_neg": neg["year1_cash"].max(),
        "cash_mean_all": df["year1_cash"].mean(),
        "corr_cash_vs_net": corr,
        "worst5_by_loss": worst5_by_loss,
        "worst5_by_cash": worst5_by_cash,
    }


def main():
    print("=" * 100)
    print("1+3. TABLEAU CROISÉ : palier de cash sorti (année 1) x % de runs finissant l'année 1 en positif")
    print("=" * 100)
    for wr_label, regime, path in DATASETS:
        df = pd.read_csv(path)
        ct = crosstab_positive_rate(df)
        print(f"\n--- Winrate {wr_label} | Régime {regime} ---")
        print(ct.to_string(index=False, formatters={
            "n_runs": "{:.0f}".format, "pct_runs": "{:.2f}%".format, "pct_positive": "{:.2f}%".format,
        }))

    print("\n" + "=" * 100)
    print("2+3. RUNS NÉGATIFS EN ANNÉE 1 : distribution du cash sorti dans CES runs spécifiquement")
    print("=" * 100)
    for wr_label, regime, path in DATASETS:
        df = pd.read_csv(path)
        stats = negative_runs_cash_stats(df)
        print(f"\n--- Winrate {wr_label} | Régime {regime} ---")
        if stats is None:
            print("  Aucun run négatif en année 1.")
            continue
        print(f"  Runs négatifs : {stats['n_neg']}/{len(df)} ({stats['pct_neg']:.2f}%)")
        print(f"  Cash sorti (runs négatifs) : moyenne {stats['cash_mean_neg']:,.0f}€ | "
              f"médiane {stats['cash_median_neg']:,.0f}€ | pire cas {stats['cash_worst_neg']:,.0f}€")
        print(f"  Cash sorti (TOUS runs, comparaison) : moyenne {stats['cash_mean_all']:,.0f}€")
        print(f"  Corrélation (cash sorti, résultat net) sur l'ensemble des runs : {stats['corr_cash_vs_net']:.3f}")
        print(f"  Top 5 pires années (par perte €) -- cash sorti associé :")
        print("    " + stats["worst5_by_loss"].to_string(index=False).replace("\n", "\n    "))
        print(f"  Top 5 plus fortes sorties de cash -- résultat net associé :")
        print("    " + stats["worst5_by_cash"].to_string(index=False).replace("\n", "\n    "))

    print("\n" + "=" * 100)
    print("4. CONCLUSION : régime A -- proba de finir positif SACHANT cash sorti 10-11k€")
    print("=" * 100)
    for wr_label, path in [("37.29% (réel)", "regime_abc_37_29pct_A.csv"), ("32% (bayésien P10)", "regime_abc_32pct_A.csv")]:
        df = pd.read_csv(path)
        band = df[(df["year1_cash"] >= 10000) & (df["year1_cash"] <= 11000)]
        band_ge10k = df[df["year1_cash"] >= 10000]
        print(f"\n--- Winrate {wr_label} (régime A) ---")
        print(f"  Runs avec cash sorti dans [10000, 11000]€ : {len(band)}/{len(df)} ({len(band)/len(df)*100:.2f}%)")
        if len(band):
            print(f"    -> P(année 1 positive | cash sorti 10-11k€) = {(band['year1_net']>0).mean()*100:.1f}%")
            print(f"    -> résultat net moyen dans ce sous-groupe : {band['year1_net'].mean():+,.0f}€ "
                  f"(médiane {band['year1_net'].median():+,.0f}€)")
        print(f"  Runs avec cash sorti >= 10000€ (tout palier) : {len(band_ge10k)}/{len(df)} ({len(band_ge10k)/len(df)*100:.2f}%)")
        if len(band_ge10k):
            print(f"    -> P(année 1 positive | cash sorti >=10k€) = {(band_ge10k['year1_net']>0).mean()*100:.1f}%")


if __name__ == "__main__":
    main()
