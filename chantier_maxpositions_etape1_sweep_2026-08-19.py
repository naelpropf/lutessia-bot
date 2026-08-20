"""Etape 1 (investigation MAX_POSITIONS, 2026-08-19) : sweep MAX_POSITIONS
sur la population B Config 2 (overflow actif) dans le moteur cascade
OFFICIEL (chantier_ab_metaux_cascade_officiel_2026-08-19.py), suite a
l'etape 0 (chantier_maxpositions_etape0_verif_2026-08-19.py) qui a montre
que le cap est BEAUCOUP plus contraignant pour B Config2 (6,4% des
signaux bloques par le cap, EV du segment bloque +1,832R -- superieur a
l'EV moyenne des trades pris, +0,823R) que pour A seule (2,6%, EV
similaire au reste) -- justifie de sweeper au lieu de fermer d'office.

eng.MAX_POSITIONS est monkeypatche AVANT chaque valeur testee -- verifie
que engine_multiformat.py:324 lit eng.MAX_POSITIONS a CHAQUE appel (pas
de valeur figee a l'import), donc l'override est bien pris en compte
pour A ET B (le parametre est un attribut de module global, PAS
specifique a une flotte -- aucune notion de cap separe A/B n'existe dans
le moteur, verifie a l'etape 0)."""
import importlib.util
import sys
import time

import numpy as np
import pandas as pd

import robustness_5ers_risk_challenge as eng

_spec = importlib.util.spec_from_file_location("abm", "chantier_ab_metaux_cascade_officiel_2026-08-19.py")
abm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(abm)

MAX_POSITIONS_VALUES = [3, 4, 5, 6]


def run_sweep_maxpos(n_sims, ceilings, out_tag, seed=9999, maxpos_values=None):
    pop_A, _, _ = abm.load_common_A()
    pop_B = abm.build_pop_B()
    oa_all = pd.read_csv("chantier_gold_silver_pop_metaux_all_2026-08-19.csv")
    metal_set = set(oa_all["ticker"].unique())
    market_data, excluded_map = abm.build_market_data_and_excluded_map(pop_A, pop_B)

    rows = []
    for max_pos in (maxpos_values if maxpos_values is not None else MAX_POSITIONS_VALUES):
        eng.MAX_POSITIONS = max_pos
        print(f"\n{'='*78}\nMAX_POSITIONS = {max_pos}\n{'='*78}")
        for ceiling in ceilings:
            t0 = time.time()
            df = abm.run_n_sims(pop_A, pop_B, ceiling, n_sims, seed, True, market_data, excluded_map, metal_set)
            row = abm.summarize_df(df, f"Config2_AB_maxpos{max_pos}", ceiling)
            b_admitted = df["B_trades_admitted"].mean()
            b_cap_blocked = df["B_cap_blocked"].mean()
            b_corr_blocked = df["B_corr_blocked"].mean()
            b_total_attempts = b_admitted + b_cap_blocked + b_corr_blocked
            row["max_positions"] = max_pos
            row["B_trades_admitted_moy"] = b_admitted
            row["B_cap_blocked_moy"] = b_cap_blocked
            row["B_corr_blocked_moy"] = b_corr_blocked
            row["B_cap_blocked_pct"] = 100 * b_cap_blocked / b_total_attempts if b_total_attempts else float("nan")
            row["B_corr_blocked_pct"] = 100 * b_corr_blocked / b_total_attempts if b_total_attempts else float("nan")
            row["B_rythme_mensuel_admis"] = b_admitted / df["sim_duration_months"].mean()
            rows.append(row)
            print(f"[maxpos={max_pos} plafond={ceiling:.0f}$] profit_moy={row['profit_moyen']:+,.0f}$ "
                  f"solde_neg_an4={row['solde_negatif_annee4']:.2f}% hit_ceiling={row['hit_ceiling_pct']:.2f}% "
                  f"annee1<0={row['annee1_neg']:.2f}% | B: admis={b_admitted:.0f} "
                  f"cap_bloque={row['B_cap_blocked_pct']:.1f}% corr_bloque={row['B_corr_blocked_pct']:.1f}% "
                  f"rythme={row['B_rythme_mensuel_admis']:.1f}/mois ({time.time()-t0:.0f}s)")
            pd.DataFrame(rows).to_csv(f"chantier_maxpositions_etape1_sweep_{out_tag}_2026-08-19.csv", index=False)
    eng.MAX_POSITIONS = 3  # restaure le defaut projet
    return pd.DataFrame(rows)


if __name__ == "__main__":
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    ceilings_arg = [float(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [960.0, 1000.0, 3000.0, 5000.0]
    out_tag = sys.argv[3] if len(sys.argv) > 3 else "screen"
    maxpos_arg = [int(x) for x in sys.argv[4].split(",")] if len(sys.argv) > 4 else None
    run_sweep_maxpos(n_sims, ceilings_arg, out_tag, maxpos_values=maxpos_arg)
