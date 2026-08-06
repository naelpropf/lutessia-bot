"""
Correction méthodologique : le calcul précédent de trésorerie réelle (real_cash_risk
mois par mois, année 1) comptait CHAQUE upgrade (200k, 500k) comme argent sorti de la
poche du trader. C'est faux -- scaling_simulation.py (ligne 235) n'autorise un upgrade
QUE si reserve >= cost (jamais automatique sur le seul +8% cumulé) : l'upgrade est donc
TOUJOURS payé par la réserve commune (alimentée par 80% des gains une fois financé),
jamais par le trader directement.

Argent RÉEL sorti de la poche du trader, dans ce script (rien d'autre) :
  (a) le coût initial du tout premier challenge à 50k, par compte (avant tout
      financement, réserve = 0 par construction) ;
  (b) le coût de reconstruction après une casse, MAIS SEULEMENT LE MANQUE À GAGNER si
      la réserve courante ne suffit pas à le couvrir intégralement (on pioche d'abord
      dans la réserve existante, le trader ne paie que le manque, pas le coût entier
      si une partie est déjà couverte par la réserve).
Aucun coût d'upgrade n'est jamais compté comme argent personnel (toujours gaté par
reserve >= cost, donc toujours financé par la réserve quand il a lieu).

Monte Carlo (2000 runs, bootstrap par permutation), copytrade 3 comptes/3 firms,
risque 2%/compte, seuil rr_tp1>=1.5, payoff réaliste TP2 + trailing 0.2xSL, plafond 3
positions/compte, corrélation 0.6+JPY, faisabilité marge(1:30)/100 lots -- restreint à
l'horizon de la première année (12 mois), la période la plus critique puisque les
comptes ne sont pas encore financés au départ (réserve = 0).
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

RISK_PCT = 2.0
N_ACCOUNTS = 3
YEAR_SECONDS = 365.25 * 86400


def run_one_real_cash(trades, slot_arrivals, risk_pct, market_data, excluded_map, rng, order=None):
    """Un compte : rejoue la logique EXACTE de scaling_simulation.py (upgrade gaté par
    reserve >= cost), en ne comptabilisant en 'argent réel sorti de la poche' QUE le
    challenge initial et le manque à gagner (cost - reserve) sur une casse dont la
    réserve ne couvre pas l'intégralité. Retourne le cash réel cumulé au bout d'un an
    (365.25 jours) -- si la période disponible est plus courte, retourne le cumul final."""
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

    real_cash_paid = CHALLENGE_COST[palier]  # (a) premier challenge, toujours poche perso (réserve=0)
    year1_real_cash = None

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]

        if year1_real_cash is None and now > YEAR_SECONDS:
            year1_real_cash = real_cash_paid

        close_time = now + trade["hold_seconds"]
        open_positions = [(t, c) for (t, c) in open_positions if c > now]

        if len(open_positions) >= MAX_POSITIONS:
            continue
        if any(t in excluded_map[trade["ticker"]] for (t, _) in open_positions):
            continue

        effective_risk_pct, _ = feasible_risk_pct(trade["ticker"], trade["sl_distance"], palier, risk_pct, market_data)
        risk_amount = effective_risk_pct / 100 * palier
        pnl = trade["outcome_r"] * risk_amount

        open_positions.append((trade["ticker"], close_time))
        cumulative_since_reset += pnl
        peak_since_reset = max(peak_since_reset, cumulative_since_reset)
        trading_days_since_reset.add(int(now // 86400))

        if phase == "funded" and pnl > 0:
            reserve += pnl * RESERVE_SHARE

        drawdown = peak_since_reset - cumulative_since_reset
        if drawdown >= BREAK_DD_PCT / 100 * palier:
            cost = CHALLENGE_COST[palier]
            if reserve >= cost:
                reserve -= cost  # (b) intégralement couvert par la réserve : 0€ de poche
            else:
                shortfall = cost - reserve  # (b) manque à gagner seulement
                real_cash_paid += shortfall
                reserve = 0.0
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

        if phase == "funded":
            idx = TIER_SEQUENCE.index(palier)
            if idx + 1 < len(TIER_SEQUENCE):
                next_tier = TIER_SEQUENCE[idx + 1]
                cost = UPGRADE_COST[next_tier]
                if reserve >= cost:  # upgrade TOUJOURS gaté -> jamais d'argent personnel ici
                    reserve -= cost
                    palier = next_tier
                    phase = "challenge"
                    cumulative_since_reset = 0.0
                    peak_since_reset = 0.0
                    trading_days_since_reset = set()

    if year1_real_cash is None:
        year1_real_cash = real_cash_paid

    return year1_real_cash


def run_copytrade_real_cash_year1(trades, slot_arrivals, risk_pct, market_data, excluded_map, rng):
    order = list(range(len(trades)))
    rng.shuffle(order)
    per_account = [
        run_one_real_cash(trades, slot_arrivals, risk_pct, market_data, excluded_map, rng, order=order)
        for _ in range(N_ACCOUNTS)
    ]
    return sum(per_account)


def main():
    pop = build_population_with_trailing("fixed", 0.2, verbose=True)
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    sub, trades, slot_arrivals = build_trades_trailing(pop)
    tickers = sorted(set(t["ticker"] for t in trades))
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    print(f"\nCopytrade {N_ACCOUNTS} comptes, risque {RISK_PCT}%/compte, payoff TP2 réaliste + trailing 0.2xSL")
    print(f"Coût initial garanti (poche perso, 3 comptes) : {N_ACCOUNTS * CHALLENGE_COST[TIER_SEQUENCE[0]]}€\n")

    rng = random.Random(42)
    results = [run_copytrade_real_cash_year1(trades, slot_arrivals, RISK_PCT, market_data, excluded_map, rng)
               for _ in range(N_SIMULATIONS)]

    results_sorted = sorted(results)
    n = len(results_sorted)
    mean_cash = sum(results_sorted) / n
    median_cash = results_sorted[n // 2]
    worst_case = results_sorted[-1]

    print("=" * 100)
    print(f"BESOIN RÉEL DE TRÉSORERIE PERSONNELLE — ANNÉE 1 SEULE ({N_SIMULATIONS} simulations)")
    print("=" * 100)
    print(f"Moyenne                    : {mean_cash:,.0f}€")
    print(f"Médiane                    : {median_cash:,.0f}€")
    print(f"Pire cas observé (max)     : {worst_case:,.0f}€")
    print()
    for seuil in [1000, 2000, 3000]:
        p = sum(1 for r in results if r > seuil) / n * 100
        print(f"P(besoin réel > {seuil}€) : {p:.2f}% ({sum(1 for r in results if r > seuil)}/{n} runs)")

    pd.DataFrame({"real_cash_year1": results}).to_csv("real_cash_risk_year1_mc_detail.csv", index=False)
    print("\nDétail (2000 valeurs) enregistré dans real_cash_risk_year1_mc_detail.csv")


if __name__ == "__main__":
    main()
