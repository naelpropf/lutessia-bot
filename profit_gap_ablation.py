"""
Ablation du profit net moyen sur l'horizon complet (~3.96 ans), risque 2%/compte,
winrate réel 37.29% -- isole la contribution de CHACUN des changements entre
risk_levels_trailing_02_summary.csv (10 335 102€ cité) et le run de ce soir (7 867 591€) :
  V0 : comptabilité "tout P&L" (challenge+financé compté comme profit, BUG identifié)
       + bootstrap permutation + réserve non poolée -- reproduit l'ancien script
  V1 : + comptabilité FINANCÉ SEULEMENT (challenge-phase P&L exclu du profit réel)
  V2 : + block bootstrap 2 mois (structure temporelle préservée)
  V3 : + réserve poolée = MOTEUR ACTUEL (immunité exclue : n'affecte que real_cash_paid,
       jamais net_profit -- sans effet sur cette investigation)
"""
import random

import pandas as pd

from scaling_simulation import (
    TIER_SEQUENCE, CHALLENGE_COST, UPGRADE_COST, CHALLENGE_TARGET_PCT,
    MIN_TRADING_DAYS, BREAK_DD_PCT, RESERVE_SHARE, MAX_POSITIONS, CORR_THRESHOLD,
    feasible_risk_pct, load_market_data,
)
from monte_carlo_simulation import precompute_correlation_pairs, N_SIMULATIONS
from trailing_payoff_population import build_population_with_trailing, build_trades_trailing
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence

N_ACCOUNTS = 3
BLOCK_MONTHS = 2
RISK_PCT = 2.0


