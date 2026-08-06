"""
Point 3, impact flotte (07/08) :
a) Fermeture forcee 24h/week-end appliquee a TOUTE la flotte actuelle (config
   gagnante point1 : RR>=1,25/trail0,15 + maxpos2/corr0,7 + rampe2,0%/5) --
   compare au meme moteur SANS la contrainte.
b) Variante selective : FXIFY (deja parametree, cf. fxify_fleet_test.py --
   utilisee ici comme exemple concret de "firm supplementaire" puisqu'aucune
   firm reelle n'a ete nommee) ajoutee SANS la contrainte (deja connu :
   ~4,2M$ standalone 37,29%) vs AVEC la contrainte 24h/week-end appliquee
   uniquement a son propre segment, vs ne pas l'ajouter du tout.
"""
import random
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
import point3a_ramp_fixed as ramp_eng
from real_cash_risk_year1_block_bootstrap import DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs, N_SIMULATIONS
from point3_force_close_24h_weekend import build_force_closed_population
import tp_sequence_analysis as tpseq
from fxify_fleet_test import run_fxify_fleet, MAX_POSITIONS as FXIFY_MAXPOS

POP_CONSTRUCT_SEED = 123
TARGET_RISK = 2.5
RAMP_RISK, RAMP_N = 2.0, 5
MAXPOS, CORR_TH = 2, 0.7


def build_trades_from_pop(pop, outcome_col):
    sub = pop.sort_values("date_creation").reset_index(drop=True)
    t0 = sub["date_creation"].iloc[0]
    slot_arrivals = [(d - t0).total_seconds() for d in sub["date_creation"]]
    trades = []
    for _, row in sub.iterrows():
        hold_seconds = (row["resolution_time_est"] - row["date_creation"]).total_seconds()
        sl_distance = abs(row["prix_entree"] - row["stop_loss_init"])
        trades.append({"ticker": row["ticker"], "outcome_r": row[outcome_col], "sl_distance": sl_distance,
                       "hold_seconds": hold_seconds, "date": row["date_creation"]})
    return trades, slot_arrivals


def build_ctx(trades, slot_arrivals):
    total_horizon_seconds = slot_arrivals[-1]
    mark_seconds_list = [eng.YEAR_SECONDS, total_horizon_seconds]
    block_seconds = eng.BLOCK_MONTHS * DAYS_PER_MONTH * 86400
    blocks = eng.build_blocks(trades, slot_arrivals, block_seconds)
    return total_horizon_seconds, mark_seconds_list, block_seconds, blocks


def summarize(df, label):
    return dict(label=label, profit_final_mean=df["final_net"].mean(), cash_worst=df["final_cash"].max(),
               p_year1_negatif=(df["year1_net"] < 0).mean() * 100, casses_final=df["final_breaks"].mean())


def run_fxify_variant(trades, slot_arrivals, blocks, block_seconds, total_h, marks, market_data, excluded_map,
                      n_sims=2000, seed=42):
    rng = random.Random(seed)
    rows = []
    for _ in range(n_sims):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, total_h)
        order = list(range(len(raw_trades)))
        snaps = run_fxify_fleet(raw_trades, raw_slots, market_data, excluded_map, order, marks)
        rows.append({"year1_net": snaps[0][1], "final_net": snaps[1][1], "final_cash": snaps[1][2],
                     "final_breaks": snaps[1][3], "year1_cash": snaps[0][2]})
    return pd.DataFrame(rows)


def main():
    t_start = time.time()
    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    pop["yahoo_symbol"] = pop["ticker"].apply(tpseq.ticker_to_yahoo_symbol)
    import numpy as np
    pop["outcome_r_base"] = np.where(pop["statut_final"] == "OBJECTIF ATTEINT", pop["r_trailing"], -1.0)
    pop_forced = build_force_closed_population(pop)

    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map_07 = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)
    excluded_map_06 = precompute_correlation_pairs(tickers, corr_matrix, 0.6)

    rows = []
    orig_maxpos = eng.MAX_POSITIONS

    print("=" * 100 + "\nPART A -- FERMETURE FORCEE GLOBALE (toute la flotte, config gagnante point1)\n" + "=" * 100)
    for label, outcome_col, excluded_map in [("sans_contrainte", "outcome_r_base", excluded_map_07),
                                             ("avec_force_close_24h", "outcome_r_forced", excluded_map_07)]:
        t0 = time.time()
        trades, slot_arrivals = build_trades_from_pop(pop_forced, outcome_col)
        total_h, marks, block_s, blocks = build_ctx(trades, slot_arrivals)
        eng.MAX_POSITIONS = MAXPOS
        df = ramp_eng.run_variant_ramp(trades, slot_arrivals, blocks, block_s, total_h, marks, market_data,
                                       excluded_map, RAMP_RISK, RAMP_N, TARGET_RISK, n_sims=2000, seed=42)
        eng.MAX_POSITIONS = orig_maxpos
        df.to_csv(f"point3a_fleet_{label}.csv", index=False)
        row = summarize(df, label)
        rows.append(row)
        print(f"  [{label}] profit {row['profit_final_mean']:+,.0f}$ | cash pire cas {row['cash_worst']:,.0f}$ | "
              f"P(an1<0) {row['p_year1_negatif']:.2f}% | casses {row['casses_final']:.1f} ({time.time()-t0:.0f}s)")
    pd.DataFrame(rows).to_csv("point3_summary_partial.csv", index=False)

    print("\n" + "=" * 100 + "\nPART B -- VARIANTE SELECTIVE (FXIFY comme exemple de firm additionnelle)\n" + "=" * 100)
    for label, outcome_col in [("fxify_sans_contrainte", "outcome_r_base"),
                               ("fxify_avec_force_close_24h", "outcome_r_forced")]:
        t0 = time.time()
        trades, slot_arrivals = build_trades_from_pop(pop_forced, outcome_col)
        total_h, marks, block_s, blocks = build_ctx(trades, slot_arrivals)
        df = run_fxify_variant(trades, slot_arrivals, blocks, block_s, total_h, marks, market_data, excluded_map_06)
        df.to_csv(f"point3b_{label}.csv", index=False)
        row = summarize(df, label)
        rows.append(row)
        print(f"  [{label}] profit standalone FXIFY {row['profit_final_mean']:+,.0f}$ | cash pire cas {row['cash_worst']:,.0f}$ | "
              f"P(an1<0) {row['p_year1_negatif']:.2f}% | casses {row['casses_final']:.1f} ({time.time()-t0:.0f}s)")

    out = pd.DataFrame(rows)
    out.to_csv("point3_summary_final.csv", index=False)

    baseline_row = next(r for r in rows if r["label"] == "sans_contrainte")
    fxify_constrained = next(r for r in rows if r["label"] == "fxify_avec_force_close_24h")
    gain_net = fxify_constrained["profit_final_mean"]
    print(f"\nGain net d'ajouter FXIFY AVEC la contrainte 24h/week-end (vs ne pas l'ajouter) : "
          f"{gain_net:+,.0f}$ sur son propre segment (a additionner a la flotte de base, RNG non aligne "
          f"donc addition approximative -- cf. rapport pour la mise en garde methodologique)")
    print(f"\nTerminé en {time.time()-t_start:.0f}s.")


if __name__ == "__main__":
    main()
