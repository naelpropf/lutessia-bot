"""
Construit une population avec le payoff TP2 réaliste REMPLACÉ, sur les 98 trades à
continuation TP1->TP2 confirmée, par le résultat d'une règle de trailing stop donnée
(cf. trailing_stop_sweep.py, qui a identifié 2 configs battant TP2 sec : distance fixe
0.5x la distance SL, et retracement 10% du gain depuis l'entrée). Les 374 autres
trades (continuation non confirmée, hors couverture, INVALIDÉE) gardent r_realiste
inchangé -- le trailing ne s'applique qu'aux trades où TP2 a été vérifié atteint.
"""
import pandas as pd

import tp_sequence_analysis as tpseq
from tp2_realistic_payoff import build_realistic_payoff_population
from trailing_stop_variants import compute_atr, simulate_trailing, MIN_RR_TP1

WINNING_CONFIGS = {
    "trailing_distance_fixe_0.5x": ("fixed", 0.5),
    "trailing_retracement_10pct": ("retracement", 0.10),
}


def _stop_fn(kind, param):
    if kind == "fixed":
        def fn(extreme, entry, risk_distance, atr):
            is_long_direction = extreme >= entry
            return extreme - param * risk_distance if is_long_direction else extreme + param * risk_distance
        return fn
    if kind == "retracement":
        def fn(extreme, entry, risk_distance, atr):
            is_long_direction = extreme >= entry
            gain = abs(extreme - entry)
            return extreme - param * gain if is_long_direction else extreme + param * gain
        return fn
    raise ValueError(kind)


def build_population_with_trailing(kind, param, min_rr=MIN_RR_TP1, verbose=False):
    pop, _ = build_realistic_payoff_population(min_rr=min_rr, verbose=verbose)
    confirmed = pop[pop["payoff_bucket"] == "continuation_confirmee"].copy()
    confirmed["yahoo_symbol"] = confirmed["ticker"].apply(tpseq.ticker_to_yahoo_symbol)

    unique_symbols = sorted(confirmed["yahoo_symbol"].unique())
    candles_by_symbol = {}
    for symbol in unique_symbols:
        candles = tpseq.fetch_h1_history(symbol, confirmed["date_creation"].min().to_pydatetime(),
                                          pd.Timestamp.utcnow().tz_localize(None).to_pydatetime())
        if candles is not None and not candles.empty:
            candles_by_symbol[symbol] = compute_atr(candles)

    stop_fn = _stop_fn(kind, param)
    r_map = {}
    for _, row in confirmed.iterrows():
        candles = candles_by_symbol.get(row["yahoo_symbol"])
        if candles is None:
            continue
        res = simulate_trailing(row, candles, stop_fn, f"{kind}_{param}")
        if res is not None:
            r_map[(row["ticker"], row["date_creation"])] = res["exit_r"]

    def resolve_r(r):
        if r["payoff_bucket"] == "continuation_confirmee":
            return r_map.get((r["ticker"], r["date_creation"]), r["r_realiste"])
        return r["r_realiste"]

    pop = pop.copy()
    pop["r_trailing"] = pop.apply(resolve_r, axis=1)

    if verbose:
        baseline_ev = pop["r_realiste"].mean()
        new_ev = pop["r_trailing"].mean()
        print(f"[{kind} {param}] EV réaliste (sans trailing) = {baseline_ev:+.4f} R | "
              f"EV avec trailing = {new_ev:+.4f} R (delta {new_ev - baseline_ev:+.4f} R)")

    return pop


def build_trades_trailing(pop):
    sub = pop.sort_values("date_creation").reset_index(drop=True)
    t0 = sub["date_creation"].iloc[0]
    slot_arrivals = [(d - t0).total_seconds() for d in sub["date_creation"]]

    trades = []
    for _, row in sub.iterrows():
        hold_seconds = (row["resolution_time_est"] - row["date_creation"]).total_seconds()
        sl_distance = abs(row["prix_entree"] - row["stop_loss_init"])
        trades.append({
            "ticker": row["ticker"],
            "outcome_r": row["r_trailing"],
            "sl_distance": sl_distance,
            "hold_seconds": hold_seconds,
            "date": row["date_creation"],
        })
    return sub, trades, slot_arrivals


DETAIL_CSV_PATH = "trailing_realistic_payoff_detail.csv"


def export_detail_csv(path=DETAIL_CSV_PATH):
    """Instantané statique (r_realiste + r_trailing, config verrouillée fixed/0.2x) pour
    les consommateurs qui ne doivent pas déclencher de nouvel appel réseau H1 à la volée
    (ex. analyse_live.py, appelé chaque semaine depuis la boucle live de app.py)."""
    pop = build_population_with_trailing("fixed", 0.2, verbose=True)
    pop.to_csv(path, index=False)
    print(f"Instantané enregistré dans {path} ({len(pop)} trades)")
    return pop


if __name__ == "__main__":
    export_detail_csv()
