"""
Partie 3 (suite signal_stability_bayesian.py) : propage l'incertitude
PARAMETRIQUE du winrate (pas seulement l'incertitude de sequence de trades
deja geree par le block bootstrap) a travers tout le Monte Carlo.

Statu quo du projet : 2 points fixes (40,09% reel, 37,66% = P10 du posterior
Beta(260,388)), chacun tourne en un batch SEPARE de sims -- l'incertitude sur
le PARAMETRE winrate lui-meme n'est jamais melangee a l'incertitude de
sequence a l'interieur d'un seul Monte Carlo.

Ici : a CHAQUE run, le winrate est d'abord TIRE du posterior Beta(260,388)
(confirme rigoureux dans signal_stability_bayesian.py), PUIS la sequence de
trades est bootstrappee comme d'habitude -- incertitude parametrique et
incertitude de sequence combinees dans une seule distribution.

Moteur reutilise tel quel : point_liquidity_hybrid (regle hybride, PAS de
split/fiscalite -- comparaison directe aux chiffres deja documentes du
projet, qui datent d'avant l'integration split/tax).
"""
import random
import time

import numpy as np
import pandas as pd
from scipy import stats

import robustness_5ers_risk_challenge as eng
from point_liquidity_hybrid import run_one as hybrid_run_one
from point_liquidity_rules import build_ctx
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence

CORR_TH = 0.6
ALPHA_POST, BETA_POST = 260, 388  # posterior confirme dans signal_stability_bayesian.py
DAY_SECONDS = 86400
MONTH_SECONDS = DAYS_PER_MONTH * DAY_SECONDS


def run_fixed(pop, wr_target, market_data, excluded_map, ceiling, n_sims, seed):
    trades, slot_arrivals = eng.build_flexible_population(pop, wr_target, 1.0, False, random.Random(123))
    total_h, marks, block_s, blocks = build_ctx(trades, slot_arrivals)
    rng = random.Random(seed)
    rows = []
    for _ in range(n_sims):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_s, rng, total_h)
        order = list(range(len(raw_trades)))
        snaps, hit_ceiling, full_month = hybrid_run_one(raw_trades, raw_slots, market_data, excluded_map, order,
                                                          marks, ceiling)
        rows.append({"year1_net": snaps[0][1], "final_net": snaps[1][1], "final_cash": snaps[1][2]})
    return pd.DataFrame(rows)


def run_propagated(pop, market_data, excluded_map, ceiling, n_sims, seed):
    rng_wr = random.Random(seed)
    rng_boot = random.Random(seed + 1)
    rows = []
    for _ in range(n_sims):
        wr_draw = rng_wr.betavariate(ALPHA_POST, BETA_POST)
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_draw, 1.0, False, random.Random(rng_wr.random()))
        total_h, marks, block_s, blocks = build_ctx(trades, slot_arrivals)
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_s, rng_boot, total_h)
        order = list(range(len(raw_trades)))
        snaps, hit_ceiling, full_month = hybrid_run_one(raw_trades, raw_slots, market_data, excluded_map, order,
                                                          marks, ceiling)
        rows.append({"wr_draw": wr_draw, "year1_net": snaps[0][1], "final_net": snaps[1][1], "final_cash": snaps[1][2]})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    import sys
    t_start = time.time()
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 800

    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

    all_rows = []
    for ceiling in (1000.0, 3000.0):
        print(f"\n{'='*100}\nPLAFOND {ceiling:.0f}$\n{'='*100}")

        t0 = time.time()
        df_real = run_fixed(pop, None, market_data, excluded_map, ceiling, n_sims, seed=42)
        df_p10 = run_fixed(pop, 0.3766, market_data, excluded_map, ceiling, n_sims, seed=43)
        df_two_point = pd.concat([df_real, df_p10], ignore_index=True)
        print(f"[statu quo -- 2 points fixes] wr=40.09%: profit final moy={df_real['final_net'].mean():+,.0f}$ | "
              f"wr=37.66%: profit final moy={df_p10['final_net'].mean():+,.0f}$ ({time.time()-t0:.0f}s)")

        t0 = time.time()
        df_prop = run_propagated(pop, market_data, excluded_map, ceiling, n_sims * 2, seed=100)
        print(f"[propage -- winrate ~ Beta(260,388) par run] wr_draw moyen={df_prop['wr_draw'].mean()*100:.2f}% "
              f"(std={df_prop['wr_draw'].std()*100:.2f}pp) | profit final moy={df_prop['final_net'].mean():+,.0f}$ "
              f"({time.time()-t0:.0f}s)")

        for label, df in [("statu_quo_2points", df_two_point), ("propage_beta_posterior", df_prop)]:
            df.to_csv(f"winrate_uncertainty_{label}_ceiling{int(ceiling)}.csv", index=False)
            row = dict(
                ceiling=ceiling, config=label, n=len(df),
                profit_final_mean=df["final_net"].mean(),
                profit_final_p5=df["final_net"].quantile(0.05),
                profit_final_p50=df["final_net"].median(),
                profit_final_p95=df["final_net"].quantile(0.95),
                profit_final_iqr=df["final_net"].quantile(0.75) - df["final_net"].quantile(0.25),
                profit_final_p95_p5_width=df["final_net"].quantile(0.95) - df["final_net"].quantile(0.05),
                cash_pire_cas=df["final_cash"].max(),
                cash_p95=df["final_cash"].quantile(0.95),
                p_year1_negatif_pct=(df["year1_net"] < 0).mean() * 100,
            )
            all_rows.append(row)
            print(f"  [{label}] n={row['n']} | profit final : moy={row['profit_final_mean']:+,.0f}$ P5={row['profit_final_p5']:+,.0f}$ "
                  f"P50={row['profit_final_p50']:+,.0f}$ P95={row['profit_final_p95']:+,.0f}$ (largeur P95-P5={row['profit_final_p95_p5_width']:,.0f}$) | "
                  f"cash pire cas={row['cash_pire_cas']:,.0f}$ (P95={row['cash_p95']:,.0f}$) | P(an1<0)={row['p_year1_negatif_pct']:.2f}%")

        pd.DataFrame(all_rows).to_csv("winrate_uncertainty_summary.csv", index=False)

    pd.DataFrame(all_rows).to_csv("winrate_uncertainty_summary.csv", index=False)
    print(f"\nTermine en {time.time()-t_start:.0f}s.")
