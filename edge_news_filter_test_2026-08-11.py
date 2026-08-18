"""
Test 1 (08/11) : effet reel du filtre news (`news_filter.py`, actif en
production, jamais backtesté avant ce jour).

SOURCE DE DONNEES (recherche bornee 15-20min, cf. instruction utilisateur) :
`nfs.faireconomy.media/ff_calendar_thisweek.json` (deja utilise en
production) ne sert QUE la semaine courante, aucun historique -- confirme
en lisant news_filter.py. Alternative trouvee et VALIDEE : dataset
HuggingFace `Ehsanrs2/Forex_Factory_Calendar` (licence MIT, scrape via
Selenium, 83k lignes, colonnes DateTime/Currency/Impact/Event/Actual/
Forecast/Previous/Detail) -- meme source (ForexFactory) et memes
categories d'evenements (High/Medium/Low Impact) que la production.

⚠️ COUVERTURE PARTIELLE, A NE PAS MASQUER : ce dataset couvre 2007-01-01
-> 2025-04-04 (High Impact). La population de reference va jusqu'au
2026-07-30 -- tout trade apres le 2025-04-04 n'a AUCUNE donnee news
disponible dans cette source et est explicitement EXCLU (colonne
couverture_calendrier=False), pas suppose "sans news" par defaut.

⚠️ LIMITE METHODOLOGIQUE SUR LE POINT 3 (simulation du delai) : le filtre
retarde l'execution de NEWS_WINDOW_MINUTES=2 minutes (meme constante que
news_filter.py). Les seules bougies de prix disponibles dans ce projet
sont H1 (yfinance) -- bien trop grossieres pour resoudre un mouvement de
prix sur 2 minutes (le bruit intra-heure domine largement tout signal
reel). Simuler le point 3 avec des bougies H1 produirait un chiffre
FAUSSEMENT PRECIS. Ce script NE SIMULE PAS le point 3 -- il est rapporte
comme non mesurable avec les donnees disponibles (donnees M1/tick
necessaires, non presentes dans ce projet hors une mesure ponctuelle de
slippage Dukascopy deja faite ailleurs, §2.11 registre_strategie_trading
.md, pas une archive complete).

N'importe pas ce script directement (convention du projet).
"""
import math
import re

import pandas as pd

from trailing_payoff_population import build_population_with_trailing

FF_CALENDAR_PATH = "ff_calendar_historical_2007_2025.csv"
NEWS_WINDOW_MINUTES = 2  # meme constante que news_filter.py
FOREX_PATTERN = re.compile(r"^([A-Z]{3})/([A-Z]{3})$")


def extract_currencies(ticker):
    m = FOREX_PATTERN.match(ticker)
    if m:
        return [m.group(1), m.group(2)]
    return []


def wilson_ci(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z ** 2 / n
    center = (p + z ** 2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / denom
    return (center - half, center + half)


def summarize(label, sub, base_n=None):
    n = len(sub)
    wins = (sub["statut_final"] == "OBJECTIF ATTEINT").sum()
    wr = wins / n * 100 if n else float("nan")
    lo, hi = wilson_ci(wins, n)
    ev = sub["r_trailing"].mean() if n else float("nan")
    return dict(config=label, n=n, n_exclus=(base_n - n) if base_n is not None else None,
                winrate_pct=wr, winrate_ic95_lo=lo * 100 if n else float("nan"),
                winrate_ic95_hi=hi * 100 if n else float("nan"), ev_r=ev)


if __name__ == "__main__":
    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=True)
    pop = pop.copy()
    print(f"\nPopulation totale : {len(pop)} trades, plage {pop['date_creation'].min()} -> {pop['date_creation'].max()}")

    ff = pd.read_csv(FF_CALENDAR_PATH, usecols=["DateTime", "Currency", "Impact"])
    ff["dt"] = pd.to_datetime(ff["DateTime"], utc=True, errors="coerce")
    ff_high = ff[ff["Impact"] == "High Impact Expected"].dropna(subset=["dt"]).copy()
    calendar_max_date = ff_high["dt"].max()
    print(f"Calendrier ForexFactory (High Impact) : {ff_high['dt'].min()} -> {calendar_max_date} "
          f"({len(ff_high)} evenements)")

    events_by_currency = {c: sorted(g["dt"].tolist()) for c, g in ff_high.groupby("Currency")}

    # date_creation deja UTC (confirme via dayjs.utc CentralCharts, cf. memoire projet)
    pop["date_creation_utc"] = pd.to_datetime(pop["date_creation"]).dt.tz_localize("UTC")
    pop["couverture_calendrier"] = pop["date_creation_utc"] <= calendar_max_date

    def near_news(row):
        if not row["couverture_calendrier"]:
            return None
        currencies = extract_currencies(row["ticker"])
        if not currencies:
            return False
        t0 = row["date_creation_utc"]
        window = pd.Timedelta(minutes=NEWS_WINDOW_MINUTES)
        for cur in currencies:
            times = events_by_currency.get(cur, [])
            # recherche lineaire suffisante ici (peu d'evenements/devise, pas un hot path)
            for ev_t in times:
                if abs((ev_t - t0).total_seconds()) <= window.total_seconds():
                    return True
        return False

    pop["near_high_impact_news"] = pop.apply(near_news, axis=1)

    n_total = len(pop)
    n_covered = pop["couverture_calendrier"].sum()
    n_uncovered = n_total - n_covered
    print(f"\nCouverture calendrier : {n_covered}/{n_total} trades dans la fenetre "
          f"({calendar_max_date.date()}), {n_uncovered} trades APRES (exclus, pas supposes sans news)")

    covered = pop[pop["couverture_calendrier"]].copy()
    near = covered[covered["near_high_impact_news"] == True]
    far = covered[covered["near_high_impact_news"] == False]

    rows = [
        summarize("baseline_couvert_calendrier", covered, len(covered)),
        summarize("pres_news_fort_impact_2min", near, len(covered)),
        summarize("hors_fenetre_news", far, len(covered)),
    ]
    out = pd.DataFrame(rows)
    out.to_csv("edge_news_filter_summary.csv", index=False)
    pop.to_csv("edge_news_filter_population_detail.csv", index=False)

    pd.set_option("display.width", 200)
    print("\n=== RESUME (point 1-2) ===")
    print(out.to_string(index=False))

    # Sous-periodes (robustesse) sur le sous-ensemble "pres news"
    near_sorted = near.sort_values("date_creation").reset_index(drop=True)
    if len(near_sorted) >= 20:
        half = len(near_sorted) // 2
        p1, p2 = near_sorted.iloc[:half], near_sorted.iloc[half:]
        print(f"\npres_news sous-periode 1/2 : n={len(p1)} EV={p1['r_trailing'].mean():+.4f}R")
        print(f"pres_news sous-periode 2/2 : n={len(p2)} EV={p2['r_trailing'].mean():+.4f}R")
    else:
        print(f"\npres_news : n={len(near_sorted)} trop petit pour un split sous-periode fiable")

    print("\n[ATTENTION] Point 3 (simulation du delai d'execution 2min) NON CALCULE -- "
          "necessite des donnees M1/tick, indisponibles dans ce projet (H1 seul en cache). "
          "Voir docstring de ce script.")
