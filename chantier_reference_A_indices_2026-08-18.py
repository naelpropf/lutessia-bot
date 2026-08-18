"""
Suite directe de chantier_strategie_b_gisement_indices_2026-08-18.py (meme
jour) -- TACHE 1 : impact sur la reference officielle A (RR>=1,35/corr0,80,
631 trades) si le filtre forex-only code en dur (rr_threshold_test.py:47,
`FOREX_PATTERN.match(ticker)`) est leve pour les indices mappables
(DAX40/S&P500/NASDAQ100 ; DJ30 exclu, rr_tp1=NaN sur toutes ses lignes,
bug de parsing distinct).

Reconstruit A_elargi = A (forex, 631 trades, deja construit par le
pipeline standard) + indices avec rr_tp1>=1,35 (meme seuil que la
reference), meme methodologie de payoff (analyze_trade + realistic +
trailing 0.15 fixe, deja validee/appliquee dans chantier_strategie_b_
gisement_indices_2026-08-18.py sur les 170 trades indices mappables).

N'importe pas ce script directement (convention du projet).
"""
import datetime as dt

import numpy as np
import pandas as pd

import tp_sequence_analysis as tpseq
from trailing_payoff_population import build_population_with_trailing
from trailing_stop_variants import compute_atr, simulate_trailing

HIST_PATH = "historique_lutessia_15k_force.csv"
CONTINUATION_CONFIRMED_CASES = {"tp1_avant_tp2", "meme_bougie"}
INDEX_KEYWORDS = ["DAX40", "S&P500", "NASDAQ100"]
MIN_RR_A = 1.35


def _stop_fn_fixed(param):
    def fn(extreme, entry, risk_distance, atr):
        is_long_direction = extreme >= entry
        return extreme - param * risk_distance if is_long_direction else extreme + param * risk_distance
    return fn


def load_index_population_full():
    df = pd.read_csv(HIST_PATH)
    df["date_creation"] = pd.to_datetime(df["date_creation"])
    is_index = df["ticker"].str.contains("|".join(INDEX_KEYWORDS), case=False, na=False)
    pop = df[is_index].copy()
    pop = pop[pop["statut_final"].isin(["OBJECTIF ATTEINT", "INVALIDÉE"])].copy()
    pop = pop.dropna(subset=["rr_tp1", "prix_entree", "stop_loss_init", "tp1_init", "tp2_init"]).copy()
    pop["yahoo_symbol"] = pop["ticker"].apply(tpseq.ticker_to_yahoo_symbol)
    pop = pop.dropna(subset=["yahoo_symbol"]).reset_index(drop=True)
    return pop


def compute_payoff(pop):
    unique_symbols = sorted(pop["yahoo_symbol"].unique())
    start_dt = pop["date_creation"].min() - dt.timedelta(days=1)
    end_dt = pd.Timestamp.utcnow().tz_localize(None)

    candles_by_symbol = {}
    for symbol in unique_symbols:
        candles = tpseq.fetch_h1_history(symbol, start_dt.to_pydatetime(), end_dt.to_pydatetime())
        if candles is not None and not candles.empty:
            candles_by_symbol[symbol] = compute_atr(candles)

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


def months_span(pop):
    span = pop["date_creation"].max() - pop["date_creation"].min()
    return span.total_seconds() / 86400.0 / 30.44


def outcome_r(pop):
    return np.where(pop["statut_final"] == "OBJECTIF ATTEINT", pop["r_trailing"], -1.0)


if __name__ == "__main__":
    print("=" * 70)
    print("TACHE 1 -- reference A elargie aux indices mappables (RR>=1,35)")
    print("=" * 70)

    print("\nChargement A actuel (forex, pipeline standard)...")
    pop_A = build_population_with_trailing("fixed", 0.15, min_rr=MIN_RR_A, verbose=False)
    r_A = outcome_r(pop_A)
    print(f"A actuel : n={len(pop_A)}  winrate={(r_A>0).mean()*100:.1f}%  EV={r_A.mean():+.4f}R")

    print("\nChargement + calcul payoff indices (meme methode que le gisement)...")
    pop_idx_all = load_index_population_full()
    pop_idx_all = compute_payoff(pop_idx_all)
    pop_idx_high = pop_idx_all[pop_idx_all["rr_tp1"] >= MIN_RR_A].reset_index(drop=True)
    r_idx_high = outcome_r(pop_idx_high)
    print(f"Indices RR>=1,35 (mappables, DJ30 exclu) : n={len(pop_idx_high)}  "
          f"winrate={(r_idx_high>0).mean()*100:.1f}%  EV={r_idx_high.mean():+.4f}R")
    print(f"  tickers : {pop_idx_high['ticker'].value_counts().to_dict()}")

    # Colonnes communes minimales pour la concatenation
    keep_cols = ["date_creation", "ticker", "rr_tp1", "rr_tp2", "statut_final", "r_trailing"]
    combined = pd.concat([pop_A[keep_cols], pop_idx_high[keep_cols]], ignore_index=True)
    r_combined = outcome_r(combined)

    n_A, n_idx, n_combined = len(pop_A), len(pop_idx_high), len(combined)
    wr_A, wr_combined = (r_A > 0).mean() * 100, (r_combined > 0).mean() * 100
    ev_A, ev_combined = r_A.mean(), r_combined.mean()

    print("\n" + "=" * 70)
    print("COMPARAISON A actuel vs A elargi (indices RR>=1,35 inclus)")
    print("=" * 70)
    print(f"n          : {n_A} -> {n_combined}  ({n_idx} trades ajoutes, +{n_idx/n_A*100:.1f}%)")
    print(f"winrate    : {wr_A:.1f}% -> {wr_combined:.1f}%  (delta {wr_combined-wr_A:+.1f}pt)")
    print(f"EV         : {ev_A:+.4f}R -> {ev_combined:+.4f}R  (delta {ev_combined-ev_A:+.4f}R, "
          f"{(ev_combined-ev_A)/abs(ev_A)*100:+.1f}% relatif)")
    print(f"frequence  : {n_A/months_span(pop_A):.2f} -> {n_combined/months_span(combined):.2f} trades/mois")

    combined.to_csv("chantier_reference_A_indices_population_2026-08-18.csv", index=False)
    print("\nPopulation combinee sauvegardee -> chantier_reference_A_indices_population_2026-08-18.csv")
