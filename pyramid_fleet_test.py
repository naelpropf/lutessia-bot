"""
Backtest comparatif du pyramiding (piste #4) sur la FLOTTE COPYTRADE 3 COMPTES (même
signal répliqué sur 3 firms distinctes, chaque compte filtre indépendamment selon ses
propres positions/plafond -- cf. copytrade_simulation_test.py), au risque de référence
verrouillé 2%/compte, seuil rr_tp1 >= 1.5, sur la base payoff réaliste + trailing 0.2xSL
déjà adopté (cf. pyramid_engine.py / pyramid_payoff_population.py pour le détail du
pyramidage lui-même).

Structures comparées (STRUCTURES dans pyramid_payoff_population.py) :
  A_paliers_fixes : ajouts de 100% de l'unité initiale à +0.5R et +1R
  B_degressif     : ajouts de 50% puis 25% de l'unité initiale à +0.5R et +1R

Baseline "sans pyramiding" : relit directement copytrade_vs_fleet_trailing_02_summary.csv
(ligne structure == "copytrade"), pas de recalcul -- déjà la référence verrouillée
(~10.34M€ moyen, ~41.4 casses, cf. mémoire du projet).

Faisabilité (marge levier 1:30 + plafond broker 100 lots) appliquée de façon CUMULATIVE
sur tout le paquet (initial + ajouts) via feasible_volume_incremental -- pas unité par
unité indépendamment (erreur #6 du contexte : la marge/le plafond sont partagés par tout
le paquet, puisque c'est la MÊME position sur le MÊME symbole/compte).
"""
import random
import statistics

import pandas as pd

from scaling_simulation import (
    TIER_SEQUENCE, CHALLENGE_COST, UPGRADE_COST, CHALLENGE_TARGET_PCT,
    MIN_TRADING_DAYS, BREAK_DD_PCT, RESERVE_SHARE, MAX_POSITIONS, CORR_THRESHOLD,
    load_market_data,
)
from monte_carlo_simulation import precompute_correlation_pairs, N_SIMULATIONS
from pyramid_payoff_population import (
    STRUCTURES, build_population_with_pyramid, build_trades_pyramid, pct_reaching_first_level,
)

N_ACCOUNTS = 3
RISK_PCT = 2.0  # régime final verrouillé
BASELINE_PATH = "copytrade_vs_fleet_trailing_02_summary.csv"


def feasible_volume_incremental(ticker, sl_distance, palier, target_risk_pct, market_data, existing_volume):
    """Variante CUMULATIVE de scaling_simulation.feasible_risk_pct : tient compte du
    volume DÉJÀ engagé par les unités précédentes du MÊME trade (même symbole, même
    compte) -- la marge disponible et le plafond broker (100 lots) sont partagés par
    TOUT le paquet, pas réappliqués unité par unité indépendamment. Jamais d'annulation
    (même philosophie que feasible_risk_pct) : au moins volume_min est ouvert, borné par
    volume_max ABSOLU. Retourne (volume_de_cette_unite, realized_risk_pct, was_reduced)."""
    m = market_data[ticker]
    if sl_distance <= 0:
        return 0.0, 0.0, False
    loss_per_lot = (sl_distance / m["tick_size"]) * m["tick_value"]
    if loss_per_lot <= 0:
        return 0.0, 0.0, False

    raw_volume = (target_risk_pct / 100 * palier) / loss_per_lot
    # capacité totale du palier en lots (marge), même formule que feasible_risk_pct --
    # la part déjà consommée par les unités précédentes du même trade en est déduite.
    max_volume_margin_total = palier / m["margin_per_lot"] if m["margin_per_lot"] > 0 else raw_volume + existing_volume
    remaining_margin_volume = max(0.0, max_volume_margin_total - existing_volume)
    remaining_lot_cap = max(0.0, m["volume_max"] - existing_volume)
    capped_volume = min(raw_volume, remaining_lot_cap, remaining_margin_volume)

    step = m["volume_step"]
    final_volume = max(m["volume_min"], min(m["volume_max"], round(capped_volume / step) * step))
    realized_risk_pct = (final_volume * loss_per_lot) / palier * 100
    was_reduced = capped_volume < raw_volume - step / 2
    return final_volume, realized_risk_pct, was_reduced


