"""
Point 2/3 de la relance : chiffre l'ajout de Ment Funding, en complement de
FXIFY, a la flotte existante.

HYPOTHESE VOLONTAIREMENT CONSERVATRICE (point 2 non totalement resolu) :
aucun plafond de capital combine explicite n'a ete trouve chez Ment Funding
malgre recherche approfondie (seule regle trouvee : anti-abus de leaderboard,
pas anti-multi-comptes). Faute de confirmation officielle (contrairement au
plafond 500k$ de The5%ers, confirme par leur support), ce script modelise
UN SEUL compte 2M$ (le produit le plus eleve explicitement vendu, sans
ambiguite sur sa disponibilite) plutot que de supposer un multiple non
confirme. C'est donc une BORNE BASSE du potentiel reel si plusieurs comptes
s'averent effectivement autorises.

Regles utilisees (sourcees ce soir, cf. reponse chat) : cout challenge 2M$ =
17 200$ (thepropfirmguide.com, 1-step evaluation, meme regle que les autres
paliers). Daily loss 2.5% (regle specifique au palier 2M$, plus stricte que
les 5% des paliers inferieurs, source WebSearch). Max drawdown 6% trailing
(majorite des sources, meme si une source de mentfunding.com evoquait
"statique" -- incertitude non resolue, presentee comme telle).
"""
import random
import time

import pandas as pd

from scaling_simulation import (
    CHALLENGE_TARGET_PCT, MIN_TRADING_DAYS, RESERVE_SHARE, MAX_POSITIONS,
    CORR_THRESHOLD, feasible_risk_pct, load_market_data,
)
from monte_carlo_simulation import precompute_correlation_pairs, N_SIMULATIONS
from trailing_payoff_population import build_population_with_trailing, build_trades_trailing
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from winrate_sensitivity_test import build_degraded_trades, DEGRADE_SEED

YEAR_SECONDS = 365.25 * 86400
BLOCK_MONTHS = 2
LOW_RISK, HIGH_RISK, RAMP_TRADES = 0.5, 2.0, 12

MENT_PALIER = 2000000
MENT_COST = 17200
MENT_DAILY_LOSS_PCT = 2.5
MENT_MAX_DD_PCT = 6.0  # trailing (majorite des sources ; 1 source dit statique, incertain)


