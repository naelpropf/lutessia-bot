"""
Feuille de route annee 1 (08/08, 4e relance) : structure optimisee (Blueberry
25k seule au jour 0, reste de la flotte -- FTMO + The5%ers + GFT + FundedNext
-- active ensemble des le 1er financement Blueberry). Construit un chemin
mensuel concret (pas juste des stats agregees horizon complet) :
  - Palier median/P10/P90 atteint par chaque groupe croissance a chaque mois
  - Cout cumule reellement sorti de la poche (real_cash_paid), median/P10/P90,
    mensuel
  - Statut d'immunite (P(ever_funded) par mois)
  - Mois median ou la reserve poolee franchirait les seuils FXIFY (50k$) et
    Ment Funding (20k$) DEJA UTILISES dans les sessions precedentes -- pas de
    reouverture reelle de comptes FXIFY/Ment ici, seulement le moment ou LA
    RESERVE de CETTE structure atteindrait ces seuils
  - Risque residuel post-immunite (point 2) : shortfall de reserve absorbe
    SANS etre facture au cash personnel (convention du modele, cf. code) --
    quantifie separement, frequence et ampleur en annee 1
"""
import random
import time

import numpy as np
import pandas as pd

import robustness_5ers_risk_challenge as eng
import point3a_ramp_fixed as ramp_eng
from point123_startingfirm_optimization import (
    GROUP_DEFS, build_group_seq_map, make_accounts_for_group,
)
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs

POP_CONSTRUCT_SEED = 123
TARGET_RISK = 2.5
RAMP_RISK, RAMP_N = 2.0, 5
CORR_TH = 0.6
DAY_SECONDS = 86400
MONTH_SECONDS = DAYS_PER_MONTH * DAY_SECONDS
N_MONTHS = 12
N_SIMULATIONS = 2000

FXIFY_RESERVE_THRESHOLD = 50000
MENT_RESERVE_THRESHOLD = 20000

STARTER = "Blueberry"
FIRST_TIER_OVERRIDES = {"Blueberry": 25000}
REST_GROUPS = ("FTMO", "Fivers", "GFT", "FundedNext")
SEQUENCE = [((STARTER,), "day0"), (REST_GROUPS, ("after_count", 1))]


def process_growth_upgrade_track(accounts_by_group, seq_map, state):
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


