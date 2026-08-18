"""
Reponse au point ouvert #2 (budget reel 1000e vs plafond optimal 3000$) :
teste un plafond hybride PROGRESSIF (1000$ -> 2000$ -> 3000$), la montee
etant declenchee par la RESERVE DU PROJET elle-meme (jamais un nouvel apport
personnel), evenementielle (reserve >= seuil x plafond courant), coherente
avec la methodologie deja validee pour les seuils FXIFY/Ment Funding et pour
la holding (section precedente).

Split prop firm applique (confirme reel, cf. split_tax_model.py) ; fiscalite
NON appliquee ici (deja montre separement qu'elle n'interagit quasiment pas
avec le plafond -- 0/6400 breach -- ce script isole la question du plafond
progressif seule, pour rester lisible).

Point de verification explicitement demande : le cash REELLEMENT sorti de la
poche du trader (real_cash_paid, cumulatif, ne diminue jamais) ne doit pas
depasser 1000$ tant que la reserve n'a pas "finance" la montee au palier
suivant. Comme le plafond ne fait QUE borner le montant maximal empruntable
a un instant donne (pas garantir que la reserve suffira ensuite), ceci est
verifie EMPIRIQUEMENT (pas suppose) : distribution de real_cash_paid au
moment ou chaque palier est franchi, et P(real_cash_paid > 1000$) sous le
scenario progressif.
"""
import random
import time

import numpy as np
import pandas as pd

import robustness_5ers_risk_challenge as eng
from point123_startingfirm_optimization import GROUP_DEFS, build_group_seq_map, make_accounts_for_group
from point_liquidity_rules import STARTER, FIRST_TIER_OVERRIDES, REST_GROUPS, SEQUENCE, build_ctx, RAMP_RISK, RAMP_N, TARGET_RISK, CORR_TH
from real_cash_risk_year1_block_bootstrap import DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs
from split_tax_model import split_rate_for

POP_CONSTRUCT_SEED = 123
DAY_SECONDS = 86400
YEAR_SECONDS = 365.25 * DAY_SECONDS
MONTH_SECONDS = DAYS_PER_MONTH * DAY_SECONDS
CEILING_LEVELS = [1000.0, 2000.0, 3000.0]


def handle_cost_hybrid(cost, state, pending_list, pending_key, on_success):
    ceiling = state["ceiling"]
    if state["reserve"] >= cost:
        state["reserve"] -= cost
        on_success()
        return
    shortfall = cost - state["reserve"]
    state["reserve"] = 0.0
    room = max(0.0, ceiling - state["real_cash_paid"])
    if shortfall <= room:
        state["real_cash_paid"] += shortfall
        on_success()
    else:
        paid_now = room
        remaining = shortfall - paid_now
        state["real_cash_paid"] += paid_now
        state["hit_ceiling"] = True
        pending_list.append({"key": pending_key, "cost_remaining": remaining, "on_success": on_success})


def process_pending(state, pending_list):
    i = 0
    while i < len(pending_list):
        item = pending_list[i]
        if state["reserve"] >= item["cost_remaining"]:
            state["reserve"] -= item["cost_remaining"]
            item["on_success"]()
            pending_list.pop(i)
        else:
            i += 1