def run_ment_fleet(trades, slot_arrivals, market_data, excluded_map, order, mark_seconds_list):
    acc = {"phase": "challenge", "cumulative_since_reset": 0.0, "peak_since_reset": 0.0,
           "trading_days_since_reset": set(), "open_positions": [], "total_funded_pnl": 0.0,
           "total_fees_paid": MENT_COST, "trades_taken": 0, "daily_pnl": {}}
    reserve = 0.0
    ever_funded = False
    real_cash_paid = MENT_COST
    total_breaks = 0

    marks_sorted = sorted(mark_seconds_list)
    mark_idx = 0
    snapshots = []

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]

        while mark_idx < len(marks_sorted) and now > marks_sorted[mark_idx]:
            snapshots.append((marks_sorted[mark_idx], acc["total_funded_pnl"] - acc["total_fees_paid"],
                               real_cash_paid, total_breaks))
            mark_idx += 1

        close_time = now + trade["hold_seconds"]
        acc["open_positions"] = [(t, c) for (t, c) in acc["open_positions"] if c > now]
        if len(acc["open_positions"]) >= MAX_POSITIONS:
            continue
        if any(t in excluded_map[trade["ticker"]] for (t, _) in acc["open_positions"]):
            continue

        current_risk = LOW_RISK if acc["trades_taken"] < RAMP_TRADES else HIGH_RISK
        eff_risk, _ = feasible_risk_pct(trade["ticker"], trade["sl_distance"], MENT_PALIER, current_risk, market_data)
        risk_amount = eff_risk / 100 * MENT_PALIER
        pnl = trade["outcome_r"] * risk_amount

        acc["open_positions"].append((trade["ticker"], close_time))
        acc["cumulative_since_reset"] += pnl
        acc["peak_since_reset"] = max(acc["peak_since_reset"], acc["cumulative_since_reset"])
        acc["trading_days_since_reset"].add(int(now // 86400))
        acc["trades_taken"] += 1
        close_day = int(close_time // 86400)
        acc["daily_pnl"][close_day] = acc["daily_pnl"].get(close_day, 0.0) + pnl

        if acc["phase"] == "funded":
            acc["total_funded_pnl"] += pnl
            if pnl > 0:
                reserve += pnl * RESERVE_SHARE

        trailing_dd = acc["peak_since_reset"] - acc["cumulative_since_reset"]
        daily_dd = -acc["daily_pnl"][close_day]
        broke = (trailing_dd >= MENT_MAX_DD_PCT / 100 * MENT_PALIER
                 or daily_dd >= MENT_DAILY_LOSS_PCT / 100 * MENT_PALIER)

        if broke:
            total_breaks += 1
            if reserve >= MENT_COST:
                reserve -= MENT_COST
            else:
                shortfall = MENT_COST - reserve
                reserve = 0.0
                if not ever_funded:
                    real_cash_paid += shortfall
            acc["total_fees_paid"] += MENT_COST
            acc["phase"] = "challenge"
            acc["cumulative_since_reset"] = 0.0
            acc["peak_since_reset"] = 0.0
            acc["trading_days_since_reset"] = set()
            acc["daily_pnl"] = {}
            continue

        if (acc["phase"] == "challenge" and acc["cumulative_since_reset"] >= CHALLENGE_TARGET_PCT / 100 * MENT_PALIER
                and len(acc["trading_days_since_reset"]) >= MIN_TRADING_DAYS):
            acc["phase"] = "funded"
            ever_funded = True
            acc["cumulative_since_reset"] = 0.0
            acc["peak_since_reset"] = 0.0
            acc["trading_days_since_reset"] = set()

    while mark_idx < len(marks_sorted):
        snapshots.append((marks_sorted[mark_idx], acc["total_funded_pnl"] - acc["total_fees_paid"],
                           real_cash_paid, total_breaks))
        mark_idx += 1
    return snapshots


def run_variant(trades, slot_arrivals, blocks, block_seconds, target_duration, mark_seconds_list,
                 market_data, excluded_map):
    rng = random.Random(42)
    rows = []
    for _ in range(N_SIMULATIONS):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, target_duration)
        order = list(range(len(raw_trades)))
        snaps = run_ment_fleet(raw_trades, raw_slots, market_data, excluded_map, order, mark_seconds_list)
        rows.append({
            "year1_net": snaps[0][1], "year1_cash": snaps[0][2], "year1_breaks": snaps[0][3],
            "final_net": snaps[1][1], "final_cash": snaps[1][2], "final_breaks": snaps[1][3],
        })
    return pd.DataFrame(rows)


def build_population(pop, target_winrate):
    if target_winrate is None:
        return build_trades_trailing(pop)[1:]
    rng = random.Random(DEGRADE_SEED)
    _, trades, slot_arrivals, _ = build_degraded_trades(pop, target_winrate, rng)
    return trades, slot_arrivals


def main():
    t_start = time.time()
    pop = build_population_with_trailing("fixed", 0.2, verbose=False)
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    rows = []
    for wr_label, wr_target, suffix in [("37.29%", None, "37_29pct"), ("32%", 0.32, "32pct")]:
        trades, slot_arrivals = build_population(pop, wr_target)
        total_horizon_seconds = slot_arrivals[-1]
        mark_seconds_list = [YEAR_SECONDS, total_horizon_seconds]
        block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
        blocks = build_blocks(trades, slot_arrivals, block_seconds)

        t0 = time.time()
        df = run_variant(trades, slot_arrivals, blocks, block_seconds, total_horizon_seconds,
                          mark_seconds_list, market_data, excluded_map)
        df.to_csv(f"ment_fleet_{suffix}.csv", index=False)
        row = dict(winrate=wr_label, profit_year1=df["year1_net"].mean(), profit_final=df["final_net"].mean(),
                   cash_worst=df["final_cash"].max(), casses_final=df["final_breaks"].mean())
        rows.append(row)
        print(f"{wr_label} : Ment Funding 1x2M profit final {row['profit_final']:+,.0f}$ | "
              f"cash pire cas {row['cash_worst']:,.0f}$ | casses {row['casses_final']:.1f} ({time.time()-t0:.0f}s)")

    pd.DataFrame(rows).to_csv("ment_fleet_summary.csv", index=False)
    print(f"Terminé en {time.time()-t_start:.0f}s.")


if __name__ == "__main__":
    main()
