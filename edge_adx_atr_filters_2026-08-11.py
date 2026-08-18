"""
Tests 2/3/4 (08/11) : filtres d'ENTREE ADX et ATR sur l'edge Lutessia,
population de reference (721 trades, historique_lutessia_15k_force.csv,
rr_tp1>=1,25, trailing 0,15xSL post-TP2 -- AUCUN de ces parametres deja
verrouilles n'est retouche ici, cf. registre_strategie_trading.md).

Contrainte de couverture IMPORTANTE (meme limite deja documentee pour la
verification TP1->TP2, cf. rr_threshold_test.py) : yfinance H1 ne couvre
que les ~729 derniers jours (YFINANCE_MAX_LOOKBACK_DAYS). Les trades
anterieurs a cette fenetre n'ont AUCUNE bougie disponible pour calculer
ADX/ATR a l'entree -- ils sont exclus, pas approximes. Or le walk-forward
deja fait sur cet edge (registre §2.10) a trouve une tendance
CHRONOLOGIQUE CROISSANTE forte (EV ~0R en 2022 -> +1,3-2,6R en 2025-2026)
-- restreindre a la fenetre H1 recente introduit donc un biais de
selection temporelle enorme si on compare a la population COMPLETE. Tous
les tests ci-dessous comparent le filtre au baseline SUR LE MEME
SOUS-ENSEMBLE couvert (pas la population totale), pour isoler l'effet du
filtre de l'effet de la fenetre temporelle.

ADX(14) : implementation Wilder standard via EWM(alpha=1/14), pas de
lib externe (pas de dependance ta-lib dans ce projet). ATR(14) : reutilise
trailing_stop_variants.compute_atr (deja utilise partout dans le projet,
moyenne mobile simple, PAS Wilder -- coherence avec le reste du repo
prime sur l'exactitude theorique du nom "ATR").

N'importe pas ce script directement (convention du projet).
"""
import math
import random

import numpy as np
import pandas as pd

import tp_sequence_analysis as tpseq
from trailing_payoff_population import build_population_with_trailing
from trailing_stop_variants import compute_atr, MIN_RR_TP1

N_BOOTSTRAP = 2000
ADX_THRESHOLDS = [20, 25, 30]
ATR_RATIO_BOUNDS = {
    "exclure_extremes_0.5-2.0": (0.5, 2.0),
    "regime_modere_0.7-1.5": (0.7, 1.5),
    "exclure_faible_vol_moins_0.7": (0.7, float("inf")),
    "exclure_forte_vol_plus_1.5": (0.0, 1.5),
}


