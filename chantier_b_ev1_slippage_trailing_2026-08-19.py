"""
Chantier B-EV, Chantier 1 (2026-08-19) -- quantifie le risque de slippage
sur le trailing serre 0,10xSL (gain +0,89% EV statique vs 0,15x deja
mesure, chantier_b1_trailing_sweep_2026-08-19.py) avant toute decision.

Slippage de reference : deja mesure empiriquement dans ce projet via
Dukascopy ticks sur l'ENTREE des trades forex (`slippage_proxy_dukascopy_
detail_631_2026-08-15.csv`, n=628, moyenne -0,939 pips, mediane -0,700
pips, ecart-type 3,602 pips, P5/P95 = -4,90/+2,10 pips). Pas une mesure
directe de slippage de SORTIE sur stop trailing (execution differente --
ordre stop declenche en mouvement rapide, potentiellement pire qu'une
entree limite), mais seule mesure empirique disponible dans le projet sur
CE broker/flux -- utilisee comme ordre de grandeur de reference, pas
comme verite exacte du mecanisme teste ici (limite signalee explicitement).

INDICES EXCLUS de cette analyse pips -- aucune mesure de slippage
empirique disponible pour DAX40/S&P500/NASDAQ100 dans ce projet (Dukascopy
teste uniquement sur les 14 paires FX), et la notion de "pip" ne
s'applique pas directement aux indices (points, pas pips) -- etendre
necessiterait une mesure Dukascopy separee sur indices, hors scope ici.

Methode :
1. Distance nominale du stop trailing (0,10x et 0,15x x distance SL
   initiale) convertie en pips, sur les 117 trades a continuation
   confirmee de B (dont ~structurellement une portion forex).
2. Sweep de slippage adverse S in [0, 0.5, 1, 1.5, 2, 3, 5] pips, applique
   UNIQUEMENT aux sorties reellement declenchees par le stop
   (exit_reason=='stop', pas les sorties par horizon -- celles-ci sortent
   au dernier close connu, pas un ordre stop reellement execute), sur le
   sous-ensemble FOREX de B (indices exclus, cf. ci-dessus).
3. EV(S) pour 0,10x et 0,15x, recherche du point de croisement.

N'importe pas ce script directement (convention du projet).
"""
import numpy as np
import pandas as pd

import tp_sequence_analysis as tpseq
from tp2_realistic_payoff import build_realistic_payoff_population
from trailing_stop_variants import compute_atr, simulate_trailing

INDEX_KEYWORDS = ["DAX40", "S&P500", "NASDAQ100"]
MAX_RR_B = 1.35
SLIPPAGE_SWEEP_PIPS = [0.0, 0.5, 0.939, 1.0, 1.5, 2.0, 3.0, 5.0]
FACTORS = [0.10, 0.15]


def make_stop_fn_fixed(mult):
    def fn(extreme, entry, risk_distance, atr):
        is_long_direction = extreme >= entry
        return extreme - mult * risk_distance if is_long_direction else extreme + mult * risk_distance
    return fn


def pip_size(ticker):
    return 0.01 if ticker.endswith("/JPY") else 0.0001


