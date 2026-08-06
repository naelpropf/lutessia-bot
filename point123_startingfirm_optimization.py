"""
Suite du 08/08 : 3 questions avant de considerer 9 324$ comme un plancher.
1. Quelle firm SEULE au demarrage minimise vraiment le cash pire cas (5 firms
   testees individuellement, reste ensemble au 1er financement, sur le modele
   d2 deja valide) ?
2. Combiner la meilleure firm de demarrage avec les leviers deja connus
   (1er palier 25k, variantes de rampe).
3. Decomposer le plancher structurel du cash pire cas atteint.

Reprend GROUP_DEFS de point2_sequencing_engine.py, mais parametre RAMP_RISK/
RAMP_N/premier palier au lieu de constantes figees, pour pouvoir les balayer.
"""
import random
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
import point3a_ramp_fixed as ramp_eng
from point2_sequencing_engine import GROUP_DEFS as BASE_GROUP_DEFS, build_ctx
from real_cash_risk_year1_block_bootstrap import DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs

POP_CONSTRUCT_SEED = 123
TARGET_RISK = 2.5
MAXPOS, CORR_TH = 3, 0.6
DAY_SECONDS = 86400

# variante 1-compte de The5%ers pour la comparaison "1 firm seule" equitable
GROUP_DEFS = dict(BASE_GROUP_DEFS)
GROUP_DEFS["Fivers1"] = dict(n_accounts=1, dd=3.0, kind="fivers")

ALL_FIRMS = ["FTMO", "Blueberry", "Fivers", "GFT", "FundedNext"]


def build_group_seq_map(sequence, first_tier_overrides):
    """Pour chaque groupe growth, calcule la sequence de paliers/couts REELLEMENT
    utilisee (avec le 1er palier eventuellement substitue) -- necessaire pour que
    la logique d'upgrade retrouve le compte dans sa sequence."""
    first_tier_overrides = first_tier_overrides or {}
    seq_map = {}
    for group_names, _ in sequence:
        for gname in group_names:
            gdef = GROUP_DEFS[gname]
            if gdef["kind"] != "growth":
                continue
            seq = list(gdef["seq"])
            cost = dict(gdef["cost"])
            override = first_tier_overrides.get(gname)
            if override is not None:
                old_first = seq[0]
                ratio = gdef["cost"][old_first] / old_first
                seq[0] = override
                cost[override] = cost.get(override, round(override * ratio))
            seq_map[gname] = (seq, cost, gdef["upgrade"], gdef["cap"])
    return seq_map


def make_accounts_for_group(gname, gdef, active, seq_map):
    if gdef["kind"] == "fivers":
        return [eng.make_acc(eng.PALIER_5ERS, eng.SUMMER_COST, active=active) for _ in range(gdef["n_accounts"])]
    seq, cost, _, _ = seq_map[gname]
    return [eng.make_acc(seq[0], cost[seq[0]], active=active) for _ in range(gdef["n_accounts"])]


def process_growth_upgrade_seq(accounts_by_group, seq_map, state):
    for gname, accs in accounts_by_group.items():
        gdef = GROUP_DEFS[gname]
        if gdef["kind"] != "growth":
            continue
        seq, cost_map, upgrade_map, cap = seq_map[gname]

        def combined(exclude_idx=None):
            return sum(a["palier"] for i, a in enumerate(accs) if i != exclude_idx and a["active"])

        for i, acc in enumerate(accs):
            if not acc["active"] or acc["phase"] != "funded":
                continue
            idx = seq.index(acc["palier"])
            if idx + 1 >= len(seq):
                continue
            next_tier = seq[idx + 1]
            ucost = upgrade_map[next_tier]
            would_be = combined(exclude_idx=i) + next_tier
            if state["reserve"] >= ucost and would_be <= cap:
                state["reserve"] -= ucost
                acc["total_fees_paid"] += ucost
                acc["palier"] = next_tier
                acc["cost"] = cost_map[next_tier]
                acc["phase"] = "challenge"
                acc["cumulative_since_reset"] = 0.0
                acc["peak_since_reset"] = 0.0
                acc["trading_days_since_reset"] = set()


