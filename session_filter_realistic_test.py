"""
Reprend session_filter_copytrade_test.py (filtre de session horaire asiatique,
00h-08h UTC, sur la config de référence copytrade 3 comptes / 2% par compte) mais
remplace le payoff naïf "rr_tp2 systématique" par le payoff TP2 RÉALISTE construit
dans tp2_realistic_payoff.py : rr_tp2 si la continuation TP1->TP2 est vérifiée par les
bougies H1, rr_tp1 sinon (non confirmée ou hors couverture historique Yahoo).

3 scénarios (mêmes 472 trades candidats bruts) :
  1. Référence           : aucun filtre horaire
  2. Exclusion stricte    : signaux asiatiques (00h-08h UTC) jamais pris
  3. Exclusion partielle  : signaux asiatiques gardés mais à risque moitié (1% au lieu
     de 2%)

Résultat toujours pour la FLOTTE COMBINÉE (somme des 3 comptes).
"""
import random

import pandas as pd

import rr_threshold_test as rrt
from scaling_simulation import (
    TIER_SEQUENCE, CHALLENGE_COST, UPGRADE_COST, CHALLENGE_TARGET_PCT,
    MIN_TRADING_DAYS, BREAK_DD_PCT, RESERVE_SHARE, MAX_POSITIONS, CORR_THRESHOLD,
    feasible_risk_pct, load_market_data,
)
from monte_carlo_simulation import precompute_correlation_pairs, N_SIMULATIONS
from copytrade_simulation_test import summarize_copytrade, N_ACCOUNTS
from tp2_realistic_payoff import build_realistic_payoff_population, build_trades_realistic

MIN_RR_TP1 = 1.5
BASE_RISK_PCT = 2.0
ASIAN_START_H, ASIAN_END_H = 0, 8
SOFT_ASIAN_MULTIPLIER = 0.5


def is_asian(dt):
    return ASIAN_START_H <= dt.hour < ASIAN_END_H


def run_one_session(trades, slot_arrivals, base_risk_pct, market_data, excluded_map, rng, order=None):
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
    }


def run_copytrade_one_session(trades, slot_arrivals, base_risk_pct, market_data, excluded_map, rng,
                               n_accounts=N_ACCOUNTS):
    order = list(range(len(trades)))
    rng.shuffle(order)

    account_results = [
        run_one_session(trades, slot_arrivals, base_risk_pct, market_data, excluded_map, rng, order=order)
        for _ in range(n_accounts)
    ]
    return {
        "net_profit": sum(r["net_profit"] for r in account_results),
        "broken_count": sum(r["broken_count"] for r in account_results),
        "max_consecutive_breaks": max(r["max_consecutive_breaks"] for r in account_results),
    }


