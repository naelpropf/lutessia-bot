"""
Point 2 (08/08) : moteur generique de sequencage de 5 firms (FTMO, Blueberry,
The5%ers, Goat Funded Trader, FundedNext) activees progressivement par
IMMUNITE (compteur de groupes distincts ayant atteint leur propre premier
financement), pas par delai fixe ni seuil de reserve -- meme principe deja
valide pour The5%ers seule.

Groupes disponibles :
  FTMO       : 2 comptes, paliers 50k->100k->200k, DD5%, plafond combine 400k
  Blueberry  : 1 compte, paliers 50k->200k->500k, DD5%, plafond combine 400k
  Fivers     : 4 comptes The5%ers, palier fixe 100k (pas d'upgrade), DD5%
               (corrige 08/08 -- programme reellement retenu = High Stakes
               2-Step format 8/5%, DD journalier officiel 5% source
               help.the5ers.com/the5ers.com/faqs ; 3% appartenait a tort au
               Bootcamp/Hyper Growth, jamais utilises dans ce projet),
               prix 179$->545$ a 26j
  GFT        : 1 compte Goat Funded Trader, paliers 50k->100k->200k (approxime
               sur le modele FTMO, prix GFT reels non sources), DD4%,
               plafond combine 400k
  FundedNext : 1 compte, paliers 50k->100k->200k (approxime sur le modele
               FTMO), DD5%, plafond 200k (mono-compte, cf. rapport precedent)

Chaque groupe a un trigger ("day0") ou ("after_count", n) : actif des le
depart, ou des que n groupes DISTINCTS (pas n comptes) ont individuellement
atteint leur propre premier financement.
"""
import random
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
import point3a_ramp_fixed as ramp_eng
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs

POP_CONSTRUCT_SEED = 123
TARGET_RISK = 2.5
RAMP_RISK, RAMP_N = 2.0, 5
MAXPOS, CORR_TH = 3, 0.6
DAY_SECONDS = 86400

FTMO_SEQ, FTMO_COST, FTMO_UPGRADE = list(eng.TIER_SEQUENCE_FTMO), dict(eng.CHALLENGE_COST_FTMO), dict(eng.UPGRADE_COST_FTMO)
BB_SEQ, BB_COST, BB_UPGRADE = list(eng.TIER_SEQUENCE_BB), dict(eng.CHALLENGE_COST_BB), dict(eng.UPGRADE_COST_BB)

# dd = DD journalier (%), dd_max = DD max/total (%) -- differencies par firm (audit
# 08/08 session 6, verification croisee vs sources officielles) :
#   FTMO 5%/10%, Blueberry 5%/10%, GFT 4%/10% (trailing), Fivers 5%/10% (deja
#   corrige session 5), FundedNext (Stellar Lite, palier max) 4%/8% -- AVANT cette
#   correction, dd=5.0 (faux, etait 4%) et dd_max non differencie du tout (10%
#   global via BREAK_DD_PCT partout dans le moteur, faux, etait 8%). Meme type de
#   bug de donnees que le DD journalier Fivers corrige session 5.
GROUP_DEFS = {
    "FTMO": dict(n_accounts=2, seq=FTMO_SEQ, cost=FTMO_COST, upgrade=FTMO_UPGRADE, dd=5.0, dd_max=10.0, cap=400000, kind="growth"),
    "Blueberry": dict(n_accounts=1, seq=list(BB_SEQ), cost=dict(BB_COST), upgrade=dict(BB_UPGRADE), dd=5.0, dd_max=10.0, cap=400000, kind="growth"),
    "GFT": dict(n_accounts=1, seq=FTMO_SEQ, cost=FTMO_COST, upgrade=FTMO_UPGRADE, dd=4.0, dd_max=10.0, cap=400000, kind="growth"),
    "FundedNext": dict(n_accounts=1, seq=FTMO_SEQ, cost=FTMO_COST, upgrade=FTMO_UPGRADE, dd=4.0, dd_max=8.0, cap=200000, kind="growth"),  # corrige 08/08 session 6 : etait dd=5.0, dd_max absent (10.0 global)
    "Fivers": dict(n_accounts=4, dd=5.0, dd_max=10.0, kind="fivers"),  # corrige 08/08 session 5 : etait 3.0 (faux, cf docstring)
}


