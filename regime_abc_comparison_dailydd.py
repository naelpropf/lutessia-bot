"""
Version corrigée de regime_abc_comparison.py : ajoute la limite de perte
JOURNALIÈRE (5% -- règle FTMO/Blueberry 2-Step, cohérente avec le fait que cette
structure 50k->200k->500k représente désormais le segment croissance FTMO/Blueberry,
cf. three_firm_fleet_test.py) en plus du drawdown trailing 10% déjà modélisé, pour
mesurer l'écart dû à l'absence de cette règle dans les chiffres de référence
initiaux (voir daily_dd_threshold_verification.py pour la démonstration du bug sur
la trajectoire réelle : +70.6% de casses).

Perte journalière = somme du P&L RÉALISÉ (trades qui se CLÔTURENT) le même jour
SIMULÉ (index de jour synthétique now//86400, PAS la date calendaire d'origine du
trade -- les trades sont rebrassés par le block bootstrap, donc seul l'indice de
jour simulé a un sens ici). Proxy : ignore le mark-to-market intrajournalier des
positions encore ouvertes, donc sous-estime probablement encore un peu le vrai taux
de casse (plancher de l'écart réel, pas un plafond).

Reste identique à regime_abc_comparison.py sinon (mêmes 3 régimes A/B/C, mêmes
2 winrates, même moteur block bootstrap/réserve poolée/immunité/999$ init).
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
BLOCK_MONTHS = 2
RESERVE_SWITCH_THRESHOLD = 5000.0
LOW_RISK, HIGH_RISK = 0.5, 2.0
DAILY_LOSS_PCT = 5.0  # FTMO/Blueberry 2-Step

REGIMES = {
    "A. 2% direct": {"flat2": True, "reserve_gate": False},
    "B. Hybride amélioré (bascule immédiate)": {"flat2": False, "reserve_gate": False},
    "C. Hybride actuel (bascule @5000€)": {"flat2": False, "reserve_gate": True},
}


def run_fleet_multi_mark(trades, slot_arrivals, market_data, excluded_map, order, regime_cfg, mark_seconds_list):
    accounts = []
    for _ in range(N_ACCOUNTS):
        accounts.append({
            "palier": TIER_SEQUENCE[0], "phase": "challenge", "cumulative_since_reset": 0.0,
            "peak_since_reset": 0.0, "trading_days_since_reset": set(), "open_positions": [],
            "total_funded_pnl": 0.0, "total_fees_paid": CHALLENGE_COST[TIER_SEQUENCE[0]],
            "daily_pnl": {},
        })
    reserve = 0.0
    switched = regime_cfg["flat2"]
    ever_funded = False
    real_cash_paid = CHALLENGE_COST[TIER_SEQUENCE[0]] * N_ACCOUNTS
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

            current_risk = HIGH_RISK if switched else LOW_RISK
            eff_risk, _ = feasible_risk_pct(trade["ticker"], trade["sl_distance"], acc["palier"], current_risk, market_data)
            risk_amount = eff_risk / 100 * acc["palier"]
            pnl = trade["outcome_r"] * risk_amount

            acc["open_positions"].append((trade["ticker"], close_time))
            acc["cumulative_since_reset"] += pnl
            acc["peak_since_reset"] = max(acc["peak_since_reset"], acc["cumulative_since_reset"])
            acc["trading_days_since_reset"].add(int(now // 86400))

            close_day = int(close_time // 86400)
            acc["daily_pnl"][close_day] = acc["daily_pnl"].get(close_day, 0.0) + pnl

            if acc["phase"] == "funded":
                acc["total_funded_pnl"] += pnl
                if pnl > 0:
                    reserve += pnl * RESERVE_SHARE

            if not switched and not regime_cfg["flat2"] and ever_funded:
                if not regime_cfg["reserve_gate"] or reserve >= RESERVE_SWITCH_THRESHOLD:
                    switched = True

            trailing_dd = acc["peak_since_reset"] - acc["cumulative_since_reset"]
            daily_dd = -acc["daily_pnl"][close_day]
            broke = (trailing_dd >= BREAK_DD_PCT / 100 * acc["palier"]
                     or daily_dd >= DAILY_LOSS_PCT / 100 * acc["palier"])

            if broke:
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
                acc["daily_pnl"] = {}
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
        snapshots.append((marks_sorted[mark_idx], combined_net, real_cash_paid, total_breaks))
        mark_idx += 1

    return snapshots


def run_regime(trades, slot_arrivals, blocks, block_seconds, target_duration, mark_seconds_list,
               market_data, excluded_map, regime_cfg):
    rng = random.Random(42)
    rows = []
    for _ in range(N_SIMULATIONS):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, target_duration)
        order = list(range(len(raw_trades)))
        snaps = run_fleet_multi_mark(raw_trades, raw_slots, market_data, excluded_map, order, regime_cfg, mark_seconds_list)
        row = {
            "year1_net": snaps[0][1], "year1_cash": snaps[0][2], "year1_breaks": snaps[0][3],
            "final_net": snaps[1][1], "final_cash": snaps[1][2], "final_breaks": snaps[1][3],
        }
        rows.append(row)
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

    all_results = {}
    for wr_label, wr_target in [("37.29%", None), ("32%", 0.32)]:
        trades, slot_arrivals = build_population(pop, wr_target)
        total_horizon_seconds = slot_arrivals[-1]
        mark_seconds_list = [YEAR_SECONDS, total_horizon_seconds]
        block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
        blocks = build_blocks(trades, slot_arrivals, block_seconds)

        for regime_label, regime_cfg in REGIMES.items():
            print(f"Calcul : winrate {wr_label} | régime {regime_label}...")
            df = run_regime(trades, slot_arrivals, blocks, block_seconds, total_horizon_seconds,
                             mark_seconds_list, market_data, excluded_map, regime_cfg)
            all_results[(wr_label, regime_label)] = df
            df.to_csv(f"regime_abc_dailydd_{wr_label.replace('%','pct').replace('.','_')}_{regime_label[:1]}.csv", index=False)

    summary_rows = []
    for (wr_label, regime_label), df in all_results.items():
        cash = df["final_cash"]
        row = {
            "winrate": wr_label, "regime": regime_label,
            "profit_year1_moyen": df["year1_net"].mean(), "profit_year1_median": df["year1_net"].median(),
            "profit_final_moyen": df["final_net"].mean(), "profit_final_median": df["final_net"].median(),
            "pct_loss_year1": (df["year1_net"] < 0).mean() * 100,
            "cash_worst": cash.max(), "cash_mean": cash.mean(),
            "p_gt_1000": (cash > 1000).mean() * 100, "p_gt_3000": (cash > 3000).mean() * 100,
            "p_gt_5000": (cash > 5000).mean() * 100, "p_gt_10000": (cash > 10000).mean() * 100,
            "casses_moyennes_final": df["final_breaks"].mean(),
        }
        summary_rows.append(row)
        print(f"\n[{wr_label}] {regime_label}")
        print(f"  Profit an1  : moyenne {row['profit_year1_moyen']:+,.0f}€ | médiane {row['profit_year1_median']:+,.0f}€")
        print(f"  Profit final: moyenne {row['profit_final_moyen']:+,.0f}€ | médiane {row['profit_final_median']:+,.0f}€")
        print(f"  P(perte) an1 : {row['pct_loss_year1']:.2f}%")
        print(f"  Trésorerie -- moyenne {row['cash_mean']:,.0f}€ | pire cas {row['cash_worst']:,.0f}€")
        print(f"  Casses moyennes (horizon complet) : {row['casses_moyennes_final']:.2f}")

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv("regime_abc_dailydd_summary.csv", index=False)
    print("\nRésumé enregistré dans regime_abc_dailydd_summary.csv")


if __name__ == "__main__":
    main()
