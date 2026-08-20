"""Etape 0 (rigueur statistique prealable) du chantier fusion GOLD/SILVER
dans Strategie B, demande explicitement avant tout test de fusion/Monte
Carlo :
1. Correction multi-comparaisons (Benjamini-Hochberg principal + Bonferroni
   en verification stricte) sur les 14 tests par ticker (population spot
   or/argent, chantier_or_argent_evaluation_2026-08-19.py).
2. Shrinkage bayesien k=50, formule EXACTE de chantier_pair_ranking_
   shrinkage_kfold_2026-08-16.py:28-34 (ev_shrunk = w*ev + (1-w)*global_mean,
   w = n/(n+k)) -- k=50 deja utilise/adopte ailleurs dans le projet
   (registre_strategie_trading.md:2605).
3. Sortie des 3 scenarios de selection demandes (A/B/C).
"""
import numpy as np
import pandas as pd

CSV_PATH = "or_argent_population_trailing_2026-08-19.csv"
K_SHRINK = 50
SEED = 9999
N_BOOT = 5000

NEAR_ZERO_TICKERS = ["SILVER - CHF", "SILVER - USD", "GOLD - NZD"]  # candidats scenario C, ci-dessous verifie pas juste suppose


def boot_pvalue(arr, seed=SEED, n_iter=N_BOOT):
    """p-value bilaterale : 2*min(P(moyenne_boot<=0), P(moyenne_boot>=0)),
    meme bootstrap (5000 iter, seed=9999) que boot_ci deja utilise dans le
    projet (chantier_rrtp2_stability_verification_2026-08-16.py:18-21)."""
    rng = np.random.default_rng(seed)
    boot = np.array([rng.choice(arr, size=len(arr), replace=True).mean() for _ in range(n_iter)])
    p_le0 = (boot <= 0).mean()
    p_ge0 = (boot >= 0).mean()
    return 2 * min(p_le0, p_ge0), np.percentile(boot, [2.5, 97.5])


def bh_correction(pvals, alpha=0.05):
    """Benjamini-Hochberg : trie croissant, seuil i/m*alpha, plus grand i
    tel que p(i)<=i/m*alpha, tous les tests <= ce rang sont significatifs."""
    m = len(pvals)
    order = np.argsort(pvals)
    sorted_p = pvals[order]
    thresh = (np.arange(1, m + 1) / m) * alpha
    passed = sorted_p <= thresh
    if not passed.any():
        cutoff_rank = 0
    else:
        cutoff_rank = np.max(np.where(passed)[0]) + 1
    significant = np.zeros(m, dtype=bool)
    significant[order[:cutoff_rank]] = True
    return significant


def main():
    df = pd.read_csv(CSV_PATH)
    df["outcome_r"] = df["r_trailing"]  # payoff realiste (rr_tp2 si continuation confirmee) + trailing 0.10x
    global_mean = df["outcome_r"].mean()
    n_total = len(df)
    print(f"Population spot or/argent : n={n_total}, EV globale (pool) = {global_mean:+.4f}R\n")

    rows = []
    for ticker, g in df.groupby("ticker"):
        n = len(g)
        if n < 30:
            continue
        arr = g["outcome_r"].to_numpy()
        ev = arr.mean()
        pval, (ci_lo, ci_hi) = boot_pvalue(arr)
        w = n / (n + K_SHRINK)
        ev_shrunk = w * ev + (1 - w) * global_mean
        rows.append(dict(ticker=ticker, n=n, ev=ev, ev_shrunk=ev_shrunk, w=w,
                          ci_lo=ci_lo, ci_hi=ci_hi, pval=pval))

    tbl = pd.DataFrame(rows).sort_values("ev", ascending=False).reset_index(drop=True)
    pvals = tbl["pval"].to_numpy()
    m = len(pvals)

    tbl["bonferroni_sig"] = pvals < (0.05 / m)
    tbl["bh_sig"] = bh_correction(pvals, alpha=0.05)
    tbl["raw_sig_5pct"] = pvals < 0.05

    print("=" * 100)
    print(f"Correction multi-comparaisons ({m} tests simultanes, alpha=0,05)")
    print("=" * 100)
    print(f"{'Ticker':15s} {'n':>4s} {'EV brut':>9s} {'EV shrink(k=50)':>16s} {'w=n/(n+k)':>10s} "
          f"{'p-value':>9s} {'brut<5%':>8s} {'BH':>5s} {'Bonf.':>6s}")
    for _, r in tbl.iterrows():
        print(f"{r['ticker']:15s} {r['n']:4.0f} {r['ev']:+9.4f} {r['ev_shrunk']:+16.4f} {r['w']:10.3f} "
              f"{r['pval']:9.4f} {'oui' if r['raw_sig_5pct'] else 'non':>8s} "
              f"{'oui' if r['bh_sig'] else 'non':>5s} {'oui' if r['bonferroni_sig'] else 'non':>6s}")

    n_raw = tbl["raw_sig_5pct"].sum()
    n_bh = tbl["bh_sig"].sum()
    n_bonf = tbl["bonferroni_sig"].sum()
    print(f"\nSignificatifs (brut, non corrige) : {n_raw}/{m}")
    print(f"Significatifs apres correction BH : {n_bh}/{m}")
    print(f"Significatifs apres correction Bonferroni : {n_bonf}/{m}")

    print("\n" + "=" * 100)
    print("Definition des 3 scenarios de selection")
    print("=" * 100)

    scenario_A = sorted(tbl["ticker"].tolist())
    print(f"A) Pool complet (aucun filtre par ticker) : {len(scenario_A)} tickers -> {scenario_A}")

    scenario_B = sorted(tbl.loc[tbl["bh_sig"], "ticker"].tolist())
    print(f"B) Survivants correction BH (+shrinkage informatif, pas un filtre supplementaire) : "
          f"{len(scenario_B)} tickers -> {scenario_B}")
    excluded_B = sorted(set(scenario_A) - set(scenario_B))
    print(f"   Exclus par B : {excluded_B}")

    near_zero_actual = sorted(tbl.loc[tbl["ev_shrunk"].abs() < tbl["ev_shrunk"].abs().median() * 0.5, "ticker"].tolist())
    print(f"\n   [verif] tickers proches de zero par EV shrinke (seuil = 50% de la mediane |EV shrinke|) : {near_zero_actual}")
    print(f"   [verif] tickers proposes dans le prompt (SILVER-CHF/USD, GOLD-NZD) : {sorted(NEAR_ZERO_TICKERS)}")
    scenario_C_exclude = sorted(set(near_zero_actual) | set(NEAR_ZERO_TICKERS))
    scenario_C = sorted(set(scenario_A) - set(scenario_C_exclude))
    print(f"C) Exclusion des proches-de-zero seulement : exclut {scenario_C_exclude} -> "
          f"{len(scenario_C)} tickers -> {scenario_C}")

    tbl.to_csv("chantier_gold_silver_etape0_stats_2026-08-19.csv", index=False)
    with open("chantier_gold_silver_etape0_scenarios_2026-08-19.txt", "w", encoding="utf-8") as f:
        f.write(f"A={scenario_A}\nB={scenario_B}\nC={scenario_C}\n")
    print("\nSauvegarde : chantier_gold_silver_etape0_stats_2026-08-19.csv, "
          "chantier_gold_silver_etape0_scenarios_2026-08-19.txt")


if __name__ == "__main__":
    main()
