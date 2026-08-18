"""
Confirmation n=600 (convention du projet) du variant "any" (echange cible
correlation, ecart de quartile quelconque favorable) vs REF -- seul variant
retenu de la Section 2 du chantier principal (extreme = no-op, gap2 = bruit).
Cascade check complet (4 axes) aux 2 plafonds standard.
"""
import time
import importlib.util
import pandas as pd

_spec = importlib.util.spec_from_file_location("chantier_correlation_swap_main", "chantier_correlation_swap_2026-08-16.py")
_main = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_main)
load_pop, load_excluded_map, section1_ranking = _main.load_pop, _main.load_excluded_map, _main.section1_ranking
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
    full_rank, rank_h1, by_q = section1_ranking(pop)
    quartile_full = full_rank["quartile"].to_dict()

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
        print(f"[REF          plafond={ceiling:.0f}$ n={n_sims}] profit_moy={row['profit_moyen']:+,.0f}$ "
              f"profit_med={row['profit_median']:+,.0f}$ solde_neg={row['solde_negatif_annee4']:.2f}% "
              f"hit_ceiling={row['hit_ceiling_pct']:.2f}% annee1<0={row['annee1_neg']:.2f}% ({time.time()-t0:.0f}s)")

        t0 = time.time()
        df_any = run_propagated(pop, market_data, excluded_map, ceiling, seq, config, position_mode="corr_swap",
                                 quartile_of=quartile_full, swap_variant="any", **common_kwargs)
        row = summarize(df_any, "any (classement complet)", ceiling)
        all_rows.append(row)
        print(f"[any          plafond={ceiling:.0f}$ n={n_sims}] profit_moy={row['profit_moyen']:+,.0f}$ "
              f"profit_med={row['profit_median']:+,.0f}$ solde_neg={row['solde_negatif_annee4']:.2f}% "
              f"hit_ceiling={row['hit_ceiling_pct']:.2f}% annee1<0={row['annee1_neg']:.2f}% "
              f"admits_moy={row.get('corr_swap_admits_moy', float('nan')):.2f} ({time.time()-t0:.0f}s)")

    pd.DataFrame(all_rows).to_csv(f"chantier_correlation_swap_n{n_sims}_confirm_2026-08-16.csv", index=False)
    print(f"\nTermine en {time.time()-t_start:.0f}s.")
