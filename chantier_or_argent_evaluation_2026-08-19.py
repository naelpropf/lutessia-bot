"""Evaluation EV/winrate/bootstrap du pilote or/argent (Etape 2), meme methode
que le pilote exotiques de ce soir (chantier_exotiques_pilote_2026-08-19.py) :
filtre RR planifie >=1,00, R realise = rr_tp1 si OBJECTIF ATTEINT sinon -1,0
(convention standard du projet, cf. scaling_simulation.py:209), signaux
"SEUIL PRESERVE" (encore ouverts, pas de resultat resolu) exclus -- meme
critere terminal que rr_threshold_test.build_extended_population:56
(statut_final.isin(["OBJECTIF ATTEINT", "INVALIDEE"])).

Bootstrap IC95% : boot_ci (chantier_rrtp2_stability_verification_2026-08-
16.py:18-21), 5000 iterations, seed=9999 (coherent avec le reste du projet).
"""
import numpy as np
import pandas as pd

CSV_PATH = "historique_or_argent_pilote_2026-08-19.csv"
MIN_RR = 1.00


def boot_ci(arr, seed=9999, n_iter=5000):
    rng = np.random.default_rng(seed)
    boot = np.array([rng.choice(arr, size=len(arr), replace=True).mean() for _ in range(n_iter)])
    return np.percentile(boot, [2.5, 97.5])


def main():
    df = pd.read_csv(CSV_PATH)
    n_raw = len(df)

    df = df[df["statut_final"].isin(["OBJECTIF ATTEINT", "INVALIDÉE"])].copy()
    n_resolved = len(df)

    df = df[df["rr_tp1"] >= MIN_RR].copy()
    n_filtered = len(df)

    df["outcome_r"] = np.where(df["statut_final"] == "OBJECTIF ATTEINT", df["rr_tp1"], -1.0)

    print(f"Population brute : {n_raw} lignes")
    print(f"Apres exclusion SEUIL PRESERVE (non resolus) : {n_resolved} lignes")
    print(f"Apres filtre RR planifie >= {MIN_RR} : {n_filtered} lignes")
    print(f"NaN rr_tp1 (prix_entree manquant) exclus au passage : "
          f"{n_resolved - df['rr_tp1'].notna().sum() if 'rr_tp1' in df else 'n/a'}")

    is_spot = ~df["ticker"].str.contains("FULL", na=False)
    df_spot = df[is_spot].copy()
    df_fut = df[~is_spot].copy()
    print(f"\nSpot (hors contrats futures datees FULLxxxx) : {len(df_spot)} lignes")
    print(f"Futures datees (GOLD/SILVER FULLxxxx, produit distinct, exclues de l'analyse principale) : {len(df_fut)} lignes")

    print("\n" + "=" * 78)
    print(f"Par ticker (n>=30, population SPOT, RR>={MIN_RR})")
    print("=" * 78)
    rows = []
    for ticker, g in df_spot.groupby("ticker"):
        n = len(g)
        if n < 30:
            continue
        ev = g["outcome_r"].mean()
        winrate = (g["statut_final"] == "OBJECTIF ATTEINT").mean()
        lo, hi = boot_ci(g["outcome_r"].to_numpy())
        rows.append(dict(ticker=ticker, n=n, ev=ev, winrate=winrate, ci_lo=lo, ci_hi=hi,
                          excludes_zero=(lo > 0 or hi < 0)))
    tbl = pd.DataFrame(rows).sort_values("ev", ascending=False)
    for _, r in tbl.iterrows():
        flag = "  <-- IC95% exclut 0" if r["excludes_zero"] else ""
        print(f"  {r['ticker']:15s} n={r['n']:4.0f}  EV={r['ev']:+.4f}R  winrate={r['winrate']*100:5.1f}%  "
              f"IC95%=[{r['ci_lo']:+.4f},{r['ci_hi']:+.4f}]{flag}")

    below30 = df_spot.groupby("ticker").size()
    below30 = below30[below30 < 30]
    if len(below30):
        print(f"\nTickers avec n<30 (non evalues individuellement) : {dict(below30)}")

    print("\n" + "=" * 78)
    print("POOL COMPLET (tous tickers or/argent spot confondus, RR>=1,00)")
    print("=" * 78)
    ev_pool = df_spot["outcome_r"].mean()
    winrate_pool = (df_spot["statut_final"] == "OBJECTIF ATTEINT").mean()
    lo, hi = boot_ci(df_spot["outcome_r"].to_numpy())
    print(f"n={len(df_spot)}  EV={ev_pool:+.4f}R  winrate={winrate_pool*100:.1f}%  IC95%=[{lo:+.4f},{hi:+.4f}]")
    excludes_zero = lo > 0 or hi < 0
    print(f"IC95% exclut zero : {excludes_zero}")

    print("\n" + "=" * 78)
    print("Comparaison a la barre de jugement du projet")
    print("=" * 78)
    print(f"Reference A (population principale RR>=1,35) : +0,89 a +0,93R")
    print(f"Reference B (bande 1,00-1,35)                : +0,80R")
    print(f"Pilote exotiques (ce soir, rejete)            : +0,0587R, IC95% incluant zero")
    print(f"Pilote or/argent (ce chantier)                : {ev_pool:+.4f}R, IC95%=[{lo:+.4f},{hi:+.4f}]")

    tbl.to_csv("chantier_or_argent_evaluation_par_ticker_2026-08-19.csv", index=False)
    df_spot.to_csv("historique_or_argent_pilote_filtre_spot_2026-08-19.csv", index=False)


if __name__ == "__main__":
    main()
