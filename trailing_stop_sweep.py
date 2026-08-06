"""
Balayage de paramètres pour les 3 variantes de trailing stop post-TP2 (cf.
trailing_stop_variants.py, qui a montré qu'AUCUN réglage par défaut ne battait TP2 sec
au niveau EV). Avant d'abandonner la piste, teste plusieurs réglages par variante :
  A. ATR H1 et ATR D1 : multiplicateurs 1x, 1.5x, 2x, 3x
  B. Distance fixe (proportion de la distance SL initiale) : 0.5x, 1x, 1.5x, 2x
  C. %-retracement du gain depuis l'entrée : 10%, 20%, 30%, 40%

Référence directe : EV (= R moyen, tous gagnants) sur les 98 trades à continuation
TP2 confirmée, avec TP2 sec (rr_tp2, pas de trailing) recalculée SPÉCIFIQUEMENT sur ce
sous-ensemble de 98 (pas la population globale de 472, qui inclut aussi les perdants et
les autres gagnants -- comparaison directe demandée).
"""
import pandas as pd

import tp_sequence_analysis as tpseq
from tp2_realistic_payoff import build_realistic_payoff_population
from trailing_stop_variants import (
    compute_atr, find_tp2_touch, simulate_trailing, MIN_RR_TP1,
)

ATR_H1_MULTIPLIERS = [1.0, 1.5, 2.0, 3.0]
ATR_D1_MULTIPLIERS = [1.0, 1.5, 2.0, 3.0]
FIXED_MULTIPLIERS = [0.5, 1.0, 1.5, 2.0]
RETRACEMENT_PCTS = [0.10, 0.20, 0.30, 0.40]


