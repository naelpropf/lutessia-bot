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
TARGET = 67

pop, market_data, excluded_map, seq, config = dt._common_setup()
cpop = dt._contrarian_population()

rng_wr = random.Random(SEED)
rng_boot = random.Random(SEED + 1)
rng_wr_c = random.Random(SEED + 2)
rng_boot_c = random.Random(SEED + 3)

for run_idx in range(TARGET + 1):
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
          contrarian_trades=raw_trades_c, contrarian_slots=raw_slots_c, log_events=True)

for label, pooled in (("SEPAREE", False), ("COMMUNE", True)):
    res = dt.run_dual(raw_trades, raw_slots, market_data, excluded_map, order, seq, config,
                       ei.DEFAULT_EMERGENCY, dt.EVAL_RISK, dt.FLEET_RISK, dt.GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                       ei.EXTRA_THRESHOLD_MULT, reserve_pooled=pooled, **kw)
    events = res.pop("event_log")
    print(f"\n{'='*100}\nRUN {TARGET} -- RESERVE {label}\n{'='*100}")
    print(f"T1_net={res['T1_net']:+,.0f}$  T2_net={res['T2_net']:+,.0f}$  hit_ceiling_combine={res['combined_hit_ceiling']}  "
          f"real_cash_paid_final={res['combined_real_cash_paid_final']:,.0f}$ (plafond={CEILING:,.0f}$)")
    hc_events = [e for e in events if e["type_evenement"] == "hit_ceiling_touche"]
    for e in hc_events:
        print(f"  hit_ceiling_touche : {e}")
    # evenements autour du premier hit_ceiling (ou, si aucun, les 15 premiers evenements notables)
    if hc_events:
        t0 = hc_events[0]["jour_simulation"]
        window = [e for e in events if abs(e["jour_simulation"] - t0) <= 5 and e["type_evenement"] != "casse"]
        print(f"\n  -- Evenements non-casse dans les +/-5j autour du 1er hit_ceiling (j={t0}) --")
        for e in window:
            print(f"    j={e['jour_simulation']:>7.1f} trader={e.get('trader')} firm={e.get('firm')} type={e['type_evenement']}")
        casses_window = [e for e in events if abs(e["jour_simulation"] - t0) <= 5 and e["type_evenement"] == "casse"]
        print(f"  -- {len(casses_window)} casse(s) dans la meme fenetre --")
        for e in casses_window[:20]:
            print(f"    j={e['jour_simulation']:>7.1f} trader={e['trader']} firm={e['firm']} ticker={e.get('ticker')} r={e.get('r_realise')}")
