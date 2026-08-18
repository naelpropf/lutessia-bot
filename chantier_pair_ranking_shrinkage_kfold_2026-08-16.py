"""
Chantier 2026-08-16 (Section 3) : fiabilisation du classement de paires.
Suite de S2.32 (registre_strategie_trading.md) -- le classement EV brut par
paire (14 tickers, population 631 trades) a echoue un test de stabilite
split H1/H2 (Spearman=0,446). Ici : (a) estimateur a retrecissement empirique
bayesien (shrinkage vers la moyenne globale, pondere par n_paire), (b)
validation k-fold temporelle (4 blocs chronologiques) au lieu d'un split
unique, pour verifier si le shrinkage recupere un classement stable.
"""
import numpy as np
import pandas as pd

from trailing_payoff_population import build_population_with_trailing

MIN_RR = 1.35


def load_pop():
    pop = build_population_with_trailing("fixed", 0.15, min_rr=MIN_RR, verbose=False)
    return pop.sort_values("date_creation").reset_index(drop=True)


def raw_ev(pop_slice):
    g = pop_slice.groupby("ticker")["r_trailing"]
    return pd.DataFrame({"n": g.count(), "ev": g.mean()})


def shrunk_ev(pop_slice, k):
    """EV shrinke vers la moyenne globale (ponderee par n_paire), poids = n/(n+k)."""
    raw = raw_ev(pop_slice)
    global_mean = pop_slice["r_trailing"].mean()
    w = raw["n"] / (raw["n"] + k)
    raw["ev_shrunk"] = w * raw["ev"] + (1 - w) * global_mean
    return raw


def quartile_from_ev(series):
    return pd.qcut(series.rank(method="first", ascending=False), 4, labels=[1, 2, 3, 4]).astype(int)


def main():
    pop = load_pop()
    n_total = len(pop)
    global_mean_full = pop["r_trailing"].mean()
    print(f"Population : n={n_total}, EV globale (moyenne simple, toutes paires) = {global_mean_full:+.4f}R")

    print("\n" + "=" * 70)
    print("Point 2 -- classement shrinke sur la population COMPLETE (in-sample)")
    print("=" * 70)
    raw_full = raw_ev(pop)
    raw_full["quartile_raw"] = quartile_from_ev(raw_full["ev"])
    tables = {"raw": raw_full[["n", "ev", "quartile_raw"]].rename(columns={"ev": "ev_raw"})}
    for k in (20, 30):
        sh = shrunk_ev(pop, k)
        sh[f"quartile_k{k}"] = quartile_from_ev(sh["ev_shrunk"])
        tables[f"k{k}"] = sh[["ev_shrunk", f"quartile_k{k}"]].rename(columns={"ev_shrunk": f"ev_shrunk_k{k}"})

    combined = tables["raw"].join(tables["k20"]).join(tables["k30"])
    combined = combined.sort_values("ev_raw", ascending=False)
    print(combined.to_string(float_format=lambda x: f"{x:.3f}"))

    # ============================================================
    # Point 3 -- validation k-fold temporelle (4 blocs chronologiques)
    # ============================================================
    print("\n" + "=" * 70)
    print("Point 3 -- validation k-fold temporelle (4 blocs chronologiques)")
    print("=" * 70)

    n_folds = 4
    boundaries = np.linspace(0, n_total, n_folds + 1).astype(int)
    blocks = [pop.iloc[boundaries[i]:boundaries[i + 1]] for i in range(n_folds)]
    for i, b in enumerate(blocks):
        print(f"  Bloc {i}: n={len(b)}  {b['date_creation'].min()} -> {b['date_creation'].max()}")

    methods = {"raw": None, "k20": 20, "k30": 30}
    fold_results = {m: [] for m in methods}
    coverage_results = []

    for fold in range(n_folds):
        test_block = blocks[fold]
        train_block = pd.concat([blocks[j] for j in range(n_folds) if j != fold], ignore_index=True)

        test_ev = raw_ev(test_block)["ev"]  # verite terrain out-of-sample sur ce bloc

        for m_name, k in methods.items():
            if k is None:
                train_series = raw_ev(train_block)["ev"]
            else:
                train_series = shrunk_ev(train_block, k)["ev_shrunk"]

            common = train_series.index.intersection(test_ev.index)
            if len(common) < 4:
                fold_results[m_name].append(np.nan)
                continue
            rho = train_series.loc[common].corr(test_ev.loc[common], method="spearman")
            fold_results[m_name].append(rho)

        n_common = len(raw_ev(train_block)["ev"].index.intersection(test_ev.index))
        coverage_results.append({"fold": fold, "n_test": len(test_block),
                                  "n_tickers_test": len(test_ev), "n_tickers_common": n_common})

    print("\nCouverture par fold :")
    print(pd.DataFrame(coverage_results).to_string(index=False))

    print("\nSpearman (classement train vs EV reel test), par fold et par methode :")
    fold_df = pd.DataFrame(fold_results, index=[f"fold{i}" for i in range(n_folds)])
    print(fold_df.to_string(float_format=lambda x: f"{x:.3f}"))

    means = fold_df.mean()
    print(f"\nSpearman MOYEN sur les {n_folds} folds :")
    for m_name in methods:
        print(f"  {m_name:6s} : {means[m_name]:+.3f}")

    best_method = means.idxmax()
    best_mean = means[best_method]

    print(f"\nMeilleure methode : {best_method} (Spearman moyen={best_mean:+.3f})")

    # ============================================================
    # Points 4/5 -- decision
    # ============================================================
    print("\n" + "=" * 70)
    if best_mean < 0.6:
        print(f"Point 4 -- VERDICT : Spearman moyen k-fold reste <0,6 (best={best_mean:+.3f}) MEME "
              f"avec shrinkage.")
        print("Le classement par paire n'est PAS structurellement recuperable a cet effectif "
              "(631 trades / 14 paires = ~45 trades/paire en moyenne, ~11/paire par fold de 4 -- "
              "trop peu pour un classement stable). A documenter clairement, pas de conclusion forcee.")
    else:
        print(f"Point 5 -- VERDICT : Spearman moyen k-fold >= 0,6 avec {best_method} "
              f"(best={best_mean:+.3f}). Classement recupere -- comparaison au classement brut :")
        best_k = methods[best_method]
        if best_k is None:
            final_ev = raw_ev(pop)["ev"]
        else:
            final_ev = shrunk_ev(pop, best_k)["ev_shrunk"]
        final_quartile = quartile_from_ev(final_ev)
        cmp = pd.DataFrame({"quartile_raw_S1": raw_full["quartile_raw"], f"quartile_{best_method}": final_quartile})
        cmp["changed"] = cmp["quartile_raw_S1"] != cmp[f"quartile_{best_method}"]
        print(cmp.sort_values("quartile_raw_S1").to_string())
        print(f"\nPaires ayant change de quartile : {cmp['changed'].sum()}/{len(cmp)}")

    combined.to_csv("chantier_pair_ranking_shrinkage_full_2026-08-16.csv")
    fold_df.to_csv("chantier_pair_ranking_shrinkage_kfold_2026-08-16.csv")

    return combined, fold_df, means


if __name__ == "__main__":
    main()