def compute_adx(candles, period=14):
    c = candles.sort_values("datetime").reset_index(drop=True).copy()
    up_move = c["high"].diff()
    down_move = -c["low"].diff()
    plus_dm = ((up_move > down_move) & (up_move > 0)).astype(float) * up_move.clip(lower=0)
    minus_dm = ((down_move > up_move) & (down_move > 0)).astype(float) * down_move.clip(lower=0)
    prev_close = c["close"].shift(1)
    tr = pd.concat([
        c["high"] - c["low"],
        (c["high"] - prev_close).abs(),
        (c["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)

    atr_wilder = tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    plus_dm_s = plus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    minus_dm_s = minus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    plus_di = 100 * plus_dm_s / atr_wilder
    minus_di = 100 * minus_dm_s / atr_wilder
    di_sum = (plus_di + minus_di).replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / di_sum
    c["adx"] = dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    return c


def build_population_with_indicators(min_rr=MIN_RR_TP1):
    pop = build_population_with_trailing("fixed", 0.15, min_rr=min_rr, verbose=True)
    pop = pop.copy()
    pop["yahoo_symbol"] = pop["ticker"].apply(tpseq.ticker_to_yahoo_symbol)

    unique_symbols = sorted(pop["yahoo_symbol"].dropna().unique())
    indic_by_symbol = {}
    print(f"Chargement bougies H1 + calcul ADX/ATR pour {len(unique_symbols)} tickers...")
    for symbol in unique_symbols:
        candles = tpseq.fetch_h1_history(symbol, pop["date_creation"].min().to_pydatetime(),
                                          pd.Timestamp.utcnow().tz_localize(None).to_pydatetime())
        if candles is None or candles.empty:
            continue
        c = compute_atr(candles)
        c = compute_adx(c)
        c["atr_ref_median"] = c["atr"].median()
        c["atr_ratio"] = c["atr"] / c["atr_ref_median"]
        indic_by_symbol[symbol] = c.sort_values("datetime").reset_index(drop=True)

    adx_vals, atr_ratio_vals, has_indic = [], [], []
    for _, row in pop.iterrows():
        candles = indic_by_symbol.get(row["yahoo_symbol"])
        if candles is None:
            adx_vals.append(np.nan)
            atr_ratio_vals.append(np.nan)
            has_indic.append(False)
            continue
        eligible = candles[candles["datetime"] <= row["date_creation"]]
        if eligible.empty or eligible["adx"].isna().all():
            adx_vals.append(np.nan)
            atr_ratio_vals.append(np.nan)
            has_indic.append(False)
            continue
        last = eligible.iloc[-1]
        adx_vals.append(last["adx"])
        atr_ratio_vals.append(last["atr_ratio"])
        has_indic.append(not pd.isna(last["adx"]))

    pop["adx_at_entry"] = adx_vals
    pop["atr_ratio_at_entry"] = atr_ratio_vals
    pop["has_indicators"] = has_indic
    return pop


def wilson_ci(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z ** 2 / n
    center = (p + z ** 2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / denom
    return (center - half, center + half)


def bootstrap_p_annee_neg(r_values, dates, n_boot=N_BOOTSTRAP, seed=12345):
    """Rééchantillonnage par bloc (avec remise) de la sequence de R pour
    estimer P(somme R sur ~1 an < 0). Trades/an estime depuis la plage
    reelle des dates du sous-ensemble teste (pas un chiffre global fixe)."""
    r_values = np.asarray(r_values, dtype=float)
    n = len(r_values)
    if n < 5:
        return float("nan"), 0
    span_days = max(1.0, (dates.max() - dates.min()).days)
    trades_per_year = n / span_days * 365.25
    trades_per_year = max(5, int(round(trades_per_year)))
    rng = random.Random(seed)
    n_neg = 0
    for _ in range(n_boot):
        draw = [r_values[rng.randrange(n)] for _ in range(trades_per_year)]
        if sum(draw) < 0:
            n_neg += 1
    return n_neg / n_boot * 100, trades_per_year


def summarize_subset(label, sub, full_covered_n):
    n = len(sub)
    wins = (sub["statut_final"] == "OBJECTIF ATTEINT").sum()
    winrate = wins / n * 100 if n else float("nan")
    lo, hi = wilson_ci(wins, n)
    ev = sub["r_trailing"].mean() if n else float("nan")
    p_neg, tpy = bootstrap_p_annee_neg(sub["r_trailing"].values, sub["date_creation"])
    return dict(config=label, n=n, n_exclus=full_covered_n - n, winrate_pct=winrate,
                winrate_ic95_lo=lo * 100 if n else float("nan"), winrate_ic95_hi=hi * 100 if n else float("nan"),
                ev_r=ev, p_annee_negative_pct=p_neg, trades_par_an_estime=tpy)


def subperiod_check(sub, label, n_splits=2):
    sub_sorted = sub.sort_values("date_creation").reset_index(drop=True)
    n = len(sub_sorted)
    if n < 20:
        return [{"config": label, "sous_periode": "n_insuffisant", "n": n, "ev_r": float("nan")}]
    rows = []
    chunk = n // n_splits
    for i in range(n_splits):
        start = i * chunk
        end = (i + 1) * chunk if i < n_splits - 1 else n
        part = sub_sorted.iloc[start:end]
        rows.append({"config": label, "sous_periode": f"{i+1}/{n_splits}", "n": len(part),
                     "ev_r": part["r_trailing"].mean(),
                     "date_debut": str(part["date_creation"].min().date()),
                     "date_fin": str(part["date_creation"].max().date())})
    return rows


if __name__ == "__main__":
    pop = build_population_with_indicators(min_rr=1.25)
    print(f"\nPopulation totale : {len(pop)} trades")
    covered = pop[pop["has_indicators"]].copy()
    print(f"Sous-ensemble avec indicateurs ADX/ATR disponibles (couverture H1) : "
          f"{len(covered)}/{len(pop)} ({len(covered)/len(pop)*100:.1f}%)")
    print(f"Plage de dates du sous-ensemble couvert : {covered['date_creation'].min()} -> "
          f"{covered['date_creation'].max()}")
    print(f"Plage de dates population totale : {pop['date_creation'].min()} -> {pop['date_creation'].max()}")

    rows = []
    subperiod_rows = []

    # --- Baseline (sous-ensemble couvert, AUCUN filtre) ---
    baseline_row = summarize_subset("baseline_couvert_sans_filtre", covered, len(covered))
    rows.append(baseline_row)
    subperiod_rows += subperiod_check(covered, "baseline_couvert_sans_filtre")

    # --- Test 2 : filtre ADX ---
    adx_ok = covered.dropna(subset=["adx_at_entry"])
    for thr in ADX_THRESHOLDS:
        sub = adx_ok[adx_ok["adx_at_entry"] >= thr]
        label = f"ADX>={thr}"
        rows.append(summarize_subset(label, sub, len(covered)))
        subperiod_rows += subperiod_check(sub, label)

    # --- Test 3 : filtre ATR (ratio vs mediane historique du ticker) ---
    atr_ok = covered.dropna(subset=["atr_ratio_at_entry"])
    for label, (lo, hi) in ATR_RATIO_BOUNDS.items():
        sub = atr_ok[(atr_ok["atr_ratio_at_entry"] >= lo) & (atr_ok["atr_ratio_at_entry"] <= hi)]
        rows.append(summarize_subset(f"ATR_{label}", sub, len(covered)))
        subperiod_rows += subperiod_check(sub, f"ATR_{label}")

    out = pd.DataFrame(rows)
    out.to_csv("edge_adx_atr_filters_summary.csv", index=False)
    pd.DataFrame(subperiod_rows).to_csv("edge_adx_atr_filters_subperiods.csv", index=False)
    pop.to_csv("edge_adx_atr_population_detail.csv", index=False)

    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", None)
    print("\n=== RESUME ===")
    print(out.to_string(index=False))
    print("\n=== SOUS-PERIODES ===")
    print(pd.DataFrame(subperiod_rows).to_string(index=False))
