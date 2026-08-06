"""
Règle de risque ADAPTATIF basée sur le winrate live observé en continu, comparée au
palier fixe 2% déjà simulé (winrate_sensitivity_test.py), sur les mêmes 5 pools de
winrate dégradé (35/30/25/20/15%, même construction/seed -- réutilise
winrate_sensitivity_test.build_degraded_trades telle quelle).

Règle testée : winrate glissant calculé en CONTINU (recalculé à CHAQUE trade pris par
CE compte, pas seulement tous les N trades) sur les N derniers trades PRIS PAR CE
COMPTE (pas le flux brut de signaux -- un trade non pris à cause du plafond/corrélation
n'entre pas dans la fenêtre, cohérent avec ce que le trader observerait réellement).
Paliers (RISK_TIERS) :
    winrate < 25%        -> 0.5%
    25% <= winrate < 30%  -> 1.0%
    30% <= winrate < 35%  -> 1.5%
    winrate >= 35%        -> 2.0%
Avant que la fenêtre de N trades soit remplie (démarrage), repli sur le palier le plus
bas (0.5%, cohérent avec la Phase 1 de validation déjà en place). Testé pour N=10/20/30.

Le winrate est recalculé PAR COMPTE (pas au niveau flotte) : en copytrade, les 3 comptes
répliquent le même signal mais chacun filtre indépendamment selon SES PROPRES positions
ouvertes (déjà le principe de copytrade_simulation_test.py) -- le sous-ensemble de
trades réellement pris peut donc diverger d'un compte à l'autre, et c'est cette
observation PROPRE À CHAQUE COMPTE qui pilote son risque adaptatif.

Contrainte de trésorerie réelle : tout coût de rachat de challenge NON couvert par la
réserve commune devient de la "dette personnelle" (personal_cash_debt) -- argent
réellement sorti de la poche du trader. Cette dette est REMBOURSÉE EN PRIORITÉ par les
contributions futures à la réserve (80% des gains en phase financée), avant que ces
contributions puissent à nouveau servir à payer un rachat/upgrade. Si personal_cash_debt
atteint CASH_DEBT_LIMIT (3000€ par défaut) AVANT un nouveau rachat de challenge, le
compte s'ARRÊTE DÉFINITIVEMENT (plus aucun trade, plus aucune tentative) -- pas de
rachat infini même en théorie, cohérent avec la contrainte demandée.
"""
import random
import statistics
from collections import deque

import pandas as pd

from scaling_simulation import (
    TIER_SEQUENCE, CHALLENGE_COST, UPGRADE_COST, CHALLENGE_TARGET_PCT,
    MIN_TRADING_DAYS, BREAK_DD_PCT, RESERVE_SHARE, MAX_POSITIONS, CORR_THRESHOLD,
    feasible_risk_pct, load_market_data,
)
from monte_carlo_simulation import precompute_correlation_pairs, N_SIMULATIONS
from trailing_payoff_population import build_population_with_trailing
from winrate_sensitivity_test import build_degraded_trades, TARGET_WINRATES as _ALL_TARGETS, DEGRADE_SEED

N_ACCOUNTS = 3
CASH_DEBT_LIMIT = 3000.0
WINDOW_SIZES = [10, 20, 30]
TEST_WINRATES = [0.35, 0.30, 0.25, 0.20, 0.15]  # sous-ensemble demandé (pas 13/10%)

# (seuil_winrate_exclusif_haut, risque_pct) -- premier seuil que wr ne dépasse pas gagne.
RISK_TIERS = [(0.25, 0.5), (0.30, 1.0), (0.35, 1.5), (float("inf"), 2.0)]
COLD_START_RISK_PCT = RISK_TIERS[0][1]  # 0.5%, tant que la fenêtre n'est pas remplie


def risk_for_winrate(wr):
    for threshold, risk in RISK_TIERS:
        if wr < threshold:
            return risk
    return RISK_TIERS[-1][1]


