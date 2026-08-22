"""chantier_taskE_pivot_2026-08-23.py

TACHE E (session du 23/08), point 1 : reteste le pivot jour0 a tailles
reduites (Blueberry Instant Elite 2,5k$/100$, 5k$/200$, 10k$/400$,
25k$/800$) sur la reference ACTUELLE (donnees r_trailing corrigees, 5
leviers adoptes, B_tradable_pgp lancee en premier, sequentiel B->A a
3000$ -- moteur chantier_taskD_sequential_BA_2026-08-23.py, meme
population/risque/S1.8/S2.35 que la Tache D, AUCUNE degradation --
scenario REF pur).

Tranche la question laissee ambigue en 08/18 (chantier_pivot_instant_
taille_reduite_2026-08-18.py, n=300 screening, moteur pre-fix/pre-5-
leviers/A-seule) : une taille reduite bat-elle 25k$/800$ (config REF
actuelle) EN PROFIT ET EN ANNEE1<0, ou seulement en cout d'entree sans
battre la reference sur les metriques de risque/profit ?

5 configs : REF (25k$ dynamique standard, palier BASE_PALIER["Blueberry"]),
Pivot2500/5000/10000/25000 (Instant Elite FIXE toute la vie du compte,
cf. PIVOT_PRICE dans chantier_taskD_sequential_BA_2026-08-23.py).

Usage : python chantier_taskE_pivot_2026-08-23.py <n_sims> <ceilings_csv>
"""
import sys
import time
import importlib.util

import pandas as pd

_spec = importlib.util.spec_from_file_location("taskd", "chantier_taskD_sequential_BA_2026-08-23.py")
taskd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(taskd)

SEQUENTIAL_B_THRESHOLD = 3000.0

PIVOT_CONFIGS = [
    ("REF_25k_dynamique", dict(pivot_fmt_key=None, pivot_palier=None)),
    ("Pivot_InstantElite_2500", dict(pivot_fmt_key="Blueberry_InstantElite", pivot_palier=2500.0)),
    ("Pivot_InstantElite_5000", dict(pivot_fmt_key="Blueberry_InstantElite", pivot_palier=5000.0)),
    ("Pivot_InstantElite_10000", dict(pivot_fmt_key="Blueberry_InstantElite", pivot_palier=10000.0)),
    ("Pivot_InstantElite_25000", dict(pivot_fmt_key="Blueberry_InstantElite", pivot_palier=25000.0)),
]


def main():
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    ceilings = [float(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [1000.0, 3000.0]

    pop_A, _, _ = taskd.load_common_A()
    pop_B = taskd.build_pop_B()
    oa_all = pd.read_csv("chantier_gold_silver_pop_metaux_all_2026-08-19.csv")
    metal_set = set(oa_all["ticker"].unique())
    market_data, excluded_map = taskd.build_market_data_and_excluded_map(pop_A, pop_B)
    print(f"[verif] pop_A={len(pop_A)} pop_B={len(pop_B)} seuil_sequentiel={SEQUENTIAL_B_THRESHOLD:.0f}$", flush=True)

    size_func = taskd.rr2.make_size_func_tail(1.6)  # S2.35, adopte

    rows = []
    for ceiling in ceilings:
        for label, kw in PIVOT_CONFIGS:
            t0 = time.time()
            df = taskd.run_n_sims(pop_A, pop_B, ceiling, n_sims, 9999, True, market_data, excluded_map, metal_set,
                                   sequential_b_threshold=SEQUENTIAL_B_THRESHOLD, size_func=size_func, **kw)
            row = taskd.summarize_df(df, f"{label}_c{ceiling:.0f}", ceiling)
            row["config"] = label
            row["cout_ouverture_reel"] = (taskd.PIVOT_PRICE[(kw["pivot_fmt_key"], kw["pivot_palier"])]
                                           if kw["pivot_fmt_key"] is not None else 800.0)
            dt = time.time() - t0
            print(f"[{label} c={ceiling:.0f}$] cout={row['cout_ouverture_reel']:.0f}$ "
                  f"combined_net_moy={row['profit_moyen']:+,.0f}$ profit_median={row['profit_median']:+,.0f}$ "
                  f"solde_neg_an4={row['solde_negatif_annee4']:.2f}% annee1<0={row['annee1_neg']:.2f}% "
                  f"n={n_sims} ({dt:.0f}s)", flush=True)
            rows.append(row)
            pd.DataFrame(rows).to_csv(f"chantier_taskE_pivot_2026-08-23_n{n_sims}.csv", index=False)


if __name__ == "__main__":
    main()
