"""
Illustration demandee explicitement (08/12) : trouver un run concret ou la
reserve commune (config 4, A/B + reserve_pooled=True) a evite un coup dur
qui se serait produit sous reserve separee (config 3, A/B + reserve_pooled=
False) sur le MEME tirage de marche (meme seed, meme run_idx -> memes trades
pour T1 ET T2, seule la mecanique de reserve differe entre les 2 runs).

N'importe pas ce script directement (convention du projet).
"""
import importlib.util
import random

spec = importlib.util.spec_from_file_location("dt", "dual_trader_2026-08-11.py")
dt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dt)

import robustness_5ers_risk_challenge as eng
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from point_liquidity_rules import DAY_SECONDS
import etape_e_fleet_integration as ei

SEED = 9999
CEILING = 1000.0
N_SCAN = 80

pop, market_data, excluded_map, seq, config = dt._common_setup()
cpop = dt._contrarian_population()

rng_wr = random.Random(SEED)
rng_boot = random.Random(SEED + 1)
rng_wr_c = random.Random(SEED + 2)
rng_boot_c = random.Random(SEED + 3)

candidates = []
for run_idx in range(N_SCAN):
    wr_draw = rng_wr.betavariate(ei.ALPHA_POST, ei.BETA_POST)
    trades, slot_arrivals = eng.build_flexible_population(pop, wr_draw, 1.0, False, random.Random(rng_boot.random()))
    block_seconds = 2 * 30 * DAY_SECONDS
    blocks = build_blocks(trades, slot_arrivals, block_seconds)
    target_duration = slot_arrivals[-1]
    raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot, target_duration)
    order = list(range(len(raw_trades)))

    wr_draw_c = rng_wr_c.betavariate(ei.ALPHA_POST, ei.BETA_POST)
    trades_c, slots_c = eng.build_flexible_population(cpop, wr_draw_c, 1.0, False, random.Random(rng_boot_c.random()))
    blocks_c = build_blocks(trades_c, slots_c, block_seconds)
    raw_trades_c, raw_slots_c = build_full_block_bootstrap_sequence(blocks_c, block_seconds, rng_boot_c, target_duration)

    kw = dict(ceiling_combined=CEILING, bb_variant="split", spec_variant="rr_band",
              contrarian_trades=raw_trades_c, contrarian_slots=raw_slots_c)
    res_sep = dt.run_dual(raw_trades, raw_slots, market_data, excluded_map, order, seq, config,
                           ei.DEFAULT_EMERGENCY, dt.EVAL_RISK, dt.FLEET_RISK, dt.GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                           ei.EXTRA_THRESHOLD_MULT, reserve_pooled=False, **kw)
    res_pool = dt.run_dual(raw_trades, raw_slots, market_data, excluded_map, order, seq, config,
                            ei.DEFAULT_EMERGENCY, dt.EVAL_RISK, dt.FLEET_RISK, dt.GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                            ei.EXTRA_THRESHOLD_MULT, reserve_pooled=True, **kw)

    sep_hc = res_sep["combined_hit_ceiling"]
    pool_hc = res_pool["combined_hit_ceiling"]
    interesting = sep_hc and not pool_hc
    print(f"run={run_idx:3d}  separee: hit_ceiling={sep_hc} T1_net={res_sep['T1_net']:+,.0f} T2_net={res_sep['T2_net']:+,.0f} "
          f"T1_min_reserve={res_sep['T1_reserve_min_full']:,.0f} T2_min_reserve={res_sep['T2_reserve_min_full']:,.0f}  |  "
          f"commune: hit_ceiling={pool_hc} T1_net={res_pool['T1_net']:+,.0f} T2_net={res_pool['T2_net']:+,.0f}"
          f"{'   <-- CANDIDAT (separee casse, commune sauve)' if interesting else ''}")
    candidates.append((run_idx, interesting, res_sep, res_pool))

print("\n--- Candidats ou la reserve commune evite un hit_ceiling que la reserve separee subit ---")
for run_idx, interesting, res_sep, res_pool in candidates:
    if interesting:
        print(f"  run {run_idx}")
