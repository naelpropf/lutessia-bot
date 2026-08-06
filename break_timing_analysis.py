"""
Distribution TEMPORELLE des casses (pas seulement leur moyenne totale) sur la config de
référence verrouillée : copytrade 3 comptes/3 firms, risque 2%/compte (régime final),
seuil rr_tp1 >= 1.5, payoff réaliste + trailing stop 0.2xSL déjà adopté (même config
exacte que copytrade_vs_fleet_trailing_02_summary.csv, ligne "copytrade" -- 41.4 casses
moyennes sur ~3.96 ans, 2022-08 -> 2026-07).

Pour CHAQUE run Monte Carlo (bootstrap par permutation, même méthode que
copytrade_simulation_test.py -- UNE permutation des trades, appliquée identiquement aux
3 comptes indépendants puisque c'est le même signal répliqué), on capture l'INSTANT de
CHAQUE casse (sur les 3 comptes confondus, c'est la charge opérationnelle totale de la
flotte qui nous intéresse -- rachats de challenge/KYC/re-vérifications), puis on calcule :
  - le nombre MAX de casses dans n'importe quelle fenêtre glissante de 30 jours
  - le nombre MAX de casses dans n'importe quelle fenêtre glissante de 91 jours (trimestre)
(fenêtre glissante, pas alignée sur le calendrier -- le pire cas peut chevaucher 2 mois
calendaires).

Les instants d'arrivée des signaux (slot_arrivals) sont les VRAIS timestamps historiques,
inchangés par le bootstrap (seule l'identité du trade affecté à chaque créneau est
permutée) -- donc la date réelle d'un pic de casses dans un run donné correspond à une
vraie période du calendrier, pas un artefact temporel du Monte Carlo.
"""
import random
import statistics
from datetime import timedelta

import pandas as pd

from scaling_simulation import (
    TIER_SEQUENCE, CHALLENGE_COST, UPGRADE_COST, CHALLENGE_TARGET_PCT,
    MIN_TRADING_DAYS, BREAK_DD_PCT, RESERVE_SHARE, MAX_POSITIONS, CORR_THRESHOLD,
    feasible_risk_pct, load_market_data,
)
from monte_carlo_simulation import precompute_correlation_pairs, N_SIMULATIONS
from trailing_payoff_population import build_population_with_trailing, build_trades_trailing
from copytrade_simulation_test import N_ACCOUNTS

RISK_PCT = 2.0
MONTH_SECONDS = 30 * 86400
QUARTER_SECONDS = 91 * 86400


