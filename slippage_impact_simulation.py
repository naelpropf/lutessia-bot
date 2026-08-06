"""
Impact du slippage réel (Dukascopy, méthode empirique -- tirage dans la distribution
mesurée, 469 trades) sur le rendement et les casses, à plusieurs niveaux de risque
fixe (0.5% à 3%), réserve poolée + immunité perso post-financement (moteur établi
cette nuit), block bootstrap 2 mois, année 1, 2000 runs -- copytrade 3 comptes,
plafond 3 positions, corrélation 0.6+JPY, faisabilité marge/lots.

Phase 1 isolée séparément (0.5% risque, 3 comptes 50k, budget perso ~2000€) : P(au
moins une casse), trésorerie perso pire cas -- comparée à l'ancien chiffre cité
(21 972€), qui vient d'une méthodologie ANTÉRIEURE aux corrections de cette nuit
(bootstrap par PERMUTATION + réserve NON poolée, cf. risk_switch_threshold_summary.csv)
-- pas directement comparable, donc recalculée ici avec le moteur actuel pour une
vraie comparaison avant/après slippage sur la MÊME base.
"""
import random

import numpy as np
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
MONTH_SECONDS = 30.44 * 86400
BLOCK_MONTHS = 2
RISK_LEVELS = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]


def build_trades(pop, outcome_col):
    sub = pop.sort_values("date_creation").reset_index(drop=True)
    sub["resolution_time_est"] = pd.to_datetime(sub["resolution_time_est"])
    t0 = sub["date_creation"].iloc[0]
    slot_arrivals = [(d - t0).total_seconds() for d in sub["date_creation"]]
    trades = []
    for _, row in sub.iterrows():
        hold_seconds = (row["resolution_time_est"] - row["date_creation"]).total_seconds()
        sl_distance = abs(row["prix_entree"] - row["stop_loss_init"])
        trades.append({
            "ticker": row["ticker"], "outcome_r": row[outcome_col],
            "sl_distance": sl_distance, "hold_seconds": hold_seconds, "date": row["date_creation"],
        })
    return sub, trades, slot_arrivals


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
    real_cash_paid = 0.0
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


