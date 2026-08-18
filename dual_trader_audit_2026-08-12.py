"""
Audit demande explicitement (08/12) : verification manuelle de 3 runs pris
au hasard parmi les ~300 de Section 1 (replication, separe+BB split,
3000$/3000$), meme seed=9999 que le run officiel -- avance le RNG
sequentiellement (comme replay_run202) jusqu'a chaque run_idx cible, capture
le journal complet + verification explicite que le plafond Blueberry
combine (400k$) n'est jamais depasse.

Indices choisis : random.Random(12345).sample(range(300), 3) -> [5, 152, 213]
(reproductible, documente, pas trie sur le volet).

N'importe pas ce script directement (convention du projet).
"""
import importlib.util
import json
import random

spec = importlib.util.spec_from_file_location("dt", "dual_trader_2026-08-11.py")
dt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dt)

import robustness_5ers_risk_challenge as eng
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from point_liquidity_rules import DAY_SECONDS
import etape_e_fleet_integration as ei

TARGET_RUNS = [5, 152, 213]
SEED = 9999
CEILINGS = {"T1": 3000.0, "T2": 3000.0}

pop, market_data, excluded_map, seq, config = dt._common_setup()

rng_wr = random.Random(SEED)
rng_boot = random.Random(SEED + 1)

max_target = max(TARGET_RUNS)
for run_idx in range(max_target + 1):
    wr_draw = rng_wr.betavariate(ei.ALPHA_POST, ei.BETA_POST)
    trades, slot_arrivals = eng.build_flexible_population(pop, wr_draw, 1.0, False, random.Random(rng_boot.random()))
    block_seconds = 2 * 30 * DAY_SECONDS
    blocks = build_blocks(trades, slot_arrivals, block_seconds)
    target_duration = slot_arrivals[-1]
    raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot, target_duration)
    order = list(range(len(raw_trades)))

    if run_idx not in TARGET_RUNS:
        continue

    res = dt.run_dual(raw_trades, raw_slots, market_data, excluded_map, order, seq, config,
                       ei.DEFAULT_EMERGENCY, dt.EVAL_RISK, dt.FLEET_RISK, dt.GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                       ei.EXTRA_THRESHOLD_MULT,
                       ceilings=CEILINGS, reserve_pooled=False, bb_variant="split", spec_variant="replication",
                       log_events=True)

    events = res.pop("event_log")
    print(f"\n{'='*90}\nRUN {run_idx}\n{'='*90}")
    print(f"T1_net={res['T1_net']:+,.0f}$ T2_net={res['T2_net']:+,.0f}$ "
          f"T1_hit_ceiling={res['T1_hit_ceiling']} T2_hit_ceiling={res['T2_hit_ceiling']} "
          f"combined_hit_ceiling={res['combined_hit_ceiling']}")
    print(f"BB combine final : T1_palier_sum={res['bb_T1_palier_sum']:,.0f}$ "
          f"({res['bb_T1_n_accounts']} comptes) + T2_palier_sum={res['bb_T2_palier_sum']:,.0f}$ "
          f"({res['bb_T2_n_accounts']} comptes) = {res['bb_used_shared_final']:,.0f}$ "
          f"(plafond combine = {dt.BB_COMBINED_CAP:,.0f}$, "
          f"{'OK <= plafond' if res['bb_used_shared_final'] <= dt.BB_COMBINED_CAP else 'VIOLATION !!'})")

    bb_events = [e for e in events if e["firm"] == "Blueberry"]
    print(f"\n-- Chronologie complete des evenements Blueberry ({len(bb_events)}) --")
    max_seen = 0.0
    for e in bb_events:
        max_seen = max(max_seen, e["bb_used_shared_combined"])
        print(f"  j={e['jour_simulation']:>7.1f} trader={e['trader']} type={e['type_evenement']:20s} "
              f"bb_used_shared_combined={e['bb_used_shared_combined']:>10,.0f}$  {e}")
    print(f"  --> MAX bb_used_shared_combined observe pendant le run : {max_seen:,.0f}$ "
          f"({'OK' if max_seen <= dt.BB_COMBINED_CAP else 'VIOLATION !!'})")

    casse_events = [e for e in events if e["type_evenement"] == "casse"]
    hc_events = [e for e in events if e["type_evenement"] == "hit_ceiling_touche"]
    print(f"\n-- Resume : {len(casse_events)} casses total (T1={sum(1 for e in casse_events if e['trader']=='T1')}, "
          f"T2={sum(1 for e in casse_events if e['trader']=='T2')}), {len(hc_events)} evenement(s) hit_ceiling_touche --")
    for e in hc_events:
        print(f"    hit_ceiling: j={e['jour_simulation']:.1f} trader={e['trader']} {e}")

    with open(f"dual_trader_audit_run{run_idx}.json", "w", encoding="utf-8") as fh:
        json.dump({"run_idx": run_idx, "result_summary": {k: v for k, v in res.items() if k != "event_log"},
                   "events": events}, fh, ensure_ascii=False, indent=1, default=str)
    print(f"\n[journal complet sauvegarde] dual_trader_audit_run{run_idx}.json ({len(events)} evenements)")
