"""
Trouve le seuil de réserve optimal pour basculer de 0.5% à 2% de risque par compte,
sur l'année 1 (la période critique, réserve=0 au départ). Réutilise EXACTEMENT la
méthodologie corrigée de real_cash_risk_year1_mc.py (upgrade gaté par reserve>=coût,
donc jamais payé par le trader ; une casse est couverte par la réserve en priorité,
le trader ne paie que le manque à gagner si la réserve est insuffisante).

5 déclencheurs testés (tous en copytrade 3 comptes/3 firms, seuil rr_tp1>=1.5, payoff
réaliste TP2 + trailing 0.2xSL, plafond 3 positions, corrélation 0.6+JPY, faisabilité
marge/lots) :
  1. Bascule immédiate au 1er financement (réserve peut être encore à 0)
  2. Bascule quand la réserve atteint 1000€
  3. Bascule quand la réserve atteint 2000€
  4. Bascule quand la réserve atteint 3000€
  5. Bascule quand la réserve atteint 5000€

La bascule est IRRÉVERSIBLE une fois déclenchée (même si un upgrade consomme ensuite
la réserve et la fait retomber sous le seuil) -- c'est un changement de politique de
risque permanent, pas un interrupteur qui va-et-vient avec le niveau de réserve.
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

LOW_RISK = 0.5
HIGH_RISK = 2.0
N_ACCOUNTS = 3
YEAR_SECONDS = 365.25 * 86400

TRIGGERS = {
    "1. Immédiat au financement": None,
    "2. Réserve >= 1000€": 1000,
    "3. Réserve >= 2000€": 2000,
    "4. Réserve >= 3000€": 3000,
    "5. Réserve >= 5000€": 5000,
}


def run_one_hybrid(trades, slot_arrivals, reserve_threshold, market_data, excluded_map, rng, order=None):
    """Un compte : risque LOW_RISK jusqu'au déclencheur (immédiat au 1er financement si
    reserve_threshold=None, sinon dès que la réserve atteint ce seuil), HIGH_RISK
    ensuite, de façon irréversible. Retourne (real_cash_year1, net_profit_year1,
    switch_time_seconds ou None si jamais déclenché sur tout l'historique dispo)."""
    if order is None:
        order = list(range(len(trades)))
        rng.shuffle(order)

    palier = TIER_SEQUENCE[0]
    phase = "challenge"
    cumulative_since_reset = 0.0
    peak_since_reset = 0.0
    trading_days_since_reset = set()
    reserve = 0.0
    open_positions = []

    real_cash_paid = CHALLENGE_COST[palier]
    total_trading_pnl = 0.0
    total_fees_paid = CHALLENGE_COST[palier]

    switched = False
    switch_time = None
    year1_real_cash = None
    year1_net_profit = None

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]

        if year1_real_cash is None and now > YEAR_SECONDS:
            year1_real_cash = real_cash_paid
            year1_net_profit = total_trading_pnl - total_fees_paid

        close_time = now + trade["hold_seconds"]
        open_positions = [(t, c) for (t, c) in open_positions if c > now]

        if len(open_positions) >= MAX_POSITIONS:
            continue
        if any(t in excluded_map[trade["ticker"]] for (t, _) in open_positions):
            continue

        current_risk = HIGH_RISK if switched else LOW_RISK
        effective_risk_pct, _ = feasible_risk_pct(trade["ticker"], trade["sl_distance"], palier, current_risk, market_data)
        risk_amount = effective_risk_pct / 100 * palier
        pnl = trade["outcome_r"] * risk_amount

        open_positions.append((trade["ticker"], close_time))
        total_trading_pnl += pnl
        cumulative_since_reset += pnl
        peak_since_reset = max(peak_since_reset, cumulative_since_reset)
        trading_days_since_reset.add(int(now // 86400))

        if phase == "funded" and pnl > 0:
            reserve += pnl * RESERVE_SHARE

        if not switched and reserve_threshold is not None and reserve >= reserve_threshold:
            switched = True
            switch_time = now

        drawdown = peak_since_reset - cumulative_since_reset
        if drawdown >= BREAK_DD_PCT / 100 * palier:
            cost = CHALLENGE_COST[palier]
            if reserve >= cost:
                reserve -= cost
            else:
                real_cash_paid += cost - reserve
                reserve = 0.0
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
            cumulative_since_reset = 0.0
            peak_since_reset = 0.0
            trading_days_since_reset = set()
            if not switched and reserve_threshold is None:
                switched = True
                switch_time = now

        if phase == "funded":
            idx = TIER_SEQUENCE.index(palier)
            if idx + 1 < len(TIER_SEQUENCE):
                next_tier = TIER_SEQUENCE[idx + 1]
                cost = UPGRADE_COST[next_tier]
                if reserve >= cost:
                    reserve -= cost
                    total_fees_paid += cost
                    palier = next_tier
                    phase = "challenge"
                    cumulative_since_reset = 0.0
                    peak_since_reset = 0.0
                    trading_days_since_reset = set()

    if year1_real_cash is None:
        year1_real_cash = real_cash_paid
        year1_net_profit = total_trading_pnl - total_fees_paid

    return year1_real_cash, year1_net_profit, switch_time


def run_copytrade_hybrid_year1(trades, slot_arrivals, reserve_threshold, market_data, excluded_map, rng):
    order = list(range(len(trades)))
    rng.shuffle(order)
    per_account = [
        run_one_hybrid(trades, slot_arrivals, reserve_threshold, market_data, excluded_map, rng, order=order)
        for _ in range(N_ACCOUNTS)
    ]
    combined_real_cash = sum(r[0] for r in per_account)
    combined_net_profit = sum(r[1] for r in per_account)
    switch_time = per_account[0][2]  # identique sur les 3 comptes (même ordre, même trajectoire)
    return combined_real_cash, combined_net_profit, switch_time


def main():
    pop = build_population_with_trailing("fixed", 0.2, verbose=False)
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    sub, trades, slot_arrivals = build_trades_trailing(pop)
    tickers = sorted(set(t["ticker"] for t in trades))
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    print(f"Copytrade {N_ACCOUNTS} comptes, {LOW_RISK}% -> {HIGH_RISK}% selon déclencheur, "
          f"payoff TP2 réaliste + trailing 0.2xSL\n")

    rows = []
    for label, threshold in TRIGGERS.items():
        rng = random.Random(42)
        results = [run_copytrade_hybrid_year1(trades, slot_arrivals, threshold, market_data, excluded_map, rng)
                   for _ in range(N_SIMULATIONS)]

        real_cash_vals = sorted(r[0] for r in results)
        net_profit_vals = [r[1] for r in results]
        switch_times = [r[2] for r in results if r[2] is not None]

        n = len(real_cash_vals)
        mean_cash = sum(real_cash_vals) / n
        median_cash = real_cash_vals[n // 2]
        worst_cash = real_cash_vals[-1]

        mean_net_profit = sum(net_profit_vals) / len(net_profit_vals)

        pct_switched_year1 = sum(1 for r in results if r[2] is not None and r[2] <= YEAR_SECONDS) / n * 100
        delays_year1 = [t / 86400 / 30.44 for t in switch_times if t <= YEAR_SECONDS]
        mean_delay_months = sum(delays_year1) / len(delays_year1) if delays_year1 else float("nan")

        row = {"trigger": label, "reserve_threshold": threshold,
               "mean_real_cash": mean_cash, "median_real_cash": median_cash, "worst_real_cash": worst_cash,
               "pct_gt_1000": sum(1 for r in real_cash_vals if r > 1000) / n * 100,
               "pct_gt_2000": sum(1 for r in real_cash_vals if r > 2000) / n * 100,
               "pct_gt_3000": sum(1 for r in real_cash_vals if r > 3000) / n * 100,
               "mean_net_profit_year1": mean_net_profit,
               "pct_switched_within_year1": pct_switched_year1,
               "mean_delay_months": mean_delay_months}
        rows.append(row)

        print("=" * 100)
        print(f"DÉCLENCHEUR : {label}")
        print("=" * 100)
        print(f"Trésorerie réelle -- moyenne {mean_cash:,.0f}€ | médiane {median_cash:,.0f}€ | pire cas {worst_cash:,.0f}€")
        print(f"P(>1000€) {row['pct_gt_1000']:.2f}% | P(>2000€) {row['pct_gt_2000']:.2f}% | P(>3000€) {row['pct_gt_3000']:.2f}%")
        print(f"Profit net moyen année 1 (flotte) : {mean_net_profit:+,.0f}€")
        print(f"Bascule atteinte pendant l'année 1 : {pct_switched_year1:.1f}% des runs "
              f"(délai moyen quand atteint : {mean_delay_months:.2f} mois)")
        print()

    summary_df = pd.DataFrame(rows)
    summary_df.to_csv("risk_switch_threshold_summary.csv", index=False)

    print("=" * 100)
    print("TABLEAU COMPARATIF FINAL")
    print("=" * 100)
    print(summary_df.to_string(index=False))
    print("\nRésumé enregistré dans risk_switch_threshold_summary.csv")
    return summary_df


if __name__ == "__main__":
    main()
