"""
Chiffrage du passage à N comptes The5%ers Summer Plan 100k (2-Step, variante 8/5 --
prix 179$, cible Phase 1 alignée sur CHALLENGE_TARGET_PCT=8% déjà utilisé dans tout le
projet) à la place des 3x50k prévus initialement.

Contraintes appliquées :
- N in {3, 4} SEULEMENT (300k / 400k), pour rester sous le plafond de copie
  inter-comptes de 500 000$ cumulés confirmé par le support The5%ers (N=5/6 exclus).
- Plan de risque réel conservé : 0.5% par compte pendant les RAMP_TRADES premiers
  trades RÉELS pris par CE compte (peu importe la phase challenge/financé), puis
  bascule définitive à 2% (régime A -- pas de seuil de réserve, pas de gate
  ever_funded : c'est un ramp-up basé sur le nombre de trades, pas sur un événement
  de financement). RAMP_TRADES=12 = milieu de la fourchette "10-15 trades réels"
  donnée -- CHOIX ARBITRAIRE À AJUSTER SI BESOIN.
- Moteur complet identique à regime_abc_comparison.py : block bootstrap 2 mois,
  réserve poolée entre les N comptes, immunité post-financement (ever_funded),
  comptabilité funded-only du P&L, coût cash initial = prix challenge x N.
- SIMPLIFICATION ASSUMÉE (conservatrice, sous-estime probablement le profit réel) :
  palier FIXE à 100 000$, PAS de scaling vers le haut. Le vrai plan 2-Step scale
  automatiquement et gratuitement par paliers de +10% de profit sur le même compte
  financé (jusqu'à un plafond variable selon les sources, 175k à 500k -- pas
  confirmé avec assez de certitude pour être modélisé sans fausser le chiffrage).
  Coût de rachat de challenge après casse = 179$ (prix Summer Plan), inchangé quel
  que soit le nombre de casses (pas de tarif dégressif connu).
"""
import random

import pandas as pd

from scaling_simulation import (
    CHALLENGE_TARGET_PCT, MIN_TRADING_DAYS, BREAK_DD_PCT, RESERVE_SHARE,
    MAX_POSITIONS, CORR_THRESHOLD, feasible_risk_pct, load_market_data,
)
from monte_carlo_simulation import precompute_correlation_pairs, N_SIMULATIONS
from trailing_payoff_population import build_population_with_trailing, build_trades_trailing
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from winrate_sensitivity_test import build_degraded_trades, DEGRADE_SEED

YEAR_SECONDS = 365.25 * 86400
BLOCK_MONTHS = 2
LOW_RISK, HIGH_RISK = 0.5, 2.0
RAMP_TRADES = 12  # milieu de "10-15 trades réels" -- ajustable

PALIER_100K = 100000
CHALLENGE_COST_100K = 179  # Summer Plan 2-Step 8/5 (cible Phase1=8%, cohérent avec CHALLENGE_TARGET_PCT)

N_VARIANTS = [3, 4]


