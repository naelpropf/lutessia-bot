"""
Stress-test winrate remplaçant l'ancien scénario 28% (naïf, "15 pertes -> winrate
observé implicite") par un scénario 32% justifié par mise à jour bayésienne :
prior calibré sur les 472 trades historiques (Beta ~ mean 37.29%, IC95 [32.9%,41.7%])
mis à jour avec 0 succès/15 essais -> postérieur médian 36.1%, P10 = 33.3% (proche du
32% retenu, légèrement plus conservateur que la borne bayésienne stricte).

Moteur : block bootstrap 2 mois, réserve poolée, immunité post-financement,
correctif comptable 999€ (achat initial des 3 challenges) -- PAS de slippage ici
(stress-test isolé sur le winrate, sujet distinct du slippage déjà traité). r_trailing
(convention verrouillée actuelle, RR moyen gagnants 4.115 -- PAS 3.89, qui est la
figure r_realiste SANS trailing ; distinction documentée dans le rapport).

3 colonnes comparées à chaque niveau de risque (0.5% à 3%) : référence (37.29%),
scénario 32% (nouveau, bayésien), ancien 28% (conservé pour contraste seulement).
"""
import random

import pandas as pd

from scaling_simulation import (
    TIER_SEQUENCE, CHALLENGE_COST, UPGRADE_COST, CHALLENGE_TARGET_PCT,
    MIN_TRADING_DAYS, BREAK_DD_PCT, RESERVE_SHARE, MAX_POSITIONS, CORR_THRESHOLD,
    feasible_risk_pct, load_market_data,
)
from monte_carlo_simulation import precompute_correlation_pairs, N_SIMULATIONS
from trailing_payoff_population import build_population_with_trailing
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from winrate_sensitivity_test import build_degraded_trades, DEGRADE_SEED

N_ACCOUNTS = 3
YEAR_SECONDS = 365.25 * 86400
BLOCK_MONTHS = 2
RISK_LEVELS = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
SCENARIOS = {"reference_37.29": None, "bayesien_32": 0.32, "ancien_28": 0.28}


def run_fleet_year1_pooled(trades, slot_arrivals, market_data, excluded_map, order, risk_pct):
    accounts = []
    for _ in range(N_ACCOUNTS):
        accounts.append({
            "palier": TIER_SEQUENCE[0], "phase": "challenge", "cumulative_since_reset": 0.0,
            "peak_since_reset": 0.0, "trading_days_since_reset": set(), "open_positions": [],
            "total_funded_pnl": 0.0, "total_fees_paid": CHALLENGE_COST[TIER_SEQUENCE[0]],
        })
    reserve = 0.0
    ever_funded = False
    real_cash_paid = CHALLENGE_COST[TIER_SEQUENCE[0]] * N_ACCOUNTS  # correctif 999€
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

            eff_risk, _ = feasible_risk_pct(trade["ticker"], trade["sl_distance"], acc["palier"], risk_pct, market_data)
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


def run_risk_level(trades, slot_arrivals, market_data, excluded_map, blocks, block_seconds, risk_pct):
    rng = random.Random(42)
    rows = []
    for _ in range(N_SIMULATIONS):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, YEAR_SECONDS)
        cutoff = sum(1 for s in raw_slots if s <= YEAR_SECONDS)
        synth_trades = raw_trades[:cutoff]
        synth_slots = raw_slots[:cutoff]
        order = list(range(len(synth_trades)))
        net, cash, breaks = run_fleet_year1_pooled(synth_trades, synth_slots, market_data, excluded_map, order, risk_pct)
        rows.append({"net_profit": net, "real_cash_paid": cash, "total_breaks": breaks})
    return pd.DataFrame(rows)


