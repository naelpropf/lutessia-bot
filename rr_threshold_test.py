"""
Teste l'effet d'un abaissement du seuil de filtre R:R (calculé sur rr_tp1, entrée),
avec les VRAIES durées de trade (vérification par bougies H1, comme
tp_sequence_analysis.py) plutôt que l'approximation à durée fixe utilisée dans le
calcul rapide initial.

Étapes :
1. Construit une population étendue à MIN_RR=1.0 (sur-ensemble des 8 seuils testés :
   1.0, 1.1, 1.25, 1.35, 1.5, 1.75, 2.0, 2.5), avec vérification des durées réelles
   via les bougies H1 déjà en cache (yfinance_cache/, mêmes tickers que d'habitude) —
   pas de nouveau scraping CentralCharts, juste des requêtes Yahoo Finance publiques
   (déjà utilisées ailleurs dans ce projet, cf. tp_sequence_analysis.py).
2. Pour chaque seuil : winrate/EV/somme des R (convention rr_tp1, la même que
   scaling_simulation.py partout ailleurs dans ce projet) + corrélation rr_tp1/gain.
3. Monte Carlo (2000 sims, bootstrap par permutation) par seuil, risque fixe 0.5%,
   toutes les règles de scaling actuelles (plafond 3 positions, corrélation 0.6+JPY,
   scaling 50k->200k->500k avec 4 jours min, contrainte de faisabilité marge/lots).
4. Robustesse par sous-période : 1ère moitié vs 2e moitié chronologique de chaque
   population, mêmes métriques qu'à l'étape 2.
"""
import re

import numpy as np
import pandas as pd

import tp_sequence_analysis as tpseq
from scaling_simulation import (
    TIER_SEQUENCE, CHALLENGE_COST, UPGRADE_COST, CHALLENGE_TARGET_PCT,
    MIN_TRADING_DAYS, BREAK_DD_PCT, RESERVE_SHARE, MAX_POSITIONS, CORR_THRESHOLD,
    is_jpy, feasible_risk_pct, load_market_data,
)
from monte_carlo_simulation import (
    run_one, summarize, precompute_correlation_pairs, N_SIMULATIONS,
)

FOREX_PATTERN = re.compile(r"^[A-Z]{3}/[A-Z]{3}$")
HIST_PATH = "historique_lutessia_15k_force.csv"
MIN_RR_SUPERSET = 1.0
THRESHOLDS = [1.0, 1.1, 1.25, 1.35, 1.5, 1.75, 2.0, 2.5]
RISK_PCT = 0.5


def build_extended_population(min_rr=MIN_RR_SUPERSET):
    # <<< CORRECTIF 2026-08-18 : l'ancien filtre `FOREX_PATTERN.match(t)` excluait
    # silencieusement TOUT ticker non-forex (indices inclus), independamment de tout
    # critere RR ou whitelist scraper -- jamais un choix methodologique documente,
    # juste un artefact herite de l'epoque ou seul le forex etait pertinent (voir
    # chantier_reference_A_indices_2026-08-18.py / registre_parametres_projet.md
    # S1.8bis pour la mesure d'impact : +17,6% de volume sur A, EV quasi inchangee).
    # Remplace par un critere base sur la mappabilite reelle (forex OU indices geres
    # par ticker_to_yahoo_symbol / INDEX_KEYWORD_MAP) -- MINI DJ30 reste exclu
    # naturellement (rr_tp1=NaN dans la source, echoue deja le filtre ligne precedente,
    # et de toute facon absent de INDEX_KEYWORD_MAP).
    df = pd.read_csv(HIST_PATH)
    df["date_creation"] = pd.to_datetime(df["date_creation"])
    pop = df[(df["rr_tp1"] >= min_rr) & (df["statut_final"].isin(["OBJECTIF ATTEINT", "INVALIDÉE"]))].copy()
    pop["yahoo_symbol"] = pop["ticker"].apply(tpseq.ticker_to_yahoo_symbol)
    pop = pop.dropna(subset=["yahoo_symbol"]).copy()
    pop = pop.sort_values("date_creation").reset_index(drop=True)

    assert pop["yahoo_symbol"].notna().all(), "Tickers non mappés inattendus (forex+indices mappés ici)"

    unique_symbols = sorted(pop["yahoo_symbol"].unique())
    start_dt = pop["date_creation"].min() - pd_timedelta_1d()
    end_dt = pd.Timestamp.utcnow().tz_localize(None)

    print(f"Population étendue (rr_tp1 >= {min_rr}, forex+indices mappés, terminaux) : {len(pop)} trades")
    print(f"Chargement/complément des bougies H1 pour {len(unique_symbols)} tickers...")

    candles_by_symbol = {}
    for symbol in unique_symbols:
        candles = tpseq.fetch_h1_history(symbol, start_dt.to_pydatetime(), end_dt.to_pydatetime())
        if candles is not None and not candles.empty:
            candles_by_symbol[symbol] = candles

    results = []
    for _, row in pop.iterrows():
        candles = candles_by_symbol.get(row["yahoo_symbol"])
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
    print(f"Durées réelles vérifiées (bougies H1) : {n_verified}/{len(pop)} "
          f"({n_verified/len(pop)*100:.1f}%) — durée médiane de repli : {median_duration}")

    return pop, median_duration


