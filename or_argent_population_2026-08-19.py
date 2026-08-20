"""Pipeline duree-reelle + payoff-realiste + trailing pour la population GOLD/
SILVER (chantier fusion dans Strategie B, 2026-08-19). Copie/adaptation A
L'IDENTIQUE de la chaine standard du projet (rr_threshold_test.
build_extended_population -> tp2_realistic_payoff.build_realistic_payoff_
population -> trailing_payoff_population.build_population_with_trailing),
SEULE difference : source CSV + mapping ticker->symbole Yahoo (gold_silver_
yahoo_mapping_2026-08-19.py au lieu de tp_sequence_analysis.
ticker_to_yahoo_symbol, qui ne gere pas GOLD/SILVER, cf. sa docstring).

Meme convention de payoff realiste (tp2_realistic_payoff.py:27-35) :
- OBJECTIF ATTEINT, continuation confirmee (TP1->TP2 verifie) : R = rr_tp2
- OBJECTIF ATTEINT, reste (non confirme OU hors couverture)   : R = rr_tp1
- INVALIDEE                                                    : R = -1.0

Meme trailing adopte sur B (registre_strategie_trading.md S5.1, 0,10x SL,
DOMINANCE STRICTE n=600) applique aux trades a continuation confirmee.
"""
import importlib.util

import pandas as pd

import tp_sequence_analysis as tpseq
from trailing_stop_variants import compute_atr, simulate_trailing

_spec = importlib.util.spec_from_file_location("gsmap", "gold_silver_yahoo_mapping_2026-08-19.py")
gsmap = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gsmap)
build_synthetic_candles = gsmap.build_synthetic_candles
or_argent_ticker_to_symbol = gsmap.or_argent_ticker_to_symbol

HIST_PATH = "historique_or_argent_pilote_2026-08-19.csv"
MIN_RR = 1.00
TRAILING_FACTOR = 0.10

CONTINUATION_CONFIRMED_CASES = {"tp1_avant_tp2", "meme_bougie"}
CONTINUATION_NOT_CONFIRMED_CASES = {"tp2_non_atteint_dans_fenetre", "tp1_non_detecte"}
OUT_OF_COVERAGE_CASES = {"hors_couverture_historique", "pas_de_donnees"}


def build_extended_population_or_argent(min_rr=MIN_RR):
    """Equivalent de rr_threshold_test.build_extended_population (rr_threshold_
    test.py:43-103), source = pilote or/argent, mapping symbole = gold_silver_
    yahoo_mapping au lieu de tp_sequence_analysis.ticker_to_yahoo_symbol."""
    df = pd.read_csv(HIST_PATH)
    df["date_creation"] = pd.to_datetime(df["date_creation"])
    pop = df[(df["rr_tp1"] >= min_rr) & (df["statut_final"].isin(["OBJECTIF ATTEINT", "INVALIDÉE"]))].copy()
    pop = pop.sort_values("date_creation").reset_index(drop=True)

    unique_tickers = sorted(pop["ticker"].unique())
    print(f"Population or/argent (rr_tp1 >= {min_rr}, resolus) : {len(pop)} trades, {len(unique_tickers)} tickers")

    start_dt = pop["date_creation"].min() - pd.Timedelta(days=1)
    end_dt = pd.Timestamp.utcnow().tz_localize(None)

    candles_by_ticker = {}
    for ticker in unique_tickers:
        candles = build_synthetic_candles(ticker, start_dt.to_pydatetime(), end_dt.to_pydatetime())
        if candles is not None and not candles.empty:
            candles_by_ticker[ticker] = candles

    results = []
    for _, row in pop.iterrows():
        candles = candles_by_ticker.get(row["ticker"])
        if candles is None:
            results.append({"case": "pas_de_donnees", "tp1_time": None, "tp2_time": None, "sl_time": None})
            continue
        res = tpseq.analyze_trade(row, candles)
        results.append(res)

    res_df = pd.DataFrame(results)
    pop["case"] = res_df["case"].values
    pop["tp1_time"] = pd.to_datetime(res_df["tp1_time"].values)
    pop["sl_time"] = pd.to_datetime(res_df["sl_time"].values)

    pop["resolution_time"] = pop.apply(
        lambda r: r["tp1_time"] if r["statut_final"] == "OBJECTIF ATTEINT" else r["sl_time"], axis=1
    )
    pop["resolution_verifiee"] = pop["resolution_time"].notna()

    verified = pop[pop["resolution_verifiee"]]
    median_duration = (verified["resolution_time"] - verified["date_creation"]).median()
    pop["resolution_time_est"] = pop["resolution_time"].fillna(pop["date_creation"] + median_duration)

    n_verified = pop["resolution_verifiee"].sum()
    print(f"Durées réelles vérifiées (bougies H1 synthétiques incluses) : {n_verified}/{len(pop)} "
          f"({n_verified/len(pop)*100:.1f}%) — durée médiane de repli : {median_duration}")

    return pop, median_duration, candles_by_ticker


