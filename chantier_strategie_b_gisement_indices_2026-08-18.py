"""
Suite du chantier "amelioration Strategie B" (2026-08-18) -- verifications
prealables (citation de code) puis quantification d'un gisement trouve.

QUESTION 1 (filtre RR>2 amont) : REPONSE = NON, jamais existe. `scraper.py`
(5 commits au total dans git log, aucun ne touche a un seuil RR) calcule
rr_tp1/rr_tp2 pour CHAQUE signal scrape sans jamais filtrer dessus avant
stockage (scrape_lutessia_archives, ligne ~383-384 : calcul systematique,
aucune condition RR). Le seul filtre a la collecte est un whitelist
D'ACTIFS (`_is_target_asset`, scraper.py:101-107), pas un filtre RR.

QUESTION 2 (couverture actifs) : REPONSE = NON, pas tous les actifs.
- Whitelist scraper (`TARGET_FOREX_TICKERS`/`TARGET_INDEX_KEYWORDS`/
  `TARGET_CRYPTO_SUFFIXES`, scraper.py:82-98) = 15 paires FX + 2 metaux +
  5 indices + 2 cryptos = 24 instruments potentiels.
- Brut scrape reellement present (historique_lutessia_15k_force.csv,
  1966 lignes) : 14 paires FX (1645 lignes) + 6 tickers indices bruts
  (321 lignes) + 0 metal + 0 crypto (jamais poste par Lutessia sur la
  fenetre scrapee, ou cause differente non investiguee ici -- signale,
  pas confirme).
- MAIS `build_extended_population()` (rr_threshold_test.py:47) applique
  un filtre FOREX-ONLY CODE EN DUR (`FOREX_PATTERN.match(ticker)`),
  INDEPENDANT du whitelist scraper et de tout critere RR -- il draine
  TOUTE population utilisee dans ce projet (A comme B) vers du forex pur.
  **321 trades indices sont scrapes avec succes puis silencieusement
  elimines a cette etape, jamais vus par aucune simulation du projet.**
  C'est le gisement demande par la tache.

Ticker "MINI DJ30 FULL0625" (53 lignes) a rr_tp1 = NaN sur TOUTES ses
lignes (echec de parsing prix en amont, bug distinct, signale mais pas
corrige ici) -- exclu de la quantification, pas mappable de toute facon
(DJ30 absent de INDEX_KEYWORD_MAP, tp_sequence_analysis.py:43-47).

Ce script quantifie les 268 trades indices restants (DAX40/S&P500/
NASDAQ100, mappables via INDEX_KEYWORD_MAP), MEME methodologie que la
population FX standard (analyze_trade + realistic payoff + trailing,
reutilise directement tp_sequence_analysis.py/trailing_stop_variants.py),
puis stress-test H1/H2+4 blocs AVANT toute conclusion -- rappel explicite
de l'echec H2 du classement de paires (chantier_correlation_swap_2026-
08-16.py Section 1), meme rigueur ici.

N'importe pas ce script directement (convention du projet).
"""
import datetime as dt

import numpy as np
import pandas as pd

import tp_sequence_analysis as tpseq
from trailing_stop_variants import compute_atr, simulate_trailing

HIST_PATH = "historique_lutessia_15k_force.csv"
CONTINUATION_CONFIRMED_CASES = {"tp1_avant_tp2", "meme_bougie"}
INDEX_KEYWORDS = ["DAX40", "S&P500", "NASDAQ100"]


def load_index_population():
    df = pd.read_csv(HIST_PATH)
    df["date_creation"] = pd.to_datetime(df["date_creation"])

    is_index = df["ticker"].str.contains("|".join(INDEX_KEYWORDS), case=False, na=False)
    pop = df[is_index].copy()
    print(f"Tickers indices bruts (avant nettoyage) : {pop['ticker'].value_counts().to_dict()}")

    pop = pop[pop["statut_final"].isin(["OBJECTIF ATTEINT", "INVALIDÉE"])].copy()
    pop = pop.dropna(subset=["rr_tp1", "prix_entree", "stop_loss_init", "tp1_init", "tp2_init"]).copy()
    pop["yahoo_symbol"] = pop["ticker"].apply(tpseq.ticker_to_yahoo_symbol)
    dropped_unmapped = pop["yahoo_symbol"].isna().sum()
    if dropped_unmapped:
        print(f"[Exclu] {dropped_unmapped} trades non mappables (ex. DJ30, hors INDEX_KEYWORD_MAP)")
    pop = pop.dropna(subset=["yahoo_symbol"]).reset_index(drop=True)
    return pop


