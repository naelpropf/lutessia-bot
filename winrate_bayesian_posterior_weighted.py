"""
Monte Carlo Phase 1 (0.5%->2% hybride vs 2% direct) où le winrate n'est PAS fixé à un
point (37.29%/32%/28%) mais TIRÉ, à CHAQUE run, dans la distribution postérieure
bayésienne complète Beta(172.66, 305.36) établie précédemment (prior calibré sur les
472 trades historiques, mis à jour avec 15 pertes consécutives). Pondère ainsi
automatiquement chaque scénario de winrate par sa vraie probabilité, au lieu de traiter
37/32/28% comme 3 points isolés à poids égal.

Par run : (1) tirage winrate ~ Beta(172.66, 305.36) ; (2) dégradation de la population
à ce winrate précis (retourne aléatoirement des gagnants en perdants, comme
winrate_sensitivity_test.py, mais avec un tirage ET une sélection de trades à retourner
DIFFÉRENTS à chaque run -- pas un seul jeu de trades réutilisé 2000 fois) ; (3) sur
r_slippage (slippage réel Dukascopy intégré) ; (4) séquence block bootstrap 2 mois,
année 1 ; (5) moteur réserve poolée + immunité + correctif 999€.
"""
import random

import pandas as pd

from scaling_simulation import (
    TIER_SEQUENCE, CHALLENGE_COST, UPGRADE_COST, CHALLENGE_TARGET_PCT,
    MIN_TRADING_DAYS, BREAK_DD_PCT, RESERVE_SHARE, MAX_POSITIONS, CORR_THRESHOLD,
    feasible_risk_pct, load_market_data,
)
from monte_carlo_simulation import precompute_correlation_pairs, N_SIMULATIONS
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from slippage_adjusted_population import build_adjusted_population

N_ACCOUNTS = 3
YEAR_SECONDS = 365.25 * 86400
BLOCK_MONTHS = 2
RESERVE_SWITCH_THRESHOLD = 5000.0
ALPHA_POST, BETA_POST = 172.66, 305.36  # posterior établi précédemment (0 succès/15 essais)


def build_degraded_trades(sub_slip, target_winrate, rng):
    n = len(sub_slip)
    is_win = (sub_slip["statut_final"] == "OBJECTIF ATTEINT").to_numpy()
    current_n_win = int(is_win.sum())
    target_n_win = round(target_winrate * n)

    win_idx = list(sub_slip.index[is_win])
    flip_to_loss = set(rng.sample(win_idx, current_n_win - target_n_win)) if target_n_win < current_n_win else set()

    t0 = sub_slip["date_creation"].iloc[0]
    slot_arrivals = [(d - t0).total_seconds() for d in sub_slip["date_creation"]]
    trades = []
    for idx, row in sub_slip.iterrows():
        hold_seconds = (row["resolution_time_est"] - row["date_creation"]).total_seconds()
        sl_distance = abs(row["prix_entree"] - row["stop_loss_init"])
        outcome_r = -1.0 if idx in flip_to_loss else row["r_slippage"]
        trades.append({"ticker": row["ticker"], "outcome_r": outcome_r, "sl_distance": sl_distance,
                        "hold_seconds": hold_seconds, "date": row["date_creation"]})
    return trades, slot_arrivals


def run_fleet_year1(trades, slot_arrivals, market_data, excluded_map, order, low_risk, high_risk, switch_enabled):
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
    real_cash_paid = CHALLENGE_COST[TIER_SEQUENCE[0]] * N_ACCOUNTS
    total_breaks = 0

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]

        for acc in accounts:
            close_time = now + trade["hold_seconds"]
            acc["open_positions"] = [(t, c) for (t, c) in acc["open_positions"] if c > now]
            if len(acc["open_positions"]) >= MAX_POSITIONS:
                continue
            if any(t in excluded_map[trade["ticker"]] for (t, _) in acc["open_positions"]):
                continue

            current_risk = (high_risk if switched else low_risk) if switch_enabled else low_risk
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

            if switch_enabled and not switched and reserve >= RESERVE_SWITCH_THRESHOLD:
                switched = True

            drawdown = acc["peak_since_reset"] - acc["cumulative_since_reset"]
            if drawdown >= BREAK_DD_PCT / 100 * acc["palier"]:
                cost = CHALLENGE_COST[acc["palier"]]
                total_breaks += 1
                if reserve >= cost:
                    reserve -= cost
                else:
                    shortfall = cost - reserve
                    reserve = 0.0
                    if not ever_funded:
                        real_cash_paid += shortfall
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

    combined_net = sum(a["total_funded_pnl"] - a["total_fees_paid"] for a in accounts)
    return combined_net, real_cash_paid, total_breaks


