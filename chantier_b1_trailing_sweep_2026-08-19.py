"""
Chantier "faire grandir B", Point 1 (2026-08-19) -- le trailing stop
post-TP2 0,15xSL a ete calibre/verrouille sur la population A (cf.
trailing_stop_sweep.py, sweep sur 98 trades a continuation confirmee de
la population RR>=1,5 de l'epoque) -- jamais retestee specifiquement sur
B (bande RR 1,00-1,35, winrate/EV differents).

Population B "actuelle" = B forex (RR dans [1,00 ; 1,35)) + TOUS les
indices mappables (DAX40/S&P500/NASDAQ100), independamment de leur RR --
c'est la population du routage "tout-indices->B" CONFIRME ADOPTE n=600
(chantier_strategie_b_isolation_indices_2026-08-18.py, variant
'tout_indices', deja utilisee comme reference pour tout ce chantier, pas
un ajout a re-tester).

Etape 1 : distribution des excursions post-TP2 (peak_r) sur cette
population B, meme methode que trailing_stop_variants.py (sous-ensemble a
continuation confirmee = tp1_avant_tp2/meme_bougie, cf.
CONTINUATION_CONFIRMED_CASES).

Etape 2 : sweep de facteurs [0.10, 0.15, 0.20, 0.25] x distance SL initiale
(meme famille "Distance_fixe" que trailing_stop_sweep.py, methode
identique -- simulate_trailing() de trailing_stop_variants.py, horizon
borne min(3x delai creation->TP2, 30j), meme convention de declenchement
stop-avant-extremum), calcul EV sur le sous-ensemble a continuation
confirmee ET impact sur l'EV globale de la population B complete
(substitution du payoff des trades a continuation confirmee uniquement,
les autres gardent r_realiste inchange) -- analyse DETERMINISTE sur
donnees historiques, pas de Monte Carlo ici (comme trailing_stop_sweep.py
pour A) ; si un facteur domine clairement, l'etape suivante (Monte Carlo
fleet n=300/n=600) sera un chantier separe.

N'importe pas ce script directement (convention du projet).
"""
import datetime as dt

import numpy as np
import pandas as pd

import tp_sequence_analysis as tpseq
from tp2_realistic_payoff import build_realistic_payoff_population
from trailing_stop_variants import compute_atr, simulate_trailing, find_tp2_touch

INDEX_KEYWORDS = ["DAX40", "S&P500", "NASDAQ100"]
CONTINUATION_CONFIRMED_CASES = {"tp1_avant_tp2", "meme_bougie"}
MIN_RR_B, MAX_RR_B = 1.0, 1.35
FACTORS = [0.10, 0.15, 0.20, 0.25]


def make_stop_fn_fixed(mult):
    def fn(extreme, entry, risk_distance, atr):
        is_long_direction = extreme >= entry
        return extreme - mult * risk_distance if is_long_direction else extreme + mult * risk_distance
    return fn


def load_forex_b():
    """Population forex B (RR dans [1,00;1,35)), EXCLUT les indices (deja
    inclus separement via load_index_population_full ci-dessous, sinon
    double-comptage -- meme garde-fou que Point 1 du chantier precedent).

    <<< BUG CORRIGE (detecte en cours de route, 2026-08-19) : appeler
    build_realistic_payoff_population(min_rr=1.0) PUIS filtrer rr_tp1>=1.0
    exclut a tort 13 trades reellement a RR=1,00 pile (plancher structurel
    du signal Lutessia) mais representes en flottant comme 0,999999999999...
    (verifie : build_population_with_trailing(min_rr=0.75) puis filtre
    <1.35 SANS refiltrer >=1.0 donne bien n=401, le chiffre officiel deja
    adopte -- le filtre strict >=1.0 en Python sur un flottant qui vaut
    "presque 1.0" les rejette). Corrige en appelant avec min_rr=0.75 (sous
    le bruit flottant) et en NE reappliquant PAS de borne basse stricte."""
    pop = build_realistic_payoff_population(min_rr=0.75, verbose=False)[0]
    is_index = pop["ticker"].str.contains("|".join(INDEX_KEYWORDS), case=False, na=False)
    pop = pop[~is_index].copy()
    pop = pop[pop["rr_tp1"] < MAX_RR_B].reset_index(drop=True)
    return pop


