"""
Scénario COPYTRADE : le MÊME signal est répliqué simultanément sur 3 comptes, une
firm par compte (donc pas de plafond de conformité cross-comptes — 3 firms distinctes,
pas 3 comptes chez la même firm). Chaque compte applique le plafond de 3 positions +
la corrélation 0.6/JPY INDÉPENDAMMENT sur SES PROPRES positions ouvertes (qui
divergent d'un compte à l'autre dès qu'un compte casse/scale différemment) — donc un
signal peut être pris par 0, 1, 2 ou 3 comptes selon l'état de chacun au moment où le
signal arrive. C'est la différence structurelle avec fleet_simulation_test.py : là-bas
un signal va à UN SEUL compte (le moins chargé) ; ici il est TENTÉ sur les 3 en même
temps, indépendamment.

CORRECTIF (2026-08-01) : run_copytrade_one()/simulate_account_with_events() comptaient
AVANT cette date tout le P&L de trading (y compris en phase "challenge", jamais
réellement encaissable) comme profit réel -- même bug corrigé le même soir dans
sizing_fleet_test.py, jamais propagé ici (cf. monte_carlo_simulation.py, même date).
Corrigés ensemble, avec 3 ajouts supplémentaires établis cette nuit sur le risque de
trésorerie perso (real_cash_paid, absent d'ici avant ce correctif) : réserve POOLÉE
(partagée entre les 3 comptes, pas 3 réserves indépendantes), immunité perso
post-1er-financement, et le correctif comptable des 999€ (achat initial des 3
challenges, toujours cash). run_copytrade_one() attend maintenant un `order` déjà
construit par l'appelant (bootstrap PAR BLOC de 2 mois recommandé -- cf.
real_cash_risk_year1_block_bootstrap.py -- au lieu de la permutation simple
utilisée avant, qui sous-estimait la vraie queue de risque). Tout CSV généré via
l'ancienne version (risk_levels_trailing_02/trailing/realistic_summary.csv,
copytrade_vs_fleet_*_summary.csv) surestime le profit net de ~30-40% -- régénéré.
"""
import random
import statistics

import pandas as pd

from scaling_simulation import (
    TIER_SEQUENCE, CHALLENGE_COST, UPGRADE_COST, CHALLENGE_TARGET_PCT,
    MIN_TRADING_DAYS, BREAK_DD_PCT, RESERVE_SHARE, MAX_POSITIONS, CORR_THRESHOLD,
    feasible_risk_pct, load_market_data,
)
from monte_carlo_simulation import run_one, precompute_correlation_pairs, N_SIMULATIONS
from rr_threshold_test import build_extended_population
from fleet_simulation_test import build_trades  # réutilise la construction trades/slot_arrivals
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence

THRESHOLD = 1.5
RISK_PCT = 2.0
N_ACCOUNTS = 3
BLOCK_MONTHS = 2


def build_block_bootstrap_order(trades, slot_arrivals, blocks, block_seconds, rng, target_duration):
    """Construit une séquence bootstrap PAR BLOC de 2 mois (au lieu d'une permutation
    simple) sur l'horizon `target_duration` -- retourne (trades_run, slots_run, order),
    prêt à passer à run_copytrade_one()."""
    trades_run, slots_run = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, target_duration)
    order = list(range(len(trades_run)))
    return trades_run, slots_run, order


