"""
Point 1 + Point 3 de la relance d'analyse viabilite The5%ers.

CONSTAT (verification methodologique, point 1) : tous les moteurs existants
(the5ers_summer_100k_N_accounts_dailydd.py, three_firm_fleet_dailydd.py,
the5ers_viability_scenarios.py) utilisent CHALLENGE_COST_100K = 179$ comme cout
de rachat a CHAQUE casse, de facon perpetuelle sur tout l'horizon simule
(~3.96 ans). Aucune bascule vers un prix plein tarif n'existe dans le code.
C'est une hypothese optimiste : le Summer Plan est une offre explicitement
"limited time" (ete 2026), sans date de fin publique (the5ers.com/summer-plan/,
verifie ce soir), et rien ne garantit son maintien sur 4 ans. Prix normal
sourcé pour le 100K 2-Step High Stakes hors promo : ~495$ (propfirmmatch.com,
dec. 2024 ; la fourchette marche generale pour une eval 100K est 300-600$
selon plusieurs sources prop firm consultees ce soir).

Ce script :
- S1bis (point 1) : regenere les chiffres 5ers-seul ET flotte-3-firms avec un
  rachat a 179$ seulement pendant les X premiers mois (X in {12,18,24}, testes
  par sensibilite), puis 495$ ensuite, sur toute la duree restante.
- S3bis (point 3) : risque PLEIN 2% (pas reduit, contrairement au tremplin du
  scenario 3 precedent), rachat a 179$ tant que l'offre dure (X mois), PUIS
  ARRET TOTAL des rachats sur The5%ers (pas de bascule a 495$, capital de
  croissance redirige vers FTMO/Blueberry qui restent inchanges).
"""
import random
import time

import pandas as pd

from scaling_simulation import (
    CHALLENGE_TARGET_PCT, MIN_TRADING_DAYS, BREAK_DD_PCT, RESERVE_SHARE,
    MAX_POSITIONS as DEFAULT_MAX_POSITIONS, CORR_THRESHOLD, feasible_risk_pct, load_market_data,
)
from monte_carlo_simulation import precompute_correlation_pairs, N_SIMULATIONS
from trailing_payoff_population import build_population_with_trailing, build_trades_trailing
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from winrate_sensitivity_test import build_degraded_trades, DEGRADE_SEED
import three_firm_fleet_dailydd as fleet3

YEAR_SECONDS = 365.25 * 86400
MONTH_SECONDS = YEAR_SECONDS / 12
BLOCK_MONTHS = 2

PALIER_100K = 100000
SUMMER_COST = 179
POST_SUMMER_COST = 495  # source : propfirmmatch.com (100K High Stakes 2-Step, hors promo)
DAILY_LOSS_PCT_5ERS = 3.0
LOW_RISK, HIGH_RISK, RAMP_TRADES = 0.5, 2.0, 12
MAX_POSITIONS = DEFAULT_MAX_POSITIONS

CUTOFF_MONTHS_SENSITIVITY = [12, 18, 24]  # point 1 : sensibilite date de fin d'offre
CUTOFF_MONTHS_POINT3 = [6, 12]  # point 3 : arret programme, plage suggeree par l'utilisateur


