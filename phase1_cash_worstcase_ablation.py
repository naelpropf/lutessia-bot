"""
Étude d'ablation : isole la contribution de CHACUN des 3 changements de méthodologie
(bootstrap permutation -> block bootstrap ; réserve non poolée -> poolée ; sans
immunité -> avec immunité post-financement) à l'écart entre le pire cas de
trésorerie perso ANCIEN (21 972€, risk_switch_threshold_test.py, déclencheur
réserve>=5000€) et le pire cas ACTUEL (1 998€), sur le même scénario Phase 1 (0.5%
risque, 3 comptes 50k, année 1).

CORRECTIF DÉCOUVERT en construisant cette ablation : les moteurs "réserve poolée"
écrits cette nuit (three_regime_cash_comparison.py, slippage_impact_simulation.py)
initialisaient real_cash_paid=0.0, alors que le moteur ORIGINAL (risk_switch_
threshold_test.py) initialise real_cash_paid=CHALLENGE_COST[palier] PAR COMPTE dès
le départ (le tout premier achat de challenge est nécessairement payé cash, aucune
réserve n'existe encore) -- soit 999€ (3x333€) manquants dans TOUS les résultats de
trésorerie perso rapportés cette nuit sur le moteur poolé. Corrigé ici et appliqué
UNIFORMÉMENT aux 4 variantes de l'ablation pour que la comparaison isole VRAIMENT les
3 changements demandés, pas cet artefact de comptabilité.
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
YEAR_SECONDS = 365.25 * 86400
BLOCK_MONTHS = 2
RESERVE_SWITCH_THRESHOLD = 5000.0
LOW_RISK = 0.5
HIGH_RISK = 2.0


def run_one_account(trades, slot_arrivals, market_data, excluded_map, order, shared_reserve_state, pooled, immune):
    """shared_reserve_state : dict mutable {'reserve':..., 'switched':..., 'ever_funded':...}
    -- PARTAGÉ entre comptes si pooled=True, sinon un dict INDÉPENDANT par compte
    (appelant responsable de passer soit le même dict soit un nouveau par compte)."""
    palier = TIER_SEQUENCE[0]
    phase = "challenge"
    cumulative_since_reset = 0.0
    peak_since_reset = 0.0
    trading_days_since_reset = set()
    open_positions = []

    real_cash_paid = CHALLENGE_COST[palier]  # 1er achat de challenge : toujours cash, corrigé (cf. docstring)
    total_fees_paid = CHALLENGE_COST[palier]
    total_funded_pnl = 0.0

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]
        if now > YEAR_SECONDS:
            break

        close_time = now + trade["hold_seconds"]
        open_positions = [(t, c) for (t, c) in open_positions if c > now]
        if len(open_positions) >= MAX_POSITIONS:
            continue
        if any(t in excluded_map[trade["ticker"]] for (t, _) in open_positions):
            continue

        current_risk = HIGH_RISK if shared_reserve_state["switched"] else LOW_RISK
        eff_risk, _ = feasible_risk_pct(trade["ticker"], trade["sl_distance"], palier, current_risk, market_data)
        risk_amount = eff_risk / 100 * palier
        pnl = trade["outcome_r"] * risk_amount

        open_positions.append((trade["ticker"], close_time))
        cumulative_since_reset += pnl
        peak_since_reset = max(peak_since_reset, cumulative_since_reset)
        trading_days_since_reset.add(int(now // 86400))

        if phase == "funded":
            total_funded_pnl += pnl
            if pnl > 0:
                shared_reserve_state["reserve"] += pnl * RESERVE_SHARE

        if not shared_reserve_state["switched"] and shared_reserve_state["reserve"] >= RESERVE_SWITCH_THRESHOLD:
            shared_reserve_state["switched"] = True

        drawdown = peak_since_reset - cumulative_since_reset
        if drawdown >= BREAK_DD_PCT / 100 * palier:
            cost = CHALLENGE_COST[palier]
            if shared_reserve_state["reserve"] >= cost:
                shared_reserve_state["reserve"] -= cost
            else:
                shortfall = cost - shared_reserve_state["reserve"]
                shared_reserve_state["reserve"] = 0.0
                if not (immune and shared_reserve_state["ever_funded"]):
                    real_cash_paid += shortfall
            total_fees_paid += cost
            phase = "challenge"
            cumulative_since_reset = 0.0
            peak_since_reset = 0.0
            trading_days_since_reset = set()
            continue

        if (phase == "challenge"
                and cumulative_since_reset >= CHALLENGE_TARGET_PCT / 100 * palier
                and len(trading_days_since_reset) >= MIN_TRADING_DAYS):
            phase = "funded"
            shared_reserve_state["ever_funded"] = True
            cumulative_since_reset = 0.0
            peak_since_reset = 0.0
            trading_days_since_reset = set()

        if phase == "funded":
            idx = TIER_SEQUENCE.index(palier)
            if idx + 1 < len(TIER_SEQUENCE):
                next_tier = TIER_SEQUENCE[idx + 1]
                cost = UPGRADE_COST[next_tier]
                if shared_reserve_state["reserve"] >= cost:
                    shared_reserve_state["reserve"] -= cost
                    total_fees_paid += cost
                    palier = next_tier
                    phase = "challenge"
                    cumulative_since_reset = 0.0
                    peak_since_reset = 0.0
                    trading_days_since_reset = set()

    return real_cash_paid, total_funded_pnl - total_fees_paid


def run_fleet_one(trades, slot_arrivals, market_data, excluded_map, order, pooled, immune):
    if pooled:
        shared_state = {"reserve": 0.0, "switched": False, "ever_funded": False}
        states = [shared_state] * N_ACCOUNTS
    else:
        states = [{"reserve": 0.0, "switched": False, "ever_funded": False} for _ in range(N_ACCOUNTS)]

    total_cash, total_net = 0.0, 0.0
    for acc_state in states:
        cash, net = run_one_account(trades, slot_arrivals, market_data, excluded_map, order, acc_state, pooled, immune)
        total_cash += cash
        total_net += net
    return total_cash, total_net


def run_variant(trades_perm, slots_perm, blocks, block_seconds, market_data, excluded_map,
                 bootstrap, pooled, immune, label):
    rng = random.Random(42)
    cash_vals, net_vals = [], []
    for _ in range(N_SIMULATIONS):
        if bootstrap == "permutation":
            order = list(range(len(trades_perm)))
            rng.shuffle(order)
            trades_run, slots_run = trades_perm, slots_perm
        else:  # block
            raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, YEAR_SECONDS)
            trades_run, slots_run = raw_trades, raw_slots
            order = list(range(len(trades_run)))

        cash, net = run_fleet_one(trades_run, slots_run, market_data, excluded_map, order, pooled, immune)
        cash_vals.append(cash)
        net_vals.append(net)

    cash_series = pd.Series(cash_vals)
    print(f"\n--- {label} ---")
    print(f"  bootstrap={bootstrap:<12} pooled={pooled!s:<6} immune={immune!s:<6}")
    print(f"  Trésorerie perso -- moyenne {cash_series.mean():,.0f}€ | médiane {cash_series.median():,.0f}€ | "
          f"PIRE CAS {cash_series.max():,.0f}€")
    return cash_series.max(), cash_series.mean()


def main():
    pop = build_population_with_trailing("fixed", 0.2, verbose=False)
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    sub, trades, slot_arrivals = build_trades_trailing(pop)
    tickers = sorted(set(t["ticker"] for t in trades))
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
    blocks = build_blocks(trades, slot_arrivals, block_seconds)

    print("=" * 100)
    print("ABLATION -- Phase 1 (0.5% risque, 3x50k), pire cas trésorerie perso, 2000 runs par variante")
    print("=" * 100)

    results = {}
    results["V0"] = run_variant(trades, slot_arrivals, blocks, block_seconds, market_data, excluded_map,
                                 "permutation", False, False,
                                 "V0 -- ANCIEN (permutation + non-poolée + sans immunité) -- reproduction du contexte 21972€")
    results["V1"] = run_variant(trades, slot_arrivals, blocks, block_seconds, market_data, excluded_map,
                                 "block", False, False,
                                 "V1 -- + block bootstrap (structure temporelle préservée)")
    results["V2"] = run_variant(trades, slot_arrivals, blocks, block_seconds, market_data, excluded_map,
                                 "block", True, False,
                                 "V2 -- + réserve POOLÉE (partagée sur les 3 comptes)")
    results["V3"] = run_variant(trades, slot_arrivals, blocks, block_seconds, market_data, excluded_map,
                                 "block", True, True,
                                 "V3 -- + immunité post-financement (moteur ACTUEL)")

    print("\n" + "=" * 100)
    print("DÉCOMPOSITION DE L'ÉCART (pire cas)")
    print("=" * 100)
    print(f"V0 (ancien, comptabilité corrigée)      : {results['V0'][0]:>10,.0f}€")
    print(f"V1 (+ block bootstrap)                  : {results['V1'][0]:>10,.0f}€  "
          f"(delta {results['V1'][0]-results['V0'][0]:+,.0f}€)")
    print(f"V2 (+ réserve poolée)                   : {results['V2'][0]:>10,.0f}€  "
          f"(delta {results['V2'][0]-results['V1'][0]:+,.0f}€)")
    print(f"V3 (+ immunité) = MOTEUR ACTUEL          : {results['V3'][0]:>10,.0f}€  "
          f"(delta {results['V3'][0]-results['V2'][0]:+,.0f}€)")
    total_gap = results['V0'][0] - results['V3'][0]
    print(f"\nÉcart total (V0 - V3) : {total_gap:+,.0f}€")
    for step, delta in [("Bootstrap (perm->block)", results['V1'][0]-results['V0'][0]),
                         ("Pooling (non-poolée->poolée)", results['V2'][0]-results['V1'][0]),
                         ("Immunité (sans->avec)", results['V3'][0]-results['V2'][0])]:
        pct = delta / -total_gap * 100 if total_gap != 0 else float('nan')
        print(f"  {step:<32} : {delta:+,.0f}€ ({pct:.1f}% de l'écart total)")


if __name__ == "__main__":
    main()
