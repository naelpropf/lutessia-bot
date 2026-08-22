"""chantier_tacheB_clustering_diagnostic_2026-08-23.py

Diagnostic instrumente (pas de raisonnement a priori) sur la cause du
clustering_4mo/6mo -> annee1<0%=0,00% uniforme sur les 4 plafonds
(chantier_tacheB_sequence_2026-08-23.py). 2 hypotheses testees separement :

  a. Nombre de tirages bootstrap effectifs par simulation : mesure directe
     (pas calcul theorique) du nombre de blocs piocher pour couvrir la duree
     totale, aux 3 granularites (2/4/6 mois), sur plusieurs simulations.
  b. Compensation naturelle : les blocs 4/6 mois sont des UNIONS EXACTES de
     blocs 2 mois consecutifs (4mo = 2x2mo, 6mo = 3x2mo, meme origine
     temporelle t=0) -- decompose chaque bloc 4/6 mois en ses sous-blocs
     2 mois constitutifs, compare l'EV du bloc entier a l'EV de son PIRE
     sous-segment pour mesurer la compensation.
"""
import importlib.util
import random

import numpy as np
import pandas as pd

_spec = importlib.util.spec_from_file_location("pdb", "point_d_bloc1_bloc2_2026-08-22.py")
pdb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pdb)
bsl = pdb.bsl
s18 = bsl.s18

from real_cash_risk_year1_block_bootstrap import build_blocks
from reference_metrics_final import build_full_block_bootstrap_sequence

DAY_SECONDS = 86400
BLOCK_2MO = 2 * 30 * DAY_SECONDS
BLOCK_4MO = 4 * 30 * DAY_SECONDS
BLOCK_6MO = 6 * 30 * DAY_SECONDS


def block_ev_table(true_trades, true_slots, block_seconds):
    blocks = build_blocks(true_trades, true_slots, block_seconds)
    rows = []
    for i, blk in enumerate(blocks):
        if len(blk) == 0:
            rows.append(dict(idx=i, n=0, ev=float("nan"), wr=float("nan")))
            continue
        outcomes = [t["outcome_r"] for t, off in blk]
        ev = sum(outcomes) / len(outcomes)
        wr = sum(1 for o in outcomes if o > 0) / len(outcomes)
        rows.append(dict(idx=i, n=len(outcomes), ev=ev, wr=wr))
    return pd.DataFrame(rows)


def main():
    pop, market_data, excluded_map, alpha_post, beta_post, label = pdb.load_scenario_pgp()
    print(f"Population : {label}, n={len(pop)}", flush=True)

    true_trades, true_slots = s18.build_flexible_population_with_rr(pop, None, 1.0, False, random.Random(0))
    full_duration = true_slots[-1]
    print(f"[verif] duree totale pop (target_duration pour toute trajectoire) = {full_duration/DAY_SECONDS:.1f} jours", flush=True)

    # ---- Hypothese A : nombre de tirages bootstrap effectifs mesure directement ----
    print(f"\n{'='*90}\nHYPOTHESE A -- nombre de tirages bootstrap effectifs par simulation\n{'='*90}", flush=True)
    for name, bsec in [("2 mois (REF)", BLOCK_2MO), ("4 mois", BLOCK_4MO), ("6 mois", BLOCK_6MO)]:
        blocks = build_blocks(true_trades, true_slots, bsec)
        n_pool = len(blocks)
        n_pool_nonempty = sum(1 for b in blocks if len(b) > 0)
        draw_counts = []
        rng = random.Random(777)
        for _ in range(30):
            cursor = 0.0
            n_draws = 0
            while cursor < full_duration:
                rng.randrange(n_pool)  # meme consommation rng que build_full_block_bootstrap_sequence
                n_draws += 1
                cursor += bsec
            draw_counts.append(n_draws)
        print(f"  {name:14s} : pool={n_pool} blocs ({n_pool_nonempty} non-vides), "
              f"tirages/simulation mesures sur 30 runs = {draw_counts[0]} "
              f"(min={min(draw_counts)}, max={max(draw_counts)}, constant={len(set(draw_counts))==1})", flush=True)

    # ---- Hypothese B : compensation naturelle (decomposition en sous-blocs 2 mois) ----
    print(f"\n{'='*90}\nHYPOTHESE B -- compensation naturelle (decomposition en sous-blocs 2 mois)\n{'='*90}", flush=True)
    ev2 = block_ev_table(true_trades, true_slots, BLOCK_2MO)
    print(f"[reference] distribution EV blocs 2 mois (n={len(ev2)}, non-vides={ev2['ev'].notna().sum()}) : "
          f"min={ev2['ev'].min():+.3f}R P10={ev2['ev'].quantile(0.10):+.3f}R median={ev2['ev'].median():+.3f}R "
          f"P90={ev2['ev'].quantile(0.90):+.3f}R max={ev2['ev'].max():+.3f}R", flush=True)

    for name, bsec, ratio in [("4 mois", BLOCK_4MO, 2), ("6 mois", BLOCK_6MO, 3)]:
        evN = block_ev_table(true_trades, true_slots, bsec)
        print(f"\n  --- Blocs {name} (n={len(evN)}, non-vides={evN['ev'].notna().sum()}) ---", flush=True)
        print(f"  distribution EV bloc entier : min={evN['ev'].min():+.3f}R P10={evN['ev'].quantile(0.10):+.3f}R "
              f"median={evN['ev'].median():+.3f}R P90={evN['ev'].quantile(0.90):+.3f}R max={evN['ev'].max():+.3f}R", flush=True)

        n_compensated = 0
        n_valid = 0
        details = []
        for _, row in evN.iterrows():
            if row["n"] == 0:
                continue
            idx = int(row["idx"])
            sub_idx = list(range(idx * ratio, idx * ratio + ratio))
            sub_evs = [ev2.loc[ev2["idx"] == si, "ev"].values[0] for si in sub_idx if si in ev2["idx"].values]
            sub_evs = [e for e in sub_evs if not np.isnan(e)]
            if not sub_evs:
                continue
            n_valid += 1
            worst_sub = min(sub_evs)
            whole = row["ev"]
            is_compensated = whole > worst_sub + 0.05  # marge non-triviale
            if is_compensated:
                n_compensated += 1
            details.append((idx, worst_sub, whole, is_compensated))

        print(f"  blocs {name} dont l'EV entiere > EV du PIRE sous-segment (compensation) : "
              f"{n_compensated}/{n_valid} ({100*n_compensated/n_valid:.1f}%)", flush=True)
        worst5 = sorted(details, key=lambda x: x[1])[:5]
        print(f"  5 pires sous-segments (idx_bloc, EV_pire_sous_bloc, EV_bloc_entier, compense?) :", flush=True)
        for idx, worst_sub, whole, comp in worst5:
            print(f"    bloc {name} #{idx} : pire_sous_bloc_EV={worst_sub:+.3f}R, bloc_entier_EV={whole:+.3f}R, "
                  f"compense={comp}", flush=True)


if __name__ == "__main__":
    main()