def run_one(trades, slot_arrivals, market_data, excluded_map, order, mark_seconds_list, sequence,
           ramp_risk, ramp_n, first_tier_overrides=None):
    first_tier_overrides = first_tier_overrides or {}
    seq_map = build_group_seq_map(sequence, first_tier_overrides)
    accounts_by_group = {}
    active0_cost = 0.0
    for group_names, trigger in sequence:
        for gname in group_names:
            gdef = GROUP_DEFS[gname]
            is_day0 = trigger == "day0"
            accs = make_accounts_for_group(gname, gdef, active=is_day0, seq_map=seq_map)
            accounts_by_group[gname] = accs
            if is_day0:
                active0_cost += sum(a["cost"] for a in accs)

    state = {"reserve": 0.0, "ever_funded": False, "real_cash_paid": active0_cost, "total_breaks": 0,
             "group_funded_count": 0, "group_own_funded": set(), "activation_times": {}}
    pending = [(names, trig) for names, trig in sequence if trig != "day0"]

    def activate_group(gname, now):
        accs = accounts_by_group[gname]
        cost0 = sum(a["cost"] for a in accs)
        if state["reserve"] >= cost0:
            state["reserve"] -= cost0
        else:
            shortfall = cost0 - state["reserve"]
            state["reserve"] = 0.0
            if not state["ever_funded"]:
                state["real_cash_paid"] += shortfall
        for a in accs:
            a["active"] = True
            a["total_fees_paid"] = a["cost"]
        state["activation_times"][gname] = now

    marks_sorted = sorted(mark_seconds_list)
    mark_idx = 0
    snapshots = []

    def combined_net():
        return sum(a["total_funded_pnl"] - a["total_fees_paid"] for accs in accounts_by_group.values() for a in accs)

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]
        while mark_idx < len(marks_sorted) and now > marks_sorted[mark_idx]:
            snapshots.append((marks_sorted[mark_idx], combined_net(), state["real_cash_paid"], state["total_breaks"]))
            mark_idx += 1

        for gname, accs in accounts_by_group.items():
            gdef = GROUP_DEFS[gname]
            for acc in accs:
                was_challenge = acc["active"] and acc["phase"] == "challenge"
                cost_now = None
                if gdef["kind"] == "fivers":
                    cost_now = eng.SUMMER_COST if now < eng.PRICE_CUTOFF_SECONDS else eng.POST_SUMMER_COST_REAL
                ramp_eng.process_trade_ramp_pure(acc, trade, now, market_data, excluded_map, gdef["dd"],
                                                  eng.BREAK_DD_PCT, state, ramp_risk, ramp_n, TARGET_RISK,
                                                  cost_override=cost_now)
                if was_challenge and acc["phase"] == "funded" and gname not in state["group_own_funded"]:
                    state["group_own_funded"].add(gname)
                    state["group_funded_count"] += 1

        process_growth_upgrade_seq(accounts_by_group, seq_map, state)

        still_pending = []
        for group_names, trig in pending:
            _, n_req = trig
            if state["group_funded_count"] >= n_req:
                for gname in group_names:
                    activate_group(gname, now)
            else:
                still_pending.append((group_names, trig))
        pending = still_pending

    while mark_idx < len(marks_sorted):
        snapshots.append((marks_sorted[mark_idx], combined_net(), state["real_cash_paid"], state["total_breaks"]))
        mark_idx += 1

    all_groups = set(g for names, _ in sequence for g in names)
    full_structure_time = max((state["activation_times"].get(g, 0) for g in all_groups), default=0)
    return snapshots, full_structure_time


def run_variant(trades, slot_arrivals, blocks, block_seconds, target_duration, mark_seconds_list,
               market_data, excluded_map, sequence, ramp_risk=2.0, ramp_n=5, first_tier_overrides=None,
               n_sims=2000, seed=42):
    rng = random.Random(seed)
    rows = []
    for _ in range(n_sims):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, target_duration)
        order = list(range(len(raw_trades)))
        snaps, full_time = run_one(raw_trades, raw_slots, market_data, excluded_map, order, mark_seconds_list,
                                   sequence, ramp_risk, ramp_n, first_tier_overrides)
        rows.append({"year1_net": snaps[0][1], "year1_cash": snaps[0][2], "year1_breaks": snaps[0][3],
                     "final_net": snaps[1][1], "final_cash": snaps[1][2], "final_breaks": snaps[1][3],
                     "full_structure_days": full_time / DAY_SECONDS})
    return pd.DataFrame(rows)


def summarize(df, label, extra=None):
    row = dict(label=label, profit_final_mean=df["final_net"].mean(), cash_worst=df["final_cash"].max(),
               p_year1_negatif=(df["year1_net"] < 0).mean() * 100, casses_final=df["final_breaks"].mean(),
               delai_structure_complete_median=df["full_structure_days"].median())
    if extra:
        row.update(extra)
    return row


def sequence_single_firm(starter):
    rest = tuple(f for f in ALL_FIRMS if f != starter)
    return [((starter,), "day0"), (rest, ("after_count", 1))]


def main():
    t_start = time.time()
    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

    rows = []
    for wr_label, wr_target, suffix in [("40.09%_reel", None, "40_09pct"), ("37.66%_P10bayesien", 0.3766, "37_66pct")]:
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_target, 1.0, False, random.Random(POP_CONSTRUCT_SEED))
        total_h, marks, block_s, blocks = build_ctx(trades, slot_arrivals)
        print(f"\n{'='*100}\nWINRATE {wr_label}\n{'='*100}")

        print("--- 1. Chaque firm seule au demarrage ---")
        starter_map = {"FTMO": "FTMO", "Blueberry": "Blueberry", "The5%ers(1cpt)": "Fivers1", "GFT": "GFT", "FundedNext": "FundedNext"}
        for label, starter in starter_map.items():
            seq = sequence_single_firm_custom(starter)
            t0 = time.time()
            df = run_variant(trades, slot_arrivals, blocks, block_s, total_h, marks, market_data, excluded_map,
                             seq, ramp_risk=2.0, ramp_n=5, n_sims=2000, seed=42)
            df.to_csv(f"point123_starter_{label.replace('%','pct').replace('(','_').replace(')','')}_{suffix}.csv", index=False)
            row = summarize(df, f"starter_{label}", {"winrate": wr_label})
            rows.append(row)
            print(f"  [{label} seule] profit {row['profit_final_mean']:+,.0f}$ | cash pire cas {row['cash_worst']:,.0f}$ | "
                  f"P(an1<0) {row['p_year1_negatif']:.2f}% | delai {row['delai_structure_complete_median']:.0f}j ({time.time()-t0:.0f}s)")
        pd.DataFrame(rows).to_csv("point123_summary_partial.csv", index=False)

    pd.DataFrame(rows).to_csv("point123_step1_summary.csv", index=False)
    print(f"\nEtape 1 terminée en {time.time()-t_start:.0f}s.")


def sequence_single_firm_custom(starter):
    real_starter = "Fivers" if starter == "Fivers1" else starter
    rest = tuple(f for f in ALL_FIRMS if f != real_starter)
    return [((starter,), "day0"), (rest, ("after_count", 1))]


if __name__ == "__main__":
    main()
