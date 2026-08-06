"""
Compare, pour un régime FIXE 0.5% pur vs un régime FIXE 2% direct dès le départ
(pas de bascule -- deux régimes statiques, à ne pas confondre avec le régime hybride
0.5%->2%@5000€ utilisé partout ailleurs), la VITESSE à laquelle le plafond de budget
perso de 3000€ (poche partagée sur les 3 comptes, cf. personal_cash_ceiling_test.py)
est atteint : jour moyen/médian de franchissement, et nombre de trades réellement
exécutés (les 3 comptes combinés, challenge + financé) avant ce franchissement.

Budget illimité ici (pas de retraite forcée) -- on ne mesure QUE le moment du premier
franchissement des 3000€ cumulés, pas les conséquences dessus (déjà traité dans
personal_cash_ceiling_test.py). Mêmes graines rng (42) pour les deux régimes ->
séquences de blocs directement comparables (paires), même construction que les
scripts précédents (année 1, block bootstrap 2 mois).
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
PERSONAL_CASH_LIMIT = 3000.0


def run_fleet_year1_fixed_risk(trades, slot_arrivals, market_data, excluded_map, order, fixed_risk_pct):
    accounts = []
    for _ in range(N_ACCOUNTS):
        accounts.append({
            "palier": TIER_SEQUENCE[0], "phase": "challenge", "cumulative_since_reset": 0.0,
            "peak_since_reset": 0.0, "trading_days_since_reset": set(), "reserve": 0.0,
            "open_positions": [],
        })
    cumulative_personal_cash = 0.0
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

            eff_risk, _ = feasible_risk_pct(trade["ticker"], trade["sl_distance"], acc["palier"], fixed_risk_pct, market_data)
            risk_amount = eff_risk / 100 * acc["palier"]
            pnl = trade["outcome_r"] * risk_amount

            acc["open_positions"].append((trade["ticker"], close_time))
            acc["cumulative_since_reset"] += pnl
            acc["peak_since_reset"] = max(acc["peak_since_reset"], acc["cumulative_since_reset"])
            acc["trading_days_since_reset"].add(int(now // 86400))
            total_trades_taken += 1

            if pnl > 0 and acc["phase"] == "funded":
                acc["reserve"] += pnl * RESERVE_SHARE

            drawdown = acc["peak_since_reset"] - acc["cumulative_since_reset"]
            if drawdown >= BREAK_DD_PCT / 100 * acc["palier"]:
                cost = CHALLENGE_COST[acc["palier"]]
                if acc["reserve"] >= cost:
                    acc["reserve"] -= cost
                else:
                    needed_personal = cost - acc["reserve"]
                    was_below = cumulative_personal_cash <= PERSONAL_CASH_LIMIT
                    cumulative_personal_cash += needed_personal
                    acc["reserve"] = 0.0
                    if crossing_day is None and was_below and cumulative_personal_cash > PERSONAL_CASH_LIMIT:
                        crossing_day = now / 86400
                        crossing_trades = total_trades_taken
                acc["phase"] = "challenge"
                acc["cumulative_since_reset"] = 0.0
                acc["peak_since_reset"] = 0.0
                acc["trading_days_since_reset"] = set()
                continue

            if (acc["phase"] == "challenge"
                    and acc["cumulative_since_reset"] >= CHALLENGE_TARGET_PCT / 100 * acc["palier"]
                    and len(acc["trading_days_since_reset"]) >= MIN_TRADING_DAYS):
                acc["phase"] = "funded"
                acc["cumulative_since_reset"] = 0.0
                acc["peak_since_reset"] = 0.0
                acc["trading_days_since_reset"] = set()

            if acc["phase"] == "funded":
                idx = TIER_SEQUENCE.index(acc["palier"])
                if idx + 1 < len(TIER_SEQUENCE):
                    next_tier = TIER_SEQUENCE[idx + 1]
                    cost = UPGRADE_COST[next_tier]
                    if acc["reserve"] >= cost:
                        acc["reserve"] -= cost
                        acc["palier"] = next_tier
                        acc["phase"] = "challenge"
                        acc["cumulative_since_reset"] = 0.0
                        acc["peak_since_reset"] = 0.0
                        acc["trading_days_since_reset"] = set()

    return crossing_day, crossing_trades, cumulative_personal_cash


def run_regime(blocks, block_seconds, market_data, excluded_map, fixed_risk_pct, label):
    rng = random.Random(42)
    rows = []
    for _ in range(N_SIMULATIONS):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, YEAR_SECONDS)
        cutoff = sum(1 for s in raw_slots if s <= YEAR_SECONDS)
        synth_trades = raw_trades[:cutoff]
        synth_slots = raw_slots[:cutoff]
        order = list(range(len(synth_trades)))

        crossing_day, crossing_trades, final_cash = run_fleet_year1_fixed_risk(
            synth_trades, synth_slots, market_data, excluded_map, order, fixed_risk_pct
        )
        rows.append({"crossing_day": crossing_day, "crossing_trades": crossing_trades, "final_cash": final_cash})

    df = pd.DataFrame(rows)
    df.to_csv(f"cash_ceiling_speed_{label}.csv", index=False)

    n = len(df)
    reached = df.dropna(subset=["crossing_day"])
    p_reached = len(reached) / n * 100

    print("=" * 100)
    print(f"RÉGIME FIXE {fixed_risk_pct}% -- {n} runs, année 1")
    print("=" * 100)
    print(f"P(plafond 3000€ atteint pendant l'année 1) = {p_reached:.2f}% ({len(reached)}/{n})")
    if not reached.empty:
        print(f"Jour de franchissement -- moyenne {reached['crossing_day'].mean():.1f}j | "
              f"médiane {reached['crossing_day'].median():.1f}j")
        print(f"Trades (3 comptes combinés) avant franchissement -- moyenne {reached['crossing_trades'].mean():.1f} | "
              f"médiane {reached['crossing_trades'].median():.1f}")
        print(f"Trades par compte (moyenne / 3) -- {reached['crossing_trades'].mean()/3:.1f}")
    return df, reached


def main():
    pop = build_population_with_trailing("fixed", 0.2, verbose=False)
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    sub, trades, slot_arrivals = build_trades_trailing(pop)
    tickers = sorted(set(t["ticker"] for t in trades))
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
    blocks = build_blocks(trades, slot_arrivals, block_seconds)

    df_low, reached_low = run_regime(blocks, block_seconds, market_data, excluded_map, 0.5, "low_0.5pct")
    print()
    df_high, reached_high = run_regime(blocks, block_seconds, market_data, excluded_map, 2.0, "high_2.0pct")

    print("\n" + "=" * 100)
    print("COMPARATIF FINAL")
    print("=" * 100)
    print(f"0.5% pur -- jour moyen {reached_low['crossing_day'].mean():.1f}j | trades moyen (fleet) {reached_low['crossing_trades'].mean():.1f}")
    print(f"2.0% direct -- jour moyen {reached_high['crossing_day'].mean():.1f}j | trades moyen (fleet) {reached_high['crossing_trades'].mean():.1f}")
    ratio_day = reached_low['crossing_day'].mean() / reached_high['crossing_day'].mean()
    ratio_trades = reached_low['crossing_trades'].mean() / reached_high['crossing_trades'].mean()
    print(f"Ratio vitesse (0.5% / 2%) -- jours : {ratio_day:.2f}x | trades : {ratio_trades:.2f}x")


if __name__ == "__main__":
    main()
