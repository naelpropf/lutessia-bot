"""chantier_pivot_unlock_speed_2026-08-23.py

Question utilisateur : a tresorerie 3000$, une taille de pivot plus grosse
accelere-t-elle le deblocage de la flotte (puisque le risque est deja plat
a 0% a ce plafond, cf. chantier_taskE_pivot_2026-08-23.py) ? Le moteur
(chantier_taskD_sequential_BA_2026-08-23.py) track deja en interne
`full_structure_month` (par trader) et le moment ou A s'active
(`_seq_activated`), mais aucun des deux n'est expose dans `run_dual_ab`'s
result dict -- extension minimale (patch par inspect.getsource + exec,
zero modification du fichier source reel) qui ajoute 2 champs :
  - `A_activation_month` : mois ou la reserve de B franchit
    sequential_b_threshold=3000$ et declenche l'ouverture de A (le vrai
    "deblocage" que la question vise).
  - `B_full_structure_month` : mois ou TOUS les firms de B sont ouverts
    (structure complete cote B).
"""
import importlib.util
import inspect
import sys
import time

import pandas as pd

_spec = importlib.util.spec_from_file_location("taskd", "chantier_taskD_sequential_BA_2026-08-23.py")
taskd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(taskd)

# --- patch run_dual_ab : ajoute A_activation_month + B_full_structure_month au resultat ---
src = inspect.getsource(taskd.run_dual_ab)
marker1 = 'st["A"]["_seq_activated"] = True'
lines0 = src.split("\n")
for i, line in enumerate(lines0):
    if marker1 in line:
        indent = line[:len(line) - len(line.lstrip())]
        lines0[i] = line + f'\n{indent}st["A"]["_seq_activated_month"] = now / MONTH_SECONDS'
        break
else:
    raise RuntimeError("point d'injection _seq_activated introuvable")
src = "\n".join(lines0)

marker2 = 'result["combined_hit_ceiling"] = combined_cash["hit_ceiling"]'
lines = src.split("\n")
for i, line in enumerate(lines):
    if marker2 in line:
        indent = line[:len(line) - len(line.lstrip())]
        lines[i] = (f'{indent}result["A_activation_month"] = st["A"].get("_seq_activated_month")\n'
                     f'{indent}result["B_full_structure_month"] = st["B"].get("full_structure_month")\n'
                     f'{line}')
        break
else:
    raise RuntimeError("point d'injection result dict introuvable")
src = "\n".join(lines)

code = compile(src, "<run_dual_ab_unlock_speed>", "exec")
exec(code, taskd.__dict__)  # exec dans le namespace REEL du module -- rebind direct

SEQUENTIAL_B_THRESHOLD = 3000.0

PIVOT_CONFIGS = [
    ("REF_25k_dynamique", dict(pivot_fmt_key=None, pivot_palier=None)),
    ("Pivot_InstantElite_2500", dict(pivot_fmt_key="Blueberry_InstantElite", pivot_palier=2500.0)),
    ("Pivot_InstantElite_5000", dict(pivot_fmt_key="Blueberry_InstantElite", pivot_palier=5000.0)),
    ("Pivot_InstantElite_10000", dict(pivot_fmt_key="Blueberry_InstantElite", pivot_palier=10000.0)),
    ("Pivot_InstantElite_25000", dict(pivot_fmt_key="Blueberry_InstantElite", pivot_palier=25000.0)),
]


def run_n_sims_with_unlock(pop_A, pop_B, ceiling, n_sims, seed, include_B, market_data, excluded_map, metal_set,
                            **kw):
    """taskd.run_n_sims appelle run_dual_ab par nom, resolu dans taskd.__dict__
    -- deja patche en place plus haut (exec directement dans taskd.__dict__,
    pas une copie), donc un appel direct suffit, pas besoin de re-copier."""
    return taskd.run_n_sims(pop_A, pop_B, ceiling, n_sims, seed, include_B, market_data, excluded_map, metal_set, **kw)


def main():
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    ceiling = float(sys.argv[2]) if len(sys.argv) > 2 else 3000.0

    pop_A, _, _ = taskd.load_common_A()
    pop_B = taskd.build_pop_B()
    oa_all = pd.read_csv("chantier_gold_silver_pop_metaux_all_2026-08-19.csv")
    metal_set = set(oa_all["ticker"].unique())
    market_data, excluded_map = taskd.build_market_data_and_excluded_map(pop_A, pop_B)
    print(f"[verif] pop_A={len(pop_A)} pop_B={len(pop_B)} seuil_sequentiel={SEQUENTIAL_B_THRESHOLD:.0f}$ ceiling={ceiling:.0f}$", flush=True)

    size_func = taskd.rr2.make_size_func_tail(1.6)

    rows = []
    for label, kw in PIVOT_CONFIGS:
        t0 = time.time()
        df = run_n_sims_with_unlock(pop_A, pop_B, ceiling, n_sims, 9999, True, market_data, excluded_map, metal_set,
                                     sequential_b_threshold=SEQUENTIAL_B_THRESHOLD, size_func=size_func, **kw)
        n_activated = df["A_activation_month"].notna().sum()
        act = df["A_activation_month"].dropna()
        struct = df["B_full_structure_month"].dropna()
        dt = time.time() - t0
        print(f"[{label} c={ceiling:.0f}$] A_active={n_activated}/{n_sims} "
              f"A_activation_month(median/p10/p90)={act.median():.2f}/{act.quantile(.1):.2f}/{act.quantile(.9):.2f} "
              f"B_full_structure_month(median)={struct.median() if len(struct) else float('nan'):.2f} "
              f"({dt:.0f}s)", flush=True)
        rows.append(dict(config=label,
                          A_activation_month_median=act.median() if len(act) else float("nan"),
                          A_activation_month_p10=act.quantile(.1) if len(act) else float("nan"),
                          A_activation_month_p90=act.quantile(.9) if len(act) else float("nan"),
                          A_never_activated_pct=100 * (1 - n_activated / n_sims),
                          B_full_structure_month_median=struct.median() if len(struct) else float("nan")))
        pd.DataFrame(rows).to_csv("chantier_pivot_unlock_speed_2026-08-23.csv", index=False)

    print(f"\n{'='*95}\nSYNTHESE\n{'='*95}")
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
