"""
Simule 3 variantes de trailing stop APRÈS TP2 (position gardée pleine taille, pas de
clôture à TP2) sur les 98 trades à continuation TP1->TP2 CONFIRMÉE (cf.
tp2_realistic_payoff.py / trailing_stop_vigilance_check.py, qui a montré un potentiel
non marginal : 81.6% de ces trades avec un extra >= +1R sur un horizon borné réaliste).

Horizon de recherche borné à min(3x délai création->TP2, 30 jours) -- même choix que le
garde-fou, pour éviter de mesurer une dérive de prix sur des mois/années sans rapport
avec une position réellement tenue ouverte.

Convention de déclenchement (par bougie H1, à partir de la bougie où TP2 est touché) :
  1. on vérifie D'ABORD si le niveau de stop COURANT (fixé à la bougie précédente) est
     franchi par le low (long) / high (short) de la bougie -> sortie à ce niveau ;
  2. SEULEMENT si le stop n'a pas été touché, on mémorise le nouvel extremum favorable
     (high pour long / low pour short) et on recalcule le stop suivant selon la règle.
  Ordre volontairement conservateur (le stop protège la bougie AVANT d'être remonté).

Si l'horizon est atteint sans déclenchement, sortie au dernier prix de clôture connu
dans l'horizon (PAS au sommet -- éviterait de refaire l'erreur du MFE non borné).

Variantes :
  A. ATR(14, H1) : stop = extremum - k * ATR_courant, k=2.5
  B. Distance fixe proportionnelle au risque initial : stop = extremum - 1.0 * risk_distance (1R)
  C. %-retracement du gain ouvert depuis l'entrée : stop = extremum - 0.30 * (extremum - entry)
"""
import numpy as np
import pandas as pd

import tp_sequence_analysis as tpseq
from tp2_realistic_payoff import build_realistic_payoff_population

MIN_RR_TP1 = 1.5
MAX_HORIZON_ABS = pd.Timedelta(days=30)
HORIZON_MULTIPLIER = 3

ATR_PERIOD = 14
ATR_K = 2.5
FIXED_TRAIL_R = 1.0
RETRACEMENT_PCT = 0.30


