"""
Partie A du 06/08 : deux corrections + une nouvelle analyse sur la structure de
DEPART (3 comptes/firms, The5%ers 4x100k + FTMO(2)/Blueberry(1) scaling plafonne).

CORRECTION FTMO (point A.1) : plafonds reels confirmes au site officiel FTMO
(05/08/2026) -- taille de compte INDIVIDUEL max 200 000$ (pas 500 000$), plafond
de capital COMBINE 400 000$ (type "defaut", celui utilise ici) ou 200 000$ (type
"Aggressive", non utilise). L'ancienne sequence TIER_SEQUENCE=[50k,200k,500k]
(scaling_simulation.py) etait partagee entre FTMO et Blueberry -- correcte pour
Blueberry (aucune correction demandee), fausse pour FTMO qui saute directement
de 200k a 500k sans palier intermediaire alors que la vraie progression FTMO est
50k->100k->200k (200k = plafond absolu par compte, jamais 500k). Prix du palier
100k non source officiellement -- APPROXIME proportionnellement au meme ratio
cout/palier que les autres tiers FTMO deja utilises dans ce projet (~0.5-0.67%
du palier) : challenge 100k = 500$, upgrade 50k->100k = 500$. A verifier/corriger
si un prix officiel FTMO 100k est trouve.

Le plafond COMBINE de 400k (FIRM_CAP) reste inchange et continue, comme avant,
a bloquer tout palier superieur meme si la sequence per-firm l'autorisait --
avec la correction FTMO, ce plafond de 400k devient d'ailleurs redondant pour
FTMO seul (200k max/compte * 2 comptes = 400k = exactement le plafond), mais
reste la contrainte active pour Blueberry (1 seul compte, bloque a 200k des
qu'il tente 500k puisque 500k > 400k).

NOUVELLE ANALYSE (point A.3) : la reserve/immunite de ce script est un flag
GLOBAL partage entre les 3 firms (meme design que hybrid_reserve_switch_test.py,
PAS le design "par segment" de three_firm_fleet_dailydd.py) -- des qu'UN SEUL
compte de la flotte (n'importe lequel) finance pour la premiere fois, plus aucun
cassage ulterieur ne tape le cash personnel. On isole donc, dans la fenetre
PRE-IMMUNITE uniquement, la part du cash reellement paye attribuable a chaque
firm (The5%ers vs FTMO vs Blueberry), puis on compare :
  - Variante ACTUELLE : The5%ers demarre en meme temps que FTMO/Blueberry (t=0)
  - Variante RETARDEE : The5%ers ne s'active qu'au moment ou FTMO/Blueberry
    financent un premier compte (immunite globale deja demarree a ce moment,
    donc le cout d'ouverture des 4 comptes The5%ers a ce moment est absorbe par
    la reserve/l'immunite, jamais par le cash personnel)
"""
import random
import time

import pandas as pd

from scaling_simulation import (
    CHALLENGE_TARGET_PCT, MIN_TRADING_DAYS, BREAK_DD_PCT, RESERVE_SHARE,
    MAX_POSITIONS, CORR_THRESHOLD, feasible_risk_pct, load_market_data,
    TIER_SEQUENCE as TIER_SEQUENCE_BB, CHALLENGE_COST as CHALLENGE_COST_BB,
    UPGRADE_COST as UPGRADE_COST_BB,
)
from monte_carlo_simulation import precompute_correlation_pairs, N_SIMULATIONS
from trailing_payoff_population import build_population_with_trailing, build_trades_trailing
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from winrate_sensitivity_test import build_degraded_trades, DEGRADE_SEED

YEAR_SECONDS = 365.25 * 86400
BLOCK_MONTHS = 2
DAY_SECONDS = 86400
LOW_RISK, HIGH_RISK, RAMP_TRADES = 0.5, 2.0, 12

# --- The5%ers (prix realiste 179$->545$ a 26 jours, daily DD 3%) ---
PALIER_5ERS, SUMMER_COST, POST_SUMMER_COST = 100000, 179, 545
DAILY_LOSS_5ERS, PRICE_CUTOFF_SECONDS = 3.0, 26 * DAY_SECONDS
N_5ERS = 4

