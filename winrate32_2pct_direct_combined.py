"""
Scénario COMBINÉ : winrate 32% (borne bayésienne P10) ET régime 2% direct dès le 1er
trade, sur le moteur complet à jour (block bootstrap 2 mois, réserve poolée, immunité
post-financement, correctif 999€, slippage réel Dukascopy intégré).

Compare 3 scénarios sur le MÊME moteur complet, Phase 1 (0.5%/2% direct, 3x50k) :
  A. 37.29% (réel) + 2% direct + slippage      -- déjà calculé (two_regime_full_distribution_updated.py)
  B. 32% (dégradé) + hybride + slippage         -- nouveau
  C. 32% (dégradé) + 2% direct + slippage       -- nouveau (scénario combiné demandé)

Le winrate est dégradé APRÈS application du slippage (même sélection aléatoire de
trades gagnants "retournés" en perdants que winrate_sensitivity_test.py, DEGRADE_SEED
=123, pour rester comparable aux tests précédents) -- sur r_slippage, pas r_trailing,
pour que le slippage reste actif sur tous les trades restants du scénario dégradé.
"""
import random

import pandas as pd

from scaling_simulation import (
    TIER_SEQUENCE, CHALLENGE_COST, UPGRADE_COST, CHALLENGE_TARGET_PCT,
    MIN_TRADING_DAYS, BREAK_DD_PCT, RESERVE_SHARE, MAX_POSITIONS, CORR_THRESHOLD,
    feasible_risk_pct, load_market_data,
)
from monte_carlo_simulation import precompute_correlation_pairs, N_SIMULATIONS
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from slippage_adjusted_population import build_adjusted_population
from winrate_sensitivity_test import DEGRADE_SEED

N_ACCOUNTS = 3
YEAR_SECONDS = 365.25 * 86400
BLOCK_MONTHS = 2
RESERVE_SWITCH_THRESHOLD = 5000.0
TARGET_WINRATE = 0.32


def build_degraded_trades_with_slippage(pop_slip, target_winrate, rng):
    sub = pop_slip.sort_values("date_creation").reset_index(drop=True)
    sub["resolution_time_est"] = pd.to_datetime(sub["resolution_time_est"])
    n = len(sub)
    is_win = (sub["statut_final"] == "OBJECTIF ATTEINT").to_numpy()
    current_n_win = int(is_win.sum())
    target_n_win = round(target_winrate * n)

    win_idx = list(sub.index[is_win])
    flip_to_loss = set(rng.sample(win_idx, current_n_win - target_n_win)) if target_n_win < current_n_win else set()

    t0 = sub["date_creation"].iloc[0]
    slot_arrivals = [(d - t0).total_seconds() for d in sub["date_creation"]]
    trades = []
    for idx, row in sub.iterrows():
        hold_seconds = (row["resolution_time_est"] - row["date_creation"]).total_seconds()
        sl_distance = abs(row["prix_entree"] - row["stop_loss_init"])
        if idx in flip_to_loss:
            outcome_r = -1.0
        else:
            outcome_r = row["r_slippage"] if row["statut_final"] == "OBJECTIF ATTEINT" else row["r_slippage"]
        trades.append({"ticker": row["ticker"], "outcome_r": outcome_r, "sl_distance": sl_distance,
                        "hold_seconds": hold_seconds, "date": row["date_creation"]})
    actual_wr = (current_n_win - len(flip_to_loss)) / n
    return trades, slot_arrivals, actual_wr


def build_trades_reference(pop_slip):
    sub = pop_slip.sort_values("date_creation").reset_index(drop=True)
    sub["resolution_time_est"] = pd.to_datetime(sub["resolution_time_est"])
    t0 = sub["date_creation"].iloc[0]
    slot_arrivals = [(d - t0).total_seconds() for d in sub["date_creation"]]
    trades = []
    for _, row in sub.iterrows():
        hold_seconds = (row["resolution_time_est"] - row["date_creation"]).total_seconds()
        sl_distance = abs(row["prix_entree"] - row["stop_loss_init"])
        trades.append({"ticker": row["ticker"], "outcome_r": row["r_slippage"], "sl_distance": sl_distance,
                        "hold_seconds": hold_seconds, "date": row["date_creation"]})
    return trades, slot_arrivals


def run_fleet_year1(trades, slot_arrivals, market_data, excluded_map, order, low_risk, high_risk, switch_enabled):
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
    return combined_net, real_cash_paid, total_breaks


