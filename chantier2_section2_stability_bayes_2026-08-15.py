"""
CHANTIER 2, Section 2 (08/15) : stabilite temporelle du winrate + distribution
bayesienne rigoureuse, sur la population ACTUELLE (RR>=1,35, 631 trades,
`build_population_with_trailing`), pas l'ancienne base (RR>=1,25/721 ou
RR>=1,5/472).

Bayes : prior de Jeffreys Beta(0.5,0.5) (standard pour une proportion
binomiale, non-informatif) mis a jour avec les vrais succes/echecs de la
population -- PAS le posterior Beta(172.66,305.36) de
`winrate_bayesian_posterior_weighted.py` (celui-la vient d'un contexte
totalement different : ancienne population 472 trades + un scenario "15
pertes consecutives" specifique, sans rapport avec la question posee ici).
Sensibilite verifiee avec un prior uniforme Beta(1,1) pour montrer que le
choix de prior importe peu a n=631 (domine par les donnees).
"""
import numpy as np
import pandas as pd
from scipy import stats

from trailing_payoff_population import build_population_with_trailing

MIN_RR = 1.35


def main():
    pop = build_population_with_trailing("fixed", 0.15, min_rr=MIN_RR, verbose=False)
    pop = pop.sort_values("date_creation").reset_index(drop=True)
    n = len(pop)
    is_win = (pop["statut_final"] == "OBJECTIF ATTEINT").to_numpy()
    wins, losses = int(is_win.sum()), n - int(is_win.sum())
    winrate_obs = wins / n
    rr_mean = pop["rr_tp1"].mean()

    print("=" * 70)
    print(f"Population : n={n} (RR>={MIN_RR}), wins={wins}, losses={losses}, "
          f"winrate observe={winrate_obs*100:.2f}%, RR(rr_tp1) moyen={rr_mean:.3f}")
    print("=" * 70)

    # ------------------------------------------------------------
    # 1. Stabilite temporelle par sous-periode (semestrielle + trimestrielle)
    # ------------------------------------------------------------
    print("\n--- Winrate par SEMESTRE ---")
    pop["semester"] = pop["date_creation"].dt.to_period("6M" if False else "Q")  # placeholder, remplace ci-dessous
    pop["semester"] = pop["date_creation"].dt.year.astype(str) + "-S" + \
        (((pop["date_creation"].dt.month - 1) // 6) + 1).astype(str)
    sem_stats = pop.groupby("semester").apply(
        lambda g: pd.Series({"n": len(g), "wins": (g["statut_final"] == "OBJECTIF ATTEINT").sum()})
    )
    sem_stats["winrate"] = sem_stats["wins"] / sem_stats["n"]
    sem_stats["wilson_lo"], sem_stats["wilson_hi"] = zip(*[
        wilson_ci(int(row["wins"]), int(row["n"])) for _, row in sem_stats.iterrows()
    ])
    print(sem_stats.to_string(formatters={"winrate": "{:.3f}".format, "wilson_lo": "{:.3f}".format,
                                            "wilson_hi": "{:.3f}".format}))

    print("\n--- Winrate par TRIMESTRE (granularite fine, robustesse) ---")
    pop["quarter"] = pop["date_creation"].dt.to_period("Q").astype(str)
    q_stats = pop.groupby("quarter").apply(
        lambda g: pd.Series({"n": len(g), "wins": (g["statut_final"] == "OBJECTIF ATTEINT").sum()})
    )
    q_stats["winrate"] = q_stats["wins"] / q_stats["n"]
    print(q_stats.to_string(formatters={"winrate": "{:.3f}".format}))

    # ------------------------------------------------------------
    # 2. Test de derive (signe de tendance dans le temps)
    # ------------------------------------------------------------
    print("\n--- Test de derive temporelle ---")
    t_days = (pop["date_creation"] - pop["date_creation"].min()).dt.total_seconds() / 86400
    win01 = is_win.astype(float)

    # (a) correlation point-bisériale trade-par-trade (le plus puissant, pas de perte
    #     d'info par binning) -- H0 : pas de correlation entre le temps et le resultat
    r_pb, p_pb = stats.pointbiserialr(win01, t_days)
    print(f"Correlation point-biseriale (win vs temps, trade-par-trade) : r={r_pb:+.4f}, p={p_pb:.4f}")

    # (b) regression lineaire sur les winrates SEMESTRIELS (poids = n, pour lisibilite/verif visuelle)
    x = np.arange(len(sem_stats))
    y = sem_stats["winrate"].to_numpy()
    slope, intercept, r_lin, p_lin, se = stats.linregress(x, y)
    print(f"Regression lineaire (winrate semestriel vs indice de periode) : "
          f"pente={slope:+.4f}/semestre, r={r_lin:+.3f}, p={p_lin:.4f}")

    print(f"\n-> VERDICT DERIVE : ", end="")
    if p_pb < 0.05:
        direction = "en HAUSSE" if r_pb > 0 else "en BAISSE"
        print(f"derive temporelle STATISTIQUEMENT SIGNIFICATIVE ({direction}, p={p_pb:.4f}) -- "
              f"attention, le winrate global peut ne pas representer le regime actuel.")
    else:
        print(f"AUCUNE derive temporelle statistiquement significative detectee "
              f"(p={p_pb:.4f} > 0.05, test trade-par-trade le plus puissant disponible) -- "
              f"le winrate global (n={n}) est une estimation raisonnable du regime actuel, "
              f"pas de biais de tendance a corriger.")

    # ------------------------------------------------------------
    # 3. Distribution bayesienne du winrate reel
    # ------------------------------------------------------------
    print("\n" + "=" * 70)
    print("Distribution bayesienne du winrate reel")
    print("=" * 70)

    for prior_name, (a0, b0) in [("Jeffreys Beta(0.5,0.5) -- non-informatif standard", (0.5, 0.5)),
                                  ("Uniforme Beta(1,1) -- controle de sensibilite", (1.0, 1.0))]:
        a_post, b_post = a0 + wins, b0 + losses
        dist = stats.beta(a_post, b_post)
        p10, p50, p90 = dist.ppf([0.10, 0.50, 0.90])
        print(f"\nPrior : {prior_name}")
        print(f"  Posterior Beta({a_post:.1f}, {b_post:.1f})")
        print(f"  P10={p10*100:.2f}% | P50={p50*100:.2f}% | P90={p90*100:.2f}%")
        for thr in [0.35, 0.38, 0.40, 0.42]:
            p_above = dist.sf(thr)
            ev_thr = thr * rr_mean - (1 - thr) * 1.0
            print(f"  P(winrate > {thr*100:.0f}%) = {p_above*100:5.1f}%  |  EV a ce seuil (RR={rr_mean:.2f}) = {ev_thr:+.4f}R")

    # seuil de rentabilite (EV=0) et P(EV reel < seuil) sous le prior Jeffreys (principal)
    a_post, b_post = 0.5 + wins, 0.5 + losses
    dist = stats.beta(a_post, b_post)
    wr_threshold = 1.0 / (rr_mean + 1.0)
    p_below = dist.cdf(wr_threshold)
    print(f"\n--- Seuil de rentabilite (EV=0) ---")
    print(f"Avec RR moyen = {rr_mean:.3f} : winrate seuil = 1/(RR+1) = {wr_threshold*100:.2f}%")
    print(f"P(winrate reel < seuil, donc EV reel < 0) sous le posterior Jeffreys = {p_below*100:.2f}%")
    print(f"Marge du winrate observe au-dessus du seuil : {(winrate_obs - wr_threshold)*100:+.2f}pt "
          f"({winrate_obs*100:.2f}% observe vs {wr_threshold*100:.2f}% seuil)")

    return sem_stats, q_stats, dist, wr_threshold, rr_mean, winrate_obs, n


def wilson_ci(k, n, z=1.96):
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return center - half, center + half


if __name__ == "__main__":
    main()
