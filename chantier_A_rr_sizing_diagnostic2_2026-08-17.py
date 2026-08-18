"""
Section A (reouverture) + Section A-bis - Etape 0 (2026-08-17) : diagnostic
fin, granularite plus fine que le decile, pour repondre a 2 questions
distinctes :
1. (Section A, boost+downsizing permanent) Existe-t-il des segments rr_tp2
   a EV REELLEMENT NEGATIVE (pas juste sous la moyenne) ? A quelle
   granularite ?
2. (Section A-bis, downsizing temporel) Le(s) segment(s) les plus faibles
   en EV contribuent-ils de facon DISPROPORTIONNEE aux pertes (frequence
   ET magnitude), ou juste a un profit moyen plus bas ?

Meme population que chantier_A_rr_sizing_diagnostic_2026-08-17.py
(MIN_RR_NEW=1.35, "fixed" trailing 0.15, n=631).
"""
import numpy as np
import pandas as pd

from trailing_payoff_population import build_population_with_trailing

MIN_RR_NEW = 1.35


def bootstrap_ci(values, n_boot=5000, seed=9999):
    rng = np.random.default_rng(seed)
    arr = values.to_numpy()
    n = len(arr)
    means = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, n, n)
        means[i] = arr[idx].mean()
    return np.percentile(means, 2.5), np.percentile(means, 97.5)


if __name__ == "__main__":
    pop = build_population_with_trailing("fixed", 0.15, min_rr=MIN_RR_NEW, verbose=False)
    print(f"[verif] population (RR>={MIN_RR_NEW}) : {len(pop)} trades")

    global_ev = pop["r_trailing"].mean()
    print(f"EV globale = {global_ev:+.3f}R\n")

    # === Question 1 : granularite fine (20 tranches = ventiles) ===
    print("=" * 78)
    print("QUESTION 1 (Section A) : segments a EV REELLEMENT NEGATIVE, granularite fine")
    print("=" * 78)
    for n_bins, label in [(10, "deciles"), (20, "ventiles")]:
        pop2 = pop.copy()
        pop2["_bin"] = pd.qcut(pop2["rr_tp2"], n_bins, duplicates="drop")
        print(f"\n--- {label} (n_bins demande={n_bins}) ---")
        n_negative = 0
        n_below_mean = 0
        n_below_ci_low = 0
        ci_low, ci_high = bootstrap_ci(pop["r_trailing"])
        for bucket, sub in pop2.groupby("_bin", observed=True):
            n = len(sub)
            ev = sub["r_trailing"].mean()
            flag = ""
            if ev < 0:
                flag += " <-- EV NEGATIVE"
                n_negative += 1
            if ev < global_ev:
                n_below_mean += 1
            if ev < ci_low:
                flag += " <-- sous IC95%% bas"
                n_below_ci_low += 1
            small = " [n petit]" if n < 20 else ""
            print(f"  {str(bucket):>22s} n={n:3d} EV={ev:+.3f}R{flag}{small}")
        print(f"  => {n_negative}/{len(pop2['_bin'].cat.categories) if hasattr(pop2['_bin'],'cat') else '?'} tranches a EV NEGATIVE, "
              f"{n_below_mean} sous la moyenne globale, {n_below_ci_low} sous l'IC95%% bas ([{ci_low:+.3f},{ci_high:+.3f}])")

    # Tranches de largeur FIXE (pas seulement egal-effectif) pour eviter tout
    # artefact du decoupage par quantile
    print("\n--- Tranches largeur fixe (pas=1.0 sur rr_tp2) ---")
    edges = list(np.arange(1.0, pop["rr_tp2"].max() + 1.0, 1.0))
    pop["_fixedbin"] = pd.cut(pop["rr_tp2"], edges)
    for bucket, sub in pop.groupby("_fixedbin", observed=True):
        if len(sub) == 0:
            continue
        n = len(sub)
        ev = sub["r_trailing"].mean()
        flag = " <-- EV NEGATIVE" if ev < 0 else ""
        small = " [n petit]" if n < 20 else ""
        print(f"  {str(bucket):>18s} n={n:3d} EV={ev:+.3f}R{flag}{small}")

    # === Question 2 : contribution aux PERTES (frequence + magnitude) ===
    print("\n" + "=" * 78)
    print("QUESTION 2 (Section A-bis) : contribution des segments aux PERTES")
    print("=" * 78)
    losers = pop[pop["r_trailing"] < 0].copy()
    print(f"\n[verif] {len(losers)}/{len(pop)} trades perdants ({len(losers)/len(pop)*100:.1f}%), "
          f"perte moyenne={losers['r_trailing'].mean():+.3f}R perte max={losers['r_trailing'].min():+.3f}R")

    pop["_decile"] = pd.qcut(pop["rr_tp2"], 10, duplicates="drop")
    print(f"\n{'Decile rr_tp2':>20s} {'EV':>8s} {'n_pop':>6s} {'%pop':>6s} {'n_perdants':>10s} {'%pertes':>8s} "
          f"{'ratio':>6s} {'perte_moy':>10s} {'perte_max':>10s}")
    for bucket, sub in pop.groupby("_decile", observed=True):
        n_pop = len(sub)
        pct_pop = n_pop / len(pop) * 100
        sub_losers = sub[sub["r_trailing"] < 0]
        n_l = len(sub_losers)
        pct_losses = n_l / len(losers) * 100 if len(losers) else 0.0
        ratio = pct_losses / pct_pop if pct_pop > 0 else float("nan")
        loss_mean = sub_losers["r_trailing"].mean() if n_l else float("nan")
        loss_max = sub_losers["r_trailing"].min() if n_l else float("nan")
        ev = sub["r_trailing"].mean()
        print(f"{str(bucket):>20s} {ev:>+7.3f}R {n_pop:>6d} {pct_pop:>5.1f}% {n_l:>10d} {pct_losses:>7.1f}% "
              f"{ratio:>6.2f} {loss_mean:>+9.3f}R {loss_max:>+9.3f}R")

    print("\n[lecture] ratio=1.00 -> le decile contribue aux pertes exactement proportionnellement "
          "a son poids dans la population (pas de surrepresentation). ratio>1.2 -> surrepresentation "
          "notable. perte_moy plus negative -> pertes plus severes en magnitude sur ce decile.")
