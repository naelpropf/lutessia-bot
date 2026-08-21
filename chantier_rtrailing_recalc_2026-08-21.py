"""chantier_rtrailing_recalc_2026-08-21.py

Regenere r_trailing via la source MT5 (deja branchee dans tp_sequence_
analysis.fetch_h1_history + garde-fou prospectif dans analyze_trade, cf.
project_rtrailing_bug_scope_validated_2026-08-21) pour les 3 configs
distinctes confirmees cette session :
  - "officielle_verrouillee" : rr_tp1>=1,5 (MIN_RR_TP1), trailing=0,2
    (config figee derriere le p=0,0027 cite au registre ET utilisee chaque
    semaine par analyse_live.py -- aucune intention explicite trouvee pour
    ce choix, vestige pre-scission A/B le plus probable).
  - "A_reelle" : rr_tp1>=1,35 (MIN_RR_NEW), trailing=0,15 (population
    reellement tradee par Strategie A, n=631 forex).
  - "B_reelle" : rr_tp1<1,35 (tout le spectre B, y compris la bande
    1,25-1,35 qui appartient reellement a B, pas a A), trailing=0,10.

Reutilise SANS reinvention : trailing_payoff_population.build_population_
with_trailing (deja la fonction officielle), qui appelle tp_sequence_
analysis.analyze_trade/fetch_h1_history en interne -- desormais MT5-aware
par construction, aucune nouvelle logique de simulation ecrite ici."""
import pandas as pd
import numpy as np

import trailing_payoff_population as tpp
import tp_sequence_analysis as tpseq

CONFIGS = {
    "officielle_verrouillee": dict(kind="fixed", param=0.2, min_rr=1.5),
    "A_reelle": dict(kind="fixed", param=0.15, min_rr=1.35),
}


def main():
    results = {}
    for name, cfg in CONFIGS.items():
        print(f"\n{'='*90}\nRegeneration : {name} (min_rr={cfg['min_rr']}, trailing={cfg['param']})\n{'='*90}", flush=True)
        pop = tpp.build_population_with_trailing(cfg["kind"], cfg["param"], min_rr=cfg["min_rr"], verbose=True)
        out_path = f"chantier_rtrailing_recalc_{name}_2026-08-21.csv"
        pop.to_csv(out_path, index=False)
        print(f"Sauvegarde : {out_path} ({len(pop)} trades)", flush=True)
        results[name] = pop

    print(f"\n{'='*90}\nRESUME comparatif\n{'='*90}")
    for name, pop in results.items():
        n = len(pop)
        n_incertain = (pop["case"] == "resolution_incertaine_horizon_insuffisant").sum() if "case" in pop else 0
        wins = pop[pop["statut_final"] == "OBJECTIF ATTEINT"]
        ev = pop["r_trailing"].mean() if "r_trailing" in pop else float("nan")
        print(f"  {name}: n={n} incertain_prospectif={n_incertain} EV_population={ev:+.4f}R "
              f"winrate={len(wins)/n*100:.2f}%")


if __name__ == "__main__":
    main()
