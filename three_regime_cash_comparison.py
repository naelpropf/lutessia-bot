"""
Reprend TOUTES les analyses de trésorerie perso de la nuit (personal_cash_ceiling_test.py,
year1_loss_decomposition.py, cash_ceiling_speed_by_regime.py, reference_metrics_final.py)
avec le modèle CORRIGÉ établi dans bad_year1_recovery_pooled_reserve.py :
  - réserve UNIQUE partagée par les 3 comptes (pas 3 réserves indépendantes)
  - budget personnel utilisé UNIQUEMENT tant qu'aucun compte n'a jamais été financé ;
    dès le premier financement (ever_funded=True, définitif), plus aucun rachat ne
    tape dans le budget perso, quel que soit l'état de la réserve à cet instant.

Produit le tableau comparatif final demandé, ANNÉE 1, sur les 3 régimes :
  - 0.5% pur (fixe toute l'année)
  - 2% direct (fixe toute l'année dès le départ)
  - hybride 0.5%->2%@réserve commune 5000€ (régime verrouillé de référence)

Mêmes 2000 runs / mêmes tirages block bootstrap 2 mois pour les 3 régimes (rng
réinitialisée à la graine 42 avant chaque régime) -> comparaison directe, appariée.
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


def run_fleet_year1_pooled(trades, slot_arrivals, market_data, excluded_map, order, low_risk, high_risk, switch_enabled):
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
    total_trades_taken = 0
    crossing_day = None
    crossing_trades = None

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
            total_trades_taken += 1

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
                        was_below = real_cash_paid <= 3000.0
                        real_cash_paid += shortfall
                        if crossing_day is None and was_below and real_cash_paid > 3000.0:
                            crossing_day = now / 86400
                            crossing_trades = total_trades_taken
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
    return combined_net, real_cash_paid, crossing_day, crossing_trades


def run_regime(blocks, block_seconds, market_data, excluded_map, low_risk, high_risk, switch_enabled, label):
    rng = random.Random(42)
    rows = []
    for _ in range(N_SIMULATIONS):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, YEAR_SECONDS)
        cutoff = sum(1 for s in raw_slots if s <= YEAR_SECONDS)
        synth_trades = raw_trades[:cutoff]
        synth_slots = raw_slots[:cutoff]
        order = list(range(len(synth_trades)))

        net, cash, cday, ctrades = run_fleet_year1_pooled(
            synth_trades, synth_slots, market_data, excluded_map, order, low_risk, high_risk, switch_enabled
        )
        rows.append({"net_profit": net, "real_cash_paid": cash, "crossing_day": cday, "crossing_trades": ctrades})

    df = pd.DataFrame(rows)
    df.to_csv(f"three_regime_cash_{label}.csv", index=False)
    return df


def summarize(df, label):
    n = len(df)
    losers = df[df["net_profit"] < 0]
    cash = df["real_cash_paid"].sort_values()
    reached = df.dropna(subset=["crossing_day"])

    print("=" * 100)
    print(f"RÉGIME : {label} -- {n} runs, année 1, réserve poolée + immunité post-financement")
    print("=" * 100)
    print(f"P(perte) année 1                 : {len(losers)/n*100:.2f}% ({len(losers)}/{n})")
    print(f"Trésorerie perso -- moyenne       : {cash.mean():,.0f}€")
    print(f"Trésorerie perso -- médiane       : {cash.median():,.0f}€")
    print(f"Trésorerie perso -- pire cas      : {cash.max():,.0f}€")
    for t in (1000, 2000, 3000):
        pct = (cash > t).sum() / n * 100
        print(f"P(>{t}€)                        : {pct:.2f}%")
    print(f"P(dépasse 3000€, budget strict)  : {(cash > 3000).sum()/n*100:.2f}% ({(cash>3000).sum()}/{n})")
    if not reached.empty:
        print(f"[Parmi les runs qui dépassent 3000€] jour moyen {reached['crossing_day'].mean():.1f}j | "
              f"trades fleet moyen {reached['crossing_trades'].mean():.1f}")
    else:
        print("[Aucun run ne dépasse 3000€ -- pas de statistique de timing]")
    print()

    return {
        "regime": label, "n": n, "pct_loss": len(losers) / n * 100,
        "cash_mean": cash.mean(), "cash_median": cash.median(), "cash_worst": cash.max(),
        "p_gt_1000": (cash > 1000).sum() / n * 100, "p_gt_2000": (cash > 2000).sum() / n * 100,
        "p_gt_3000": (cash > 3000).sum() / n * 100,
        "crossing_day_mean": reached["crossing_day"].mean() if not reached.empty else None,
        "crossing_trades_mean": reached["crossing_trades"].mean() if not reached.empty else None,
    }


def main():
    pop = build_population_with_trailing("fixed", 0.2, verbose=False)
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    sub, trades, slot_arrivals = build_trades_trailing(pop)
    tickers = sorted(set(t["ticker"] for t in trades))
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
    blocks = build_blocks(trades, slot_arrivals, block_seconds)

    df_low = run_regime(blocks, block_seconds, market_data, excluded_map, 0.5, 0.5, False, "0.5%_pur")
    s_low = summarize(df_low, "0.5% PUR (fixe)")

    df_high = run_regime(blocks, block_seconds, market_data, excluded_map, 2.0, 2.0, False, "2.0%_direct")
    s_high = summarize(df_high, "2.0% DIRECT (fixe dès le départ)")

    df_hybrid = run_regime(blocks, block_seconds, market_data, excluded_map, 0.5, 2.0, True, "hybride_0.5-2.0")
    s_hybrid = summarize(df_hybrid, "HYBRIDE 0.5%->2%@réserve 5000€")

    summary_df = pd.DataFrame([s_low, s_high, s_hybrid])
    summary_df.to_csv("three_regime_cash_comparison_summary.csv", index=False)

    print("=" * 100)
    print("TABLEAU COMPARATIF FINAL -- réserve poolée + immunité perso post-financement")
    print("=" * 100)
    print(summary_df.to_string(index=False))


if __name__ == "__main__":
    main()
