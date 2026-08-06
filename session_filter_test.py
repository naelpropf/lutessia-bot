"""
Teste l'effet d'un filtre de session horaire sur la performance globale du bot, avec
la méthodologie déjà validée : seuil d'entrée rr_tp1 >= 1.5, durées réelles de trade
(bougies H1, cf. tp_sequence_analysis.py / rr_threshold_test.py), plafond de 3
positions + corrélation 0.6/JPY (scaling_simulation.py), scaling complet
50k->200k->500k (+8%/-10%, 4 jours de trading min, réserve 80%, contrainte de
faisabilité marge/100 lots), risque de référence 0.5% par trade (RISK_PCT_PER_TRADE,
le risque RÉELLEMENT utilisé en production dans app_mt5.py). Monte Carlo 2000 runs
bootstrap par permutation (cf. monte_carlo_simulation.py) + trajectoire déterministe
chronologique réelle pour l'écart-type mensuel du rendement (cf.
copytrade_risk_levels_test.py, adapté ici à un seul compte).

Point de départ : session_hour_analysis.py a établi (sur les trades PRIS, fuseau UTC
vérifié via le JS source de CentralCharts) une EV(TP2) de +1.694 R en session US
seule (16h-22h UTC, n=132) contre +1.240 R en session asiatique (00h-08h UTC, n=121)
— écart notable sur deux échantillons de taille correcte (>=50). Cette EV(TP2) sert
uniquement à REPÉRER la session à tester ici ; les simulations Monte Carlo et
déterministe ci-dessous utilisent, comme partout ailleurs dans ce dépôt, la
convention de payoff rr_tp1 (scénario "100% TP1" / sortie visée réelle en TP1
convention interne aux simulations existantes) pour rester comparables aux résultats
déjà connus (rr_threshold_summary.csv, seuil 1.5).

3 scénarios comparés sur le MÊME pool brut de 472 trades (rr_tp1 >= 1.5, forex,
terminaux) — seule la règle d'admission/risque de la session asiatique change :
  1. Référence           : aucun filtre horaire, risque uniforme 0.5%
  2. Exclusion stricte    : signaux asiatiques (00h-08h UTC) jamais pris
  3. Exclusion partielle  : signaux asiatiques gardés mais à risque moitié (0.25%)

Le filtre horaire change QUELS trades passent le plafond de 3 positions et la
corrélation (moins de candidats en scénario 2 laisse mécaniquement plus de place aux
autres sessions) -> le plafond/corrélation est réappliqué séparément à chaque
scénario (pas un masque a posteriori sur les trades déjà pris en référence).
"""
import random

import pandas as pd

import rr_threshold_test as rrt
from scaling_simulation import (
    TIER_SEQUENCE, CHALLENGE_COST, UPGRADE_COST, CHALLENGE_TARGET_PCT,
    MIN_TRADING_DAYS, BREAK_DD_PCT, RESERVE_SHARE, MAX_POSITIONS, CORR_THRESHOLD,
    feasible_risk_pct, load_market_data,
)
from monte_carlo_simulation import precompute_correlation_pairs, summarize, N_SIMULATIONS

MIN_RR_TP1 = 1.5
BASE_RISK_PCT = 0.5  # RISK_PCT_PER_TRADE réel (app_mt5.py)
ASIAN_START_H, ASIAN_END_H = 0, 8
SOFT_ASIAN_MULTIPLIER = 0.5


def is_asian(dt):
    return ASIAN_START_H <= dt.hour < ASIAN_END_H


def build_trades_with_multiplier(taken, multiplier_fn):
    taken = taken.sort_values("date_creation").reset_index(drop=True)
    t0 = taken["date_creation"].iloc[0]
    slot_arrivals = [(d - t0).total_seconds() for d in taken["date_creation"]]

    trades = []
    for _, row in taken.iterrows():
        hold_seconds = (row["resolution_time_est"] - row["date_creation"]).total_seconds()
        sl_distance = abs(row["prix_entree"] - row["stop_loss_init"])
        trades.append({
            "ticker": row["ticker"],
            "outcome_r": row["rr_tp1"] if row["statut_final"] == "OBJECTIF ATTEINT" else -1.0,
            "sl_distance": sl_distance,
            "hold_seconds": hold_seconds,
            "risk_multiplier": multiplier_fn(row),
        })
    return trades, slot_arrivals


