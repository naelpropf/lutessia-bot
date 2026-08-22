"""chantier_pivot_bloc2_context_2026-08-23.py

Question utilisateur : le lancement reel est imminent, dans un contexte
decrit comme similaire a bloc2 (le "pire bloc historique" par winrate,
2022-08-20->2023-12-17) + evenements Jackson Hole 28/08 et FOMC 15-16/09 a
venir. Les tests de classement pivot (vitesse/risque) faits jusqu'ici
utilisaient un bootstrap standard (tirage aleatoire sur toute
l'historique), PAS conditionne sur un demarrage type bloc2.

Verification : "adapte_prudent" (Tache D, deja teste par le VPS) force en
realite la fenetre Israel-Hamas (SHOCK_WINDOW=2023-10-07->2023-11-15,
chantier_taskD_scenarios_2026-08-23.py:44), PAS bloc2 -- le classement
pivot n'a JAMAIS ete teste sous bloc2 specifiquement.

Reutilise forced_window_B (deja natif dans taskd.run_dual_ab, meme
mecanisme que adapte_prudent) avec BLOC2=(2022-08-20, 2023-12-17) --
force les trades REELS de bloc2 comme 1er segment de B (offsets
re-ancres), A garde son tirage bootstrap normal sur ce meme cran. Mesure
vitesse de deblocage (A_activation_month/B_full_structure_month, meme
patch que chantier_pivot_unlock_speed_2026-08-23.py) ET risque
(solde_negatif%/annee1<0%) ensemble, aux 5 tailles de pivot, ceiling=1000$
(tresorerie reelle).
"""
import importlib.util
import inspect
import random

import numpy as np
import pandas as pd

_spec = importlib.util.spec_from_file_location("taskd", "chantier_taskD_sequential_BA_2026-08-23.py")
taskd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(taskd)

SEQUENTIAL_B_THRESHOLD = 3000.0
CEILING = 1000.0
N_SIMS = 300
BLOC2 = (pd.Timestamp("2022-08-20"), pd.Timestamp("2023-12-17"))

PIVOT_CONFIGS = [
    ("REF_25k_dynamique", dict(pivot_fmt_key=None, pivot_palier=None)),
    ("Pivot_InstantElite_2500", dict(pivot_fmt_key="Blueberry_InstantElite", pivot_palier=2500.0)),
    ("Pivot_InstantElite_5000", dict(pivot_fmt_key="Blueberry_InstantElite", pivot_palier=5000.0)),
    ("Pivot_InstantElite_10000", dict(pivot_fmt_key="Blueberry_InstantElite", pivot_palier=10000.0)),
    ("Pivot_InstantElite_25000", dict(pivot_fmt_key="Blueberry_InstantElite", pivot_palier=25000.0)),
]

# --- patch run_dual_ab : ajoute A_activation_month + B_full_structure_month (meme technique que chantier_pivot_unlock_speed_2026-08-23.py) ---
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

code = compile(src, "<run_dual_ab_bloc2>", "exec")
exec(code, taskd.__dict__)


def run_config(pop_A, pop_B, n_sims, seed, market_data, excluded_map, metal_set, label, forced_window, kw):
    size_func = taskd.rr2.make_size_func_tail(1.6)
    df = taskd.run_n_sims(pop_A, pop_B, CEILING, n_sims, seed, True, market_data, excluded_map, metal_set,
                           sequential_b_threshold=SEQUENTIAL_B_THRESHOLD, size_func=size_func,
                           forced_window_B=forced_window, **kw)
    profit = df["combined_net"] - df["combined_is_paid"]
    a1_neg = (df["combined_year1_net"] < 0).mean() * 100
    solde_neg = (profit < 0).mean() * 100
    act = df["A_activation_month"].dropna()
    struct = df["B_full_structure_month"].dropna()
    n_active = df["A_activation_month"].notna().sum()
    print(f"[{label}] profit_moy={profit.mean():+,.0f}$ solde_neg={solde_neg:.2f}% annee1<0={a1_neg:.2f}% "
          f"A_active={n_active}/{n_sims} A_activation_month_median={act.median():.2f} "
          f"B_full_structure_month_median={struct.median() if len(struct) else float('nan'):.2f}", flush=True)
    return dict(label=label, profit_moy=profit.mean(), solde_neg=solde_neg, annee1_neg=a1_neg,
                A_activation_month_median=act.median() if len(act) else float("nan"),
                B_full_structure_month_median=struct.median() if len(struct) else float("nan"),
                A_never_activated_pct=100 * (1 - n_active / n_sims))


def main():
    pop_A, _, _ = taskd.load_common_A()
    pop_B = taskd.build_pop_B()
    oa_all = pd.read_csv("chantier_gold_silver_pop_metaux_all_2026-08-19.csv")
    metal_set = set(oa_all["ticker"].unique())
    market_data, excluded_map = taskd.build_market_data_and_excluded_map(pop_A, pop_B)
    n_w = int(((pop_B["date_creation"] >= BLOC2[0]) & (pop_B["date_creation"] < BLOC2[1])).sum())
    print(f"[verif] pop_A={len(pop_A)} pop_B={len(pop_B)} bloc2=[{BLOC2[0].date()}->{BLOC2[1].date()}] "
          f"n_trades_bloc2={n_w} ceiling={CEILING:.0f}$", flush=True)

    rows = []
    for label, kw in PIVOT_CONFIGS:
        print(f"\n{'='*90}\n{label} -- BASELINE (bootstrap normal)\n{'='*90}", flush=True)
        row_base = run_config(pop_A, pop_B, N_SIMS, 9999, market_data, excluded_map, metal_set,
                               f"{label}_baseline", None, kw)
        row_base["variant"] = "baseline"
        rows.append(row_base)

        print(f"\n{'='*90}\n{label} -- BLOC2 force en 1er (contexte actuel)\n{'='*90}", flush=True)
        row_bloc2 = run_config(pop_A, pop_B, N_SIMS, 9999, market_data, excluded_map, metal_set,
                                f"{label}_bloc2", BLOC2, kw)
        row_bloc2["variant"] = "bloc2_force"
        rows.append(row_bloc2)

        delta_speed = row_bloc2["A_activation_month_median"] - row_base["A_activation_month_median"]
        delta_risk = row_bloc2["solde_neg"] - row_base["solde_neg"]
        print(f"  -> DELTA (bloc2 - baseline) : vitesse A={delta_speed:+.2f}mois, "
              f"solde_neg={delta_risk:+.2f}pts, profit={((row_bloc2['profit_moy']/row_base['profit_moy'])-1)*100:+.2f}%", flush=True)

        pd.DataFrame(rows).to_csv("chantier_pivot_bloc2_context_2026-08-23.csv", index=False)

    print(f"\n{'='*95}\nSYNTHESE\n{'='*95}")
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