def compute_atr(candles, period=ATR_PERIOD):
    c = candles.sort_values("datetime").reset_index(drop=True)
    prev_close = c["close"].shift(1)
    tr = pd.concat([
        c["high"] - c["low"],
        (c["high"] - prev_close).abs(),
        (c["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    c["atr"] = tr.rolling(period, min_periods=1).mean()
    return c


def find_tp2_touch(row, candles):
    entry, sl, tp1, tp2 = row["prix_entree"], row["stop_loss_init"], row["tp1_init"], row["tp2_init"]
    is_long = tp1 > entry
    creation = row["date_creation"]
    window = candles[candles["datetime"] >= creation].sort_values("datetime").reset_index(drop=True)
    if window.empty:
        return None, None, None
    hits = window[window["high"] >= tp2] if is_long else window[window["low"] <= tp2]
    if hits.empty:
        return None, None, None
    tp2_idx = hits.index[0]
    return window, tp2_idx, is_long


def simulate_trailing(row, candles, stop_fn, label):
    """stop_fn(extreme_price, entry, risk_distance, atr_at_step) -> niveau de stop"""
    entry, sl = row["prix_entree"], row["stop_loss_init"]
    risk_distance = abs(entry - sl)

    window, tp2_idx, is_long = find_tp2_touch(row, candles)
    if window is None:
        return None

    tp2_time = window.loc[tp2_idx, "datetime"]
    delay_to_tp2 = tp2_time - row["date_creation"]
    horizon_limit = tp2_time + min(HORIZON_MULTIPLIER * delay_to_tp2, MAX_HORIZON_ABS)

    sub = window[(window.index >= tp2_idx) & (window["datetime"] <= horizon_limit)].reset_index(drop=True)
    if sub.empty:
        sub = window.iloc[[tp2_idx]].reset_index(drop=True)

    # L'EXTREMUM initial doit tenir compte du fait que la bougie qui touche TP2 peut
    # elle-même avoir continué bien au-delà de tp2_init avant sa clôture (médiane +0.30R,
    # moyenne +0.58R sur les 98 trades) -- l'ignorer donnerait un avantage artificiel et
    # croissant aux multiplicateurs de plus en plus petits (un "cadeau" fixe qui pèse
    # proportionnellement plus lourd quand la distance de trailing rétrécit), sans rapport
    # avec la qualité réelle de la règle de trailing testée.
    tp2_price = row["tp2_init"]
    touching_candle = sub.iloc[0]
    extreme = max(tp2_price, touching_candle["high"]) if is_long else min(tp2_price, touching_candle["low"])
    stop_level = stop_fn(extreme, entry, risk_distance, sub["atr"].iloc[0] if "atr" in sub else None)

    exit_price = None
    exit_reason = "horizon"
    for i, candle in sub.iterrows():
        if i == 0:
            continue  # bougie de touche de TP2 elle-même : le stop initial ne peut pas encore avoir été franchi
        if is_long:
            if candle["low"] <= stop_level:
                exit_price = stop_level
                exit_reason = "stop"
                break
            if candle["high"] > extreme:
                extreme = candle["high"]
                stop_level = stop_fn(extreme, entry, risk_distance, candle["atr"] if "atr" in candle else None)
        else:
            if candle["high"] >= stop_level:
                exit_price = stop_level
                exit_reason = "stop"
                break
            if candle["low"] < extreme:
                extreme = candle["low"]
                stop_level = stop_fn(extreme, entry, risk_distance, candle["atr"] if "atr" in candle else None)

    if exit_price is None:
        exit_price = sub["close"].iloc[-1]
        exit_reason = "horizon"

    exit_r = (exit_price - entry) / risk_distance if is_long else (entry - exit_price) / risk_distance
    return {
        "variant": label, "tp2_time": tp2_time, "exit_reason": exit_reason,
        "exit_price": exit_price, "exit_r": exit_r, "peak_r": (extreme - entry) / risk_distance if is_long
                     else (entry - extreme) / risk_distance,
        "n_candles": len(sub),
    }


def stop_fn_atr(extreme, entry, risk_distance, atr):
    is_long_direction = extreme >= entry
    atr = atr if atr and atr > 0 else risk_distance * 0.1  # filet de sécurité si ATR indisponible
    return extreme - ATR_K * atr if is_long_direction else extreme + ATR_K * atr


def stop_fn_fixed(extreme, entry, risk_distance, atr):
    is_long_direction = extreme >= entry
    return extreme - FIXED_TRAIL_R * risk_distance if is_long_direction else extreme + FIXED_TRAIL_R * risk_distance


def stop_fn_retracement(extreme, entry, risk_distance, atr):
    is_long_direction = extreme >= entry
    gain = abs(extreme - entry)
    return extreme - RETRACEMENT_PCT * gain if is_long_direction else extreme + RETRACEMENT_PCT * gain


VARIANTS = {
    "A_atr": stop_fn_atr,
    "B_distance_fixe": stop_fn_fixed,
    "C_retracement_pct": stop_fn_retracement,
}


def main():
    pop, _ = build_realistic_payoff_population(min_rr=MIN_RR_TP1, verbose=False)
    confirmed = pop[pop["payoff_bucket"] == "continuation_confirmee"].copy().reset_index(drop=True)
    confirmed["yahoo_symbol"] = confirmed["ticker"].apply(tpseq.ticker_to_yahoo_symbol)

    unique_symbols = sorted(confirmed["yahoo_symbol"].unique())
    candles_by_symbol = {}
    for symbol in unique_symbols:
        candles = tpseq.fetch_h1_history(symbol, confirmed["date_creation"].min().to_pydatetime(),
                                          pd.Timestamp.utcnow().tz_localize(None).to_pydatetime())
        if candles is not None and not candles.empty:
            candles_by_symbol[symbol] = compute_atr(candles)

    all_rows = []
    for label, stop_fn in VARIANTS.items():
        for _, row in confirmed.iterrows():
            candles = candles_by_symbol.get(row["yahoo_symbol"])
            if candles is None:
                continue
            res = simulate_trailing(row, candles, stop_fn, label)
            if res is None:
                continue
            all_rows.append({
                "ticker": row["ticker"], "date_creation": row["date_creation"],
                "rr_tp2": row["rr_tp2"], **res,
            })

    detail_df = pd.DataFrame(all_rows)
    detail_df.to_csv("trailing_stop_variants_detail.csv", index=False)

    print(f"Trades à continuation confirmée traités : {len(confirmed)}")
    print("\n" + "=" * 100)
    print("COMPARAISON DES 3 VARIANTES DE TRAILING (sur les 98 trades à continuation confirmée)")
    print("=" * 100)
    for label in VARIANTS:
        sub = detail_df[detail_df["variant"] == label]
        n = len(sub)
        mean_r = sub["exit_r"].mean()
        mean_rr_tp2 = sub["rr_tp2"].mean()
        mean_gain_vs_tp2 = (sub["exit_r"] - sub["rr_tp2"]).mean()
        pct_beats_tp2 = (sub["exit_r"] > sub["rr_tp2"]).mean() * 100
        pct_worse_tp2 = (sub["exit_r"] < sub["rr_tp2"] - 0.05).mean() * 100
        n_stop_triggered = (sub["exit_reason"] == "stop").sum()
        print(f"\n--- Variante {label} ---")
        print(f"  N = {n} | R de sortie moyen = {mean_r:+.2f}R (vs rr_tp2 moyen {mean_rr_tp2:+.2f}R) | "
              f"gain moyen vs TP2 sec = {mean_gain_vs_tp2:+.2f}R")
        print(f"  % trades où le trailing FAIT MIEUX que TP2 sec : {pct_beats_tp2:.1f}%")
        print(f"  % trades où le trailing fait MOINS BIEN que TP2 sec (whipsaw)  : {pct_worse_tp2:.1f}%")
        print(f"  Stop déclenché : {n_stop_triggered}/{n} | Horizon atteint sans stop : {n - n_stop_triggered}/{n}")

    # EV globale sur la population totale (472 trades) si on remplace le payoff des 98
    # trades à continuation confirmée par le résultat de chaque variante de trailing
    # (les 374 autres trades gardent r_realiste inchangé).
    total_n = len(pop)
    baseline_ev = pop["r_realiste"].mean()
    print("\n" + "=" * 100)
    print("IMPACT SUR L'EV GLOBALE (population totale, 472 trades)")
    print("=" * 100)
    print(f"EV baseline (payoff TP2 réaliste actuel, sans trailing) : {baseline_ev:+.3f} R")
    for label in VARIANTS:
        sub = detail_df[detail_df["variant"] == label].set_index(detail_df[detail_df["variant"] == label].index)
        r_map = dict(zip(zip(sub["ticker"], sub["date_creation"]), sub["exit_r"]))
        r_new = pop.apply(
            lambda r: r_map.get((r["ticker"], r["date_creation"]), r["r_realiste"])
            if r["payoff_bucket"] == "continuation_confirmee" else r["r_realiste"],
            axis=1,
        )
        ev_new = r_new.mean()
        print(f"  Variante {label:20s} : EV = {ev_new:+.3f} R (delta vs baseline {ev_new - baseline_ev:+.4f} R)")

    print("\nDétail enregistré dans trailing_stop_variants_detail.csv")
    return detail_df


if __name__ == "__main__":
    main()
