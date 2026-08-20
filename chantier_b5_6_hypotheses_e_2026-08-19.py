"""
Chantier B5-6 (2026-08-19) -- teste les 3 hypotheses du Chantier E (session
precedente) sur B :
  H1. Segmentation interne rr_tp1 (B n'est pas homogene dans sa bande,
      skew=+2,29 -- floor-cluster vs upper-part different en EV ?)
  H2. Sizing par distance_SL% -- deja teste en B-EV-3 (segmentation), NON
      stable en stress-test (4/6 et 3/6 inversions) -- rappel du verdict
      existant, pas de recalcul redondant.
  H3. Timeout sur la traine longue de duree -- diagnostic correlation
      duree<->R, motive un mecanisme de coupure temporelle si negatif.

N'importe pas ce script directement (convention du projet).
"""
import importlib.util

import numpy as np
import pandas as pd
from scipy import stats

ISO_SCRIPT = "chantier_strategie_b_isolation_indices_2026-08-18.py"
spec = importlib.util.spec_from_file_location("iso_b56", ISO_SCRIPT)
iso = importlib.util.module_from_spec(spec)
spec.loader.exec_module(iso)


def outcome_r(pop):
    return np.where(pop["statut_final"] == "OBJECTIF ATTEINT", pop["r_trailing"], -1.0)


def bootstrap_ci(values, n_boot=5000, seed=9999):
    rng = np.random.default_rng(seed)
    arr = values.to_numpy()
    n = len(arr)
    means = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, n, n)
        means[i] = arr[idx].mean()
    return np.percentile(means, 2.5), np.percentile(means, 97.5)


def stresstest_segment(pop, r_col, mask_fn, label):
    pop_sorted = pop.sort_values("date_creation").reset_index(drop=True)
    mid = len(pop_sorted) // 2
    subperiods = {"H1": pop_sorted.iloc[:mid], "H2": pop_sorted.iloc[mid:]}
    for i, b in enumerate(np.array_split(pop_sorted, 4)):
        subperiods[f"bloc{i}"] = b
    print(f"\n  --- Stress-test H1/H2+4blocs : {label} ---")
    consistent = True
    n_ok = 0
    for name, sp in subperiods.items():
        seg = sp[mask_fn(sp)]
        rest = sp[~mask_fn(sp)]
        if len(seg) < 5 or len(rest) < 5:
            print(f"    [{name}] n_segment={len(seg)} insuffisant -- ininterpretable")
            continue
        ev_seg, ev_rest = seg[r_col].mean(), rest[r_col].mean()
        below = ev_seg < ev_rest
        consistent = consistent and below
        n_ok += 1
        flag = "OK (segment<reste)" if below else "INVERSION"
        print(f"    [{name}] n_seg={len(seg)} EV={ev_seg:+.3f}R | n_reste={len(rest)} EV={ev_rest:+.3f}R -- {flag}")
    print(f"  Coherent sur {n_ok} sous-periodes evaluables : {consistent}")
    return consistent


