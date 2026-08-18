"""
CHANTIER 2, Section 1 point 1 (08/15) : reteste le slippage reel Dukascopy sur
la population ACTUELLE (RR>=1,35, 631 trades) -- l'ancien test
(slippage_proxy_dukascopy.py, -6,3% d'EV cite) tournait sur RR>=1,5/472
trades. 469/472 de ces trades sont deja mesures (slippage_proxy_dukascopy_
detail.csv) ; les 162 trades supplementaires qui entrent dans la population
avec le seuil abaisse a 1,35 sont mesures ICI (nouveaux appels Dukascopy),
puis fusionnes avec les 469 deja en cache pour produire le detail complet
sur les 631 trades (`slippage_proxy_dukascopy_detail_631_2026-08-15.csv`).
"""
import pandas as pd

from dukascopy_ticks import fetch_nearest_tick
from trailing_payoff_population import build_population_with_trailing

MAX_DELTA_SECONDS_WARN = 30


def main():
    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.35, verbose=False)
    pop = pop.sort_values("date_creation").reset_index(drop=True)

    slip_old = pd.read_csv("slippage_proxy_dukascopy_detail.csv")
    slip_old["date_creation"] = pd.to_datetime(slip_old["date_creation"])
    old_keys = set(zip(slip_old["ticker"], slip_old["date_creation"]))

    missing = pop[~pop.apply(lambda r: (r["ticker"], r["date_creation"]) in old_keys, axis=1)]
    print(f"Population 631 : {len(old_keys & set(zip(pop['ticker'], pop['date_creation'])))} deja mesures, "
          f"{len(missing)} a mesurer.")

    rows = []
    n_missing_tick = 0
    for i, (_, row) in enumerate(missing.iterrows()):
        result = fetch_nearest_tick(row["ticker"], row["date_creation"].to_pydatetime())
        if result is None:
            n_missing_tick += 1
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
        if (i + 1) % 40 == 0:
            print(f"  {i+1}/{len(missing)} nouveaux trades traites...")

    new_df = pd.DataFrame(rows)
    print(f"\nNouveaux trades mesures : {len(new_df)}/{len(missing)} ({n_missing_tick} sans tick trouve)")

    full = pd.concat([slip_old, new_df], ignore_index=True)
    # Ne garde que les lignes qui appartiennent bien a la population 631 (au cas ou
    # slip_old contenait des trades RR<1.35, exclus du seuil actuel)
    pop_keys = set(zip(pop["ticker"], pop["date_creation"]))
    full = full[full.apply(lambda r: (r["ticker"], r["date_creation"]) in pop_keys, axis=1)].copy()
    full.to_csv("slippage_proxy_dukascopy_detail_631_2026-08-15.csv", index=False)

    print(f"\nDetail complet (population 631) : {len(full)}/{len(pop)} trades avec slippage mesure "
          f"({len(pop) - len(full)} manquants au total, tick introuvable)")

    print(f"\nSlippage en pips (positif = prix Lutessia meilleur que le prix reel dispo) :")
    print(f"  Moyenne : {full['slippage_pips'].mean():+.3f} pips")
    print(f"  Mediane : {full['slippage_pips'].median():+.3f} pips")
    print(f"  Ecart-type : {full['slippage_pips'].std():.3f} pips")
    print(f"  P5 / P95 : {full['slippage_pips'].quantile(0.05):+.3f} / {full['slippage_pips'].quantile(0.95):+.3f} pips")

    print(f"\nPar classe d'actif :")
    for asset in ["/JPY", "/USD", "/GBP", "/CHF", "/CAD"]:
        seg = full[full["ticker"].str.endswith(asset)]
        if len(seg) == 0:
            continue
        print(f"  {asset:<6} : n={len(seg):<4} slippage moyen {seg['slippage_pips'].mean():+.3f} pips")

    print(f"\nComparaison ancien test (RR>=1.5, n=469) vs nouveau (RR>=1.35, n={len(full)}) :")
    print(f"  Ancien  : moyenne {slip_old['slippage_pips'].mean():+.3f} pips")
    print(f"  Nouveau : moyenne {full['slippage_pips'].mean():+.3f} pips")


if __name__ == "__main__":
    main()
