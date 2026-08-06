"""
Risque de trésorerie RÉELLE (distinct du risque statistique déjà mesuré) : avant
d'avoir jamais atteint le statut "financé" pour la première fois, chaque casse du
challenge 50k coûte CHALLENGE_COST[50000] = 333€ de VRAI argent (poche perso), pas
la "réserve" simulée (alimentée par 80% des gains une fois financé, qui elle peut
aller à l'infini négatif dans le modèle actuel — non pertinent ici puisqu'aucun
gain réel n'existe encore tant qu'on n'a jamais été financé).

Question posée : avec un budget réel de 1000€ (puis 2000€), quelle est la
probabilité de l'épuiser AVANT la toute première réussite du challenge ? Et combien
de tentatives (à 333€ chacune) faut-il en moyenne ?

Seuil utilisé : rr_tp1 >= 1.5 (le seuil actuellement adopté en production, cf.
app.py). Si l'intention était de tester à l'ancien seuil 2.0, le réexécuter avec
THRESHOLD = 2.0 ci-dessous.
"""
import random

import pandas as pd

from scaling_simulation import (
    TIER_SEQUENCE, CHALLENGE_COST, CHALLENGE_TARGET_PCT, MIN_TRADING_DAYS,
    BREAK_DD_PCT, MAX_POSITIONS, CORR_THRESHOLD, feasible_risk_pct, load_market_data,
)
from monte_carlo_simulation import precompute_correlation_pairs, N_SIMULATIONS
from rr_threshold_test import build_extended_population

THRESHOLD = 1.5
RISK_LEVELS = [0.5, 1.0, 1.5, 2.0, 3.0]
RESERVE_LEVELS = [1000, 2000, 3000]
CHALLENGE_COST_50K = CHALLENGE_COST[TIER_SEQUENCE[0]]

# 2000 runs suffisent pour les seuils -1000/-2000€ (probas de quelques % à ~10%),
# mais une estimation fiable de la queue à 0.1% a besoin de bien plus d'échantillons
# (à 2000 runs, un événement à 0.1% n'apparaît en moyenne que 2 fois — beaucoup trop
# bruité). On relance donc avec un N plus grand pour CETTE analyse spécifique.
EXTENDED_N = 20000