def make_growth_accounts(gname, gdef, active):
    return [eng.make_acc(gdef["seq"][0], gdef["cost"][gdef["seq"][0]], active=active) for _ in range(gdef["n_accounts"])]


def process_growth_upgrade_seq(accounts_by_group, state):
    for gname, accounts in accounts_by_group.items():
        gdef = GROUP_DEFS[gname]
        if gdef["kind"] != "growth":
            continue
        seq, cost_map, upgrade_map, cap = gdef["seq"], gdef["cost"], gdef["upgrade"], gdef["cap"]

        def combined(exclude_idx=None):
            return sum(a["palier"] for i, a in enumerate(accounts) if i != exclude_idx and a["active"])

        for i, acc in enumerate(accounts):
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


def run_one(trades, slot_arrivals, market_data, excluded_map, order, mark_seconds_list, sequence):
    """sequence : liste de (group_names_tuple, trigger) ou trigger = "day0" ou
    ("after_count", n). Chaque group_names_tuple s'active simultanement des que
    son trigger est satisfait."""
    accounts_by_group = {}
    active0_cost = 0.0
    for group_names, trigger in sequence:
        for gname in group_names:
            gdef = GROUP_DEFS[gname]
            is_day0 = trigger == "day0"
            if gdef["kind"] == "growth":
                accounts_by_group[gname] = make_growth_accounts(gname, gdef, active=is_day0)
                if is_day0:
                    active0_cost += sum(a["cost"] for a in accounts_by_group[gname])
            else:
                accounts_by_group[gname] = [eng.make_acc(eng.PALIER_5ERS, eng.SUMMER_COST, active=is_day0)
                                            for _ in range(gdef["n_accounts"])]
                if is_day0:
                    active0_cost += eng.SUMMER_COST * gdef["n_accounts"]

    state = {"reserve": 0.0, "ever_funded": False, "real_cash_paid": active0_cost, "total_breaks": 0,
             "group_funded_count": 0, "group_own_funded": set(), "activation_times": {}}

    pending = [(names, trig) for names, trig in sequence if trig != "day0"]

    def activate_group(gname, now):
        gdef = GROUP_DEFS[gname]
        accs = accounts_by_group[gname]
        cost0 = sum(a["cost"] for a in accs) if gdef["kind"] == "growth" else eng.SUMMER_COST * gdef["n_accounts"]
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
                # process_trade_ramp_pure renvoie un "just_funded" GATE SUR L'IMMUNITE
                # GLOBALE du projet (ne se declenche qu'une seule fois pour TOUTE la
                # simulation, cf. state["ever_funded"] dans point3a_ramp_fixed.py) --
                # PAS un signal "ce groupe vient de financer SON PROPRE premier compte".
                # Detection correcte : transition de phase reelle sur CE compte.
                was_challenge = acc["active"] and acc["phase"] == "challenge"
                if gdef["kind"] == "fivers":
                    cost_now = eng.SUMMER_COST if now < eng.PRICE_CUTOFF_SECONDS else eng.POST_SUMMER_COST_REAL
                    ramp_eng.process_trade_ramp_pure(acc, trade, now, market_data, excluded_map,
                                                      gdef["dd"], eng.BREAK_DD_PCT, state, RAMP_RISK,
                                                      RAMP_N, TARGET_RISK, cost_override=cost_now)
                else:
                    ramp_eng.process_trade_ramp_pure(acc, trade, now, market_data, excluded_map,
                                                      gdef["dd"], eng.BREAK_DD_PCT, state, RAMP_RISK,
                                                      RAMP_N, TARGET_RISK)
                if was_challenge and acc["phase"] == "funded" and gname not in state["group_own_funded"]:
                    state["group_own_funded"].add(gname)
                    state["group_funded_count"] += 1

        process_growth_upgrade_seq(accounts_by_group, state)

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
               market_data, excluded_map, sequence, n_sims=2000, seed=42):
    rng = random.Random(seed)
    rows = []
    for _ in range(n_sims):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, target_duration)
        order = list(range(len(raw_trades)))
        snaps, full_time = run_one(raw_trades, raw_slots, market_data, excluded_map, order, mark_seconds_list, sequence)
        rows.append({"year1_net": snaps[0][1], "year1_cash": snaps[0][2], "year1_breaks": snaps[0][3],
                     "final_net": snaps[1][1], "final_cash": snaps[1][2], "final_breaks": snaps[1][3],
                     "full_structure_days": full_time / DAY_SECONDS})
    return pd.DataFrame(rows)


