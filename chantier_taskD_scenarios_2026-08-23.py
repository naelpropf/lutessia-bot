"""chantier_taskD_scenarios_2026-08-23.py

TACHE D (session du 23/08) : modelisation de la sequence B->A declenchee a
3000$ de tresorerie, sur le moteur double-flotte chantier_taskD_sequential_
BA_2026-08-23.py (copie patchee de chantier_ab_metaux_cascade_officiel_2026-
08-19.py -- populations A_seule/B_tradable_pgp courantes, risque par cote
issu de la Tache C2 (A=1,25/1,90%, B=1,50/1,50%), S1.8 deja present dans ce
moteur (process_trade_corr_swap_rr toujours actif), S2.35 ajoute (size_func
tail x1.6 sur rr_tp2). Degradations (winrate_override_B/ev_scale_B/
forced_window_B) ajoutees a run_n_sims EN PRESERVANT le couplage calendaire
joint A/B (meme idx tire pour blocks_A[idx]/blocks_B[idx] a chaque pas de
curseur, cf. corr_PnL_A_B) -- seul le tout premier cran de curseur est
force sur B quand forced_window_B est fourni, A garde son tirage normal
sur ce meme cran.

3 scenarios simules (PAS de replay litteral bloc2, cf. consigne explicite) :
- REF : sequentiel B->A a 3000$, aucune degradation.
- adapte_prudent : degradation PONCTUELLE seule -- le tout premier bloc de 2
  mois de B est force a etre la fenetre choc reelle israel_hamas (memes
  fenetres/mecanisme que chantier_coldstart_svb_isrhamas_2026-08-23.py, deja
  quantifie comme modeste/sans risque de ruine ajoute -- PAS un regime
  soutenu comme bloc2).
- adapte_marge_securite : degradation ponctuelle (idem) + strate de
  robustesse generale sur TOUT le reste de la trajectoire de B (winrate
  P10=48.02%, memes chiffres que chantier_tacheB_stress_degrade_2026-08-23.py
  -- aucun seuil teste ne fait remonter le risque de ruine au-dela de REF).

AUCUNE hypothese midterm degradee pour les indices (decision actee cette
session) -- pas applique ici.

Usage : python chantier_taskD_scenarios_2026-08-23.py <n_sims> <ceilings_csv>
"""
import sys
import time
import importlib.util

import pandas as pd

_spec = importlib.util.spec_from_file_location("taskd", "chantier_taskD_sequential_BA_2026-08-23.py")
taskd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(taskd)

SEQUENTIAL_B_THRESHOLD = 3000.0
SHOCK_WINDOW = (pd.Timestamp("2023-10-07"), pd.Timestamp("2023-11-15"))  # israel_hamas, 26 trades dans B_tradable_pgp
WINRATE_P10 = 0.4802

SCENARIOS = [
    ("REF", dict()),
    ("adapte_prudent", dict(forced_window_B=SHOCK_WINDOW)),
    ("adapte_marge_securite", dict(forced_window_B=SHOCK_WINDOW, winrate_override_B=WINRATE_P10)),
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
    seq = taskd.ei.seq_grouped_multi(1000, 15000, 25000, 25000)

    rows = []
    for ceiling in ceilings:
        for label, kw in SCENARIOS:
            t0 = time.time()
            df = taskd.run_n_sims(pop_A, pop_B, ceiling, n_sims, 9999, True, market_data, excluded_map, metal_set,
                                   sequential_b_threshold=SEQUENTIAL_B_THRESHOLD, size_func=size_func, **kw)
            row = taskd.summarize_df(df, f"{label}_c{ceiling:.0f}", ceiling)
            row["scenario"] = label
            dt = time.time() - t0
            print(f"[{label} c={ceiling:.0f}$] combined_net_moy={row['profit_moyen']:+,.0f}$ "
                  f"solde_neg_an4={row['solde_negatif_annee4']:.2f}% annee1<0={row['annee1_neg']:.2f}% "
                  f"n={n_sims} ({dt:.0f}s)", flush=True)
            rows.append(row)
            pd.DataFrame(rows).to_csv(f"chantier_taskD_scenarios_2026-08-23_n{n_sims}.csv", index=False)


if __name__ == "__main__":
    main()