def compute_trade_pnl(units, ticker, sl_distance, palier, target_risk_pct, market_data):
    """Pnl total du trade (somme des unités), avec faisabilité cumulative sur tout le
    paquet. Réutilise la MÊME distance de risque ORIGINALE pour dimensionner CHAQUE
    unité (convention Turtle : même "N" pour tout le paquet) -- le exit_r de chaque
    unité a déjà été calculé par pyramid_engine par rapport à SA PROPRE entrée."""
    existing_volume = 0.0
    total_pnl = 0.0
    any_reduced = False
    for u in units:
        volume, realized_risk_pct, was_reduced = feasible_volume_incremental(
            ticker, sl_distance, palier, u["fraction"] * target_risk_pct, market_data, existing_volume
        )
        existing_volume += volume
        any_reduced = any_reduced or was_reduced
        risk_amount = realized_risk_pct / 100 * palier
        total_pnl += risk_amount * u["exit_r"]
    return total_pnl, any_reduced


def run_pyramid_account(trades, slot_arrivals, risk_pct, market_data, excluded_map, rng, order=None):
    """Copie de monte_carlo_simulation.run_one adaptée aux trades multi-unités
    (pyramiding), avec compute_trade_pnl à la place de risk_amount * outcome_r. Ajoute
    le tracking d'un drawdown max % (jamais exposé par le moteur existant) -- maximum de
    (peak_since_reset - cumulative_since_reset) / palier * 100 à CHAQUE étape, pas
    seulement au moment d'une casse."""
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
    broken_count = 0
    total_trading_pnl = 0.0
    open_positions = []
    consecutive_breaks = 0
    max_consecutive_breaks = 0
    max_dd_pct = 0.0

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]
        close_time = now + trade["hold_seconds"]

        open_positions = [(t, c) for (t, c) in open_positions if c > now]
        if len(open_positions) >= MAX_POSITIONS:
            continue
        if any(t in excluded_map[trade["ticker"]] for (t, _) in open_positions):
            continue

        pnl, _ = compute_trade_pnl(trade["units"], trade["ticker"], trade["sl_distance"], palier, risk_pct, market_data)

        open_positions.append((trade["ticker"], close_time))
        total_trading_pnl += pnl
        cumulative_since_reset += pnl
        peak_since_reset = max(peak_since_reset, cumulative_since_reset)
        trading_days_since_reset.add(int(now // 86400))

        if phase == "funded" and pnl > 0:
            reserve += pnl * RESERVE_SHARE

        drawdown = peak_since_reset - cumulative_since_reset
        max_dd_pct = max(max_dd_pct, drawdown / palier * 100)

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

        if (phase == "challenge" and cumulative_since_reset >= CHALLENGE_TARGET_PCT / 100 * palier
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
        "net_profit": net_profit, "broken_count": broken_count,
        "max_consecutive_breaks": max_consecutive_breaks, "max_dd_pct": max_dd_pct,
        "final_tier": palier,
    }


def run_copytrade_pyramid_one(trades, slot_arrivals, risk_pct, market_data, excluded_map, rng):
    """Un run Monte Carlo : UNE permutation, appliquée identiquement aux 3 comptes
    indépendants (même signal répliqué) -- même principe que
    copytrade_simulation_test.run_copytrade_one."""
    order = list(range(len(trades)))
    rng.shuffle(order)
    account_results = [
        run_pyramid_account(trades, slot_arrivals, risk_pct, market_data, excluded_map, rng, order=order)
        for _ in range(N_ACCOUNTS)
    ]
    return {
        "net_profit": sum(r["net_profit"] for r in account_results),
        "broken_count": sum(r["broken_count"] for r in account_results),
        "max_consecutive_breaks": max(r["max_consecutive_breaks"] for r in account_results),
        "max_dd_pct": max(r["max_dd_pct"] for r in account_results),
    }


def summarize_pyramid(results):
    profits = sorted(r["net_profit"] for r in results)
    n = len(profits)
    return {
        "mean_profit": statistics.mean(profits),
        "median_profit": statistics.median(profits),
        "p5_profit": profits[int(0.05 * n)],
        "worst_profit": profits[0],
        "best_profit": profits[-1],
        "mean_broken_count": statistics.mean(r["broken_count"] for r in results),
        "mean_max_dd_pct": statistics.mean(r["max_dd_pct"] for r in results),
        "worst_max_dd_pct": max(r["max_dd_pct"] for r in results),
    }


def run_structure(label, add_levels, add_fractions, corr_matrix, market_data):
    pop, _ = build_population_with_pyramid(add_levels, add_fractions, verbose=True)
    pct_first_level = pct_reaching_first_level(pop)
    sub, trades, slot_arrivals = build_trades_pyramid(pop)
    tickers = sorted(set(t["ticker"] for t in trades))
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    rng = random.Random(42)
    results = [run_copytrade_pyramid_one(trades, slot_arrivals, RISK_PCT, market_data, excluded_map, rng)
               for _ in range(N_SIMULATIONS)]
    mc = summarize_pyramid(results)

    print(f"\n{'='*100}\nSTRUCTURE : {label}\n{'='*100}")
    print(f"% population atteignant le 1er palier (+{add_levels[0]}R) : {pct_first_level:.1f}%")
    print(f"Profit net moyen : {mc['mean_profit']:+,.0f}€ | médian : {mc['median_profit']:+,.0f}€ | "
          f"p5 : {mc['p5_profit']:+,.0f}€")
    print(f"Casses moyennes (flotte) : {mc['mean_broken_count']:.2f}")
    print(f"Drawdown max moyen (pire compte) : {mc['mean_max_dd_pct']:.2f}% | pire observé : {mc['worst_max_dd_pct']:.2f}%")

    return {
        "structure": label, "mean_profit": mc["mean_profit"], "median_profit": mc["median_profit"],
        "p5_profit": mc["p5_profit"], "mean_broken_count": mc["mean_broken_count"],
        "mean_max_dd_pct": mc["mean_max_dd_pct"], "worst_max_dd_pct": mc["worst_max_dd_pct"],
        "pct_reaching_first_level": pct_first_level,
    }


def main():
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)

    rows = []
    try:
        baseline_df = pd.read_csv(BASELINE_PATH)
        baseline = baseline_df[baseline_df["structure"] == "copytrade"].iloc[0]
        rows.append({
            "structure": "baseline_sans_pyramiding", "mean_profit": baseline["mean_profit"],
            "median_profit": baseline["median_profit"], "p5_profit": baseline["p5_profit"],
            "mean_broken_count": baseline["mean_broken_count"], "mean_max_dd_pct": float("nan"),
            "worst_max_dd_pct": float("nan"), "pct_reaching_first_level": float("nan"),
        })
    except (FileNotFoundError, IndexError):
        print(f"[AVERTISSEMENT] Baseline {BASELINE_PATH} introuvable -- pas de comparaison directe possible.")

    for label, (levels, fractions) in STRUCTURES.items():
        rows.append(run_structure(label, levels, fractions, corr_matrix, market_data))

    summary_df = pd.DataFrame(rows)
    summary_df.to_csv("pyramid_backtest_summary.csv", index=False)

    print("\n" + "=" * 100)
    print("TABLEAU COMPARATIF FINAL -- baseline vs pyramiding (structures A/B)")
    print("=" * 100)
    print(summary_df.to_string(index=False))
    print("\nRésumé enregistré dans pyramid_backtest_summary.csv")
    return summary_df


if __name__ == "__main__":
    main()
