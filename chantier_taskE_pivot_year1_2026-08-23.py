"""chantier_taskE_pivot_year1_2026-08-23.py

Complement a chantier_taskE_pivot_2026-08-23.py (deja fait par le VPS,
n=300 aux 2 plafonds + n=600 confirme a c=1000$ -- ranking deja etabli :
Pivot Instant Elite 2500$/5000$ dominent REF 25k$ EN PROFIT ET EN RISQUE a
c=1000$, tout converge a c=3000$). Ce script AJOUTE uniquement le profit
annee 1 (deja track par le moteur via df["combined_year1_net"], jamais
extrait dans summarize_df original) -- reutilise integralement
chantier_taskD_sequential_BA_2026-08-23.py::run_n_sims, memes 5 configs,
meme seed=9999, meme size_func S2.35, n=300 (screening suffisant, le
ranking est deja confirme n=600 par ailleurs).
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


def summarize_with_year1(df, label, ceiling):
    row = taskd.summarize_df(df, label, ceiling)
    row["profit_annee1_moyen"] = df["combined_year1_net"].mean()
    row["profit_annee1_median"] = df["combined_year1_net"].median()
    return row


def main():
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    ceilings = [float(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [1000.0, 3000.0]

    pop_A, _, _ = taskd.load_common_A()
    pop_B = taskd.build_pop_B()
    oa_all = pd.read_csv("chantier_gold_silver_pop_metaux_all_2026-08-19.csv")
    metal_set = set(oa_all["ticker"].unique())
    market_data, excluded_map = taskd.build_market_data_and_excluded_map(pop_A, pop_B)
    print(f"[verif] pop_A={len(pop_A)} pop_B={len(pop_B)} seuil_sequentiel={SEQUENTIAL_B_THRESHOLD:.0f}$", flush=True)

    size_func = taskd.rr2.make_size_func_tail(1.6)

    rows = []
    for ceiling in ceilings:
        for label, kw in PIVOT_CONFIGS:
            t0 = time.time()
            df = taskd.run_n_sims(pop_A, pop_B, ceiling, n_sims, 9999, True, market_data, excluded_map, metal_set,
                                   sequential_b_threshold=SEQUENTIAL_B_THRESHOLD, size_func=size_func, **kw)
            row = summarize_with_year1(df, f"{label}_c{ceiling:.0f}", ceiling)
            row["config"] = label
            row["cout_ouverture_reel"] = (taskd.PIVOT_PRICE[(kw["pivot_fmt_key"], kw["pivot_palier"])]
                                           if kw["pivot_fmt_key"] is not None else 800.0)
            dt = time.time() - t0
            print(f"[{label} c={ceiling:.0f}$] cout={row['cout_ouverture_reel']:.0f}$ "
                  f"profit_an1_moy={row['profit_annee1_moyen']:+,.0f}$ profit_4ans_moy={row['profit_moyen']:+,.0f}$ "
                  f"solde_neg_an4={row['solde_negatif_annee4']:.2f}% annee1<0={row['annee1_neg']:.2f}% "
                  f"n={n_sims} ({dt:.0f}s)", flush=True)
            rows.append(row)
            pd.DataFrame(rows).to_csv("chantier_taskE_pivot_year1_2026-08-23.csv", index=False)

    print(f"\n{'='*95}\nSYNTHESE\n{'='*95}")
    print(pd.DataFrame(rows)[["config", "ceiling", "cout_ouverture_reel", "profit_annee1_moyen", "profit_moyen",
                               "solde_negatif_annee4", "annee1_neg"]].to_string(index=False))


if __name__ == "__main__":
    main()
