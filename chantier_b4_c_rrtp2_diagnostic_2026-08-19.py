"""
Chantier B4-C (2026-08-19) -- diagnostic du mecanisme rr_tp2 sur B : le
sizing/routage rr_tp2 (§2.35, ADOPTE sur A) a echoue net en stress-test H1
quand rejoue sur B (deja etabli, session precedente). Mecanisme du succes
sur A : correlation rr_tp2<->distance_TP2% = +0,45 (mesuree 08/16, cible
TP2 reellement plus lointaine, PAS un stop-loss artificiellement resserre
-- registre_strategie_trading.md:1771). Recalcule ICI, fraichement, sur les
DEUX populations actuelles (A=742 RR>=1,35 avec indices, B=571
tout-indices->B) pour comparabilite directe sous le meme pipeline.

distance_TP2% = |tp2_init - prix_entree| / prix_entree * 100 (meme
convention que distance_SL% deja utilisee ailleurs dans le projet,
chantier_segmentation_variables_2026-08-17.py).

N'importe pas ce script directement (convention du projet).
"""
import importlib.util

import numpy as np
import pandas as pd
from scipy import stats

ISO_SCRIPT = "chantier_strategie_b_isolation_indices_2026-08-18.py"
spec = importlib.util.spec_from_file_location("iso_b4c", ISO_SCRIPT)
iso = importlib.util.module_from_spec(spec)
spec.loader.exec_module(iso)

REFA_SCRIPT = "chantier_reference_A_indices_2026-08-18.py"
spec2 = importlib.util.spec_from_file_location("refa_b4c", REFA_SCRIPT)
refa = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(refa)

RAW = pd.read_csv("historique_lutessia_15k_force.csv")
RAW["date_creation"] = pd.to_datetime(RAW["date_creation"])
TP2_MAP = RAW.drop_duplicates(subset=["ticker", "date_creation"]).set_index(
    ["ticker", "date_creation"])[["tp2_init", "prix_entree"]]


def attach_tp2(pop):
    pop = pop.copy()
    idx = pd.MultiIndex.from_arrays([pop["ticker"], pop["date_creation"]])
    pop["tp2_init"] = idx.map(TP2_MAP["tp2_init"])
    if "prix_entree" not in pop.columns:
        pop["prix_entree"] = idx.map(TP2_MAP["prix_entree"])
    pop["distance_tp2_pct"] = (pop["tp2_init"] - pop["prix_entree"]).abs() / pop["prix_entree"] * 100
    return pop.dropna(subset=["distance_tp2_pct", "rr_tp2"])


def report(pop, label):
    corr, p = stats.pearsonr(pop["rr_tp2"], pop["distance_tp2_pct"])
    print(f"\n--- {label} (n={len(pop)}) ---")
    print(f"  Pearson(rr_tp2, distance_TP2%) = {corr:+.3f} (p={p:.4f})")
    print(f"  distance_TP2% : moyenne={pop['distance_tp2_pct'].mean():.3f} "
          f"mediane={pop['distance_tp2_pct'].median():.3f}")
    print(f"  rr_tp2        : moyenne={pop['rr_tp2'].mean():.3f} mediane={pop['rr_tp2'].median():.3f}")
    return corr, p


def sweep_thresholds(pop, r_col, thresholds, label):
    print(f"\n  --- Sweep de seuils rr_tp2 sur {label} (EV au-dessus vs en-dessous) ---")
    global_ev = pop[r_col].mean()
    for th in thresholds:
        above = pop[pop["rr_tp2"] > th]
        below = pop[pop["rr_tp2"] <= th]
        if len(above) < 10 or len(below) < 10:
            print(f"    seuil>{th:.1f} : n insuffisant (above={len(above)}, below={len(below)})")
            continue
        print(f"    seuil>{th:.1f} : n_above={len(above):4d} EV_above={above[r_col].mean():+.3f}R | "
              f"n_below={len(below):4d} EV_below={below[r_col].mean():+.3f}R | "
              f"delta={above[r_col].mean()-below[r_col].mean():+.3f}R (global={global_ev:+.3f}R)")