def run_adaptive_account(trades, slot_arrivals, window_n, market_data, excluded_map, rng, order=None,
                          cash_debt_limit=CASH_DEBT_LIMIT):
    if order is None:
        order = list(range(len(trades)))
        rng.shuffle(order)

    reserve = 0.0
    personal_cash_debt = 0.0
    palier = TIER_SEQUENCE[0]
    phase = "challenge"
    total_fees_paid = CHALLENGE_COST[palier]
    cumulative_since_reset = 0.0
    peak_since_reset = 0.0
    trading_days_since_reset = set()
    broken_count = 0
    total_trading_pnl = 0.0
    open_positions = []
    outcome_window = deque(maxlen=window_n)
    retired = False
    n_taken = 0

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]
        close_time = now + trade["hold_seconds"]

        open_positions = [(t, c) for (t, c) in open_positions if c > now]
        if len(open_positions) >= MAX_POSITIONS:
            continue
        if any(t in excluded_map[trade["ticker"]] for (t, _) in open_positions):
            continue

        n_taken += 1
        target_risk_pct = (risk_for_winrate(sum(outcome_window) / window_n)
                            if len(outcome_window) == window_n else COLD_START_RISK_PCT)
        outcome_window.append(1 if trade["outcome_r"] > 0 else 0)

        eff_risk, _ = feasible_risk_pct(trade["ticker"], trade["sl_distance"], palier, target_risk_pct, market_data)
        risk_amount = eff_risk / 100 * palier
        pnl = trade["outcome_r"] * risk_amount

        open_positions.append((trade["ticker"], close_time))
        total_trading_pnl += pnl
        cumulative_since_reset += pnl
        peak_since_reset = max(peak_since_reset, cumulative_since_reset)
        trading_days_since_reset.add(int(now // 86400))

        if phase == "funded" and pnl > 0:
            contribution = pnl * RESERVE_SHARE
            if personal_cash_debt > 0:
                reimbursed = min(personal_cash_debt, contribution)
                personal_cash_debt -= reimbursed
                contribution -= reimbursed
            reserve += contribution

        drawdown = peak_since_reset - cumulative_since_reset
        if drawdown >= BREAK_DD_PCT / 100 * palier:
            broken_count += 1
            if personal_cash_debt >= cash_debt_limit:
                retired = True
                break  # plus de rachat possible : le compte s'arrête définitivement ici
            cost = CHALLENGE_COST[palier]
            if reserve >= cost:
                reserve -= cost
            else:
                personal_cash_debt += cost - reserve
                reserve = 0.0
            total_fees_paid += cost
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
                if reserve >= cost:  # upgrade TOUJOURS gaté par la réserve, jamais de dette personnelle ici
                    reserve -= cost
                    total_fees_paid += cost
                    palier = next_tier
                    phase = "challenge"
                    cumulative_since_reset = 0.0
                    peak_since_reset = 0.0
                    trading_days_since_reset = set()

    net_profit = total_trading_pnl - total_fees_paid
    return {
        "net_profit": net_profit, "broken_count": broken_count, "retired": retired,
        "personal_cash_debt_final": personal_cash_debt, "n_taken": n_taken,
    }


def run_copytrade_adaptive_one(trades, slot_arrivals, window_n, market_data, excluded_map, rng):
    order = list(range(len(trades)))
    rng.shuffle(order)
    account_results = [
        run_adaptive_account(trades, slot_arrivals, window_n, market_data, excluded_map, rng, order=order)
        for _ in range(N_ACCOUNTS)
    ]
    return {
        "net_profit": sum(r["net_profit"] for r in account_results),
        "broken_count": sum(r["broken_count"] for r in account_results),
        "retired_count": sum(1 for r in account_results if r["retired"]),
    }


def summarize(results):
    profits = sorted(r["net_profit"] for r in results)
    n = len(profits)
    return {
        "mean_profit": statistics.mean(profits),
        "median_profit": statistics.median(profits),
        "p5_profit": profits[int(0.05 * n)],
        "pct_loss": sum(1 for p in profits if p < 0) / n * 100,
        "mean_broken_count": statistics.mean(r["broken_count"] for r in results),
        "mean_retired_count": statistics.mean(r["retired_count"] for r in results),
        "pct_runs_any_retired": sum(1 for r in results if r["retired_count"] > 0) / n * 100,
    }


def main():
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    pop = build_population_with_trailing("fixed", 0.2, verbose=False)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    try:
        fixed_df = pd.read_csv("winrate_sensitivity_summary.csv")
    except FileNotFoundError:
        fixed_df = None

    rows = []
    for target in TEST_WINRATES:
        degrade_rng = random.Random(DEGRADE_SEED)
        sub, trades, slot_arrivals, actual_winrate = build_degraded_trades(pop, target, degrade_rng)

        fixed_row = None
        if fixed_df is not None:
            match = fixed_df[fixed_df["target_winrate_pct"] == target * 100]
            if not match.empty:
                fixed_row = match.iloc[0]

        print(f"\n{'#'*100}\nWINRATE CIBLE {target*100:.0f}% (réalisé : {actual_winrate*100:.2f}%)\n{'#'*100}")
        if fixed_row is not None:
            print(f"[Référence risque FIXE 2%, déjà calculé] profit moyen {fixed_row['mean_profit']:+,.0f}€ | "
                  f"P(perte) {fixed_row['pct_loss']:.1f}% | casses {fixed_row['mean_broken_count']:.2f}")

        for window_n in WINDOW_SIZES:
            mc_rng = random.Random(42)
            results = [run_copytrade_adaptive_one(trades, slot_arrivals, window_n, market_data, excluded_map, mc_rng)
                       for _ in range(N_SIMULATIONS)]
            s = summarize(results)

            print(f"\n--- Adaptatif, fenêtre N={window_n} ---")
            print(f"Profit net moyen : {s['mean_profit']:+,.0f}€ | médian : {s['median_profit']:+,.0f}€ | "
                  f"p5 : {s['p5_profit']:+,.0f}€")
            print(f"P(perte nette) : {s['pct_loss']:.1f}%")
            print(f"Casses moyennes (flotte) : {s['mean_broken_count']:.2f}")
            print(f"Comptes retraités (dette > {CASH_DEBT_LIMIT:.0f}€) : {s['mean_retired_count']:.3f} en moyenne "
                  f"| {s['pct_runs_any_retired']:.1f}% des runs ont au moins 1 compte retraité")

            rows.append({
                "target_winrate_pct": target * 100, "actual_winrate_pct": actual_winrate * 100,
                "window_n": window_n, "mean_profit": s["mean_profit"], "median_profit": s["median_profit"],
                "p5_profit": s["p5_profit"], "pct_loss": s["pct_loss"],
                "mean_broken_count": s["mean_broken_count"], "mean_retired_count": s["mean_retired_count"],
                "pct_runs_any_retired": s["pct_runs_any_retired"],
                "fixed2pct_mean_profit": fixed_row["mean_profit"] if fixed_row is not None else float("nan"),
                "fixed2pct_pct_loss": fixed_row["pct_loss"] if fixed_row is not None else float("nan"),
                "fixed2pct_mean_broken_count": fixed_row["mean_broken_count"] if fixed_row is not None else float("nan"),
            })

    summary_df = pd.DataFrame(rows)
    summary_df.to_csv("adaptive_risk_summary.csv", index=False)

    print("\n" + "=" * 100)
    print("TABLEAU COMPARATIF FINAL -- risque adaptatif (par fenêtre N) vs risque fixe 2% déjà calculé")
    print("=" * 100)
    cols = ["target_winrate_pct", "window_n", "mean_profit", "pct_loss", "mean_broken_count",
            "pct_runs_any_retired", "fixed2pct_mean_profit", "fixed2pct_pct_loss", "fixed2pct_mean_broken_count"]
    print(summary_df[cols].to_string(index=False))
    print("\nRésumé enregistré dans adaptive_risk_summary.csv")
    return summary_df


if __name__ == "__main__":
    main()