def simulate_prefunding(trades, slot_arrivals, risk_pct, market_data, excluded_map, rng):
    """Simule UNIQUEMENT la phase avant la 1ère réussite du challenge (toujours au
    palier 50k). Retourne (attempts, funded) : attempts = nombre de tentatives de
    challenge effectivement engagées (la 1ère est déjà payée avant le 1er trade),
    funded = True si le statut financé a été atteint dans l'historique disponible
    de cette permutation, False si l'historique s'épuise avant."""
    order = list(range(len(trades)))
    rng.shuffle(order)

    palier = TIER_SEQUENCE[0]
    cumulative_since_reset = 0.0
    peak_since_reset = 0.0
    trading_days_since_reset = set()
    open_positions = []
    attempts = 1

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]
        close_time = now + trade["hold_seconds"]

        open_positions = [(t, c) for (t, c) in open_positions if c > now]
        if len(open_positions) >= MAX_POSITIONS:
            continue
        if any(t in excluded_map[trade["ticker"]] for (t, _) in open_positions):
            continue

        target_risk_pct = risk_pct(palier) if callable(risk_pct) else risk_pct
        effective_risk_pct, _ = feasible_risk_pct(
            trade["ticker"], trade["sl_distance"], palier, target_risk_pct, market_data
        )
        risk_amount = effective_risk_pct / 100 * palier
        pnl = trade["outcome_r"] * risk_amount

        open_positions.append((trade["ticker"], close_time))

        cumulative_since_reset += pnl
        peak_since_reset = max(peak_since_reset, cumulative_since_reset)
        trading_days_since_reset.add(int(now // 86400))

        drawdown = peak_since_reset - cumulative_since_reset
        if drawdown >= BREAK_DD_PCT / 100 * palier:
            attempts += 1
            cumulative_since_reset = 0.0
            peak_since_reset = 0.0
            trading_days_since_reset = set()
            continue

        if (cumulative_since_reset >= CHALLENGE_TARGET_PCT / 100 * palier
                and len(trading_days_since_reset) >= MIN_TRADING_DAYS):
            return attempts, True

    return attempts, False


def run_for_risk_level(pop, risk_pct, market_data, corr_matrix, n=N_SIMULATIONS, seed=42):
    sub = pop.sort_values("date_creation").reset_index(drop=True)
    t0 = sub["date_creation"].iloc[0]
    slot_arrivals = [(d - t0).total_seconds() for d in sub["date_creation"]]

    trades = []
    for _, row in sub.iterrows():
        hold_seconds = (row["resolution_time_est"] - row["date_creation"]).total_seconds()
        sl_distance = abs(row["prix_entree"] - row["stop_loss_init"])
        trades.append({
            "ticker": row["ticker"],
            "outcome_r": row["rr_tp1"] if row["statut_final"] == "OBJECTIF ATTEINT" else -1.0,
            "sl_distance": sl_distance,
            "hold_seconds": hold_seconds,
        })

    tickers = sorted(set(t["ticker"] for t in trades))
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    rng = random.Random(seed)
    results = [simulate_prefunding(trades, slot_arrivals, risk_pct, market_data, excluded_map, rng) for _ in range(n)]
    return results


def main():
    pop_full, _ = build_extended_population()
    pop = pop_full[pop_full["rr_tp1"] >= THRESHOLD].copy()
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)

    print(f"Seuil utilisé : rr_tp1 >= {THRESHOLD} (seuil actuellement en production)")
    print(f"Coût d'une tentative de challenge à 50k : {CHALLENGE_COST_50K}€")
    print(f"Nombre de simulations par niveau de risque : {EXTENDED_N} "
          f"(relevé de {N_SIMULATIONS} pour une résolution fiable sur la queue à 0.1%)\n")

    rows = []
    for risk_pct in RISK_LEVELS:
        results = run_for_risk_level(pop, risk_pct, market_data, corr_matrix, n=EXTENDED_N)
        attempts = [a for a, funded in results]
        funded_flags = [funded for a, funded in results]
        n = len(results)

        never_funded = sum(1 for f in funded_flags if not f)
        attempts_when_funded = [a for a, f in zip(attempts, funded_flags) if f]
        mean_attempts = sum(attempts_when_funded) / len(attempts_when_funded) if attempts_when_funded else float("nan")

        p_more_than_3 = sum(1 for a in attempts if a > 3) / n * 100

        row = {"risk_pct": risk_pct, "n_never_funded_in_sample": never_funded,
               "mean_attempts_before_success": mean_attempts, "pct_more_than_3_attempts": p_more_than_3}

        print(f"--- Risque {risk_pct}% ---")
        print(f"  Jamais financé dans l'historique disponible de la permutation : {never_funded}/{n} "
              f"({never_funded/n*100:.1f}%)")
        print(f"  Tentatives moyennes avant 1ère réussite (sur les runs financés) : {mean_attempts:.2f}")
        print(f"  P(plus de 3 tentatives nécessaires) : {p_more_than_3:.1f}%")

        for reserve in RESERVE_LEVELS:
            max_attempts_ok = reserve // CHALLENGE_COST_50K  # nb de tentatives finançables sans dépasser la réserve
            p_breach = sum(1 for a in attempts if a * CHALLENGE_COST_50K > reserve) / n * 100
            row[f"pct_breach_{reserve}"] = p_breach
            print(f"  P(réserve réelle < -{reserve}€ avant 1ère réussite) : {p_breach:.2f}% "
                  f"(épuisée dès la {int(max_attempts_ok)+1}e tentative)")

        # Plus petit N tel que P(il faille plus de N tentatives) < 0.1% — le seuil de
        # "quasi-certitude de réussite" demandé.
        max_observed = max(attempts)
        quasi_certain_n = None
        for k in range(1, max_observed + 2):
            p_tail = sum(1 for a in attempts if a > k) / n * 100
            if p_tail < 0.1:
                quasi_certain_n = k
                break
        row["quasi_certain_attempts"] = quasi_certain_n
        if quasi_certain_n is not None:
            p_at_k = sum(1 for a in attempts if a > quasi_certain_n) / n * 100
            print(f"  Quasi-certitude de réussite (P(plus de N tentatives) < 0.1%) : atteinte à N = {quasi_certain_n} "
                  f"tentatives (P observée = {p_at_k:.3f}%, coût cumulé {quasi_certain_n * CHALLENGE_COST_50K}€)")
        else:
            print(f"  Quasi-certitude de réussite : NON atteinte même au max observé ({max_observed} tentatives) "
                  f"sur {n} runs — queue trop épaisse pour conclure à ce N.")
        print()

        rows.append(row)

    summary_df = pd.DataFrame(rows)
    summary_df.to_csv("real_cash_risk_summary.csv", index=False)
    print("Résumé enregistré dans real_cash_risk_summary.csv")
    return summary_df


if __name__ == "__main__":
    main()