def simulate_account_with_events_session(trades, slot_arrivals, order, base_risk_pct, market_data,
                                          excluded_map, start_date):
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
    events = [(start_date, -CHALLENGE_COST[palier], palier)]

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
        eff_risk, _ = feasible_risk_pct(trade["ticker"], trade["sl_distance"], palier, target_risk_pct, market_data)
        risk_amount = eff_risk / 100 * palier
        pnl = trade["outcome_r"] * risk_amount

        open_positions.append((trade["ticker"], close_time))
        total_trading_pnl += pnl
        cumulative_since_reset += pnl
        peak_since_reset = max(peak_since_reset, cumulative_since_reset)
        trading_days_since_reset.add(int(now // 86400))
        events.append((trade["date"], pnl, palier))

        if phase == "funded" and pnl > 0:
            reserve += pnl * RESERVE_SHARE

        dd = peak_since_reset - cumulative_since_reset
        if dd >= BREAK_DD_PCT / 100 * palier:
            broken_count += 1
            total_fees_paid += CHALLENGE_COST[palier]
            events.append((trade["date"], -CHALLENGE_COST[palier], palier))
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
                if reserve >= cost:
                    reserve -= cost
                    total_fees_paid += cost
                    events.append((trade["date"], -cost, palier))
                    palier = next_tier
                    phase = "challenge"
                    cumulative_since_reset = 0.0
                    peak_since_reset = 0.0
                    trading_days_since_reset = set()

    net_profit = total_trading_pnl - total_fees_paid
    return {"net_profit": net_profit, "broken_count": broken_count, "final_tier": palier, "events": events}


def run_deterministic_copytrade_session(trades, slot_arrivals, base_risk_pct, market_data, excluded_map, start_date,
                                         n_accounts=N_ACCOUNTS):
    natural_order = list(range(len(trades)))
    account_runs = [
        simulate_account_with_events_session(trades, slot_arrivals, natural_order, base_risk_pct, market_data,
                                              excluded_map, start_date)
        for _ in range(n_accounts)
    ]
    combined_net_det = sum(r["net_profit"] for r in account_runs)

    all_events = []
    for r in account_runs:
        all_events.extend(r["events"])
    ev_df = pd.DataFrame(all_events, columns=["date", "net", "palier"])
    ev_df["month_index"] = ev_df["date"].apply(lambda d: (d.year - start_date.year) * 12 + (d.month - start_date.month))
    n_months = ev_df["month_index"].max() + 1

    palier_by_month = {}
    for i, r in enumerate(account_runs):
        acc_ev = pd.DataFrame(r["events"], columns=["date", "net", "palier"])
        acc_ev["month_index"] = acc_ev["date"].apply(lambda d: (d.year - start_date.year) * 12 + (d.month - start_date.month))
        palier_by_month[i] = acc_ev.groupby("month_index")["palier"].last().reindex(range(n_months)).ffill().bfill()

    combined_palier_by_month = sum(palier_by_month.values())
    monthly_net = ev_df.groupby("month_index")["net"].sum().reindex(range(n_months), fill_value=0.0)
    monthly_pct = monthly_net / combined_palier_by_month * 100

    return combined_net_det, monthly_pct.std(), monthly_pct.mean(), n_months, [r["broken_count"] for r in account_runs]


def run_scenario(name, pop_scenario, multiplier_fn, corr_matrix, market_data, pop_brut_n):
    pop_scenario = pop_scenario.copy()
    pop_scenario["risk_multiplier"] = pop_scenario.apply(multiplier_fn, axis=1)
    sub, trades, slot_arrivals = build_trades_realistic(pop_scenario, lambda row: row["risk_multiplier"])
    tickers = sorted(set(t["ticker"] for t in trades))
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    rng = random.Random(42)
    mc_results = [run_copytrade_one_session(trades, slot_arrivals, BASE_RISK_PCT, market_data, excluded_map, rng)
                  for _ in range(N_SIMULATIONS)]
    mc = summarize_copytrade(mc_results)

    start_date = sub["date_creation"].iloc[0]
    net_det, monthly_std, monthly_mean, n_months, per_account_broken = run_deterministic_copytrade_session(
        trades, slot_arrivals, BASE_RISK_PCT, market_data, excluded_map, start_date
    )

    taken = rrt.taken_trades(pop_scenario, corr_matrix)
    n_asian_taken = int(taken["date_creation"].apply(is_asian).sum())

    print("=" * 100)
    print(f"SCÉNARIO : {name}")
    print("=" * 100)
    print(f"Trades pris PAR COMPTE (après plafond 3 positions + corrélation 0.6/JPY) : {len(taken)} / {pop_brut_n} "
          f"candidats ({len(taken)/pop_brut_n*100:.1f}%) — dont {n_asian_taken} en session asiatique")
    print(f"Profit net FLOTTE COMBINÉE (3 comptes) moyen (MC, {N_SIMULATIONS} runs) : {mc['mean_profit']:+,.0f}€")
    print(f"Profit net combiné médian                                                : {mc['median_profit']:+,.0f}€")
    print(f"5e percentile combiné                                                     : {mc['p5_profit']:+,.0f}€")
    print(f"P(perte nette combinée)                                                   : {mc['pct_loss']:.1f}%")
    print(f"Nombre moyen de casses COMBINÉES (3 comptes)                              : {mc['mean_broken_count']:.2f}")
    print(f"Écart-type mensuel du rendement combiné (déterministe, {n_months} mois)    : {monthly_std:.2f}%")
    print(f"Rendement mensuel moyen combiné (déterministe)                            : {monthly_mean:+.2f}%")
    print(f"Profit net combiné (trajectoire déterministe, réf.)                       : {net_det:+,.0f}€")
    print(f"Casses par compte (déterministe) : {per_account_broken}")
    print()

    return {
        "scenario": name, "n_taken_per_account": len(taken), "n_brut": pop_brut_n,
        "pct_captured": len(taken) / pop_brut_n * 100, "n_asian_taken": n_asian_taken,
        **mc, "monthly_std_pct": monthly_std, "monthly_mean_pct": monthly_mean,
        "n_months": n_months, "net_profit_deterministic": net_det,
    }


def main():
    pop, median_duration = build_realistic_payoff_population(min_rr=MIN_RR_TP1, verbose=True)
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)

    pop_brut_n = len(pop)
    n_asian_brut = int(pop["date_creation"].apply(is_asian).sum())
    print(f"\nCOPYTRADE {N_ACCOUNTS} comptes, risque {BASE_RISK_PCT}%/compte, payoff TP2 RÉALISTE")
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
    summary_df.to_csv("session_filter_realistic_summary.csv", index=False)

    old_df = None
    try:
        old_df = pd.read_csv("session_filter_copytrade_summary.csv")
    except FileNotFoundError:
        pass

    print("=" * 100)
    print("TABLEAU COMPARATIF — FLOTTE COMBINÉE (3 comptes, 2%/compte, payoff TP2 RÉALISTE)")
    print("=" * 100)
    cols = ["scenario", "n_taken_per_account", "pct_captured", "mean_profit", "median_profit",
            "p5_profit", "mean_broken_count", "monthly_std_pct"]
    print(summary_df[cols].to_string(index=False))

    if old_df is not None:
        print("\n" + "=" * 100)
        print("COMPARAISON avec l'ancien payoff rr_tp2 systématique (naïf, session_filter_copytrade_summary.csv)")
        print("=" * 100)
        for i, row in summary_df.iterrows():
            old_mean = old_df.iloc[i]["mean_profit"]
            ratio = row["mean_profit"] / old_mean if old_mean else float("nan")
            print(f"  {row['scenario']:55s} : réaliste {row['mean_profit']:+,.0f}€ vs naïf {old_mean:+,.0f}€ "
                  f"(x{ratio:.2f})")

    print("\nRésumé enregistré dans session_filter_realistic_summary.csv")
    return summary_df


if __name__ == "__main__":
    main()