def compute_payoff(pop):
    unique_symbols = sorted(pop["yahoo_symbol"].unique())
    start_dt = pop["date_creation"].min() - dt.timedelta(days=1)
    end_dt = pd.Timestamp.utcnow().tz_localize(None)

    print(f"\nChargement bougies H1 pour {len(unique_symbols)} symboles indices : {unique_symbols}")
    candles_by_symbol = {}
    for symbol in unique_symbols:
        candles = tpseq.fetch_h1_history(symbol, start_dt.to_pydatetime(), end_dt.to_pydatetime())
        if candles is not None and not candles.empty:
            candles_by_symbol[symbol] = compute_atr(candles)
        else:
            print(f"  [ATTENTION] aucune bougie recuperee pour {symbol}")

    cases, r_realiste, r_trailing = [], [], []
    for _, row in pop.iterrows():
        candles = candles_by_symbol.get(row["yahoo_symbol"])
        if candles is None:
            cases.append("pas_de_donnees")
            r_realiste.append(-1.0 if row["statut_final"] != "OBJECTIF ATTEINT" else row["rr_tp1"])
            r_trailing.append(r_realiste[-1])
            continue

        res = tpseq.analyze_trade(row, candles)
        case = res.get("case", "pas_de_donnees")
        cases.append(case)

        if row["statut_final"] != "OBJECTIF ATTEINT":
            r_real = -1.0
        elif case in CONTINUATION_CONFIRMED_CASES:
            r_real = row["rr_tp2"]
        else:
            r_real = row["rr_tp1"]
        r_realiste.append(r_real)

        if row["statut_final"] == "OBJECTIF ATTEINT" and case in CONTINUATION_CONFIRMED_CASES:
            sim = simulate_trailing(row, candles, _stop_fn_fixed(0.15), "fixed_0.15")
            r_trailing.append(sim["exit_r"] if sim is not None else r_real)
        else:
            r_trailing.append(r_real)

    pop = pop.copy()
    pop["case"] = cases
    pop["r_realiste"] = r_realiste
    pop["r_trailing"] = r_trailing
    return pop


def _stop_fn_fixed(param):
    def fn(extreme, entry, risk_distance, atr):
        is_long_direction = extreme >= entry
        return extreme - param * risk_distance if is_long_direction else extreme + param * risk_distance
    return fn


def months_span(pop):
    span = pop["date_creation"].max() - pop["date_creation"].min()
    return span.total_seconds() / 86400.0 / 30.44


def report(pop):
    print("\n" + "=" * 70)
    print("QUANTIFICATION -- gisement indices (DAX40/S&P500/NASDAQ100)")
    print("=" * 70)

    print(f"\nDistribution des cas (verification continuation) :")
    print(pop["case"].value_counts())

    n = len(pop)
    span_mo = months_span(pop)
    winrate = (pop["r_trailing"] > 0).mean() * 100
    ev = pop["r_trailing"].mean()
    print(f"\n[Tout le gisement mappable] n={n} sur {span_mo:.1f} mois")
    print(f"  winrate = {winrate:.1f}%  EV = {ev:+.4f}R  frequence = {n/span_mo:.1f} trades/mois")
    print(f"  rr_tp1 : min={pop['rr_tp1'].min():.2f} P50={pop['rr_tp1'].median():.2f} "
          f"max={pop['rr_tp1'].max():.2f}")

    band = pop[(pop["rr_tp1"] >= 1.0) & (pop["rr_tp1"] < 1.35)]
    if len(band) > 0:
        print(f"\n[Sous-bande B-equivalente 1,00<=rr_tp1<1,35] n={len(band)}")
        print(f"  winrate = {(band['r_trailing']>0).mean()*100:.1f}%  "
              f"EV = {band['r_trailing'].mean():+.4f}R  "
              f"frequence = {len(band)/months_span(band):.1f} trades/mois")
    else:
        print("\n[Sous-bande B-equivalente] n=0 -- aucun trade indice dans cette bande")

    return n, span_mo


def stresstest(pop):
    print("\n" + "=" * 70)
    print("STRESS-TEST H1/H2+4 blocs -- gisement indices vs FX (rappel echec")
    print("classement de paires H2, meme rigueur ici)")
    print("=" * 70)

    pop_sorted = pop.sort_values("date_creation").reset_index(drop=True)
    mid = len(pop_sorted) // 2
    subperiods = {"H1": pop_sorted.iloc[:mid], "H2": pop_sorted.iloc[mid:]}
    blocks4 = np.array_split(pop_sorted, 4)
    for i, b in enumerate(blocks4):
        subperiods[f"bloc{i}"] = b

    global_ev = pop_sorted["r_trailing"].mean()
    evs = []
    for name, sp in subperiods.items():
        if len(sp) < 5:
            print(f"  [{name}] n={len(sp)} insuffisant -- ininterpretable")
            continue
        ev_sp = sp["r_trailing"].mean()
        wr_sp = (sp["r_trailing"] > 0).mean() * 100
        evs.append(ev_sp)
        sign_match = (ev_sp > 0) == (global_ev > 0)
        print(f"  [{name}] n={len(sp)}  EV={ev_sp:+.4f}R  winrate={wr_sp:.1f}%  "
              f"{'meme signe que global' if sign_match else '!! SIGNE DIFFERENT du global'}")

    print(f"\n  EV globale = {global_ev:+.4f}R")
    all_positive = all(e > 0 for e in evs)
    print(f"  Toutes les sous-periodes EV>0 : {all_positive}")
    if not all_positive:
        print("  >> INSTABILITE detectee -- meme profil d'echec que le classement de")
        print("     paires (H2, chantier_correlation_swap_2026-08-16.py Section 1).")
        print("     NE PAS integrer sans reserve -- signal non confirme robuste.")


if __name__ == "__main__":
    pop = load_index_population()
    print(f"\nPopulation indices utilisable (mappee, statut resolu) : {len(pop)} trades")
    pop = compute_payoff(pop)
    report(pop)
    stresstest(pop)
