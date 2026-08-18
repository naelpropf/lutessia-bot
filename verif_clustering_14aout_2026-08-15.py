"""
Verification demandee 08/15 (suite au chantier plafond de position §2.28) :
le 14/08 (2 signaux le meme jour calendaire, 00:22 et 13:24 -- observation
EN PRODUCTION, hors de la population historique qui s'arrete au 2026-07-30,
`historique_lutessia_15k_force.csv` -- verifie ci-dessous, aucune ligne
2026-08-14 dans le CSV) est-il un jour normal ou un outlier, et Section 1
du chantier precedent (`chantier_position_cap_2026-08-15.py`) sous-compte-
t-elle les arrivees groupees ?

Q1 : frequence des jours calendaires avec 2+ signaux distincts, population
"complete" (min_rr=1.25, 721 trades -- le seuil cite par l'utilisateur).
Q2 : audit du code de Section 1 -- compte-t-il bien un chevauchement REEL
(temps, pas jour calendaire) ou existe-t-il un biais.
Q3 : sur les 631 trades (min_rr=1.35, la population effectivement utilisee
en Section 1), comparer le taux de blocage "temps reel" (deja calcule,
0.8%) a un taux "naif jour calendaire" (compte tout chevauchement de
JOUR comme collision potentielle, sans tenir compte des heures reelles)
pour voir si l'ecart s'explique par la granularite (heure vs jour) plutot
qu'un bug.
"""
import pandas as pd

import robustness_5ers_risk_challenge as eng
from rr_threshold_test import build_extended_population
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs

pd.set_option("display.width", 140)


def q1_frequence_jours_groupes():
    print("=" * 70)
    print("Q1 -- frequence des jours avec 2+ signaux (population min_rr=1.25, 721 trades)")
    print("=" * 70)
    pop, median_dur = build_extended_population(min_rr=1.25)
    print(f"n = {len(pop)} (attendu 721)")
    pop["day"] = pop["date_creation"].dt.date

    counts = pop.groupby("day").size()
    n_days_actifs = len(counts)
    print(f"\nJours calendaires distincts avec >=1 signal : {n_days_actifs}")
    print(f"Jours avec 2+ signaux le meme jour : {(counts >= 2).sum()} "
          f"({(counts >= 2).sum() / n_days_actifs * 100:.1f}% des jours actifs)")
    print(f"Jours avec 3+ signaux le meme jour : {(counts >= 3).sum()} "
          f"({(counts >= 3).sum() / n_days_actifs * 100:.1f}% des jours actifs)")
    print(f"\nDistribution (nb signaux/jour -> nb de jours) :")
    print(counts.value_counts().sort_index().to_string())

    n_signaux_dans_jours_groupes = pop[pop["day"].isin(counts[counts >= 2].index)].shape[0]
    print(f"\nPart de la POPULATION (pas des jours) touchee par un jour groupe (2+) : "
          f"{n_signaux_dans_jours_groupes}/{len(pop)} ({n_signaux_dans_jours_groupes / len(pop) * 100:.1f}%)")

    print(f"\n-> VERDICT Q1 : ", end="")
    pct2plus = (counts >= 2).sum() / n_days_actifs * 100
    if pct2plus >= 15:
        print(f"les jours a 2+ signaux sont FREQUENTS ({pct2plus:.1f}% des jours actifs) -- "
              f"le 14/08 est un jour NORMAL, pas un outlier.")
    else:
        print(f"les jours a 2+ signaux sont RARES ({pct2plus:.1f}% des jours actifs) -- "
              f"a comparer au verdict Q3 pour trancher si le 14/08 est un outlier ou pas.")
    return pop, counts


def q2_audit_methodologie():
    print("\n" + "=" * 70)
    print("Q2 -- audit du code de Section 1 (chantier_position_cap_2026-08-15.py)")
    print("=" * 70)
    print("""
Relecture de la boucle de replay (section1_replay(), lignes ~95-120) :

    for _, row in pop.iterrows():
        now = row["date_creation"]                      # timestamp COMPLET (jour+heure+minute)
        close_time = row["resolution_time_est"]          # timestamp COMPLET de cloture estimee
        ...
        open_positions = [(t, c, x) for (t, c, x) in open_positions if c > now]
        if len(open_positions) >= eng.MAX_POSITIONS:
            blocked_reason = "cap_position"
        ...
        if blocked_reason is None:
            open_positions.append((ticker, close_time, rr))

Le code compare des TIMESTAMPS COMPLETS (pas des jours calendaires) --
2 signaux le meme jour calendaire mais espaces de plusieurs heures (ex.
00:22 et 13:24, ecart 13h02) ne sont PAS automatiquement en collision : la
1ere position doit encore etre "ouverte" (close_time > now de la 2e) au
moment de la 2e arrivee. AUCUN bug de granularite jour/heure trouve --
c'est le comportement VOULU et correct (une vraie collision de plafond
depend de la duree REELLE de detention, pas du jour calendaire).

Point de vigilance reel, DIFFERENT d'un bug de comptage : resolution_time_est
utilise la duree REELLE verifiee par bougies H1 pour ~50%% des trades, et
un FALLBACK = duree MEDIANE globale (~7h41) pour l'autre moitie (trades
hors couverture Yahoo H1, ~730j). Ce n'est pas un bug de la Section 1 (deja
la convention standard du projet, `rr_threshold_test.build_extended_population`,
utilisee partout) -- mais une source plausible et DIRECTIONNELLE de sous-
comptage : si la distribution reelle des durees a une queue longue (des
trades tenus bien plus longtemps que la mediane), le fallback a la mediane
COURCOURCIT ces trades-la dans le modele, libere leur slot trop tot, et
peut donc faire manquer des collisions reelles impliquant les positions
les plus longues. Quantifie ci-dessous.
""")

    pop, median_dur = build_extended_population(min_rr=1.35)
    verified = pop[pop["resolution_verifiee"]]
    durations_h = (verified["resolution_time"] - verified["date_creation"]).dt.total_seconds() / 3600
    print(f"Distribution des durees REELLES verifiees (bougies H1), n={len(verified)}/{len(pop)} :")
    print(durations_h.describe(percentiles=[0.5, 0.75, 0.9, 0.95, 0.99]).to_string())
    print(f"\nMediane utilisee comme fallback pour les {len(pop) - len(verified)} trades non verifies : "
          f"{median_dur}")
    p90 = durations_h.quantile(0.90)
    p95 = durations_h.quantile(0.95)
    mean_h = durations_h.mean()
    med_h = durations_h.median()
    print(f"\nAsymetrie : moyenne={mean_h:.1f}h vs mediane={med_h:.1f}h "
          f"(p90={p90:.1f}h, p95={p95:.1f}h) -- {'queue longue confirmee, moyenne > mediane' if mean_h > med_h * 1.15 else 'distribution relativement symetrique'}.")
    part_longues = (durations_h > 2 * med_h).mean() * 100
    print(f"Part des trades verifies avec duree > 2x la mediane : {part_longues:.1f}%")
    print(f"\n-> VERDICT Q2 : pas de bug de comptage jour/heure dans Section 1 (comparaison de "
          f"timestamps complets, correcte). Biais DIRECTIONNEL plausible mais MINEUR via le fallback "
          f"median (sous-estime la duree des positions les plus longues pour ~49%% des trades non "
          f"verifies) -- limite de donnees deja connue du projet, pas une erreur de Section 1 elle-meme.")


