"""
Chantier B6-1.2 (2026-08-19) -- compare les seuils voisins 1,20/1,25/1,30
pour la segmentation interne rr_tp1 sur B, meme protocole de stress-test
que le reste de la session.

N'importe pas ce script directement (convention du projet).
"""
import importlib.util

import numpy as np
import pandas as pd

ISO_SCRIPT = "chantier_strategie_b_isolation_indices_2026-08-18.py"
spec = importlib.util.spec_from_file_location("iso_b62", ISO_SCRIPT)
iso = importlib.util.module_from_spec(spec)
spec.loader.exec_module(iso)


def outcome_r(pop):
    return np.where(pop["statut_final"] == "OBJECTIF ATTEINT", pop["r_trailing"], -1.0)


def stresstest_threshold(pop, th):
    pop_sorted = pop.sort_values("date_creation").reset_index(drop=True)
    mid = len(pop_sorted) // 2
    subperiods = {"H1": pop_sorted.iloc[:mid], "H2": pop_sorted.iloc[mid:]}
    for i, b in enumerate(np.array_split(pop_sorted, 4)):
        subperiods[f"bloc{i}"] = b
    print(f"\n  --- seuil rr_tp1<={th:.2f} ---")
    n_ok, n_eval = 0, 0
    for name, sp in subperiods.items():
        seg = sp[sp["rr_tp1"] <= th]["r"]
        rest = sp[sp["rr_tp1"] > th]["r"]
        if len(seg) < 5 or len(rest) < 5:
            print(f"    [{name}] n_seg={len(seg)} insuffisant -- ininterpretable")
            continue
        n_eval += 1
        ev_seg, ev_rest = seg.mean(), rest.mean()
        below = ev_seg < ev_rest
        n_ok += int(below)
        flag = "OK (segment<reste)" if below else "INVERSION"
        print(f"    [{name}] n_seg={len(seg):3d} EV={ev_seg:+.4f}R | n_reste={len(rest):3d} EV={ev_rest:+.4f}R "
              f"delta={ev_seg-ev_rest:+.4f}R -- {flag}")
    print(f"  Ratio coherent : {n_ok}/{n_eval}")
    return n_ok, n_eval


if __name__ == "__main__":
    pop_B = iso.build_pop_B("tout_indices")
    pop_B["r"] = outcome_r(pop_B)
    global_ev = pop_B["r"].mean()
    print(f"[verif] population B : n={len(pop_B)}, EV globale={global_ev:+.4f}R")

    print("\n" + "=" * 78)
    print("COMPARAISON DES SEUILS VOISINS -- rr_tp1<=1,20 / 1,25 / 1,30")
    print("=" * 78)
    results = {}
    for th in (1.20, 1.25, 1.30):
        seg = pop_B[pop_B["rr_tp1"] <= th]["r"]
        rest = pop_B[pop_B["rr_tp1"] > th]["r"]
        print(f"\nSeuil {th:.2f} (coupe complete) : n_seg={len(seg)} EV_seg={seg.mean():+.4f}R | "
              f"n_reste={len(rest)} EV_reste={rest.mean():+.4f}R (delta={seg.mean()-rest.mean():+.4f}R)")
        n_ok, n_eval = stresstest_threshold(pop_B, th)
        results[th] = (n_ok, n_eval, seg.mean() - rest.mean())

    print("\n" + "=" * 78)
    print("RESUME")
    print("=" * 78)
    for th, (n_ok, n_eval, delta) in results.items():
        print(f"  seuil={th:.2f} : {n_ok}/{n_eval} sous-periodes coherentes, delta={delta:+.4f}R")
