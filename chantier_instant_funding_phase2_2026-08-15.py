"""
CHANTIER instant funding, PHASE 2 (08/15) : modelisation economique
eval classique vs instant funding, POUR LES 2 FIRMS OU UNE VRAIE OFFRE
INSTANT EXISTE ET EST COMPARABLE AU PALIER ACTUEL DU PROJET (Phase 1) :
Blueberry (25k) et GFT (50k). FTMO (pas d'instant funding reel), The5%ers
(Hyper Growth n'est PAS instant -- garde une phase d'eval 10%), FundedNext
(Stellar Instant plafonne a 20k$, incompatible avec le palier 200k du
projet) sont EXCLUS -- voir rapport Phase 1.

Simulation compte UNIQUE (pas la flotte complete) : population reelle
RR>=1,35, block bootstrap 2 mois, ~4 ans, n=300 seeds, risque eval=1,25%/
funded=1,90% (GFT eval specifique=1,75%, coherent avec le reste du
projet). Track CLASSIQUE (eval standard deja utilisee, palier BASE_PALIER,
prix de repay = prix eval au meme palier) vs INSTANT (funded des t=0,
format instant reel, prix de reopen = prix instant PLEIN TARIF a chaque
casse -- pas de rabais, coherent avec le point 5 du prompt).
"""
import random
import sys
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from engine_multiformat import FORMATS, make_acc_mf, process_trade_mf, _current_phase
from corrected_scaling_mechanism import BASE_PALIER

DAY_SECONDS = 86400
YEAR_SECONDS = 365.25 * DAY_SECONDS
MONTH_SECONDS = DAYS_PER_MONTH * DAY_SECONDS
SIM_YEARS = 4
MIN_RR = 1.35
CORR_TH = 0.80
EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK = 1.25, 1.90, 1.75

FIRMS_CONFIG = {
    "Blueberry": dict(classic_fmt="Blueberry_Prime2Step", instant_fmt="Blueberry_InstantElite",
                       palier=BASE_PALIER["Blueberry"], eval_risk=EVAL_RISK,
                       classic_price=165.0, instant_price=800.0),
    "GFT": dict(classic_fmt="GFT_2Step_GOAT", instant_fmt="GFT_InstantGOAT",
                palier=BASE_PALIER["GFT"], eval_risk=GFT_EVAL_RISK,
                classic_price=288.0, instant_price=488.0),
}


def run_one_account(trades, slot_arrivals, market_data, excluded_map, order, fmt, palier,
                     eval_risk, reopen_price, funded_from_start, risk_funded=FLEET_RISK):
    acc = make_acc_mf(fmt, palier, cost=reopen_price, active=True)
    if funded_from_start:
        acc["phase"] = "funded"
    state = {"reserve": 1e18, "total_breaks": 0}  # reserve infinie ici : le cout des
    # reouvertures est trace separement (cash_paid), pas de plafond dans cette
    # comparaison de base (point 6 traite a part, avec plafond explicite)
    cash_paid = reopen_price  # cout d'entree initial (eval OU instant)
    n_breaks = 0
    funded_day = 0.0 if funded_from_start else None
    total_trading_days_to_fund = None

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]
        if not acc["active"]:
            continue
        pdef = _current_phase(fmt, acc)
        r = risk_funded if acc["phase"] == "funded" else eval_risk
        phase_before = acc["phase"]
        just_funded = process_trade_mf(acc, trade, now, fmt, state, r, market_data, excluded_map,
                                        split_flat=0.80, reserve_share=0.0, cost_override=0.0)
        if just_funded and funded_day is None:
            funded_day = now / DAY_SECONDS

        reset_happened = (acc["cumulative_since_reset"] == 0.0 and acc["peak_since_reset"] == 0.0
                           and len(acc["trading_days_since_reset"]) == 0)
        progressed = (fmt["phases"] and phase_before == "challenge" and
                      (acc["phase"] == "funded" or acc["phase_index"] > 0))
        broke = reset_happened and not progressed and acc["active"]
        if broke:
            # process_trade_mf a deja reinitialise l'etat du compte en interne
            # (cost_override=0.0 -> reset gratuit, meme mecanisme que le
            # moteur de flotte). Ici on ajoute seulement le VRAI cout de
            # reouverture (prix plein tarif instant ou repay-eval classique),
            # trace separement du moteur (pas de plafond de reserve dans
            # cette comparaison de base -- point 6 traite a part).
            n_breaks += 1
            cash_paid += reopen_price
            acc["total_fees_paid"] += reopen_price

    net_profit = acc["total_funded_pnl"] - acc["total_fees_paid"]
    return dict(net_profit=net_profit, cash_paid=cash_paid, n_breaks=n_breaks,
                funded_day=funded_day if funded_day is not None else float("nan"))