# --- Croissance FTMO(2)/Blueberry(1), daily DD 5%, plafond combine 400k/firm ---
GROWTH_FIRMS = ["FTMO", "FTMO", "Blueberry"]
N_GROWTH = len(GROWTH_FIRMS)
FIRM_CAP = {"FTMO": 400000, "Blueberry": 400000}
DAILY_LOSS_GROWTH = 5.0

# CORRECTION A.1 : sequence de paliers PROPRE A CHAQUE FIRM (avant : une seule
# sequence [50k,200k,500k] partagee, fausse pour FTMO)
TIER_SEQUENCE_FTMO = [50000, 100000, 200000]
CHALLENGE_COST_FTMO = {50000: CHALLENGE_COST_BB[50000], 100000: 500, 200000: 1000}
UPGRADE_COST_FTMO = {100000: 500, 200000: 1000}

TIER_SEQUENCE_BY_FIRM = {"FTMO": TIER_SEQUENCE_FTMO, "Blueberry": TIER_SEQUENCE_BB}
CHALLENGE_COST_BY_FIRM = {"FTMO": CHALLENGE_COST_FTMO, "Blueberry": CHALLENGE_COST_BB}
UPGRADE_COST_BY_FIRM = {"FTMO": UPGRADE_COST_FTMO, "Blueberry": UPGRADE_COST_BB}


def make_acc(palier, cost, active=True):
    return {"palier": palier, "cost": cost, "phase": "challenge", "cumulative_since_reset": 0.0,
            "peak_since_reset": 0.0, "trading_days_since_reset": set(), "open_positions": [],
            "total_funded_pnl": 0.0, "total_fees_paid": cost, "trades_taken": 0, "daily_pnl": {},
            "active": active}


def process_trade(acc, trade, now, market_data, excluded_map, daily_loss_pct, max_dd_pct, state, source,
                   cost_override=None):
    if not acc["active"]:
        return False
    close_time = now + trade["hold_seconds"]
    acc["open_positions"] = [(t, c) for (t, c) in acc["open_positions"] if c > now]
    if len(acc["open_positions"]) >= MAX_POSITIONS:
        return False
    if any(t in excluded_map[trade["ticker"]] for (t, _) in acc["open_positions"]):
        return False

    current_risk = LOW_RISK if acc["trades_taken"] < RAMP_TRADES else HIGH_RISK
    eff_risk, _ = feasible_risk_pct(trade["ticker"], trade["sl_distance"], acc["palier"], current_risk, market_data)
    risk_amount = eff_risk / 100 * acc["palier"]
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
            state["reserve"] += pnl * RESERVE_SHARE

    trailing_dd = acc["peak_since_reset"] - acc["cumulative_since_reset"]
    daily_dd = -acc["daily_pnl"][close_day]
    broke = (trailing_dd >= max_dd_pct / 100 * acc["palier"] or daily_dd >= daily_loss_pct / 100 * acc["palier"])

    just_funded = False
    if broke:
        state["total_breaks"] += 1
        state["breaks_by_source"][source] = state["breaks_by_source"].get(source, 0) + 1
        cost = cost_override if cost_override is not None else acc["cost"]
        if state["reserve"] >= cost:
            state["reserve"] -= cost
        else:
            shortfall = cost - state["reserve"]
            state["reserve"] = 0.0
            if not state["ever_funded"]:
                state["real_cash_paid"] += shortfall
                state["cash_by_source"][source] = state["cash_by_source"].get(source, 0.0) + shortfall
        acc["total_fees_paid"] += cost
        acc["phase"] = "challenge"
        acc["cumulative_since_reset"] = 0.0
        acc["peak_since_reset"] = 0.0
        acc["trading_days_since_reset"] = set()
        acc["daily_pnl"] = {}
        return False

    if (acc["phase"] == "challenge" and acc["cumulative_since_reset"] >= CHALLENGE_TARGET_PCT / 100 * acc["palier"]
            and len(acc["trading_days_since_reset"]) >= MIN_TRADING_DAYS):
        acc["phase"] = "funded"
        if not state["ever_funded"]:
            just_funded = True
        state["ever_funded"] = True
        acc["cumulative_since_reset"] = 0.0
        acc["peak_since_reset"] = 0.0
        acc["trading_days_since_reset"] = set()
    return just_funded