def run_copytrade_one(trades, slot_arrivals, risk_pct, market_data, excluded_map, order):
    """Un run : `order` déjà construit par l'appelant (permutation OU, recommandé,
    séquence bootstrap par bloc de 2 mois -- cf. real_cash_risk_year1_block_bootstrap.py
    + reference_metrics_final.build_full_block_bootstrap_sequence), appliqué
    IDENTIQUEMENT aux 3 comptes (même signal répliqué). Réserve POOLÉE (partagée),
    financé-seulement, immunité post-1er-financement, correctif 999€."""
    accounts = []
    for _ in range(N_ACCOUNTS):
        accounts.append({
            "palier": TIER_SEQUENCE[0], "phase": "challenge", "cumulative_since_reset": 0.0,
            "peak_since_reset": 0.0, "trading_days_since_reset": set(), "open_positions": [],
            "total_funded_pnl": 0.0, "total_fees_paid": CHALLENGE_COST[TIER_SEQUENCE[0]],
            "broken_count": 0, "consecutive_breaks": 0, "max_consecutive_breaks": 0,
        })
    reserve = 0.0
    ever_funded = False
    real_cash_paid = CHALLENGE_COST[TIER_SEQUENCE[0]] * N_ACCOUNTS  # correctif 999€

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
                acc["broken_count"] += 1
                acc["consecutive_breaks"] += 1
                acc["max_consecutive_breaks"] = max(acc["max_consecutive_breaks"], acc["consecutive_breaks"])
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
                acc["consecutive_breaks"] = 0

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

    combined_net_profit = sum(a["total_funded_pnl"] - a["total_fees_paid"] for a in accounts)
    combined_broken = sum(a["broken_count"] for a in accounts)
    combined_max_consec = max(a["max_consecutive_breaks"] for a in accounts)
    return {
        "net_profit": combined_net_profit,
        "broken_count": combined_broken,
        "max_consecutive_breaks": combined_max_consec,
        "real_cash_paid": real_cash_paid,
    }


def summarize_copytrade(results):
    profits = sorted(r["net_profit"] for r in results)
    n = len(profits)
    cash = sorted(r.get("real_cash_paid", 0.0) for r in results)
    return {
        "mean_profit": statistics.mean(profits),
        "median_profit": statistics.median(profits),
        "p5_profit": profits[int(0.05 * n)],
        "worst_profit": profits[0],
        "best_profit": profits[-1],
        "pct_loss": sum(1 for p in profits if p < 0) / n * 100,
        "mean_broken_count": statistics.mean(r["broken_count"] for r in results),
        "mean_max_consecutive_breaks": statistics.mean(r["max_consecutive_breaks"] for r in results),
        "max_max_consecutive_breaks": max(r["max_consecutive_breaks"] for r in results),
        "mean_real_cash_paid": statistics.mean(cash),
        "worst_real_cash_paid": cash[-1],
    }


