"""
Théorie des valeurs extrêmes (Peaks-Over-Threshold + distribution de Pareto
généralisée) sur la trésorerie perso du régime 2% direct "débloqué" (2000 runs déjà
simulés, two_regime_full_dist_2pct_debloque.csv, colonne real_cash_paid) -- estime la
queue au-delà de ce que 2000 tirages peuvent montrer directement, SANS relancer de
Monte Carlo à 4000/8000/20000 runs.

Méthode :
  1. Seuil élevé u (percentile 90 ET 95 des 2000 valeurs, pour vérifier la robustesse
     au choix du seuil -- un bon ajustement GPD doit donner des estimés cohérents
     entre les deux seuils).
  2. Ajustement GPD par méthode des moments sur les dépassements (x - u | x > u) --
     xi_hat = 0.5*(m²/v - 1), sigma_hat = 0.5*m*(m²/v + 1), m/v = moyenne/variance
     des dépassements (Hosking & Wallis 1987, standard pour POT).
  3. Formule de retour : P(X > u+y) = zeta_u * (1 + xi*y/sigma)^(-1/xi), zeta_u =
     proportion des 2000 tirages au-dessus du seuil -- inversée pour trouver la
     valeur x_p au niveau de probabilité 1/N souhaité (N=4000/8000/20000).
  4. Incertitude par BOOTSTRAP non-paramétrique (rééchantillonnage avec remise des
     2000 valeurs, ré-ajustement GPD à chaque tirage, 2000 réplications) -- donne un
     intervalle [P5, P95] sur chaque estimation de queue, pas juste un point.
  5. Cohérence : le pire cas observé (7992€) doit correspondre à une probabilité de
     dépassement plausible pour n=2000 tirages (grosso modo entre 1/500 et 1/4000,
     cf. théorie des statistiques d'ordre extrêmes -- E[rang du max] ~ n).
"""
import numpy as np
import pandas as pd

RNG_SEED = 42
N_BOOTSTRAP = 2000
TARGET_N = [4000, 8000, 20000]
THRESHOLD_PERCENTILES = [0.90, 0.95]


def fit_gpd_moments(excesses):
    """Méthode des moments (Hosking & Wallis 1987). Retourne (xi, sigma)."""
    m = excesses.mean()
    v = excesses.var(ddof=1)
    if v <= 0 or m <= 0:
        return None, None
    xi = 0.5 * (m ** 2 / v - 1)
    sigma = 0.5 * m * (m ** 2 / v + 1)
    return xi, sigma


def gpd_return_level(xi, sigma, zeta_u, u, target_n):
    """Valeur x_p telle que P(X > x_p) = 1/target_n, via la GPD ajustée au-delà de u."""
    p_exceed_threshold = 1.0 / target_n / zeta_u  # P(dépasser x_p | dépasse déjà u)
    if p_exceed_threshold <= 0 or p_exceed_threshold >= 1:
        return None
    if abs(xi) < 1e-8:
        y = -sigma * np.log(p_exceed_threshold)
    else:
        y = (sigma / xi) * (p_exceed_threshold ** (-xi) - 1)
    return u + y


def gpd_survival_at(xi, sigma, zeta_u, u, x):
    """P(X > x) prédite par le modèle GPD ajusté, pour x >= u."""
    y = x - u
    if y < 0:
        return None
    if abs(xi) < 1e-8:
        tail = np.exp(-y / sigma)
    else:
        base = 1 + xi * y / sigma
        if base <= 0:
            return 0.0
        tail = base ** (-1 / xi)
    return zeta_u * tail


