"""
Point 4 (06/08, 3e relance) : re-test pyramiding / Kelly fractionnel / ATR sous la
configuration ACTUELLEMENT verrouillee -- RR>=1.5, trailing 0.2xSL post-TP2,
flotte 3 firms (FTMO corrige 50k->100k->200k, Blueberry, The5%ers retardee
jusqu'a l'immunite), daily DD reel par firm, risque 2,5% uniforme.

Ancien test (30/07) : structure fleet generique 3 comptes (regime 0,5%->2%@5000e,
PAS de daily DD modelise), verdict pyramiding rejete net (~4.2M vs 10.3M baseline,
casses x2), Kelly25 marginal (+7,6% profit mais casses x3, DD trailing +33%),
Kelly50 rejete (profit ~egal, casses x4, DD +75%). Meme population sous-jacente
(RR>=1.5, deja verifiee identique -- sizing_stats.build_base_population utilise
DEJA build_population_with_trailing("fixed",0.2), donc pas de changement de
payoff depuis l'ancien test -- seul le MOTEUR FLOTTE change ici).

Pyramiding : substitue dans "outcome_r" la valeur effective ponderee par les
fractions reellement engagees (base + add-ons), calculee a partir de
pyramid_payoff_population.build_population_with_pyramid (deja disponible,
walk bougie par bougie) -- palier-independant par construction (cf. derivation
dans le rapport), donc directement injectable dans le moteur flotte actuel
exactement comme pour le stress RR/slippage des rapports precedents.

Kelly/ATR : risque PAR TICKER (Kelly) ou PAR TRADE (ATR) au lieu du risque flat
2,5% -- process_trade_variable_risk ci-dessous accepte un risk_fn(ticker, date)
au lieu d'un scalaire.
"""
import random
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
from real_cash_risk_year1_block_bootstrap import DAYS_PER_MONTH
from pyramid_payoff_population import build_population_with_pyramid, STRUCTURES
from sizing_stats import build_base_population, compute_kelly_risk_by_ticker, compute_atr_ratio_by_trade

POP_CONSTRUCT_SEED = 123
BASE_RISK = 2.5


def build_ctx(trades, slot_arrivals):
    total_horizon_seconds = slot_arrivals[-1]
    mark_seconds_list = [eng.YEAR_SECONDS, total_horizon_seconds]
    block_seconds = eng.BLOCK_MONTHS * DAYS_PER_MONTH * 86400
    blocks = eng.build_blocks(trades, slot_arrivals, block_seconds)
    return total_horizon_seconds, mark_seconds_list, block_seconds, blocks


def build_pyramid_trades(structure_label):
    add_levels, add_fractions = STRUCTURES[structure_label]
    pop, _ = build_population_with_pyramid(add_levels, add_fractions, verbose=False)
    sub = pop.sort_values("date_creation").reset_index(drop=True)
    t0 = sub["date_creation"].iloc[0]
    slot_arrivals = [(d - t0).total_seconds() for d in sub["date_creation"]]
    trades = []
    for _, row in sub.iterrows():
        units = row["units"]
        effective_r = sum(u["fraction"] * u["exit_r"] for u in units)
        hold_seconds = (row["resolution_time_est"] - row["date_creation"]).total_seconds()
        sl_distance = abs(row["prix_entree"] - row["stop_loss_init"])
        trades.append({"ticker": row["ticker"], "outcome_r": effective_r, "sl_distance": sl_distance,
                       "hold_seconds": hold_seconds, "date": row["date_creation"]})
    return trades, slot_arrivals


