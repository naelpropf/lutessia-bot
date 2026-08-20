"""Lancement sequentiel B->A (2026-08-20) : B_tradable (Config0, 1051
trades, deja acte comme meilleur candidat solo) demarre seule, A s'ouvre
quand la reserve de B franchit un seuil. Overflow metaux B->A actif des
que A existe (decision utilisateur, meme mecanisme que Config2 jour0).

Reutilise chantier_ab_metaux_cascade_officiel_2026-08-19.py:run_dual_ab
avec sequential_b_threshold -- cf. docstring de cette fonction pour la
justification du choix de NE PAS reutiliser try_gft_delayed_trigger
(declencheur temporel) ni open_group() (format Blueberry statique) tel
quel."""
import importlib.util
import sys
import time

import numpy as np
import pandas as pd

_spec = importlib.util.spec_from_file_location("abm", "chantier_ab_metaux_cascade_officiel_2026-08-19.py")
abm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(abm)


def build_pop_B_tradable():
    pop = pd.read_csv("chantier_gold_silver_pop_B_config0_tradable_2026-08-19.csv")
    pop["date_creation"] = pd.to_datetime(pop["date_creation"])
    pop["resolution_time_est"] = pd.to_datetime(pop["resolution_time_est"])
    return pop


abm.build_pop_B = build_pop_B_tradable
abm.ALPHA_POST_B_METAUX = 533
abm.BETA_POST_B_METAUX = 520


def run_sweep_sequential(n_sims, ceilings, thresholds, out_tag, seed=9999):
    pop_A, _, _ = abm.load_common_A()
    pop_B = abm.build_pop_B()
    oa_all = pd.read_csv("chantier_gold_silver_pop_metaux_all_2026-08-19.csv")
    metal_set = set(oa_all["ticker"].unique())
    market_data, excluded_map = abm.build_market_data_and_excluded_map(pop_A, pop_B)

    rows = []
    for threshold in thresholds:
        for ceiling in ceilings:
            t0 = time.time()
            df = abm.run_n_sims(pop_A, pop_B, ceiling, n_sims, seed, True, market_data, excluded_map, metal_set,
                                 sequential_b_threshold=threshold)
            row = abm.summarize_df(df, f"Sequentiel_seuil{threshold:.0f}", ceiling)
            row["seuil_declenchement"] = threshold
            rows.append(row)
            print(f"[seuil={threshold:.0f}$ plafond={ceiling:.0f}$] profit_moy={row['profit_moyen']:+,.0f}$ "
                  f"solde_neg_an4={row['solde_negatif_annee4']:.2f}% hit_ceiling={row['hit_ceiling_pct']:.2f}% "
                  f"annee1<0={row['annee1_neg']:.2f}% corr_PnL(A,B)={row['corr_PnL_A_B']:.3f} ({time.time()-t0:.0f}s)")
            pd.DataFrame(rows).to_csv(f"chantier_lancement_sequentiel_BA_{out_tag}_2026-08-19.csv", index=False)
    return pd.DataFrame(rows)


def run_stress_sequential(n_sims, ceilings, thresholds, out_tag, seed=13579):
    pop_A, _, _ = abm.load_common_A()
    pop_B = abm.build_pop_B()
    oa_all = pd.read_csv("chantier_gold_silver_pop_metaux_all_2026-08-19.csv")
    metal_set = set(oa_all["ticker"].unique())
    market_data, excluded_map = abm.build_market_data_and_excluded_map(pop_A, pop_B)

    rows = []
    for n_parts, tag in ((2, "H"), (4, "bloc")):
        parts = abm.date_subperiods(pop_A, pop_B, n_parts)
        for i, (sub_A, sub_B) in enumerate(parts):
            if len(sub_A) < 10 or len(sub_B) < 10:
                print(f"[{tag}{i+1}] sous-population trop petite (A={len(sub_A)}, B={len(sub_B)}) -- ignore")
                continue
            for threshold in thresholds:
                for ceiling in ceilings:
                    t0 = time.time()
                    df = abm.run_n_sims(sub_A, sub_B, ceiling, n_sims, seed, True, market_data, excluded_map,
                                         metal_set, sequential_b_threshold=threshold)
                    row = abm.summarize_df(df, f"Sequentiel_seuil{threshold:.0f}_{tag}{i+1}", ceiling)
                    row["seuil_declenchement"] = threshold
                    row["n_trades_A"] = len(sub_A)
                    row["n_trades_B"] = len(sub_B)
                    rows.append(row)
                    print(f"[{tag}{i+1} seuil={threshold:.0f}$ c={ceiling:.0f}$] profit_moy={row['profit_moyen']:+,.0f}$ "
                          f"solde_neg_an4={row['solde_negatif_annee4']:.2f}% annee1<0={row['annee1_neg']:.2f}% "
                          f"({time.time()-t0:.0f}s)")
                    pd.DataFrame(rows).to_csv(f"chantier_lancement_sequentiel_BA_stress_{out_tag}_2026-08-19.csv", index=False)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    mode = sys.argv[1]  # "sweep" ou "stress"
    n_sims = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    ceilings_arg = [float(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else [3000.0, 5000.0]
    thresholds_arg = [float(x) for x in sys.argv[4].split(",")] if len(sys.argv) > 4 else [5000.0]
    out_tag = sys.argv[5] if len(sys.argv) > 5 else "screen"
    if mode == "sweep":
        run_sweep_sequential(n_sims, ceilings_arg, thresholds_arg, out_tag)
    elif mode == "stress":
        run_stress_sequential(n_sims, ceilings_arg, thresholds_arg, out_tag)
