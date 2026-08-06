"""
Même analyse que winrate28_reference_regime_test.py, mais avec le régime 2% DIRECT
(risque fixe 2%/compte dès le premier trade, PAS de phase basse ni de bascule) au lieu
de l'hybride 0.5%->2%. Tout le reste identique : copytrade 3 comptes/flotte combinée,
réserve poolée (80% des gains financés), rr_tp1>=1.5, payoff réaliste + trailing
0.2xSL, plafond 3 positions/compte, corrélation 0.6+JPY, scaling 50k->200k->500k
(+8%/4j min), faisabilité marge 1:30 + 100 lots. Même winrate dégradé 28%
(DEGRADE_SEED=123, distribution des RR des gains inchangée) comparé à la référence
réelle (~37.3%).
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
from winrate_sensitivity_test import build_degraded_trades, DEGRADE_SEED

N_ACCOUNTS = 3
YEAR_SECONDS = 365.25 * 86400
MONTH_SECONDS = 30.44 * 86400
BLOCK_MONTHS = 2
FIXED_RISK = 2.0
TARGET_WINRATE = 0.28
MARK_MONTHS = [6, 12, 18, 24, 30, 36, 42, 48]


def run_fleet_multi_mark(trades, slot_arrivals, market_data, excluded_map, order, mark_seconds_list):
    accounts = []
    for _ in range(N_ACCOUNTS):
        accounts.append({
            "palier": TIER_SEQUENCE[0], "phase": "challenge", "cumulative_since_reset": 0.0,
            "peak_since_reset": 0.0, "trading_days_since_reset": set(), "open_positions": [],
            "total_funded_pnl": 0.0, "total_fees_paid": CHALLENGE_COST[TIER_SEQUENCE[0]],
        })
    reserve = 0.0
    ever_funded = False
    first_funded_time = None
    total_breaks = 0

    marks_sorted = sorted(mark_seconds_list)
    mark_idx = 0
    snapshots = []

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]

        while mark_idx < len(marks_sorted) and now > marks_sorted[mark_idx]:
            combined_net = sum(a["total_funded_pnl"] - a["total_fees_paid"] for a in accounts)
            snapshots.append((marks_sorted[mark_idx], combined_net))
            mark_idx += 1

        for acc in accounts:
            close_time = now + trade["hold_seconds"]
            acc["open_positions"] = [(t, c) for (t, c) in acc["open_positions"] if c > now]
            if len(acc["open_positions"]) >= MAX_POSITIONS:
                continue
            if any(t in excluded_map[trade["ticker"]] for (t, _) in acc["open_positions"]):
                continue

            eff_risk, _ = feasible_risk_pct(trade["ticker"], trade["sl_distance"], acc["palier"], FIXED_RISK, market_data)
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

            drawdown = acc["peak_since_reset"] - acc["cumulative_since_reset"]
            if drawdown >= BREAK_DD_PCT / 100 * acc["palier"]:
                cost = CHALLENGE_COST[acc["palier"]]
                total_breaks += 1
                if reserve >= cost:
                    reserve -= cost
                else:
                    reserve = 0.0
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
                if not ever_funded:
                    ever_funded = True
                    first_funded_time = now
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
        snapshots.append((marks_sorted[mark_idx], combined_net))
        mark_idx += 1

    final_net = sum(a["total_funded_pnl"] - a["total_fees_paid"] for a in accounts)
    return snapshots, final_net, first_funded_time, total_breaks


def compute_monthly_rate(trades, slot_arrivals, market_data, excluded_map, order, winrate_label):
    open_positions = []
    captured = []
    for slot_idx in order:
        trade = trades[slot_idx]
        now = slot_arrivals[slot_idx]
        close_time = now + trade["hold_seconds"]
        open_positions = [(t, c) for (t, c) in open_positions if c > now]
        if len(open_positions) >= MAX_POSITIONS:
            continue
        if any(t in excluded_map[trade["ticker"]] for (t, _) in open_positions):
            continue
        open_positions.append((trade["ticker"], close_time))
        captured.append(trade["outcome_r"])

    total_span_months = slot_arrivals[order[-1]] / MONTH_SECONDS
    freq_per_month = len(captured) / total_span_months
    ev_captee = sum(captured) / len(captured)

    print(f"\n--- Taux de rendement mensuel indépendant du capital -- {winrate_label} ---")
    print(f"Trades captés (plafond+corrélation) : {len(captured)}/{len(trades)} sur {total_span_months:.1f} mois "
          f"-> {freq_per_month:.2f} trades captés/mois/compte")
    print(f"EV captée : {ev_captee:+.4f}R")
    monthly_rate = ev_captee * (FIXED_RISK / 100) * freq_per_month * 100
    print(f"  Taux mensuel (2% direct, régime unique) = {ev_captee:+.4f} x {FIXED_RISK}% x {freq_per_month:.2f} "
          f"= {monthly_rate:+.3f}%/mois")
    return ev_captee, freq_per_month


def run_monte_carlo(trades, slot_arrivals, market_data, excluded_map, blocks, block_seconds, label):
    mark_seconds_list = [m / 12 * YEAR_SECONDS for m in MARK_MONTHS]
    target_duration = max(MARK_MONTHS) / 12 * YEAR_SECONDS

    rng = random.Random(42)
    rows = []
    for _ in range(N_SIMULATIONS):
        synthetic_trades, synthetic_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, target_duration)
        order = list(range(len(synthetic_trades)))
        snaps, final_net, first_funded_time, total_breaks = run_fleet_multi_mark(
            synthetic_trades, synthetic_slots, market_data, excluded_map, order, mark_seconds_list
        )
        row = {f"month{m}_net": snaps[i][1] for i, m in enumerate(MARK_MONTHS)}
        row.update({
            "final_net": final_net,
            "first_funded_days": first_funded_time / 86400 if first_funded_time is not None else None,
            "total_breaks": total_breaks,
        })
        rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(f"winrate28_2pctdirect_{label}_detail.csv", index=False)
    return df


def report_distribution(df, label):
    print(f"\n{'='*100}\nDISTRIBUTION PROFIT NET -- {label} (horizon complet ~4 ans, n={len(df)})\n{'='*100}")
    col = "final_net"
    for p in [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95]:
        print(f"P{int(p*100):<3} : {df[col].quantile(p):+,.0f}€")
    print(f"Moyenne : {df[col].mean():+,.0f}€")
    print(f"P(perte nette) : {(df[col] < 0).sum()/len(df)*100:.2f}%")


def report_by_6months(df, label):
    print(f"\n{'='*100}\nPROFIT NET CUMULÉ PAR TRANCHE DE 6 MOIS -- {label}\n{'='*100}")
    for m in MARK_MONTHS:
        col = f"month{m}_net"
        print(f"Mois 0-{m:<3} : moyenne {df[col].mean():+,.0f}€ | médiane {df[col].median():+,.0f}€")


def report_structural(df, label):
    print(f"\n--- Variables structurelles -- {label} ---")
    funded = df.dropna(subset=["first_funded_days"])
    print(f"P(1er financement atteint sur 4 ans) : {len(funded)/len(df)*100:.1f}%")
    if not funded.empty:
        print(f"Délai moyen avant 1er financement : {funded['first_funded_days'].mean():.0f}j "
              f"(médiane {funded['first_funded_days'].median():.0f}j)")
    print(f"Nb de casses moyen (flotte, sur 4 ans) : {df['total_breaks'].mean():.2f} (médiane {df['total_breaks'].median():.0f})")


def main():
    pop = build_population_with_trailing("fixed", 0.2, verbose=False)
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    current_winrate = (pop["statut_final"] == "OBJECTIF ATTEINT").mean()
    avg_win_r = pop.loc[pop["statut_final"] == "OBJECTIF ATTEINT", "r_trailing"].mean()
    breakeven_theoretical = 1 / (1 + avg_win_r) * 100
    print(f"Winrate réel population : {current_winrate*100:.2f}% | RR moyen des gains : {avg_win_r:.3f}")
    print(f"Point de rupture théorique brut (sans frais/casses) : {breakeven_theoretical:.2f}%")

    degrade_rng = random.Random(DEGRADE_SEED)
    sub28, trades28, slots28, actual_wr28 = build_degraded_trades(pop, TARGET_WINRATE, degrade_rng)
    print(f"\nWinrate cible 28% -> réalisé : {actual_wr28*100:.2f}%")

    subref, tradesref, slotsref = build_trades_trailing(pop)

    order28 = list(range(len(trades28)))
    orderref = list(range(len(tradesref)))

    print("\n" + "=" * 100)
    print("1. TAUX DE RENDEMENT MENSUEL INDÉPENDANT DU CAPITAL -- 2% DIRECT")
    print("=" * 100)
    compute_monthly_rate(tradesref, slotsref, market_data, excluded_map, orderref, "RÉFÉRENCE (winrate réel ~37.3%)")
    compute_monthly_rate(trades28, slots28, market_data, excluded_map, order28, "DÉGRADÉ (winrate 28%)")

    block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
    blocks28 = build_blocks(trades28, slots28, block_seconds)
    blocksref = build_blocks(tradesref, slotsref, block_seconds)

    print("\n" + "=" * 100)
    print("LANCEMENT MONTE CARLO (2000 runs, block bootstrap 2 mois, horizon 4 ans, RÉGIME 2% DIRECT)")
    print("=" * 100)
    df_ref = run_monte_carlo(tradesref, slotsref, market_data, excluded_map, blocksref, block_seconds, "reference")
    df_28 = run_monte_carlo(trades28, slots28, market_data, excluded_map, blocks28, block_seconds, "degrade28")

    report_distribution(df_ref, "RÉFÉRENCE (~37.3%) -- 2% direct")
    report_by_6months(df_ref, "RÉFÉRENCE (~37.3%) -- 2% direct")
    report_structural(df_ref, "RÉFÉRENCE (~37.3%) -- 2% direct")

    report_distribution(df_28, "DÉGRADÉ (28%) -- 2% direct")
    report_by_6months(df_28, "DÉGRADÉ (28%) -- 2% direct")
    report_structural(df_28, "DÉGRADÉ (28%) -- 2% direct")

    print("\n" + "=" * 100)
    print("5. MARGE PAR RAPPORT AU POINT DE RUPTURE")
    print("=" * 100)
    print(f"Winrate testé : 28% | Point de rupture théorique brut (ce moteur) : {breakeven_theoretical:.2f}%")
    print(f"P(perte nette) à 28% (2% direct, dual n/a, réserve poolée) : {(df_28['final_net']<0).sum()/len(df_28)*100:.2f}%")


if __name__ == "__main__":
    main()
