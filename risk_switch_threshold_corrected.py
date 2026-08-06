"""
Re-valide le choix du seuil de bascule 0.5%->2% (déclencheur réserve) avec le moteur
COMPLET et corrigé (comptabilité financé-seulement, block bootstrap 2 mois, réserve
poolée, immunité post-financement, correctif 999€) -- l'ancien tableau
(risk_switch_threshold_summary.csv / risk_switch_threshold_block_bootstrap_summary.csv)
utilisait la même fonction buggée que copytrade_simulation_test.py (tout le P&L
compté comme profit, y compris en phase challenge) pour sa colonne "profit", même si
sa colonne "real_cash_paid" n'était pas affectée par ce bug spécifique (confirmé
précédemment). Réévalue les 5 déclencheurs originaux + 7000€/10000€, année 1.
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
LOW_RISK, HIGH_RISK = 0.5, 2.0
TRIGGERS = {
    "1. Immédiat au financement": 0.0,
    "2. Réserve >= 1000€": 1000,
    "3. Réserve >= 2000€": 2000,
    "4. Réserve >= 3000€": 3000,
    "5. Réserve >= 5000€": 5000,
    "6. Réserve >= 7000€": 7000,
    "7. Réserve >= 10000€": 10000,
}


def run_fleet_year1(trades, slot_arrivals, market_data, excluded_map, order, reserve_threshold):
    accounts = []
    for _ in range(N_ACCOUNTS):
        accounts.append({
            "palier": TIER_SEQUENCE[0], "phase": "challenge", "cumulative_since_reset": 0.0,
            "peak_since_reset": 0.0, "trading_days_since_reset": set(), "open_positions": [],
            "total_funded_pnl": 0.0, "total_fees_paid": CHALLENGE_COST[TIER_SEQUENCE[0]],
        })
    reserve = 0.0
    switched = False
    ever_funded = False
    real_cash_paid = CHALLENGE_COST[TIER_SEQUENCE[0]] * N_ACCOUNTS

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]

        for acc in accounts:
            close_time = now + trade["hold_seconds"]
            acc["open_positions"] = [(t, c) for (t, c) in acc["open_positions"] if c > now]
            if len(acc["open_positions"]) >= MAX_POSITIONS:
                continue
            if any(t in excluded_map[trade["ticker"]] for (t, _) in acc["open_positions"]):
                continue

            current_risk = HIGH_RISK if switched else LOW_RISK
            eff_risk, _ = feasible_risk_pct(trade["ticker"], trade["sl_distance"], acc["palier"], current_risk, market_data)
            risk_amount = eff_risk / 100 * acc["palier"]
            pnl = trade["outcome_r"] * risk_amount

            acc["open_positions"].append((trade["ticker"], close_time))
            acc["cumulative_since_reset"] += pnl
            acc["peak_since_reset"] = max(acc["peak_since_reset"], acc["cumulative_since_reset"])
            acc["trading_days_since_reset"].add(int(now // 86400))

            if acc["phase"] == "funded":
                acc["total_funded_pnl"] += pnl
                if pnl > 0:
                    reserve += pnl * RESERVE_SHARE

            if not switched and ever_funded and reserve >= reserve_threshold:
                switched = True  # "immédiat" (threshold=0) = dès le 1er financement, jamais avant

            drawdown = acc["peak_since_reset"] - acc["cumulative_since_reset"]
            if drawdown >= BREAK_DD_PCT / 100 * acc["palier"]:
                cost = CHALLENGE_COST[acc["palier"]]
                if reserve >= cost:
                    reserve -= cost
                else:
                    shortfall = cost - reserve
                    reserve = 0.0
                    if not ever_funded:
                        real_cash_paid += shortfall
                acc["total_fees_paid"] += cost
                acc["phase"] = "challenge"
                acc["cumulative_since_reset"] = 0.0
                acc["peak_since_reset"] = 0.0
                acc["trading_days_since_reset"] = set()
                continue

            if (acc["phase"] == "challenge"
                    and acc["cumulative_since_reset"] >= CHALLENGE_TARGET_PCT / 100 * acc["palier"]
                    and len(acc["trading_days_since_reset"]) >= MIN_TRADING_DAYS):
                acc["phase"] = "funded"
                ever_funded = True
                acc["cumulative_since_reset"] = 0.0
                acc["peak_since_reset"] = 0.0
                acc["trading_days_since_reset"] = set()

            if acc["phase"] == "funded":
                idx = TIER_SEQUENCE.index(acc["palier"])
                if idx + 1 < len(TIER_SEQUENCE):
                    next_tier = TIER_SEQUENCE[idx + 1]
                    cost = UPGRADE_COST[next_tier]
                    if reserve >= cost:
                        reserve -= cost
                        acc["total_fees_paid"] += cost
                        acc["palier"] = next_tier
                        acc["phase"] = "challenge"
                        acc["cumulative_since_reset"] = 0.0
                        acc["peak_since_reset"] = 0.0
                        acc["trading_days_since_reset"] = set()

    combined_net = sum(a["total_funded_pnl"] - a["total_fees_paid"] for a in accounts)
    return combined_net, real_cash_paid


def main():
    pop = build_population_with_trailing("fixed", 0.2, verbose=False)
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    sub, trades, slot_arrivals = build_trades_trailing(pop)
    tickers = sorted(set(t["ticker"] for t in trades))
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
    blocks = build_blocks(trades, slot_arrivals, block_seconds)

    rows = []
    cash_by_trigger = {}
    for label, threshold in TRIGGERS.items():
        rng = random.Random(42)
        cash_vals, profit_vals = [], []
        for _ in range(N_SIMULATIONS):
            raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, YEAR_SECONDS)
            cutoff = sum(1 for s in raw_slots if s <= YEAR_SECONDS)
            synth_trades, synth_slots = raw_trades[:cutoff], raw_slots[:cutoff]
            order = list(range(len(synth_trades)))
            net, cash = run_fleet_year1(synth_trades, synth_slots, market_data, excluded_map, order, threshold)
            cash_vals.append(cash)
            profit_vals.append(net)

        cash_sorted = sorted(cash_vals)
        n = len(cash_sorted)
        row = {
            "trigger": label, "threshold": threshold,
            "mean_real_cash": sum(cash_sorted) / n, "worst_real_cash": cash_sorted[-1],
            "pct_gt_1000": sum(1 for c in cash_vals if c > 1000) / n * 100,
            "pct_gt_2000": sum(1 for c in cash_vals if c > 2000) / n * 100,
            "pct_gt_3000": sum(1 for c in cash_vals if c > 3000) / n * 100,
            "mean_net_profit_year1": sum(profit_vals) / n,
        }
        rows.append(row)
        print(f"{label:<28} : cash moy {row['mean_real_cash']:>7,.0f}€ | pire cas {row['worst_real_cash']:>8,.0f}€ | "
              f"P(>1000€) {row['pct_gt_1000']:>5.1f}% | P(>2000€) {row['pct_gt_2000']:>5.1f}% | "
              f"P(>3000€) {row['pct_gt_3000']:>5.1f}% | profit moyen an1 {row['mean_net_profit_year1']:>12,.0f}€")
        cash_by_trigger[label] = cash_vals

    # Preuve empirique : comparaison run-par-run (même graine/même ordre de tirage) entre
    # 2 déclencheurs extrêmes -- doit être PARFAITEMENT identique si le mécanisme isolé
    # dans le code est correct.
    labels = list(TRIGGERS.keys())
    ref_label, other_label = labels[0], labels[-1]
    ref_cash = cash_by_trigger[ref_label]
    other_cash = cash_by_trigger[other_label]
    n_diff = sum(1 for a, b in zip(ref_cash, other_cash) if abs(a - b) > 1e-6)
    print(f"\nPreuve run-par-run : '{ref_label}' vs '{other_label}' -- {n_diff}/{N_SIMULATIONS} runs diffèrent "
          f"(0 attendu si le mécanisme isolé est correct)")

    df = pd.DataFrame(rows)
    df.to_csv("risk_switch_threshold_corrected_summary.csv", index=False)
    print("\nRésumé enregistré dans risk_switch_threshold_corrected_summary.csv")


if __name__ == "__main__":
    main()
