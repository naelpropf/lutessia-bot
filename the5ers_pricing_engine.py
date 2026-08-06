"""
Moteur The5%ers unifie avec bascule de prix de rachat realiste :
- Les 4 comptes INITIAUX sont toujours ouverts au prix Summer Plan (179$).
- Tout rachat apres une casse est facture 179$ tant que now < cutoff_seconds,
  PUIS au prix plein tarif POST_SUMMER_COST au-dela.

Cutoff par defaut : fin aout 2026, soit 26 jours a partir d'aujourd'hui
(2026-08-05), en supposant que la flotte demarre maintenant (t=0 de la
simulation = lancement reel). Sur les ~19,5 a 30,9 casses moyennes deja
mesurees en annee 1, la quasi-totalite tombent donc apres le cutoff.

PRIX POST-SUMMER-PLAN (point 1, sourcE) : 545$ pour le 100K High Stakes
2-Step. Source directe et officielle : annonce The5ers sur X/Twitter
(@the5erstrading, 16 jan. 2025) : "Starting January 16, 2025, the prices
for our 100K and 60K High Stakes accounts will be updated to $545 and $329,
respectively." Recoupe par propfirmmatch.com (100K High Stakes 2-Step :
545$ normal / 490,50$ avec code promo -10%, coherent avec 545*0.9=490.5).
Remplace l'estimation precedente de 495$ (moins bien sourcee, donnee datee
dec. 2024, avant la hausse de prix de janvier 2025).
"""
import random

import pandas as pd

from scaling_simulation import (
    CHALLENGE_TARGET_PCT, MIN_TRADING_DAYS, BREAK_DD_PCT, RESERVE_SHARE, feasible_risk_pct,
)
from monte_carlo_simulation import N_SIMULATIONS
from reference_metrics_final import build_full_block_bootstrap_sequence

PALIER_100K = 100000
SUMMER_COST = 179
POST_SUMMER_COST = 545  # source : annonce officielle The5ers (X, 16/01/2025)
DAILY_LOSS_PCT_5ERS = 3.0

DAY_SECONDS = 86400
DEFAULT_CUTOFF_DAYS = 26  # fin aout 2026, depuis aujourd'hui (2026-08-05)


def run_5ers_fleet(trades, slot_arrivals, market_data, excluded_map, order, mark_seconds_list,
                    n_accounts, low_risk, high_risk, ramp_trades, max_positions,
                    cutoff_seconds=DEFAULT_CUTOFF_DAYS * DAY_SECONDS, post_summer_cost=POST_SUMMER_COST):
    accounts = []
    for _ in range(n_accounts):
        accounts.append({
            "phase": "challenge", "cumulative_since_reset": 0.0,
            "peak_since_reset": 0.0, "trading_days_since_reset": set(), "open_positions": [],
            "total_funded_pnl": 0.0, "total_fees_paid": SUMMER_COST,
            "trades_taken": 0, "daily_pnl": {},
        })
    reserve = 0.0
    ever_funded = False
    real_cash_paid = SUMMER_COST * n_accounts
    total_breaks = 0

    marks_sorted = sorted(mark_seconds_list)
    mark_idx = 0
    snapshots = []

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]

        while mark_idx < len(marks_sorted) and now > marks_sorted[mark_idx]:
            combined_net = sum(a["total_funded_pnl"] - a["total_fees_paid"] for a in accounts)
            snapshots.append((marks_sorted[mark_idx], combined_net, real_cash_paid, total_breaks))
            mark_idx += 1

        for acc in accounts:
            close_time = now + trade["hold_seconds"]
            acc["open_positions"] = [(t, c) for (t, c) in acc["open_positions"] if c > now]
            if len(acc["open_positions"]) >= max_positions:
                continue
            if any(t in excluded_map[trade["ticker"]] for (t, _) in acc["open_positions"]):
                continue

            current_risk = low_risk if acc["trades_taken"] < ramp_trades else high_risk
            eff_risk, _ = feasible_risk_pct(trade["ticker"], trade["sl_distance"], PALIER_100K, current_risk, market_data)
            risk_amount = eff_risk / 100 * PALIER_100K
            pnl = trade["outcome_r"] * risk_amount

            acc["open_positions"].append((trade["ticker"], close_time))
            acc["cumulative_since_reset"] += pnl
            acc["peak_since_reset"] = max(acc["peak_since_reset"], acc["cumulative_since_reset"])
            acc["trading_days_since_reset"].add(int(now // 86400))
            acc["trades_taken"] += 1

            close_day = int(close_time // 86400)
            acc["daily_pnl"][close_day] = acc["daily_pnl"].get(close_day, 0.0) + pnl

            if acc["phase"] == "funded":
                acc["total_funded_pnl"] += pnl
                if pnl > 0:
                    reserve += pnl * RESERVE_SHARE

            trailing_dd = acc["peak_since_reset"] - acc["cumulative_since_reset"]
            daily_dd = -acc["daily_pnl"][close_day]
            broke = (trailing_dd >= BREAK_DD_PCT / 100 * PALIER_100K
                     or daily_dd >= DAILY_LOSS_PCT_5ERS / 100 * PALIER_100K)

            if broke:
                total_breaks += 1
                rebuy_cost = SUMMER_COST if now < cutoff_seconds else post_summer_cost
                if reserve >= rebuy_cost:
                    reserve -= rebuy_cost
                else:
                    shortfall = rebuy_cost - reserve
                    reserve = 0.0
                    if not ever_funded:
                        real_cash_paid += shortfall
                acc["total_fees_paid"] += rebuy_cost
                acc["phase"] = "challenge"
                acc["cumulative_since_reset"] = 0.0
                acc["peak_since_reset"] = 0.0
                acc["trading_days_since_reset"] = set()
                acc["daily_pnl"] = {}
                continue

            if (acc["phase"] == "challenge"
                    and acc["cumulative_since_reset"] >= CHALLENGE_TARGET_PCT / 100 * PALIER_100K
                    and len(acc["trading_days_since_reset"]) >= MIN_TRADING_DAYS):
                acc["phase"] = "funded"
                ever_funded = True
                acc["cumulative_since_reset"] = 0.0
                acc["peak_since_reset"] = 0.0
                acc["trading_days_since_reset"] = set()

    while mark_idx < len(marks_sorted):
        combined_net = sum(a["total_funded_pnl"] - a["total_fees_paid"] for a in accounts)
        snapshots.append((marks_sorted[mark_idx], combined_net, real_cash_paid, total_breaks))
        mark_idx += 1

    return snapshots


def run_variant(trades, slot_arrivals, blocks, block_seconds, target_duration, mark_seconds_list,
                market_data, excluded_map, **engine_kwargs):
    rng = random.Random(42)
    rows = []
    for _ in range(N_SIMULATIONS):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, target_duration)
        order = list(range(len(raw_trades)))
        snaps = run_5ers_fleet(raw_trades, raw_slots, market_data, excluded_map, order, mark_seconds_list,
                                **engine_kwargs)
        rows.append({
            "year1_net": snaps[0][1], "year1_cash": snaps[0][2], "year1_breaks": snaps[0][3],
            "final_net": snaps[1][1], "final_cash": snaps[1][2], "final_breaks": snaps[1][3],
        })
    return pd.DataFrame(rows)
