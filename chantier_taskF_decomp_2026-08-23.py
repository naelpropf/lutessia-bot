"""chantier_taskF_decomp_2026-08-23.py

Verification demandee par l'utilisateur : decompose le saut de profit entre
la reference officielle du registre (S6.5, 17,74-18,03M$, ancienne
population Config0/pre-5-leviers) et le resultat Tache F (58,02-58,77M$) en
isolant chaque changement, un par un.

Limite explicite (a ne pas cacher) : V2/FTMO-discount/GoatGuard/payout_cycle
sont codes EN DUR (pas de flag) dans chantier_taskD_sequential_BA_2026-08-
23.py depuis sa base -08-19 -- impossible de les desactiver individuellement
avec ce moteur pour isoler un "r_trailing seul" totalement propre. L'etape A
ci-dessous est donc "donnees corrigees + V2/FTMO/GoatGuard/payout deja actifs
(comme ils l'etaient DEJA dans le moteur double-flotte avant cette session)
+ risque UNIFORME 1,25/1,90 (ancienne convention) + PAS de S2.35 + pivot 25k$
dynamique + REF (pas de degradation)" -- pas une isolation parfaite de
"r_trailing seul", precise explicitement dans la sortie.

Etapes :
A. donnees corrigees, risque uniforme 1,25/1,90 (les 2 cotes), PAS de S2.35,
   pivot 25k$ dynamique, REF (pas de sequentiel degrade)
B. + S2.35 (size_func tail x1.6, routing rr_tp2)
C. + risque differencie par cote (A=1,25/1,90, B=1,50/1,50)
D. + pivot 2500$ Instant Elite (au lieu de 25k$ dynamique)
E. + scenario "adapte_prudent" (fenetre choc israel_hamas forcee sur B)
   au lieu de REF -- config Tache F finale

Usage : python chantier_taskF_decomp_2026-08-23.py <n_sims> <ceilings_csv>
"""
import sys
import time
import importlib.util

import pandas as pd

_spec = importlib.util.spec_from_file_location("taskd", "chantier_taskD_sequential_BA_2026-08-23.py")
taskd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(taskd)

SEQUENTIAL_B_THRESHOLD = 3000.0
SHOCK_WINDOW = (pd.Timestamp("2023-10-07"), pd.Timestamp("2023-11-15"))
UNIFORM_RISK = {"A": (1.25, 1.90), "B": (1.25, 1.90)}
DIFFERENTIATED_RISK = {"A": (1.25, 1.90), "B": (1.50, 1.50)}


def run_step(label, pop_A, pop_B, market_data, excluded_map, metal_set, ceiling, n_sims,
             risk_dict, use_s235, pivot_fmt_key, pivot_palier, apply_shock):
    taskd.RISK_BY_TID = risk_dict
    size_func = taskd.rr2.make_size_func_tail(1.6) if use_s235 else None
    forced_window = SHOCK_WINDOW if apply_shock else None
    t0 = time.time()
    df = taskd.run_n_sims(pop_A, pop_B, ceiling, n_sims, 9999, True, market_data, excluded_map, metal_set,
                           sequential_b_threshold=SEQUENTIAL_B_THRESHOLD, size_func=size_func,
                           forced_window_B=forced_window, pivot_fmt_key=pivot_fmt_key, pivot_palier=pivot_palier)
    net = df["combined_net"] - df["combined_is_paid"]
    year1_neg = df["combined_year1_net"] < 0
    dt = time.time() - t0
    row = dict(step=label, ceiling=ceiling, n=len(df), profit_moyen=net.mean(), profit_median=net.median(),
               solde_negatif_annee4=(net < 0).mean() * 100, annee1_neg=year1_neg.mean() * 100)
    print(f"[{label} c={ceiling:.0f}$] profit_moy={row['profit_moyen']:+,.0f}$ profit_med={row['profit_median']:+,.0f}$ "
          f"solde_neg={row['solde_negatif_annee4']:.2f}% annee1<0={row['annee1_neg']:.2f}% n={n_sims} ({dt:.0f}s)",
          flush=True)
    return row


def main():
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    ceilings = [float(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [1000.0, 3000.0]

    pop_A, _, _ = taskd.load_common_A()
    pop_B = taskd.build_pop_B()
    oa_all = pd.read_csv("chantier_gold_silver_pop_metaux_all_2026-08-19.csv")
    metal_set = set(oa_all["ticker"].unique())
    market_data, excluded_map = taskd.build_market_data_and_excluded_map(pop_A, pop_B)
    print(f"[verif] pop_A={len(pop_A)} pop_B={len(pop_B)}", flush=True)

    STEPS = [
        ("A_donnees_corrigees_risque_uniforme", UNIFORM_RISK, False, None, None, False),
        ("B_plus_S2.35", UNIFORM_RISK, True, None, None, False),
        ("C_plus_risque_differencie", DIFFERENTIATED_RISK, True, None, None, False),
        ("D_plus_pivot_2500", DIFFERENTIATED_RISK, True, "Blueberry_InstantElite", 2500.0, False),
        ("E_plus_adapte_prudent_FINAL", DIFFERENTIATED_RISK, True, "Blueberry_InstantElite", 2500.0, True),
    ]

    rows = []
    for ceiling in ceilings:
        print(f"{'='*90}\nCEILING={ceiling:.0f}$\n{'='*90}", flush=True)
        for label, risk_dict, use_s235, pivot_fmt_key, pivot_palier, apply_shock in STEPS:
            row = run_step(label, pop_A, pop_B, market_data, excluded_map, metal_set, ceiling, n_sims,
                           risk_dict, use_s235, pivot_fmt_key, pivot_palier, apply_shock)
            rows.append(row)
            pd.DataFrame(rows).to_csv(f"chantier_taskF_decomp_2026-08-23_n{n_sims}.csv", index=False)


if __name__ == "__main__":
    main()
