"""
Alternative au Scaling Plan A1 (mesure precedente : 2 274 631$/2 298 627$,
-60,5% vs l'ancien mecanisme d'achat) : au lieu de faire grossir un compte
EXISTANT (ce qui exige qu'il survive plusieurs mois consecutifs avec profit
soutenu -- peu realiste vu l'attrition independante deja mesuree, ~7-9j entre
casses), utilise le surplus de reserve pour OUVRIR UN NOUVEAU COMPTE SEPARE
a un palier plus gros (un cran au-dessus du palier de base de la firm), EN
PLUS des comptes existants -- jamais en remplacement. Meme principe que le
deblocage groupe de la flotte a 30k$, applique en continu apres deblocage.

Limite au 4 firms "growth" (Blueberry, FTMO, GFT, FundedNext -- cout
proportionnel via FEE_RATIO deja utilise dans corrected_scaling_mechanism.py).
Fivers (The5%ers) exclu de ce levier : aucun prix source pour un palier
200k, pas de tier superieur documente dans le projet -- simplification
assumee et documentee, pas testee ici.

Plafond de securite : 1 compte supplementaire max par firm growth (4 max au
total) pour garder le test tractable -- pas d'empilement illimite. Palier du
compte supplementaire = 2x le palier de base de la firm (Blueberry 25k->50k,
FTMO/GFT/FundedNext 50k->100k, coherent avec la vraie sequence FTMO
50k->100k->200k).

3 configs comparees :
  1. "none"          : flotte fixe, aucun mecanisme de croissance apres
                        deblocage (nouveau baseline)
  2. "scaling"        : Scaling Plan A1 (deja mesure, repris ici pour verif
                        croisee sur la meme graine)
  3. "extra_account"  : compte supplementaire finance par surplus de reserve
                        (seuil teste : 2x/3x/5x le cout du nouveau compte)
"""
import random
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
from point123_startingfirm_optimization import GROUP_DEFS
from point_liquidity_rules import RAMP_RISK, RAMP_N, TARGET_RISK, CORR_TH, DAY_SECONDS
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from split_tax_model import compute_is, handle_tax_payment, IS_THRESHOLD_ACOMPTE, Q_OFFSETS_DAYS, \
    SOLDE_OFFSET_DAYS, ACOMPTE_FRACTION
from corrected_scaling_mechanism import FEE_RATIO, BASE_PALIER, SCALING_WINDOW_MONTHS, \
    SCALING_PROFIT_THRESHOLD_PCT, SCALING_MULT

ALPHA_POST, BETA_POST = 260, 388
YEAR_SECONDS = 365.25 * DAY_SECONDS
MONTH_SECONDS = DAYS_PER_MONTH * DAY_SECONDS
STARTER = "Blueberry"
SEQ_GROUPED = [((STARTER,), "day0"), (("FTMO", "Fivers", "GFT", "FundedNext"), ("after_count", 1))]
DEFAULT_RESERVE = 30000.0
DEFAULT_EMERGENCY = 300.0
SPLIT_FLAT = 0.80
FINAL_RESERVE_SHARE = 0.95
FINAL_EVAL_RISK = 2.25
FINAL_FLEET_RISK = 2.5
GROWTH_FIRMS = ("Blueberry", "FTMO", "GFT", "FundedNext")
EXTRA_ACCOUNT_MULT = 2.0  # palier du compte supplementaire = 2x le palier de base


def make_growth_acc(palier, active=False):
    a = eng.make_acc(palier, round(palier * FEE_RATIO), active=active)
    a["base_palier"] = palier
    a["base_cost"] = round(palier * FEE_RATIO)
    a["scaling_window_start"] = 0.0
    a["scaling_window_pnl"] = 0.0
    return a


