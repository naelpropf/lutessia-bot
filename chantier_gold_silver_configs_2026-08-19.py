"""Etape 1 : construit les populations A et B pour les 3 configs de routage
des metaux (chantier routage A/B metaux, 2026-08-19).

Config 0 (baseline deja mesuree, chantier_gold_silver_fusion_b_2026-08-19.py) :
  100% metaux -> B, aucun split RR.
Config 1 (split RR, meme regle que forex/indices) :
  metal rr_tp1>=1.35 -> A, sinon -> B. Deterministe, pas de logique runtime.
Config 2 (overflow conditionnel) :
  metal -> B par defaut ; SI bloque-correlation dans B au moment de
  l'admission -> redirige vers A. Necessite une logique RUNTIME (pas
  determinable a la construction de la population) -- ce script construit
  la population B "candidate" complete (100% metaux, comme Config 0) et
  laisse le moteur de simulation gerer l'overflow trade-par-trade (cf.
  chantier_gold_silver_ab_engine_2026-08-19.py).
"""
import importlib.util

import pandas as pd

from trailing_payoff_population import build_population_with_trailing

_spec = importlib.util.spec_from_file_location("b6", "chantier_b6_montecarlo_2026-08-19.py")
b6 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(b6)

KEEP_COLS = ["date_creation", "ticker", "rr_tp1", "rr_tp2", "statut_final", "r_trailing", "resolution_time_est",
             "prix_entree", "stop_loss_init"]
MIN_RR_A = 1.35


def monthly_rate(pop):
    span_days = (pop["date_creation"].max() - pop["date_creation"].min()).days
    return len(pop) / (span_days / 30.44)


def report_side(label, pop):
    ev = pop["r_trailing"].mean()
    rr_moy = pop["rr_tp1"].mean()
    rate = monthly_rate(pop)
    print(f"  {label:20s} n={len(pop):5d}  RR_moy={rr_moy:.3f}  EV={ev:+.4f}R  rythme={rate:.2f}/mois")
    return dict(label=label, n=len(pop), rr_moy=rr_moy, ev=ev, rate=rate)


def main():
    print("Chargement A/B de base (sans metaux)...")
    pop_A0 = build_population_with_trailing("fixed", 0.15, min_rr=1.35, verbose=False)[KEEP_COLS]
    pop_B0 = b6.build_pop_B_variant(trailing_factor=0.10)[KEEP_COLS]
    rate_A0 = monthly_rate(pop_A0)

    oa = pd.read_csv("or_argent_population_trailing_2026-08-19.csv")
    oa["date_creation"] = pd.to_datetime(oa["date_creation"])
    oa["resolution_time_est"] = pd.to_datetime(oa["resolution_time_est"])
    oa = oa[KEEP_COLS]

    rows = []
    print(f"\n=== Baseline sans metaux (reference) ===")
    rows.append(report_side("A (sans metaux)", pop_A0))
    rows.append(report_side("B (sans metaux)", pop_B0))

    print(f"\n=== Config 0 : 100% metaux -> B (deja mesure) ===")
    pop_B_c0 = pd.concat([pop_B0, oa], ignore_index=True).sort_values("date_creation").reset_index(drop=True)
    rows.append(report_side("A (Config 0, = A0)", pop_A0))
    rows.append(report_side("B (Config 0)", pop_B_c0))
    print(f"  Ratio B/A rythme = {monthly_rate(pop_B_c0)/rate_A0*100:.1f}%")

    print(f"\n=== Config 1 : split RR (metal rr_tp1>={MIN_RR_A} -> A, sinon -> B) ===")
    oa_to_A = oa[oa["rr_tp1"] >= MIN_RR_A]
    oa_to_B = oa[oa["rr_tp1"] < MIN_RR_A]
    pop_A_c1 = pd.concat([pop_A0, oa_to_A], ignore_index=True).sort_values("date_creation").reset_index(drop=True)
    pop_B_c1 = pd.concat([pop_B0, oa_to_B], ignore_index=True).sort_values("date_creation").reset_index(drop=True)
    rows.append(report_side("A (Config 1)", pop_A_c1))
    rows.append(report_side("B (Config 1)", pop_B_c1))
    print(f"  Metaux -> A : {len(oa_to_A)} | Metaux -> B : {len(oa_to_B)}")
    print(f"  Ratio B/A rythme = {monthly_rate(pop_B_c1)/monthly_rate(pop_A_c1)*100:.1f}%")

    print(f"\n=== Config 2 : overflow conditionnel (runtime, apercu structurel ici) ===")
    print(f"  Population B 'candidate' = identique a Config 0 (100% metaux, {len(pop_B_c0)} trades),")
    print(f"  A 'candidate' = A seul + metaux qui SERAIENT overflow (non determinable hors simulation).")
    print(f"  Composition finale reelle -> sortie du moteur de simulation (Etape 3).")

    pop_A_c1.to_csv("chantier_gold_silver_pop_A_config1_2026-08-19.csv", index=False)
    pop_B_c1.to_csv("chantier_gold_silver_pop_B_config1_2026-08-19.csv", index=False)
    pop_B_c0.to_csv("chantier_gold_silver_pop_B_config0_2026-08-19.csv", index=False)
    pop_A0.to_csv("chantier_gold_silver_pop_A_config0_2026-08-19.csv", index=False)
    oa.to_csv("chantier_gold_silver_pop_metaux_all_2026-08-19.csv", index=False)

    pd.DataFrame(rows).to_csv("chantier_gold_silver_configs_composition_2026-08-19.csv", index=False)
    print("\nSauvegarde : chantier_gold_silver_pop_{A,B}_config{0,1}_2026-08-19.csv, "
          "chantier_gold_silver_pop_metaux_all_2026-08-19.csv, "
          "chantier_gold_silver_configs_composition_2026-08-19.csv")


if __name__ == "__main__":
    main()