def pd_timedelta_1d():
    return pd.Timedelta(days=1)


def global_stats(sub):
    n = len(sub)
    wins = sub[sub["statut_final"] == "OBJECTIF ATTEINT"]
    losses = sub[sub["statut_final"] == "INVALIDÉE"]
    winrate = len(wins) / n if n else float("nan")
    avg_rr_wins = wins["rr_tp1"].mean() if len(wins) else float("nan")
    ev = winrate * avg_rr_wins - (1 - winrate) if len(wins) else float("nan")
    sum_r = wins["rr_tp1"].sum() - len(losses)

    win_indicator = (sub["statut_final"] == "OBJECTIF ATTEINT").astype(int)
    corr = sub["rr_tp1"].corr(win_indicator) if n > 2 else float("nan")

    return {
        "n": n, "winrate_pct": winrate * 100, "avg_rr_wins": avg_rr_wins,
        "ev": ev, "sum_r": sum_r, "corr_rr_win": corr,
    }


def correlated(a, b, corr_matrix):
    if is_jpy(a) and is_jpy(b):
        return True
    return abs(corr_matrix.loc[a, b]) > CORR_THRESHOLD


def taken_trades(sub, corr_matrix):
    """Marche chronologique RÉELLE (pas de permutation) sur la population déjà
    filtrée par seuil R:R, en appliquant le plafond de 3 positions + l'exclusion par
    corrélation (0.6 + règle JPY), avec les VRAIES durées de détention estimées
    (resolution_time_est). Retourne le sous-ensemble effectivement exécutable —
    c'est CE sous-ensemble, pas la population brute, qui doit servir à mesurer le
    winrate/EV réels du bot une fois le plafond de positions actif."""
    sub = sub.sort_values("date_creation").reset_index(drop=True)
    open_positions = []
    taken_idx = []

    for idx, row in sub.iterrows():
        now = row["date_creation"]
        close_time = row["resolution_time_est"]

        open_positions = [(t, c) for (t, c) in open_positions if c > now]

        if len(open_positions) >= MAX_POSITIONS:
            continue
        if any(correlated(row["ticker"], t, corr_matrix) for (t, _) in open_positions):
            continue

        open_positions.append((row["ticker"], close_time))
        taken_idx.append(idx)

    return sub.loc[taken_idx]


def run_mc_for_threshold(pop, threshold, market_data, corr_matrix, risk_pct=RISK_PCT):
    sub = pop[pop["rr_tp1"] >= threshold].copy().sort_values("date_creation").reset_index(drop=True)

    t0 = sub["date_creation"].iloc[0]
    slot_arrivals = [(d - t0).total_seconds() for d in sub["date_creation"]]

    trades = []
    for _, row in sub.iterrows():
        hold_seconds = (row["resolution_time_est"] - row["date_creation"]).total_seconds()
        sl_distance = abs(row["prix_entree"] - row["stop_loss_init"])
        trades.append({
            "ticker": row["ticker"],
            "outcome_r": row["rr_tp1"] if row["statut_final"] == "OBJECTIF ATTEINT" else -1.0,
            "sl_distance": sl_distance,
            "hold_seconds": hold_seconds,
        })

    tickers = sorted(set(t["ticker"] for t in trades))
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    import random
    rng = random.Random(42)
    results = [run_one(trades, slot_arrivals, risk_pct, market_data, excluded_map, rng) for _ in range(N_SIMULATIONS)]
    return sub, summarize(results)