def process_growth_upgrade(accounts, state):
    def firm_combined(firm, exclude_idx=None):
        return sum(a["palier"] for i, a in enumerate(accounts)
                   if GROWTH_FIRMS[i] == firm and i != exclude_idx and a["active"])
    for i, acc in enumerate(accounts):
        if not acc["active"] or acc["phase"] != "funded":
            continue
        firm = GROWTH_FIRMS[i]
        seq = TIER_SEQUENCE_BY_FIRM[firm]
        idx = seq.index(acc["palier"])
        if idx + 1 >= len(seq):
            continue
        next_tier = seq[idx + 1]
        cost = UPGRADE_COST_BY_FIRM[firm][next_tier]
        would_be = firm_combined(firm, exclude_idx=i) + next_tier
        if state["reserve"] >= cost and would_be <= FIRM_CAP[firm]:
            state["reserve"] -= cost
            acc["total_fees_paid"] += cost
            acc["palier"] = next_tier
            acc["cost"] = CHALLENGE_COST_BY_FIRM[firm][next_tier]
            acc["phase"] = "challenge"
            acc["cumulative_since_reset"] = 0.0
            acc["peak_since_reset"] = 0.0
            acc["trading_days_since_reset"] = set()
        elif state["reserve"] >= cost:
            state["blocked_upgrades"] += 1


def run_one(trades, slot_arrivals, market_data, excluded_map, order, mark_seconds_list, delay_5ers):
    fivers_cost0 = SUMMER_COST * N_5ERS
    fivers = [make_acc(PALIER_5ERS, SUMMER_COST, active=not delay_5ers) for _ in range(N_5ERS)]
    growth = [make_acc(TIER_SEQUENCE_BY_FIRM[f][0], CHALLENGE_COST_BY_FIRM[f][TIER_SEQUENCE_BY_FIRM[f][0]])
              for f in GROWTH_FIRMS]

    growth_cost0 = sum(a["cost"] for a in growth)
    state = {
        "reserve": 0.0, "ever_funded": False,
        "real_cash_paid": (0.0 if delay_5ers else fivers_cost0) + growth_cost0,
        "total_breaks": 0, "blocked_upgrades": 0,
        "cash_by_source": {"5ers": 0.0 if delay_5ers else fivers_cost0, "FTMO": 0.0, "Blueberry": 0.0},
        "breaks_by_source": {},
        "fivers_activated_at": 0.0 if not delay_5ers else None,
        "fivers_activation_cost_from_reserve": 0.0,
        "fivers_activation_cost_personal": 0.0,
    }
    # cout initial FTMO/Blueberry ventile par firm des le depart
    for f, a in zip(GROWTH_FIRMS, growth):
        state["cash_by_source"][f] += a["cost"]

    marks_sorted = sorted(mark_seconds_list)
    mark_idx = 0
    snapshots = []

    def combined_net():
        return sum(a["total_funded_pnl"] - a["total_fees_paid"] for a in fivers + growth)

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]

        while mark_idx < len(marks_sorted) and now > marks_sorted[mark_idx]:
            snapshots.append((marks_sorted[mark_idx], combined_net(), state["real_cash_paid"], state["total_breaks"]))
            mark_idx += 1

        for acc in fivers:
            acc["_dynamic_cost"] = SUMMER_COST if now < PRICE_CUTOFF_SECONDS else POST_SUMMER_COST
            process_trade(acc, trade, now, market_data, excluded_map, DAILY_LOSS_5ERS, BREAK_DD_PCT, state,
                          "5ers", cost_override=acc["_dynamic_cost"])

        for i, acc in enumerate(growth):
            just_funded = process_trade(acc, trade, now, market_data, excluded_map, DAILY_LOSS_GROWTH, BREAK_DD_PCT,
                                         state, GROWTH_FIRMS[i])
            if just_funded and delay_5ers and state["fivers_activated_at"] is None:
                # immunite globale vient de demarrer via la croissance -> on active The5%ers
                state["fivers_activated_at"] = now
                cost = fivers_cost0
                if state["reserve"] >= cost:
                    state["reserve"] -= cost
                    state["fivers_activation_cost_from_reserve"] = cost
                else:
                    shortfall = cost - state["reserve"]
                    state["reserve"] = 0.0
                    # ever_funded deja True ici (just_funded l'a mis a True juste avant) -> absorbe, pas de cash perso
                    state["fivers_activation_cost_from_reserve"] = cost - shortfall
                for a in fivers:
                    a["active"] = True
                    a["total_fees_paid"] = a["cost"]

        process_growth_upgrade(growth, state)

    while mark_idx < len(marks_sorted):
        snapshots.append((marks_sorted[mark_idx], combined_net(), state["real_cash_paid"], state["total_breaks"]))
        mark_idx += 1

    return snapshots, state


