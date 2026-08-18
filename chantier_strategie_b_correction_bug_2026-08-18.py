"""
TACHE 3 -- correction du bug filtre forex-only pour B (pas un nouveau
levier -- le filtre force-only de rr_threshold_test.py:47 n'a jamais ete
un choix methodologique documente, juste un artefact code en dur herite
de l'epoque ou seul le forex etait scrape/pertinent). Applique la meme
correction que Tache 1 (reference A) a la population B (bande RR
1,00<=rr_tp1<1,35), en recombinant B_forex (n=401) + indices dans la
meme bande (n=59, deja calcule dans chantier_strategie_b_gisement_
indices_2026-08-18.py).

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
    return pop.dropna(subset=["yahoo_symbol"]).reset_index(drop=True)


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


def outcome_r(pop):
    return np.where(pop["statut_final"] == "OBJECTIF ATTEINT", pop["r_trailing"], -1.0)


def months_span(pop):
    span = pop["date_creation"].max() - pop["date_creation"].min()
    return span.total_seconds() / 86400.0 / 30.44


if __name__ == "__main__":
    print("=" * 70)
    print("TACHE 3 -- correction bug filtre forex-only sur B (1,00<=rr_tp1<1,35)")
    print("=" * 70)

    pop_B_fx = build_population_with_trailing("fixed", 0.15, min_rr=0.75, verbose=False)
    pop_B_fx = pop_B_fx[pop_B_fx["rr_tp1"] < MIN_RR_A].reset_index(drop=True)
    r_B_fx = outcome_r(pop_B_fx)
    print(f"\nB avant correction (forex seul) : n={len(pop_B_fx)} "
          f"winrate={(r_B_fx>0).mean()*100:.1f}% EV={r_B_fx.mean():+.4f}R "
          f"freq={len(pop_B_fx)/months_span(pop_B_fx):.2f}/mois")

    pop_idx = compute_payoff(load_index_population_full())
    pop_idx_band = pop_idx[(pop_idx["rr_tp1"] >= 1.0) & (pop_idx["rr_tp1"] < MIN_RR_A)].reset_index(drop=True)
    r_idx_band = outcome_r(pop_idx_band)
    print(f"\nIndices dans la meme bande : n={len(pop_idx_band)} "
          f"winrate={(r_idx_band>0).mean()*100:.1f}% EV={r_idx_band.mean():+.4f}R")

    keep_cols = ["date_creation", "ticker", "rr_tp1", "rr_tp2", "statut_final", "r_trailing"]
    pop_B_corrected = pd.concat([pop_B_fx[keep_cols], pop_idx_band[keep_cols]], ignore_index=True)
    r_B_corrected = outcome_r(pop_B_corrected)

    print("\n" + "=" * 70)
    print("B avant/apres correction")
    print("=" * 70)
    n0, n1 = len(pop_B_fx), len(pop_B_corrected)
    wr0, wr1 = (r_B_fx > 0).mean() * 100, (r_B_corrected > 0).mean() * 100
    ev0, ev1 = r_B_fx.mean(), r_B_corrected.mean()
    print(f"n          : {n0} -> {n1}  (+{n1-n0} trades, +{(n1-n0)/n0*100:.1f}%)")
    print(f"winrate    : {wr0:.1f}% -> {wr1:.1f}%  (delta {wr1-wr0:+.1f}pt)")
    print(f"EV         : {ev0:+.4f}R -> {ev1:+.4f}R  (delta {ev1-ev0:+.4f}R, "
          f"{(ev1-ev0)/abs(ev0)*100:+.1f}% relatif)")
    print(f"frequence  : {n0/months_span(pop_B_fx):.2f} -> {n1/months_span(pop_B_corrected):.2f} trades/mois "
          f"(+{(n1/months_span(pop_B_corrected))/(n0/months_span(pop_B_fx))*100-100:.1f}%)")

    print("\n[Limite signalee] Le diagnostic 'bloque par correlation' (n=16, Delta=+0,668R,")
    print("chantier precedent) N'EST PAS recalcule ici -- correlation_matrix.csv ne couvre")
    print("QUE les 14 paires FX (verifie), aucune donnee de correlation pour DAX40/S&P500/")
    print("NASDAQ100. Etendre ce diagnostic necessiterait de calculer une matrice de")
    print("correlation indices<->FX au prealable -- tache separee, pas une simple")
    print("recombinaison de population comme ici.")

    pop_B_corrected.to_csv("chantier_strategie_b_population_corrigee_2026-08-18.csv", index=False)