def stresstest_threshold(pop, r_col, th, label):
    pop_sorted = pop.sort_values("date_creation").reset_index(drop=True)
    mid = len(pop_sorted) // 2
    subperiods = {"H1": pop_sorted.iloc[:mid], "H2": pop_sorted.iloc[mid:]}
    for i, b in enumerate(np.array_split(pop_sorted, 4)):
        subperiods[f"bloc{i}"] = b
    print(f"\n  --- Stress-test H1/H2+4blocs, seuil rr_tp2>{th:.1f} sur {label} ---")
    consistent = True
    for name, sp in subperiods.items():
        above = sp[sp["rr_tp2"] > th][r_col]
        below = sp[sp["rr_tp2"] <= th][r_col]
        if len(above) < 5 or len(below) < 5:
            print(f"    [{name}] n insuffisant (above={len(above)}, below={len(below)}) -- ininterpretable")
            continue
        better = above.mean() > below.mean()
        consistent = consistent and better
        flag = "OK (above>below)" if better else "INVERSION (above<=below)"
        print(f"    [{name}] n_above={len(above)} EV={above.mean():+.3f}R | "
              f"n_below={len(below)} EV={below.mean():+.3f}R -- {flag}")
    print(f"  Coherent sur toutes les sous-periodes evaluables : {consistent}")
    return consistent


def outcome_r(pop):
    return np.where(pop["statut_final"] == "OBJECTIF ATTEINT", pop["r_trailing"], -1.0)


if __name__ == "__main__":
    pop_A_fx = refa.build_population_with_trailing("fixed", 0.15, min_rr=1.35, verbose=False)
    pop_idx_all = refa.compute_payoff(refa.load_index_population_full())
    pop_idx_high = pop_idx_all[pop_idx_all["rr_tp1"] >= 1.35].reset_index(drop=True)
    keep_cols = ["date_creation", "ticker", "rr_tp1", "rr_tp2", "statut_final", "r_trailing"]
    pop_A = pd.concat([pop_A_fx[keep_cols], pop_idx_high[keep_cols]], ignore_index=True)
    print(f"[verif] population A reconstruite (742 attendu) : n={len(pop_A)}")
    pop_A = attach_tp2(pop_A)
    pop_A["r"] = outcome_r(pop_A)

    pop_B = iso.build_pop_B("tout_indices")
    pop_B = attach_tp2(pop_B)
    pop_B["r"] = outcome_r(pop_B)

    print("=" * 78)
    print("CORRELATION rr_tp2 <-> distance_TP2%, A vs B (recalcule frais)")
    print("=" * 78)
    corr_A, p_A = report(pop_A, "A (RR>=1,35)")
    corr_B, p_B = report(pop_B, "B (tout-indices->B)")
    print(f"\n[Comparaison] A : r={corr_A:+.3f} (reference historique deja citee : +0,45) | B : r={corr_B:+.3f}")

    if abs(corr_B) < 0.7 * abs(corr_A):
        print("\n>> Correlation nettement plus faible sur B -- indice d'un echec STRUCTUREL "
              "(le mecanisme sous-jacent ne tient pas aussi bien sur B).")
    else:
        print("\n>> Correlation comparable a A -- le mecanisme sous-jacent semble tenir, "
              "l'echec du seuil >8 pourrait etre une question de calibration, pas de structure.")

    print("\n" + "=" * 78)
    print("SWEEP DE SEUILS rr_tp2 SUR B (avant conclusion definitive)")
    print("=" * 78)
    print(f"[verif] distribution rr_tp2 sur B : min={pop_B['rr_tp2'].min():.2f} "
          f"P25={pop_B['rr_tp2'].quantile(.25):.2f} P50={pop_B['rr_tp2'].median():.2f} "
          f"P75={pop_B['rr_tp2'].quantile(.75):.2f} P90={pop_B['rr_tp2'].quantile(.90):.2f} "
          f"max={pop_B['rr_tp2'].max():.2f}")
    thresholds = [pop_B['rr_tp2'].quantile(q) for q in (0.5, 0.6, 0.7, 0.75, 0.8, 0.9)]
    thresholds = sorted(set(round(t, 2) for t in thresholds)) + [8.0]
    sweep_thresholds(pop_B, "r", thresholds, "B")

    # Stress-test le meilleur seuil trouve (delta max, hors seuil 8.0 deja connu perdant)
    best_th = None
    best_delta = -999
    global_ev = pop_B["r"].mean()
    for th in thresholds:
        above = pop_B[pop_B["rr_tp2"] > th]["r"]
        below = pop_B[pop_B["rr_tp2"] <= th]["r"]
        if len(above) < 10 or len(below) < 10:
            continue
        delta = above.mean() - below.mean()
        if delta > best_delta:
            best_delta = delta
            best_th = th
    if best_th is not None:
        print(f"\n[verif] meilleur seuil trouve sur B (delta max) : rr_tp2>{best_th:.2f} (delta={best_delta:+.3f}R)")
        stresstest_threshold(pop_B, "r", best_th, "B")
