"""
Point 5 (07/08, 2e relance) : ajout d'une 4e firm de croissance (accessible des
le depart, daily DD confortable, pas de bascule par seuil necessaire) sur la
config FINALE verrouillee (RR>=1,25/trail0,15xSL/maxpos=3/corr=0,6/rampe
2,0%x5 trades/The5%ers retardee).

a) Sensibilite generique : nouvelle firm hypothetique DD=5%, week-end
   autorise, plafond combine variable {300k,400k,800k,2M} -- sequence de
   paliers etendue [50k,200k,500k,1M,2M] (costs approximes proportionnellement
   au meme ratio ~0,5-0,6% que les tiers deja utilises dans le projet, non
   sources au-dela de 500k -- a corriger si des prix officiels sont trouves
   pour une firm reelle a ces paliers).
b) Goat Funded Trader (concret, confirme support) : DD=4%, week-end autorise,
   comptes 5k-400k, plafond combine 400k, ouverture SEQUENTIELLE (comme
   FTMO/Blueberry -- PAS d'achat groupe). Sequence de paliers approximee sur
   le modele FTMO (50k->100k->200k, memes couts -- prix GFT reels non
   sources, a corriger si trouves) puisque le plafond combine (400k) est
   identique a FTMO.
c) FundedNext, 1 SEUL compte (hypothese basse en attendant clarification
   support sur la portee de l'interdiction copytrade post-financement) :
   DD=5% (Stellar 2-Step), week-end autorise, meme structure que FTMO
   (50k->100k->200k), PAS de plafond combine modelise (un seul compte, donc
   sans objet). Economiquement IDENTIQUE a l'ajout d'un 3e compte FTMO --
   compare directement pour verifier.
"""
import random
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
import point3a_ramp_fixed as ramp_eng
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs, N_SIMULATIONS

POP_CONSTRUCT_SEED = 123
TARGET_RISK = 2.5
RAMP_RISK, RAMP_N = 2.0, 5
MAXPOS, CORR_TH = 3, 0.6

# sequence etendue generique, cout approx proportionnel (~0.5-0.6% du palier),
# NON SOURCE au-dela de 500k -- flag explicite dans le rapport
EXT_TIER_SEQUENCE = [50000, 200000, 500000, 1000000, 2000000]
EXT_CHALLENGE_COST = {50000: 333, 200000: 1000, 500000: 3000, 1000000: 6000, 2000000: 12000}
EXT_UPGRADE_COST = {200000: 1000, 500000: 3000, 1000000: 6000, 2000000: 12000}

FTMO_TIER_SEQUENCE = list(eng.TIER_SEQUENCE_FTMO)
FTMO_CHALLENGE_COST = dict(eng.CHALLENGE_COST_FTMO)
FTMO_UPGRADE_COST = dict(eng.UPGRADE_COST_FTMO)


def build_ctx(trades, slot_arrivals):
    total_horizon_seconds = slot_arrivals[-1]
    mark_seconds_list = [eng.YEAR_SECONDS, total_horizon_seconds]
    block_seconds = eng.BLOCK_MONTHS * DAYS_PER_MONTH * 86400
    blocks = build_blocks(trades, slot_arrivals, block_seconds)
    return total_horizon_seconds, mark_seconds_list, block_seconds, blocks