if __name__ == "__main__":
    pop_B = iso.build_pop_B("tout_indices")
    pop_B["r"] = outcome_r(pop_B)

    print("=" * 78)
    print("H1 -- segmentation interne rr_tp1 sur B (bande 1,00-1,35)")
    print("=" * 78)
    global_ev = pop_B["r"].mean()
    ci_lo, ci_hi = bootstrap_ci(pop_B["r"])
    print(f"EV globale B = {global_ev:+.4f}R  IC95%=[{ci_lo:+.4f},{ci_hi:+.4f}]")

    # Floor cluster (rr_tp1 tres proche du plancher 1.00) vs reste
    for floor_th in (1.05, 1.10, 1.20):
        floor_cluster = pop_B[pop_B["rr_tp1"] <= floor_th]
        rest = pop_B[pop_B["rr_tp1"] > floor_th]
        print(f"\n  Seuil plancher <= {floor_th:.2f} : n_floor={len(floor_cluster)} "
              f"EV_floor={floor_cluster['r'].mean():+.4f}R | n_rest={len(rest)} EV_rest={rest['r'].mean():+.4f}R "
              f"(delta={floor_cluster['r'].mean()-rest['r'].mean():+.4f}R)")

    print("\n  -- Quintiles rr_tp1 sur B --")
    pop_B["_qbin"] = pd.qcut(pop_B["rr_tp1"], 5, duplicates="drop")
    for name, g in pop_B.groupby("_qbin", observed=True):
        flag = " <-- EV NEGATIVE" if g["r"].mean() < 0 else (" <-- sous IC95% bas" if g["r"].mean() < ci_lo else "")
        print(f"    {str(name):>22s} n={len(g):3d} EV={g['r'].mean():+.4f}R winrate={((g['r']>0).mean()*100):.1f}%{flag}")

    # Stress-test le seuil le plus prometteur (1.10 ou celui avec le plus gros delta)
    best_th, best_delta = None, -999
    for th in (1.05, 1.10, 1.15, 1.20, 1.25):
        seg = pop_B[pop_B["rr_tp1"] <= th]["r"]
        rest = pop_B[pop_B["rr_tp1"] > th]["r"]
        if len(seg) < 30 or len(rest) < 30:
            continue
        d = abs(seg.mean() - rest.mean())
        if d > best_delta:
            best_delta, best_th = d, th
    if best_th is not None:
        print(f"\n  [verif] seuil le plus discriminant trouve : rr_tp1<={best_th:.2f} (|delta|={best_delta:.4f}R)")
        stresstest_segment(pop_B, "r", lambda sp, t=best_th: sp["rr_tp1"] <= t, f"rr_tp1<={best_th:.2f}")

    print("\n" + "=" * 78)
    print("H2 -- sizing par distance_SL% -- RAPPEL du verdict deja etabli (B-EV-3, meme session)")
    print("=" * 78)
    print("  distance_SL% : 2 quintiles hauts signales en coupe simple (EV 0,608R/0,440R sous IC95%),")
    print("  mais stress-test H1/H2+4blocs NON coherent (4/6 et 3/6 inversions respectivement)")
    print("  -- deja REJETE comme signal stable sur B, pas de recalcul redondant ici.")
    print("  Note complementaire : le sizing standard (risk_amount = risk_pct% x palier / distance_SL)")
    print("  neutralise deja mecaniquement le risque $ par trade independamment de distance_SL% --")
    print("  l'hypothese 'stop plus large = risque $ plus eleve' ne s'applique PAS sous ce moteur de sizing")
    print("  (verifie par citation : engine_multiformat.py:329-330, eng.feasible_risk_pct calcule le volume")
    print("  a partir du risque cible et de sl_distance, le risque $ vise reste constant).")

    print("\n" + "=" * 78)
    print("H3 -- timeout sur la traine longue de duree")
    print("=" * 78)
    pop_B["duree_h"] = (pop_B["resolution_time_est"] - pop_B["date_creation"]).dt.total_seconds() / 3600
    corr_duree, p_duree = stats.pearsonr(pop_B["duree_h"], pop_B["r"])
    print(f"  Pearson(duree_h, r) = {corr_duree:+.3f} (p={p_duree:.4f}) "
          f"{'SIGNIFICATIF' if p_duree < 0.05 else 'non significatif'}")

    print("\n  -- Quintiles duree --")
    pop_B["_dbin"] = pd.qcut(pop_B["duree_h"], 5, duplicates="drop")
    for name, g in pop_B.groupby("_dbin", observed=True):
        flag = " <-- EV NEGATIVE" if g["r"].mean() < 0 else (" <-- sous IC95% bas" if g["r"].mean() < ci_lo else "")
        print(f"    {str(name):>28s} n={len(g):3d} EV={g['r'].mean():+.4f}R winrate={((g['r']>0).mean()*100):.1f}%{flag}")

    # Segment "traine longue" specifique (P90+)
    p90 = pop_B["duree_h"].quantile(0.90)
    long_tail = pop_B[pop_B["duree_h"] > p90]
    rest = pop_B[pop_B["duree_h"] <= p90]
    print(f"\n  Traine longue (duree>P90={p90:.1f}h) : n={len(long_tail)} EV={long_tail['r'].mean():+.4f}R "
          f"winrate={((long_tail['r']>0).mean()*100):.1f}%")
    print(f"  Reste (duree<=P90)               : n={len(rest)} EV={rest['r'].mean():+.4f}R "
          f"winrate={((rest['r']>0).mean()*100):.1f}%")
    if len(long_tail) >= 20:
        stresstest_segment(pop_B, "r", lambda sp, t=p90: sp["duree_h"] > t, "traine longue (P90)")
    else:
        print(f"  n={len(long_tail)} < 20 -- trop petit pour un stress-test fiable, signale seulement.")