if __name__ == "__main__":
    print("=" * 70)
    print("Chantier B-EV-1 -- slippage sur trailing serre (0,10x vs 0,15x), FOREX seul")
    print("=" * 70)

    pop = build_realistic_payoff_population(min_rr=0.75, verbose=False)[0]
    is_index = pop["ticker"].str.contains("|".join(INDEX_KEYWORDS), case=False, na=False)
    pop = pop[~is_index].copy()
    pop = pop[pop["rr_tp1"] < MAX_RR_B].reset_index(drop=True)
    confirmed = pop[pop["payoff_bucket"] == "continuation_confirmee"].reset_index(drop=True)
    confirmed["yahoo_symbol"] = confirmed["ticker"].apply(tpseq.ticker_to_yahoo_symbol)
    print(f"\nPopulation B forex, continuation confirmee : n={len(confirmed)} "
          f"(indices exclus, pas de slippage empirique disponible pour eux)")

    unique_symbols = sorted(confirmed["yahoo_symbol"].unique())
    candles_by_symbol = {}
    for symbol in unique_symbols:
        candles = tpseq.fetch_h1_history(symbol, confirmed["date_creation"].min().to_pydatetime(),
                                          pd.Timestamp.utcnow().tz_localize(None).to_pydatetime())
        if candles is not None and not candles.empty:
            candles_by_symbol[symbol] = compute_atr(candles)

    # --- Etape 1 : distance nominale du stop en pips ---
    print("\n" + "=" * 70)
    print("ETAPE 1 -- distance nominale du stop trailing (pips), 0,10x vs 0,15x")
    print("=" * 70)
    for mult in FACTORS:
        dists_pips = []
        for _, row in confirmed.iterrows():
            risk_distance = abs(row["prix_entree"] - row["stop_loss_init"])
            trail_distance = mult * risk_distance
            dists_pips.append(trail_distance / pip_size(row["ticker"]))
        dists_pips = pd.Series(dists_pips)
        print(f"  {mult:.2f}xSL : moyenne={dists_pips.mean():.1f} pips | mediane={dists_pips.median():.1f} pips | "
              f"P25={dists_pips.quantile(.25):.1f} | P75={dists_pips.quantile(.75):.1f}")

    print(f"\n  Reference slippage empirique (entree, Dukascopy, n=628, projet) : "
          f"moyenne=-0,939 pips, mediane=-0,700 pips, P5=-4,90 / P95=+2,10 pips, ecart-type=3,602 pips")

    # --- Etape 2/3 : simulation exit_r pour chaque facteur, exit_reason tracked ---
    print("\n" + "=" * 70)
    print("ETAPE 2/3 -- sweep slippage adverse sur les sorties stop-declenchees")
    print("=" * 70)

    results_by_factor = {}
    for mult in FACTORS:
        stop_fn = make_stop_fn_fixed(mult)
        rows = []
        for _, row in confirmed.iterrows():
            candles = candles_by_symbol.get(row["yahoo_symbol"])
            if candles is None:
                continue
            res = simulate_trailing(row, candles, stop_fn, f"fixed_{mult}")
            if res is None:
                continue
            risk_distance = abs(row["prix_entree"] - row["stop_loss_init"])
            rows.append(dict(ticker=row["ticker"], exit_r=res["exit_r"], exit_reason=res["exit_reason"],
                              risk_distance=risk_distance, pip_sz=pip_size(row["ticker"])))
        results_by_factor[mult] = pd.DataFrame(rows)
        n_stop = (results_by_factor[mult]["exit_reason"] == "stop").sum()
        print(f"  {mult:.2f}xSL : n={len(results_by_factor[mult])}, sorties stop-declenchees={n_stop} "
              f"({n_stop/len(results_by_factor[mult])*100:.1f}%), sorties horizon={len(results_by_factor[mult])-n_stop}")

    print()
    sweep_rows = []
    for S in SLIPPAGE_SWEEP_PIPS:
        evs = {}
        for mult in FACTORS:
            df = results_by_factor[mult].copy()
            is_stop = df["exit_reason"] == "stop"
            slip_r = S * df["pip_sz"] / df["risk_distance"]
            df["exit_r_adj"] = np.where(is_stop, df["exit_r"] - slip_r, df["exit_r"])
            evs[mult] = df["exit_r_adj"].mean()
        delta = evs[0.10] - evs[0.15]
        flag = "0,10x reste MEILLEUR" if delta > 0 else "0,10x devient PIRE (inversion)"
        sweep_rows.append(dict(slippage_pips=S, ev_010=evs[0.10], ev_015=evs[0.15], delta=delta, flag=flag))
        print(f"  slippage={S:.3f} pips : EV(0,10x)={evs[0.10]:+.4f}R | EV(0,15x)={evs[0.15]:+.4f}R | "
              f"delta={delta:+.4f}R -- {flag}")

    df_sweep = pd.DataFrame(sweep_rows)
    df_sweep.to_csv("chantier_b_ev1_slippage_sweep_2026-08-19.csv", index=False)

    inversion = df_sweep[df_sweep["delta"] <= 0]
    print("\n" + "=" * 70)
    if len(inversion) > 0:
        seuil = inversion.iloc[0]["slippage_pips"]
        print(f"VERDICT : le gain de 0,10x s'annule/s'inverse a partir de ~{seuil:.2f} pips de slippage adverse.")
    else:
        print(f"VERDICT : 0,10x reste meilleur que 0,15x sur toute la plage testee "
              f"(jusqu'a {SLIPPAGE_SWEEP_PIPS[-1]:.1f} pips).")