def run_variant_extra_firm(trades, slot_arrivals, blocks, block_seconds, target_duration, mark_seconds_list,
                           market_data, excluded_map, extra_firm_dd, extra_firm_cap, extra_tier_seq,
                           extra_challenge_cost, extra_upgrade_cost, n_sims=2000, seed=42):
    """3 comptes existants (FTMO x2, Blueberry x1, DD standard 5%) + 1 compte
    supplementaire de la nouvelle firm (DD=extra_firm_dd, plafond=extra_firm_cap,
    propre sequence de paliers), + The5%ers retardee comme d'habitude."""
    firms = list(eng.GROWTH_FIRMS) + ["EXTRA"]
    tier_seq_by_firm = dict(eng.TIER_SEQUENCE_BY_FIRM)
    tier_seq_by_firm["EXTRA"] = extra_tier_seq
    cost_by_firm = dict(eng.CHALLENGE_COST_BY_FIRM)
    cost_by_firm["EXTRA"] = extra_challenge_cost
    upgrade_by_firm = dict(eng.UPGRADE_COST_BY_FIRM)
    upgrade_by_firm["EXTRA"] = extra_upgrade_cost
    firm_cap = dict(eng.FIRM_CAP)
    firm_cap["EXTRA"] = extra_firm_cap
    daily_loss_by_firm = {"FTMO": eng.DAILY_LOSS_GROWTH, "Blueberry": eng.DAILY_LOSS_GROWTH, "EXTRA": extra_firm_dd}

    def process_growth_upgrade_n(accounts, state):
        def firm_combined(firm, exclude_idx=None):
            return sum(a["palier"] for i, a in enumerate(accounts)
                       if firms[i] == firm and i != exclude_idx and a["active"])
        for i, acc in enumerate(accounts):
            if not acc["active"] or acc["phase"] != "funded":
                continue
            firm = firms[i]
            seq = tier_seq_by_firm[firm]
            idx = seq.index(acc["palier"])
            if idx + 1 >= len(seq):
                continue
            next_tier = seq[idx + 1]
            cost = upgrade_by_firm[firm][next_tier]
            would_be = firm_combined(firm, exclude_idx=i) + next_tier
            if state["reserve"] >= cost and would_be <= firm_cap[firm]:
                state["reserve"] -= cost
                acc["total_fees_paid"] += cost
                acc["palier"] = next_tier
                acc["cost"] = cost_by_firm[firm][next_tier]
                acc["phase"] = "challenge"
                acc["cumulative_since_reset"] = 0.0
                acc["peak_since_reset"] = 0.0
                acc["trading_days_since_reset"] = set()

    def run_one(trades, slot_arrivals, order):
        fivers = [eng.make_acc(eng.PALIER_5ERS, eng.SUMMER_COST, active=False) for _ in range(eng.N_5ERS)]
        growth = [eng.make_acc(tier_seq_by_firm[f][0], cost_by_firm[f][tier_seq_by_firm[f][0]]) for f in firms]
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
                cost_now = eng.SUMMER_COST if now < eng.PRICE_CUTOFF_SECONDS else eng.POST_SUMMER_COST_REAL
                ramp_eng.process_trade_ramp_pure(acc, trade, now, market_data, excluded_map, eng.DAILY_LOSS_5ERS_REAL,
                                                 eng.BREAK_DD_PCT, state, RAMP_RISK, RAMP_N, TARGET_RISK,
                                                 cost_override=cost_now)

            for i, acc in enumerate(growth):
                firm = firms[i]
                just_funded = ramp_eng.process_trade_ramp_pure(acc, trade, now, market_data, excluded_map,
                                                                daily_loss_by_firm[firm], eng.BREAK_DD_PCT, state,
                                                                RAMP_RISK, RAMP_N, TARGET_RISK)
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

            process_growth_upgrade_n(growth, state)

        while mark_idx < len(marks_sorted):
            snapshots.append((marks_sorted[mark_idx], combined_net(), state["real_cash_paid"], state["total_breaks"]))
            mark_idx += 1
        return snapshots

    rng = random.Random(seed)
    rows = []
    for _ in range(n_sims):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, target_duration)
        order = list(range(len(raw_trades)))
        snaps = run_one(raw_trades, raw_slots, order)
        rows.append({"year1_net": snaps[0][1], "year1_cash": snaps[0][2], "year1_breaks": snaps[0][3],
                     "final_net": snaps[1][1], "final_cash": snaps[1][2], "final_breaks": snaps[1][3]})
    return pd.DataFrame(rows)


