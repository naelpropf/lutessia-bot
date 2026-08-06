"""
Point 5, etage B : Monte Carlo flotte complet sur les candidats retenus de
l'etage A (EV brute) + balayage maxpos/correlation independant sur la
population verrouillee. Le grid croise complet (4x4x3x3=144) est infaisable en
temps raisonnable (chaque cellule RR/trailing necessite une nouvelle
construction de population avec re-simulation H1) -- design reduit et assume :
  - RR x trailing : candidat actuel (1.5, 0.2) + meilleur EV brute (1.25, 0.15)
    + meilleur controle de drawdown brut (2.0, 0.15), cf. point5_stageA_ev_screen.csv
  - maxpos x correlation : balaye INDEPENDAMMENT sur la population verrouillee
    (1.5, 0.2) -- ces 2 parametres ne changent pas la population de trades,
    seulement le filtrage flotte, donc rapides a tester sans re-simulation H1.
"""
import random
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
from real_cash_risk_year1_block_bootstrap import DAYS_PER_MONTH
from trailing_payoff_population import build_population_with_trailing, build_trades_trailing
from monte_carlo_simulation import precompute_correlation_pairs

POP_CONSTRUCT_SEED = 123
RISK = 2.5


def build_ctx(trades, slot_arrivals):
    total_horizon_seconds = slot_arrivals[-1]
    mark_seconds_list = [eng.YEAR_SECONDS, total_horizon_seconds]
    block_seconds = eng.BLOCK_MONTHS * DAYS_PER_MONTH * 86400
    blocks = eng.build_blocks(trades, slot_arrivals, block_seconds)
    return total_horizon_seconds, mark_seconds_list, block_seconds, blocks


def summarize(df, label, extra=None):
    row = dict(label=label, profit_final_mean=df["final_net"].mean(), cash_worst=df["final_cash"].max(),
               p_year1_negatif=(df["year1_net"] < 0).mean() * 100, casses_final=df["final_breaks"].mean())
    if extra:
        row.update(extra)
    return row


def main():
    t_start = time.time()
    rows = []

    print("=" * 100 + "\nRR x TRAILING -- candidats etage A\n" + "=" * 100)
    for rr, mult, label in [(1.5, 0.2, "actuel_1.5_0.2"), (1.25, 0.15, "meilleur_EV_1.25_0.15"),
                            (2.0, 0.15, "meilleur_DD_2.0_0.15")]:
        t0 = time.time()
        pop = build_population_with_trailing("fixed", mult, min_rr=rr, verbose=False)
        market_data, excluded_map = eng.prep_common(pop)
        trades, slot_arrivals = eng.build_flexible_population(pop, None, 1.0, False, random.Random(POP_CONSTRUCT_SEED))
        total_h, marks, block_s, blocks = build_ctx(trades, slot_arrivals)
        df = eng.run_variant(trades, slot_arrivals, blocks, block_s, total_h, marks, market_data, excluded_map,
                             RISK, RISK, "event", None, 2000, 42)
        df.to_csv(f"point5_rrtrail_{label}.csv", index=False)
        row = summarize(df, label, {"rr": rr, "trailing_mult": mult})
        rows.append(row)
        print(f"  [{label}] profit {row['profit_final_mean']:+,.0f}$ | cash pire cas {row['cash_worst']:,.0f}$ | "
              f"P(an1<0) {row['p_year1_negatif']:.2f}% | casses {row['casses_final']:.1f} ({time.time()-t0:.0f}s)")
    pd.DataFrame(rows).to_csv("point5_summary_partial.csv", index=False)

    print("\n" + "=" * 100 + "\nMAXPOS x CORRELATION -- population verrouillee (1.5, 0.2)\n" + "=" * 100)
    pop = build_population_with_trailing("fixed", 0.2, min_rr=1.5, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    trades, slot_arrivals = eng.build_flexible_population(pop, None, 1.0, False, random.Random(POP_CONSTRUCT_SEED))
    total_h, marks, block_s, blocks = build_ctx(trades, slot_arrivals)

    orig_maxpos = eng.MAX_POSITIONS
    for maxpos in [2, 3, 4]:
        for corr_th in [0.5, 0.6, 0.7]:
            if maxpos == 3 and corr_th == 0.6:
                label = "actuel_maxpos3_corr0.6 (=identique a actuel_1.5_0.2 ci-dessus)"
                rows.append(dict(label=label, profit_final_mean=rows[0]["profit_final_mean"],
                                 cash_worst=rows[0]["cash_worst"], p_year1_negatif=rows[0]["p_year1_negatif"],
                                 casses_final=rows[0]["casses_final"], maxpos=3, corr_threshold=0.6))
                continue
            t0 = time.time()
            excluded_map = precompute_correlation_pairs(tickers, corr_matrix, corr_th)
            eng.MAX_POSITIONS = maxpos
            df = eng.run_variant(trades, slot_arrivals, blocks, block_s, total_h, marks, market_data, excluded_map,
                                 RISK, RISK, "event", None, 2000, 42)
            eng.MAX_POSITIONS = orig_maxpos
            df.to_csv(f"point5_maxpos{maxpos}_corr{str(corr_th).replace('.', '_')}.csv", index=False)
            row = summarize(df, f"maxpos{maxpos}_corr{corr_th}", {"maxpos": maxpos, "corr_threshold": corr_th})
            rows.append(row)
            print(f"  maxpos={maxpos} corr={corr_th} : profit {row['profit_final_mean']:+,.0f}$ | "
                  f"cash pire cas {row['cash_worst']:,.0f}$ | P(an1<0) {row['p_year1_negatif']:.2f}% | "
                  f"casses {row['casses_final']:.1f} ({time.time()-t0:.0f}s)")
        pd.DataFrame(rows).to_csv("point5_summary_partial.csv", index=False)

    out = pd.DataFrame(rows)
    out.to_csv("point5_summary_final.csv", index=False)
    best = out.loc[out["profit_final_mean"].idxmax()]
    print(f"\nMeilleure combinaison (profit final) : {best['label']} -> {best['profit_final_mean']:+,.0f}$")
    print(f"\nTerminé en {time.time()-t_start:.0f}s.")


if __name__ == "__main__":
    main()
