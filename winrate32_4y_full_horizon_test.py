"""
Sweep de risque (0.5% à 3%, régimes plats + hybride 0.5%->2%@5000€) sur l'HORIZON
COMPLET du projet (~3.96 ans, durée réelle de la population 2022-08 -> 2026-07,
pas une extrapolation à 4 ans ronds), à winrate 32% (borne bayésienne P10) -- avec
vérification en parallèle au winrate réel 37.29% pour valider contre les chiffres de
référence déjà cités par l'utilisateur.

Moteur : block bootstrap 2 mois, réserve poolée, immunité post-financement, correctif
999€. PAS de slippage ici (non demandé pour ce test, reste isolé sur l'effet winrate x
horizon x régime -- cohérent avec winrate32_bayesian_stress_test.py qui l'excluait
aussi). r_trailing (convention verrouillée).
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
from winrate_sensitivity_test import build_degraded_trades, DEGRADE_SEED

N_ACCOUNTS = 3
BLOCK_MONTHS = 2
RESERVE_SWITCH_THRESHOLD = 5000.0
FLAT_RISK_LEVELS = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
REFERENCE_4Y = {0.5: 2_630_000, 1.0: 5_460_000, 1.5: 8_060_000, 2.0: 10_340_000, 3.0: 13_390_000}


def run_fleet_full(trades, slot_arrivals, market_data, excluded_map, order, low_risk, high_risk, switch_enabled,
                    n_months):
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
    total_breaks = 0

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

            current_risk = (high_risk if switched else low_risk) if switch_enabled else low_risk
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

            if switch_enabled and not switched and reserve >= RESERVE_SWITCH_THRESHOLD:
                switched = True

            drawdown = acc["peak_since_reset"] - acc["cumulative_since_reset"]
            if drawdown >= BREAK_DD_PCT / 100 * acc["palier"]:
                cost = CHALLENGE_COST[acc["palier"]]
                total_breaks += 1
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
    monthly_proxy = combined_net / n_months
    return combined_net, real_cash_paid, total_breaks, monthly_proxy


def run_regime(trades, slot_arrivals, market_data, excluded_map, blocks, block_seconds, target_duration, n_months,
               low_risk, high_risk, switch_enabled):
    rng = random.Random(42)
    rows = []
    for _ in range(N_SIMULATIONS):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, target_duration)
        order = list(range(len(raw_trades)))
        net, cash, breaks, monthly = run_fleet_full(raw_trades, raw_slots, market_data, excluded_map, order,
                                                      low_risk, high_risk, switch_enabled, n_months)
        rows.append({"net_profit": net, "real_cash_paid": cash, "total_breaks": breaks, "monthly_proxy": monthly})
    return pd.DataFrame(rows)


def build_trades_for_winrate(pop, target_winrate):
    if target_winrate is None:
        return build_trades_trailing(pop)[1:]  # trades, slot_arrivals
    rng = random.Random(DEGRADE_SEED)
    _, trades, slot_arrivals, _ = build_degraded_trades(pop, target_winrate, rng)
    return trades, slot_arrivals


def main():
    pop = build_population_with_trailing("fixed", 0.2, verbose=False)
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    trades_ref, slots_ref = build_trades_for_winrate(pop, None)
    trades_32, slots_32 = build_trades_for_winrate(pop, 0.32)

    total_horizon_seconds = slots_ref[-1]  # même horizon réel pour les deux (arrivées identiques)
    total_horizon_years = total_horizon_seconds / (365.25 * 86400)
    n_months = total_horizon_seconds / (30.44 * 86400)
    print(f"Horizon complet : {total_horizon_years:.2f} ans ({n_months:.1f} mois)")

    block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
    blocks_ref = build_blocks(trades_ref, slots_ref, block_seconds)
    blocks_32 = build_blocks(trades_32, slots_32, block_seconds)

    all_rows = []
    regimes = [(lvl, lvl, False, f"{lvl}% plat") for lvl in FLAT_RISK_LEVELS]
    regimes.append((0.5, 2.0, True, "Hybride 0.5->2%@5000€"))

    for low, high, switch, label in regimes:
        print(f"\n{'='*100}\nRÉGIME : {label}\n{'='*100}")
        df_ref = run_regime(trades_ref, slots_ref, market_data, excluded_map, blocks_ref, block_seconds,
                             total_horizon_seconds, n_months, low, high, switch)
        df_32 = run_regime(trades_32, slots_32, market_data, excluded_map, blocks_32, block_seconds,
                            total_horizon_seconds, n_months, low, high, switch)

        ref_key = high if not switch else None
        ref_cited = REFERENCE_4Y.get(ref_key) if ref_key in REFERENCE_4Y else None

        row = {
            "regime": label,
            "profit_37.29_moyen": df_ref["net_profit"].mean(), "profit_32_moyen": df_32["net_profit"].mean(),
            "casses_37.29": df_ref["total_breaks"].mean(), "casses_32": df_32["total_breaks"].mean(),
            "std_mensuel_37.29": df_ref["monthly_proxy"].std(), "std_mensuel_32": df_32["monthly_proxy"].std(),
            "cash_worst_37.29": df_ref["real_cash_paid"].max(), "cash_worst_32": df_32["real_cash_paid"].max(),
        }
        all_rows.append(row)

        print(f"37.29% -- profit moyen 4 ans : {row['profit_37.29_moyen']:+,.0f}€"
              + (f" (référence citée ~{ref_cited:,.0f}€, écart {(row['profit_37.29_moyen']/ref_cited-1)*100:+.1f}%)"
                 if ref_cited else ""))
        print(f"32%    -- profit moyen 4 ans : {row['profit_32_moyen']:+,.0f}€ "
              f"({(row['profit_32_moyen']/row['profit_37.29_moyen']-1)*100:+.1f}% vs référence)")
        print(f"Casses 4 ans -- 37.29% {row['casses_37.29']:.2f} | 32% {row['casses_32']:.2f}")
        print(f"Écart-type mensuel (proxy €/mois) -- 37.29% {row['std_mensuel_37.29']:,.0f}€ | "
              f"32% {row['std_mensuel_32']:,.0f}€")
        print(f"Pire cas trésorerie perso -- 37.29% {row['cash_worst_37.29']:,.0f}€ | 32% {row['cash_worst_32']:,.0f}€")

    summary_df = pd.DataFrame(all_rows)
    summary_df.to_csv("winrate32_4y_full_horizon_summary.csv", index=False)

    print(f"\n{'='*100}\nHYBRIDE VS 2% DIRECT SUR L'HORIZON COMPLET -- L'ÉCART SE RATTRAPE-T-IL ?\n{'='*100}")
    hybride_row = summary_df[summary_df["regime"].str.contains("Hybride")].iloc[0]
    direct2_row = summary_df[summary_df["regime"] == "2.0% plat"].iloc[0]
    for wr_label, col in [("37.29%", "profit_37.29_moyen"), ("32%", "profit_32_moyen")]:
        gap_pct = (1 - hybride_row[col] / direct2_row[col]) * 100
        print(f"[{wr_label}] Hybride {hybride_row[col]:+,.0f}€ vs 2% direct {direct2_row[col]:+,.0f}€ "
              f"-- hybride reste {gap_pct:.1f}% en dessous sur l'horizon complet")

    print("\nRésumé complet enregistré dans winrate32_4y_full_horizon_summary.csv")


if __name__ == "__main__":
    main()
