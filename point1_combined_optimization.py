"""
Point 1 (07/08) : combine RR>=1,25 / trailing 0,15xSL (decouverte majeure de la
session precedente, domine largement la config verrouillee) avec maxpos=2,
correlation=0,7, et la rampe 2,0%/5 trades (elle aussi decouverte gagnante de
la session precedente) -- 4 configs pour isoler l'apport de chaque axe.
"""
import random
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
import point3a_ramp_fixed as ramp_eng
from real_cash_risk_year1_block_bootstrap import DAYS_PER_MONTH
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs

POP_CONSTRUCT_SEED = 123
TARGET_RISK = 2.5
RAMP_RISK, RAMP_N = 2.0, 5


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
    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map_06 = precompute_correlation_pairs(tickers, corr_matrix, 0.6)
    excluded_map_07 = precompute_correlation_pairs(tickers, corr_matrix, 0.7)

    rows = []
    orig_maxpos = eng.MAX_POSITIONS

    for wr_label, wr_target, suffix in [("37.29%", None, "37_29pct"), ("32%", 0.32, "32pct")]:
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_target, 1.0, False, random.Random(POP_CONSTRUCT_SEED))
        total_h, marks, block_s, blocks = build_ctx(trades, slot_arrivals)
        print(f"\n{'='*100}\nWINRATE {wr_label} (population RR>=1.25, trailing 0.15x)\n{'='*100}")

        # a) RR1.25/trail0.15 seul (maxpos3/corr0.6 standard, rampe standard 0.5%/12)
        t0 = time.time()
        df_a = eng.run_variant(trades, slot_arrivals, blocks, block_s, total_h, marks, market_data, excluded_map_06,
                               TARGET_RISK, TARGET_RISK, "event", None, 2000, 42)
        df_a.to_csv(f"point1_a_seul_{suffix}.csv", index=False)
        row_a = summarize(df_a, "a_RR1.25_trail0.15_seul", {"winrate": wr_label})
        rows.append(row_a)
        print(f"  a) seul : profit {row_a['profit_final_mean']:+,.0f}$ | cash pire cas {row_a['cash_worst']:,.0f}$ | "
              f"P(an1<0) {row_a['p_year1_negatif']:.2f}% | casses {row_a['casses_final']:.1f} ({time.time()-t0:.0f}s)")

        # b) + maxpos=2/corr=0.7
        t0 = time.time()
        eng.MAX_POSITIONS = 2
        df_b = eng.run_variant(trades, slot_arrivals, blocks, block_s, total_h, marks, market_data, excluded_map_07,
                               TARGET_RISK, TARGET_RISK, "event", None, 2000, 42)
        eng.MAX_POSITIONS = orig_maxpos
        df_b.to_csv(f"point1_b_maxposcorr_{suffix}.csv", index=False)
        row_b = summarize(df_b, "b_+maxpos2_corr0.7", {"winrate": wr_label})
        rows.append(row_b)
        print(f"  b) +maxpos2/corr0.7 : profit {row_b['profit_final_mean']:+,.0f}$ | cash pire cas {row_b['cash_worst']:,.0f}$ | "
              f"P(an1<0) {row_b['p_year1_negatif']:.2f}% | casses {row_b['casses_final']:.1f} ({time.time()-t0:.0f}s)")

        # c) + rampe 2.0%/5 (maxpos3/corr0.6 standard)
        t0 = time.time()
        df_c = ramp_eng.run_variant_ramp(trades, slot_arrivals, blocks, block_s, total_h, marks, market_data,
                                         excluded_map_06, RAMP_RISK, RAMP_N, TARGET_RISK, n_sims=2000, seed=42)
        df_c.to_csv(f"point1_c_rampe_{suffix}.csv", index=False)
        row_c = summarize(df_c, "c_+rampe2.0x5", {"winrate": wr_label})
        rows.append(row_c)
        print(f"  c) +rampe2.0%x5 : profit {row_c['profit_final_mean']:+,.0f}$ | cash pire cas {row_c['cash_worst']:,.0f}$ | "
              f"P(an1<0) {row_c['p_year1_negatif']:.2f}% | casses {row_c['casses_final']:.1f} ({time.time()-t0:.0f}s)")

        # d) tout combine : maxpos2/corr0.7 + rampe2.0%/5
        t0 = time.time()
        eng.MAX_POSITIONS = 2
        df_d = ramp_eng.run_variant_ramp(trades, slot_arrivals, blocks, block_s, total_h, marks, market_data,
                                         excluded_map_07, RAMP_RISK, RAMP_N, TARGET_RISK, n_sims=2000, seed=42)
        eng.MAX_POSITIONS = orig_maxpos
        df_d.to_csv(f"point1_d_tout_{suffix}.csv", index=False)
        row_d = summarize(df_d, "d_tout_combine", {"winrate": wr_label})
        rows.append(row_d)
        print(f"  d) TOUT combine : profit {row_d['profit_final_mean']:+,.0f}$ | cash pire cas {row_d['cash_worst']:,.0f}$ | "
              f"P(an1<0) {row_d['p_year1_negatif']:.2f}% | casses {row_d['casses_final']:.1f} ({time.time()-t0:.0f}s)")

        pd.DataFrame(rows).to_csv("point1_combined_summary_partial.csv", index=False)

    out = pd.DataFrame(rows)
    out.to_csv("point1_combined_summary_final.csv", index=False)
    best = out.loc[out["profit_final_mean"].idxmax()]
    print(f"\nMeilleure combinaison (profit final) : {best['label']} ({best['winrate']}) -> {best['profit_final_mean']:+,.0f}$")
    print(f"\nTerminé en {time.time()-t_start:.0f}s.")


if __name__ == "__main__":
    main()
