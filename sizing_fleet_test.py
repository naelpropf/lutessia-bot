"""
Backtest comparatif Kelly fractionnel (piste #5) et sizing ajusté ATR (piste #6) sur la
FLOTTE COPYTRADE 3 COMPTES (même signal répliqué, chaque compte filtre indépendamment
selon ses propres positions/plafond -- cf. copytrade_simulation_test.py), seuil
rr_tp1 >= 1.5, payoff réaliste + trailing 0.2xSL déjà adopté INCHANGÉ (le trailing ne
s'applique qu'aux 98 trades à continuation confirmée -- r_realiste sert de base ici
exactement comme dans risk_levels_trailing_02_test.py). Pas de pyramiding ici (piste #4,
déjà traitée et rejetée séparément) : chaque trade reste UNE position unique, seul le
RISQUE CIBLE varie selon la méthode de sizing.

Configs comparées :
  - Fixed 0.5% / Fixed 2%  : relues directement dans risk_levels_trailing_02_summary.csv
    (déjà la référence verrouillée du projet, cf. mémoire), pas de recalcul.
  - Kelly 25% / Kelly 50%  : risque cible = fraction x Kelly plein PAR PAIRE (cf.
    sizing_stats.compute_kelly_risk_by_ticker), indépendant de l'ATR.
  - ATR-adjusté            : risque cible = 2.0% x ratio_ATR(paire, instant du trade)
    (cf. sizing_stats.compute_atr_ratio_by_trade).
  - Combiné (Kelly 50% x ATR) : risque cible = Kelly_50%(paire) x ratio_ATR(trade).

Faisabilité (levier 1:30 + plafond 100 lots) appliquée via scaling_simulation.
feasible_risk_pct à CHAQUE trade (une seule unité par trade ici, pas de cumul
inter-unités comme pour le pyramiding).
"""
import random
import statistics

import pandas as pd

from scaling_simulation import (
    TIER_SEQUENCE, CHALLENGE_COST, UPGRADE_COST, CHALLENGE_TARGET_PCT,
    MIN_TRADING_DAYS, BREAK_DD_PCT, RESERVE_SHARE, MAX_POSITIONS, CORR_THRESHOLD,
    feasible_risk_pct, load_market_data,
)
from monte_carlo_simulation import precompute_correlation_pairs, N_SIMULATIONS
from sizing_stats import build_base_population, compute_kelly_risk_by_ticker, compute_atr_ratio_by_trade

N_ACCOUNTS = 3
BASE_RISK_PCT = 2.0  # référence pour l'ajustement ATR seul
BASELINE_PATH = "risk_levels_trailing_02_summary.csv"


def build_trades_sizing(pop, ratio_map):
    sub = pop.sort_values("date_creation").reset_index(drop=True)
    t0 = sub["date_creation"].iloc[0]
    slot_arrivals = [(d - t0).total_seconds() for d in sub["date_creation"]]

    trades = []
    for _, row in sub.iterrows():
        hold_seconds = (row["resolution_time_est"] - row["date_creation"]).total_seconds()
        sl_distance = abs(row["prix_entree"] - row["stop_loss_init"])
        trades.append({
            "ticker": row["ticker"],
            "outcome_r": row["r_trailing"],
            "sl_distance": sl_distance,
            "hold_seconds": hold_seconds,
            "date": row["date_creation"],
            "atr_ratio": ratio_map.get((row["ticker"], row["date_creation"]), 1.0),
        })
    return sub, trades, slot_arrivals