def process_trade_variable_risk(acc, trade, now, market_data, excluded_map, daily_loss_pct, max_dd_pct, state,
                                risk_fn):
    """Variante de eng.process_trade ou le risque cible depend du trade (ticker/date),
    via risk_fn(trade) -> risque_pct. Duplique le corps pour eviter de modifier le
    moteur commun (utilise par tous les scripts precedents de la session)."""
    if not acc["active"]:
        return False
    close_time = now + trade["hold_seconds"]
    acc["open_positions"] = [(t, c) for (t, c) in acc["open_positions"] if c > now]
    if len(acc["open_positions"]) >= eng.MAX_POSITIONS:
        return False
    if any(t in excluded_map[trade["ticker"]] for (t, _) in acc["open_positions"]):
        return False

    current_risk = eng.LOW_RISK if acc["trades_taken"] < eng.RAMP_TRADES else risk_fn(trade)
    eff_risk, _ = eng.feasible_risk_pct(trade["ticker"], trade["sl_distance"], acc["palier"], current_risk, market_data)
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
            state["reserve"] += pnl * eng.RESERVE_SHARE

    trailing_dd = acc["peak_since_reset"] - acc["cumulative_since_reset"]
    daily_dd = -acc["daily_pnl"][close_day]
    broke = (trailing_dd >= max_dd_pct / 100 * acc["palier"] or daily_dd >= daily_loss_pct / 100 * acc["palier"])

    just_funded = False
    if broke:
        state["total_breaks"] += 1
        cost = trade.get("cost_override") or acc["cost"]
        if state["reserve"] >= cost:
            state["reserve"] -= cost
        else:
            shortfall = cost - state["reserve"]
            state["reserve"] = 0.0
            if not state["ever_funded"]:
                state["real_cash_paid"] += shortfall
        acc["total_fees_paid"] += cost
        acc["phase"] = "challenge"
        acc["cumulative_since_reset"] = 0.0
        acc["peak_since_reset"] = 0.0
        acc["trading_days_since_reset"] = set()
        acc["daily_pnl"] = {}
        return False

    if (acc["phase"] == "challenge" and acc["cumulative_since_reset"] >= eng.CHALLENGE_TARGET_PCT / 100 * acc["palier"]
            and len(acc["trading_days_since_reset"]) >= eng.MIN_TRADING_DAYS):
        acc["phase"] = "funded"
        if not state["ever_funded"]:
            just_funded = True
        state["ever_funded"] = True
        acc["cumulative_since_reset"] = 0.0
        acc["peak_since_reset"] = 0.0
        acc["trading_days_since_reset"] = set()
    return just_funded


def run_one_variable_risk(trades, slot_arrivals, market_data, excluded_map, order, mark_seconds_list, risk_fn):
    fivers = [eng.make_acc(eng.PALIER_5ERS, eng.SUMMER_COST, active=False) for _ in range(eng.N_5ERS)]
    growth = [eng.make_acc(eng.TIER_SEQUENCE_BY_FIRM[f][0], eng.CHALLENGE_COST_BY_FIRM[f][eng.TIER_SEQUENCE_BY_FIRM[f][0]])
              for f in eng.GROWTH_FIRMS]
    growth_cost0 = sum(a["cost"] for a in growth)
    state = {"reserve": 0.0, "ever_funded": False, "real_cash_paid": growth_cost0,
             "total_breaks": 0, "fivers_activated_at": None}
    fivers_cost0 = eng.SUMMER_COST * eng.N_5ERS

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
            trade["cost_override"] = eng.SUMMER_COST if now < eng.PRICE_CUTOFF_SECONDS else eng.POST_SUMMER_COST_REAL
            process_trade_variable_risk(acc, trade, now, market_data, excluded_map, eng.DAILY_LOSS_5ERS_REAL,
                                        eng.BREAK_DD_PCT, state, risk_fn)

        trade["cost_override"] = None
        for acc in growth:
            just_funded = process_trade_variable_risk(acc, trade, now, market_data, excluded_map,
                                                       eng.DAILY_LOSS_GROWTH, eng.BREAK_DD_PCT, state, risk_fn)
            if just_funded and state["fivers_activated_at"] is None:
                state["fivers_activated_at"] = now
                cost = fivers_cost0
                if state["reserve"] >= cost:
                    state["reserve"] -= cost
                else:
                    shortfall = cost - state["reserve"]
                    state["reserve"] = 0.0
                    if not state["ever_funded"]:
                        state["real_cash_paid"] += shortfall
                for a in fivers:
                    a["active"] = True
                    a["total_fees_paid"] = a["cost"]

        eng.process_growth_upgrade(growth, state)

    while mark_idx < len(marks_sorted):
        snapshots.append((marks_sorted[mark_idx], combined_net(), state["real_cash_paid"], state["total_breaks"]))
        mark_idx += 1
    return snapshots


def run_variant_variable_risk(trades, slot_arrivals, blocks, block_seconds, target_duration, mark_seconds_list,
                              market_data, excluded_map, risk_fn, n_sims=2000, seed=42):
    rng = random.Random(seed)
    rows = []
    for _ in range(n_sims):
        raw_trades, raw_slots = eng.build_full_block_bootstrap_sequence(blocks, block_seconds, rng, target_duration)
        order = list(range(len(raw_trades)))
        snaps = run_one_variable_risk(raw_trades, raw_slots, market_data, excluded_map, order, mark_seconds_list, risk_fn)
        rows.append({"year1_net": snaps[0][1], "year1_cash": snaps[0][2], "year1_breaks": snaps[0][3],
                     "final_net": snaps[1][1], "final_cash": snaps[1][2], "final_breaks": snaps[1][3]})
    return pd.DataFrame(rows)


def summarize(df, label):
    return dict(label=label, profit_final_mean=df["final_net"].mean(), cash_worst=df["final_cash"].max(),
               p_year1_negatif=(df["year1_net"] < 0).mean() * 100, casses_final=df["final_breaks"].mean())