def run_one(trades, slot_arrivals, market_data, excluded_map, order, ceiling_mode, escalation_mult,
            apply_split=True):
    """ceiling_mode : float fixe (1000.0 ou 3000.0), ou 'progressive'."""
    seq_map = build_group_seq_map(SEQUENCE, FIRST_TIER_OVERRIDES)
    accounts_by_group = {}
    active0_cost = 0.0
    for group_names, trigger in SEQUENCE:
        for gname in group_names:
            gdef = GROUP_DEFS[gname]
            is_day0 = trigger == "day0"
            accs = make_accounts_for_group(gname, gdef, active=is_day0, seq_map=seq_map)
            for a in accs:
                a["upgrades"] = 0
            accounts_by_group[gname] = accs
            if is_day0:
                active0_cost += sum(a["cost"] for a in accs)

    is_progressive = ceiling_mode == "progressive"
    start_ceiling = CEILING_LEVELS[0] if is_progressive else ceiling_mode

    state = {"reserve": 0.0, "ever_funded": False, "real_cash_paid": active0_cost, "total_breaks": 0,
             "group_funded_count": 0, "group_own_funded": set(), "hit_ceiling": False,
             "full_structure_month": None, "ceiling": start_ceiling, "ceiling_idx": 0,
             "escalation_months": [], "escalation_cash_at_trigger": []}
    pending_group_trigger = [(names, trig) for names, trig in SEQUENCE if trig != "day0"]
    pending_reopen = []
    pending_group_open = []

    def combined_net():
        return sum(a["total_funded_pnl"] - a["total_fees_paid"] for accs in accounts_by_group.values() for a in accs)

    def reopen_account(acc, cost):
        acc["active"] = True
        acc["total_fees_paid"] += cost
        acc["phase"] = "challenge"
        acc["cumulative_since_reset"] = 0.0
        acc["peak_since_reset"] = 0.0
        acc["trading_days_since_reset"] = set()
        acc["daily_pnl"] = {}

    def open_group(gname):
        for a in accounts_by_group[gname]:
            a["active"] = True
            a["total_fees_paid"] = a["cost"]

    def process_trade(acc, trade, now, daily_loss_pct, cost_override=None):
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
            net_pnl = pnl * split_rate_for(acc) if (apply_split and pnl > 0) else pnl
            acc["total_funded_pnl"] += net_pnl
            if net_pnl > 0:
                state["reserve"] += net_pnl * eng.RESERVE_SHARE

        trailing_dd = acc["peak_since_reset"] - acc["cumulative_since_reset"]
        daily_dd = -acc["daily_pnl"][close_day]
        broke = (trailing_dd >= eng.BREAK_DD_PCT / 100 * acc["palier"] or daily_dd >= daily_loss_pct / 100 * acc["palier"])

        just_funded_own = False
        if broke:
            state["total_breaks"] += 1
            cost = cost_override if cost_override is not None else acc["cost"]
            acc["active"] = False
            handle_cost_hybrid(cost, state, pending_reopen, id(acc), lambda a=acc, c=cost: reopen_account(a, c))
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

    def process_growth_upgrade():
        for gname, accs in accounts_by_group.items():
            gdef = GROUP_DEFS[gname]
            if gdef["kind"] != "growth":
                continue
            seq, cost_map, upgrade_map, cap = seq_map[gname]

            def combined(exclude_idx=None, accs=accs):
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
                if would_be > cap:
                    continue
                if state["reserve"] >= ucost:
                    state["reserve"] -= ucost
                    acc["total_fees_paid"] += ucost
                    acc["palier"] = next_tier
                    acc["cost"] = cost_map[next_tier]
                    acc["phase"] = "challenge"
                    acc["cumulative_since_reset"] = 0.0
                    acc["peak_since_reset"] = 0.0
                    acc["trading_days_since_reset"] = set()
                    acc["upgrades"] = acc.get("upgrades", 0) + 1

    def structure_complete():
        for g in ("Blueberry", "FTMO", "Fivers", "GFT", "FundedNext"):
            if not accounts_by_group[g][0]["active"]:
                return False
        return True

    year1_snapshot = {}

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]

        if is_progressive and state["ceiling_idx"] < len(CEILING_LEVELS) - 1:
            if state["reserve"] >= escalation_mult * state["ceiling"]:
                state["ceiling_idx"] += 1
                state["ceiling"] = CEILING_LEVELS[state["ceiling_idx"]]
                state["escalation_months"].append(now / MONTH_SECONDS)
                state["escalation_cash_at_trigger"].append(state["real_cash_paid"])

        if not year1_snapshot and now >= YEAR_SECONDS:
            year1_snapshot["net"] = combined_net()
            year1_snapshot["cash"] = state["real_cash_paid"]

        for gname, accs in accounts_by_group.items():
            gdef = GROUP_DEFS[gname]
            for acc in accs:
                cost_now = None
                if gdef["kind"] == "fivers":
                    cost_now = eng.SUMMER_COST if now < eng.PRICE_CUTOFF_SECONDS else eng.POST_SUMMER_COST_REAL
                was_challenge = acc["active"] and acc["phase"] == "challenge"
                process_trade(acc, trade, now, gdef["dd"], cost_override=cost_now)
                if was_challenge and acc["phase"] == "funded" and gname not in state["group_own_funded"]:
                    state["group_own_funded"].add(gname)
                    state["group_funded_count"] += 1

        process_growth_upgrade()
        process_pending(state, pending_reopen)
        process_pending(state, pending_group_open)

        still_pending = []
        for group_names, trig in pending_group_trigger:
            _, n_req = trig
            if state["group_funded_count"] >= n_req:
                for gname in group_names:
                    cost0 = sum(a["cost"] for a in accounts_by_group[gname])
                    handle_cost_hybrid(cost0, state, pending_group_open, gname,
                                       lambda g=gname: open_group(g))
            else:
                still_pending.append((group_names, trig))
        pending_group_trigger = still_pending

        if state["full_structure_month"] is None and structure_complete():
            state["full_structure_month"] = now / MONTH_SECONDS

    final_net = combined_net()
    if not year1_snapshot:
        year1_snapshot = {"net": final_net, "cash": state["real_cash_paid"]}
    return {
        "final_net_company": final_net,
        "year1_net_company": year1_snapshot["net"],
        "year1_cash_paid": year1_snapshot["cash"],
        "real_cash_paid_final": state["real_cash_paid"],
        "hit_ceiling": state["hit_ceiling"],
        "month_reach_2000": state["escalation_months"][0] if len(state["escalation_months"]) >= 1 else None,
        "month_reach_3000": state["escalation_months"][1] if len(state["escalation_months"]) >= 2 else None,
        "cash_at_trigger_2000": state["escalation_cash_at_trigger"][0] if len(state["escalation_cash_at_trigger"]) >= 1 else None,
        "cash_at_trigger_3000": state["escalation_cash_at_trigger"][1] if len(state["escalation_cash_at_trigger"]) >= 2 else None,
        "full_structure_month": state["full_structure_month"],
    }


