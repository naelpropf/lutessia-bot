"""chantier_taskF_final_2026-08-23.py

TACHE F (session du 23/08) : recalcul final sur la reference COMPLETE et a
jour -- combine tous les resultats adoptes cette session :
- 5 leviers (V2, S1.8, S2.35, FTMO-10%/GoatGuard, payout) -- deja actifs
  par defaut dans chantier_taskD_sequential_BA_2026-08-23.py::run_n_sims.
- Risque optimal par cote (Tache C2) : A=1,25%/1,90%, B=1,50%/1,50%
  (RISK_BY_TID dans le moteur).
- Pivot optimal (Tache E) : Blueberry Instant Elite 2 500$ (100$) --
  meilleur profit ET risque a c=1000$, cf. chantier_taskE_pivot_2026-08-23.py.
- Sequence B->A (Tache D) : declenchement a 3000$, scenario "adapte_prudent"
  retenu comme reference centrale (degradation Fed ponctuelle uniquement,
  pas la strate de marge de securite -- celle-ci reste un stress-test, pas
  la reference centrale demandee).

Calcule : solde_negatif% PAR BLOC (4 sous-periodes calendaires communes
A/B, meme convention que date_subperiods du moteur), annee1<0%, profit
median/moyen annee 1, profit final a 4 ans -- compare au dernier chiffre
de reference officiel du registre (registre_strategie_trading.md §6.5,
lancement sequentiel 3000$, ancienne population Config0 pre-correction :
17,74M$-18,03M$ n=600).

Usage : python chantier_taskF_final_2026-08-23.py <n_sims> <ceilings_csv>
"""
import sys
import time
import importlib.util

import pandas as pd

_spec = importlib.util.spec_from_file_location("taskd", "chantier_taskD_sequential_BA_2026-08-23.py")
taskd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(taskd)

SEQUENTIAL_B_THRESHOLD = 3000.0
SHOCK_WINDOW = (pd.Timestamp("2023-10-07"), pd.Timestamp("2023-11-15"))  # israel_hamas
PIVOT_FMT_KEY = "Blueberry_InstantElite"
PIVOT_PALIER = 2500.0

REGISTRE_REF_LOW, REGISTRE_REF_HIGH = 17_740_000.0, 18_030_000.0  # sec 6.5, ancienne population


def run_full_config(pop_A, pop_B, market_data, excluded_map, metal_set, ceiling, n_sims, size_func, label,
                     apply_shock=True):
    forced_window = SHOCK_WINDOW if apply_shock else None
    df = taskd.run_n_sims(pop_A, pop_B, ceiling, n_sims, 9999, True, market_data, excluded_map, metal_set,
                           sequential_b_threshold=SEQUENTIAL_B_THRESHOLD, size_func=size_func,
                           forced_window_B=forced_window, pivot_fmt_key=PIVOT_FMT_KEY, pivot_palier=PIVOT_PALIER)
    net = df["combined_net"] - df["combined_is_paid"]
    year1_neg = df["combined_year1_net"] < 0
    row = dict(config=label, ceiling=ceiling, n=len(df),
               profit_moyen=net.mean(), profit_median=net.median(),
               profit_moyen_annee1=df["combined_year1_net"].mean(),
               profit_median_annee1=df["combined_year1_net"].median(),
               solde_negatif_annee4=(net < 0).mean() * 100,
               annee1_neg=year1_neg.mean() * 100)
    return row


def main():
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    ceilings = [float(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [1000.0, 3000.0]

    pop_A, _, _ = taskd.load_common_A()
    pop_B = taskd.build_pop_B()
    oa_all = pd.read_csv("chantier_gold_silver_pop_metaux_all_2026-08-19.csv")
    metal_set = set(oa_all["ticker"].unique())
    market_data, excluded_map = taskd.build_market_data_and_excluded_map(pop_A, pop_B)
    size_func = taskd.rr2.make_size_func_tail(1.6)
    print(f"[verif] pop_A={len(pop_A)} pop_B={len(pop_B)} pivot={PIVOT_FMT_KEY}@{PIVOT_PALIER:.0f}$ "
          f"seuil={SEQUENTIAL_B_THRESHOLD:.0f}$", flush=True)

    rows = []
    for ceiling in ceilings:
        t0 = time.time()
        row = run_full_config(pop_A, pop_B, market_data, excluded_map, metal_set, ceiling, n_sims, size_func,
                               f"FINAL_global_c{ceiling:.0f}")
        row["bloc"] = "global"
        dt = time.time() - t0
        print(f"[GLOBAL c={ceiling:.0f}$] profit_moy={row['profit_moyen']:+,.0f}$ profit_med={row['profit_median']:+,.0f}$ "
              f"profit_moy_an1={row['profit_moyen_annee1']:+,.0f}$ profit_med_an1={row['profit_median_annee1']:+,.0f}$ "
              f"solde_neg_an4={row['solde_negatif_annee4']:.2f}% annee1<0={row['annee1_neg']:.2f}% n={n_sims} ({dt:.0f}s)",
              flush=True)
        rows.append(row)
        pd.DataFrame(rows).to_csv(f"chantier_taskF_final_2026-08-23_n{n_sims}.csv", index=False)

        parts = taskd.date_subperiods(pop_A, pop_B, 4)
        for i, (sub_A, sub_B) in enumerate(parts):
            if len(sub_A) < 10 or len(sub_B) < 10:
                print(f"[bloc{i+1} c={ceiling:.0f}$] sous-population trop petite (A={len(sub_A)}, B={len(sub_B)}) -- ignore",
                      flush=True)
                continue
            t0 = time.time()
            row_b = run_full_config(sub_A, sub_B, market_data, excluded_map, metal_set, ceiling, n_sims, size_func,
                                     f"FINAL_bloc{i+1}_c{ceiling:.0f}", apply_shock=False)
            row_b["bloc"] = f"bloc{i+1}"
            row_b["n_trades_A"] = len(sub_A)
            row_b["n_trades_B"] = len(sub_B)
            dt = time.time() - t0
            print(f"[bloc{i+1} c={ceiling:.0f}$] profit_moy={row_b['profit_moyen']:+,.0f}$ "
                  f"solde_neg_an4={row_b['solde_negatif_annee4']:.2f}% annee1<0={row_b['annee1_neg']:.2f}% "
                  f"n_A={len(sub_A)} n_B={len(sub_B)} ({dt:.0f}s)", flush=True)
            rows.append(row_b)
            pd.DataFrame(rows).to_csv(f"chantier_taskF_final_2026-08-23_n{n_sims}.csv", index=False)

    print(f"\n[comparaison] reference officielle registre S6.5 (ancienne population, sequentiel 3000$) : "
          f"{REGISTRE_REF_LOW:,.0f}$-{REGISTRE_REF_HIGH:,.0f}$", flush=True)


if __name__ == "__main__":
    main()
