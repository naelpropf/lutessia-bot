"""
CHANTIER 2, Section 1 -- assemblage final : (a) slippage reel deterministe
(mesure par trade, pas un tirage empirique) + (c) latence d'execution
(5-15s, mesuree via decalage de tick Dukascopy) + combinaison de TOUS les
frottements (a-f) + EV plancher final (Section 1 point 3), sur la
population 631 (RR>=1,35).
"""
import datetime as dt

import numpy as np
import pandas as pd
from scipy import stats

from dukascopy_ticks import fetch_nearest_tick
from trailing_payoff_population import build_population_with_trailing

LATENCY_SECONDS = 10.0  # milieu de la fourchette 5-15s demandee
MIN_RR = 1.35


def pip_size(ticker):
    return 0.01 if ticker.endswith("/JPY") else 0.0001


def main():
    pop = build_population_with_trailing("fixed", 0.15, min_rr=MIN_RR, verbose=False)
    pop = pop.sort_values("date_creation").reset_index(drop=True)
    n = len(pop)

    slip = pd.read_csv("slippage_proxy_dukascopy_detail_631_2026-08-15.csv")
    slip["date_creation"] = pd.to_datetime(slip["date_creation"])
    slip = slip.drop_duplicates(subset=["ticker", "date_creation"])

    merged = pop.merge(slip[["ticker", "date_creation", "slippage_pips", "direction"]],
                        on=["ticker", "date_creation"], how="left")
    n_measured = merged["slippage_pips"].notna().sum()
    print(f"Population n={n}, slippage mesure sur {n_measured} ({n_measured/n*100:.1f}%)")

    # ------------------------------------------------------------
    # (a) Slippage REEL, deterministe (mesure par trade, pas un tirage empirique)
    # ------------------------------------------------------------
    pip = merged["ticker"].apply(pip_size)
    slippage_price = merged["slippage_pips"] * pip
    prix_entree = merged["prix_entree"]
    stop_loss_init = merged["stop_loss_init"]
    original_sl_distance = (prix_entree - stop_loss_init).abs()
    r_trailing = merged["r_trailing"]
    is_buy = merged["direction"] == "buy"

    actual_entry = np.where(is_buy, prix_entree - slippage_price, prix_entree + slippage_price)
    adjusted_sl_distance = (actual_entry - stop_loss_init).abs()
    exit_price = np.where(is_buy, prix_entree + r_trailing * original_sl_distance,
                           prix_entree - r_trailing * original_sl_distance)
    new_movement = np.where(is_buy, exit_price - actual_entry, actual_entry - exit_price)
    adjusted_sl_distance_safe = np.maximum(adjusted_sl_distance, original_sl_distance * 0.05)
    r_slippage = new_movement / adjusted_sl_distance_safe
    merged["r_slippage"] = np.where(merged["slippage_pips"].notna(), r_slippage, merged["r_trailing"])

    ev_sans = merged["r_trailing"].mean()
    ev_avec_a = merged["r_slippage"].mean()
    print(f"\n(a) SLIPPAGE REEL (mesure deterministe, 628/631 trades, 3 sans tick -> r_trailing conserve)")
    print(f"  EV sans frottement       : {ev_sans:+.4f}R")
    print(f"  EV avec slippage seul(a) : {ev_avec_a:+.4f}R  (delta {ev_avec_a-ev_sans:+.4f}R, "
          f"{(ev_avec_a/ev_sans-1)*100:+.1f}%)")

    # ------------------------------------------------------------
    # (c) Latence d'execution -- decalage de tick a +10s (deja en cache
    # apres le fetch de (a), meme heure -> pas de nouvel appel reseau)
    # ------------------------------------------------------------
    print(f"\n(c) LATENCE D'EXECUTION (delai email->bot, proxy {LATENCY_SECONDS:.0f}s = milieu de 5-15s)")
    lat_rows = []
    for _, row in merged.dropna(subset=["direction"]).iterrows():
        t0 = row["date_creation"].to_pydatetime()
        t1 = t0 + dt.timedelta(seconds=LATENCY_SECONDS)
        r0 = fetch_nearest_tick(row["ticker"], t0, max_search_hours=0)
        r1 = fetch_nearest_tick(row["ticker"], t1, max_search_hours=0)
        if r0 is None or r1 is None:
            continue
        _, ask0, bid0, _ = r0
        _, ask1, bid1, _ = r1
        ref0 = ask0 if row["direction"] == "buy" else bid0
        ref1 = ask1 if row["direction"] == "buy" else bid1
        move = (ref1 - ref0) if row["direction"] == "buy" else (ref0 - ref1)
        # move>0 = le prix a bouge EN DEFAVEUR pendant le delai (on paierait plus cher / on vendrait moins cher)
        lat_rows.append({"ticker": row["ticker"], "move_pips": move / pip_size(row["ticker"]),
                          "sl_distance": abs(row["prix_entree"] - row["stop_loss_init"])})
    lat_df = pd.DataFrame(lat_rows)
    print(f"  Mesure sur {len(lat_df)}/{n} trades (memes heures que (a), deja en cache)")
    print(f"  Mouvement moyen sur {LATENCY_SECONDS:.0f}s (positif = defavorable) : {lat_df['move_pips'].mean():+.4f} pips "
          f"(mediane {lat_df['move_pips'].median():+.4f}, ecart-type {lat_df['move_pips'].std():.4f})")
    lat_df["cost_r"] = (lat_df["move_pips"].clip(lower=0) * lat_df["ticker"].apply(pip_size)) / lat_df["sl_distance"]
    # cout = seulement la part DEFAVORABLE (clip>=0) -- hypothese pessimiste demandee,
    # on n'imagine pas de "gain" de latence meme si mesure en moyenne proche de 0
    cost_latence_moyen = lat_df["cost_r"].mean()
    print(f"  Cout latence (hypothese pessimiste, ne compte que le mouvement defavorable) : "
          f"{cost_latence_moyen:.5f}R/trade en moyenne")
    t_stat, p_val = stats.ttest_1samp(lat_df["move_pips"], 0)
    print(f"  Test (mouvement moyen != 0) : t={t_stat:.2f}, p={p_val:.4f} -- "
          f"{'mouvement significativement non-nul' if p_val < 0.05 else 'pas de biais directionnel detectable sur '+str(LATENCY_SECONDS)+'s, bruit domine largement le signal a cette echelle de temps'}")

    # ------------------------------------------------------------
    # COMBINAISON DE TOUS LES FROTTEMENTS (hypothese pessimiste sur chacun)
    # ------------------------------------------------------------
    print("\n" + "=" * 70)
    print("COMBINAISON DE TOUS LES FROTTEMENTS (hypothese pessimiste, additive en R)")
    print("=" * 70)
    # repris des resultats deja obtenus dans les scripts precedents de ce chantier
    cost_a = ev_sans - ev_avec_a          # slippage reel (deja negatif si defavorable)
    cost_b = 0.0                           # deja inclus dans (a), cf. note methodologique
    cost_c = cost_latence_moyen            # latence, hypothese pessimiste (mouvement defavorable seul)
    cost_d = 0.07918                       # swap, hypothese haute -3 pips/nuit (chantier2_section1_frictions_bdef)
    cost_e = 0.00458                       # erreurs de parsing, hypothese haute 3% (idem)
    cost_f = 0.00275                       # gap week-end, dilue population totale (idem)

    total_cost = cost_a + cost_b + cost_c + cost_d + cost_e + cost_f
    ev_floor = ev_sans - total_cost
    print(f"  a) Slippage reel (mesure)              : -{cost_a:.5f}R")
    print(f"  b) Spread (deja inclus dans a)          : -{cost_b:.5f}R")
    print(f"  c) Latence execution (5-15s, pessimiste): -{cost_c:.5f}R")
    print(f"  d) Swap/rollover (-3 pips/nuit, pessim.): -{cost_d:.5f}R")
    print(f"  e) Erreurs parsing (3%, pessimiste)     : -{cost_e:.5f}R")
    print(f"  f) Gap week-end (dilue population)      : -{cost_f:.5f}R")
    print(f"  -----------------------------------------------")
    print(f"  TOTAL frottements                       : -{total_cost:.5f}R")
    print(f"\n  EV brute (avant frottements)  : {ev_sans:+.4f}R")
    print(f"  EV PLANCHER (tous frottements, hypothese pessimiste cumulee) : {ev_floor:+.4f}R")

    # combine avec le P10 bayesien du winrate (Section 2)
    is_win = (pop["statut_final"] == "OBJECTIF ATTEINT").to_numpy()
    wins, losses = int(is_win.sum()), n - int(is_win.sum())
    rr_mean = pop["rr_tp1"].mean()
    a_post, b_post = 0.5 + wins, 0.5 + losses
    wr_p10 = stats.beta(a_post, b_post).ppf(0.10)
    ev_p10_brut = wr_p10 * rr_mean - (1 - wr_p10) * 1.0
    ev_p10_plancher = ev_p10_brut - total_cost

    print(f"\n  P10 bayesien du winrate (Section 2) = {wr_p10*100:.2f}%")
    print(f"  EV a ce P10, AVANT frottements  : {ev_p10_brut:+.4f}R")
    print(f"  EV PLANCHER FINAL (P10 winrate + tous frottements pessimistes) : {ev_p10_plancher:+.4f}R")
    wr_threshold = 1.0 / (rr_mean + 1.0)
    print(f"\n  Seuil de rentabilite (EV=0, RR={rr_mean:.3f}) = winrate {wr_threshold*100:.2f}%")
    print(f"  Marge de l'EV plancher final au-dessus de 0 : {ev_p10_plancher:+.4f}R "
          f"({'toujours positif' if ev_p10_plancher > 0 else 'NEGATIF -- alerte'})")


if __name__ == "__main__":
    main()
