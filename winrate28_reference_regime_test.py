"""
Scénario dégradé winrate=28% (même méthode que winrate_sensitivity_test.py :
distribution des RR des gains INCHANGÉE, seule la proportion gagnants/perdants est
altérée par tirage aléatoire, DEGRADE_SEED=123 pour cohérence avec les niveaux
35/30/25/20/15/13/10% déjà testés), sur les PARAMÈTRES DE RÉFÉRENCE explicitement
redonnés par l'utilisateur :
  - copytrade 3 comptes/3 firms, résultat FLOTTE COMBINÉE
  - régime hybride : 0.5% jusqu'à réserve COMMUNE POOLÉE >= 5000€ ET les 3 comptes
    au palier >= 200k (double condition, pas juste la réserve), puis 2% irréversible
  - seuil rr_tp1>=1.5, payoff réaliste + trailing 0.2xSL
  - plafond 3 positions/compte, corrélation 0.6+JPY
  - scaling 50k->200k->500k, financé +8%/4j min, réserve 80% (poolée)
  - faisabilité marge (1:30) + plafond 100 lots

Réutilise le moteur "réserve poolée" établi cette nuit (bad_year1_recovery_pooled_reserve.py
/ three_regime_cash_comparison.py) mais ajoute la 2e condition de bascule (palier>=200k
sur les 3 comptes) qui n'y était pas encore implémentée, et calcule en plus : temps du
1er financement, nb de casses, snapshots tous les 6 mois sur 4 ans.

Tourne le MÊME moteur sur le winrate RÉEL (~37.3%, r_trailing tel quel) en parallèle,
pour une comparaison directe point par point (partie 4 de la demande).
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
RESERVE_SWITCH_THRESHOLD = 5000.0
SWITCH_TIER_MIN = 200000
LOW_RISK = 0.5
HIGH_RISK = 2.0
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
    switched = False
    switch_time = None
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

            if not switched and reserve >= RESERVE_SWITCH_THRESHOLD and all(a["palier"] >= SWITCH_TIER_MIN for a in accounts):
                switched = True
                switch_time = now

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
    return snapshots, final_net, switch_time, first_funded_time, total_breaks


def compute_monthly_rate(trades, slot_arrivals, market_data, excluded_map, order, winrate_label):
    """Partie 1 : taux de rendement mensuel indépendant du capital = EV_captée x
    risque x fréquence de trades captés/mois, calculé sur la chronologie réelle
    (pas de bootstrap), pour UN compte représentatif (filtre plafond/corrélation
    identique aux 3 comptes, ils sont interchangeables tant qu'aucune divergence de
    palier n'entre en jeu ici -- ce calcul ignore le palier, en % pur)."""
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
    print(f"EV captée (moyenne outcome_r sur les trades captés) : {ev_captee:+.4f}R")
    for risk_label, risk_pct in [("phase 0.5%", LOW_RISK), ("phase 2%", HIGH_RISK)]:
        monthly_rate = ev_captee * (risk_pct / 100) * freq_per_month * 100
        print(f"  Taux mensuel ({risk_label}) = EV_captée x risque x fréquence = "
              f"{ev_captee:+.4f} x {risk_pct}% x {freq_per_month:.2f} = {monthly_rate:+.3f}%/mois")
    return ev_captee, freq_per_month


def run_monte_carlo(trades, slot_arrivals, market_data, excluded_map, blocks, block_seconds, label):
    mark_seconds_list = [m / 12 * YEAR_SECONDS for m in MARK_MONTHS]
    target_duration = max(MARK_MONTHS) / 12 * YEAR_SECONDS

    rng = random.Random(42)
    rows = []
    for _ in range(N_SIMULATIONS):
        synthetic_trades, synthetic_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, target_duration)
        order = list(range(len(synthetic_trades)))
        snaps, final_net, switch_time, first_funded_time, total_breaks = run_fleet_multi_mark(
            synthetic_trades, synthetic_slots, market_data, excluded_map, order, mark_seconds_list
        )
        row = {f"month{m}_net": snaps[i][1] for i, m in enumerate(MARK_MONTHS)}
        row.update({
            "final_net": final_net,
            "switch_time_days": switch_time / 86400 if switch_time is not None else None,
            "first_funded_days": first_funded_time / 86400 if first_funded_time is not None else None,
            "total_breaks": total_breaks,
        })
        rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(f"winrate28_{label}_detail.csv", index=False)
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
    switched = df.dropna(subset=["switch_time_days"])
    funded = df.dropna(subset=["first_funded_days"])
    print(f"P(bascule atteinte sur 4 ans) : {len(switched)/len(df)*100:.1f}%")
    if not switched.empty:
        print(f"Délai moyen de bascule (réserve>=5000€ ET 3 comptes>=200k) : {switched['switch_time_days'].mean():.0f}j "
              f"(médiane {switched['switch_time_days'].median():.0f}j)")
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

    # === 1. Taux de rendement mensuel ===
    print("\n" + "=" * 100)
    print("1. TAUX DE RENDEMENT MENSUEL INDÉPENDANT DU CAPITAL")
    print("=" * 100)
    compute_monthly_rate(tradesref, slotsref, market_data, excluded_map, orderref, "RÉFÉRENCE (winrate réel ~37.3%)")
    compute_monthly_rate(trades28, slots28, market_data, excluded_map, order28, "DÉGRADÉ (winrate 28%)")

    # === 2-4. Monte Carlo complet + 6 mois + structurel, pour les 2 scénarios ===
    block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
    blocks28 = build_blocks(trades28, slots28, block_seconds)
    blocksref = build_blocks(tradesref, slotsref, block_seconds)

    print("\n" + "=" * 100)
    print("LANCEMENT MONTE CARLO (2000 runs, block bootstrap 2 mois, horizon 4 ans) -- RÉFÉRENCE puis DÉGRADÉ 28%")
    print("=" * 100)
    df_ref = run_monte_carlo(tradesref, slotsref, market_data, excluded_map, blocksref, block_seconds, "reference")
    df_28 = run_monte_carlo(trades28, slots28, market_data, excluded_map, blocks28, block_seconds, "degrade28")

    report_distribution(df_ref, "RÉFÉRENCE (~37.3%)")
    report_by_6months(df_ref, "RÉFÉRENCE (~37.3%)")
    report_structural(df_ref, "RÉFÉRENCE (~37.3%)")

    report_distribution(df_28, "DÉGRADÉ (28%)")
    report_by_6months(df_28, "DÉGRADÉ (28%)")
    report_structural(df_28, "DÉGRADÉ (28%)")

    print("\n" + "=" * 100)
    print("5. MARGE PAR RAPPORT AU POINT DE RUPTURE")
    print("=" * 100)
    print(f"Winrate testé : 28% | Point de rupture empirique connu (winrate_sensitivity_test.py, ancien moteur) : ~20.5%")
    print(f"Marge brute : {28 - 20.5:.1f} points")
    print(f"P(perte nette) à 28% sur ce moteur (dual-gate, réserve poolée) : {(df_28['final_net']<0).sum()/len(df_28)*100:.2f}%")


if __name__ == "__main__":
    main()
