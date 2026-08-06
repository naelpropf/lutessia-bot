"""
Point 5 (06/08, 3e relance) : balayage croise des parametres de strategie.
Vu le nombre de combinaisons (4 RR x 4 trailing x 3 maxpos x 3 correlation =
144), methodologie a 2 etages (deja etablie dans ce projet, cf.
pyramid_level_sweep.py) :
  Etage A : tri RAPIDE sur l'EV BRUTE en R (RR x trailing, 16 combos, pas de
  Monte Carlo/sizing $) -- identifie les combinaisons prometteuses.
  Etage B (script separe) : Monte Carlo flotte complet (2000 runs) sur la
  combinaison verrouillee actuelle + les meilleurs candidats de l'etage A +
  le balayage maxpos/correlation (pas besoin de re-simuler H1, ces 2
  parametres n'affectent que le filtrage flotte, pas la population de trades).
"""
import time

import numpy as np
import pandas as pd

from trailing_payoff_population import build_population_with_trailing

RR_LEVELS = [1.25, 1.5, 1.75, 2.0]
TRAILING_MULTS = [0.15, 0.2, 0.25, 0.3]


def main():
    t_start = time.time()
    rows = []
    for rr in RR_LEVELS:
        for mult in TRAILING_MULTS:
            t0 = time.time()
            pop = build_population_with_trailing("fixed", mult, min_rr=rr, verbose=False)
            outcome_r = np.where(pop["statut_final"] == "OBJECTIF ATTEINT", pop["r_trailing"], -1.0)
            n = len(pop)
            winrate = (pop["statut_final"] == "OBJECTIF ATTEINT").mean() * 100
            mean_r = outcome_r.mean()
            win_r = outcome_r[outcome_r > 0]
            avg_win_r = win_r.mean() if len(win_r) else float("nan")
            cum = np.cumsum(outcome_r)
            peak = np.maximum.accumulate(cum)
            max_dd_r = (peak - cum).max()
            row = dict(rr_threshold=rr, trailing_mult=mult, n_trades=n, winrate_pct=winrate,
                      mean_ev_r=mean_r, avg_win_r=avg_win_r, max_dd_r=max_dd_r,
                      total_r=outcome_r.sum())
            rows.append(row)
            print(f"  RR>={rr} trailing={mult}x : n={n} winrate={winrate:.1f}% EV={mean_r:+.4f}R "
                  f"avgWinR={avg_win_r:.3f} maxDD_R={max_dd_r:.1f} totalR={outcome_r.sum():.1f} ({time.time()-t0:.0f}s)")

    out = pd.DataFrame(rows).sort_values("mean_ev_r", ascending=False)
    out.to_csv("point5_stageA_ev_screen.csv", index=False)
    print("\nClassement par EV brute (R/trade), meilleur en premier :")
    print(out[["rr_threshold", "trailing_mult", "n_trades", "winrate_pct", "mean_ev_r", "total_r"]].to_string(index=False))
    print(f"\nTerminé en {time.time()-t_start:.0f}s.")


if __name__ == "__main__":
    main()