def run_scenario(trades, slot_arrivals, market_data, excluded_map, low_risk, high_risk, switch_enabled, label):
    rng = random.Random(42)
    rows = []
    for _ in range(N_SIMULATIONS):
        block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
        blocks = build_blocks(trades, slot_arrivals, block_seconds)
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, YEAR_SECONDS)
        cutoff = sum(1 for s in raw_slots if s <= YEAR_SECONDS)
        synth_trades = raw_trades[:cutoff]
        synth_slots = raw_slots[:cutoff]
        order = list(range(len(synth_trades)))
        net, cash, breaks = run_fleet_year1(synth_trades, synth_slots, market_data, excluded_map, order,
                                             low_risk, high_risk, switch_enabled)
        rows.append({"net_profit": net, "real_cash_paid": cash, "total_breaks": breaks})
    df = pd.DataFrame(rows)
    df.to_csv(f"winrate32_2pct_combined_{label}.csv", index=False)
    return df


def report(df, label):
    n = len(df)
    p_break = (df["total_breaks"] > 0).mean() * 100
    cash = df["real_cash_paid"]
    print(f"\n--- {label} ---")
    print(f"  P(>=1 casse)          : {p_break:.2f}%")
    print(f"  Trésorerie moyenne    : {cash.mean():,.0f}€")
    print(f"  Trésorerie pire cas   : {cash.max():,.0f}€")
    print(f"  P(>3000€)             : {(cash>3000).mean()*100:.2f}%")
    print(f"  P(>5000€)             : {(cash>5000).mean()*100:.2f}%")
    print(f"  P(>10000€)            : {(cash>10000).mean()*100:.2f}%")
    print(f"  Profit net moyen      : {df['net_profit'].mean():+,.0f}€")
    return {"label": label, "p_break": p_break, "cash_mean": cash.mean(), "cash_worst": cash.max(),
            "p_gt_3000": (cash>3000).mean()*100, "p_gt_5000": (cash>5000).mean()*100,
            "p_gt_10000": (cash>10000).mean()*100, "profit_mean": df["net_profit"].mean()}


def main():
    pop_slip = build_adjusted_population("empirical")
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop_slip["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    trades_ref, slots_ref = build_trades_reference(pop_slip)
    rng32 = random.Random(DEGRADE_SEED)
    trades_32, slots_32, actual_wr = build_degraded_trades_with_slippage(pop_slip, TARGET_WINRATE, rng32)
    print(f"Winrate 32% réalisé : {actual_wr*100:.2f}%")

    print("\n" + "=" * 100)
    print("A. 37.29% (réel) + 2% DIRECT + slippage [déjà connu, recalculé ici pour cohérence]")
    print("=" * 100)
    df_A = run_scenario(trades_ref, slots_ref, market_data, excluded_map, 2.0, 2.0, False, "A_ref_2pct")
    res_A = report(df_A, "A. Référence 37.29% + 2% direct")

    print("\n" + "=" * 100)
    print("B. 32% (dégradé) + HYBRIDE + slippage")
    print("=" * 100)
    df_B = run_scenario(trades_32, slots_32, market_data, excluded_map, 0.5, 2.0, True, "B_32pct_hybride")
    res_B = report(df_B, "B. 32% + hybride")

    print("\n" + "=" * 100)
    print("C. 32% (dégradé) + 2% DIRECT + slippage [SCÉNARIO COMBINÉ DEMANDÉ]")
    print("=" * 100)
    df_C = run_scenario(trades_32, slots_32, market_data, excluded_map, 2.0, 2.0, False, "C_32pct_2pct")
    res_C = report(df_C, "C. 32% + 2% direct (COMBINÉ)")

    print("\n" + "=" * 100)
    print("COMPARAISON -- ADDITIF OU DISPROPORTIONNÉ ?")
    print("=" * 100)
    summary = pd.DataFrame([res_A, res_B, res_C])
    print(summary.to_string(index=False))
    summary.to_csv("winrate32_2pct_combined_summary.csv", index=False)

    # Test d'additivité simple sur le pire cas de trésorerie
    baseline = res_A["cash_worst"]  # remplace par le cas "aucun facteur défavorable" si dispo séparément
    print(f"\nPire cas A (37.29%+2%direct) : {res_A['cash_worst']:,.0f}€")
    print(f"Pire cas B (32%+hybride)     : {res_B['cash_worst']:,.0f}€")
    print(f"Pire cas C (32%+2%direct)    : {res_C['cash_worst']:,.0f}€")
    additive_estimate = res_A["cash_worst"] + res_B["cash_worst"]
    print(f"\nSi purement additif (A + B, approximation grossière) : ~{additive_estimate:,.0f}€ (repère, pas rigoureux)")
    print(f"Valeur réelle observée (C) : {res_C['cash_worst']:,.0f}€")


if __name__ == "__main__":
    main()