def run_one(trades, slot_arrivals, market_data, excluded_map, order, ceiling, min_reserve_for_unlock,
            emergency_capital, target_risk_override, eval_risk_override, reserve_share,
            growth_mode, extra_threshold_mult):
    accounts_by_group = {}
    active0_cost = 0.0
    for group_names, trigger in SEQ_GROUPED:
        for gname in group_names:
            gdef = GROUP_DEFS[gname]
            is_day0 = trigger == "day0"
            if gdef["kind"] == "fivers":
                accs = [eng.make_acc(eng.PALIER_5ERS, eng.SUMMER_COST, active=is_day0) for _ in range(gdef["n_accounts"])]
            else:
                accs = [make_growth_acc(BASE_PALIER[gname], active=is_day0) for _ in range(gdef["n_accounts"])]
            for a in accs:
                a["_gname"] = gname
            accounts_by_group[gname] = accs
            if is_day0:
                active0_cost += sum(a["cost"] for a in accs)

    extra_opened = {g: False for g in GROWTH_FIRMS}
    target_risk = target_risk_override if target_risk_override is not None else TARGET_RISK
    fleet_unlocked = False
    state = {"reserve": 0.0, "ever_funded": False, "real_cash_paid": active0_cost, "total_breaks": 0,
             "group_funded_count": 0, "group_own_funded": set(), "hit_ceiling": False,
             "emergency_remaining": emergency_capital, "is_paid_cum": 0.0,
             "tax_breach_count": 0, "tax_breach_total": 0.0, "tax_breach_max": 0.0,
             "tax_breach_concurrent_with_repurchase": 0, "tax_breach_events": []}
    pending_group_trigger = [(names, trig) for names, trig in SEQ_GROUPED if trig != "day0"]
    pending_reopen = []
    pending_group_open = []

    def combined_net():
        return sum(a["total_funded_pnl"] - a["total_fees_paid"] for accs in accounts_by_group.values() for a in accs)

    def n_active_accounts():
        return sum(1 for accs in accounts_by_group.values() for a in accs if a["active"])

    def downgrade_active():
        return not fleet_unlocked

    def cost_for_palier(gname, palier):
        if gname == "Fivers":
            return None
        return round(palier * FEE_RATIO)

    def handle_cost_hybrid(cost, pending_list, pending_key, on_success):
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

    def process_pending(pending_list):
        i = 0
        while i < len(pending_list):
            item = pending_list[i]
            if state["reserve"] >= item["cost_remaining"]:
                state["reserve"] -= item["cost_remaining"]
                item["on_success"]()
                pending_list.pop(i)
            else:
                i += 1

    def reopen_account(acc, cost):
        acc["active"] = True
        acc["total_fees_paid"] += cost
        acc["phase"] = "challenge"
        acc["cumulative_since_reset"] = 0.0
        acc["peak_since_reset"] = 0.0
        acc["trading_days_since_reset"] = set()
        acc["daily_pnl"] = {}
        if downgrade_active() and acc.get("_gname") == STARTER:
            acc["palier"] = acc["base_palier"]
            acc["cost"] = acc["base_cost"]

    def open_group(gname):
        for a in accounts_by_group[gname]:
            a["active"] = True
            a["total_fees_paid"] = a["cost"]

    def try_emergency_bootstrap():
        if n_active_accounts() != 0 or emergency_capital <= 0 or state["emergency_remaining"] <= 0:
            return
        bb_acc = accounts_by_group[STARTER][0]
        cost = bb_acc["base_cost"] if downgrade_active() else bb_acc["cost"]
        if state["emergency_remaining"] >= cost:
            state["emergency_remaining"] -= cost
            reopen_account(bb_acc, cost)
            pending_reopen[:] = [p for p in pending_reopen if p["key"] != id(bb_acc)]

    def process_trade(acc, trade, now, daily_loss_pct, gname, cost_override=None):
        if not acc["active"]:
            return False
        close_time = now + trade["hold_seconds"]
        acc["open_positions"] = [(t, c) for (t, c) in acc["open_positions"] if c > now]
        if len(acc["open_positions"]) >= eng.MAX_POSITIONS:
            return False
        if any(t in excluded_map[trade["ticker"]] for (t, _) in acc["open_positions"]):
            return False

        if acc["phase"] == "challenge":
            current_risk = eval_risk_override if eval_risk_override is not None else (
                RAMP_RISK if acc["trades_taken"] < RAMP_N else target_risk)
        else:
            current_risk = RAMP_RISK if acc["trades_taken"] < RAMP_N else target_risk
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
            net_pnl = pnl * SPLIT_FLAT if pnl > 0 else pnl
            acc["total_funded_pnl"] += net_pnl
            if gname != "Fivers":
                acc["scaling_window_pnl"] += net_pnl
            if net_pnl > 0:
                state["reserve"] += net_pnl * reserve_share

        trailing_dd = acc["peak_since_reset"] - acc["cumulative_since_reset"]
        daily_dd = -acc["daily_pnl"][close_day]
        broke = (trailing_dd >= eng.BREAK_DD_PCT / 100 * acc["palier"] or daily_dd >= daily_loss_pct / 100 * acc["palier"])

        if broke:
            state["total_breaks"] += 1
            if downgrade_active() and gname == STARTER:
                cost = acc["base_cost"]
            elif gname == "Fivers":
                cost = cost_override
            else:
                cost = cost_for_palier(gname, acc["palier"])
            acc["active"] = False
            handle_cost_hybrid(cost, pending_reopen, id(acc), lambda a=acc, c=cost: reopen_account(a, c))
            return False

        if (acc["phase"] == "challenge" and acc["cumulative_since_reset"] >= eng.CHALLENGE_TARGET_PCT / 100 * acc["palier"]
                and len(acc["trading_days_since_reset"]) >= eng.MIN_TRADING_DAYS):
            acc["phase"] = "funded"
            state["ever_funded"] = True
            acc["cumulative_since_reset"] = 0.0
            acc["peak_since_reset"] = 0.0
            acc["trading_days_since_reset"] = set()
            if gname != "Fivers":
                acc["scaling_window_start"] = now
                acc["scaling_window_pnl"] = 0.0
            return True
        return False

    def process_scaling(now):
        if growth_mode != "scaling":
            return
        for gname, accs in accounts_by_group.items():
            gdef = GROUP_DEFS[gname]
            if gdef["kind"] != "growth":
                continue
            cap = gdef["cap"]
            window_seconds = SCALING_WINDOW_MONTHS[gname] * MONTH_SECONDS

            def combined(exclude_idx=None, accs=accs):
                return sum(a["palier"] for i, a in enumerate(accs) if i != exclude_idx and a["active"])

            for i, acc in enumerate(accs):
                if not acc["active"] or acc["phase"] != "funded":
                    continue
                if now - acc["scaling_window_start"] < window_seconds:
                    continue
                threshold = SCALING_PROFIT_THRESHOLD_PCT / 100 * acc["palier"]
                if acc["scaling_window_pnl"] >= threshold:
                    room = max(0.0, cap - combined(exclude_idx=i))
                    new_palier = min(acc["palier"] * SCALING_MULT, acc["palier"] + room)
                    if new_palier > acc["palier"]:
                        acc["palier"] = new_palier
                        acc["cost"] = cost_for_palier(gname, new_palier)
                acc["scaling_window_start"] = now
                acc["scaling_window_pnl"] = 0.0

    def process_extra_account(now):
        if growth_mode != "extra_account" or not fleet_unlocked:
            return None
        for gname in GROWTH_FIRMS:
            if extra_opened[gname]:
                continue
            extra_palier = BASE_PALIER[gname] * EXTRA_ACCOUNT_MULT
            extra_cost = round(extra_palier * FEE_RATIO)
            if state["reserve"] >= extra_threshold_mult * extra_cost:
                state["reserve"] -= extra_cost
                new_acc = make_growth_acc(extra_palier, active=True)
                new_acc["total_fees_paid"] = extra_cost
                new_acc["_gname"] = gname
                accounts_by_group[gname].append(new_acc)
                extra_opened[gname] = True
                return now / MONTH_SECONDS
        return None

    def structure_complete():
        for g in ("Blueberry", "FTMO", "Fivers", "GFT", "FundedNext"):
            if not accounts_by_group[g][0]["active"]:
                return False
        return True

    fy_start_net = {0: 0.0}
    acomptes_paid_by_year = {}
    next_fy_to_close = 0
    tax_events = []

    def close_fiscal_year(y):
        profit_y = combined_net() - fy_start_net.get(y, 0.0)
        is_y = compute_is(profit_y)
        fy_start_net[y + 1] = combined_net()
        acomptes_y = acomptes_paid_by_year.get(y, 0.0)
        solde = max(0.0, is_y - acomptes_y)
        solde_time = (y + 1) * YEAR_SECONDS + SOLDE_OFFSET_DAYS * DAY_SECONDS
        tax_events.append((solde_time, solde))
        if is_y > IS_THRESHOLD_ACOMPTE:
            for q_off in Q_OFFSETS_DAYS:
                t_acompte = (y + 1) * YEAR_SECONDS + q_off * DAY_SECONDS
                amt = ACOMPTE_FRACTION * is_y
                tax_events.append((t_acompte, amt))
                acomptes_paid_by_year[y + 1] = acomptes_paid_by_year.get(y + 1, 0.0) + amt
        tax_events.sort(key=lambda e: e[0])

    full_structure_month = None
    reserve_hit_30k_month = None
    year1_net_split = None
    first_extra_month = None
    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]

        if year1_net_split is None and now >= YEAR_SECONDS:
            year1_net_split = combined_net()

        while (next_fy_to_close + 1) * YEAR_SECONDS <= now:
            close_fiscal_year(next_fy_to_close)
            next_fy_to_close += 1

        i = 0
        while i < len(tax_events):
            t_ev, amt = tax_events[i]
            if t_ev > now:
                i += 1
                continue
            tax_events.pop(i)
            handle_tax_payment(amt, state, ceiling, now, pending_reopen, pending_group_open)
            state["is_paid_cum"] += amt

        for gname, accs in list(accounts_by_group.items()):
            gdef = GROUP_DEFS[gname]
            for acc in list(accs):
                cost_now = None
                if gdef["kind"] == "fivers":
                    cost_now = eng.SUMMER_COST if now < eng.PRICE_CUTOFF_SECONDS else eng.POST_SUMMER_COST_REAL
                was_challenge = acc["active"] and acc["phase"] == "challenge"
                just_funded = process_trade(acc, trade, now, gdef["dd"], gname, cost_override=cost_now)
                if was_challenge and just_funded and gname not in state["group_own_funded"]:
                    state["group_own_funded"].add(gname)
                    state["group_funded_count"] += 1

        process_scaling(now)
        extra_month = process_extra_account(now)
        if extra_month is not None and first_extra_month is None:
            first_extra_month = extra_month
        process_pending(pending_reopen)
        process_pending(pending_group_open)
        try_emergency_bootstrap()

        if reserve_hit_30k_month is None and state["reserve"] >= min_reserve_for_unlock:
            reserve_hit_30k_month = now / MONTH_SECONDS

        still_pending = []
        for group_names, trig in pending_group_trigger:
            _, n_req = trig
            if state["group_funded_count"] >= n_req and state["reserve"] >= min_reserve_for_unlock:
                for gname in group_names:
                    cost0 = sum(a["cost"] for a in accounts_by_group[gname])
                    handle_cost_hybrid(cost0, pending_group_open, gname, lambda g=gname: open_group(g))
                fleet_unlocked = True
            else:
                still_pending.append((group_names, trig))
        pending_group_trigger = still_pending

        if full_structure_month is None and structure_complete():
            full_structure_month = now / MONTH_SECONDS

    if year1_net_split is None:
        year1_net_split = combined_net()

    return {
        "final_net_split": combined_net(),
        "is_paid_cum": state["is_paid_cum"],
        "year1_net_split": year1_net_split,
        "reserve_hit_30k_month": reserve_hit_30k_month,
        "first_extra_month": first_extra_month,
    }