def simulate_account_with_events(trades, slot_arrivals, order, risk_pct, market_data, excluded_map, start_date):
    """Rejoue UN compte sur l'ordre donné (déterministe si order = chronologie réelle),
    en gardant trace des événements (date, net, palier) pour la ventilation
    mensuelle/annuelle — même logique que run_one mais avec journalisation."""
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

        eff_risk, _ = feasible_risk_pct(trade["ticker"], trade["sl_distance"], palier, risk_pct, market_data)
        risk_amount = eff_risk / 100 * palier
        pnl = trade["outcome_r"] * risk_amount

        open_positions.append((trade["ticker"], close_time))
        if phase == "funded":
            total_trading_pnl += pnl  # correctif (2026-08-01) : seul le pnl financé compte
        cumulative_since_reset += pnl
        peak_since_reset = max(peak_since_reset, cumulative_since_reset)
        trading_days_since_reset.add(int(now // 86400))
        events.append((trade["date"], pnl if phase == "funded" else 0.0, palier))

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
    return {
        "net_profit": net_profit, "broken_count": broken_count, "final_tier": palier, "events": events,
    }


def main():
    pop_full, _ = build_extended_population()
    pop = pop_full[pop_full["rr_tp1"] >= THRESHOLD].copy()
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)

    sub, trades, slot_arrivals = build_trades(pop)
    tickers = sorted(set(t["ticker"] for t in trades))
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    print(f"Seuil rr_tp1 >= {THRESHOLD}, risque {RISK_PCT}%, COPYTRADE sur {N_ACCOUNTS} comptes "
          f"(même signal répliqué, chaque compte applique son propre plafond 3 positions + corr 0.6/JPY)")
    print(f"Pool de signaux disponibles : {len(sub)}\n")

    # --- 1-4. Monte Carlo combiné (block bootstrap 2 mois, horizon réel complet) ---
    print("=" * 100)
    print(f"MONTE CARLO COPYTRADE COMBINÉ — {N_SIMULATIONS} simulations (block bootstrap {BLOCK_MONTHS} mois)")
    print("=" * 100)
    block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
    blocks = build_blocks(trades, slot_arrivals, block_seconds)
    total_horizon_seconds = slot_arrivals[-1]

    rng = random.Random(42)
    results = []
    for _ in range(N_SIMULATIONS):
        trades_run, slots_run, order = build_block_bootstrap_order(
            trades, slot_arrivals, blocks, block_seconds, rng, total_horizon_seconds
        )
        results.append(run_copytrade_one(trades_run, slots_run, RISK_PCT, market_data, excluded_map, order))
    mc = summarize_copytrade(results)

    print(f"Profit net combiné moyen   : {mc['mean_profit']:+,.0f}€")
    print(f"Profit net combiné médian  : {mc['median_profit']:+,.0f}€")
    print(f"5e percentile              : {mc['p5_profit']:+,.0f}€")
    print(f"Pire cas / meilleur cas    : {mc['worst_profit']:+,.0f}€ / {mc['best_profit']:+,.0f}€")
    print(f"P(perte nette)             : {mc['pct_loss']:.1f}%")
    print(f"Casses combinées (moyenne) : {mc['mean_broken_count']:.2f}")
    print(f"Max casses consécutives (un compte) : {mc['max_max_consecutive_breaks']}")
    print(f"Trésorerie perso -- moyenne {mc['mean_real_cash_paid']:,.0f}€ | pire cas {mc['worst_real_cash_paid']:,.0f}€")

    # --- Trajectoire déterministe combinée (mensuel/annuel) ---
    print("\n" + "=" * 100)
    print("TRAJECTOIRE DÉTERMINISTE COPYTRADE (chronologie réelle) — ventilation mensuelle/annuelle")
    print("=" * 100)
    natural_order = list(range(len(trades)))
    start_date = sub["date_creation"].iloc[0]
    account_runs = [
        simulate_account_with_events(trades, slot_arrivals, natural_order, RISK_PCT, market_data, excluded_map, start_date)
        for _ in range(N_ACCOUNTS)
    ]
    combined_net_det = sum(r["net_profit"] for r in account_runs)
    print(f"Profit net combiné (déterministe) : {combined_net_det:+,.0f}€")
    for i, r in enumerate(account_runs):
        print(f"  Compte {i+1} : palier final {r['final_tier']}€, casses {r['broken_count']}, net {r['net_profit']:+,.0f}€")

    all_events = []
    for i, r in enumerate(account_runs):
        all_events.extend(r["events"])
    ev_df = pd.DataFrame(all_events, columns=["date", "net", "palier"])
    ev_df["month_index"] = ev_df["date"].apply(lambda d: (d.year - start_date.year) * 12 + (d.month - start_date.month))
    n_months = ev_df["month_index"].max() + 1

    # capital combiné courant = somme des paliers des 3 comptes à cet instant. Comme
    # copytrade traite chaque compte indépendamment, on approxime avec le palier
    # affiché sur CET événement * 3 comptes n'est pas correct (paliers divergent) —
    # on reconstruit donc le palier courant de CHAQUE compte au fil du temps.
    palier_by_month = {}
    for i, r in enumerate(account_runs):
        acc_ev = pd.DataFrame(r["events"], columns=["date", "net", "palier"])
        acc_ev["month_index"] = acc_ev["date"].apply(lambda d: (d.year - start_date.year) * 12 + (d.month - start_date.month))
        last_palier_per_month = acc_ev.groupby("month_index")["palier"].last().reindex(range(n_months)).ffill().bfill()
        palier_by_month[i] = last_palier_per_month

    combined_palier_by_month = sum(palier_by_month.values())
    monthly_net = ev_df.groupby("month_index")["net"].sum().reindex(range(n_months), fill_value=0.0)
    monthly_pct = monthly_net / combined_palier_by_month * 100

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

    pd.DataFrame([{"scenario": "copytrade_3_comptes", **mc}]).to_csv("copytrade_simulation_summary.csv", index=False)
    print("\nRésumé enregistré dans copytrade_simulation_summary.csv")


if __name__ == "__main__":
    main()
