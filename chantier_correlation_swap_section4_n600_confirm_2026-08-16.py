"""
Confirmation n=600 (convention du projet) du variant "any-RR" (echange cible
correlation, critere RR planifie du signal) vs REF -- "any-RR-hybrid" est
omis ici car identique a "any-RR" a n=300 (egalites exactes de RR quasi
inexistantes, cf. chantier_correlation_swap_section4_rr_2026-08-16.py).
Cascade check complet (4 axes) aux 2 plafonds standard.
"""
import time
import importlib.util
import pandas as pd

_spec = importlib.util.spec_from_file_location("chantier_correlation_swap_main", "chantier_correlation_swap_2026-08-16.py")
_main = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_main)
load_pop, load_excluded_map = _main.load_pop, _main.load_excluded_map
run_propagated, summarize = _main.run_propagated, _main.summarize
EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK = _main.EVAL_RISK, _main.FLEET_RISK, _main.GFT_EVAL_RISK

import robustness_5ers_risk_challenge as eng
import etape_e_fleet_integration as ei

if __name__ == "__main__":
    import sys
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 600

    t_start = time.time()
    pop = load_pop()
    excluded_map = load_excluded_map(pop)

    market_data = eng.load_market_data()
    seq = ei.seq_grouped_multi(1000, 15000, 25000, 25000)
    config = ei.CONFIG_REF

    common_kwargs = dict(emergency=ei.DEFAULT_EMERGENCY, eval_risk=EVAL_RISK, fleet_risk=FLEET_RISK,
                          gft_eval_risk=GFT_EVAL_RISK, reserve_share=ei.FINAL_RESERVE_SHARE,
                          extra_threshold_mult=ei.EXTRA_THRESHOLD_MULT, n_sims=n_sims, seed=9999,
                          b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True,
                          ftmo_discount=True, gft_goat_guard=True, payout_cycle=True)

    all_rows = []
    for ceiling in (1000.0, 3000.0):
        t0 = time.time()
        df_ref = run_propagated(pop, market_data, excluded_map, ceiling, seq, config, position_mode="baseline",
                                 **common_kwargs)
        row = summarize(df_ref, "REF", ceiling)
        all_rows.append(row)
        print(f"[REF     plafond={ceiling:.0f}$ n={n_sims}] profit_moy={row['profit_moyen']:+,.0f}$ "
              f"profit_med={row['profit_median']:+,.0f}$ solde_neg={row['solde_negatif_annee4']:.2f}% "
              f"hit_ceiling={row['hit_ceiling_pct']:.2f}% annee1<0={row['annee1_neg']:.2f}% ({time.time()-t0:.0f}s)")

        t0 = time.time()
        df_rr = run_propagated(pop, market_data, excluded_map, ceiling, seq, config, position_mode="corr_swap_rr",
                                swap_variant="rr", **common_kwargs)
        row = summarize(df_rr, "any-RR", ceiling)
        all_rows.append(row)
        print(f"[any-RR  plafond={ceiling:.0f}$ n={n_sims}] profit_moy={row['profit_moyen']:+,.0f}$ "
              f"profit_med={row['profit_median']:+,.0f}$ solde_neg={row['solde_negatif_annee4']:.2f}% "
              f"hit_ceiling={row['hit_ceiling_pct']:.2f}% annee1<0={row['annee1_neg']:.2f}% "
              f"admits_moy={row.get('corr_swap_admits_moy', float('nan')):.2f} ({time.time()-t0:.0f}s)")

    pd.DataFrame(all_rows).to_csv(f"chantier_correlation_swap_section4_n{n_sims}_confirm_2026-08-16.csv", index=False)
    print(f"\nTermine en {time.time()-t_start:.0f}s.")
