import importlib.util
import pandas as pd

_spec = importlib.util.spec_from_file_location("adxfx", "chantier_adx_fx_only_B_tradable_2026-08-20.py")
adxfx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(adxfx)

abm = adxfx.abm
pop_B_tradable = adxfx.load_pop_B_tradable()
oa_all = pd.read_csv(adxfx.POP_METAUX_ALL_CSV)
metal_set = set(oa_all["ticker"].unique())

abm.build_pop_B = lambda: pop_B_tradable
pop_A, _, _ = abm.load_common_A()
pop_B = abm.build_pop_B()
market_data, excluded_map = abm.build_market_data_and_excluded_map(pop_A, pop_B)
parts = abm.date_subperiods(pop_A, pop_B, 4)
sub_A2, sub_B2 = parts[1]
print(f"bloc2 : n_trades_A={len(sub_A2)} n_trades_B={len(sub_B2)}", flush=True)

for label, (alpha, beta) in [("PRIOR BASELINE (533,520) 50.62%", (533,520)),
                              ("PRIOR ADX-improved (515,483) 51.61%", (515,483))]:
    abm.ALPHA_POST_B_METAUX = alpha
    abm.BETA_POST_B_METAUX = beta
    for ceiling in (3000.0, 5000.0):
        df = abm.run_n_sims(sub_A2, sub_B2, ceiling, 600, 9999, True, market_data, excluded_map, metal_set,
                             sequential_b_threshold=adxfx.SEQUENTIAL_THRESHOLD)
        row = abm.summarize_df(df, "bloc2", ceiling)
        print(f"  [{label} c={ceiling:.0f}$] annee1<0={row['annee1_neg']:.2f}% profit_moy={row['profit_moyen']:+,.0f}$", flush=True)
