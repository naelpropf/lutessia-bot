"""
Exploration de la viabilite de The5%ers dans la flotte compte tenu de son daily DD
strict a 3% (vs 5% FTMO/Blueberry). Six scenarios, tous batis sur le moteur corrige
`the5ers_summer_100k_N_accounts_dailydd.py` / `three_firm_fleet_dailydd.py` (daily DD
reel + trailing 10% + block bootstrap 2 mois, 2000 simulations MC par config).

S1 - Sensibilite au seuil : daily DD hypothetique 5% au lieu de 3% sur The5%ers seul.
S2 - Risque reduit permanent sur The5%ers (1% et 0.5% au lieu de 2%).
S3 - Tremplin Phase 1 : The5%ers a 0.5%, plafonne a PHASE1_CAP_TRADES par compte, puis
     laisse au repos ; croissance FTMO+Blueberry inchangee (regime A, 2%).
S4 - Sizing contraint par le budget DD journalier (risque/trade <= daily_loss/max_pos).
S5 - Plafond de positions simultanees reduit a 1 sur The5%ers.
S6 - Cout d'entree pur : 4x100k vs 3x50k, meme regime (0.5%), daily DD desactive.

Chaque scenario ecrit son propre CSV (detail + resume) et le tableau de synthese final
est ecrit dans the5ers_viability_scenarios_summary.csv.
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
BLOCK_MONTHS = 2

WINRATES = [("37.29%", None), ("32%", 0.32)]

PALIER_100K = 100000
CHALLENGE_COST_100K = 179
PALIER_50K = 50000
CHALLENGE_COST_50K = 333

DISABLED_DAILY_PCT = 1000.0  # cle pour desactiver la limite journaliere (S6)
PHASE1_CAP_TRADES = 15


# ---------------------------------------------------------------------------
# Moteur generique (une seule flotte The5%ers, N comptes identiques)
# ---------------------------------------------------------------------------

def run_5ers_fleet(trades, slot_arrivals, market_data, excluded_map, order, mark_seconds_list,
                    n_accounts, palier, challenge_cost, daily_loss_pct, low_risk, high_risk,
                    ramp_trades, max_positions, phase1_cap_trades=None, per_trade_cap_pct=None):
    accounts = []
    for _ in range(n_accounts):
        accounts.append({
            "phase": "challenge", "cumulative_since_reset": 0.0,
            "peak_since_reset": 0.0, "trading_days_since_reset": set(), "open_positions": [],
            "total_funded_pnl": 0.0, "total_fees_paid": challenge_cost,
            "trades_taken": 0, "daily_pnl": {},
        })
    reserve = 0.0
    ever_funded = False
    real_cash_paid = challenge_cost * n_accounts
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
            if phase1_cap_trades is not None and acc["trades_taken"] >= phase1_cap_trades:
                continue

            close_time = now + trade["hold_seconds"]
            acc["open_positions"] = [(t, c) for (t, c) in acc["open_positions"] if c > now]
            if len(acc["open_positions"]) >= max_positions:
                continue
            if any(t in excluded_map[trade["ticker"]] for (t, _) in acc["open_positions"]):
                continue

            current_risk = low_risk if acc["trades_taken"] < ramp_trades else high_risk
            if per_trade_cap_pct is not None:
                current_risk = min(current_risk, per_trade_cap_pct)
            eff_risk, _ = feasible_risk_pct(trade["ticker"], trade["sl_distance"], palier, current_risk, market_data)
            risk_amount = eff_risk / 100 * palier
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
            broke = (trailing_dd >= BREAK_DD_PCT / 100 * palier
                     or daily_dd >= daily_loss_pct / 100 * palier)

            if broke:
                total_breaks += 1
                if reserve >= challenge_cost:
                    reserve -= challenge_cost
                else:
                    shortfall = challenge_cost - reserve
                    reserve = 0.0
                    if not ever_funded:
                        real_cash_paid += shortfall
                acc["total_fees_paid"] += challenge_cost
                acc["phase"] = "challenge"
                acc["cumulative_since_reset"] = 0.0
                acc["peak_since_reset"] = 0.0
                acc["trading_days_since_reset"] = set()
                acc["daily_pnl"] = {}
                continue

            if (acc["phase"] == "challenge"
                    and acc["cumulative_since_reset"] >= CHALLENGE_TARGET_PCT / 100 * palier
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


def run_variant(trades, slot_arrivals, blocks, block_seconds, target_duration, mark_seconds_list,
                 market_data, excluded_map, **engine_kwargs):
    rng = random.Random(42)
    rows = []
    for _ in range(N_SIMULATIONS):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, target_duration)
        order = list(range(len(raw_trades)))
        snaps = run_5ers_fleet(raw_trades, raw_slots, market_data, excluded_map, order, mark_seconds_list,
                                **engine_kwargs)
        rows.append({
            "year1_net": snaps[0][1], "year1_cash": snaps[0][2], "year1_breaks": snaps[0][3],
            "final_net": snaps[1][1], "final_cash": snaps[1][2], "final_breaks": snaps[1][3],
        })
    return pd.DataFrame(rows)


def run_variant_tremplin(trades, slot_arrivals, blocks, block_seconds, target_duration, mark_seconds_list,
                          market_data, excluded_map, n_5ers, phase1_cap_trades):
    """S3 : segment The5%ers plafonne (tremplin) + segment croissance FTMO/Blueberry
    inchange (regime A, 2%, reutilise tel quel depuis three_firm_fleet_dailydd)."""
    rng = random.Random(42)
    rows = []
    for _ in range(N_SIMULATIONS):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, target_duration)
        order = list(range(len(raw_trades)))

        snaps_5ers = run_5ers_fleet(
            raw_trades, raw_slots, market_data, excluded_map, order, mark_seconds_list,
            n_accounts=n_5ers, palier=PALIER_100K, challenge_cost=CHALLENGE_COST_100K,
            daily_loss_pct=3.0, low_risk=0.5, high_risk=0.5, ramp_trades=0,
            max_positions=DEFAULT_MAX_POSITIONS, phase1_cap_trades=phase1_cap_trades,
        )
        snaps_growth, _ = fleet3.run_growth_segment(raw_trades, raw_slots, market_data, excluded_map, order, mark_seconds_list)

        rows.append({
            "year1_net": snaps_5ers[0][1] + snaps_growth[0][1],
            "year1_cash": snaps_5ers[0][2] + snaps_growth[0][2],
            "year1_breaks": snaps_5ers[0][3] + snaps_growth[0][3],
            "final_net": snaps_5ers[1][1] + snaps_growth[1][1],
            "final_cash": snaps_5ers[1][2] + snaps_growth[1][2],
            "final_breaks": snaps_5ers[1][3] + snaps_growth[1][3],
            "year1_net_5ers": snaps_5ers[0][1], "year1_net_growth": snaps_growth[0][1],
            "final_net_5ers": snaps_5ers[1][1], "final_net_growth": snaps_growth[1][1],
        })
    return pd.DataFrame(rows)


def build_population(pop, target_winrate):
    if target_winrate is None:
        return build_trades_trailing(pop)[1:]
    rng = random.Random(DEGRADE_SEED)
    _, trades, slot_arrivals, _ = build_degraded_trades(pop, target_winrate, rng)
    return trades, slot_arrivals


def summarize(df, label, extra=None):
    cash = df["final_cash"]
    row = {
        "scenario": label,
        "profit_year1_moyen": df["year1_net"].mean(),
        "profit_final_moyen": df["final_net"].mean(),
        "pct_loss_year1": (df["year1_net"] < 0).mean() * 100,
        "cash_worst": cash.max(), "cash_mean": cash.mean(),
        "casses_moyennes_final": df["final_breaks"].mean(),
    }
    if extra:
        row.update(extra)
    return row


def main():
    t_start = time.time()
    pop = build_population_with_trailing("fixed", 0.2, verbose=False)
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    synthesis_rows = []

    for wr_label, wr_target in WINRATES:
        print(f"\n{'='*100}\nWINRATE {wr_label}\n{'='*100}")
        trades, slot_arrivals = build_population(pop, wr_target)
        total_horizon_seconds = slot_arrivals[-1]
        mark_seconds_list = [YEAR_SECONDS, total_horizon_seconds]
        block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
        blocks = build_blocks(trades, slot_arrivals, block_seconds)
        common_args = (trades, slot_arrivals, blocks, block_seconds, total_horizon_seconds,
                       mark_seconds_list, market_data, excluded_map)

        # ---------------- S1 : sensibilite au seuil (5% hypothetique vs 3% reel) ----------------
        for n in [3, 4]:
            t0 = time.time()
            df = run_variant(*common_args, n_accounts=n, palier=PALIER_100K, challenge_cost=CHALLENGE_COST_100K,
                              daily_loss_pct=5.0, low_risk=0.5, high_risk=2.0, ramp_trades=12,
                              max_positions=DEFAULT_MAX_POSITIONS)
            df.to_csv(f"scenario1_5ers_N{n}_daily5pct_{wr_label.replace('%','pct').replace('.','_')}.csv", index=False)
            row = summarize(df, f"S1 - daily 5% hypothetique (N={n})", {"winrate": wr_label, "n_accounts": n})
            synthesis_rows.append(row)
            print(f"S1 N={n} daily=5% : profit final {row['profit_final_moyen']:+,.0f}$ | casses {row['casses_moyennes_final']:.1f} ({time.time()-t0:.0f}s)")

        # ---------------- S2 : risque reduit permanent (1% et 0.5%), daily reel 3% ----------------
        for risk in [1.0, 0.5]:
            t0 = time.time()
            df = run_variant(*common_args, n_accounts=4, palier=PALIER_100K, challenge_cost=CHALLENGE_COST_100K,
                              daily_loss_pct=3.0, low_risk=risk, high_risk=risk, ramp_trades=0,
                              max_positions=DEFAULT_MAX_POSITIONS)
            df.to_csv(f"scenario2_5ers_risk{str(risk).replace('.','_')}pct_{wr_label.replace('%','pct').replace('.','_')}.csv", index=False)
            row = summarize(df, f"S2 - risque reduit {risk}% (N=4)", {"winrate": wr_label, "n_accounts": 4})
            synthesis_rows.append(row)
            print(f"S2 risk={risk}% : profit final {row['profit_final_moyen']:+,.0f}$ | casses {row['casses_moyennes_final']:.1f} ({time.time()-t0:.0f}s)")

        # ---------------- S3 : tremplin Phase 1 (0.5%, plafonne) + croissance FTMO/Blueberry ----------------
        t0 = time.time()
        df = run_variant_tremplin(*common_args, n_5ers=4, phase1_cap_trades=PHASE1_CAP_TRADES)
        df.to_csv(f"scenario3_tremplin_{wr_label.replace('%','pct').replace('.','_')}.csv", index=False)
        row = summarize(df, "S3 - tremplin Phase1 (5ers 0.5% plafonne 15 trades) + croissance 2%",
                         {"winrate": wr_label, "n_accounts": 4,
                          "profit_final_5ers": df["final_net_5ers"].mean(),
                          "profit_final_growth": df["final_net_growth"].mean()})
        synthesis_rows.append(row)
        print(f"S3 tremplin : profit final {row['profit_final_moyen']:+,.0f}$ (5ers {row['profit_final_5ers']:+,.0f}$ / croissance {row['profit_final_growth']:+,.0f}$) | casses {row['casses_moyennes_final']:.1f} ({time.time()-t0:.0f}s)")

        # ---------------- S4 : sizing contraint par le budget DD journalier ----------------
        per_trade_cap = 3.0 / DEFAULT_MAX_POSITIONS  # 3% / 3 positions = 1.0%
        t0 = time.time()
        df = run_variant(*common_args, n_accounts=4, palier=PALIER_100K, challenge_cost=CHALLENGE_COST_100K,
                          daily_loss_pct=3.0, low_risk=0.5, high_risk=2.0, ramp_trades=12,
                          max_positions=DEFAULT_MAX_POSITIONS, per_trade_cap_pct=per_trade_cap)
        df.to_csv(f"scenario4_sizing_budget_{wr_label.replace('%','pct').replace('.','_')}.csv", index=False)
        row = summarize(df, f"S4 - sizing plafonne budget DD ({per_trade_cap:.2f}%/trade max)",
                         {"winrate": wr_label, "n_accounts": 4})
        synthesis_rows.append(row)
        print(f"S4 sizing budget : profit final {row['profit_final_moyen']:+,.0f}$ | casses {row['casses_moyennes_final']:.1f} ({time.time()-t0:.0f}s)")

        # ---------------- S5 : 1 position max au lieu de 3 ----------------
        t0 = time.time()
        df = run_variant(*common_args, n_accounts=4, palier=PALIER_100K, challenge_cost=CHALLENGE_COST_100K,
                          daily_loss_pct=3.0, low_risk=0.5, high_risk=2.0, ramp_trades=12,
                          max_positions=1)
        df.to_csv(f"scenario5_maxpos1_{wr_label.replace('%','pct').replace('.','_')}.csv", index=False)
        row = summarize(df, "S5 - 1 position max (au lieu de 3)", {"winrate": wr_label, "n_accounts": 4})
        synthesis_rows.append(row)
        print(f"S5 maxpos=1 : profit final {row['profit_final_moyen']:+,.0f}$ | casses {row['casses_moyennes_final']:.1f} ({time.time()-t0:.0f}s)")

        # ---------------- S6 : cout d'entree pur, 4x100k vs 3x50k, meme regime 0.5%, daily off ----------------
        mark_seconds_year1_only = [YEAR_SECONDS, YEAR_SECONDS]  # duplique : year1==final pour ce scenario 12 mois
        common_args_y1 = (trades, slot_arrivals, blocks, block_seconds, total_horizon_seconds,
                          mark_seconds_year1_only, market_data, excluded_map)
        t0 = time.time()
        df_100k = run_variant(*common_args_y1, n_accounts=4, palier=PALIER_100K, challenge_cost=CHALLENGE_COST_100K,
                               daily_loss_pct=DISABLED_DAILY_PCT, low_risk=0.5, high_risk=0.5, ramp_trades=0,
                               max_positions=DEFAULT_MAX_POSITIONS)
        row100 = {
            "scenario": "S6 - 4x100k @0.5%, daily off, 12 mois", "winrate": wr_label, "n_accounts": 4,
            "profit_year1_moyen": df_100k["year1_net"].mean(), "profit_final_moyen": df_100k["year1_net"].mean(),
            "pct_loss_year1": (df_100k["year1_net"] < 0).mean() * 100,
            "cash_worst": df_100k["year1_cash"].max(), "cash_mean": df_100k["year1_cash"].mean(),
            "casses_moyennes_final": df_100k["year1_breaks"].mean(),
            "cout_entree_total": CHALLENGE_COST_100K * 4,
        }
        synthesis_rows.append(row100)

        df_50k = run_variant(*common_args_y1, n_accounts=3, palier=PALIER_50K, challenge_cost=CHALLENGE_COST_50K,
                              daily_loss_pct=DISABLED_DAILY_PCT, low_risk=0.5, high_risk=0.5, ramp_trades=0,
                              max_positions=DEFAULT_MAX_POSITIONS)
        row50 = {
            "scenario": "S6 - 3x50k @0.5%, daily off, 12 mois", "winrate": wr_label, "n_accounts": 3,
            "profit_year1_moyen": df_50k["year1_net"].mean(), "profit_final_moyen": df_50k["year1_net"].mean(),
            "pct_loss_year1": (df_50k["year1_net"] < 0).mean() * 100,
            "cash_worst": df_50k["year1_cash"].max(), "cash_mean": df_50k["year1_cash"].mean(),
            "casses_moyennes_final": df_50k["year1_breaks"].mean(),
            "cout_entree_total": CHALLENGE_COST_50K * 3,
        }
        synthesis_rows.append(row50)
        df_100k.to_csv(f"scenario6_4x100k_{wr_label.replace('%','pct').replace('.','_')}.csv", index=False)
        df_50k.to_csv(f"scenario6_3x50k_{wr_label.replace('%','pct').replace('.','_')}.csv", index=False)
        print(f"S6 4x100k : profit an1 {row100['profit_year1_moyen']:+,.0f}$ | cout entree {row100['cout_entree_total']}$ | casses {row100['casses_moyennes_final']:.1f}")
        print(f"S6 3x50k  : profit an1 {row50['profit_year1_moyen']:+,.0f}$ | cout entree {row50['cout_entree_total']}$ | casses {row50['casses_moyennes_final']:.1f} ({time.time()-t0:.0f}s)")

    synth_df = pd.DataFrame(synthesis_rows)
    synth_df.to_csv("the5ers_viability_scenarios_summary.csv", index=False)
    print(f"\nTerminé en {time.time()-t_start:.0f}s. Résumé enregistré dans the5ers_viability_scenarios_summary.csv")


if __name__ == "__main__":
    main()