def main():
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    t_start = time.time()

    pop = build_population_with_trailing("fixed", 0.15, min_rr=MIN_RR, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

    all_rows = []
    for firm, cfg in FIRMS_CONFIG.items():
        print("=" * 70)
        print(f"{firm} -- classique ({cfg['classic_fmt']}) vs instant ({cfg['instant_fmt']})")
        print("=" * 70)
        classic_fmt = FORMATS[cfg["classic_fmt"]]
        instant_fmt = FORMATS[cfg["instant_fmt"]]

        rng_wr = random.Random(9999)
        rng_boot = random.Random(10000)
        classic_rows, instant_rows = [], []
        for _ in range(n_sims):
            trades, slot_arrivals = eng.build_flexible_population(pop, None, 1.0, False, random.Random(rng_boot.random()))
            block_seconds = 2 * 30 * DAY_SECONDS
            blocks = build_blocks(trades, slot_arrivals, block_seconds)
            raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot,
                                                                          SIM_YEARS * YEAR_SECONDS)
            order = list(range(len(raw_trades)))

            classic_rows.append(run_one_account(raw_trades, raw_slots, market_data, excluded_map, order,
                                                 classic_fmt, cfg["palier"], cfg["eval_risk"], cfg["classic_price"],
                                                 funded_from_start=False))
            instant_rows.append(run_one_account(raw_trades, raw_slots, market_data, excluded_map, order,
                                                 instant_fmt, cfg["palier"], cfg["eval_risk"], cfg["instant_price"],
                                                 funded_from_start=True))

        cdf = pd.DataFrame(classic_rows)
        idf = pd.DataFrame(instant_rows)

        print(f"\nTemps pour etre finance (classique) : mediane={cdf['funded_day'].median():.1f}j, "
              f"moyenne={cdf['funded_day'].mean():.1f}j, P90={cdf['funded_day'].quantile(0.9):.1f}j")
        print(f"(instant : 0j par definition)")

        print(f"\nProfit net sur {SIM_YEARS} ans : classique {cdf['net_profit'].mean():+,.0f}$ (median "
              f"{cdf['net_profit'].median():+,.0f}$) | instant {idf['net_profit'].mean():+,.0f}$ (median "
              f"{idf['net_profit'].median():+,.0f}$)")
        print(f"Cash total paye (entree + reouvertures) : classique {cdf['cash_paid'].mean():,.0f}$ | "
              f"instant {idf['cash_paid'].mean():,.0f}$")
        print(f"Nombre de casses moyen : classique {cdf['n_breaks'].mean():.2f} | instant {idf['n_breaks'].mean():.2f}")
        print(f"P95 cash paye (annee la plus chere, borne haute risque de tresorerie) : "
              f"classique {cdf['cash_paid'].quantile(0.95):,.0f}$ | instant {idf['cash_paid'].quantile(0.95):,.0f}$")

        delta_profit = idf["net_profit"].mean() - cdf["net_profit"].mean()
        print(f"\nDelta profit net (instant - classique) sur {SIM_YEARS} ans : {delta_profit:+,.0f}$")
        print(f"Verdict brut : {'INSTANT GAGNE' if delta_profit > 0 else 'CLASSIQUE GAGNE'}")

        all_rows.append(dict(firm=firm, track="classic", profit_mean=cdf["net_profit"].mean(),
                              profit_median=cdf["net_profit"].median(), cash_paid_mean=cdf["cash_paid"].mean(),
                              cash_paid_p95=cdf["cash_paid"].quantile(0.95), n_breaks_mean=cdf["n_breaks"].mean(),
                              funded_day_median=cdf["funded_day"].median()))
        all_rows.append(dict(firm=firm, track="instant", profit_mean=idf["net_profit"].mean(),
                              profit_median=idf["net_profit"].median(), cash_paid_mean=idf["cash_paid"].mean(),
                              cash_paid_p95=idf["cash_paid"].quantile(0.95), n_breaks_mean=idf["n_breaks"].mean(),
                              funded_day_median=0.0))

        cdf.to_csv(f"chantier_instant_funding_{firm}_classic_n{n_sims}.csv", index=False)
        idf.to_csv(f"chantier_instant_funding_{firm}_instant_n{n_sims}.csv", index=False)

    pd.DataFrame(all_rows).to_csv(f"chantier_instant_funding_summary_n{n_sims}.csv", index=False)
    print(f"\nTermine en {time.time()-t_start:.0f}s.")


if __name__ == "__main__":
    main()