def load_index_population_full():
    """TOUS les indices mappables, independamment de rr_tp1 (routage
    tout-indices->B) -- meme classification (payoff_bucket via
    tpseq.analyze_trade) que la population forex pour comparaison directe."""
    df = pd.read_csv("historique_lutessia_15k_force.csv")
    df["date_creation"] = pd.to_datetime(df["date_creation"])
    is_index = df["ticker"].str.contains("|".join(INDEX_KEYWORDS), case=False, na=False)
    pop = df[is_index].copy()
    pop = pop[pop["statut_final"].isin(["OBJECTIF ATTEINT", "INVALIDÉE"])].copy()
    pop = pop.dropna(subset=["rr_tp1", "prix_entree", "stop_loss_init", "tp1_init", "tp2_init"]).copy()
    pop["yahoo_symbol"] = pop["ticker"].apply(tpseq.ticker_to_yahoo_symbol)
    pop = pop.dropna(subset=["yahoo_symbol"]).reset_index(drop=True)

    unique_symbols = sorted(pop["yahoo_symbol"].unique())
    start_dt = pop["date_creation"].min() - dt.timedelta(days=1)
    end_dt = pd.Timestamp.utcnow().tz_localize(None)
    candles_by_symbol = {}
    for symbol in unique_symbols:
        candles = tpseq.fetch_h1_history(symbol, start_dt.to_pydatetime(), end_dt.to_pydatetime())
        if candles is not None and not candles.empty:
            candles_by_symbol[symbol] = compute_atr(candles)

    cases, r_realiste = [], []
    for _, row in pop.iterrows():
        candles = candles_by_symbol.get(row["yahoo_symbol"])
        if candles is None:
            cases.append("pas_de_donnees")
            r_realiste.append(-1.0 if row["statut_final"] != "OBJECTIF ATTEINT" else row["rr_tp1"])
            continue
        res = tpseq.analyze_trade(row, candles)
        case = res.get("case", "pas_de_donnees")
        cases.append(case)
        if row["statut_final"] != "OBJECTIF ATTEINT":
            r_realiste.append(-1.0)
        elif case in CONTINUATION_CONFIRMED_CASES:
            r_realiste.append(row["rr_tp2"])
        else:
            r_realiste.append(row["rr_tp1"])

    pop = pop.copy()
    pop["case"] = cases
    pop["r_realiste"] = r_realiste
    pop["payoff_bucket"] = np.where(
        pop["statut_final"] != "OBJECTIF ATTEINT", "perte",
        np.where(pop["case"].isin(CONTINUATION_CONFIRMED_CASES), "continuation_confirmee", "autre"))
    return pop, candles_by_symbol