def build_realistic_payoff_population_or_argent(min_rr=MIN_RR, verbose=True):
    """Equivalent de tp2_realistic_payoff.build_realistic_payoff_population
    (tp2_realistic_payoff.py:48-104)."""
    pop_full, median_duration, candles_by_ticker = build_extended_population_or_argent(min_rr=min_rr)
    pop = pop_full[pop_full["rr_tp1"] >= min_rr].copy()

    wins_mask = pop["statut_final"] == "OBJECTIF ATTEINT"

    def classify(case):
        if case in CONTINUATION_CONFIRMED_CASES:
            return "continuation_confirmee"
        if case in CONTINUATION_NOT_CONFIRMED_CASES:
            return "continuation_non_confirmee"
        if case in OUT_OF_COVERAGE_CASES:
            return "hors_couverture"
        return "autre"

    pop["payoff_bucket"] = None
    pop.loc[wins_mask, "payoff_bucket"] = pop.loc[wins_mask, "case"].apply(classify)

    def realistic_r(row):
        if row["statut_final"] != "OBJECTIF ATTEINT":
            return -1.0
        if row["payoff_bucket"] == "continuation_confirmee":
            return row["rr_tp2"]
        return row["rr_tp1"]

    pop["r_realiste"] = pop.apply(realistic_r, axis=1)

    if verbose:
        wins = pop[wins_mask]
        n_wins = len(wins)
        print(f"\nTrades OBJECTIF ATTEINT : {n_wins}")
        print(wins["case"].value_counts())
        print(f"\nBuckets payoff :")
        print(wins["payoff_bucket"].value_counts())
        ev_realiste = pop["r_realiste"].mean()
        print(f"EV payoff realiste : {ev_realiste:+.4f} R")

    return pop, median_duration, candles_by_ticker


def build_population_with_trailing_or_argent(trailing_factor=TRAILING_FACTOR, min_rr=MIN_RR, verbose=True):
    """Equivalent de trailing_payoff_population.build_population_with_trailing
    (trailing_payoff_population.py:36-73), meme variante 'fixed' 0,10x adoptee
    sur B (registre_strategie_trading.md S5.1)."""
    pop, median_duration, candles_by_ticker = build_realistic_payoff_population_or_argent(min_rr=min_rr, verbose=verbose)
    confirmed = pop[pop["payoff_bucket"] == "continuation_confirmee"].copy()

    def _stop_fn_param(extreme, entry, risk_distance, atr):
        is_long_direction = extreme >= entry
        return extreme - trailing_factor * risk_distance if is_long_direction else extreme + trailing_factor * risk_distance

    r_map = {}
    n_trailed = 0
    for _, row in confirmed.iterrows():
        candles = candles_by_ticker.get(row["ticker"])
        if candles is None:
            continue
        candles_atr = compute_atr(candles)
        res = simulate_trailing(row, candles_atr, _stop_fn_param, f"fixed_{trailing_factor}")
        if res is not None:
            r_map[(row["ticker"], row["date_creation"])] = res["exit_r"]
            n_trailed += 1

    def resolve_r(r):
        if r["payoff_bucket"] == "continuation_confirmee":
            return r_map.get((r["ticker"], r["date_creation"]), r["r_realiste"])
        return r["r_realiste"]

    pop = pop.copy()
    pop["r_trailing"] = pop.apply(resolve_r, axis=1)

    if verbose:
        baseline_ev = pop["r_realiste"].mean()
        new_ev = pop["r_trailing"].mean()
        print(f"\n[trailing {trailing_factor}] trades trailes effectivement : {n_trailed}/{len(confirmed)} "
              f"(continuation confirmee avec couverture candles)")
        print(f"EV réaliste (sans trailing) = {baseline_ev:+.4f} R | "
              f"EV avec trailing = {new_ev:+.4f} R (delta {new_ev - baseline_ev:+.4f} R)")

    return pop


if __name__ == "__main__":
    pop = build_population_with_trailing_or_argent()
    pop.to_csv("or_argent_population_trailing_2026-08-19.csv", index=False)
    print(f"\nSauvegarde : or_argent_population_trailing_2026-08-19.csv ({len(pop)} trades)")