def main():
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)

    pop_baseline = pd.read_csv("population_with_force.csv")
    pop_baseline["date_creation"] = pd.to_datetime(pop_baseline["date_creation"])
    pop_slip = build_adjusted_population("empirical")

    tickers = sorted(pop_baseline["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    sub_b, trades_b, slots_b = build_trades(pop_baseline, "r_trailing")
    sub_s, trades_s, slots_s = build_trades(pop_slip, "r_slippage")

    block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
    blocks_b = build_blocks(trades_b, slots_b, block_seconds)
    blocks_s = build_blocks(trades_s, slots_s, block_seconds)

    print("=" * 100)
    print("3+6. SWEEP DE NIVEAUX DE RISQUE (0.5% -> 3%), AVEC vs SANS SLIPPAGE (année 1, 2000 runs)")
    print("=" * 100)

    summary_rows = []
    phase1_baseline_df = None
    phase1_slip_df = None
    for risk_pct in RISK_LEVELS:
        df_b = run_risk_level(trades_b, slots_b, market_data, excluded_map, blocks_b, block_seconds, risk_pct)
        df_s = run_risk_level(trades_s, slots_s, market_data, excluded_map, blocks_s, block_seconds, risk_pct)

        if risk_pct == 0.5:
            phase1_baseline_df, phase1_slip_df = df_b, df_s

        row = {
            "risk_pct": risk_pct,
            "ev_sans_slippage": sum(t["outcome_r"] for t in trades_b) / len(trades_b),
            "ev_avec_slippage": sum(t["outcome_r"] for t in trades_s) / len(trades_s),
            "profit_moyen_sans": df_b["net_profit"].mean(), "profit_moyen_avec": df_s["net_profit"].mean(),
            "profit_median_sans": df_b["net_profit"].median(), "profit_median_avec": df_s["net_profit"].median(),
            "casses_moyennes_sans": df_b["total_breaks"].mean(), "casses_moyennes_avec": df_s["total_breaks"].mean(),
            "pct_perte_sans": (df_b["net_profit"] < 0).mean() * 100, "pct_perte_avec": (df_s["net_profit"] < 0).mean() * 100,
            "std_profit_sans": df_b["net_profit"].std(), "std_profit_avec": df_s["net_profit"].std(),
        }
        summary_rows.append(row)

        print(f"\n--- Risque {risk_pct}% ---")
        print(f"  EV               : sans {row['ev_sans_slippage']:+.4f}R | avec {row['ev_avec_slippage']:+.4f}R")
        print(f"  Profit net moyen : sans {row['profit_moyen_sans']:+,.0f}€ | avec {row['profit_moyen_avec']:+,.0f}€ "
              f"({(row['profit_moyen_avec']/row['profit_moyen_sans']-1)*100:+.1f}%)")
        print(f"  Casses moyennes  : sans {row['casses_moyennes_sans']:.2f} | avec {row['casses_moyennes_avec']:.2f}")
        print(f"  P(perte)         : sans {row['pct_perte_sans']:.2f}% | avec {row['pct_perte_avec']:.2f}%")
        print(f"  Écart-type profit annuel (proxy dispersion) : sans {row['std_profit_sans']:,.0f}€ | "
              f"avec {row['std_profit_avec']:,.0f}€")

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv("slippage_impact_summary.csv", index=False)

    print("\n" + "=" * 100)
    print("4. PHASE 1 ISOLÉE (0.5% risque, 3 comptes 50k, budget perso ~2000€)")
    print("=" * 100)
    n = len(phase1_baseline_df)
    for label, df in [("SANS slippage", phase1_baseline_df), ("AVEC slippage", phase1_slip_df)]:
        p_break = (df["total_breaks"] > 0).mean() * 100
        cash = df["real_cash_paid"]
        print(f"\n{label} :")
        print(f"  P(au moins une casse sur la flotte) : {p_break:.2f}%")
        print(f"  Casses moyennes : {df['total_breaks'].mean():.2f}")
        print(f"  Trésorerie perso -- moyenne {cash.mean():,.0f}€ | pire cas {cash.max():,.0f}€ | "
              f"P(>3000€) {(cash>3000).mean()*100:.2f}%")
    print(f"\n[Rappel] Le chiffre '21 972€' cité vient d'une méthodologie antérieure "
          f"(bootstrap par permutation + réserve NON poolée, risk_switch_threshold_summary.csv) -- "
          f"pas directement comparable au moteur actuel (block bootstrap 2 mois + réserve poolée + "
          f"immunité post-financement), qui donne un pire cas bien plus bas par construction "
          f"(cf. {phase1_baseline_df['real_cash_paid'].max():,.0f}€ sans slippage ci-dessus, "
          f"déjà établi précédemment à 1998€ sur le même moteur/graine).")

    print("\n" + "=" * 100)
    print("5. IMPACT PLUS DANGEREUX SUR LES SL SERRÉS ?")
    print("=" * 100)
    slip_detail = pd.read_csv("slippage_proxy_dukascopy_detail.csv")
    slip_detail["slippage_pct_sl"] = slip_detail["slippage"].abs() / slip_detail["sl_distance"] * 100
    corr = np.corrcoef(slip_detail["sl_distance"], slip_detail["slippage_pct_sl"])[0, 1]
    print(f"Corrélation (distance SL absolue <-> impact % du slippage) : r = {corr:+.3f} "
          f"(négatif attendu si SL serrés sont plus impactés)")
    for threshold in [10, 15, 20, 25]:
        n_over = (slip_detail["slippage_pct_sl"] > threshold).sum()
        print(f"Trades avec impact slippage > {threshold}% de la distance SL : {n_over}/{len(slip_detail)} "
              f"({n_over/len(slip_detail)*100:.1f}%)")

    # SL les plus serrés (quartile inférieur) vs les plus larges
    q1 = slip_detail["sl_distance"].quantile(0.25)
    q3 = slip_detail["sl_distance"].quantile(0.75)
    tight = slip_detail[slip_detail["sl_distance"] <= q1]
    wide = slip_detail[slip_detail["sl_distance"] >= q3]
    print(f"\nImpact moyen (% distance SL) -- SL serrés (Q1, n={len(tight)}) : {tight['slippage_pct_sl'].mean():.2f}%")
    print(f"Impact moyen (% distance SL) -- SL larges (Q4, n={len(wide)}) : {wide['slippage_pct_sl'].mean():.2f}%")

    print("\n" + "=" * 100)
    print("TABLEAU COMPARATIF FINAL")
    print("=" * 100)
    print(summary_df.to_string(index=False))
    print("\nRésumé enregistré dans slippage_impact_summary.csv")


if __name__ == "__main__":
    main()
