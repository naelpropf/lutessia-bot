"""
Simule la VRAIE flotte de 3 comptes MT5 avec routage dynamique (cf. account_router.py),
chacun scalant indépendamment (50k->200k->500k, son propre challenge/reserve/drawdown),
au lieu du modèle à un seul compte utilisé dans tous les tests précédents
(scaling_simulation.py, monte_carlo_simulation.py, rr_threshold_test.py,
rr_risk_combo_test.py, real_cash_risk_test.py — AUCUN ne modélisait la flotte).

Règles utilisées pour le routage/plafond par compte : celles déjà VALIDÉES dans ce
projet (3 positions/compte, corrélation 0.6 + règle JPY explicite) — PAS les valeurs
actuellement dans account_router.py (2 positions/compte, corrélation 0.5, pas de
règle JPY), qui semble ne pas avoir été mis à jour suite à ces décisions (à corriger
séparément, hors scope de ce test).

Logique de sélection de compte reproduite depuis account_router.select_account() :
parmi les comptes éligibles (sous le plafond, pas de position ouverte corrélée),
choisit celui avec le MOINS de positions ouvertes (0 en priorité) ; aucun compte
éligible -> signal ignoré (comme dans le code réel).

Deux volets :
1. Monte Carlo (bootstrap par permutation, 2000 runs) sur la flotte combinée, pour
   la distribution de profit net combiné et le taux de capture de signaux.
2. Une trajectoire déterministe unique (chronologie réelle, pas de permutation)
   pour la ventilation mensuelle/annuelle combinée, comparable à celle déjà produite
   pour le compte seul.
"""
import random

import pandas as pd

from scaling_simulation import (
    TIER_SEQUENCE, CHALLENGE_COST, UPGRADE_COST, CHALLENGE_TARGET_PCT,
    MIN_TRADING_DAYS, BREAK_DD_PCT, RESERVE_SHARE, is_jpy, feasible_risk_pct, load_market_data,
)
import statistics

from monte_carlo_simulation import precompute_correlation_pairs, N_SIMULATIONS


def summarize_fleet(results):
    profits = sorted(r["net_profit"] for r in results)
    n = len(profits)
    p5 = profits[int(0.05 * n)]
    return {
        "mean_profit": statistics.mean(profits),
        "median_profit": statistics.median(profits),
        "p5_profit": p5,
        "worst_profit": profits[0],
        "best_profit": profits[-1],
        "pct_loss": sum(1 for p in profits if p < 0) / n * 100,
        "mean_broken_count": statistics.mean(r["broken_count"] for r in results),
        "mean_max_consecutive_breaks": statistics.mean(r["max_consecutive_breaks"] for r in results),
        "max_max_consecutive_breaks": max(r["max_consecutive_breaks"] for r in results),
    }
from rr_threshold_test import build_extended_population

THRESHOLD = 1.5
RISK_PCT = 2.0
CORR_THRESHOLD_FLEET = 0.6
MAX_POSITIONS_PER_ACCOUNT = 3
N_ACCOUNTS = 3


def build_trades(pop):
    sub = pop.sort_values("date_creation").reset_index(drop=True)
    t0 = sub["date_creation"].iloc[0]
    slot_arrivals = [(d - t0).total_seconds() for d in sub["date_creation"]]
    trades = []
    for _, row in sub.iterrows():
        hold_seconds = (row["resolution_time_est"] - row["date_creation"]).total_seconds()
        sl_distance = abs(row["prix_entree"] - row["stop_loss_init"])
        trades.append({
            "ticker": row["ticker"],
            "outcome_r": row["rr_tp1"] if row["statut_final"] == "OBJECTIF ATTEINT" else -1.0,
            "sl_distance": sl_distance,
            "hold_seconds": hold_seconds,
            "date": row["date_creation"],
        })
    return sub, trades, slot_arrivals