def run_posterior_weighted(sub_slip, market_data, excluded_map, low_risk, high_risk, switch_enabled, label):
    rng = random.Random(42)
    block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
    rows = []
    for _ in range(N_SIMULATIONS):
        winrate_draw = rng.betavariate(ALPHA_POST, BETA_POST)
        trades, slot_arrivals = build_degraded_trades(sub_slip, winrate_draw, rng)
        blocks = build_blocks(trades, slot_arrivals, block_seconds)

        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, YEAR_SECONDS)
        cutoff = sum(1 for s in raw_slots if s <= YEAR_SECONDS)
        synth_trades = raw_trades[:cutoff]
        synth_slots = raw_slots[:cutoff]
        order = list(range(len(synth_trades)))

        net, cash, breaks = run_fleet_year1(synth_trades, synth_slots, market_data, excluded_map, order,
                                             low_risk, high_risk, switch_enabled)
        rows.append({"winrate_draw": winrate_draw, "net_profit": net, "real_cash_paid": cash, "total_breaks": breaks})

    df = pd.DataFrame(rows)
    df.to_csv(f"winrate_bayesian_posterior_{label}.csv", index=False)
    return df


def report(df, label):
    n = len(df)
    cash = df["real_cash_paid"]
    print(f"\n{'='*100}\n{label}\n{'='*100}")
    print(f"Winrate tiré -- moyenne {df['winrate_draw'].mean()*100:.2f}% | "
          f"médiane {df['winrate_draw'].median()*100:.2f}% | "
          f"P5-P95 [{df['winrate_draw'].quantile(0.05)*100:.2f}%, {df['winrate_draw'].quantile(0.95)*100:.2f}%]")
    print(f"Profit net -- moyenne {df['net_profit'].mean():+,.0f}€ | médiane {df['net_profit'].median():+,.0f}€")
    print(f"P(perte) : {(df['net_profit']<0).mean()*100:.2f}%")
    print(f"P(>=1 casse) : {(df['total_breaks']>0).mean()*100:.2f}% | casses moyennes {df['total_breaks'].mean():.2f}")
    print(f"Trésorerie -- moyenne {cash.mean():,.0f}€ | médiane {cash.median():,.0f}€ | pire cas {cash.max():,.0f}€")
    for p in [0.90, 0.95, 0.99]:
        print(f"  P{int(p*100)} : {cash.quantile(p):,.0f}€")
    print(f"P(>3000€) {(cash>3000).mean()*100:.2f}% | P(>5000€) {(cash>5000).mean()*100:.2f}% | "
          f"P(>10000€) {(cash>10000).mean()*100:.2f}%")


def main():
    pop_slip = build_adjusted_population("empirical")
    sub_slip = pop_slip.sort_values("date_creation").reset_index(drop=True)
    sub_slip["resolution_time_est"] = pd.to_datetime(sub_slip["resolution_time_est"])

    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(sub_slip["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    df_hybride = run_posterior_weighted(sub_slip, market_data, excluded_map, 0.5, 2.0, True, "hybride")
    report(df_hybride, "RÉGIME HYBRIDE -- winrate pondéré par le postérieur bayésien complet")

    df_2pct = run_posterior_weighted(sub_slip, market_data, excluded_map, 2.0, 2.0, False, "2pct_direct")
    report(df_2pct, "RÉGIME 2% DIRECT -- winrate pondéré par le postérieur bayésien complet")

    print(f"\n{'='*100}\nCOMPARAISON FINALE\n{'='*100}")
    print(f"{'':<25}{'Hybride':>15}{'2% direct':>15}")
    print(f"{'Profit net moyen':<25}{df_hybride['net_profit'].mean():>15,.0f}{df_2pct['net_profit'].mean():>15,.0f}")
    print(f"{'Profit net médian':<25}{df_hybride['net_profit'].median():>15,.0f}{df_2pct['net_profit'].median():>15,.0f}")
    print(f"{'P(perte)':<25}{(df_hybride['net_profit']<0).mean()*100:>14.2f}%{(df_2pct['net_profit']<0).mean()*100:>14.2f}%")
    print(f"{'Trésorerie moyenne':<25}{df_hybride['real_cash_paid'].mean():>15,.0f}{df_2pct['real_cash_paid'].mean():>15,.0f}")
    print(f"{'Trésorerie pire cas':<25}{df_hybride['real_cash_paid'].max():>15,.0f}{df_2pct['real_cash_paid'].max():>15,.0f}")
    print(f"{'P(>3000€)':<25}{(df_hybride['real_cash_paid']>3000).mean()*100:>14.2f}%{(df_2pct['real_cash_paid']>3000).mean()*100:>14.2f}%")
    print(f"{'P(>5000€)':<25}{(df_hybride['real_cash_paid']>5000).mean()*100:>14.2f}%{(df_2pct['real_cash_paid']>5000).mean()*100:>14.2f}%")


if __name__ == "__main__":
    main()
