"""
Chantier B4-A (2026-08-19) -- score Force restreint aux indices de B.

Q1 : un test Force<->resultat a-t-il deja ete fait sur forex ? OUI --
registre_strategie_trading.md S2.1 ("Force score -- REJETE, DEUX variantes
testees") : correlation Force<->victoire r=+0,026 (t=0,56, n=472),
Force<->R r=+0,072 (t=1,55, n=472) -- toutes deux NON significatives.
Teste sur l'ancienne population forex (RR seuil different, pre-expansion
indices). Ici : meme calcul sur la population B forex ACTUELLE (reference
directe), puis le vrai test demande sur les indices de B seuls.

N'importe pas ce script directement (convention du projet).
"""
import importlib.util

import numpy as np
import pandas as pd
from scipy import stats

ISO_SCRIPT = "chantier_strategie_b_isolation_indices_2026-08-18.py"
spec = importlib.util.spec_from_file_location("iso_b4a", ISO_SCRIPT)
iso = importlib.util.module_from_spec(spec)
spec.loader.exec_module(iso)

INDEX_KEYWORDS = ["DAX40", "S&P500", "NASDAQ100"]


def outcome_r(pop):
    return np.where(pop["statut_final"] == "OBJECTIF ATTEINT", pop["r_trailing"], -1.0)


def report_force_corr(sub, label):
    r = outcome_r(sub)
    force = sub["score_force"].to_numpy()
    win = (r > 0).astype(float)
    corr_win, p_win = stats.pearsonr(force, win)
    corr_r, p_r = stats.pearsonr(force, r)
    n = len(sub)
    t_win = corr_win * np.sqrt(n - 2) / np.sqrt(1 - corr_win**2) if abs(corr_win) < 1 else float("inf")
    t_r = corr_r * np.sqrt(n - 2) / np.sqrt(1 - corr_r**2) if abs(corr_r) < 1 else float("inf")
    print(f"\n--- {label} (n={n}) ---")
    print(f"  score_force : moyenne={force.mean():.3f} mediane={np.median(force):.3f} "
          f"min={force.min():.2f} max={force.max():.2f}")
    print(f"  Correlation Force<->victoire : r={corr_win:+.3f} (t={t_win:.2f}, p={p_win:.3f}) "
          f"{'SIGNIFICATIF' if p_win < 0.05 else 'non significatif'}")
    print(f"  Correlation Force<->R        : r={corr_r:+.3f} (t={t_r:.2f}, p={p_r:.3f}) "
          f"{'SIGNIFICATIF' if p_r < 0.05 else 'non significatif'}")

    # quintiles
    sub = sub.copy()
    sub["_r"] = r
    sub["_qbin"] = pd.qcut(sub["score_force"], min(5, sub["score_force"].nunique()), duplicates="drop")
    print(f"  Segments par quintile Force :")
    for name, g in sub.groupby("_qbin", observed=True):
        print(f"    {str(name):>18s} n={len(g):3d} EV={g['_r'].mean():+.3f}R winrate={((g['_r']>0).mean()*100):.1f}%")
    return corr_r, p_r, n


def stresstest_force(sub, label):
    sub = sub.sort_values("date_creation").reset_index(drop=True)
    sub["_r"] = outcome_r(sub)
    mid = len(sub) // 2
    subperiods = {"H1": sub.iloc[:mid], "H2": sub.iloc[mid:]}
    for i, b in enumerate(np.array_split(sub, 4)):
        subperiods[f"bloc{i}"] = b
    print(f"\n  --- Stress-test H1/H2+4blocs (correlation Force<->R) pour {label} ---")
    for name, sp in subperiods.items():
        if len(sp) < 10:
            print(f"    [{name}] n={len(sp)} insuffisant -- ininterpretable")
            continue
        c, p = stats.pearsonr(sp["score_force"], sp["_r"])
        print(f"    [{name}] n={len(sp)} r={c:+.3f} (p={p:.3f})")


if __name__ == "__main__":
    pop_B = iso.build_pop_B("tout_indices")
    raw = pd.read_csv("historique_lutessia_15k_force.csv")
    raw["date_creation"] = pd.to_datetime(raw["date_creation"])
    force_map = raw.drop_duplicates(subset=["ticker", "date_creation"]).set_index(
        ["ticker", "date_creation"])["score_force"]
    pop_B["score_force"] = pop_B.set_index(["ticker", "date_creation"]).index.map(force_map)

    missing = pop_B["score_force"].isna().sum()
    print(f"[verif] population B : n={len(pop_B)}, score_force manquant pour {missing} lignes")
    pop_B = pop_B.dropna(subset=["score_force"]).reset_index(drop=True)

    is_index = pop_B["ticker"].str.contains("|".join(INDEX_KEYWORDS), case=False, na=False)
    pop_fx = pop_B[~is_index].reset_index(drop=True)
    pop_idx = pop_B[is_index].reset_index(drop=True)

    print("=" * 70)
    print("REFERENCE -- B forex seul (population actuelle, pas l'ancienne S2.1)")
    print("=" * 70)
    report_force_corr(pop_fx, "B forex")

    print("\n" + "=" * 70)
    print("TEST PRINCIPAL -- indices de B seuls")
    print("=" * 70)
    corr_r_idx, p_idx, n_idx = report_force_corr(pop_idx, "B indices")

    if n_idx >= 30:
        stresstest_force(pop_idx, "B indices")
    else:
        print(f"\n  n={n_idx} < 30 -- trop petit pour un stress-test H1/H2+4blocs fiable "
              f"(sous-groupes de ~{n_idx//6} trades chacun) -- signale, pas teste.")