def build_trades_for_scenario(pop, target_winrate):
    if target_winrate is None:
        sub = pop.sort_values("date_creation").reset_index(drop=True)
        t0 = sub["date_creation"].iloc[0]
        slot_arrivals = [(d - t0).total_seconds() for d in sub["date_creation"]]
        trades = []
        for _, row in sub.iterrows():
            hold_seconds = (row["resolution_time_est"] - row["date_creation"]).total_seconds()
            sl_distance = abs(row["prix_entree"] - row["stop_loss_init"])
            trades.append({"ticker": row["ticker"], "outcome_r": row["r_trailing"],
                            "sl_distance": sl_distance, "hold_seconds": hold_seconds, "date": row["date_creation"]})
        wins = pop[pop["statut_final"] == "OBJECTIF ATTEINT"]
        avg_win_r = wins["r_trailing"].mean()
        actual_wr = len(wins) / len(pop)
        return trades, slot_arrivals, actual_wr, avg_win_r
    else:
        rng = random.Random(DEGRADE_SEED)
        sub, trades, slot_arrivals, actual_wr = build_degraded_trades(pop, target_winrate, rng)
        winners_r = [t["outcome_r"] for t in trades if t["outcome_r"] > 0]
        avg_win_r = sum(winners_r) / len(winners_r)
        return trades, slot_arrivals, actual_wr, avg_win_r


def main():
    pop = build_population_with_trailing("fixed", 0.2, verbose=False)
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    scenario_data = {}
    for label, target in SCENARIOS.items():
        trades, slots, actual_wr, avg_win_r = build_trades_for_scenario(pop, target)
        scenario_data[label] = (trades, slots)
        print(f"{label} : winrate réalisé {actual_wr*100:.2f}% | RR moyen gagnants {avg_win_r:.3f}")

    print("\n" + "=" * 100)
    print("SWEEP DE RISQUE 0.5%->3%, 3 SCÉNARIOS DE WINRATE CÔTE À CÔTE (année 1, 2000 runs)")
    print("=" * 100)

    all_rows = []
    phase1_by_scenario = {}
    for risk_pct in RISK_LEVELS:
        print(f"\n{'='*100}\nRISQUE {risk_pct}%\n{'='*100}")
        for label, (trades, slots) in scenario_data.items():
            block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
            blocks = build_blocks(trades, slots, block_seconds)
            df = run_risk_level(trades, slots, market_data, excluded_map, blocks, block_seconds, risk_pct)
            if risk_pct == 0.5:
                phase1_by_scenario[label] = df

            row = {
                "risk_pct": risk_pct, "scenario": label,
                "profit_moyen": df["net_profit"].mean(), "profit_median": df["net_profit"].median(),
                "std_profit": df["net_profit"].std(), "casses_moyennes": df["total_breaks"].mean(),
                "pct_perte": (df["net_profit"] < 0).mean() * 100,
                "cash_moyen": df["real_cash_paid"].mean(), "cash_worst": df["real_cash_paid"].max(),
            }
            all_rows.append(row)
            print(f"  {label:<18} : profit moyen {row['profit_moyen']:+,.0f}€ | casses {row['casses_moyennes']:.2f} | "
                  f"P(perte) {row['pct_perte']:.2f}% | std {row['std_profit']:,.0f}€")

    summary_df = pd.DataFrame(all_rows)
    summary_df.to_csv("winrate32_bayesian_stress_summary.csv", index=False)

    print("\n" + "=" * 100)
    print("PHASE 1 ISOLÉE (0.5% risque, 3x50k)")
    print("=" * 100)
    for label, df in phase1_by_scenario.items():
        p_break = (df["total_breaks"] > 0).mean() * 100
        cash = df["real_cash_paid"]
        print(f"\n{label} :")
        print(f"  P(au moins une casse) : {p_break:.2f}%")
        print(f"  Trésorerie -- moyenne {cash.mean():,.0f}€ | pire cas {cash.max():,.0f}€ | "
              f"P(>3000€) {(cash>3000).mean()*100:.2f}%")

    print("\n" + "=" * 100)
    print("TABLEAU COMPARATIF FINAL")
    print("=" * 100)
    pivot = summary_df.pivot(index="risk_pct", columns="scenario",
                              values=["profit_moyen", "casses_moyennes", "pct_perte"])
    print(pivot.to_string())
    print("\nRésumé complet enregistré dans winrate32_bayesian_stress_summary.csv")


if __name__ == "__main__":
    main()