def run_fleet_100k(trades, slot_arrivals, market_data, excluded_map, order, n_accounts, mark_seconds_list):
    accounts = []
    for _ in range(n_accounts):
        accounts.append({
            "phase": "challenge", "cumulative_since_reset": 0.0,
            "peak_since_reset": 0.0, "trading_days_since_reset": set(), "open_positions": [],
            "total_funded_pnl": 0.0, "total_fees_paid": CHALLENGE_COST_100K,
            "trades_taken": 0,
        })
    reserve = 0.0
    ever_funded = False
    real_cash_paid = CHALLENGE_COST_100K * n_accounts
    total_breaks = 0

    marks_sorted = sorted(mark_seconds_list)
    mark_idx = 0
    snapshots = []

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]

        while mark_idx < len(marks_sorted) and now > marks_sorted[mark_idx]:
            combined_net = sum(a["total_funded_pnl"] - a["total_fees_paid"] for a in accounts)
            snapshots.append((marks_sorted[mark_idx], combined_net, real_cash_paid, total_breaks))
            mark_idx += 1

        for acc in accounts:
            close_time = now + trade["hold_seconds"]
            acc["open_positions"] = [(t, c) for (t, c) in acc["open_positions"] if c > now]
            if len(acc["open_positions"]) >= MAX_POSITIONS:
                continue
            if any(t in excluded_map[trade["ticker"]] for (t, _) in acc["open_positions"]):
                continue

            current_risk = LOW_RISK if acc["trades_taken"] < RAMP_TRADES else HIGH_RISK
            eff_risk, _ = feasible_risk_pct(trade["ticker"], trade["sl_distance"], PALIER_100K, current_risk, market_data)
            risk_amount = eff_risk / 100 * PALIER_100K
            pnl = trade["outcome_r"] * risk_amount

            acc["open_positions"].append((trade["ticker"], close_time))
            acc["cumulative_since_reset"] += pnl
            acc["peak_since_reset"] = max(acc["peak_since_reset"], acc["cumulative_since_reset"])
            acc["trading_days_since_reset"].add(int(now // 86400))
            acc["trades_taken"] += 1

            if acc["phase"] == "funded":
                acc["total_funded_pnl"] += pnl
                if pnl > 0:
                    reserve += pnl * RESERVE_SHARE

            drawdown = acc["peak_since_reset"] - acc["cumulative_since_reset"]
            if drawdown >= BREAK_DD_PCT / 100 * PALIER_100K:
                total_breaks += 1
                if reserve >= CHALLENGE_COST_100K:
                    reserve -= CHALLENGE_COST_100K
                else:
                    shortfall = CHALLENGE_COST_100K - reserve
                    reserve = 0.0
                    if not ever_funded:
                        real_cash_paid += shortfall
                acc["total_fees_paid"] += CHALLENGE_COST_100K
                acc["phase"] = "challenge"
                acc["cumulative_since_reset"] = 0.0
                acc["peak_since_reset"] = 0.0
                acc["trading_days_since_reset"] = set()
                continue

            if (acc["phase"] == "challenge"
                    and acc["cumulative_since_reset"] >= CHALLENGE_TARGET_PCT / 100 * PALIER_100K
                    and len(acc["trading_days_since_reset"]) >= MIN_TRADING_DAYS):
                acc["phase"] = "funded"
                ever_funded = True
                acc["cumulative_since_reset"] = 0.0
                acc["peak_since_reset"] = 0.0
                acc["trading_days_since_reset"] = set()

    while mark_idx < len(marks_sorted):
        combined_net = sum(a["total_funded_pnl"] - a["total_fees_paid"] for a in accounts)
        snapshots.append((marks_sorted[mark_idx], combined_net, real_cash_paid, total_breaks))
        mark_idx += 1

    return snapshots


def run_variant(trades, slot_arrivals, blocks, block_seconds, target_duration, mark_seconds_list,
                 market_data, excluded_map, n_accounts):
    rng = random.Random(42)
    rows = []
    for _ in range(N_SIMULATIONS):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, target_duration)
        order = list(range(len(raw_trades)))
        snaps = run_fleet_100k(raw_trades, raw_slots, market_data, excluded_map, order, n_accounts, mark_seconds_list)
        rows.append({
            "year1_net": snaps[0][1], "year1_cash": snaps[0][2], "year1_breaks": snaps[0][3],
            "final_net": snaps[1][1], "final_cash": snaps[1][2], "final_breaks": snaps[1][3],
        })
    return pd.DataFrame(rows)


def build_population(pop, target_winrate):
    if target_winrate is None:
        return build_trades_trailing(pop)[1:]
    rng = random.Random(DEGRADE_SEED)
    _, trades, slot_arrivals, _ = build_degraded_trades(pop, target_winrate, rng)
    return trades, slot_arrivals


def main():
    pop = build_population_with_trailing("fixed", 0.2, verbose=False)
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    summary_rows = []
    for wr_label, wr_target in [("37.29%", None), ("32%", 0.32)]:
        trades, slot_arrivals = build_population(pop, wr_target)
        total_horizon_seconds = slot_arrivals[-1]
        mark_seconds_list = [YEAR_SECONDS, total_horizon_seconds]
        block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
        blocks = build_blocks(trades, slot_arrivals, block_seconds)

        for n_accounts in N_VARIANTS:
            print(f"Calcul : winrate {wr_label} | N={n_accounts} comptes 100k...")
            df = run_variant(trades, slot_arrivals, blocks, block_seconds, total_horizon_seconds,
                              mark_seconds_list, market_data, excluded_map, n_accounts)
            df.to_csv(f"the5ers_100k_N{n_accounts}_{wr_label.replace('%','pct').replace('.','_')}.csv", index=False)

            cash = df["final_cash"]
            row = {
                "winrate": wr_label, "n_accounts": n_accounts, "capital_total": n_accounts * PALIER_100K,
                "profit_year1_moyen": df["year1_net"].mean(), "profit_year1_median": df["year1_net"].median(),
                "profit_final_moyen": df["final_net"].mean(), "profit_final_median": df["final_net"].median(),
                "pct_loss_year1": (df["year1_net"] < 0).mean() * 100,
                "cash_worst": cash.max(), "cash_mean": cash.mean(),
                "p_gt_1000": (cash > 1000).mean() * 100, "p_gt_3000": (cash > 3000).mean() * 100,
                "p_gt_5000": (cash > 5000).mean() * 100, "p_gt_10000": (cash > 10000).mean() * 100,
                "casses_moyennes_final": df["final_breaks"].mean(),
            }
            summary_rows.append(row)
            print(f"  Profit an1  : moyenne {row['profit_year1_moyen']:+,.0f}$ | médiane {row['profit_year1_median']:+,.0f}$")
            print(f"  Profit final: moyenne {row['profit_final_moyen']:+,.0f}$ | médiane {row['profit_final_median']:+,.0f}$")
            print(f"  P(perte) an1 : {row['pct_loss_year1']:.2f}%")
            print(f"  Trésorerie -- moyenne {row['cash_mean']:,.0f}$ | pire cas {row['cash_worst']:,.0f}$")
            print(f"  P(>1000$) {row['p_gt_1000']:.2f}% | P(>3000$) {row['p_gt_3000']:.2f}% | "
                  f"P(>5000$) {row['p_gt_5000']:.2f}% | P(>10000$) {row['p_gt_10000']:.2f}%")
            print(f"  Casses moyennes (horizon complet) : {row['casses_moyennes_final']:.2f}")

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv("the5ers_100k_N_accounts_summary.csv", index=False)
    print("\nRésumé enregistré dans the5ers_100k_N_accounts_summary.csv")


if __name__ == "__main__":
    main()