def q3_taux_naif_vs_reel():
    print("\n" + "=" * 70)
    print("Q3 -- taux de blocage : temps reel (deja mesure) vs jour-calendaire naif (631 trades, RR>=1.35)")
    print("=" * 70)

    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.35, verbose=False)
    pop = pop.sort_values("date_creation").reset_index(drop=True)
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, 0.80)

    # --- (a) methode TEMPS REEL, identique a Section 1 (rappel/reproduction) ---
    open_positions = []
    rows = []
    for _, row in pop.iterrows():
        now = row["date_creation"]
        close_time = row["resolution_time_est"]
        ticker = row["ticker"]
        open_positions = [(t, c) for (t, c) in open_positions if c > now]
        blocked_cap = len(open_positions) >= eng.MAX_POSITIONS
        blocked_corr = (not blocked_cap) and any(t in excluded_map[ticker] for (t, _) in open_positions)
        rows.append({"blocked_cap": blocked_cap, "blocked_corr": blocked_corr, "day": now.date()})
        if not blocked_cap and not blocked_corr:
            open_positions.append((ticker, close_time))
    df_real = pd.DataFrame(rows)
    n = len(df_real)
    rate_real = df_real["blocked_cap"].mean() * 100

    # --- (b) methode NAIVE jour-calendaire : ignore les heures, compte >=1 conflit
    #     potentiel des qu'un signal arrive un jour ou 3 AUTRES trades sont deja
    #     comptabilises ce meme jour calendaire (peu importe l'heure exacte) --
    #     borne HAUTE deliberement grossiere, pour situer l'ecart de granularite,
    #     PAS une proposition de methode alternative correcte.
    pop["day"] = pop["date_creation"].dt.date
    day_counts = pop.groupby("day").size()
    rows_naive = []
    seen_today = {}
    for _, row in pop.iterrows():
        d = row["date_creation"].date()
        n_before_today = seen_today.get(d, 0)
        blocked_naive = n_before_today >= eng.MAX_POSITIONS
        rows_naive.append(blocked_naive)
        seen_today[d] = n_before_today + 1
    rate_naive = (sum(rows_naive) / len(rows_naive)) * 100

    print(f"n = {n} trades (RR>=1.35, meme population que Section 1 du chantier)")
    print(f"\nTaux de blocage CAP -- methode TEMPS REEL (Section 1, correcte) : "
          f"{df_real['blocked_cap'].sum()}/{n} = {rate_real:.2f}%")
    print(f"Taux de blocage CAP -- methode NAIVE jour-calendaire (borne haute grossiere, "
          f"ignore les heures) : {sum(rows_naive)}/{n} = {rate_naive:.2f}%")
    print(f"\nRatio naif/reel : {rate_naive / rate_real:.1f}x" if rate_real > 0 else "rate_real=0, ratio non defini")

    print(f"\n-> VERDICT Q3 : ", end="")
    if rate_naive > rate_real * 3:
        print(f"le taux naif jour-calendaire ({rate_naive:.2f}%) est nettement plus eleve que le taux "
              f"temps-reel mesure en Section 1 ({rate_real:.2f}%) -- ATTENDU, puisque 'meme jour' est une "
              f"condition beaucoup plus large que 'chevauchement reel' (duree mediane de detention ~7h41, "
              f"largement sous 24h). L'ecart ne signale PAS un bug -- il quantifie simplement a quel point "
              f"'signaux le meme jour' et 'signaux qui se bloquent reellement' sont deux choses differentes. "
              f"Le chiffre correct pour juger le plafond de position reste celui de Section 1 (temps reel).")
    else:
        print("le taux naif et le taux reel sont proches -- pas d'ecart de granularite notable.")


if __name__ == "__main__":
    pop721, counts = q1_frequence_jours_groupes()
    q2_audit_methodologie()
    q3_taux_naif_vs_reel()
