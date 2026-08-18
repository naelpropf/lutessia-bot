"""
Verification finale 2026-08-16 (S2.35, registre_strategie_trading.md) : avant
adoption definitive, reproduit proprement et documente exactement (a) la table
complete rr_tp2 (cumulative + tranches non-chevauchantes), (b) le stress-test
de stabilite temporelle (H1/H2 + k-fold 4 blocs, meme standard que S1/S3 pour
le classement de paires), avec une metrique de correlation par fold (Pearson,
equivalent au Spearman utilise pour le classement de paires -- ici la relation
testee est continue [rr_tp2 vs r_trailing], pas un classement de categories,
Pearson est la mesure directe de cette relation).
"""
import numpy as np
import pandas as pd
from trailing_payoff_population import build_population_with_trailing

MIN_RR = 1.35


def boot_ci(arr, seed=9999, n_iter=5000):
    rng = np.random.default_rng(seed)
    boot = np.array([rng.choice(arr, size=len(arr), replace=True).mean() for _ in range(n_iter)])
    return np.percentile(boot, [2.5, 97.5])


def main():
    pop = build_population_with_trailing("fixed", 0.15, min_rr=MIN_RR, verbose=False)
    pop = pop.sort_values("date_creation").reset_index(drop=True)
    global_ev = pop["r_trailing"].mean()
    n_total = len(pop)
    print(f"Population : n={n_total}, EV globale = {global_ev:+.4f}R")

    print("\n" + "=" * 72)
    print("POINT 3 -- table complete rr_tp2 (etapes 1-2)")
    print("=" * 72)

    print("\n--- Seuils cumulatifs (rr_tp2>=X) ---")
    rows_cum = []
    for th in (3, 4, 5, 6, 8, 10):
        sub = pop[pop["rr_tp2"] >= th]
        n = len(sub)
        ev = sub["r_trailing"].mean()
        wr = (sub["r_trailing"] > 0).mean()
        ci = boot_ci(sub["r_trailing"].to_numpy()) if n >= 10 else (np.nan, np.nan)
        out = not (ci[0] <= global_ev <= ci[1]) if n >= 10 else None
        rows_cum.append(dict(seuil=f">={th}", n=n, ev=ev, winrate=wr * 100, ci_lo=ci[0], ci_hi=ci[1], hors_ic=out))
    df_cum = pd.DataFrame(rows_cum)
    print(df_cum.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print("\n--- Tranches non-chevauchantes (couvre TOUTE la population) ---")
    bins = [pop["rr_tp2"].min() - 0.01, 3, 4, 5, 6, 8, pop["rr_tp2"].max() + 0.01]
    rows_bins = []
    for name, sub in pop.groupby(pd.cut(pop["rr_tp2"], bins=bins)):
        n = len(sub)
        if n == 0:
            continue
        ev = sub["r_trailing"].mean()
        wr = (sub["r_trailing"] > 0).mean()
        ci = boot_ci(sub["r_trailing"].to_numpy()) if n >= 10 else (np.nan, np.nan)
        out = not (ci[0] <= global_ev <= ci[1]) if n >= 10 else None
        flag = "" if n >= 20 else " /!\\ n<20"
        rows_bins.append(dict(tranche=str(name), n=n, ev=ev, winrate=wr * 100, ci_lo=ci[0], ci_hi=ci[1],
                               hors_ic_globale=out, flag=flag))
    df_bins = pd.DataFrame(rows_bins)
    print(df_bins.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print(f"\nSomme des n par tranche = {df_bins['n'].sum()} (doit = {n_total})")

    print("\n" + "=" * 72)
    print("POINT 2 -- stress-test de stabilite temporelle (methode : split H1/H2")
    print("PUIS k-fold temporel 4 blocs, meme standard que S1/S3 classement paires)")
    print("=" * 72)

    print("\n--- Split H1/H2 (2 sous-periodes) ---")
    mid = n_total // 2
    h1, h2 = pop.iloc[:mid], pop.iloc[mid:]
    rows_h = []
    for label, half in (("H1", h1), ("H2", h2)):
        ev_half = half["r_trailing"].mean()
        tail = half[half["rr_tp2"] > 8]
        rest = half[half["rr_tp2"] <= 8]
        pear = half["rr_tp2"].corr(half["r_trailing"])
        spear = half["rr_tp2"].corr(half["r_trailing"], method="spearman")
        rows_h.append(dict(periode=label, n=len(half), date_min=str(half["date_creation"].min()),
                            date_max=str(half["date_creation"].max()), ev_periode=ev_half,
                            n_tail=len(tail), ev_tail=tail["r_trailing"].mean(),
                            ev_rest=rest["r_trailing"].mean(), pearson=pear, spearman=spear,
                            tail_au_dessus=tail["r_trailing"].mean() > rest["r_trailing"].mean()))
    df_h = pd.DataFrame(rows_h)
    print(df_h.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print("\n--- K-fold temporel (4 blocs chronologiques successifs) ---")
    bounds = np.linspace(0, n_total, 5).astype(int)
    rows_k = []
    for i in range(4):
        block = pop.iloc[bounds[i]:bounds[i + 1]]
        tail = block[block["rr_tp2"] > 8]
        rest = block[block["rr_tp2"] <= 8]
        pear = block["rr_tp2"].corr(block["r_trailing"])
        spear = block["rr_tp2"].corr(block["r_trailing"], method="spearman")
        rows_k.append(dict(bloc=i, n=len(block), ev_bloc=block["r_trailing"].mean(),
                            n_tail=len(tail), ev_tail=tail["r_trailing"].mean() if len(tail) else np.nan,
                            ev_rest=rest["r_trailing"].mean(), pearson=pear, spearman=spear,
                            tail_au_dessus=(tail["r_trailing"].mean() > rest["r_trailing"].mean()) if len(tail) else None))
    df_k = pd.DataFrame(rows_k)
    print(df_k.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print(f"\nPearson moyen (4 blocs) = {df_k['pearson'].mean():+.4f}")
    print(f"Spearman moyen (4 blocs) = {df_k['spearman'].mean():+.4f}")
    print(f"Nb blocs ou tail_au_dessus=True : {df_k['tail_au_dessus'].sum()}/4")
    print(f"Nb sous-periodes H1/H2 ou tail_au_dessus=True : {df_h['tail_au_dessus'].sum()}/2")

    print("\n" + "=" * 72)
    print("VERDICT STABILITE")
    print("=" * 72)
    all_positive_pearson = (df_k["pearson"] > 0).all() and (df_h["pearson"] > 0).all()
    all_tail_above = (df_k["tail_au_dessus"] == True).all() and (df_h["tail_au_dessus"] == True).all()
    print(f"Pearson positif dans TOUTES les sous-periodes (H1,H2,4 blocs) : {all_positive_pearson}")
    print(f"EV(queue rr_tp2>8) > EV(reste) dans TOUTES les sous-periodes : {all_tail_above}")
    if all_positive_pearson and all_tail_above:
        print("-> STABLE : direction constante sur les 6 sous-periodes independantes testees "
              "(2 moities + 4 blocs). Contraste avec le classement de paires (S1), dont la "
              "direction s'inversait en H2.")
    else:
        print("-> INSTABLE : au moins une sous-periode contredit la direction globale, a traiter "
              "avec la meme prudence que le classement de paires.")

    df_cum.to_csv("chantier_rrtp2_stability_cumulatif_2026-08-16.csv", index=False)
    df_bins.to_csv("chantier_rrtp2_stability_tranches_2026-08-16.csv", index=False)
    df_h.to_csv("chantier_rrtp2_stability_h1h2_2026-08-16.csv", index=False)
    df_k.to_csv("chantier_rrtp2_stability_kfold_2026-08-16.csv", index=False)


if __name__ == "__main__":
    main()