def run_one(trades, slot_arrivals, market_data, excluded_map, order, n_months_target):
    seq_map = build_group_seq_map(SEQUENCE, FIRST_TIER_OVERRIDES)
    accounts_by_group = {}
    active0_cost = 0.0
    for group_names, trigger in SEQUENCE:
        for gname in group_names:
            gdef = GROUP_DEFS[gname]
            is_day0 = trigger == "day0"
            accs = make_accounts_for_group(gname, gdef, active=is_day0, seq_map=seq_map)
            accounts_by_group[gname] = accs
            if is_day0:
                active0_cost += sum(a["cost"] for a in accs)

    state = {"reserve": 0.0, "ever_funded": False, "real_cash_paid": active0_cost, "total_breaks": 0,
             "group_funded_count": 0, "group_own_funded": set(),
             "post_immunity_shortfall_absorbed": 0.0}
    pending = [(names, trig) for names, trig in SEQUENCE if trig != "day0"]

    def activate_group(gname):
        accs = accounts_by_group[gname]
        cost0 = sum(a["cost"] for a in accs)
        if state["reserve"] >= cost0:
            state["reserve"] -= cost0
        else:
            shortfall = cost0 - state["reserve"]
            state["reserve"] = 0.0
            if not state["ever_funded"]:
                state["real_cash_paid"] += shortfall
            else:
                state["post_immunity_shortfall_absorbed"] += shortfall
        for a in accs:
            a["active"] = True
            a["total_fees_paid"] = a["cost"]

    def process_trade_custom(acc, trade, now, daily_loss_pct, cost_override=None):
        if not acc["active"]:
            return False
        close_time = now + trade["hold_seconds"]
        acc["open_positions"] = [(t, c) for (t, c) in acc["open_positions"] if c > now]
        if len(acc["open_positions"]) >= eng.MAX_POSITIONS:
            return False
        if any(t in excluded_map[trade["ticker"]] for (t, _) in acc["open_positions"]):
            return False

        current_risk = RAMP_RISK if acc["trades_taken"] < RAMP_N else TARGET_RISK
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
        broke = (trailing_dd >= eng.BREAK_DD_PCT / 100 * acc["palier"] or daily_dd >= daily_loss_pct / 100 * acc["palier"])

        just_funded_own = False
        if broke:
            state["total_breaks"] += 1
            cost = cost_override if cost_override is not None else acc["cost"]
            if state["reserve"] >= cost:
                state["reserve"] -= cost
            else:
                shortfall = cost - state["reserve"]
                state["reserve"] = 0.0
                if not state["ever_funded"]:
                    state["real_cash_paid"] += shortfall
                else:
                    state["post_immunity_shortfall_absorbed"] += shortfall
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
            just_funded_own = True
            state["ever_funded"] = True
            acc["cumulative_since_reset"] = 0.0
            acc["peak_since_reset"] = 0.0
            acc["trading_days_since_reset"] = set()
        return just_funded_own

    monthly_cash, monthly_ever_funded = [], []
    monthly_tier_by_group = {g: [] for g in ["Blueberry", "FTMO", "GFT", "FundedNext"]}
    monthly_fivers_active = []
    monthly_post_immunity_shortfall = []
    fxify_threshold_month, ment_threshold_month = None, None

    last_month_idx = -1
    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]
        month_idx = int(now // MONTH_SECONDS)

        if month_idx > last_month_idx:
            for m in range(last_month_idx + 1, min(month_idx, n_months_target) + 1):
                monthly_cash.append(state["real_cash_paid"])
                monthly_ever_funded.append(state["ever_funded"])
                monthly_fivers_active.append(accounts_by_group["Fivers"][0]["active"])
                monthly_post_immunity_shortfall.append(state["post_immunity_shortfall_absorbed"])
                for g in ["Blueberry", "FTMO", "GFT", "FundedNext"]:
                    accs = accounts_by_group[g]
                    monthly_tier_by_group[g].append(min(a["palier"] for a in accs) if accs[0]["active"] else 0)
            last_month_idx = month_idx
            if fxify_threshold_month is None and state["reserve"] >= FXIFY_RESERVE_THRESHOLD:
                fxify_threshold_month = month_idx
            if ment_threshold_month is None and state["reserve"] >= MENT_RESERVE_THRESHOLD:
                ment_threshold_month = month_idx
        if month_idx >= n_months_target:
            break

        for gname, accs in accounts_by_group.items():
            gdef = GROUP_DEFS[gname]
            for acc in accs:
                cost_now = None
                if gdef["kind"] == "fivers":
                    cost_now = eng.SUMMER_COST if now < eng.PRICE_CUTOFF_SECONDS else eng.POST_SUMMER_COST_REAL
                was_challenge = acc["active"] and acc["phase"] == "challenge"
                process_trade_custom(acc, trade, now, gdef["dd"], cost_override=cost_now)
                if was_challenge and acc["phase"] == "funded" and gname not in state["group_own_funded"]:
                    state["group_own_funded"].add(gname)
                    state["group_funded_count"] += 1

        process_growth_upgrade_track(accounts_by_group, seq_map, state)

        if fxify_threshold_month is None and state["reserve"] >= FXIFY_RESERVE_THRESHOLD:
            fxify_threshold_month = month_idx
        if ment_threshold_month is None and state["reserve"] >= MENT_RESERVE_THRESHOLD:
            ment_threshold_month = month_idx

        still_pending = []
        for group_names, trig in pending:
            _, n_req = trig
            if state["group_funded_count"] >= n_req:
                for gname in group_names:
                    activate_group(gname)
            else:
                still_pending.append((group_names, trig))
        pending = still_pending

    while len(monthly_cash) < n_months_target:
        monthly_cash.append(state["real_cash_paid"])
        monthly_ever_funded.append(state["ever_funded"])
        monthly_fivers_active.append(accounts_by_group["Fivers"][0]["active"])
        monthly_post_immunity_shortfall.append(state["post_immunity_shortfall_absorbed"])
        for g in ["Blueberry", "FTMO", "GFT", "FundedNext"]:
            accs = accounts_by_group[g]
            monthly_tier_by_group[g].append(min(a["palier"] for a in accs) if accs[0]["active"] else 0)

    return {
        "monthly_cash": monthly_cash, "monthly_ever_funded": monthly_ever_funded,
        "monthly_tier_by_group": monthly_tier_by_group, "monthly_fivers_active": monthly_fivers_active,
        "monthly_post_immunity_shortfall": monthly_post_immunity_shortfall,
        "fxify_threshold_month": fxify_threshold_month, "ment_threshold_month": ment_threshold_month,
        "final_breaks": state["total_breaks"],
    }


def main():
    t_start = time.time()
    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

    for wr_label, wr_target, suffix in [("40.09%_reel", None, "40_09pct"), ("37.66%_P10bayesien", 0.3766, "37_66pct")]:
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_target, 1.0, False, random.Random(POP_CONSTRUCT_SEED))
        total_horizon = slot_arrivals[-1]
        block_seconds = eng.BLOCK_MONTHS * DAYS_PER_MONTH * 86400
        blocks = build_blocks(trades, slot_arrivals, block_seconds)

        print(f"\n{'='*100}\nWINRATE {wr_label} : {N_SIMULATIONS} runs...\n{'='*100}")
        rng = random.Random(42)
        all_cash, all_ever_funded, all_fivers_active = [], [], []
        all_tiers = {g: [] for g in ["Blueberry", "FTMO", "GFT", "FundedNext"]}
        all_post_shortfall = []
        fxify_months, ment_months = [], []

        t0 = time.time()
        for _ in range(N_SIMULATIONS):
            raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, total_horizon)
            order = list(range(len(raw_trades)))
            res = run_one(raw_trades, raw_slots, market_data, excluded_map, order, N_MONTHS)
            all_cash.append(res["monthly_cash"])
            all_ever_funded.append(res["monthly_ever_funded"])
            all_fivers_active.append(res["monthly_fivers_active"])
            all_post_shortfall.append(res["monthly_post_immunity_shortfall"])
            for g in all_tiers:
                all_tiers[g].append(res["monthly_tier_by_group"][g])
            if res["fxify_threshold_month"] is not None:
                fxify_months.append(res["fxify_threshold_month"])
            if res["ment_threshold_month"] is not None:
                ment_months.append(res["ment_threshold_month"])
        print(f"  ({time.time()-t0:.0f}s)")

        cash_arr = np.array(all_cash)
        ever_funded_arr = np.array(all_ever_funded)
        fivers_arr = np.array(all_fivers_active)
        shortfall_arr = np.array(all_post_shortfall)

        rows = []
        for m in range(N_MONTHS):
            row = {
                "mois": m + 1,
                "cash_p10": np.percentile(cash_arr[:, m], 10), "cash_median": np.percentile(cash_arr[:, m], 50),
                "cash_p90": np.percentile(cash_arr[:, m], 90), "cash_p99": np.percentile(cash_arr[:, m], 99),
                "cash_max": cash_arr[:, m].max(),
                "p_immunite_acquise": ever_funded_arr[:, m].mean() * 100,
                "p_fivers_actif": fivers_arr[:, m].mean() * 100,
                "post_immunity_shortfall_p90": np.percentile(shortfall_arr[:, m], 90),
                "post_immunity_shortfall_max": shortfall_arr[:, m].max(),
                "p_post_immunity_shortfall_gt0": (shortfall_arr[:, m] > 0).mean() * 100,
            }
            for g in all_tiers:
                col = np.array(all_tiers[g])[:, m]
                row[f"{g}_tier_median"] = np.percentile(col, 50)
                row[f"{g}_tier_p10"] = np.percentile(col, 10)
                row[f"{g}_tier_p90"] = np.percentile(col, 90)
            rows.append(row)

        out = pd.DataFrame(rows)
        out.to_csv(f"point_roadmap_year1_{suffix}.csv", index=False)

        print(f"\n--- Feuille de route mensuelle ({wr_label}) ---")
        for r in rows:
            print(f"  Mois {r['mois']:2d} : cash median={r['cash_median']:.0f}$ (P90={r['cash_p90']:.0f}$, P99={r['cash_p99']:.0f}$) | "
                  f"immunite={r['p_immunite_acquise']:.1f}% | 5ers actif={r['p_fivers_actif']:.1f}% | "
                  f"BB={r['Blueberry_tier_median']:.0f}$ FTMO={r['FTMO_tier_median']:.0f}$ GFT={r['GFT_tier_median']:.0f}$ FN={r['FundedNext_tier_median']:.0f}$")

        print(f"\nSeuil reserve FXIFY (50k$) atteint dans l'annee : {len(fxify_months)}/{N_SIMULATIONS} runs "
              f"({len(fxify_months)/N_SIMULATIONS*100:.1f}%)"
              + (f", mois median {np.median(fxify_months):.0f}" if fxify_months else ""))
        print(f"Seuil reserve Ment Funding (20k$) atteint dans l'annee : {len(ment_months)}/{N_SIMULATIONS} runs "
              f"({len(ment_months)/N_SIMULATIONS*100:.1f}%)"
              + (f", mois median {np.median(ment_months):.0f}" if ment_months else ""))

        # distribution cash fin d'annee 1 uniquement
        cash_year1 = cash_arr[:, -1]
        print(f"\n--- Distribution cash reellement sorti, FIN ANNEE 1 uniquement ({wr_label}) ---")
        print(f"Median={np.median(cash_year1):.0f}$ P90={np.percentile(cash_year1,90):.0f}$ "
              f"P95={np.percentile(cash_year1,95):.0f}$ P99={np.percentile(cash_year1,99):.0f}$ Max={cash_year1.max():.0f}$")
        for threshold in [500, 1000, 3000, 5000, 10000]:
            pct = (cash_year1 <= threshold).mean() * 100
            print(f"  % runs sous {threshold}$ en annee 1 : {pct:.1f}%")

        print(f"\nRisque residuel post-immunite (annee 1) : P(shortfall absorbe > 0 a un moment) = "
              f"{(shortfall_arr[:, -1] > 0).mean()*100:.2f}% | P90={np.percentile(shortfall_arr[:,-1],90):.0f}$ | "
              f"max observe={shortfall_arr[:,-1].max():.0f}$")

    print(f"\nTerminé en {time.time()-t_start:.0f}s.")


if __name__ == "__main__":
    main()