def main():
    pop, median_duration = build_extended_population()
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)

    print("\n" + "=" * 100)
    print("ÉTAPE 1-3 : STATS GLOBALES + MONTE CARLO PAR SEUIL (durées réelles, risque 0.5%)")
    print("=" * 100)

    mc_summary_rows = []
    subs_by_threshold = {}
    taken_by_threshold = {}
    for thr in THRESHOLDS:
        sub = pop[pop["rr_tp1"] >= thr].copy()
        subs_by_threshold[thr] = sub
        gs_raw = global_stats(sub)

        taken = taken_trades(sub, corr_matrix)
        taken_by_threshold[thr] = taken
        gs_taken = global_stats(taken)

        _, mc = run_mc_for_threshold(pop, thr, market_data, corr_matrix)
        mc_summary_rows.append({
            "threshold": thr,
            "n_brut": gs_raw["n"], "winrate_brut_pct": gs_raw["winrate_pct"], "ev_brut": gs_raw["ev"],
            "sum_r_brut": gs_raw["sum_r"], "corr_rr_win": gs_raw["corr_rr_win"],
            "n_pris": gs_taken["n"], "winrate_pris_pct": gs_taken["winrate_pct"], "ev_pris": gs_taken["ev"],
            "sum_r_pris": gs_taken["sum_r"],
            **mc,
        })

        print(f"\n--- Seuil rr_tp1 >= {thr} ---")
        print(f"  Population brute (avant plafond/corrélation) : N={gs_raw['n']} | Winrate={gs_raw['winrate_pct']:.1f}% | "
              f"RR moyen gains={gs_raw['avg_rr_wins']:.2f} | EV={gs_raw['ev']:+.3f} R | Somme des R={gs_raw['sum_r']:+.1f} | "
              f"corr(rr_tp1, gain)={gs_raw['corr_rr_win']:+.3f}")
        print(f"  Trades PRIS (après plafond 3 positions + corrélation 0.6/JPY) : N={gs_taken['n']} "
              f"({gs_taken['n']/gs_raw['n']*100:.1f}% de la population brute) | Winrate={gs_taken['winrate_pct']:.1f}% | "
              f"EV={gs_taken['ev']:+.3f} R | Somme des R={gs_taken['sum_r']:+.1f}")
        print(f"  Monte Carlo (0.5% risque, {N_SIMULATIONS} runs, réapplique le filtre à chaque permutation) : "
              f"profit net moyen {mc['mean_profit']:+,.0f}€ | médian {mc['median_profit']:+,.0f}€ | "
              f"P(perte) {mc['pct_loss']:.1f}% | casses moyen {mc['mean_broken_count']:.2f} | "
              f"max casses consécutives {mc['max_max_consecutive_breaks']}")

    summary_df = pd.DataFrame(mc_summary_rows)
    summary_df.to_csv("rr_threshold_summary.csv", index=False)

    print("\n" + "=" * 100)
    print("ÉTAPE 4 : ROBUSTESSE PAR SOUS-PÉRIODE (1ère moitié vs 2e moitié chronologique)")
    print("=" * 100)
    period_rows = []
    for thr in THRESHOLDS:
        sub = taken_by_threshold[thr].sort_values("date_creation").reset_index(drop=True)
        mid = len(sub) // 2
        first_half = sub.iloc[:mid]
        second_half = sub.iloc[mid:]

        gs1 = global_stats(first_half)
        gs2 = global_stats(second_half)
        period_rows.append({"threshold": thr, "half": "1ère moitié",
                             "date_min": first_half["date_creation"].min(), "date_max": first_half["date_creation"].max(),
                             **gs1})
        period_rows.append({"threshold": thr, "half": "2e moitié",
                             "date_min": second_half["date_creation"].min(), "date_max": second_half["date_creation"].max(),
                             **gs2})

        print(f"\n--- Seuil {thr} (sur les trades PRIS, après plafond/corrélation) ---")
        print(f"  1ère moitié ({first_half['date_creation'].min()} -> {first_half['date_creation'].max()}, n={gs1['n']}) : "
              f"winrate {gs1['winrate_pct']:.1f}% | EV {gs1['ev']:+.3f} R | somme R {gs1['sum_r']:+.1f}")
        print(f"  2e moitié   ({second_half['date_creation'].min()} -> {second_half['date_creation'].max()}, n={gs2['n']}) : "
              f"winrate {gs2['winrate_pct']:.1f}% | EV {gs2['ev']:+.3f} R | somme R {gs2['sum_r']:+.1f}")

    period_df = pd.DataFrame(period_rows)
    period_df.to_csv("rr_threshold_period_split.csv", index=False)

    print("\nRésumés enregistrés dans rr_threshold_summary.csv et rr_threshold_period_split.csv")
    return summary_df, period_df


if __name__ == "__main__":
    main()
