"""
Complete slippage_proxy_dukascopy.py (qui mesure prix Lutessia vs marche reel AU
MEME instant date_creation -- feed/precision, PAS la latence) avec l'impact du
delai de detection REEL du bot : app.py verifie les emails IMAP toutes les 60s
(time.sleep(60) dans la boucle principale, cf. app.py ligne 646) -- un signal
peut donc dormir jusqu'a ~60s avant d'etre vu, puis un temps de traitement/
execution MT5 marginal (connexion locale mesuree ~7ms, cf. trade_logger.py).

Ceci N'EST PAS une mesure sur des trades reellement executes (aucun n'existe,
trades_reels.csv vide) -- c'est une ESTIMATION ARCHITECTURALE : mouvement de
marche reel (ticks Dukascopy) survenu entre date_creation et date_creation+30s
(cas median, email arrive au milieu du cycle de poll) et +60s (pire cas, email
arrive juste apres un poll) sur le meme echantillon que le proxy de slippage
deja valide dans le projet.
"""
import random
import time

import numpy as np
import pandas as pd
from datetime import timedelta

from dukascopy_ticks import fetch_nearest_tick

POP_PATH = "trailing_realistic_payoff_detail.csv"
OFFSETS_SECONDS = [30, 60]


def main():
    df = pd.read_csv(POP_PATH)
    df["date_creation"] = pd.to_datetime(df["date_creation"])
    rng = random.Random(42)
    idx = list(df.index)
    rng.shuffle(idx)
    sample = idx[:250]  # echantillon -- cache deja largement chaud sur ces heures

    rows = []
    t0 = time.time()
    for n_done, i in enumerate(sample):
        row = df.loc[i]
        ticker = row["ticker"]
        direction = "buy" if row["tp1_init"] > row["prix_entree"] else "sell"
        sl_distance = abs(row["prix_entree"] - row["stop_loss_init"])
        if sl_distance == 0:
            continue
        base = fetch_nearest_tick(ticker, row["date_creation"].to_pydatetime())
        if base is None:
            continue
        _, base_ask, base_bid, _ = base
        base_ref = base_ask if direction == "buy" else base_bid

        rec = {"ticker": ticker, "direction": direction, "sl_distance": sl_distance, "r_trailing": row["r_trailing"]}
        for off in OFFSETS_SECONDS:
            later = fetch_nearest_tick(ticker, (row["date_creation"] + timedelta(seconds=off)).to_pydatetime())
            if later is None:
                rec[f"move_R_{off}s"] = np.nan
                continue
            _, l_ask, l_bid, _ = later
            l_ref = l_ask if direction == "buy" else l_bid
            # mouvement DEFAVORABLE si le prix a bouge contre la direction du trade
            # pendant l'attente (achat : prix monte = plus cher a entrer -> perte de R)
            move_price = (l_ref - base_ref) if direction == "buy" else (base_ref - l_ref)
            rec[f"move_R_{off}s"] = -move_price / sl_distance  # negatif = defavorable, en fraction de R
        rows.append(rec)
        if (n_done + 1) % 50 == 0:
            print(f"  {n_done+1}/{len(sample)} traites ({time.time()-t0:.0f}s)...")

    out = pd.DataFrame(rows)
    out.to_csv("latency_window_impact_detail.csv", index=False)
    print(f"\nEchantillon exploitable : {len(out)}/{len(sample)}")
    for off in OFFSETS_SECONDS:
        col = f"move_R_{off}s"
        vals = out[col].dropna()
        print(f"\n--- Fenetre +{off}s (equivaut a {'cas median' if off==30 else 'pire cas'} du polling IMAP 60s) ---")
        print(f"  n={len(vals)} | mouvement moyen = {vals.mean():+.4f}R | median = {vals.median():+.4f}R | "
              f"P10={vals.quantile(.1):+.4f}R | P90={vals.quantile(.9):+.4f}R")
        pips = vals * out.loc[vals.index, "sl_distance"] / out.loc[vals.index, "ticker"].apply(lambda t: 0.01 if t.endswith("/JPY") else 0.0001)
        print(f"  en pips : moyenne={pips.mean():+.2f} | median={pips.median():+.2f}")


if __name__ == "__main__":
    main()