SEQUENCES = {
    "a_reference_3firms": [(("FTMO", "Blueberry"), "day0"), (("Fivers",), ("after_count", 1))],
    "a2_reference_plus2firms_ensemble": [
        (("FTMO", "Blueberry"), "day0"), (("Fivers", "GFT", "FundedNext"), ("after_count", 1))],
    "b_minimal_absolu": [
        (("FTMO",), "day0"), (("Blueberry",), ("after_count", 1)), (("Fivers",), ("after_count", 2)),
        (("GFT", "FundedNext"), ("after_count", 3))],
    "c_intermediaire": [
        (("FTMO",), "day0"), (("Blueberry", "Fivers"), ("after_count", 1)),
        (("GFT", "FundedNext"), ("after_count", 2))],
    "d1_ftmobb_day0_reste_ensemble": [
        (("FTMO", "Blueberry"), "day0"), (("Fivers", "GFT", "FundedNext"), ("after_count", 1))],
    "d2_ftmoseul_reste_ensemble": [
        (("FTMO",), "day0"), (("Blueberry", "Fivers", "GFT", "FundedNext"), ("after_count", 1))],
}


def build_ctx(trades, slot_arrivals):
    total_horizon_seconds = slot_arrivals[-1]
    mark_seconds_list = [eng.YEAR_SECONDS, total_horizon_seconds]
    block_seconds = eng.BLOCK_MONTHS * DAYS_PER_MONTH * 86400
    blocks = build_blocks(trades, slot_arrivals, block_seconds)
    return total_horizon_seconds, mark_seconds_list, block_seconds, blocks


def summarize(df, label, extra=None):
    row = dict(label=label, profit_final_mean=df["final_net"].mean(), cash_worst=df["final_cash"].max(),
               p_year1_negatif=(df["year1_net"] < 0).mean() * 100, casses_final=df["final_breaks"].mean(),
               delai_structure_complete_median=df["full_structure_days"].median(),
               delai_structure_complete_p90=df["full_structure_days"].quantile(0.9))
    if extra:
        row.update(extra)
    return row


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

        for seq_label, sequence in SEQUENCES.items():
            t0 = time.time()
            df = run_variant(trades, slot_arrivals, blocks, block_s, total_h, marks, market_data, excluded_map,
                             sequence, n_sims=2000, seed=42)
            df.to_csv(f"point2_seq_{seq_label}_{suffix}.csv", index=False)
            row = summarize(df, seq_label, {"winrate": wr_label})
            rows.append(row)
            print(f"  [{seq_label}] profit {row['profit_final_mean']:+,.0f}$ | cash pire cas {row['cash_worst']:,.0f}$ | "
                  f"P(an1<0) {row['p_year1_negatif']:.2f}% | delai structure complete median {row['delai_structure_complete_median']:.0f}j "
                  f"(P90 {row['delai_structure_complete_p90']:.0f}j) ({time.time()-t0:.0f}s)")
        pd.DataFrame(rows).to_csv("point2_seq_summary_partial.csv", index=False)

    pd.DataFrame(rows).to_csv("point2_seq_summary_final.csv", index=False)
    print(f"\nTerminé en {time.time()-t_start:.0f}s.")


if __name__ == "__main__":
    main()