def run_one_with_break_times(trades, slot_arrivals, risk_pct, market_data, excluded_map, rng, order=None):
    """Copie de monte_carlo_simulation.run_one, étendue pour renvoyer l'instant (en
    secondes depuis le début, = slot_arrivals du trade qui a déclenché chaque casse)."""
    if order is None:
        order = list(range(len(trades)))
        rng.shuffle(order)

    reserve = 0.0
    palier = TIER_SEQUENCE[0]
    phase = "challenge"
    total_fees_paid = CHALLENGE_COST[palier]
    cumulative_since_reset = 0.0
    peak_since_reset = 0.0
    trading_days_since_reset = set()
    total_trading_pnl = 0.0
    open_positions = []
    break_times = []

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]
        close_time = now + trade["hold_seconds"]

        open_positions = [(t, c) for (t, c) in open_positions if c > now]
        if len(open_positions) >= MAX_POSITIONS:
            continue
        if any(t in excluded_map[trade["ticker"]] for (t, _) in open_positions):
            continue

        eff_risk, _ = feasible_risk_pct(trade["ticker"], trade["sl_distance"], palier, risk_pct, market_data)
        risk_amount = eff_risk / 100 * palier
        pnl = trade["outcome_r"] * risk_amount

        open_positions.append((trade["ticker"], close_time))
        total_trading_pnl += pnl
        cumulative_since_reset += pnl
        peak_since_reset = max(peak_since_reset, cumulative_since_reset)
        trading_days_since_reset.add(int(now // 86400))

        if phase == "funded" and pnl > 0:
            reserve += pnl * RESERVE_SHARE

        drawdown = peak_since_reset - cumulative_since_reset
        if drawdown >= BREAK_DD_PCT / 100 * palier:
            break_times.append(now)
            total_fees_paid += CHALLENGE_COST[palier]
            phase = "challenge"
            cumulative_since_reset = 0.0
            peak_since_reset = 0.0
            trading_days_since_reset = set()
            continue

        if (phase == "challenge" and cumulative_since_reset >= CHALLENGE_TARGET_PCT / 100 * palier
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

    net_profit = total_trading_pnl - total_fees_paid
    return {"net_profit": net_profit, "break_times": break_times}


def run_copytrade_with_break_times(trades, slot_arrivals, risk_pct, market_data, excluded_map, rng):
    """UNE permutation, répliquée identiquement sur les 3 comptes indépendants (même
    signal, même principe que copytrade_simulation_test.run_copytrade_one) -- les
    instants de casse des 3 comptes sont fusionnés (charge opérationnelle de LA FLOTTE)."""
    order = list(range(len(trades)))
    rng.shuffle(order)

    all_break_times = []
    net_profit = 0.0
    for _ in range(N_ACCOUNTS):
        r = run_one_with_break_times(trades, slot_arrivals, risk_pct, market_data, excluded_map, rng, order=order)
        all_break_times.extend(r["break_times"])
        net_profit += r["net_profit"]

    all_break_times.sort()
    return {"net_profit": net_profit, "break_times": all_break_times}


def max_in_rolling_window(times_sorted, window_seconds):
    """Nombre MAX d'événements dans n'importe quelle fenêtre glissante de
    `window_seconds` (technique deux-pointeurs sur la liste triée)."""
    n = len(times_sorted)
    if n == 0:
        return 0
    j = 0
    best = 1
    for i in range(n):
        while times_sorted[i] - times_sorted[j] > window_seconds:
            j += 1
        best = max(best, i - j + 1)
    return best


def window_start_for_peak(times_sorted, window_seconds, peak_count):
    """Retourne l'indice de départ (dans times_sorted) de la PREMIÈRE fenêtre qui
    atteint le peak_count -- pour pouvoir remonter à la date réelle correspondante."""
    n = len(times_sorted)
    j = 0
    for i in range(n):
        while times_sorted[i] - times_sorted[j] > window_seconds:
            j += 1
        if i - j + 1 == peak_count:
            return j, i
    return None, None


def summarize_distribution(values):
    values_sorted = sorted(values)
    n = len(values_sorted)
    return {
        "mean": statistics.mean(values_sorted),
        "median": statistics.median(values_sorted),
        "p90": values_sorted[int(0.90 * n)],
        "worst": values_sorted[-1],
    }


def main():
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)

    pop = build_population_with_trailing("fixed", 0.2, verbose=True)
    sub, trades, slot_arrivals = build_trades_trailing(pop)
    start_date = sub["date_creation"].iloc[0]
    tickers = sorted(set(t["ticker"] for t in trades))
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    print(f"Population : {len(trades)} trades, {start_date} -> {sub['date_creation'].iloc[-1]}")
    print(f"Risque {RISK_PCT}%/compte, copytrade {N_ACCOUNTS} comptes, {N_SIMULATIONS} runs Monte Carlo\n")

    rng = random.Random(42)
    monthly_peaks = []
    quarterly_peaks = []
    all_broken_counts = []
    all_results = []

    for _ in range(N_SIMULATIONS):
        res = run_copytrade_with_break_times(trades, slot_arrivals, RISK_PCT, market_data, excluded_map, rng)
        bt = res["break_times"]
        all_broken_counts.append(len(bt))
        monthly_peaks.append(max_in_rolling_window(bt, MONTH_SECONDS))
        quarterly_peaks.append(max_in_rolling_window(bt, QUARTER_SECONDS))
        all_results.append(res)

    print("=" * 100)
    print("RAPPEL -- total de casses (moyenne simple, pour référence)")
    print("=" * 100)
    print(f"Casses totales moyennes (flotte, sur toute la période) : {statistics.mean(all_broken_counts):.2f}")

    print("\n" + "=" * 100)
    print(f"DISTRIBUTION DU PIC MENSUEL MAXIMUM (fenêtre glissante {MONTH_SECONDS/86400:.0f}j), sur {N_SIMULATIONS} runs")
    print("=" * 100)
    s = summarize_distribution(monthly_peaks)
    print(f"Moyenne : {s['mean']:.2f} | Médiane : {s['median']:.1f} | 90e percentile : {s['p90']} | Pire cas observé : {s['worst']}")
    print("Distribution complète (nombre de runs par valeur de pic mensuel) :")
    print(pd.Series(monthly_peaks).value_counts().sort_index().to_string())

    print("\n" + "=" * 100)
    print(f"DISTRIBUTION DU PIC TRIMESTRIEL MAXIMUM (fenêtre glissante {QUARTER_SECONDS/86400:.0f}j), sur {N_SIMULATIONS} runs")
    print("=" * 100)
    s2 = summarize_distribution(quarterly_peaks)
    print(f"Moyenne : {s2['mean']:.2f} | Médiane : {s2['median']:.1f} | 90e percentile : {s2['p90']} | Pire cas observé : {s2['worst']}")
    print("Distribution complète (nombre de runs par valeur de pic trimestriel) :")
    print(pd.Series(quarterly_peaks).value_counts().sort_index().to_string())

    pd.DataFrame({
        "monthly_peak": monthly_peaks, "quarterly_peak": quarterly_peaks, "total_broken": all_broken_counts,
    }).to_csv("break_timing_distribution.csv", index=False)

    # --- Investigation : à quoi correspond le pire cas trimestriel ? ---
    worst_idx = max(range(N_SIMULATIONS), key=lambda i: quarterly_peaks[i])
    worst_res = all_results[worst_idx]
    worst_peak = quarterly_peaks[worst_idx]
    j, i = window_start_for_peak(worst_res["break_times"], QUARTER_SECONDS, worst_peak)

    print("\n" + "=" * 100)
    print(f"INVESTIGATION -- run avec le pire pic trimestriel observé ({worst_peak} casses/trimestre)")
    print("=" * 100)
    if j is not None:
        window_start_date = start_date + timedelta(seconds=worst_res["break_times"][j])
        window_end_date = start_date + timedelta(seconds=worst_res["break_times"][i])
        print(f"Fenêtre concernée : {window_start_date.date()} -> {window_end_date.date()} "
              f"({(window_end_date - window_start_date).days} jours, {worst_peak} casses dans cette fenêtre)")
        print("Dates exactes des casses dans cette fenêtre :")
        for t in worst_res["break_times"][j:i + 1]:
            print(f"  {(start_date + timedelta(seconds=t))}")

    # Fréquence à laquelle chaque PÉRIODE DE 91 JOURS RÉELLE (indépendante du run) est
    # celle qui produit le pic trimestriel -- si un petit nombre de fenêtres calendaires
    # reviennent souvent, ça pointe vers une vraie période de marché difficile dans
    # l'historique (beaucoup de pertes réelles bootstrap-assignées à des créneaux
    # rapprochés), pas un artefact aléatoire du Monte Carlo.
    peak_window_months = []
    for res, qp in zip(all_results, quarterly_peaks):
        if qp < 6:  # ne garder que les runs avec un pic notable, pour la lisibilité
            continue
        jj, ii = window_start_for_peak(res["break_times"], QUARTER_SECONDS, qp)
        if jj is not None:
            peak_date = start_date + timedelta(seconds=res["break_times"][jj])
            peak_window_months.append(peak_date.strftime("%Y-%m"))

    if peak_window_months:
        print("\n" + "=" * 100)
        print(f"RÉCURRENCE DES FENÊTRES DE PIC (runs avec pic trimestriel >= 6 casses, n={len(peak_window_months)}) : "
              "mois calendaire de DÉBUT de la fenêtre de pic, groupé")
        print("=" * 100)
        print(pd.Series(peak_window_months).value_counts().head(15).to_string())

    print("\nRésumé enregistré dans break_timing_distribution.csv")
    return monthly_peaks, quarterly_peaks


if __name__ == "__main__":
    main()
