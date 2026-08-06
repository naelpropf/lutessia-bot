"""
Reprend two_regime_full_distribution_test.py (2% débloqué vs hybride, dominance
stochastique + coût cash) avec le moteur COMPLET et à jour :
  - block bootstrap 2 mois (déjà présent dans la version précédente)
  - réserve poolée (déjà présente)
  - immunité post-financement (déjà présente)
  - CORRECTIF 999€ (achat initial des 3 challenges compté dans real_cash_paid dès le
    départ -- absent de la version précédente, cf. phase1_cash_worstcase_ablation.py)
  - slippage réel Dukascopy intégré (méthode empirique, r_slippage -- absent de la
    version précédente, qui utilisait r_trailing brut)
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

N_ACCOUNTS = 3
YEAR_SECONDS = 365.25 * 86400
BLOCK_MONTHS = 2
RESERVE_SWITCH_THRESHOLD = 5000.0
PERCENTILES = [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95]


def build_trades(pop, outcome_col):
    sub = pop.sort_values("date_creation").reset_index(drop=True)
    sub["resolution_time_est"] = pd.to_datetime(sub["resolution_time_est"])
    t0 = sub["date_creation"].iloc[0]
    slot_arrivals = [(d - t0).total_seconds() for d in sub["date_creation"]]
    trades = []
    for _, row in sub.iterrows():
        hold_seconds = (row["resolution_time_est"] - row["date_creation"]).total_seconds()
        sl_distance = abs(row["prix_entree"] - row["stop_loss_init"])
        trades.append({
            "ticker": row["ticker"], "outcome_r": row[outcome_col],
            "sl_distance": sl_distance, "hold_seconds": hold_seconds, "date": row["date_creation"],
        })
    return sub, trades, slot_arrivals


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
    real_cash_paid = CHALLENGE_COST[TIER_SEQUENCE[0]] * N_ACCOUNTS  # CORRECTIF 999€ (1er achat, toujours cash)

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


def run_regime(blocks, block_seconds, market_data, excluded_map, low_risk, high_risk, switch_enabled, label):
    rng = random.Random(42)
    rows = []
    for _ in range(N_SIMULATIONS):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, YEAR_SECONDS)
        cutoff = sum(1 for s in raw_slots if s <= YEAR_SECONDS)
        synth_trades = raw_trades[:cutoff]
        synth_slots = raw_slots[:cutoff]
        order = list(range(len(synth_trades)))
        net, cash = run_fleet_year1(synth_trades, synth_slots, market_data, excluded_map, order, low_risk, high_risk, switch_enabled)
        rows.append({"net_profit": net, "real_cash_paid": cash})
    df = pd.DataFrame(rows)
    df.to_csv(f"two_regime_updated_{label}.csv", index=False)
    return df


def main():
    pop_slip = build_adjusted_population("empirical")
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop_slip["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    sub, trades, slot_arrivals = build_trades(pop_slip, "r_slippage")
    block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
    blocks = build_blocks(trades, slot_arrivals, block_seconds)

    print("=" * 100)
    print("2% DÉBLOQUÉ vs HYBRIDE -- MOTEUR COMPLET À JOUR (block bootstrap + poolée + "
          "immunité + correctif 999€ + slippage réel)")
    print("=" * 100)

    df_2pct = run_regime(blocks, block_seconds, market_data, excluded_map, 2.0, 2.0, False, "2pct_debloque")
    df_hybrid = run_regime(blocks, block_seconds, market_data, excluded_map, 0.5, 2.0, True, "hybride_ref")

    print(f"\nPire cas trésorerie 2% débloqué : {df_2pct['real_cash_paid'].max():,.0f}€")
    print(f"Pire cas trésorerie hybride      : {df_hybrid['real_cash_paid'].max():,.0f}€")

    print("\n" + "=" * 100)
    print("DISTRIBUTION COMPLÈTE -- PROFIT NET ANNÉE 1 (percentile par percentile)")
    print("=" * 100)
    rows = []
    for p in PERCENTILES:
        v2 = df_2pct["net_profit"].quantile(p)
        vh = df_hybrid["net_profit"].quantile(p)
        better = "2% MEILLEUR" if v2 > vh else ("HYBRIDE MEILLEUR" if vh > v2 else "égalité")
        rows.append({"percentile": f"P{int(p*100)}", "regime_2pct_debloque": v2, "regime_hybride": vh,
                     "diff": v2 - vh, "qui_gagne": better})
    perc_df = pd.DataFrame(rows)
    print(perc_df.to_string(index=False))
    perc_df.to_csv("two_regime_updated_percentiles.csv", index=False)

    all_2pct_better = all(r["diff"] >= 0 for r in rows)
    print(f"\nDominance stochastique complète : {'OUI' if all_2pct_better else 'NON'}")

    print("\n" + "=" * 100)
    print("TRÉSORERIE PERSO -- RÉGIME 2% DÉBLOQUÉ")
    print("=" * 100)
    cash = df_2pct["real_cash_paid"]
    print(f"Moyenne {cash.mean():,.0f}€ | Médiane {cash.median():,.0f}€ | Pire cas {cash.max():,.0f}€")
    for p in [0.90, 0.95, 0.99]:
        print(f"P{int(p*100)} : {cash.quantile(p):,.0f}€")
    print(f"P(>1000€) {sum(cash>1000)/len(cash)*100:.2f}% | P(>3000€) {sum(cash>3000)/len(cash)*100:.2f}% | "
          f"P(>9000€) {sum(cash>9000)/len(cash)*100:.2f}%")

    print("\nRappel régime hybride :")
    cash_h = df_hybrid["real_cash_paid"]
    print(f"Moyenne {cash_h.mean():,.0f}€ | Pire cas {cash_h.max():,.0f}€")


if __name__ == "__main__":
    main()