def analyze_threshold(data, pct, target_ns, rng):
    n = len(data)
    u = np.quantile(data, pct)
    exceed_mask = data > u
    excesses = data[exceed_mask] - u
    zeta_u = exceed_mask.sum() / n
    xi, sigma = fit_gpd_moments(excesses)

    print(f"\n--- Seuil u = P{int(pct*100)} = {u:,.0f}€ | n_dépassements = {exceed_mask.sum()}/{n} "
          f"(zeta_u = {zeta_u:.4f}) ---")
    if xi is None:
        print("Ajustement impossible (variance nulle ou négative sur les dépassements).")
        return None
    print(f"GPD ajustée -- xi (forme) = {xi:+.3f} | sigma (échelle) = {sigma:,.0f}€")
    if xi > 0:
        print("xi > 0 : queue lourde (type Pareto/Fréchet) -- pas de borne supérieure théorique.")
    elif xi < 0:
        print(f"xi < 0 : queue bornée -- borne supérieure théorique = {u - sigma/xi:,.0f}€")
    else:
        print("xi ~ 0 : queue de type exponentiel.")

    # Bootstrap non-paramétrique sur les 2000 valeurs complètes (pas juste les dépassements)
    # -> capture aussi l'incertitude sur zeta_u (proportion qui dépasse le seuil).
    boot_estimates = {t: [] for t in target_ns}
    boot_survival_7992 = []
    for _ in range(N_BOOTSTRAP):
        sample = data[rng.integers(0, n, size=n)]
        u_b = u  # seuil fixe (choix méthodologique), on rééchantillonne la distribution autour
        exc_b = sample[sample > u_b] - u_b
        zeta_b = (sample > u_b).sum() / n
        xi_b, sigma_b = fit_gpd_moments(exc_b)
        if xi_b is None:
            continue
        for t in target_ns:
            est = gpd_return_level(xi_b, sigma_b, zeta_b, u_b, t)
            if est is not None:
                boot_estimates[t].append(est)
        surv = gpd_survival_at(xi_b, sigma_b, zeta_b, u_b, 7992.0)
        if surv is not None:
            boot_survival_7992.append(surv)

    results = {}
    print(f"\n{'Niveau':<12} {'Estimation ponctuelle':>22} {'IC 90% [P5-P95] bootstrap':>35}")
    for t in target_ns:
        point = gpd_return_level(xi, sigma, zeta_u, u, t)
        arr = np.array(boot_estimates[t])
        if point is not None and len(arr) > 10:
            lo, hi = np.percentile(arr, [5, 95])
            print(f"1/{t:<10} {point:>21,.0f}€ {'[' + f'{lo:,.0f}€ - {hi:,.0f}€' + ']':>35}")
            results[t] = (point, lo, hi)
        else:
            print(f"1/{t:<10} {'estimation instable':>21}")
            results[t] = None

    if boot_survival_7992:
        arr = np.array(boot_survival_7992)
        implied_return_period = 1.0 / arr
        med_rp = np.median(implied_return_period)
        lo_rp, hi_rp = np.percentile(implied_return_period, [5, 95])
        print(f"\nPériode de retour implicite du pire cas observé (7992€) selon ce modèle GPD :")
        print(f"  médiane {med_rp:,.0f} runs | IC90% [{lo_rp:,.0f} - {hi_rp:,.0f}]")
        print(f"  (cohérent avec un maximum sur n=2000 si la période de retour tombe environ dans [500, 8000])")

    return {"u": u, "zeta_u": zeta_u, "xi": xi, "sigma": sigma, "results": results}


def main():
    df = pd.read_csv("two_regime_full_dist_2pct_debloque.csv")
    data = df["real_cash_paid"].values
    n = len(data)
    print("=" * 100)
    print(f"EXTRAPOLATION DE QUEUE (GPD/POT) -- trésorerie perso, régime 2% débloqué, n={n} runs observés")
    print("=" * 100)
    print(f"Pire cas observé directement : {data.max():,.0f}€")
    print(f"P90={np.quantile(data,0.90):,.0f}€ | P95={np.quantile(data,0.95):,.0f}€ | "
          f"P99={np.quantile(data,0.99):,.0f}€")

    rng = np.random.default_rng(RNG_SEED)
    for pct in THRESHOLD_PERCENTILES:
        analyze_threshold(data, pct, TARGET_N, rng)


if __name__ == "__main__":
    main()
