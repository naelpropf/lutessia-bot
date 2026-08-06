"""
Partie 5 de l'analyse Force : teste Force comme PONDÉRATEUR de taille de position
(palier simple : Force<7 -> 0.5x le risque normal, Force>=8.5 -> 1.5x, sinon 1x) vs
risque fixe identique pour tous les trades -- sur le régime hybride verrouillé
(0.5%->2%@réserve commune 5000€, réserve poolée + immunité perso post-financement,
copytrade 3 comptes, plafond 3 positions, corrélation 0.6+JPY, payoff réaliste +
trailing 0.2xSL), même méthodologie (block bootstrap 2 mois, année 1, 2000 runs)
que le reste de la nuit.
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

N_ACCOUNTS = 3
YEAR_SECONDS = 365.25 * 86400
BLOCK_MONTHS = 2
RESERVE_SWITCH_THRESHOLD = 5000.0
LOW_RISK = 0.5
HIGH_RISK = 2.0


def force_multiplier(score):
    if score < 7:
        return 0.5
    if score >= 8.5:
        return 1.5
    return 1.0


def build_trades_with_force(pop):
    sub = pop.sort_values("date_creation").reset_index(drop=True)
    sub["date_creation"] = pd.to_datetime(sub["date_creation"])
    sub["resolution_time_est"] = pd.to_datetime(sub["resolution_time_est"])
    t0 = sub["date_creation"].iloc[0]
    slot_arrivals = [(d - t0).total_seconds() for d in sub["date_creation"]]

    trades = []
    for _, row in sub.iterrows():
        hold_seconds = (row["resolution_time_est"] - row["date_creation"]).total_seconds()
        sl_distance = abs(row["prix_entree"] - row["stop_loss_init"])
        trades.append({
            "ticker": row["ticker"],
            "outcome_r": row["r_trailing"],
            "sl_distance": sl_distance,
            "hold_seconds": hold_seconds,
            "date": row["date_creation"],
            "force_multiplier": force_multiplier(row["score_force"]),
        })
    return sub, trades, slot_arrivals


def run_fleet_year1_pooled(trades, slot_arrivals, market_data, excluded_map, order, use_force_weighting):
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
    real_cash_paid = 0.0

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
            mult = trade["force_multiplier"] if use_force_weighting else 1.0
            risk_amount = eff_risk / 100 * acc["palier"] * mult
            pnl = trade["outcome_r"] * risk_amount

            acc["open_positions"].append((trade["ticker"], close_time))
            acc["cumulative_since_reset"] += pnl
            acc["peak_since_reset"] = max(acc["peak_since_reset"], acc["cumulative_since_reset"])
            acc["trading_days_since_reset"].add(int(now // 86400))

            if acc["phase"] == "funded":
                acc["total_funded_pnl"] += pnl
                if pnl > 0:
                    reserve += pnl * RESERVE_SHARE

            if not switched and reserve >= RESERVE_SWITCH_THRESHOLD:
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


def run_variant(blocks, block_seconds, market_data, excluded_map, use_force_weighting, label):
    rng = random.Random(42)
    rows = []
    for _ in range(N_SIMULATIONS):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, YEAR_SECONDS)
        cutoff = sum(1 for s in raw_slots if s <= YEAR_SECONDS)
        synth_trades = raw_trades[:cutoff]
        synth_slots = raw_slots[:cutoff]
        order = list(range(len(synth_trades)))
        net, cash = run_fleet_year1_pooled(synth_trades, synth_slots, market_data, excluded_map, order, use_force_weighting)
        rows.append({"net_profit": net, "real_cash_paid": cash})
    df = pd.DataFrame(rows)
    df.to_csv(f"force_weighting_{label}.csv", index=False)
    return df


def summarize(df, label):
    n = len(df)
    losers = df[df["net_profit"] < 0]
    print(f"\n{label} -- n={n}")
    print(f"  P(perte)        : {len(losers)/n*100:.2f}%")
    print(f"  Profit moyen    : {df['net_profit'].mean():+,.0f}€")
    print(f"  Profit médian   : {df['net_profit'].median():+,.0f}€")
    print(f"  P5 / P95        : {df['net_profit'].quantile(0.05):+,.0f}€ / {df['net_profit'].quantile(0.95):+,.0f}€")


def main():
    pop = pd.read_csv("population_with_force.csv")
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    sub, trades, slot_arrivals = build_trades_with_force(pop)
    tickers = sorted(set(t["ticker"] for t in trades))
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
    blocks = build_blocks(trades, slot_arrivals, block_seconds)

    print("=" * 100)
    print("PARTIE 5 -- FORCE COMME PONDÉRATEUR DE TAILLE (régime hybride, année 1, 2000 runs)")
    print("=" * 100)

    df_baseline = run_variant(blocks, block_seconds, market_data, excluded_map, False, "baseline_fixed_risk")
    summarize(df_baseline, "BASELINE (risque fixe, pas de pondération Force)")

    df_weighted = run_variant(blocks, block_seconds, market_data, excluded_map, True, "force_weighted")
    summarize(df_weighted, "PONDÉRÉ FORCE (<7 -> 0.5x | >=8.5 -> 1.5x | sinon 1x)")

    delta_mean = df_weighted["net_profit"].mean() - df_baseline["net_profit"].mean()
    delta_pct = delta_mean / abs(df_baseline["net_profit"].mean()) * 100
    print(f"\nDelta profit moyen (pondéré - baseline) : {delta_mean:+,.0f}€ ({delta_pct:+.2f}%)")


if __name__ == "__main__":
    main()
