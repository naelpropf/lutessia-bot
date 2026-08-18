"""
Section 3 (08/12, prompt utilisateur) : confirmation n=600+cascade de la
Stratégie B (canal contrarian, RR 0,75-1,25) SEULE, en isolation -- un seul
trader, flotte simple standard (identique a Run C/Run F, decision #16
§1.8/§2.35bis registre_parametres_projet.md), mais alimentee par la
population contrarian au lieu de la population standard (>=1,25). Deux
plafonds (1000$, 3000$).

Base = structure_pistes_2026-08-11.py (moteur flotte simple deja audite),
SEULE modification : la population source. Aucune autre logique touchee.

N'importe pas ce script directement (convention du projet).
"""
import random
import sys
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
from point_liquidity_rules import CORR_TH, DAY_SECONDS
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
import etape_e_fleet_integration as ei

import importlib.util
spec = importlib.util.spec_from_file_location("sp", "structure_pistes_2026-08-11.py")
sp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sp)

EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK = 1.25, 1.90, 1.75
COMMON_KW = dict(b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True,
                  ftmo_discount=True, gft_goat_guard=True, payout_cycle=True)


def contrarian_population():
    pop = build_population_with_trailing("fixed", 0.15, min_rr=0.75, verbose=False)
    band = pop[(pop["rr_tp1"] >= 0.75) & (pop["rr_tp1"] < 1.25)].copy()
    return band.reset_index(drop=True)


def run_sweep(n_sims, ceilings, seed=9999):
    cpop = contrarian_population()
    print(f"[verif] population Strategie B (0.75<=rr_tp1<1.25) : {len(cpop)} trades, "
          f"winrate={(cpop['r_trailing']>0).mean():.3f} EV={cpop['r_trailing'].mean():+.3f}R")
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(cpop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)
    seq = ei.seq_grouped_multi(1000, 15000, 25000, 25000)
    config = ei.CONFIG_REF

    rows = []
    for ceiling in ceilings:
        rng_wr = random.Random(seed)
        rng_boot = random.Random(seed + 1)
        recs = []
        t0 = time.time()
        for run_idx in range(n_sims):
            wr_draw = rng_wr.betavariate(ei.ALPHA_POST, ei.BETA_POST)
            trades, slot_arrivals = eng.build_flexible_population(cpop, wr_draw, 1.0, False, random.Random(rng_boot.random()))
            block_seconds = 2 * 30 * DAY_SECONDS
            blocks = build_blocks(trades, slot_arrivals, block_seconds)
            target_duration = slot_arrivals[-1]
            raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot, target_duration)
            order = list(range(len(raw_trades)))
            res = sp.run_one(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, seq, config,
                              ei.DEFAULT_EMERGENCY, EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                              ei.EXTRA_THRESHOLD_MULT, section=None, **COMMON_KW)
            recs.append(res)
        df = pd.DataFrame(recs)
        net = df["final_net_split"] - df["is_paid_cum"]
        year1_neg = df["year1_net_split"] < 0
        row = dict(ceiling=ceiling, n=len(df),
                   profit_moyen=net.mean(), profit_median=net.median(),
                   solde_negatif_annee4=(net < 0).mean() * 100, hit_ceiling_pct=df["hit_ceiling"].mean() * 100,
                   annee1_neg=year1_neg.mean() * 100)
        rows.append(row)
        print(f"[ceiling={ceiling:.0f}$] profit_moyen={row['profit_moyen']:+,.0f}$ profit_median={row['profit_median']:+,.0f}$ "
              f"solde_negatif_annee4={row['solde_negatif_annee4']:.2f}% hit_ceiling={row['hit_ceiling_pct']:.2f}% "
              f"annee1<0={row['annee1_neg']:.2f}% ({time.time()-t0:.0f}s)")
        pd.DataFrame(rows).to_csv(f"strategy_b_isolation_n{n_sims}.csv", index=False)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    t_start = time.time()
    import rr_threshold_test as rrt
    print(f"[verif] HIST_PATH = {rrt.HIST_PATH}, FIRM_MAX_ACCOUNTS Blueberry = {ei.FIRM_MAX_ACCOUNTS['Blueberry']}")
    run_sweep(n_sims, (1000.0, 3000.0))
    print(f"\nTermine en {time.time()-t_start:.0f}s.")
