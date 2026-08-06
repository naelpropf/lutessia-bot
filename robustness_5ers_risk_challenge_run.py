import random
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
from real_cash_risk_year1_block_bootstrap import DAYS_PER_MONTH

POP_CONSTRUCT_SEED = 123
GROWTH_FIXED_RISK = 2.5


def build_ctx(trades, slot_arrivals):
    total_horizon_seconds = slot_arrivals[-1]
    mark_seconds_list = [eng.YEAR_SECONDS, total_horizon_seconds]
    block_seconds = eng.BLOCK_MONTHS * DAYS_PER_MONTH * 86400
    blocks = eng.build_blocks(trades, slot_arrivals, block_seconds)
    return total_horizon_seconds, mark_seconds_list, block_seconds, blocks


def main():
    t_start = time.time()
    pop = eng.build_population_with_trailing("fixed", 0.2, verbose=False)
    market_data, excluded_map = eng.prep_common(pop)

    all_summary = []

    # ============================================================
    # PART 1 : risque differencie (growth 2.5% fixe, 5ers balaye)
    # ============================================================
    print("\n" + "#" * 100 + "\nPART 1 -- RISQUE DIFFERENCIE\n" + "#" * 100)
    for wr_label, wr_target, suffix in [("37.29%", None, "37_29pct"), ("32%", 0.32, "32pct")]:
        trades, slot_arrivals = eng.build_flexible_population(
            pop, wr_target, 1.0, False, random.Random(POP_CONSTRUCT_SEED))
        total_h, marks, block_s, blocks = build_ctx(trades, slot_arrivals)

        for fivers_risk in [1.0, 1.5, 2.0, 2.5]:
            t0 = time.time()
            df = eng.run_variant(trades, slot_arrivals, blocks, block_s, total_h, marks, market_data, excluded_map,
                                 GROWTH_FIXED_RISK, fivers_risk, "event", None, 2000, 42)
            df.to_csv(f"part1_diffrisk_growth2_5_5ers{str(fivers_risk).replace('.', '_')}_{suffix}.csv", index=False)
            row = eng.summarize(df, f"part1|{wr_label}|growth2.5|5ers{fivers_risk}",
                                {"winrate": wr_label, "growth_risk": GROWTH_FIXED_RISK, "fivers_risk": fivers_risk})
            all_summary.append(row)
            print(f"  [{wr_label}] growth=2.5% 5ers={fivers_risk}% : profit {row['profit_final_mean']:+,.0f}$ | "
                  f"cash pire cas {row['cash_worst']:,.0f}$ | P(an1<0) {row['p_year1_negatif']:.2f}% ({time.time()-t0:.0f}s)")
        pd.DataFrame(all_summary).to_csv("robustness_summary_partial.csv", index=False)

    # ============================================================
    # PART 2 : declencheur -- evenement vs delai fixe
    # ============================================================
    print("\n" + "#" * 100 + "\nPART 2 -- DECLENCHEUR 5ERS\n" + "#" * 100)
    for wr_label, wr_target, suffix in [("37.29%", None, "37_29pct"), ("32%", 0.32, "32pct")]:
        trades, slot_arrivals = eng.build_flexible_population(
            pop, wr_target, 1.0, False, random.Random(POP_CONSTRUCT_SEED))
        total_h, marks, block_s, blocks = build_ctx(trades, slot_arrivals)

        triggers = [("event", None)] + [("fixed_days", d) for d in [45, 60, 75, 90]]
        for trigger, delay in triggers:
            t0 = time.time()
            df = eng.run_variant(trades, slot_arrivals, blocks, block_s, total_h, marks, market_data, excluded_map,
                                 2.5, 2.5, trigger, delay, 2000, 42)
            label = trigger if trigger == "event" else f"fixed{delay}j"
            df.to_csv(f"part2_trigger_{label}_{suffix}.csv", index=False)
            row = eng.summarize(df, f"part2|{wr_label}|{label}", {"winrate": wr_label, "trigger": label})
            all_summary.append(row)
            print(f"  [{wr_label}] trigger={label} : profit {row['profit_final_mean']:+,.0f}$ | cash pire cas {row['cash_worst']:,.0f}$ "
                  f"| cash std {row['cash_std']:,.0f}$ | cash P90 {row['cash_p90']:,.0f}$ ({time.time()-t0:.0f}s)")
        pd.DataFrame(all_summary).to_csv("robustness_summary_partial.csv", index=False)

    # ============================================================
    # PART 3 : robustesse -- seed different/5000 runs, bornes IC winrate, stress RR
    # ============================================================
    print("\n" + "#" * 100 + "\nPART 3a -- SWEEP RISQUE 5000 RUNS, SEED DIFFERENT (123 au lieu de 42)\n" + "#" * 100)
    for wr_label, wr_target, suffix in [("37.29%", None, "37_29pct"), ("32%", 0.32, "32pct")]:
        trades, slot_arrivals = eng.build_flexible_population(
            pop, wr_target, 1.0, False, random.Random(POP_CONSTRUCT_SEED))
        total_h, marks, block_s, blocks = build_ctx(trades, slot_arrivals)
        for risk in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]:
            t0 = time.time()
            df = eng.run_variant(trades, slot_arrivals, blocks, block_s, total_h, marks, market_data, excluded_map,
                                 risk, risk, "event", None, 5000, 123)
            df.to_csv(f"part3a_5000runs_seed123_risk{str(risk).replace('.', '_')}_{suffix}.csv", index=False)
            row = eng.summarize(df, f"part3a|{wr_label}|risk{risk}", {"winrate": wr_label, "risk_pct": risk})
            all_summary.append(row)
            print(f"  [{wr_label}] risque={risk}% (5000 runs, seed 123) : profit {row['profit_final_mean']:+,.0f}$ | "
                  f"cash pire cas {row['cash_worst']:,.0f}$ | P(an1<0) {row['p_year1_negatif']:.2f}% ({time.time()-t0:.0f}s)")
        pd.DataFrame(all_summary).to_csv("robustness_summary_partial.csv", index=False)

    print("\n" + "#" * 100 + "\nPART 3b -- SWEEP RISQUE AUX BORNES IC95%% WINRATE (32.9%% / 41.7%%)\n" + "#" * 100)
    for wr_label, wr_target, suffix in [("32.9%", 0.329, "32_9pct"), ("41.7%", 0.417, "41_7pct")]:
        trades, slot_arrivals = eng.build_flexible_population(
            pop, wr_target, 1.0, False, random.Random(POP_CONSTRUCT_SEED))
        total_h, marks, block_s, blocks = build_ctx(trades, slot_arrivals)
        for risk in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]:
            t0 = time.time()
            df = eng.run_variant(trades, slot_arrivals, blocks, block_s, total_h, marks, market_data, excluded_map,
                                 risk, risk, "event", None, 2000, 42)
            df.to_csv(f"part3b_{suffix}_risk{str(risk).replace('.', '_')}.csv", index=False)
            row = eng.summarize(df, f"part3b|{wr_label}|risk{risk}", {"winrate": wr_label, "risk_pct": risk})
            all_summary.append(row)
            print(f"  [{wr_label}] risque={risk}% : profit {row['profit_final_mean']:+,.0f}$ | cash pire cas {row['cash_worst']:,.0f}$ "
                  f"| P(an1<0) {row['p_year1_negatif']:.2f}% ({time.time()-t0:.0f}s)")
        pd.DataFrame(all_summary).to_csv("robustness_summary_partial.csv", index=False)

    print("\n" + "#" * 100 + "\nPART 3c -- STRESS RR GAGNANTS (-10%% / -20%%), winrate 37.29%%\n" + "#" * 100)
    for stress_label, stress_factor in [("moins10pct", 0.9), ("moins20pct", 0.8)]:
        trades, slot_arrivals = eng.build_flexible_population(
            pop, None, stress_factor, False, random.Random(POP_CONSTRUCT_SEED))
        total_h, marks, block_s, blocks = build_ctx(trades, slot_arrivals)
        for risk in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]:
            t0 = time.time()
            df = eng.run_variant(trades, slot_arrivals, blocks, block_s, total_h, marks, market_data, excluded_map,
                                 risk, risk, "event", None, 2000, 42)
            df.to_csv(f"part3c_rrstress_{stress_label}_risk{str(risk).replace('.', '_')}.csv", index=False)
            row = eng.summarize(df, f"part3c|rr{stress_label}|risk{risk}",
                                {"rr_stress": stress_label, "risk_pct": risk})
            all_summary.append(row)
            print(f"  [RR {stress_label}] risque={risk}% : profit {row['profit_final_mean']:+,.0f}$ | "
                  f"cash pire cas {row['cash_worst']:,.0f}$ | P(an1<0) {row['p_year1_negatif']:.2f}% ({time.time()-t0:.0f}s)")
        pd.DataFrame(all_summary).to_csv("robustness_summary_partial.csv", index=False)

    # ============================================================
    # PART 4 : slippage reel (deja mesure Dukascopy) substitue dans le sweep de risque
    # ============================================================
    print("\n" + "#" * 100 + "\nPART 4 -- RE-TEST AVEC SLIPPAGE REEL (Dukascopy), winrate 37.29%%\n" + "#" * 100)
    trades, slot_arrivals = eng.build_flexible_population(
        pop, None, 1.0, True, random.Random(POP_CONSTRUCT_SEED))
    total_h, marks, block_s, blocks = build_ctx(trades, slot_arrivals)
    for risk in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]:
        t0 = time.time()
        df = eng.run_variant(trades, slot_arrivals, blocks, block_s, total_h, marks, market_data, excluded_map,
                             risk, risk, "event", None, 2000, 42)
        df.to_csv(f"part4_slippage_risk{str(risk).replace('.', '_')}.csv", index=False)
        row = eng.summarize(df, f"part4|slippage|risk{risk}", {"risk_pct": risk})
        all_summary.append(row)
        print(f"  [slippage reel] risque={risk}% : profit {row['profit_final_mean']:+,.0f}$ | cash pire cas {row['cash_worst']:,.0f}$ "
              f"| P(an1<0) {row['p_year1_negatif']:.2f}% ({time.time()-t0:.0f}s)")

    out = pd.DataFrame(all_summary)
    out.to_csv("robustness_summary_final.csv", index=False)
    print(f"\nTerminé en {time.time()-t_start:.0f}s ({(time.time()-t_start)/60:.1f} min).")


if __name__ == "__main__":
    main()
