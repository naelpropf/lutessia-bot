"""chantier_walkforward_retest_2026-08-21.py

Reproduit exactement la methodologie de walk_forward_gap_investigation.py
(split chronologique 60/40, test de permutation N=10000 seed=42) sur les 2
populations regenerees avec r_trailing corrige (backfill MT5 + garde-fou
prospectif) -- chantier_rtrailing_recalc_2026-08-21.py :

  1. "officielle_verrouillee" (n=618, rr_tp1>=1,5, trailing=0,2, forex+
     indices -- population ACTUELLE complete, pas l'instantane fige a 472).
  2. "A_reelle" filtree forex SEUL (n=631, rr_tp1>=1,35, trailing=0,15) --
     le regenere brut (chantier_rtrailing_recalc_A_reelle_2026-08-21.csv)
     contient 742 lignes (forex+indices, meme convention que build_extended_
     population post-fix forex-only) ; filtre applique ici pour matcher
     EXACTEMENT le n=631 forex-only cite comme "A reelle" cette session."""
import re

import numpy as np
import pandas as pd

N_PERM = 10000
PERM_SEED = 42
FOREX_PATTERN = re.compile(r"^[A-Z]{3}/[A-Z]{3}$")


def permutation_test(train, test):
    n_train, n_test = len(train), len(test)
    all_r = pd.concat([train, test])["r_trailing"].to_numpy()
    n_total = len(all_r)
    observed_gap = test["r_trailing"].mean() - train["r_trailing"].mean()

    rng = np.random.default_rng(PERM_SEED)
    gaps = np.empty(N_PERM)
    for i in range(N_PERM):
        idx = rng.permutation(n_total)
        test_idx = idx[:n_test]
        train_idx = idx[n_test:]
        gaps[i] = all_r[test_idx].mean() - all_r[train_idx].mean()

    p_value = (np.abs(gaps) >= abs(observed_gap)).mean()
    return observed_gap, p_value, gaps.mean(), gaps.std()


def run_walkforward(df, label):
    df = df.sort_values("date_creation").reset_index(drop=True)
    n = len(df)
    cut = int(round(n * 0.60))
    train = df.iloc[:cut]
    test = df.iloc[cut:].copy()

    print(f"\n{'='*100}\n{label} -- n={n} ({df['date_creation'].min().date()} -> {df['date_creation'].max().date()})\n{'='*100}")
    print(f"Split 60/40 -- train n={len(train)} EV={train['r_trailing'].mean():+.4f}R "
          f"| test n={len(test)} EV={test['r_trailing'].mean():+.4f}R")

    observed_gap, p_value, perm_mean, perm_std = permutation_test(train, test)
    print(f"Ecart observe (test-train) : {observed_gap:+.4f}R | p-value (bilateral, {N_PERM} perms) : {p_value:.4f} "
          f"| ecart permute moyen={perm_mean:+.4f}R std={perm_std:.4f}R")
    if p_value < 0.05:
        print("-> Significatif a 5%.")
    else:
        print("-> NON significatif a 5%.")

    print(f"\nEV par trimestre calendaire :")
    df2 = df.copy()
    df2["quarter"] = df2["date_creation"].dt.to_period("Q")
    q = df2.groupby("quarter").agg(n=("r_trailing", "size"), ev=("r_trailing", "mean"),
                                     winrate=("statut_final", lambda s: (s == "OBJECTIF ATTEINT").mean() * 100))
    print(q.to_string())
    return dict(label=label, n=n, train_ev=train["r_trailing"].mean(), test_ev=test["r_trailing"].mean(),
                observed_gap=observed_gap, p_value=p_value)


def main():
    off = pd.read_csv("chantier_rtrailing_recalc_officielle_verrouillee_2026-08-21.csv")
    off["date_creation"] = pd.to_datetime(off["date_creation"])
    r1 = run_walkforward(off, "OFFICIELLE_VERROUILLEE (rr_tp1>=1,5, trailing=0,2, forex+indices)")

    a = pd.read_csv("chantier_rtrailing_recalc_A_reelle_2026-08-21.csv")
    a["date_creation"] = pd.to_datetime(a["date_creation"])
    is_forex = a["ticker"].apply(lambda t: bool(FOREX_PATTERN.match(str(t))))
    a_forex = a[is_forex].reset_index(drop=True)
    assert len(a_forex) == 631, f"n inattendu apres filtre forex : {len(a_forex)} (attendu 631)"
    r2 = run_walkforward(a_forex, "A_REELLE forex seul (rr_tp1>=1,35, trailing=0,15, n=631)")

    print(f"\n{'='*100}\nRESUME\n{'='*100}")
    for r in (r1, r2):
        print(f"  {r['label']}: n={r['n']} train_EV={r['train_ev']:+.4f}R test_EV={r['test_ev']:+.4f}R "
              f"gap={r['observed_gap']:+.4f}R p={r['p_value']:.4f}")


if __name__ == "__main__":
    main()