def compute_atr_d1(candles):
    """ATR(14) journalier, calculé sur les bougies H1 rééchantillonnées en D1, puis
    reporté sur chaque bougie H1 via l'ATR du DERNIER jour calendaire COMPLET précédent
    (pas le jour en cours, pour éviter le lookahead)."""
    c = candles.sort_values("datetime").reset_index(drop=True).copy()
    c["date_only"] = c["datetime"].dt.date
    daily = c.groupby("date_only").agg(open=("open", "first"), high=("high", "max"),
                                        low=("low", "min"), close=("close", "last")).reset_index()
    prev_close = daily["close"].shift(1)
    tr = pd.concat([
        daily["high"] - daily["low"],
        (daily["high"] - prev_close).abs(),
        (daily["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    daily["atr_d1"] = tr.rolling(14, min_periods=1).mean()
    # décalage d'un jour : l'ATR du jour J n'est utilisable qu'à partir de J+1 (pas de lookahead)
    daily["atr_d1_shifted"] = daily["atr_d1"].shift(1).fillna(daily["atr_d1"].iloc[0])
    daily_map = dict(zip(daily["date_only"], daily["atr_d1_shifted"]))

    c["atr_d1"] = c["date_only"].map(daily_map)
    return c.drop(columns=["date_only"])


def make_stop_fn_atr(k, atr_col="atr"):
    def fn(extreme, entry, risk_distance, atr):
        is_long_direction = extreme >= entry
        a = atr if atr and atr > 0 else risk_distance * 0.1
        return extreme - k * a if is_long_direction else extreme + k * a
    return fn


def make_stop_fn_fixed(mult):
    def fn(extreme, entry, risk_distance, atr):
        is_long_direction = extreme >= entry
        return extreme - mult * risk_distance if is_long_direction else extreme + mult * risk_distance
    return fn


def make_stop_fn_retracement(pct):
    def fn(extreme, entry, risk_distance, atr):
        is_long_direction = extreme >= entry
        gain = abs(extreme - entry)
        return extreme - pct * gain if is_long_direction else extreme + pct * gain
    return fn


def simulate_trailing_with_atr_col(row, candles, stop_fn, label, atr_col):
    """Variante de simulate_trailing qui pioche l'ATR dans `atr_col` (atr H1 ou atr_d1)
    au lieu de la colonne 'atr' fixe -- même logique de déclenchement sinon."""
    entry, sl = row["prix_entree"], row["stop_loss_init"]
    risk_distance = abs(entry - sl)
    window, tp2_idx, is_long = find_tp2_touch(row, candles)
    if window is None:
        return None

    from trailing_stop_variants import HORIZON_MULTIPLIER, MAX_HORIZON_ABS
    tp2_time = window.loc[tp2_idx, "datetime"]
    delay_to_tp2 = tp2_time - row["date_creation"]
    horizon_limit = tp2_time + min(HORIZON_MULTIPLIER * delay_to_tp2, MAX_HORIZON_ABS)

    sub = window[(window.index >= tp2_idx) & (window["datetime"] <= horizon_limit)].reset_index(drop=True)
    if sub.empty:
        sub = window.iloc[[tp2_idx]].reset_index(drop=True)

    tp2_price = row["tp2_init"]
    touching_candle = sub.iloc[0]
    extreme = max(tp2_price, touching_candle["high"]) if is_long else min(tp2_price, touching_candle["low"])
    stop_level = stop_fn(extreme, entry, risk_distance, sub[atr_col].iloc[0] if atr_col in sub else None)

    exit_price = None
    for i, candle in sub.iterrows():
        if i == 0:
            continue
        if is_long:
            if candle["low"] <= stop_level:
                exit_price = stop_level
                break
            if candle["high"] > extreme:
                extreme = candle["high"]
                stop_level = stop_fn(extreme, entry, risk_distance, candle[atr_col] if atr_col in candle else None)
        else:
            if candle["high"] >= stop_level:
                exit_price = stop_level
                break
            if candle["low"] < extreme:
                extreme = candle["low"]
                stop_level = stop_fn(extreme, entry, risk_distance, candle[atr_col] if atr_col in candle else None)

    if exit_price is None:
        exit_price = sub["close"].iloc[-1]

    exit_r = (exit_price - entry) / risk_distance if is_long else (entry - exit_price) / risk_distance
    return exit_r


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
            candles = compute_atr(candles)
            candles = compute_atr_d1(candles)
            candles_by_symbol[symbol] = candles

    baseline_r = confirmed["rr_tp2"].mean()
    n_ref = len(confirmed)
    print(f"Référence directe -- TP2 sec sur les {n_ref} trades à continuation confirmée : "
          f"EV = {baseline_r:+.3f} R (= rr_tp2 moyen)\n")

    rows = []

    combos = []
    for k in ATR_H1_MULTIPLIERS:
        combos.append(("ATR_H1", k, "atr"))
    for k in ATR_D1_MULTIPLIERS:
        combos.append(("ATR_D1", k, "atr_d1"))

    for family, param, atr_col in combos:
        stop_fn = make_stop_fn_atr(param, atr_col)
        exit_rs = []
        for _, row in confirmed.iterrows():
            candles = candles_by_symbol.get(row["yahoo_symbol"])
            if candles is None:
                continue
            r = simulate_trailing_with_atr_col(row, candles, stop_fn, family, atr_col)
            if r is not None:
                exit_rs.append(r)
        mean_r = sum(exit_rs) / len(exit_rs) if exit_rs else float("nan")
        rows.append({"famille": family, "parametre": param, "n": len(exit_rs), "ev_r": mean_r,
                      "delta_vs_tp2_sec": mean_r - baseline_r})

    for mult in FIXED_MULTIPLIERS:
        stop_fn = make_stop_fn_fixed(mult)
        exit_rs = []
        for _, row in confirmed.iterrows():
            candles = candles_by_symbol.get(row["yahoo_symbol"])
            if candles is None:
                continue
            res = simulate_trailing(row, candles, stop_fn, "fixed")
            if res is not None:
                exit_rs.append(res["exit_r"])
        mean_r = sum(exit_rs) / len(exit_rs) if exit_rs else float("nan")
        rows.append({"famille": "Distance_fixe", "parametre": mult, "n": len(exit_rs), "ev_r": mean_r,
                      "delta_vs_tp2_sec": mean_r - baseline_r})

    for pct in RETRACEMENT_PCTS:
        stop_fn = make_stop_fn_retracement(pct)
        exit_rs = []
        for _, row in confirmed.iterrows():
            candles = candles_by_symbol.get(row["yahoo_symbol"])
            if candles is None:
                continue
            res = simulate_trailing(row, candles, stop_fn, "retracement")
            if res is not None:
                exit_rs.append(res["exit_r"])
        mean_r = sum(exit_rs) / len(exit_rs) if exit_rs else float("nan")
        rows.append({"famille": "Retracement_pct", "parametre": pct, "n": len(exit_rs), "ev_r": mean_r,
                      "delta_vs_tp2_sec": mean_r - baseline_r})

    sweep_df = pd.DataFrame(rows).sort_values("ev_r", ascending=False).reset_index(drop=True)
    sweep_df.to_csv("trailing_stop_sweep_summary.csv", index=False)

    print("=" * 100)
    print(f"TABLEAU COMPARATIF -- toutes combinaisons, classées par EV décroissante")
    print(f"(référence TP2 sec sur ce sous-ensemble de {n_ref} trades : {baseline_r:+.3f} R)")
    print("=" * 100)
    print(sweep_df.to_string(index=False))

    n_beats = (sweep_df["delta_vs_tp2_sec"] > 0).sum()
    print(f"\nCombinaisons qui BATTENT TP2 sec sur cette référence directe : {n_beats}/{len(sweep_df)}")
    if n_beats > 0:
        print("Meilleure(s) combinaison(s) :")
        print(sweep_df[sweep_df["delta_vs_tp2_sec"] > 0].to_string(index=False))

    print("\nRésumé enregistré dans trailing_stop_sweep_summary.csv")
    return sweep_df


if __name__ == "__main__":
    main()