def run_sizing_account(trades, slot_arrivals, risk_pct_fn, market_data, excluded_map, rng, order=None):
    """Copie de monte_carlo_simulation.run_one, avec risk_pct_fn(trade) -> target_risk_pct
    à la place d'un risque fixe ou d'une fonction du seul palier -- une unité par trade
    (pas de pyramiding). Ajoute le tracking du drawdown max % (cf. pyramid_fleet_test.py,
    même métrique)."""
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
    total_trading_pnl = 0.0  # brut, challenge+financé confondus -- diagnostic seulement
    total_funded_pnl = 0.0  # SEUL compteur réel : uniquement le pnl généré en phase financée
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

        target_risk_pct = risk_pct_fn(trade)
        eff_risk, _ = feasible_risk_pct(trade["ticker"], trade["sl_distance"], palier, target_risk_pct, market_data)
        risk_amount = eff_risk / 100 * palier
        pnl = trade["outcome_r"] * risk_amount

        open_positions.append((trade["ticker"], close_time))
        total_trading_pnl += pnl
        cumulative_since_reset += pnl
        peak_since_reset = max(peak_since_reset, cumulative_since_reset)
        trading_days_since_reset.add(int(now // 86400))

        # Le pnl généré PENDANT une tentative de challenge (initiale ou après upgrade)
        # n'est jamais réel -- il sert uniquement à valider (ou faire échouer) la
        # tentative, cf. correction demandée par l'utilisateur : seul le pnl généré une
        # fois le compte FINANCÉ compte comme profit réellement retirable. Un compte qui
        # casse pendant sa phase de challenge ne "perd" donc rien de réel non plus (son
        # pnl de challenge n'a jamais été compté) -- seul le coût de re-tentative
        # (total_fees_paid) est une dépense réelle.
        if phase == "funded":
            total_funded_pnl += pnl
            if pnl > 0:
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

    net_profit = total_funded_pnl - total_fees_paid  # SEUL profit réel (financé net)
    net_profit_raw = total_trading_pnl - total_fees_paid  # diagnostic (ancienne méthode)
    return {
        "net_profit": net_profit, "net_profit_raw": net_profit_raw, "broken_count": broken_count,
        "max_consecutive_breaks": max_consecutive_breaks, "max_dd_pct": max_dd_pct,
    }


def run_copytrade_sizing_one(trades, slot_arrivals, risk_pct_fn, market_data, excluded_map, rng):
    order = list(range(len(trades)))
    rng.shuffle(order)
    account_results = [
        run_sizing_account(trades, slot_arrivals, risk_pct_fn, market_data, excluded_map, rng, order=order)
        for _ in range(N_ACCOUNTS)
    ]
    return {
        "net_profit": sum(r["net_profit"] for r in account_results),
        "net_profit_raw": sum(r["net_profit_raw"] for r in account_results),
        "broken_count": sum(r["broken_count"] for r in account_results),
        "max_consecutive_breaks": max(r["max_consecutive_breaks"] for r in account_results),
        "max_dd_pct": max(r["max_dd_pct"] for r in account_results),
    }


def summarize_sizing(results):
    profits = sorted(r["net_profit"] for r in results)  # profit FINANCÉ net (seul réel)
    n = len(profits)
    raw_profits = sorted(r["net_profit_raw"] for r in results)
    return {
        "mean_profit": statistics.mean(profits),
        "median_profit": statistics.median(profits),
        "p5_profit": profits[int(0.05 * n)],
        "mean_profit_raw": statistics.mean(raw_profits),  # diagnostic : ancienne méthode (challenge+financé)
        "mean_broken_count": statistics.mean(r["broken_count"] for r in results),
        "mean_max_dd_pct": statistics.mean(r["max_dd_pct"] for r in results),
        "worst_max_dd_pct": max(r["max_dd_pct"] for r in results),
    }


def run_config(label, risk_pct_fn, trades, slot_arrivals, excluded_map, market_data, avg_risk_pct_used):
    rng = random.Random(42)
    results = [run_copytrade_sizing_one(trades, slot_arrivals, risk_pct_fn, market_data, excluded_map, rng)
               for _ in range(N_SIMULATIONS)]
    mc = summarize_sizing(results)

    print(f"\n{'='*100}\nCONFIG : {label} (risque moyen appliqué ~{avg_risk_pct_used:.2f}%/trade)\n{'='*100}")
    print(f"Profit FINANCÉ net moyen (seul réel) : {mc['mean_profit']:+,.0f}€ | médian : {mc['median_profit']:+,.0f}€ | "
          f"p5 : {mc['p5_profit']:+,.0f}€")
    print(f"  (pour référence, ancienne méthode challenge+financé confondus : {mc['mean_profit_raw']:+,.0f}€ -- "
          f"écart = pnl de challenge jamais réel, exclu par la correction)")
    print(f"Casses moyennes (flotte) : {mc['mean_broken_count']:.2f}")
    print(f"Drawdown max moyen (pire compte) : {mc['mean_max_dd_pct']:.2f}% | pire observé : {mc['worst_max_dd_pct']:.2f}%")

    return {
        "config": label, "avg_risk_pct_used": avg_risk_pct_used, "mean_profit": mc["mean_profit"],
        "median_profit": mc["median_profit"], "p5_profit": mc["p5_profit"],
        "mean_profit_raw_diagnostic": mc["mean_profit_raw"],
        "mean_broken_count": mc["mean_broken_count"], "mean_max_dd_pct": mc["mean_max_dd_pct"],
        "worst_max_dd_pct": mc["worst_max_dd_pct"],
    }


def main(run_atr_variants=False):
    """Par défaut, ne relance QUE le comparatif demandé (baseline 2% / Kelly 25% /
    Kelly 50%) avec la correction challenge-vs-financé -- passer run_atr_variants=True
    pour aussi rejouer ATR/combiné avec la même correction (pas demandé dans la relance
    en cours, laissés de côté pour rester rapide et ciblé)."""
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)

    pop = build_base_population(verbose=True)
    kelly_25_by_ticker, kelly_25_stats = compute_kelly_risk_by_ticker(pop, 0.25)
    kelly_50_by_ticker, kelly_50_stats = compute_kelly_risk_by_ticker(pop, 0.50)
    atr_ratio_map, atr_stats = compute_atr_ratio_by_trade(pop)
    kelly_25_stats.to_csv("sizing_kelly_25_stats.csv", index=False)
    kelly_50_stats.to_csv("sizing_kelly_50_stats.csv", index=False)
    atr_stats.to_csv("sizing_atr_ratio_detail.csv", index=False)

    sub, trades, slot_arrivals = build_trades_sizing(pop, atr_ratio_map)
    tickers = sorted(set(t["ticker"] for t in trades))
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    rows = []

    # Baseline recalculée à neuf avec la MÊME correction (pas relue depuis l'ancien CSV,
    # qui utilisait l'ancienne méthode challenge+financé confondus -- comparaison
    # autrement faussée, cf. demande explicite de l'utilisateur).
    rows.append(run_config(
        "baseline_fixe_2.0pct", lambda trade: 2.0,
        trades, slot_arrivals, excluded_map, market_data, 2.0,
    ))

    avg_kelly25 = sum(kelly_25_by_ticker[t["ticker"]] for t in trades) / len(trades)
    rows.append(run_config(
        "kelly_25pct", lambda trade: kelly_25_by_ticker[trade["ticker"]],
        trades, slot_arrivals, excluded_map, market_data, avg_kelly25,
    ))

    avg_kelly50 = sum(kelly_50_by_ticker[t["ticker"]] for t in trades) / len(trades)
    rows.append(run_config(
        "kelly_50pct", lambda trade: kelly_50_by_ticker[trade["ticker"]],
        trades, slot_arrivals, excluded_map, market_data, avg_kelly50,
    ))

    if run_atr_variants:
        avg_atr = sum(BASE_RISK_PCT * t["atr_ratio"] for t in trades) / len(trades)
        rows.append(run_config(
            "atr_adjuste_base2pct", lambda trade: BASE_RISK_PCT * trade["atr_ratio"],
            trades, slot_arrivals, excluded_map, market_data, avg_atr,
        ))

        avg_combined = sum(kelly_50_by_ticker[t["ticker"]] * t["atr_ratio"] for t in trades) / len(trades)
        rows.append(run_config(
            "combine_kelly50_x_atr", lambda trade: kelly_50_by_ticker[trade["ticker"]] * trade["atr_ratio"],
            trades, slot_arrivals, excluded_map, market_data, avg_combined,
        ))

    summary_df = pd.DataFrame(rows)
    summary_df.to_csv("sizing_backtest_summary_funded_corrected.csv", index=False)

    print("\n" + "=" * 100)
    print("TABLEAU COMPARATIF FINAL (CORRIGÉ -- profit FINANCÉ net uniquement) -- "
          "baseline 2% vs Kelly 25%/50%")
    print("=" * 100)
    print(summary_df.to_string(index=False))
    print("\nRésumé enregistré dans sizing_backtest_summary_funded_corrected.csv")
    return summary_df


if __name__ == "__main__":
    main()
