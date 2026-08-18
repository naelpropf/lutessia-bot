"""
Replay CIBLE (08/11) : reproduit EXACTEMENT le run_idx=202 (seed=9999,
meme boucle que etape_am_deep_dive_negative_runs_2026-08-11.py) pour
tracer la date HISTORIQUE REELLE (trade["date"], survit au block
bootstrap -- confirme en lisant robustesse_5ers_risk_challenge.
build_flexible_population) derriere chaque casse, notamment dans le
cluster dense jours 284-399 identifie par l'analyse des journaux deja
extraits.

Reproductibilite : les RNG (rng_wr/rng_boot) avancent sequentiellement a
chaque iteration -- pour obtenir EXACTEMENT le tirage du run 202, on
rejoue les iterations 0..201 SANS logging (rapide, juste pour avancer
l'etat RNG a l'identique), puis on capture l'iteration 202 avec logging
complet (chaque casse -> date historique reelle en plus des champs deja
loggues).

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

TARGET_RUN_IDX = 202
YEAR_SECONDS = 365.25 * DAY_SECONDS


def replay(ceiling, n_target=TARGET_RUN_IDX, seed=9999):
    import importlib.util
    spec = importlib.util.spec_from_file_location("etape_am_mod", "etape_am_deep_dive_negative_runs_2026-08-11.py")
    etape_am = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(etape_am)

    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)
    seq = ei.seq_grouped_multi(1000, 15000, 25000, 25000)
    config = ei.CONFIG_REF
    EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK = 1.25, 1.90, 1.75

    rng_wr = random.Random(seed)
    rng_boot = random.Random(seed + 1)

    raw_trades = None
    for run_idx in range(n_target + 1):
        wr_draw = rng_wr.betavariate(ei.ALPHA_POST, ei.BETA_POST)
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_draw, 1.0, False, random.Random(rng_boot.random()))
        block_seconds = 2 * 30 * DAY_SECONDS
        blocks = build_blocks(trades, slot_arrivals, block_seconds)
        target_duration = slot_arrivals[-1]
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot, target_duration)
        if run_idx < n_target:
            continue
        order = list(range(len(raw_trades)))
        res = etape_am.run_one(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, seq, config,
                                ei.DEFAULT_EMERGENCY, EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                                ei.EXTRA_THRESHOLD_MULT, b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True,
                                ftmo_discount=True, gft_goat_guard=True, payout_cycle=True, log_events=True)
        net = res["final_net_split"] - res["is_paid_cum"]
        print(f"[verif] ceiling={ceiling:.0f}$ run_idx={run_idx} net_final={net:+.2f}$ "
              f"(doit matcher les journaux deja extraits : -72010$ @1000$ / -73995$ @3000$)")
        return res["event_log"], raw_trades, raw_slots


if __name__ == "__main__":
    t0 = time.time()
    ceiling = float(sys.argv[1]) if len(sys.argv) > 1 else 1000.0
    event_log, raw_trades, raw_slots = replay(ceiling)

    # Construit un index temps-simulation -> date historique reelle a partir
    # de la sequence brute (raw_trades porte trade["date"], raw_slots le jour
    # de simulation correspondant -- permet de dater n'importe quel jour de
    # simulation en cherchant le trade le plus proche).
    import bisect
    slot_days = [s / 86400.0 for s in raw_slots]

    def sim_day_to_real_date(sim_day):
        idx = bisect.bisect_left(slot_days, sim_day)
        idx = min(idx, len(raw_trades) - 1)
        return raw_trades[idx]["date"]

    casses = [e for e in event_log if e["type_evenement"] == "casse"]
    casses.sort(key=lambda e: e["jour_simulation"])
    print(f"\n{len(casses)} casses -- dates historiques reelles sous-jacentes :")
    for c in casses:
        real_date = sim_day_to_real_date(c["jour_simulation"])
        print(f"  jour_sim={c['jour_simulation']:7.2f}  firm={c['firm']:12s}  ticker={c.get('ticker','?'):8s}  "
              f"R={c.get('r_realise', float('nan')):+.2f}  date_reelle={real_date}")

    import json
    out = [{"jour_simulation": c["jour_simulation"], "firm": c["firm"], "ticker": c.get("ticker"),
            "r_realise": c.get("r_realise"), "date_historique_reelle": str(sim_day_to_real_date(c["jour_simulation"]))}
           for c in casses]
    fname = f"deep_dive_run202_dates_ceiling{int(ceiling)}.json"
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(f"\nEcrit dans {fname}")
    print(f"Termine en {time.time()-t0:.0f}s.")
