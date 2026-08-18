"""
Addendum 2026-08-16 : decomposition rigoureuse de l'effet groupe (meme
script/seed/population que chantier_cascade_combined_bb_switch_any_rr_2026-
08-16.py, evite toute comparaison a des chiffres isoles venant d'un AUTRE
script/n/seed). Pour chaque plafond, calcule bb_only (bascule Blueberry
seule, any-RR desactive) et rr_only (any-RR seul, bascule Blueberry
desactivee) en plus de REF et COMBINE deja obtenus -- permet de comparer le
gain COMBINE au gain (bb_only + rr_only) mesure exactement dans les memes
conditions.
"""
import time
import importlib.util
import pandas as pd

_spec = importlib.util.spec_from_file_location("chantier_cascade_combined_main", "chantier_cascade_combined_bb_switch_any_rr_2026-08-16.py")
_main = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_main)
load_common, run_propagated, summarize = _main.load_common, _main.run_propagated, _main.summarize
EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK = _main.EVAL_RISK, _main.FLEET_RISK, _main.GFT_EVAL_RISK

import etape_e_fleet_integration as ei

if __name__ == "__main__":
    import sys
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    ceilings_arg = [float(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [960.0, 1000.0, 3000.0, 5000.0]

    t_start = time.time()
    pop, market_data, excluded_map = load_common()
    print(f"[verif] population construite : {len(pop)} trades")
    seq = ei.seq_grouped_multi(1000, 15000, 25000, 25000)
    config = ei.CONFIG_REF

    common_kwargs = dict(emergency=ei.DEFAULT_EMERGENCY, eval_risk=EVAL_RISK, fleet_risk=FLEET_RISK,
                          gft_eval_risk=GFT_EVAL_RISK, reserve_share=ei.FINAL_RESERVE_SHARE,
                          extra_threshold_mult=ei.EXTRA_THRESHOLD_MULT, n_sims=n_sims, seed=9999,
                          b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True,
                          ftmo_discount=True, gft_goat_guard=True, payout_cycle=True)

    BB_THRESHOLD_BY_CEILING = {960.0: 5000.0, 1000.0: 5000.0, 3000.0: 0.0, 5000.0: 0.0}

    rows = []
    for ceiling in ceilings_arg:
        bb_th = BB_THRESHOLD_BY_CEILING[ceiling]

        t0 = time.time()
        df_bb = run_propagated(pop, market_data, excluded_map, ceiling, seq, config,
                                bb_threshold=bb_th, use_any_rr=False, **common_kwargs)
        row = summarize(df_bb, f"bb_only (bb_th={bb_th:.0f})", ceiling, bb_th, False)
        rows.append(row)
        print(f"[bb_only  bb={bb_th:.0f} plafond={ceiling:.0f}$] profit_moy={row['profit_moyen']:+,.0f}$ "
              f"solde_neg={row['solde_negatif_annee4']:.2f}% hit_ceiling={row['hit_ceiling_pct']:.2f}% "
              f"annee1<0={row['annee1_neg']:.2f}% ({time.time()-t0:.0f}s)")

        t0 = time.time()
        df_rr = run_propagated(pop, market_data, excluded_map, ceiling, seq, config,
                                bb_threshold=float("inf"), use_any_rr=True, **common_kwargs)
        row = summarize(df_rr, "rr_only", ceiling, None, True)
        rows.append(row)
        print(f"[rr_only          plafond={ceiling:.0f}$] profit_moy={row['profit_moyen']:+,.0f}$ "
              f"solde_neg={row['solde_negatif_annee4']:.2f}% hit_ceiling={row['hit_ceiling_pct']:.2f}% "
              f"annee1<0={row['annee1_neg']:.2f}% ({time.time()-t0:.0f}s)")

        pd.DataFrame(rows).to_csv(f"chantier_cascade_combined_decomposition_n{n_sims}_2026-08-16.csv", index=False)

    print(f"\nTermine en {time.time()-t_start:.0f}s.")