def run_propagated(pop, market_data, excluded_map, ceiling, min_reserve, emergency, target_risk_ov, eval_risk_ov,
                    reserve_share, growth_mode, extra_threshold_mult, n_sims, seed):
    rng_wr = random.Random(seed)
    rng_boot = random.Random(seed + 1)
    rows = []
    for _ in range(n_sims):
        wr_draw = rng_wr.betavariate(ALPHA_POST, BETA_POST)
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_draw, 1.0, False, random.Random(rng_wr.random()))
        block_seconds = 2 * DAYS_PER_MONTH * DAY_SECONDS
        blocks = build_blocks(trades, slot_arrivals, block_seconds)
        target_duration = slot_arrivals[-1]
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot, target_duration)
        order = list(range(len(raw_trades)))
        res = run_one(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, min_reserve, emergency,
                       target_risk_ov, eval_risk_ov, reserve_share, growth_mode, extra_threshold_mult)
        rows.append(res)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    import sys
    t_start = time.time()
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300

    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

    rows = []
    for ceiling in (1000.0, 3000.0):
        print(f"\n{'='*100}\nPlafond {ceiling:.0f}$\n{'='*100}")

        for label, gm, thr in [("1. Aucun scaling (baseline)", "none", None)]:
            t0 = time.time()
            df = run_propagated(pop, market_data, excluded_map, ceiling, DEFAULT_RESERVE, DEFAULT_EMERGENCY,
                                 FINAL_FLEET_RISK, FINAL_EVAL_RISK, FINAL_RESERVE_SHARE, gm, thr, n_sims, seed=4000)
            net = df["final_net_split"] - df["is_paid_cum"]
            row = dict(ceiling=ceiling, config=label, profit=net.mean(),
                       ruine=(net < 0).sum() / len(df) * 100,
                       annee1_neg=(df["year1_net_split"] < 0).sum() / len(df) * 100,
                       delai_surplus=None)
            rows.append(row)
            print(f"[{label}] profit={row['profit']:+,.0f}$ | ruine={row['ruine']:.2f}% | "
                  f"P(annee1<0)={row['annee1_neg']:.2f}% ({time.time()-t0:.0f}s)")

        for thr in (2.0, 3.0, 5.0):
            label = f"3. Compte supplementaire (seuil={thr:.0f}x)"
            t0 = time.time()
            df = run_propagated(pop, market_data, excluded_map, ceiling, DEFAULT_RESERVE, DEFAULT_EMERGENCY,
                                 FINAL_FLEET_RISK, FINAL_EVAL_RISK, FINAL_RESERVE_SHARE, "extra_account", thr,
                                 n_sims, seed=4000)
            net = df["final_net_split"] - df["is_paid_cum"]
            delai = df["first_extra_month"].median()
            row = dict(ceiling=ceiling, config=label, profit=net.mean(),
                       ruine=(net < 0).sum() / len(df) * 100,
                       annee1_neg=(df["year1_net_split"] < 0).sum() / len(df) * 100,
                       delai_surplus=delai)
            rows.append(row)
            print(f"[{label}] profit={row['profit']:+,.0f}$ | ruine={row['ruine']:.2f}% | "
                  f"P(annee1<0)={row['annee1_neg']:.2f}% | delai 1er compte suppl.={delai} mois ({time.time()-t0:.0f}s)")
        pd.DataFrame(rows).to_csv("extra_account_vs_scaling.csv", index=False)

    pd.DataFrame(rows).to_csv("extra_account_vs_scaling.csv", index=False)
    print(f"\nTermine en {time.time()-t_start:.0f}s.")