def summarize(df, label, extra=None):
    row = dict(label=label, profit_final_mean=df["final_net"].mean(), cash_worst=df["final_cash"].max(),
               casses_final=df["final_breaks"].mean(), p_year1_negatif=(df["year1_net"] < 0).mean() * 100)
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

        # reference : structure actuelle 3 firms, sans ajout
        t0 = time.time()
        df_ref = ramp_eng.run_variant_ramp(trades, slot_arrivals, blocks, block_s, total_h, marks, market_data,
                                           excluded_map, RAMP_RISK, RAMP_N, TARGET_RISK, n_sims=2000, seed=42)
        row_ref = summarize(df_ref, "reference_3firms", {"winrate": wr_label})
        rows.append(row_ref)
        print(f"  REFERENCE (3 firms) : profit {row_ref['profit_final_mean']:+,.0f}$ | cash pire cas {row_ref['cash_worst']:,.0f}$ | "
              f"casses {row_ref['casses_final']:.1f} ({time.time()-t0:.0f}s)")

        # a) sensibilite generique, DD5%, plafonds varies
        for cap in [300000, 400000, 800000, 2000000]:
            t0 = time.time()
            df = run_variant_extra_firm(trades, slot_arrivals, blocks, block_s, total_h, marks, market_data,
                                        excluded_map, 5.0, cap, EXT_TIER_SEQUENCE, EXT_CHALLENGE_COST,
                                        EXT_UPGRADE_COST, n_sims=2000, seed=42)
            df.to_csv(f"point5_generic_cap{cap}_{suffix}.csv", index=False)
            row = summarize(df, f"generique_DD5_cap{cap}", {"winrate": wr_label})
            rows.append(row)
            print(f"  a) generique DD5%/cap={cap}$ : profit {row['profit_final_mean']:+,.0f}$ | cash pire cas {row['cash_worst']:,.0f}$ | "
                  f"casses {row['casses_final']:.1f} ({time.time()-t0:.0f}s)")

        # b) Goat Funded Trader concret
        t0 = time.time()
        df_gft = run_variant_extra_firm(trades, slot_arrivals, blocks, block_s, total_h, marks, market_data,
                                        excluded_map, 4.0, 400000, FTMO_TIER_SEQUENCE, FTMO_CHALLENGE_COST,
                                        FTMO_UPGRADE_COST, n_sims=2000, seed=42)
        df_gft.to_csv(f"point5_gft_{suffix}.csv", index=False)
        row_gft = summarize(df_gft, "goat_funded_trader", {"winrate": wr_label})
        rows.append(row_gft)
        print(f"  b) Goat Funded Trader (DD4%/cap400k) : profit {row_gft['profit_final_mean']:+,.0f}$ | "
              f"cash pire cas {row_gft['cash_worst']:,.0f}$ | casses {row_gft['casses_final']:.1f} ({time.time()-t0:.0f}s)")

        # c) FundedNext, 1 compte (DD5%, comme un 3e FTMO)
        t0 = time.time()
        df_fn = run_variant_extra_firm(trades, slot_arrivals, blocks, block_s, total_h, marks, market_data,
                                       excluded_map, 5.0, 200000, FTMO_TIER_SEQUENCE, FTMO_CHALLENGE_COST,
                                       FTMO_UPGRADE_COST, n_sims=2000, seed=42)
        df_fn.to_csv(f"point5_fundednext1_{suffix}.csv", index=False)
        row_fn = summarize(df_fn, "fundednext_1compte", {"winrate": wr_label})
        rows.append(row_fn)
        print(f"  c) FundedNext 1 compte (DD5%, ~3e FTMO) : profit {row_fn['profit_final_mean']:+,.0f}$ | "
              f"cash pire cas {row_fn['cash_worst']:,.0f}$ | casses {row_fn['casses_final']:.1f} ({time.time()-t0:.0f}s)")

        print(f"  -> Gain marginal GFT vs reference : {row_gft['profit_final_mean']-row_ref['profit_final_mean']:+,.0f}$ "
              f"| cash supplementaire : {row_gft['cash_worst']-row_ref['cash_worst']:+,.0f}$")
        print(f"  -> Gain marginal FundedNext-1 vs reference : {row_fn['profit_final_mean']-row_ref['profit_final_mean']:+,.0f}$ "
              f"| cash supplementaire : {row_fn['cash_worst']-row_ref['cash_worst']:+,.0f}$")

        pd.DataFrame(rows).to_csv("point5_newfirm_summary_partial.csv", index=False)

    pd.DataFrame(rows).to_csv("point5_newfirm_summary_final.csv", index=False)
    print(f"\nTerminé en {time.time()-t_start:.0f}s.")


if __name__ == "__main__":
    main()