def run_one_session(trades, slot_arrivals, base_risk_pct, market_data, excluded_map, rng):
    """Copie de monte_carlo_simulation.run_one, étendue pour appliquer
    trade["risk_multiplier"] au risque cible AVANT la contrainte de faisabilité
    (marge/100 lots) -- nécessaire pour le scénario "risque moitié en session
    asiatique", que le run_one d'origine ne permet pas (risk_pct n'y dépend que du
    palier, pas du trade)."""
    order = list(range(len(trades)))
    rng.shuffle(order)

    reserve = 0.0
    palier = TIER_SEQUENCE[0]
    phase = "challenge"
    total_fees_paid = CHALLENGE_COST[palier]
    cumulative_since_reset = 0.0
    peak_since_reset = 0.0
    trading_days_since_reset = set()
    broken_count = 0
    total_trading_pnl = 0.0
    open_positions = []

    consecutive_breaks = 0
    max_consecutive_breaks = 0

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]
        close_time = now + trade["hold_seconds"]

        open_positions = [(t, c) for (t, c) in open_positions if c > now]

        if len(open_positions) >= MAX_POSITIONS:
            continue
        if any(t in excluded_map[trade["ticker"]] for (t, _) in open_positions):
            continue

        target_risk_pct = base_risk_pct * trade["risk_multiplier"]
        effective_risk_pct, _ = feasible_risk_pct(
            trade["ticker"], trade["sl_distance"], palier, target_risk_pct, market_data
        )
        risk_amount = effective_risk_pct / 100 * palier
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
            broken_count += 1
            consecutive_breaks += 1
            max_consecutive_breaks = max(max_consecutive_breaks, consecutive_breaks)
            total_fees_paid += CHALLENGE_COST[palier]
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
            consecutive_breaks = 0

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
    return {
        "net_profit": net_profit,
        "broken_count": broken_count,
        "final_tier": palier,
        "max_consecutive_breaks": max_consecutive_breaks,
        "adaptive_fallback_count": 0,
    }


def run_deterministic_session(taken, base_risk_pct, market_data, start_date):
    """Trajectoire déterministe (chronologie réelle, pas de permutation) sur les
    trades déjà PRIS (taken), pour en tirer l'écart-type mensuel du rendement --
    même logique que scaling_simulation.run_simulation / copytrade_risk_levels_test.py
    run_deterministic_monthly_std, adaptée à un seul compte + multiplicateur de
    risque par trade."""
    taken = taken.sort_values("date_creation").reset_index(drop=True)

    reserve = 0.0
    palier = TIER_SEQUENCE[0]
    phase = "challenge"
    total_fees_paid = CHALLENGE_COST[palier]
    cumulative_since_reset = 0.0
    peak_since_reset = 0.0
    trading_days_since_reset = set()
    broken_count = 0
    total_trading_pnl = 0.0
    monthly_pnl = []

    for _, row in taken.iterrows():
        now = row["date_creation"]
        sl_distance = abs(row["prix_entree"] - row["stop_loss_init"])
        target_risk_pct = base_risk_pct * row["risk_multiplier"]
        effective_risk_pct, _ = feasible_risk_pct(row["ticker"], sl_distance, palier, target_risk_pct, market_data)
        risk_amount = effective_risk_pct / 100 * palier
        outcome_r = row["rr_tp1"] if row["statut_final"] == "OBJECTIF ATTEINT" else -1.0
        pnl = outcome_r * risk_amount

        total_trading_pnl += pnl
        cumulative_since_reset += pnl
        peak_since_reset = max(peak_since_reset, cumulative_since_reset)
        trading_days_since_reset.add(now.date())
        monthly_pnl.append({"date": now, "pnl": pnl, "palier": palier})

        if phase == "funded" and pnl > 0:
            reserve += pnl * RESERVE_SHARE

        drawdown = peak_since_reset - cumulative_since_reset
        if drawdown >= BREAK_DD_PCT / 100 * palier:
            broken_count += 1
            total_fees_paid += CHALLENGE_COST[palier]
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

    net_profit = total_trading_pnl - total_fees_paid

    trades_df = pd.DataFrame(monthly_pnl)
    if trades_df.empty:
        return net_profit, float("nan"), float("nan"), 0

    trades_df["month_index"] = trades_df["date"].apply(
        lambda d: (d.year - start_date.year) * 12 + (d.month - start_date.month)
    )
    n_months = trades_df["month_index"].max() + 1
    palier_by_month = trades_df.groupby("month_index")["palier"].last().reindex(range(n_months)).ffill().bfill()
    monthly_net = trades_df.groupby("month_index")["pnl"].sum().reindex(range(n_months), fill_value=0.0)
    monthly_pct = monthly_net / palier_by_month * 100

    return net_profit, monthly_pct.std(), monthly_pct.mean(), n_months


