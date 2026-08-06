"""
Construit, pour une STRUCTURE de pyramiding donnée (paliers d'ajout + fractions de
taille), la population de trades enrichie avec la liste des unités réellement ouvertes
par trade (cf. pyramid_engine.simulate_pyramid_trade), au lieu du simple `outcome_r`
scalaire utilisé partout ailleurs dans ce projet. Miroir direct de
trailing_payoff_population.py, mais walké AVANT TP2 (et pas seulement après).

Réutilise tp2_realistic_payoff.build_realistic_payoff_population (payoff réaliste +
classification payoff_bucket/resolution_verifiee, elle-même construite sur
rr_threshold_test.build_extended_population, seuil rr_tp1 >= 1.5) -- aucun nouveau
scraping CentralCharts, les bougies H1 Yahoo sont déjà en cache (yfinance_cache/) pour
ces mêmes tickers/période depuis les calculs précédents (tp_sequence_analysis,
trailing_payoff_population).
"""
import pandas as pd

import tp_sequence_analysis as tpseq
from tp2_realistic_payoff import build_realistic_payoff_population, MIN_RR_TP1
from trailing_stop_variants import compute_atr
from pyramid_engine import simulate_pyramid_trade

# Structures verrouillées pour le cas de base (2 paliers, +0.5R et +1R) :
#   A = paliers fixes (Turtle-style) : chaque ajout = 100% de l'unité initiale
#   B = dégressif : 50%, puis 25% de l'unité initiale
STRUCTURES = {
    "A_paliers_fixes": ([0.5, 1.0], [1.0, 1.0]),
    "B_degressif": ([0.5, 1.0], [0.5, 0.25]),
}


def _load_candles_by_symbol(pop):
    unique_symbols = sorted(pop["yahoo_symbol"].dropna().unique())
    candles_by_symbol = {}
    for symbol in unique_symbols:
        candles = tpseq.fetch_h1_history(symbol, pop["date_creation"].min().to_pydatetime(),
                                          pd.Timestamp.utcnow().tz_localize(None).to_pydatetime())
        if candles is not None and not candles.empty:
            candles_by_symbol[symbol] = compute_atr(candles)
    return candles_by_symbol


def build_population_with_pyramid(add_levels, add_fractions, min_rr=MIN_RR_TP1, verbose=False):
    """Retourne (pop, candles_by_symbol) : pop porte une colonne "units" (liste de
    dicts {level_r, entry_price, fraction, exit_r}) par trade, calculée par
    pyramid_engine.simulate_pyramid_trade pour les trades resolution_verifiee, et un
    repli à 1 unité (fraction 1.0, exit_r = r_realiste) pour les autres."""
    pop, _ = build_realistic_payoff_population(min_rr=min_rr, verbose=verbose)
    candles_by_symbol = _load_candles_by_symbol(pop)

    units_col = []
    n_verified_walked = 0
    for _, row in pop.iterrows():
        candles = candles_by_symbol.get(row["yahoo_symbol"])
        units = simulate_pyramid_trade(row, candles, add_levels, add_fractions)
        if row.get("resolution_verifiee", False) and candles is not None:
            n_verified_walked += 1
        units_col.append(units)
    pop = pop.copy()
    pop["units"] = units_col

    if verbose:
        n_reached_first = sum(1 for u in units_col if len(u) >= 2)
        n_reached_second = sum(1 for u in units_col if len(u) >= 3)
        print(f"[pyramid levels={add_levels} fractions={add_fractions}] "
              f"trades walkés bougie par bougie : {n_verified_walked}/{len(pop)} | "
              f"atteignent le 1er palier (+{add_levels[0]}R) : {n_reached_first}/{len(pop)} "
              f"({n_reached_first/len(pop)*100:.1f}%) | "
              f"atteignent le 2e palier (+{add_levels[1]}R) : {n_reached_second}/{len(pop)} "
              f"({n_reached_second/len(pop)*100:.1f}%)")

    return pop, candles_by_symbol


def pct_reaching_first_level(pop):
    """Fréquence des trades (population entière) qui atteignent au moins le 1er palier
    d'ajout (>= 2 unités ouvertes) -- mesure demandée dans le livrable, indépendante du
    Monte Carlo."""
    n_reached = sum(1 for u in pop["units"] if len(u) >= 2)
    return n_reached / len(pop) * 100


def build_trades_pyramid(pop):
    """Construit trades/slot_arrivals au format attendu par le moteur flotte/copytrade
    (ticker, sl_distance, hold_seconds, date), avec un champ "units" au lieu d'un
    outcome_r scalaire."""
    sub = pop.sort_values("date_creation").reset_index(drop=True)
    t0 = sub["date_creation"].iloc[0]
    slot_arrivals = [(d - t0).total_seconds() for d in sub["date_creation"]]

    trades = []
    for _, row in sub.iterrows():
        hold_seconds = (row["resolution_time_est"] - row["date_creation"]).total_seconds()
        sl_distance = abs(row["prix_entree"] - row["stop_loss_init"])
        trades.append({
            "ticker": row["ticker"],
            "units": row["units"],
            "sl_distance": sl_distance,
            "hold_seconds": hold_seconds,
            "date": row["date_creation"],
        })
    return sub, trades, slot_arrivals


if __name__ == "__main__":
    for label, (levels, fractions) in STRUCTURES.items():
        pop, _ = build_population_with_pyramid(levels, fractions, verbose=True)
        print(f"  -> % population atteignant le 1er palier : {pct_reaching_first_level(pop):.1f}%\n")
