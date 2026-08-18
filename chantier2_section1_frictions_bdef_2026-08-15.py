"""
CHANTIER 2, Section 1 points 2b/2d/2e/2f (08/15) : frottements b) spread,
d) swap/rollover, e) erreurs de parsing, f) gap de week-end -- sur la
population actuelle (RR>=1,35, 631 trades). Le slippage (a) et la latence
(c) sont traites a part (chantier2_section1_slippage_631_2026-08-15.py /
mesure tick+10s), ce script combine b/d/e/f + assemble le total avec a/c
une fois disponibles.
"""
import datetime as dt

import numpy as np
import pandas as pd

import tp_sequence_analysis as tpseq
from rr_threshold_test import build_extended_population

MIN_RR = 1.35
ROLLOVER_HOUR_UTC = 22  # convention retail standard (5pm New York / 22h UTC)
SWAP_PIPS_LOW, SWAP_PIPS_HIGH = 2.0, 3.0  # hypothese pessimiste, -2 a -3 pips/nuit
MISS_RATES = [0.01, 0.02, 0.03]


def pip_size(ticker):
    return 0.01 if ticker.endswith("/JPY") else 0.0001


def n_rollovers_crossed(start, end):
    """Nombre de fois ou l'heure de rollover (22h UTC) est franchie entre start
    (exclu) et end (inclus)."""
    if end <= start:
        return 0
    first_rollover = start.replace(hour=ROLLOVER_HOUR_UTC, minute=0, second=0, microsecond=0)
    if first_rollover <= start:
        first_rollover += dt.timedelta(days=1)
    n = 0
    t = first_rollover
    while t <= end:
        n += 1
        t += dt.timedelta(days=1)
    return n


