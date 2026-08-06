"""
Décompose les runs en perte de la simulation année 1 (reference_metrics_final.py,
volet A) pour répondre à 3 questions posées après coup sur le P(perte)=21.8% :

1. Les runs en perte sont-ils concentrés parmi ceux où la bascule 0.5%->2%
   (déclencheur réserve 5000€) survient TÔT dans l'année ?
2. Sur les runs en perte, le winrate observé sur CE run est-il cohérent avec
   l'edge normal (35-37%, malchance de séquence) ou anormalement bas (vrai
   signal d'edge dégradé plutôt que pure variance) ?
3. P(perte) SANS bascule (0.5% toute l'année) en comparaison -- la bascule
   est-elle ce qui introduit le risque, ou 0.5% pur a-t-il un risque comparable ?

Réutilise EXACTEMENT la même construction de séquence (block bootstrap 2 mois,
même graine rng=42, même ordre d'appel) que reference_metrics_final.py pour que
les 2000 runs soient directement comparables (même tirages) entre le régime
avec bascule et le régime 0.5% pur.
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
from reference_metrics_final import build_full_block_bootstrap_sequence, RESERVE_SWITCH_THRESHOLD

LOW_RISK = 0.5
HIGH_RISK = 2.0
N_ACCOUNTS = 3
YEAR_SECONDS = 365.25 * 86400
BLOCK_MONTHS = 2


def run_one_account_year1(trades, slot_arrivals, market_data, excluded_map, order, high_risk_enabled):
    """Variante de run_one_hybrid_funded qui trace en plus : le temps de bascule
    (None si jamais atteint) et le nb de trades gagnants/perdants EXÉCUTÉS sur ce
    compte (après filtre plafond/corrélation), pour un calcul de winrate fidèle à
    ce que le compte a réellement pris (pas juste la séquence brute)."""
    palier = TIER_SEQUENCE[0]
    phase = "challenge"
    cumulative_since_reset = 0.0
    peak_since_reset = 0.0
    trading_days_since_reset = set()
    reserve = 0.0
    open_positions = []

    total_funded_pnl = 0.0
    total_fees_paid = CHALLENGE_COST[palier]
    switched = False
    switch_time = None
    wins_taken = 0
    losses_taken = 0

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]

        close_time = now + trade["hold_seconds"]
        open_positions = [(t, c) for (t, c) in open_positions if c > now]

        if len(open_positions) >= MAX_POSITIONS:
            continue
        if any(t in excluded_map[trade["ticker"]] for (t, _) in open_positions):
            continue

        current_risk = (HIGH_RISK if switched else LOW_RISK) if high_risk_enabled else LOW_RISK
        effective_risk_pct, _ = feasible_risk_pct(trade["ticker"], trade["sl_distance"], palier, current_risk, market_data)
        risk_amount = effective_risk_pct / 100 * palier
        pnl = trade["outcome_r"] * risk_amount

        open_positions.append((trade["ticker"], close_time))
        cumulative_since_reset += pnl
        peak_since_reset = max(peak_since_reset, cumulative_since_reset)
        trading_days_since_reset.add(int(now // 86400))

        if phase == "funded":
            total_funded_pnl += pnl
            if pnl > 0:
                wins_taken += 1
            else:
                losses_taken += 1
            if pnl > 0:
                reserve += pnl * RESERVE_SHARE

        if high_risk_enabled and not switched and reserve >= RESERVE_SWITCH_THRESHOLD:
            switched = True
            switch_time = now

        drawdown = peak_since_reset - cumulative_since_reset
        if drawdown >= BREAK_DD_PCT / 100 * palier:
            cost = CHALLENGE_COST[palier]
            if reserve >= cost:
                reserve -= cost
            else:
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

    final_net_profit = total_funded_pnl - total_fees_paid
    return final_net_profit, switch_time, wins_taken, losses_taken


def run_fleet_year1(blocks, block_seconds, market_data, excluded_map, rng, high_risk_enabled):
    # build_full_block_bootstrap_sequence ajoute des blocs de BLOCK_MONTHS complets tant
    # que cursor < target_duration -- ça déborde de presque un bloc entier au-delà de la
    # marque d'1 an (comme reference_metrics_final.py, qui construit la séquence complète
    # sur l'horizon total puis prend un instantané au dernier trade <= marque). On
    # reproduit ici EXACTEMENT le même instantané : on tronque au dernier trade dont
    # l'arrivée est <= YEAR_SECONDS, pas au dernier bloc entier ajouté.
    raw_trades, raw_slots = build_full_block_bootstrap_sequence(
        blocks, block_seconds, rng, YEAR_SECONDS
    )
    cutoff = sum(1 for s in raw_slots if s <= YEAR_SECONDS)
    synthetic_trades = raw_trades[:cutoff]
    synthetic_slots = raw_slots[:cutoff]
    identity_order = list(range(len(synthetic_trades)))

    combined_final = 0.0
    switch_times = []
    total_wins = 0
    total_losses = 0
    for _ in range(N_ACCOUNTS):
        final_np, switch_time, wins, losses = run_one_account_year1(
            synthetic_trades, synthetic_slots, market_data, excluded_map, identity_order, high_risk_enabled
        )
        combined_final += final_np
        if switch_time is not None:
            switch_times.append(switch_time)
        total_wins += wins
        total_losses += losses

    first_switch = min(switch_times) if switch_times else None
    winrate = total_wins / (total_wins + total_losses) if (total_wins + total_losses) > 0 else None
    return combined_final, first_switch, winrate, total_wins, total_losses


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
    print(f"RÉGIME AVEC BASCULE (0.5%->2% @ réserve 5000€) -- {N_SIMULATIONS} runs, année 1 seule")
    print("=" * 100)

    rng_switch = random.Random(42)  # même graine que reference_metrics_final.py -> mêmes tirages
    rows_switch = []
    for _ in range(N_SIMULATIONS):
        final_np, first_switch, winrate, wins, losses = run_fleet_year1(
            blocks, block_seconds, market_data, excluded_map, rng_switch, high_risk_enabled=True
        )
        rows_switch.append({
            "net_profit": final_np, "first_switch_time": first_switch, "winrate": winrate,
            "wins": wins, "losses": losses,
        })
    df_switch = pd.DataFrame(rows_switch)
    df_switch.to_csv("year1_loss_decomposition_switch.csv", index=False)

    n = len(df_switch)
    losers = df_switch[df_switch["net_profit"] < 0]
    winners = df_switch[df_switch["net_profit"] >= 0]
    pct_loss_switch = len(losers) / n * 100
    print(f"P(perte) = {pct_loss_switch:.2f}% ({len(losers)}/{n} runs)")

    # --- Question 1 : timing de la bascule vs runs perdants ---
    print("\n--- Q1 : timing de la première bascule (0.5%->2%), perte vs gain ---")
    switched_losers = losers.dropna(subset=["first_switch_time"])
    switched_winners = winners.dropna(subset=["first_switch_time"])
    never_switched_losers = losers["first_switch_time"].isna().sum()
    never_switched_winners = winners["first_switch_time"].isna().sum()
    print(f"Runs perdants n'ayant JAMAIS basculé pendant l'année 1 : {never_switched_losers}/{len(losers)} "
          f"({never_switched_losers/len(losers)*100:.1f}%)")
    print(f"Runs gagnants n'ayant JAMAIS basculé pendant l'année 1 : {never_switched_winners}/{len(winners)} "
          f"({never_switched_winners/len(winners)*100:.1f}%)")
    if not switched_losers.empty and not switched_winners.empty:
        mean_switch_losers_days = switched_losers["first_switch_time"].mean() / 86400
        mean_switch_winners_days = switched_winners["first_switch_time"].mean() / 86400
        median_switch_losers_days = switched_losers["first_switch_time"].median() / 86400
        median_switch_winners_days = switched_winners["first_switch_time"].median() / 86400
        print(f"Parmi les runs ayant basculé -- délai moyen de bascule : "
              f"perdants {mean_switch_losers_days:.0f}j | gagnants {mean_switch_winners_days:.0f}j")
        print(f"Parmi les runs ayant basculé -- délai MÉDIAN de bascule : "
              f"perdants {median_switch_losers_days:.0f}j | gagnants {median_switch_winners_days:.0f}j")

    # --- Question 2 : winrate observé sur les runs perdants ---
    print("\n--- Q2 : winrate observé (trades financés exécutés) sur ce run précis ---")
    losers_wr = losers.dropna(subset=["winrate"])
    winners_wr = winners.dropna(subset=["winrate"])
    print(f"Winrate moyen -- runs PERDANTS : {losers_wr['winrate'].mean()*100:.2f}% "
          f"(médiane {losers_wr['winrate'].median()*100:.2f}%, n={len(losers_wr)})")
    print(f"Winrate moyen -- runs GAGNANTS : {winners_wr['winrate'].mean()*100:.2f}% "
          f"(médiane {winners_wr['winrate'].median()*100:.2f}%, n={len(winners_wr)})")
    print(f"Winrate moyen -- TOUS les runs  : {df_switch['winrate'].mean()*100:.2f}%")
    print(f"Nb moyen de trades financés exécutés par run perdant : {(losers['wins']+losers['losses']).mean():.1f}")
    print(f"Nb moyen de trades financés exécutés par run gagnant : {(winners['wins']+winners['losses']).mean():.1f}")

    # --- Question 3 : P(perte) sans bascule (0.5% pur toute l'année) ---
    print("\n" + "=" * 100)
    print(f"RÉGIME SANS BASCULE (0.5% fixe toute l'année) -- {N_SIMULATIONS} runs, mêmes tirages")
    print("=" * 100)
    rng_flat = random.Random(42)  # même graine -> mêmes séquences de blocs que ci-dessus
    rows_flat = []
    for _ in range(N_SIMULATIONS):
        final_np, _, winrate, wins, losses = run_fleet_year1(
            blocks, block_seconds, market_data, excluded_map, rng_flat, high_risk_enabled=False
        )
        rows_flat.append({"net_profit": final_np, "winrate": winrate, "wins": wins, "losses": losses})
    df_flat = pd.DataFrame(rows_flat)
    df_flat.to_csv("year1_loss_decomposition_flat.csv", index=False)

    n_flat = len(df_flat)
    losers_flat = df_flat[df_flat["net_profit"] < 0]
    pct_loss_flat = len(losers_flat) / n_flat * 100
    mean_flat = df_flat["net_profit"].mean()
    median_flat = df_flat["net_profit"].median()
    print(f"P(perte) = {pct_loss_flat:.2f}% ({len(losers_flat)}/{n_flat} runs)")
    print(f"Profit net moyen : {mean_flat:+,.0f}€ | médiane {median_flat:+,.0f}€")

    print("\n" + "=" * 100)
    print("RÉSUMÉ COMPARATIF")
    print("=" * 100)
    print(f"Avec bascule (0.5%->2%@5000€) : P(perte) = {pct_loss_switch:.2f}% | "
          f"profit moyen {df_switch['net_profit'].mean():+,.0f}€")
    print(f"Sans bascule (0.5% fixe)      : P(perte) = {pct_loss_flat:.2f}% | "
          f"profit moyen {mean_flat:+,.0f}€")

    print("\nDétail runs (avec bascule) : year1_loss_decomposition_switch.csv")
    print("Détail runs (sans bascule)  : year1_loss_decomposition_flat.csv")


if __name__ == "__main__":
    main()