def run_one_account(trades, slot_arrivals, market_data, excluded_map, order, shared_reserve, pooled, funded_only):
    palier = TIER_SEQUENCE[0]
    phase = "challenge"
    cumulative_since_reset = 0.0
    peak_since_reset = 0.0
    trading_days_since_reset = set()
    open_positions = []
    total_pnl_counted = 0.0
    total_fees_paid = CHALLENGE_COST[palier]

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]
        close_time = now + trade["hold_seconds"]
        open_positions = [(t, c) for (t, c) in open_positions if c > now]
        if len(open_positions) >= MAX_POSITIONS:
            continue
        if any(t in excluded_map[trade["ticker"]] for (t, _) in open_positions):
            continue

        eff_risk, _ = feasible_risk_pct(trade["ticker"], trade["sl_distance"], palier, RISK_PCT, market_data)
        risk_amount = eff_risk / 100 * palier
        pnl = trade["outcome_r"] * risk_amount

        open_positions.append((trade["ticker"], close_time))
        cumulative_since_reset += pnl
        peak_since_reset = max(peak_since_reset, cumulative_since_reset)
        trading_days_since_reset.add(int(now // 86400))

        if funded_only:
            if phase == "funded":
                total_pnl_counted += pnl
                if pnl > 0:
                    shared_reserve["reserve"] += pnl * RESERVE_SHARE
        else:
            total_pnl_counted += pnl  # BUG reproduit : compte aussi le P&L en phase challenge
            if phase == "funded" and pnl > 0:
                shared_reserve["reserve"] += pnl * RESERVE_SHARE

        drawdown = peak_since_reset - cumulative_since_reset
        if drawdown >= BREAK_DD_PCT / 100 * palier:
            cost = CHALLENGE_COST[palier]
            if shared_reserve["reserve"] >= cost:
                shared_reserve["reserve"] -= cost
            else:
                shared_reserve["reserve"] = 0.0
            total_fees_paid += cost
            phase = "challenge"
            cumulative_since_reset = 0.0
            peak_since_reset = 0.0
            trading_days_since_reset = set()
            continue

        if (phase == "challenge" and cumulative_since_reset >= CHALLENGE_TARGET_PCT / 100 * palier
                and len(trading_days_since_reset) >= MIN_TRADING_DAYS):
            phase = "funded"
            cumulative_since_reset = 0.0
            peak_since_reset = 0.0
            trading_days_since_reset = set()

        if phase == "funded":
            idx = TIER_SEQUENCE.index(palier)
            if idx + 1 < len(TIER_SEQUENCE):
                next_tier = TIER_SEQUENCE[idx + 1]
                cost = UPGRADE_COST[next_tier]
                if shared_reserve["reserve"] >= cost:
                    shared_reserve["reserve"] -= cost
                    total_fees_paid += cost
                    palier = next_tier
                    phase = "challenge"
                    cumulative_since_reset = 0.0
                    peak_since_reset = 0.0
                    trading_days_since_reset = set()

    return total_pnl_counted - total_fees_paid


def run_fleet_one(trades, slot_arrivals, market_data, excluded_map, order, pooled, funded_only):
    if pooled:
        shared = {"reserve": 0.0}
        states = [shared] * N_ACCOUNTS
    else:
        states = [{"reserve": 0.0} for _ in range(N_ACCOUNTS)]
    return sum(run_one_account(trades, slot_arrivals, market_data, excluded_map, order, s, pooled, funded_only)
               for s in states)


def run_variant(trades, slot_arrivals, blocks, block_seconds, total_horizon_seconds, market_data, excluded_map,
                 bootstrap, pooled, funded_only, label):
    rng = random.Random(42)
    profits = []
    for _ in range(N_SIMULATIONS):
        if bootstrap == "permutation":
            order = list(range(len(trades)))
            rng.shuffle(order)
            trades_run, slots_run = trades, slot_arrivals
        else:
            raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, total_horizon_seconds)
            trades_run, slots_run = raw_trades, raw_slots
            order = list(range(len(trades_run)))
        profits.append(run_fleet_one(trades_run, slots_run, market_data, excluded_map, order, pooled, funded_only))

    s = pd.Series(profits)
    print(f"\n--- {label} ---")
    print(f"  bootstrap={bootstrap:<12} pooled={pooled!s:<6} funded_only={funded_only!s:<6}")
    print(f"  Profit net moyen : {s.mean():,.0f}€ | médian {s.median():,.0f}€")
    return s.mean()


def main():
    pop = build_population_with_trailing("fixed", 0.2, verbose=False)
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    sub, trades, slot_arrivals = build_trades_trailing(pop)
    tickers = sorted(set(t["ticker"] for t in trades))
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    total_horizon_seconds = slot_arrivals[-1]
    block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
    blocks = build_blocks(trades, slot_arrivals, block_seconds)

    print("=" * 100)
    print(f"ABLATION -- profit net moyen, risque {RISK_PCT}%, horizon complet, winrate réel, 2000 runs/variante")
    print("=" * 100)
    print(f"Cible V0 (reproduction) : ~10,335,102€ (risk_levels_trailing_02_summary.csv)")
    print(f"Cible V3 (moteur actuel) : ~7,867,591€ (winrate32_4y_full_horizon_test.py)")

    v0 = run_variant(trades, slot_arrivals, blocks, block_seconds, total_horizon_seconds, market_data, excluded_map,
                      "permutation", False, False, "V0 -- ANCIEN (tout P&L + permutation + non poolée)")
    v1 = run_variant(trades, slot_arrivals, blocks, block_seconds, total_horizon_seconds, market_data, excluded_map,
                      "permutation", False, True, "V1 -- + comptabilité FINANCÉ SEULEMENT")
    v2 = run_variant(trades, slot_arrivals, blocks, block_seconds, total_horizon_seconds, market_data, excluded_map,
                      "block", False, True, "V2 -- + block bootstrap")
    v3 = run_variant(trades, slot_arrivals, blocks, block_seconds, total_horizon_seconds, market_data, excluded_map,
                      "block", True, True, "V3 -- + réserve poolée = MOTEUR ACTUEL")

    print("\n" + "=" * 100)
    print("DÉCOMPOSITION DE L'ÉCART")
    print("=" * 100)
    print(f"V0 (reproduction ancien)         : {v0:>14,.0f}€")
    print(f"V1 (+ financé seulement)         : {v1:>14,.0f}€  (delta {v1-v0:+,.0f}€)")
    print(f"V2 (+ block bootstrap)           : {v2:>14,.0f}€  (delta {v2-v1:+,.0f}€)")
    print(f"V3 (+ réserve poolée) = actuel   : {v3:>14,.0f}€  (delta {v3-v2:+,.0f}€)")
    total_gap = v0 - v3
    print(f"\nÉcart total (V0 - V3) : {total_gap:+,.0f}€")
    for stepname, delta in [("Comptabilité financé-seulement", v1-v0), ("Bootstrap (perm->block)", v2-v1),
                             ("Pooling", v3-v2)]:
        pct = delta / -total_gap * 100 if total_gap else float('nan')
        print(f"  {stepname:<35} : {delta:+,.0f}€ ({pct:.1f}% de l'écart total)")


if __name__ == "__main__":
    main()
