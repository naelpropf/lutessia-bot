"""
Section A - Etape 0 (2026-08-17) : diagnostic fin EV/winrate par decile de
rr_tp2 ET rr_tp1, sur l'ensemble de la distribution (pas seulement au-dessus
du seuil 8 deja adopte en S2.35). Objectif : voir si la relation RR/EV est
monotone sur toute la plage ou si elle n'est portee que par la queue haute
deja connue (auquel cas une fonction continue/paliers sur toute la plage
n'apporterait rien de plus que le seuil simple deja adopte).

Meme construction de population que chantier_rrtp2_sizing_2026-08-16.py
(MIN_RR_NEW=1.35, "fixed" trailing 0.15) pour rester comparable.
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


def decile_table(pop, col, global_ev, global_ci):
    print(f"\n=== Deciles sur {col} (n={len(pop)}) ===")
    print(f"EV globale = {global_ev:+.3f}R  (IC95% bootstrap = [{global_ci[0]:+.3f},{global_ci[1]:+.3f}])")
    try:
        pop["_decile"] = pd.qcut(pop[col], 10, duplicates="drop")
    except ValueError as e:
        print(f"[!!!] qcut a echoue ({e}) -- trop de valeurs dupliquees pour 10 tranches distinctes")
        return
    rows = []
    for bucket, sub in pop.groupby("_decile", observed=True):
        n = len(sub)
        ev = sub["r_trailing"].mean()
        wr = (sub["r_trailing"] > 0).mean() * 100
        flag = "  <-- n PETIT, peu interpretable" if n < 30 else ""
        rows.append((str(bucket), n, ev, wr))
        print(f"  {str(bucket):>22s}  n={n:4d}  EV={ev:+.3f}R  winrate={wr:5.1f}%{flag}")
    evs = [r[2] for r in rows]
    monotone_inc = all(evs[i] <= evs[i + 1] for i in range(len(evs) - 1))
    print(f"  Monotone croissant strict sur les {len(evs)} tranches : {monotone_inc}")
    # Pearson global + Spearman
    pear = pop[col].corr(pop["r_trailing"])
    spear = pop[col].corr(pop["r_trailing"], method="spearman")
    print(f"  Pearson({col}, r_trailing) = {pear:+.3f}   Spearman = {spear:+.3f}")
    return rows


if __name__ == "__main__":
    pop = build_population_with_trailing("fixed", 0.15, min_rr=MIN_RR_NEW, verbose=False)
    print(f"[verif] population (RR>={MIN_RR_NEW}) : {len(pop)} trades")
    print(f"[verif] colonnes rr_tp1 range=[{pop['rr_tp1'].min():.2f},{pop['rr_tp1'].max():.2f}] "
          f"rr_tp2 range=[{pop['rr_tp2'].min():.2f},{pop['rr_tp2'].max():.2f}]")

    global_ev = pop["r_trailing"].mean()
    global_ci = bootstrap_ci(pop["r_trailing"])

    decile_table(pop.copy(), "rr_tp2", global_ev, global_ci)
    decile_table(pop.copy(), "rr_tp1", global_ev, global_ci)

    # Winrate par decile compare a EV -- verifier si l'effet de queue rr_tp2>8
    # (deja adopte S2.35) domine, ou si un signal existe aussi dans le corps
    # de la distribution (deciles 4-8 par ex.)
    print("\n=== Verification cible : effet concentre en queue ou distribue ? ===")
    for col in ("rr_tp2", "rr_tp1"):
        sub_tail = pop[pop[col] > 8]
        sub_mid = pop[(pop[col] >= pop[col].quantile(0.3)) & (pop[col] <= pop[col].quantile(0.7))]
        sub_low = pop[pop[col] <= pop[col].quantile(0.3)]
        print(f"  {col}: bas(<=P30) EV={sub_low['r_trailing'].mean():+.3f}R n={len(sub_low)} | "
              f"milieu(P30-P70) EV={sub_mid['r_trailing'].mean():+.3f}R n={len(sub_mid)} | "
              f"queue(>8) EV={sub_tail['r_trailing'].mean():+.3f}R n={len(sub_tail)}")
