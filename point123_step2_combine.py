"""
Etape 2 (08/08) : combine la meilleure firm de demarrage (Blueberry seule,
cf. etape 1 -- cash pire cas 4 662$/5 328$, quasi identique a FundedNext mais
sans incertitude reglementaire) avec les leviers deja connus : 1er palier
reduit (25k) et variantes de rampe.
"""
import random
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
from point123_startingfirm_optimization import run_variant, sequence_single_firm_custom, summarize
from point2_sequencing_engine import build_ctx
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs

POP_CONSTRUCT_SEED = 123
CORR_TH = 0.6


def main():
    t_start = time.time()
    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

    seq = sequence_single_firm_custom("Blueberry")
    rows = []

    configs = [
        ("reference_2.0x5_50k", 2.0, 5, None),
        ("25k_seul_2.0x5", 2.0, 5, {"Blueberry": 25000}),
        ("ramp_1.0x5_50k", 1.0, 5, None),
        ("ramp_1.5x5_50k", 1.5, 5, None),
        ("ramp_1.0x10_50k", 1.0, 10, None),
        ("combo_25k_ramp1.0x5", 1.0, 5, {"Blueberry": 25000}),
        ("combo_25k_ramp1.5x5", 1.5, 5, {"Blueberry": 25000}),
    ]

    for wr_label, wr_target, suffix in [("40.09%_reel", None, "40_09pct"), ("37.66%_P10bayesien", 0.3766, "37_66pct")]:
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_target, 1.0, False, random.Random(POP_CONSTRUCT_SEED))
        total_h, marks, block_s, blocks = build_ctx(trades, slot_arrivals)
        print(f"\n{'='*100}\nWINRATE {wr_label}\n{'='*100}")

        for label, ramp_risk, ramp_n, tier_override in configs:
            t0 = time.time()
            df = run_variant(trades, slot_arrivals, blocks, block_s, total_h, marks, market_data, excluded_map,
                             seq, ramp_risk=ramp_risk, ramp_n=ramp_n, first_tier_overrides=tier_override,
                             n_sims=2000, seed=42)
            df.to_csv(f"point123_step2_{label}_{suffix}.csv", index=False)
            row = summarize(df, label, {"winrate": wr_label})
            rows.append(row)
            print(f"  [{label}] profit {row['profit_final_mean']:+,.0f}$ | cash pire cas {row['cash_worst']:,.0f}$ | "
                  f"P(an1<0) {row['p_year1_negatif']:.2f}% | delai {row['delai_structure_complete_median']:.0f}j ({time.time()-t0:.0f}s)")
        pd.DataFrame(rows).to_csv("point123_step2_summary_partial.csv", index=False)

    pd.DataFrame(rows).to_csv("point123_step2_summary_final.csv", index=False)
    print(f"\nTerminé en {time.time()-t_start:.0f}s.")


if __name__ == "__main__":
    main()