def run_variant(trades, slot_arrivals, blocks, block_seconds, target_duration, ceiling_mode, escalation_mult,
                n_sims, seed):
    rng = random.Random(seed)
    rows = []
    for _ in range(n_sims):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, target_duration)
        order = list(range(len(raw_trades)))
        rows.append(run_one(raw_trades, raw_slots, market_data, excluded_map, order, ceiling_mode, escalation_mult))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    import sys
    t_start = time.time()
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 800
    escalation_mults = [float(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [1.5, 2.0, 3.0]

    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

    all_rows = []
    for wr_label, wr_target in [("40.09%_reel", None), ("37.66%_P10bayesien", 0.3766)]:
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_target, 1.0, False, random.Random(POP_CONSTRUCT_SEED))
        total_h, marks, block_s, blocks = build_ctx(trades, slot_arrivals)
        print(f"\n{'='*100}\nWINRATE {wr_label}\n{'='*100}")

        for label, mode, mult in [("fixe_1000", 1000.0, None), ("fixe_3000", 3000.0, None)] + \
                                  [(f"progressif_seuil{m}x", "progressive", m) for m in escalation_mults]:
            t0 = time.time()
            df = run_variant(trades, slot_arrivals, blocks, block_s, total_h, mode, mult, n_sims=n_sims, seed=42)
            df.to_csv(f"progressive_ceiling_{label}_{wr_label.split('%')[0].replace('.', '_')}.csv", index=False)
            row = dict(
                winrate=wr_label, config=label,
                profit_year1_mean=df["year1_net_company"].mean(),
                profit_final_mean=df["final_net_company"].mean(),
                profit_final_median=df["final_net_company"].median(),
                cash_final_max=df["real_cash_paid_final"].max(),
                cash_final_p95=df["real_cash_paid_final"].quantile(0.95),
                p_hit_ceiling_pct=df["hit_ceiling"].mean() * 100,
                month_reach_3000_median=df["month_reach_3000"].median() if "progressif" in label else None,
                p_never_reach_3000_pct=df["month_reach_3000"].isna().mean() * 100 if "progressif" in label else None,
                cash_at_trigger_2000_max=df["cash_at_trigger_2000"].max() if "progressif" in label else None,
                cash_at_trigger_3000_max=df["cash_at_trigger_3000"].max() if "progressif" in label else None,
                p_cash_over_1000_pct=(df["real_cash_paid_final"] > 1000.0).mean() * 100,
                cash_over_1000_amount_mean=(df.loc[df["real_cash_paid_final"] > 1000.0, "real_cash_paid_final"] - 1000.0).mean() if (df["real_cash_paid_final"] > 1000.0).any() else 0.0,
            )
            all_rows.append(row)
            extra = ""
            if "progressif" in label:
                extra = (f" | mois median atteinte 3000$={row['month_reach_3000_median']} | "
                         f"P(jamais 3000$)={row['p_never_reach_3000_pct']:.1f}% | "
                         f"cash au moment du 1er trigger (max)={row['cash_at_trigger_2000_max']}$/{row['cash_at_trigger_3000_max']}$")
            print(f"[{label}] profit an1 (moy)={row['profit_year1_mean']:+,.0f}$ | profit final (moy)={row['profit_final_mean']:+,.0f}$ | "
                  f"cash pire cas={row['cash_final_max']:,.0f}$ (P95={row['cash_final_p95']:,.0f}$) | "
                  f"P(plafond atteint)={row['p_hit_ceiling_pct']:.1f}% | "
                  f"P(cash perso > 1000$)={row['p_cash_over_1000_pct']:.2f}% (depassement moyen si oui={row['cash_over_1000_amount_mean']:,.0f}$)"
                  f"{extra} ({time.time()-t0:.0f}s)")
            pd.DataFrame(all_rows).to_csv("progressive_ceiling_summary.csv", index=False)

    pd.DataFrame(all_rows).to_csv("progressive_ceiling_summary.csv", index=False)
    print(f"\nTermine en {time.time()-t_start:.0f}s.")
