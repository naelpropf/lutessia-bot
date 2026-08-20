"""
Point 3 -- stress-test H1/H2+4 blocs k-fold du re-test staggered unlock
(echelonne 1000/15000/25000/25000$ vs groupe seuil unique 30000$), meme
protocole que Points 1/§2.35/§2.41-42 : population REF (631, forex-only)
decoupee en sous-periodes chronologiques, n=100, 2 plafonds representatifs
(960=regime bb_threshold 5000, 3000=regime bb_threshold 0).

Reutilise chantier_p3_staggered_retest_2026-08-19.py via importlib.

N'importe pas ce script directement (convention du projet).
"""
import importlib.util
import sys
import time

import numpy as np
import pandas as pd

P3_SCRIPT = "chantier_p3_staggered_retest_2026-08-19.py"

spec = importlib.util.spec_from_file_location("p3_stress", P3_SCRIPT)
p3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p3)

if __name__ == "__main__":
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 100

    t_start = time.time()
    pop, market_data, excluded_map = p3.load_common_forex_only()
    pop_sorted = pop.sort_values("date_creation").reset_index(drop=True)
    mid = len(pop_sorted) // 2
    subperiods = {"H1": pop_sorted.iloc[:mid], "H2": pop_sorted.iloc[mid:]}
    for i, b in enumerate(np.array_split(pop_sorted, 4)):
        subperiods[f"bloc{i}"] = b
    print(f"[verif] population REF (forex-only) n={len(pop_sorted)} -- sous-periodes : "
          + ", ".join(f"{k}={len(v)}" for k, v in subperiods.items()))

    seq_staggered = p3.ref.ei.seq_grouped_multi(1000, 15000, 25000, 25000)
    seq_groupe = p3.ref.ei.seq_grouped_multi(30000, 30000, 30000, 30000)
    CEILINGS_TESTED = [960.0, 3000.0]

    rows = []
    for ceiling in CEILINGS_TESTED:
        print(f"\n{'='*70}\nplafond={ceiling:.0f}$\n{'='*70}")
        for sp_name, sp_pop in subperiods.items():
            if len(sp_pop) < 5:
                print(f"  [{sp_name}] n={len(sp_pop)} insuffisant -- ininterpretable")
                continue
            tickers = sorted(sp_pop["ticker"].unique())
            excluded_map_sp = p3.ref.precompute_correlation_pairs(
                tickers, pd.read_csv("correlation_matrix.csv", index_col=0), p3.ref.CORR_TH_NEW)
            t0 = time.time()
            df_stag = p3.run_variant(sp_pop, market_data, excluded_map_sp, n_sims, [ceiling], seq_staggered,
                                      f"echelonne_{sp_name}")
            df_grp = p3.run_variant(sp_pop, market_data, excluded_map_sp, n_sims, [ceiling], seq_groupe,
                                     f"groupe_{sp_name}")
            r, g = df_stag.iloc[0], df_grp.iloc[0]
            d_profit_pct = (r["profit_moyen"] - g["profit_moyen"]) / abs(g["profit_moyen"]) * 100 \
                if g["profit_moyen"] != 0 else float("nan")
            d_a1 = r["annee1_neg"] - g["annee1_neg"]
            better = r["profit_moyen"] > g["profit_moyen"]
            flag = "OK (echelonne > groupe)" if better else "INVERSION (echelonne <= groupe)"
            print(f"  [{sp_name}] n={len(sp_pop)} groupe profit={g['profit_moyen']:+,.0f}$ "
                  f"annee1<0={g['annee1_neg']:.1f}% | echelonne profit={r['profit_moyen']:+,.0f}$ "
                  f"({d_profit_pct:+.1f}%) annee1<0={r['annee1_neg']:.1f}% (delta={d_a1:+.1f}pt) -- "
                  f"{flag} ({time.time()-t0:.0f}s)")
            rows.append(dict(ceiling=ceiling, subperiod=sp_name, n_trades=len(sp_pop),
                              profit_groupe=g["profit_moyen"], profit_echelonne=r["profit_moyen"],
                              d_profit_pct=d_profit_pct, annee1_neg_groupe=g["annee1_neg"],
                              annee1_neg_echelonne=r["annee1_neg"], d_annee1=d_a1, inversion=not better))
            pd.DataFrame(rows).to_csv("chantier_p3_staggered_stresstest_2026-08-19.csv", index=False)

    print(f"\nTermine en {time.time()-t_start:.0f}s.")
