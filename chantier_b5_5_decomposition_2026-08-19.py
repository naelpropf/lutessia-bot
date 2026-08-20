"""
Chantier B5-5 (2026-08-19) -- decompose 2 signaux deja confirmes sur B
complet (trailing 0,10xSL et filtre ADX>32,27) separement sur B-forex et
B-indices, pour verifier si l'un des deux porte tout l'effet.

Reutilise chantier_b1_trailing_sweep_2026-08-19.py (deja corrige, bug
rr_tp1>=1.0 flottant) et chantier_b_ev3_segmentation_2026-08-19.py.

N'importe pas ce script directement (convention du projet).
"""
import importlib.util

import numpy as np
import pandas as pd

import tp_sequence_analysis as tpseq
from trailing_stop_variants import compute_atr, simulate_trailing

T1_SCRIPT = "chantier_b1_trailing_sweep_2026-08-19.py"
spec = importlib.util.spec_from_file_location("t1_b55", T1_SCRIPT)
t1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t1)

ADX_SCRIPT = "edge_adx_atr_filters_2026-08-11.py"
spec2 = importlib.util.spec_from_file_location("adx_b55", ADX_SCRIPT)
adx_mod = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(adx_mod)

INDEX_KEYWORDS = ["DAX40", "S&P500", "NASDAQ100"]


if __name__ == "__main__":
    print("=" * 78)
    print("PARTIE 1 -- trailing 0,10x vs 0,15x, decompose forex vs indices")
    print("=" * 78)

    pop_fx = t1.load_forex_b()
    pop_fx["yahoo_symbol"] = pop_fx["ticker"].apply(tpseq.ticker_to_yahoo_symbol)
    pop_idx, candles_idx = t1.load_index_population_full()

    keep_cols = ["date_creation", "ticker", "rr_tp1", "rr_tp2", "statut_final",
                 "payoff_bucket", "r_realiste", "prix_entree", "stop_loss_init",
                 "tp1_init", "tp2_init", "yahoo_symbol"]
    for subset_name, sub_pop, candles_pre in [("FOREX seul", pop_fx[keep_cols], {}),
                                                ("INDICES seul", pop_idx[keep_cols], candles_idx)]:
        confirmed = sub_pop[sub_pop["payoff_bucket"] == "continuation_confirmee"].reset_index(drop=True)
        print(f"\n--- {subset_name} : n_confirmes={len(confirmed)} ---")
        if len(confirmed) < 5:
            print("  n trop petit -- ininterpretable")
            continue
        candles_by_symbol = dict(candles_pre)
        unique_symbols = sorted(confirmed["yahoo_symbol"].unique())
        start_dt = confirmed["date_creation"].min()
        end_dt = pd.Timestamp.utcnow().tz_localize(None)
        for symbol in unique_symbols:
            if symbol in candles_by_symbol:
                continue
            candles = tpseq.fetch_h1_history(symbol, start_dt.to_pydatetime(), end_dt.to_pydatetime())
            if candles is not None and not candles.empty:
                candles_by_symbol[symbol] = compute_atr(candles)

        baseline_ev_full = sub_pop["r_realiste"].mean()
        for mult in [0.10, 0.15]:
            stop_fn = t1.make_stop_fn_fixed(mult)
            exit_rs, tickers, dates = [], [], []
            for _, row in confirmed.iterrows():
                candles = candles_by_symbol.get(row["yahoo_symbol"])
                if candles is None:
                    continue
                res = simulate_trailing(row, candles, stop_fn, f"fixed_{mult}")
                if res is None:
                    continue
                exit_rs.append(res["exit_r"]); tickers.append(row["ticker"]); dates.append(row["date_creation"])
            exit_rs = pd.Series(exit_rs)
            r_map = dict(zip(zip(tickers, dates), exit_rs))
            r_new = sub_pop.apply(
                lambda r: r_map.get((r["ticker"], r["date_creation"]), r["r_realiste"])
                if r["payoff_bucket"] == "continuation_confirmee" else r["r_realiste"], axis=1)
            ev_full = r_new.mean()
            print(f"  facteur={mult:.2f}xSL : n_confirmes_traites={len(exit_rs)} "
                  f"EV(confirmes)={exit_rs.mean():+.4f}R | EV(population complete)={ev_full:+.4f}R "
                  f"(delta vs baseline {ev_full-baseline_ev_full:+.4f}R)")

    print("\n" + "=" * 78)
    print("PARTIE 2 -- filtre ADX>32,27, decompose forex vs indices")
    print("=" * 78)

    ISO_SCRIPT = "chantier_strategie_b_isolation_indices_2026-08-18.py"
    spec3 = importlib.util.spec_from_file_location("iso_b55", ISO_SCRIPT)
    iso = importlib.util.module_from_spec(spec3)
    spec3.loader.exec_module(iso)

    pop_B = iso.build_pop_B("tout_indices")
    r_out = np.where(pop_B["statut_final"] == "OBJECTIF ATTEINT", pop_B["r_trailing"], -1.0)
    pop_B = pop_B.copy()
    pop_B["r"] = r_out
    pop_B["yahoo_symbol"] = pop_B["ticker"].apply(tpseq.ticker_to_yahoo_symbol)
    unique_symbols = sorted(pop_B["yahoo_symbol"].dropna().unique())
    indic_by_symbol = {}
    for symbol in unique_symbols:
        candles = tpseq.fetch_h1_history(symbol, pop_B["date_creation"].min().to_pydatetime(),
                                          pd.Timestamp.utcnow().tz_localize(None).to_pydatetime())
        if candles is None or candles.empty:
            continue
        c = adx_mod.compute_atr(candles)
        c = adx_mod.compute_adx(c)
        indic_by_symbol[symbol] = c.sort_values("datetime").reset_index(drop=True)
    adx_vals = []
    for _, row in pop_B.iterrows():
        candles = indic_by_symbol.get(row["yahoo_symbol"])
        if candles is None:
            adx_vals.append(np.nan); continue
        prior = candles[candles["datetime"] <= row["date_creation"]]
        adx_vals.append(prior["adx"].iloc[-1] if not prior.empty and "adx" in prior else np.nan)
    pop_B["adx_at_entry"] = adx_vals
    covered = pop_B.dropna(subset=["adx_at_entry"]).copy()

    is_index = covered["ticker"].str.contains("|".join(INDEX_KEYWORDS), case=False, na=False)
    ADX_TH = 32.268
    for label, sub in [("FOREX seul", covered[~is_index]), ("INDICES seul", covered[is_index])]:
        print(f"\n--- {label} : n_couvert={len(sub)} ---")
        if len(sub) < 10:
            print("  n trop petit -- ininterpretable")
            continue
        high = sub[sub["adx_at_entry"] > ADX_TH]
        low = sub[sub["adx_at_entry"] <= ADX_TH]
        print(f"  ADX>{ADX_TH:.2f} : n={len(high):3d} EV={high['r'].mean():+.3f}R" if len(high) else
              f"  ADX>{ADX_TH:.2f} : n=0")
        print(f"  ADX<={ADX_TH:.2f} : n={len(low):3d} EV={low['r'].mean():+.3f}R" if len(low) else
              f"  ADX<={ADX_TH:.2f} : n=0")