def run_5ers_fleet_pricing(trades, slot_arrivals, market_data, excluded_map, order, mark_seconds_list,
                            n_accounts, cutoff_seconds, mode):
    """mode='switch' : rachat 179$ avant cutoff, 495$ apres (point 1, hypothese realiste).
    mode='freeze'    : rachat 179$ avant cutoff, ARRET total des rachats apres (point 3)."""
    accounts = []
    for _ in range(n_accounts):
        accounts.append({
            "phase": "challenge", "cumulative_since_reset": 0.0,
            "peak_since_reset": 0.0, "trading_days_since_reset": set(), "open_positions": [],
            "total_funded_pnl": 0.0, "total_fees_paid": SUMMER_COST,
            "trades_taken": 0, "daily_pnl": {}, "frozen": False,
        })
    reserve = 0.0
    ever_funded = False
    real_cash_paid = SUMMER_COST * n_accounts
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
            if acc["frozen"]:
                continue
            close_time = now + trade["hold_seconds"]
            acc["open_positions"] = [(t, c) for (t, c) in acc["open_positions"] if c > now]
            if len(acc["open_positions"]) >= MAX_POSITIONS:
                continue
            if any(t in excluded_map[trade["ticker"]] for (t, _) in acc["open_positions"]):
                continue

            current_risk = LOW_RISK if acc["trades_taken"] < RAMP_TRADES else HIGH_RISK
            eff_risk, _ = feasible_risk_pct(trade["ticker"], trade["sl_distance"], PALIER_100K, current_risk, market_data)
            risk_amount = eff_risk / 100 * PALIER_100K
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
            broke = (trailing_dd >= BREAK_DD_PCT / 100 * PALIER_100K
                     or daily_dd >= DAILY_LOSS_PCT_5ERS / 100 * PALIER_100K)

            if broke:
                total_breaks += 1
                if now >= cutoff_seconds and mode == "freeze":
                    acc["frozen"] = True
                    acc["cumulative_since_reset"] = 0.0
                    acc["peak_since_reset"] = 0.0
                    acc["trading_days_since_reset"] = set()
                    acc["daily_pnl"] = {}
                    continue

                rebuy_cost = POST_SUMMER_COST if (mode == "switch" and now >= cutoff_seconds) else SUMMER_COST
                if reserve >= rebuy_cost:
                    reserve -= rebuy_cost
                else:
                    shortfall = rebuy_cost - reserve
                    reserve = 0.0
                    if not ever_funded:
                        real_cash_paid += shortfall
                acc["total_fees_paid"] += rebuy_cost
                acc["phase"] = "challenge"
                acc["cumulative_since_reset"] = 0.0
                acc["peak_since_reset"] = 0.0
                acc["trading_days_since_reset"] = set()
                acc["daily_pnl"] = {}
                continue

            if (acc["phase"] == "challenge"
                    and acc["cumulative_since_reset"] >= CHALLENGE_TARGET_PCT / 100 * PALIER_100K
                    and len(acc["trading_days_since_reset"]) >= MIN_TRADING_DAYS):
                acc["phase"] = "funded"
                ever_funded = True
                acc["cumulative_since_reset"] = 0.0
                acc["peak_since_reset"] = 0.0
                acc["trading_days_since_reset"] = set()

    while mark_idx < len(marks_sorted):
        combined_net = sum(a["total_funded_pnl"] - a["total_fees_paid"] for a in accounts)
        snapshots.append((marks_sorted[mark_idx], combined_net, real_cash_paid, total_breaks))
        mark_idx += 1

    return snapshots


