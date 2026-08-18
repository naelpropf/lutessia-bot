"""
Calibration dediee 2026-08-16 : seuil de bascule Blueberry Instant a 1000$
et 3000$, avec any-RR ACTIF (contrairement a chantier_blueberry_switch_2026-
08-15.py qui testait le seuil SEUL, compte isole du mecanisme any-RR). Le
seuil actuellement utilise dans la cascade groupee (S1.8) pour ces deux
plafonds est EXTRAPOLE par proximite de regime (1000$->5000$ comme 960$,
3000$->0$ comme 5000$), PAS mesure isolement a ces plafonds precis -- ce
chantier verifie si une calibration dediee change la conclusion. Meme
methode que chantier_blueberry_switch_2026-08-15.py (grille de 5 seuils +
reference 100% classique), mais dans le moteur COMBINE (any-RR toujours
actif, coherent avec le scenario d'adoption reel).
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
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    ceilings_arg = [float(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [1000.0, 3000.0]
    thresholds_arg = ([float(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3
                       else [0.0, 5000.0, 15000.0, 30000.0, 50000.0])

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

    rows = []
    for ceiling in ceilings_arg:
        for bb_threshold in [float("inf")] + thresholds_arg:
            t0 = time.time()
            df = run_propagated(pop, market_data, excluded_map, ceiling, seq, config,
                                 bb_threshold=bb_threshold, use_any_rr=True, **common_kwargs)
            label = "any-RR_100pct_classique" if bb_threshold == float("inf") else f"any-RR_bb_threshold_{bb_threshold:.0f}"
            row = summarize(df, label, ceiling, bb_threshold, True)
            rows.append(row)
            print(f"[plafond={ceiling:.0f}$ {label:28s}] profit_moy={row['profit_moyen']:+,.0f}$ "
                  f"profit_med={row['profit_median']:+,.0f}$ "
                  f"solde_neg={row['solde_negatif_annee4']:.2f}% "
                  f"hit_ceiling={row['hit_ceiling_pct']:.2f}% "
                  f"annee1<0={row['annee1_neg']:.2f}% "
                  f"bb_instant={row['bb_instant_opens_moy']:.2f} bb_classic={row['bb_classic_opens_moy']:.2f} "
                  f"({time.time()-t0:.0f}s)")
            pd.DataFrame(rows).to_csv(f"chantier_cascade_combined_bb_threshold_calibration_n{n_sims}_2026-08-16.csv", index=False)

    print(f"\nTermine en {time.time()-t_start:.0f}s.")
