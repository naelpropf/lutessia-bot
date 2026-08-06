"""
Proxy de slippage RÉEL (remplace l'ancienne analyse à résolution H1, jugée
insuffisante) : compare le prix Lutessia (prix_entree, précision affichée à la
minute) au tick bid/ask Dukascopy le plus proche du timestamp exact du signal
(date_creation, précision seconde), sur toute la population de référence
(rr_tp1>=1.5, 472 trades).

Convention : direction du trade déduite de tp1_init vs prix_entree (buy si
tp1_init > prix_entree, sinon sell). Slippage = écart entre le prix Lutessia et le
prix RÉELLEMENT disponible côté broker au même instant (ask pour un achat, bid pour
une vente -- le côté du carnet qu'on paierait réellement à l'entrée) :
  slippage = prix_lutessia - prix_reel_disponible (achat)
  slippage = prix_reel_disponible - prix_lutessia (vente)
Positif = le prix Lutessia était MEILLEUR que ce qui était réellement exécutable
(la vraie exécution aurait coûté plus cher) ; négatif = Lutessia annonçait un prix
plus défavorable que ce qui était dispo (marge de sécurité).
"""
import pandas as pd

from dukascopy_ticks import fetch_nearest_tick

POP_PATH = "trailing_realistic_payoff_detail.csv"
MAX_DELTA_SECONDS_WARN = 30


def main():
    df = pd.read_csv(POP_PATH)
    df["date_creation"] = pd.to_datetime(df["date_creation"])

    rows = []
    missing = 0
    for i, row in df.iterrows():
        result = fetch_nearest_tick(row["ticker"], row["date_creation"].to_pydatetime())
        if result is None:
            missing += 1
            continue
        tick_dt, ask, bid, delta = result
        direction = "buy" if row["tp1_init"] > row["prix_entree"] else "sell"
        ref_price = ask if direction == "buy" else bid
        if direction == "buy":
            slippage = row["prix_entree"] - ref_price
        else:
            slippage = ref_price - row["prix_entree"]

        pip_size = 0.01 if row["ticker"].endswith("/JPY") else 0.0001
        slippage_pips = slippage / pip_size

        rows.append({
            "ticker": row["ticker"], "date_creation": row["date_creation"], "direction": direction,
            "prix_lutessia": row["prix_entree"], "prix_reel": ref_price,
            "slippage": slippage, "slippage_pips": slippage_pips,
            "delta_secondes": delta, "sl_distance": abs(row["prix_entree"] - row["stop_loss_init"]),
            "r_trailing": row["r_trailing"],
        })
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(df)} trades traités...")

    result_df = pd.DataFrame(rows)
    result_df.to_csv("slippage_proxy_dukascopy_detail.csv", index=False)

    print(f"\n{'='*100}")
    print(f"PROXY DE SLIPPAGE RÉEL (ticks Dukascopy) -- {len(result_df)}/{len(df)} trades "
          f"({missing} sans tick trouvé)")
    print(f"{'='*100}")

    print(f"\nPrécision du matching temporel (delta entre date_creation et le tick le plus proche) :")
    print(f"  Médiane : {result_df['delta_secondes'].median():.2f}s | Moyenne : {result_df['delta_secondes'].mean():.2f}s | "
          f"P95 : {result_df['delta_secondes'].quantile(0.95):.2f}s | Max : {result_df['delta_secondes'].max():.2f}s")
    n_suspect = (result_df["delta_secondes"] > MAX_DELTA_SECONDS_WARN).sum()
    if n_suspect:
        print(f"  [AVERTISSEMENT] {n_suspect} trades avec un delta > {MAX_DELTA_SECONDS_WARN}s "
              f"(zone de faible liquidité tick probable, à examiner si besoin)")

    print(f"\nSlippage en pips (positif = prix Lutessia meilleur que le prix réel dispo) :")
    print(f"  Moyenne : {result_df['slippage_pips'].mean():+.3f} pips")
    print(f"  Médiane : {result_df['slippage_pips'].median():+.3f} pips")
    print(f"  Écart-type : {result_df['slippage_pips'].std():.3f} pips")
    print(f"  P5 / P95 : {result_df['slippage_pips'].quantile(0.05):+.3f} / {result_df['slippage_pips'].quantile(0.95):+.3f} pips")

    # Slippage en % de la distance au SL (impact relatif sur le risque du trade)
    result_df["slippage_pct_sl"] = result_df["slippage"].abs() / result_df["sl_distance"] * 100
    print(f"\nSlippage en % de la distance au stop (impact relatif sur le risque) :")
    print(f"  Moyenne : {result_df['slippage_pct_sl'].mean():.2f}% | Médiane : {result_df['slippage_pct_sl'].median():.2f}%")

    print(f"\nPar classe d'actif :")
    for asset in ["/JPY", "/USD", "/GBP", "/CHF", "/CAD"]:
        seg = result_df[result_df["ticker"].str.endswith(asset)]
        if len(seg) == 0:
            continue
        print(f"  {asset:<6} : n={len(seg):<4} slippage moyen {seg['slippage_pips'].mean():+.3f} pips")

    print(f"\nDétail enregistré dans slippage_proxy_dukascopy_detail.csv")
    return result_df


if __name__ == "__main__":
    main()
