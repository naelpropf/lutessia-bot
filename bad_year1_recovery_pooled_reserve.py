"""
CORRECTIF méthodologique sur bad_year1_recovery_test.py / reference_metrics_final.py :
ces scripts utilisaient une réserve INDÉPENDANTE par compte (chaque compte finance
UNIQUEMENT ses propres rachats avec SES propres gains), alors que tous les docstrings
du projet parlent de "réserve commune" -- incohérence jamais corrigée jusqu'ici.

Règle correcte implémentée ici (demandée explicitement) :
  - Réserve UNIQUE, partagée par les 3 comptes (alimentée par 80% des gains de
    N'IMPORTE QUEL compte en phase financée, utilisée pour payer un rachat/upgrade
    sur N'IMPORTE QUEL compte de la flotte).
  - Tant qu'AUCUN compte n'a jamais été financé (ever_funded=False) : un rachat non
    couvert par la réserve tape dans le budget personnel (real_cash_paid), exposé au
    plafond de 3000€.
  - Dès qu'AU MOINS UN compte a été financé une première fois (ever_funded=True,
    définitif, ne repasse jamais à False) : plus AUCUN rachat ne tape dans le budget
    personnel, quelle que soit l'insuffisance de la réserve à cet instant précis (le
    déficit est absorbé en interne, pas compté comme sortie personnelle -- cohérent
    avec la règle demandée "peu importe combien de casses surviennent ensuite").
  - Palier/phase/drawdown restent PROPRES À CHAQUE COMPTE (leur trajectoire peut
    diverger dès que la réserve est partagée : un compte peut être upgradé avant un
    autre selon l'ordre de consommation de la réserve commune à un instant donné) --
    d'où une marche par trade avec les 3 comptes traités EN PARALLÈLE, pas l'un après
    l'autre comme dans reference_metrics_final.py (valide uniquement en réserve
    indépendante, où les 3 comptes sont des clones déterministiques identiques).
  - Le déclenchement de bascule 0.5%->2% (switched) est également rendu FLOTTE-WIDE
    (un seul flag, sur la réserve commune >= 5000€), cohérent avec le même docstring.
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

LOW_RISK = 0.5
HIGH_RISK = 2.0
RESERVE_SWITCH_THRESHOLD = 5000.0
N_ACCOUNTS = 3
YEAR_SECONDS = 365.25 * 86400
BLOCK_MONTHS = 2
TARGET_YEARS = 4


def run_fleet_multi_mark_pooled(trades, slot_arrivals, market_data, excluded_map, order, year_marks_seconds):
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

    marks_sorted = sorted(year_marks_seconds)
    mark_idx = 0
    snapshots = []

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]

        while mark_idx < len(marks_sorted) and now > marks_sorted[mark_idx]:
            combined_net = sum(a["total_funded_pnl"] - a["total_fees_paid"] for a in accounts)
            snapshots.append((marks_sorted[mark_idx], combined_net, real_cash_paid))
            mark_idx += 1

        for acc in accounts:
            close_time = now + trade["hold_seconds"]
            acc["open_positions"] = [(t, c) for (t, c) in acc["open_positions"] if c > now]
            if len(acc["open_positions"]) >= MAX_POSITIONS:
                continue
            if any(t in excluded_map[trade["ticker"]] for (t, _) in acc["open_positions"]):
                continue

            current_risk = HIGH_RISK if switched else LOW_RISK
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
                    # sinon : déficit absorbé en interne, plus de sortie personnelle
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

    while mark_idx < len(marks_sorted):
        combined_net = sum(a["total_funded_pnl"] - a["total_fees_paid"] for a in accounts)
        snapshots.append((marks_sorted[mark_idx], combined_net, real_cash_paid))
        mark_idx += 1

    return snapshots


def main():
    pop = build_population_with_trailing("fixed", 0.2, verbose=False)
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    sub, trades, slot_arrivals = build_trades_trailing(pop)
    tickers = sorted(set(t["ticker"] for t in trades))
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
    blocks = build_blocks(trades, slot_arrivals, block_seconds)

    year_marks_seconds = [YEAR_SECONDS, TARGET_YEARS * YEAR_SECONDS]
    target_duration = TARGET_YEARS * YEAR_SECONDS

    rng = random.Random(42)
    rows = []
    for _ in range(N_SIMULATIONS):
        synthetic_trades, synthetic_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, target_duration)
        order = list(range(len(synthetic_trades)))
        snaps = run_fleet_multi_mark_pooled(synthetic_trades, synthetic_slots, market_data, excluded_map, order, year_marks_seconds)
        rows.append({
            "year1_net": snaps[0][1], "year4_net": snaps[1][1],
            "year1_cash": snaps[0][2], "year4_cash": snaps[1][2],
        })

    df = pd.DataFrame(rows)
    df.to_csv("bad_year1_recovery_pooled_detail.csv", index=False)

    n = len(df)
    bad_year1 = df[df["year1_net"] < 0]
    nb = len(bad_year1)

    print("=" * 100)
    print(f"RÉSERVE COMMUNE POOLÉE + IMMUNITÉ PERSO POST-1ER FINANCEMENT -- {n} runs")
    print("=" * 100)
    print(f"P(année 1 en perte) = {nb/n*100:.2f}% ({nb}/{n}) [comparer à 21.8%/21.75% du calcul non poolé]")

    print(f"\n--- Sous-ensemble 'année 1 en perte' (n={nb}) ---")
    print(f"Profit net cumulé fin année 4 -- moyenne {bad_year1['year4_net'].mean():+,.0f}€ | "
          f"médiane {bad_year1['year4_net'].median():+,.0f}€")
    pct_recovered = (bad_year1["year4_net"] > 0).sum() / nb * 100
    print(f"% qui redevient positif en année 4 : {pct_recovered:.1f}%")

    cash = bad_year1["year4_cash"].sort_values()
    nc = len(cash)
    print(f"\nTrésorerie perso CUMULÉE 4 ans (règle pré-financement stricte) :")
    print(f"Moyenne  : {cash.mean():,.0f}€")
    print(f"Médiane  : {cash.median():,.0f}€")
    print(f"Pire cas : {cash.max():,.0f}€")
    for t in (1000, 2000, 3000, 5000):
        pct = (cash > t).sum() / nc * 100
        print(f"P(>{t}€)  : {pct:.2f}%")

    print(f"\nDétail (2000 runs) enregistré dans bad_year1_recovery_pooled_detail.csv")


if __name__ == "__main__":
    main()