def run_variant_5ers_only(trades, slot_arrivals, blocks, block_seconds, target_duration, mark_seconds_list,
                           market_data, excluded_map, n_accounts, cutoff_seconds, mode):
    rng = random.Random(42)
    rows = []
    for _ in range(N_SIMULATIONS):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, target_duration)
        order = list(range(len(raw_trades)))
        snaps = run_5ers_fleet_pricing(raw_trades, raw_slots, market_data, excluded_map, order, mark_seconds_list,
                                        n_accounts, cutoff_seconds, mode)
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

    rows_5ers_only = []
    rows_flotte = []

    for wr_label, wr_target, suffix in [("37.29%", None, "37_29pct"), ("32%", 0.32, "32pct")]:
        print(f"\n{'='*100}\nWINRATE {wr_label}\n{'='*100}")
        trades, slot_arrivals = build_population(pop, wr_target)
        total_horizon_seconds = slot_arrivals[-1]
        mark_seconds_list = [YEAR_SECONDS, total_horizon_seconds]
        block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
        blocks = build_blocks(trades, slot_arrivals, block_seconds)
        common_args = (trades, slot_arrivals, blocks, block_seconds, total_horizon_seconds,
                       mark_seconds_list, market_data, excluded_map)

        gc = pd.read_csv(f"growth_only_cash_{suffix}.csv")
        g = pd.read_csv(f"three_firm_fleet_dailydd_{suffix}.csv")

        # ---------------- Point 1 : prix realiste (bascule 179->495), sensibilite cutoff ----------------
        for cutoff_m in CUTOFF_MONTHS_SENSITIVITY:
            t0 = time.time()
            cutoff_s = cutoff_m * MONTH_SECONDS
            df = run_variant_5ers_only(*common_args, n_accounts=4, cutoff_seconds=cutoff_s, mode="switch")
            df.to_csv(f"scenario1bis_realpricing_switch_cutoff{cutoff_m}m_{suffix}.csv", index=False)

            year1_f = g["year1_net_growth"] + df["year1_net"]
            final_f = g["final_net_growth"] + df["final_net"]
            cash_f = gc["final_cash_growth"] + df["final_cash"]
            breaks_f = gc["final_breaks_growth"] + df["final_breaks"]

            rows_5ers_only.append(dict(
                point="1", scenario=f"Prix realiste (179$ {cutoff_m}m puis 495$)", cutoff_months=cutoff_m,
                winrate=wr_label, n_accounts=4,
                profit_year1=df["year1_net"].mean(), profit_final=df["final_net"].mean(),
                cash_worst=df["final_cash"].max(), casses_final=df["final_breaks"].mean(),
            ))
            rows_flotte.append(dict(
                point="1", scenario=f"Flotte - prix realiste 5ers (179$ {cutoff_m}m puis 495$)", cutoff_months=cutoff_m,
                winrate=wr_label,
                profit_year1=year1_f.mean(), profit_final=final_f.mean(),
                cash_worst=cash_f.max(), casses_final=breaks_f.mean(),
            ))
            print(f"  [P1] cutoff={cutoff_m}m : 5ers seul profit final {df['final_net'].mean():+,.0f}$ | "
                  f"flotte profit final {final_f.mean():+,.0f}$ | flotte cash pire cas {cash_f.max():,.0f}$ "
                  f"| flotte casses {breaks_f.mean():.1f} ({time.time()-t0:.0f}s)")

        # ---------------- Point 3 : plein risque, rachat tant que Summer Plan dure, puis stop ----------------
        for cutoff_m in CUTOFF_MONTHS_POINT3:
            t0 = time.time()
            cutoff_s = cutoff_m * MONTH_SECONDS
            df = run_variant_5ers_only(*common_args, n_accounts=4, cutoff_seconds=cutoff_s, mode="freeze")
            df.to_csv(f"scenario3bis_fullrisk_freeze{cutoff_m}m_{suffix}.csv", index=False)

            year1_f = g["year1_net_growth"] + df["year1_net"]
            final_f = g["final_net_growth"] + df["final_net"]
            cash_f = gc["final_cash_growth"] + df["final_cash"]
            breaks_f = gc["final_breaks_growth"] + df["final_breaks"]

            rows_5ers_only.append(dict(
                point="3", scenario=f"Plein risque 2%, arret rachat apres {cutoff_m}m", cutoff_months=cutoff_m,
                winrate=wr_label, n_accounts=4,
                profit_year1=df["year1_net"].mean(), profit_final=df["final_net"].mean(),
                cash_worst=df["final_cash"].max(), casses_final=df["final_breaks"].mean(),
            ))
            rows_flotte.append(dict(
                point="3", scenario=f"Flotte - 5ers plein risque puis arret apres {cutoff_m}m", cutoff_months=cutoff_m,
                winrate=wr_label,
                profit_year1=year1_f.mean(), profit_final=final_f.mean(),
                cash_worst=cash_f.max(), casses_final=breaks_f.mean(),
            ))
            print(f"  [P3] freeze={cutoff_m}m : 5ers seul profit final {df['final_net'].mean():+,.0f}$ | "
                  f"flotte profit final {final_f.mean():+,.0f}$ | flotte cash pire cas {cash_f.max():,.0f}$ "
                  f"| flotte casses {breaks_f.mean():.1f} ({time.time()-t0:.0f}s)")

        # reference statu quo (deja connue) pour comparaison directe dans le meme tableau
        rows_flotte.append(dict(
            point="ref", scenario="Flotte - statu quo (179$ perpetuel, 2% permanent)", cutoff_months=None,
            winrate=wr_label,
            profit_year1=g["year1_net"].mean(), profit_final=g["final_net"].mean(),
            cash_worst=g["final_cash"].max(), casses_final=g["final_breaks"].mean(),
        ))

    pd.DataFrame(rows_5ers_only).to_csv("point1_3_5ers_only_summary.csv", index=False)
    pd.DataFrame(rows_flotte).to_csv("point1_3_flotte_summary.csv", index=False)
    print(f"\nTerminé en {time.time()-t_start:.0f}s.")


if __name__ == "__main__":
    main()