def init_account():
    palier = TIER_SEQUENCE[0]
    return {
        "palier": palier, "phase": "challenge",
        "cumulative_since_reset": 0.0, "peak_since_reset": 0.0,
        "trading_days_since_reset": set(), "reserve": 0.0,
        "total_fees_paid": CHALLENGE_COST[palier], "total_trading_pnl": 0.0,
        "broken_count": 0, "open_positions": [],
        "consecutive_breaks": 0, "max_consecutive_breaks": 0,
    }


def route(ticker, accounts, excluded_map, now):
    eligible = []
    for i, acc in enumerate(accounts):
        acc["open_positions"] = [(t, c) for (t, c) in acc["open_positions"] if c > now]
        n_pos = len(acc["open_positions"])
        if n_pos >= MAX_POSITIONS_PER_ACCOUNT:
            continue
        if any(t in excluded_map[ticker] for (t, _) in acc["open_positions"]):
            continue
        eligible.append((i, n_pos))
    if not eligible:
        return None
    eligible.sort(key=lambda x: x[1])
    return eligible[0][0]


def step_account(acc, trade, now, close_time, risk_pct, market_data):
    target_risk_pct = risk_pct(acc["palier"]) if callable(risk_pct) else risk_pct
    eff_risk, _ = feasible_risk_pct(trade["ticker"], trade["sl_distance"], acc["palier"], target_risk_pct, market_data)
    risk_amount = eff_risk / 100 * acc["palier"]
    pnl = trade["outcome_r"] * risk_amount

    acc["open_positions"].append((trade["ticker"], close_time))
    acc["total_trading_pnl"] += pnl
    acc["cumulative_since_reset"] += pnl
    acc["peak_since_reset"] = max(acc["peak_since_reset"], acc["cumulative_since_reset"])
    acc["trading_days_since_reset"].add(int(now // 86400))

    if acc["phase"] == "funded" and pnl > 0:
        acc["reserve"] += pnl * RESERVE_SHARE

    dd = acc["peak_since_reset"] - acc["cumulative_since_reset"]
    if dd >= BREAK_DD_PCT / 100 * acc["palier"]:
        acc["broken_count"] += 1
        acc["consecutive_breaks"] += 1
        acc["max_consecutive_breaks"] = max(acc["max_consecutive_breaks"], acc["consecutive_breaks"])
        acc["total_fees_paid"] += CHALLENGE_COST[acc["palier"]]
        acc["phase"] = "challenge"
        acc["cumulative_since_reset"] = 0.0
        acc["peak_since_reset"] = 0.0
        acc["trading_days_since_reset"] = set()
        return pnl

    if (acc["phase"] == "challenge" and acc["cumulative_since_reset"] >= CHALLENGE_TARGET_PCT / 100 * acc["palier"]
            and len(acc["trading_days_since_reset"]) >= MIN_TRADING_DAYS):
        acc["phase"] = "funded"
        acc["cumulative_since_reset"] = 0.0
        acc["peak_since_reset"] = 0.0
        acc["trading_days_since_reset"] = set()
        acc["consecutive_breaks"] = 0

    if acc["phase"] == "funded":
        idx = TIER_SEQUENCE.index(acc["palier"])
        if idx + 1 < len(TIER_SEQUENCE):
            next_tier = TIER_SEQUENCE[idx + 1]
            cost = UPGRADE_COST[next_tier]
            if acc["reserve"] >= cost:
                acc["reserve"] -= cost
                acc["total_fees_paid"] += cost
                acc["palier"] = next_tier
                acc["phase"] = "challenge"
                acc["cumulative_since_reset"] = 0.0
                acc["peak_since_reset"] = 0.0
                acc["trading_days_since_reset"] = set()

    return pnl


def run_fleet_one(trades, slot_arrivals, risk_pct, market_data, excluded_map, rng):
    order = list(range(len(trades)))
    rng.shuffle(order)

    accounts = [init_account() for _ in range(N_ACCOUNTS)]
    n_taken = 0

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]
        close_time = now + trade["hold_seconds"]

        acc_idx = route(trade["ticker"], accounts, excluded_map, now)
        if acc_idx is None:
            continue
        n_taken += 1
        step_account(accounts[acc_idx], trade, now, close_time, risk_pct, market_data)

    combined_net_profit = sum(a["total_trading_pnl"] - a["total_fees_paid"] for a in accounts)
    combined_broken = sum(a["broken_count"] for a in accounts)
    combined_max_consec = max(a["max_consecutive_breaks"] for a in accounts)
    final_tiers = tuple(sorted(a["palier"] for a in accounts))
    return {
        "net_profit": combined_net_profit,
        "broken_count": combined_broken,
        "max_consecutive_breaks": combined_max_consec,
        "n_taken": n_taken,
        "final_tiers": final_tiers,
    }


def run_fleet_deterministic(trades, slot_arrivals, risk_pct, market_data, excluded_map):
    """Trajectoire unique, chronologie réelle (pas de permutation) — pour la
    ventilation mensuelle/annuelle combinée. Chaque événement porte aussi le capital
    combiné COURANT (somme des paliers des 3 comptes à cet instant précis), pour
    calculer un rendement % relatif au capital réellement déployé — PAS relatif au
    capital de départ fixe (3x50k), qui gonflerait artificiellement la variance une
    fois les comptes scalés à des paliers différents."""
    accounts = [init_account() for _ in range(N_ACCOUNTS)]
    n_taken = 0
    events = []  # (date, net_amount, capital_combine_courant)
    combined_palier_start = sum(a["palier"] for a in accounts)
    events.extend((trades[0]["date"], -CHALLENGE_COST[TIER_SEQUENCE[0]], combined_palier_start) for _ in range(N_ACCOUNTS))

    for slot_idx in range(len(trades)):
        trade = trades[slot_idx]
        now = slot_arrivals[slot_idx]
        close_time = now + trade["hold_seconds"]

        acc_idx = route(trade["ticker"], accounts, excluded_map, now)
        if acc_idx is None:
            continue
        n_taken += 1
        acc = accounts[acc_idx]
        fees_before = acc["total_fees_paid"]
        pnl = step_account(acc, trade, now, close_time, risk_pct, market_data)
        fee_delta = acc["total_fees_paid"] - fees_before
        combined_palier = sum(a["palier"] for a in accounts)
        events.append((trade["date"], pnl, combined_palier))
        if fee_delta:
            events.append((trade["date"], -fee_delta, combined_palier))

    combined_net_profit = sum(a["total_trading_pnl"] - a["total_fees_paid"] for a in accounts)
    return accounts, events, n_taken, combined_net_profit


def main():
    pop_full, _ = build_extended_population()
    pop = pop_full[pop_full["rr_tp1"] >= THRESHOLD].copy()
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)

    sub, trades, slot_arrivals = build_trades(pop)
    tickers = sorted(set(t["ticker"] for t in trades))
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD_FLEET)

    print(f"Seuil rr_tp1 >= {THRESHOLD}, risque {RISK_PCT}%, flotte de {N_ACCOUNTS} comptes "
          f"(plafond {MAX_POSITIONS_PER_ACCOUNT} positions/compte, corrélation {CORR_THRESHOLD_FLEET}+JPY)")
    print(f"Pool de signaux disponibles : {len(sub)}\n")

    # --- 1. Monte Carlo combiné ---
    print("=" * 100)
    print(f"MONTE CARLO FLOTTE COMBINÉE — {N_SIMULATIONS} simulations")
    print("=" * 100)
    rng = random.Random(42)
    results = [run_fleet_one(trades, slot_arrivals, RISK_PCT, market_data, excluded_map, rng) for _ in range(N_SIMULATIONS)]
    mc = summarize_fleet(results)
    n_taken_list = [r["n_taken"] for r in results]
    mean_n_taken = sum(n_taken_list) / len(n_taken_list)

    print(f"Profit net combiné moyen   : {mc['mean_profit']:+,.0f}€")
    print(f"Profit net combiné médian  : {mc['median_profit']:+,.0f}€")
    print(f"5e percentile              : {mc['p5_profit']:+,.0f}€")
    print(f"P(perte nette)             : {mc['pct_loss']:.1f}%")
    print(f"Pire cas / meilleur cas    : {mc['worst_profit']:+,.0f}€ / {mc['best_profit']:+,.0f}€")
    print(f"Casses combinées (moyenne) : {mc['mean_broken_count']:.2f}")
    print(f"Signaux pris en moyenne (sur {len(sub)} disponibles) : {mean_n_taken:.1f} "
          f"({mean_n_taken/len(sub)*100:.1f}%)")

    # --- 2. Trajectoire déterministe combinée (mensuel/annuel) ---
    print("\n" + "=" * 100)
    print("TRAJECTOIRE DÉTERMINISTE COMBINÉE (chronologie réelle) — ventilation mensuelle/annuelle")
    print("=" * 100)
    accounts, events, n_taken_det, net_profit_det = run_fleet_deterministic(
        trades, slot_arrivals, RISK_PCT, market_data, excluded_map
    )
    print(f"Signaux pris (déterministe) : {n_taken_det}/{len(sub)} ({n_taken_det/len(sub)*100:.1f}%)")
    print(f"Profit net combiné (déterministe) : {net_profit_det:+,.0f}€")
    for i, acc in enumerate(accounts):
        print(f"  Compte {i+1} : palier final {acc['palier']}€, casses {acc['broken_count']}, "
              f"net {acc['total_trading_pnl'] - acc['total_fees_paid']:+,.0f}€")

    ev_df = pd.DataFrame(events, columns=["date", "net", "combined_palier"])
    start_date = sub["date_creation"].iloc[0]
    ev_df["month_index"] = ev_df["date"].apply(lambda d: (d.year - start_date.year) * 12 + (d.month - start_date.month))
    n_months = ev_df["month_index"].max() + 1

    monthly = ev_df.groupby("month_index").agg(
        net=("net", "sum"), palier_ref=("combined_palier", "last")
    ).reindex(range(n_months))
    monthly["palier_ref"] = monthly["palier_ref"].ffill().bfill()
    monthly["net"] = monthly["net"].fillna(0.0)
    monthly_net = monthly["net"]

    # % mensuel = net du mois / capital combiné COURANT (somme des paliers des 3
    # comptes à ce moment, PAS le capital de départ fixe 3x50k qui gonflerait la
    # variance dès qu'un compte scale à un palier supérieur).
    monthly_pct = monthly["net"] / monthly["palier_ref"] * 100
    print(f"\nRendement mensuel combiné (%, base = capital combiné courant des 3 comptes) sur {n_months} mois :")
    print(f"  Moyenne    : {monthly_pct.mean():+.2f}%")
    print(f"  Écart-type : {monthly_pct.std():.2f}%")
    print(f"  Médiane    : {monthly_pct.median():+.2f}%")

    cum_net = monthly_net.cumsum()
    print("\nProfit cumulé combiné en fin d'année :")
    for year in range(1, 6):
        end_m = year * 12 - 1
        if end_m >= n_months:
            covered = n_months - (year - 1) * 12
            if covered <= 0:
                break
            print(f"  Fin année {year} (PARTIEL, {covered}/12 mois) : {cum_net.iloc[-1]:+,.0f}€")
            break
        print(f"  Fin année {year} : {cum_net.iloc[end_m]:+,.0f}€")

    pd.DataFrame([{"scenario": "flotte_3_comptes", **mc, "mean_n_taken": mean_n_taken}]).to_csv(
        "fleet_simulation_summary.csv", index=False
    )
    print("\nRésumé enregistré dans fleet_simulation_summary.csv")


if __name__ == "__main__":
    main()