def run_scenario(name, pop_scenario, multiplier_fn, corr_matrix, market_data, pop_brut_n):
    # Monte Carlo : le pool CANDIDAT complet (pas déjà filtré plafond/corrélation) est
    # passé à run_one_session, qui réapplique le filtre à CHAQUE permutation --
    # exactement la méthodologie de rr_threshold_test.run_mc_for_threshold. Pré-filtrer
    # ici avec taken_trades() appliquerait le plafond/corrélation deux fois de suite
    # et sous-estimerait fortement le volume de trades réellement exécutés.
    pop_scenario = pop_scenario.copy()
    pop_scenario["risk_multiplier"] = pop_scenario.apply(multiplier_fn, axis=1)
    trades, slot_arrivals = build_trades_with_multiplier(pop_scenario, lambda row: row["risk_multiplier"])
    tickers = sorted(set(t["ticker"] for t in trades))
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    rng = random.Random(42)
    mc_results = [run_one_session(trades, slot_arrivals, BASE_RISK_PCT, market_data, excluded_map, rng)
                  for _ in range(N_SIMULATIONS)]
    mc = summarize(mc_results)

    # Trajectoire déterministe : UNE seule passe chronologique réelle (pas de
    # permutation) -> le plafond/corrélation est appliqué une fois via taken_trades().
    taken = rrt.taken_trades(pop_scenario, corr_matrix).copy()
    start_date = taken["date_creation"].iloc[0]
    net_det, monthly_std, monthly_mean, n_months = run_deterministic_session(
        taken, BASE_RISK_PCT, market_data, start_date
    )

    n_asian_taken = int((taken["date_creation"].apply(is_asian)).sum())

    print("=" * 100)
    print(f"SCÉNARIO : {name}")
    print("=" * 100)
    print(f"Trades pris (après plafond 3 positions + corrélation 0.6/JPY) : {len(taken)} / {pop_brut_n} candidats "
          f"({len(taken)/pop_brut_n*100:.1f}%) — dont {n_asian_taken} en session asiatique")
    print(f"Profit net moyen (MC, {N_SIMULATIONS} runs) : {mc['mean_profit']:+,.0f}€")
    print(f"Profit net médian                            : {mc['median_profit']:+,.0f}€")
    print(f"5e percentile                                 : {mc['p5_profit']:+,.0f}€")
    print(f"P(perte nette)                                : {mc['pct_loss']:.1f}%")
    print(f"Nombre moyen de casses                        : {mc['mean_broken_count']:.2f}")
    print(f"Écart-type mensuel du rendement (trajectoire déterministe, {n_months} mois) : {monthly_std:.2f}%")
    print(f"Rendement mensuel moyen (déterministe)        : {monthly_mean:+.2f}%")
    print(f"Profit net (trajectoire déterministe, réf.)   : {net_det:+,.0f}€")
    print()

    return {
        "scenario": name, "n_taken": len(taken), "n_brut": pop_brut_n,
        "pct_captured": len(taken) / pop_brut_n * 100, "n_asian_taken": n_asian_taken,
        **mc, "monthly_std_pct": monthly_std, "monthly_mean_pct": monthly_mean,
        "n_months": n_months, "net_profit_deterministic": net_det,
    }


def main():
    pop_full, median_duration = rrt.build_extended_population(min_rr=MIN_RR_TP1)
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)

    pop = pop_full[pop_full["rr_tp1"] >= MIN_RR_TP1].copy()
    pop_brut_n = len(pop)
    n_asian_brut = int(pop["date_creation"].apply(is_asian).sum())
    print(f"Population brute (rr_tp1 >= {MIN_RR_TP1}, forex, terminaux) : {pop_brut_n} trades, "
          f"dont {n_asian_brut} en session asiatique (00h-08h UTC, {n_asian_brut/pop_brut_n*100:.1f}%)\n")

    rows = []

    rows.append(run_scenario(
        "1. Référence (aucun filtre horaire)", pop,
        lambda row: 1.0, corr_matrix, market_data, pop_brut_n,
    ))

    pop_strict = pop[~pop["date_creation"].apply(is_asian)].copy()
    rows.append(run_scenario(
        "2. Exclusion stricte session asiatique", pop_strict,
        lambda row: 1.0, corr_matrix, market_data, pop_brut_n,
    ))

    rows.append(run_scenario(
        "3. Exclusion partielle (risque moitié en session asiatique)", pop,
        lambda row: SOFT_ASIAN_MULTIPLIER if is_asian(row["date_creation"]) else 1.0,
        corr_matrix, market_data, pop_brut_n,
    ))

    summary_df = pd.DataFrame(rows)
    summary_df.to_csv("session_filter_summary.csv", index=False)

    print("=" * 100)
    print("TABLEAU COMPARATIF")
    print("=" * 100)
    cols = ["scenario", "n_taken", "pct_captured", "mean_profit", "median_profit",
            "p5_profit", "mean_broken_count", "monthly_std_pct"]
    print(summary_df[cols].to_string(index=False))
    print("\nRésumé enregistré dans session_filter_summary.csv")
    return summary_df


if __name__ == "__main__":
    main()