def main():
    pop, median_dur = build_extended_population(min_rr=MIN_RR)
    pop["resolution_time_est"] = pop["resolution_time"].fillna(pop["date_creation"] + median_dur)
    pop["sl_distance"] = (pop["prix_entree"] - pop["stop_loss_init"]).abs()
    pop["direction"] = np.where(pop["tp1_init"] > pop["prix_entree"], "buy", "sell")
    n = len(pop)
    print(f"Population : n={n} (RR>={MIN_RR})")

    # ============================================================
    # (d) Swap / rollover -- pondere par la VRAIE distribution de duree
    # ============================================================
    print("\n" + "=" * 70)
    print("(d) SWAP / ROLLOVER -- hypothese haute -2 a -3 pips/nuit")
    print("=" * 70)

    pop["n_rollovers"] = [n_rollovers_crossed(r["date_creation"], r["resolution_time_est"]) for _, r in pop.iterrows()]
    pop["hold_hours"] = (pop["resolution_time_est"] - pop["date_creation"]).dt.total_seconds() / 3600
    print(f"Duree de detention : mediane={pop['hold_hours'].median():.2f}h, moyenne={pop['hold_hours'].mean():.2f}h, "
          f"p95={pop['hold_hours'].quantile(0.95):.2f}h (coherent avec l'audit du 15/08 : mediane 7,7h/moyenne "
          f"29,3h/p95~140h sur le sous-ensemble VERIFIE bougies H1 -- ici sur resolution_time_est, "
          f"verifie+fallback median, meme ordre de grandeur attendu)")
    print(f"\nDistribution du nombre de rollovers (nuits) traverses :")
    print(pop["n_rollovers"].value_counts().sort_index().to_string())
    pct_with_rollover = (pop["n_rollovers"] > 0).mean() * 100
    print(f"\nPart des trades avec au moins 1 rollover : {pct_with_rollover:.1f}%")

    pip = pop["ticker"].apply(pip_size)
    for swap_pips in (SWAP_PIPS_LOW, SWAP_PIPS_HIGH):
        cost_price = pop["n_rollovers"] * swap_pips * pip
        cost_r = cost_price / pop["sl_distance"]
        print(f"\nHypothese {swap_pips:.1f} pips/nuit : cout moyen = {cost_r.mean():.5f}R/trade "
              f"(mediane {cost_r.median():.5f}R, max {cost_r.max():.4f}R sur le trade le plus long)")

    # ============================================================
    # (e) Erreurs de parsing / execution manquee
    # ============================================================
    print("\n" + "=" * 70)
    print("(e) ERREURS DE PARSING / EXECUTION MANQUEE -- 1 a 3% des signaux")
    print("=" * 70)
    ev_base = pop["r_realiste"].mean() if "r_realiste" in pop.columns else None
    # r_realiste peut ne pas exister dans build_extended_population (pas le module
    # trailing) -- on utilise rr_tp1/-1 (convention EV brute standard du projet)
    is_win = pop["statut_final"] == "OBJECTIF ATTEINT"
    outcome_r_simple = np.where(is_win, pop["rr_tp1"], -1.0)
    ev_ref = outcome_r_simple.mean()
    print(f"EV de reference (rr_tp1 si gain / -1 si perte, avant tout autre frottement) = {ev_ref:+.4f}R")
    for miss_rate in MISS_RATES:
        ev_after = ev_ref * (1 - miss_rate)
        print(f"  miss_rate={miss_rate*100:.0f}% -> EV = {ev_after:+.4f}R "
              f"(cout = {ev_ref - ev_after:+.4f}R, soit {(1-ev_after/ev_ref)*100:.1f}% de l'EV)")
    print("  (hypothese : trades manques = echantillon aleatoire, EV moyenne identique -- "
          "cout PUREMENT proportionnel, pas de biais suppose sur QUELS trades sont manques)")

    # ============================================================
    # (f) Gap de week-end -- revérifie sur la population actuelle
    # ============================================================
    print("\n" + "=" * 70)
    print("(f) GAP DE WEEK-END -- population actuelle (RR>=1.35, 631 trades)")
    print("=" * 70)
    pop["yahoo_symbol"] = pop["ticker"].apply(tpseq.ticker_to_yahoo_symbol)
    candles_by_symbol = {}
    for symbol in sorted(pop["yahoo_symbol"].dropna().unique()):
        candles = tpseq.fetch_h1_history(symbol, pop["date_creation"].min().to_pydatetime(),
                                          pd.Timestamp.utcnow().tz_localize(None).to_pydatetime())
        if candles is not None and not candles.empty:
            candles_by_symbol[symbol] = candles

    losses = pop[pop["statut_final"] == "INVALIDÉE"].copy()
    gap_costs, gap_flags, covered_flags = [], [], []
    for _, row in losses.iterrows():
        candles = candles_by_symbol.get(row["yahoo_symbol"])
        if candles is None:
            gap_costs.append(None); gap_flags.append(False); covered_flags.append(False)
            continue
        res = tpseq.analyze_trade(row, candles)
        sl_time = res.get("sl_time")
        if sl_time is None:
            gap_costs.append(None); gap_flags.append(False); covered_flags.append(res.get("case") != "hors_couverture_historique")
            continue
        window = candles[candles["datetime"] >= row["date_creation"]].sort_values("datetime")
        excess_r, is_gap = tpseq.compute_weekend_gap_cost(row["prix_entree"], row["stop_loss_init"],
                                                            res["is_long"], sl_time, window)
        gap_costs.append(excess_r); gap_flags.append(is_gap); covered_flags.append(True)
    losses["gap_excess_r"] = gap_costs
    losses["is_gap"] = gap_flags
    losses["covered"] = covered_flags

    covered_losses = losses[losses["covered"]]
    n_gap = sum(gap_flags)
    n_covered = len(covered_losses)
    print(f"Pertes couvertes (bougies H1 disponibles + sl_time detecte) : {n_covered}/{len(losses)}")
    print(f"Pertes avec un gap de week-end (>= {tpseq.WEEKEND_GAP_THRESHOLD_HOURS}h de trou avant le SL) : "
          f"{n_gap}/{n_covered} ({n_gap/max(n_covered,1)*100:.1f}%)")
    if n_gap:
        gap_only = covered_losses[covered_losses["is_gap"]]
        print(f"Excess R moyen SUR les gaps (au-dela du -1R theorique) : {gap_only['gap_excess_r'].mean():.4f}R "
              f"(max {gap_only['gap_excess_r'].max():.4f}R)")
        # impact moyen sur la POPULATION COUVERTE totale (pertes+gains), pas juste les pertes concernees
        impact_pop = gap_only["gap_excess_r"].sum() / n_covered
        print(f"Impact moyen dilue sur l'ensemble des pertes couvertes (n={n_covered}) : {impact_pop:.5f}R/trade")
        impact_pop_all = gap_only["gap_excess_r"].sum() / n
        print(f"Impact moyen dilue sur la POPULATION TOTALE (n={n}, gains inclus) : {impact_pop_all:.5f}R/trade")
    else:
        print("Aucun gap de week-end detecte sur les pertes couvertes.")

    # ============================================================
    # (b) Spread -- symetrie buy/sell + widening pessimiste
    # ============================================================
    print("\n" + "=" * 70)
    print("(b) SPREAD -- symetrie + widening pessimiste +20-30%")
    print("=" * 70)
    print("""
NOTE METHODOLOGIQUE : la mesure de slippage Dukascopy (point a) compare deja
prix_entree au prix REELLEMENT TRADABLE (ask pour un achat, bid pour une
vente) -- le cout du COTE spread payé a l'entree est donc DEJA inclus dans
le slippage mesure, ce n'est pas un frottement separe additif. Ce qui reste
a verifier ici : (1) la mesure est-elle symetrique buy/sell (pas de biais de
methode), (2) un scenario ou le VRAI spread broker retail est plus large que
le spread interbancaire Dukascopy (+20-30%, hypothese pessimiste) -- cout
INCREMENTAL au-dela de ce qui est deja mesure.
""")


if __name__ == "__main__":
    main()