def main():
    t_start = time.time()
    pop = eng.build_population_with_trailing("fixed", 0.2, verbose=False)
    market_data, excluded_map = eng.prep_common(pop)
    rows = []

    print("=" * 100 + "\nBASELINE (rappel, deja connu) : flat 2,5%\n" + "=" * 100)
    trades0, slots0 = eng.build_flexible_population(pop, None, 1.0, False, random.Random(POP_CONSTRUCT_SEED))
    total_h, marks, block_s, blocks = build_ctx(trades0, slots0)
    df0 = eng.run_variant(trades0, slots0, blocks, block_s, total_h, marks, market_data, excluded_map,
                          BASE_RISK, BASE_RISK, "event", None, 2000, 42)
    row0 = summarize(df0, "baseline_flat2.5")
    rows.append(row0)
    print(f"  baseline : profit {row0['profit_final_mean']:+,.0f}$ | cash pire cas {row0['cash_worst']:,.0f}$ | "
          f"P(an1<0) {row0['p_year1_negatif']:.2f}% | casses {row0['casses_final']:.1f}")

    print("\n" + "=" * 100 + "\nPYRAMIDING (structures A/B, RR>=1.5, meme population que baseline)\n" + "=" * 100)
    for struct_label in ["A_paliers_fixes", "B_degressif"]:
        t0 = time.time()
        trades, slots = build_pyramid_trades(struct_label)
        th, mk, bs, bl = build_ctx(trades, slots)
        df = eng.run_variant(trades, slots, bl, bs, th, mk, market_data, excluded_map, BASE_RISK, BASE_RISK,
                             "event", None, 2000, 42)
        df.to_csv(f"point4_pyramid_{struct_label}.csv", index=False)
        row = summarize(df, f"pyramid_{struct_label}")
        rows.append(row)
        print(f"  [{struct_label}] profit {row['profit_final_mean']:+,.0f}$ | cash pire cas {row['cash_worst']:,.0f}$ | "
              f"P(an1<0) {row['p_year1_negatif']:.2f}% | casses {row['casses_final']:.1f} ({time.time()-t0:.0f}s)")

    print("\n" + "=" * 100 + "\nKELLY FRACTIONNEL (25%/50%, par ticker)\n" + "=" * 100)
    base_pop = build_base_population(verbose=False)
    for kelly_mult, label in [(0.25, "kelly25"), (0.5, "kelly50")]:
        t0 = time.time()
        risk_by_ticker, _ = compute_kelly_risk_by_ticker(base_pop, kelly_mult)
        risk_fn = lambda trade, m=risk_by_ticker: m.get(trade["ticker"], BASE_RISK)
        df = run_variant_variable_risk(trades0, slots0, blocks, block_s, total_h, marks, market_data, excluded_map,
                                       risk_fn, n_sims=2000, seed=42)
        df.to_csv(f"point4_{label}.csv", index=False)
        row = summarize(df, label)
        avg_risk = sum(risk_by_ticker.values()) / len(risk_by_ticker)
        row["avg_risk_pct"] = avg_risk
        rows.append(row)
        print(f"  [{label}] risque moyen {avg_risk:.2f}% : profit {row['profit_final_mean']:+,.0f}$ | "
              f"cash pire cas {row['cash_worst']:,.0f}$ | P(an1<0) {row['p_year1_negatif']:.2f}% | "
              f"casses {row['casses_final']:.1f} ({time.time()-t0:.0f}s)")

    print("\n" + "=" * 100 + "\nATR-AJUSTE (risque = 2,5% x ratio_ATR)\n" + "=" * 100)
    t0 = time.time()
    atr_ratio_map, _ = compute_atr_ratio_by_trade(base_pop)
    def atr_risk_fn(trade):
        ratio = atr_ratio_map.get((trade["ticker"], trade["date"]), 1.0)
        return BASE_RISK * ratio
    df = run_variant_variable_risk(trades0, slots0, blocks, block_s, total_h, marks, market_data, excluded_map,
                                   atr_risk_fn, n_sims=2000, seed=42)
    df.to_csv("point4_atr_adjusted.csv", index=False)
    row = summarize(df, "atr_adjusted")
    rows.append(row)
    print(f"  [ATR] profit {row['profit_final_mean']:+,.0f}$ | cash pire cas {row['cash_worst']:,.0f}$ | "
          f"P(an1<0) {row['p_year1_negatif']:.2f}% | casses {row['casses_final']:.1f} ({time.time()-t0:.0f}s)")

    pd.DataFrame(rows).to_csv("point4_retest_summary.csv", index=False)
    print(f"\nTerminé en {time.time()-t_start:.0f}s.")


if __name__ == "__main__":
    main()