if __name__ == "__main__":
    print("=" * 70)
    print("Chantier B Point 1 -- sweep trailing post-TP2 sur population B")
    print("=" * 70)

    pop_fx = load_forex_b()
    keep_cols = ["date_creation", "ticker", "rr_tp1", "rr_tp2", "statut_final",
                 "payoff_bucket", "r_realiste", "prix_entree", "stop_loss_init",
                 "tp1_init", "tp2_init", "yahoo_symbol"]
    pop_fx["yahoo_symbol"] = pop_fx["ticker"].apply(tpseq.ticker_to_yahoo_symbol)
    pop_idx, candles_idx = load_index_population_full()

    pop_B = pd.concat([pop_fx[keep_cols], pop_idx[keep_cols]], ignore_index=True)
    print(f"\nPopulation B (forex RR[1,00;1,35) + tous indices) : n={len(pop_B)} "
          f"({len(pop_fx)} forex + {len(pop_idx)} indices)")

    confirmed = pop_B[pop_B["payoff_bucket"] == "continuation_confirmee"].reset_index(drop=True)
    print(f"Sous-ensemble a continuation confirmee (seul concerne par le trailing) : n={len(confirmed)}")

    # Bougies (forex depuis cache standard, indices deja chargees ci-dessus)
    unique_symbols = sorted(confirmed["yahoo_symbol"].unique())
    candles_by_symbol = dict(candles_idx)
    start_dt = confirmed["date_creation"].min() - dt.timedelta(days=1)
    end_dt = pd.Timestamp.utcnow().tz_localize(None)
    for symbol in unique_symbols:
        if symbol in candles_by_symbol:
            continue
        candles = tpseq.fetch_h1_history(symbol, start_dt.to_pydatetime(), end_dt.to_pydatetime())
        if candles is not None and not candles.empty:
            candles_by_symbol[symbol] = compute_atr(candles)

    # --- Etape 1 : distribution des excursions post-TP2 (peak_r) ---
    print("\n" + "=" * 70)
    print("ETAPE 1 -- distribution des excursions post-TP2 (peak_r, MFE apres TP2)")
    print("=" * 70)
    peaks = []
    for _, row in confirmed.iterrows():
        candles = candles_by_symbol.get(row["yahoo_symbol"])
        if candles is None:
            continue
        res = simulate_trailing(row, candles, make_stop_fn_fixed(0.15), "diag_peak")
        if res is not None:
            peaks.append(res["peak_r"])
    peaks = pd.Series(peaks)
    print(f"n={len(peaks)} | moyenne={peaks.mean():+.3f}R | mediane={peaks.median():+.3f}R | "
          f"P25={peaks.quantile(.25):+.3f}R | P75={peaks.quantile(.75):+.3f}R | "
          f"%>=+1R apres TP2 : {(peaks>=1.0).mean()*100:.1f}%")

    # --- Etape 2 : sweep des facteurs ---
    print("\n" + "=" * 70)
    print("ETAPE 2 -- sweep facteurs trailing (Distance_fixe x SL initial)")
    print("=" * 70)
    baseline_r = confirmed["rr_tp2"].mean()
    print(f"Reference TP2 sec sur ces {len(confirmed)} trades : EV={baseline_r:+.4f}R\n")

    baseline_ev_full = pop_B["r_realiste"].mean()
    print(f"EV baseline population B complete (sans trailing, TP2 sec partout) : {baseline_ev_full:+.4f}R\n")

    rows = []
    for mult in FACTORS:
        stop_fn = make_stop_fn_fixed(mult)
        exit_rs, tickers, dates = [], [], []
        for _, row in confirmed.iterrows():
            candles = candles_by_symbol.get(row["yahoo_symbol"])
            if candles is None:
                continue
            res = simulate_trailing(row, candles, stop_fn, f"fixed_{mult}")
            if res is None:
                continue
            exit_rs.append(res["exit_r"])
            tickers.append(row["ticker"])
            dates.append(row["date_creation"])
        exit_rs = pd.Series(exit_rs)
        ev_confirmed = exit_rs.mean()
        r_map = dict(zip(zip(tickers, dates), exit_rs))
        r_new = pop_B.apply(
            lambda r: r_map.get((r["ticker"], r["date_creation"]), r["r_realiste"])
            if r["payoff_bucket"] == "continuation_confirmee" else r["r_realiste"], axis=1)
        ev_full = r_new.mean()
        rows.append(dict(facteur=mult, n=len(exit_rs), ev_confirmed=ev_confirmed,
                          delta_vs_tp2_sec=ev_confirmed - baseline_r,
                          ev_population_b_complete=ev_full,
                          delta_vs_baseline_full=ev_full - baseline_ev_full))
        print(f"  facteur={mult:.2f}xSL : n={len(exit_rs)} EV(confirmes)={ev_confirmed:+.4f}R "
              f"(delta TP2 sec {ev_confirmed-baseline_r:+.4f}R) | EV(pop B complete)={ev_full:+.4f}R "
              f"(delta vs baseline {ev_full-baseline_ev_full:+.4f}R)")

    df = pd.DataFrame(rows).sort_values("ev_population_b_complete", ascending=False).reset_index(drop=True)
    df.to_csv("chantier_b1_trailing_sweep_2026-08-19.csv", index=False)
    print("\n" + "=" * 70)
    print("CLASSEMENT (EV population B complete, decroissant)")
    print("=" * 70)
    print(df.to_string(index=False))
    best = df.iloc[0]
    print(f"\nMeilleur facteur sur cette mesure population-EV : {best['facteur']:.2f}xSL "
          f"(vs 0,15xSL actuellement en production)")