def run_variant(trades, slot_arrivals, blocks, block_seconds, target_duration, mark_seconds_list,
                market_data, excluded_map, delay_5ers):
    rng = random.Random(42)
    rows = []
    for _ in range(N_SIMULATIONS):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, target_duration)
        order = list(range(len(raw_trades)))
        snaps, state = run_one(raw_trades, raw_slots, market_data, excluded_map, order, mark_seconds_list, delay_5ers)
        rows.append({
            "year1_net": snaps[0][1], "year1_cash": snaps[0][2], "year1_breaks": snaps[0][3],
            "final_net": snaps[1][1], "final_cash": snaps[1][2], "final_breaks": snaps[1][3],
            "cash_5ers": state["cash_by_source"]["5ers"],
            "cash_ftmo": state["cash_by_source"]["FTMO"],
            "cash_blueberry": state["cash_by_source"]["Blueberry"],
            "breaks_5ers": state["breaks_by_source"].get("5ers", 0),
            "breaks_ftmo": state["breaks_by_source"].get("FTMO", 0),
            "breaks_blueberry": state["breaks_by_source"].get("Blueberry", 0),
            "fivers_delay_days": (state["fivers_activated_at"] / DAY_SECONDS) if state["fivers_activated_at"] else 0.0,
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
        print(f"\n{'='*100}\nWINRATE {wr_label}\n{'='*100}")
        trades, slot_arrivals = build_population(pop, wr_target)
        total_horizon_seconds = slot_arrivals[-1]
        mark_seconds_list = [YEAR_SECONDS, total_horizon_seconds]
        block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
        blocks = build_blocks(trades, slot_arrivals, block_seconds)

        for variant_label, delay in [("actuel_5ers_t0", False), ("retarde_5ers_post_immunite", True)]:
            t0 = time.time()
            df = run_variant(trades, slot_arrivals, blocks, block_seconds, total_horizon_seconds,
                              mark_seconds_list, market_data, excluded_map, delay)
            df.to_csv(f"pretimmunity_{variant_label}_{suffix}.csv", index=False)
            row = dict(
                winrate=wr_label, variant=variant_label,
                profit_final=df["final_net"].mean(),
                cash_worst=df["final_cash"].max(), cash_mean=df["final_cash"].mean(),
                cash_5ers_mean=df["cash_5ers"].mean(), cash_ftmo_mean=df["cash_ftmo"].mean(),
                cash_blueberry_mean=df["cash_blueberry"].mean(),
                cash_5ers_worst=df["cash_5ers"].max(), cash_ftmo_worst=df["cash_ftmo"].max(),
                cash_blueberry_worst=df["cash_blueberry"].max(),
                breaks_5ers_mean=df["breaks_5ers"].mean(), breaks_ftmo_mean=df["breaks_ftmo"].mean(),
                breaks_blueberry_mean=df["breaks_blueberry"].mean(),
                casses_final=df["final_breaks"].mean(),
                fivers_delay_median_days=df["fivers_delay_days"].median(),
                fivers_delay_p90_days=df["fivers_delay_days"].quantile(0.9),
            )
            rows.append(row)
            print(f"  [{variant_label}] profit final {row['profit_final']:+,.0f}$ | cash pire cas {row['cash_worst']:,.0f}$ "
                  f"(5ers {row['cash_5ers_worst']:,.0f}$ / FTMO {row['cash_ftmo_worst']:,.0f}$ / BB {row['cash_blueberry_worst']:,.0f}$) "
                  f"| casses {row['casses_final']:.1f} | delai 5ers median {row['fivers_delay_median_days']:.0f}j ({time.time()-t0:.0f}s)")

    out = pd.DataFrame(rows)
    out.to_csv("pretimmunity_breakdown_summary.csv", index=False)
    print(f"\nTerminé en {time.time()-t_start:.0f}s. Résumé : pretimmunity_breakdown_summary.csv")


if __name__ == "__main__":
    main()
