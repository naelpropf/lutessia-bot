"""
CHANTIER instant funding, Phase 2 point 5 : l'instant funding justifie-t-il
un risque reduit specifiquement (enjeu de casse plus eleve, plein tarif a
chaque reouverture) ? Sweep du risque funded sur GFT Instant GOAT (le cas
le plus expose, DD 6% trailing vs 10% static pour le format classique deja
utilise) et Blueberry Instant Elite (DD 10% trailing, comparable au 10%
static classique -- effet attendu plus faible).
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
from engine_multiformat import FORMATS
from corrected_scaling_mechanism import BASE_PALIER

import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("_phase2", "chantier_instant_funding_phase2_2026-08-15.py")
_phase2 = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_phase2)
run_one_account = _phase2.run_one_account

DAY_SECONDS = 86400
YEAR_SECONDS = 365.25 * DAY_SECONDS
MONTH_SECONDS = DAYS_PER_MONTH * DAY_SECONDS
SIM_YEARS = 4
MIN_RR, CORR_TH = 1.35, 0.80
EVAL_RISK, GFT_EVAL_RISK = 1.25, 1.75

SWEEP = {
    "GFT": dict(fmt="GFT_InstantGOAT", palier=BASE_PALIER["GFT"], eval_risk=GFT_EVAL_RISK,
                price=488.0, risks=[0.75, 1.00, 1.25, 1.50, 1.90]),
    "Blueberry": dict(fmt="Blueberry_InstantElite", palier=BASE_PALIER["Blueberry"], eval_risk=EVAL_RISK,
                       price=800.0, risks=[1.00, 1.25, 1.50, 1.90]),
}


def main():
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    t_start = time.time()

    pop = build_population_with_trailing("fixed", 0.15, min_rr=MIN_RR, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

    rows = []
    for firm, cfg in SWEEP.items():
        fmt = FORMATS[cfg["fmt"]]
        print("=" * 70)
        print(f"{firm} instant ({cfg['fmt']}) -- sweep du risque funded")
        print("=" * 70)
        for risk_funded in cfg["risks"]:
            rng_boot = random.Random(10000)
            results = []
            for _ in range(n_sims):
                trades, slot_arrivals = eng.build_flexible_population(pop, None, 1.0, False, random.Random(rng_boot.random()))
                block_seconds = 2 * 30 * DAY_SECONDS
                blocks = build_blocks(trades, slot_arrivals, block_seconds)
                raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot,
                                                                              SIM_YEARS * YEAR_SECONDS)
                order = list(range(len(raw_trades)))
                results.append(run_one_account(raw_trades, raw_slots, market_data, excluded_map, order,
                                                fmt, cfg["palier"], cfg["eval_risk"], cfg["price"],
                                                funded_from_start=True, risk_funded=risk_funded))
            df = pd.DataFrame(results)
            row = dict(firm=firm, risk_funded=risk_funded, profit_mean=df["net_profit"].mean(),
                       profit_median=df["net_profit"].median(), cash_paid_mean=df["cash_paid"].mean(),
                       n_breaks_mean=df["n_breaks"].mean())
            rows.append(row)
            print(f"  risque={risk_funded:.2f}% : profit_moy={row['profit_mean']:+,.0f}$ "
                  f"profit_med={row['profit_median']:+,.0f}$ cash_paye_moy={row['cash_paid_mean']:,.0f}$ "
                  f"casses_moy={row['n_breaks_mean']:.2f}")

    pd.DataFrame(rows).to_csv(f"chantier_instant_funding_risk_sweep_n{n_sims}.csv", index=False)
    print(f"\nTermine en {time.time()-t_start:.0f}s.")


if __name__ == "__main__":
    main()
