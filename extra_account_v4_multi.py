"""
Volets 1+2 demandes le 08/08 (suite de extra_account_v3_gft_risk.py) :

VOLET 1 (verification, pas de fuite de contraintes reelles) :
- 1a : le mecanisme "compte supplementaire" de v3 (extra_opened = bool, un
  seul compte supplementaire par firm) n'a JAMAIS compare le capital combine
  par firm a un plafond reel -- verifie : aux tailles de v3 (Blueberry 75k,
  FTMO 200k, GFT 150k, FundedNext 200k fixe, Fivers 400k fixe) aucun
  plafond connu n'est depasse (marge large partout). Pas de correction
  necessaire sur les chiffres v3 deja publies.
- 1b (recherche web 08/08) : plafonds REELS confirmes qui remplacent les
  valeurs approximatives utilisees jusqu'ici dans GROUP_DEFS (cap=400000
  generique) :
    FTMO       : $400,000 capital combine (avant scaling), PAS de limite
                 explicite de nombre de comptes -- confirme par ftmo.com/faq
    Blueberry  : $450,000 capital combine ET max 3 comptes FINANCES
                 simultanes -- confirme par sources tierces (pas de page
                 officielle unique) ; les deux contraintes sont actives ici
                 (le nombre de comptes est le facteur limitant a la taille
                 d'unite retenue, pas le capital)
    GFT (Goat Funded Trader) : $400,000 capital combine, pas de limite de
                 nombre de comptes trouvee -- confirme par help.goatfundedtrader.com
    The5%ers   : $500,000, deja confirme par le support (memoire projet)
    FundedNext : reste fixe a 1 compte 200k (plafond mono-compte), hors
                 perimetre de ce mecanisme (copytrade non confirme, cf 0.4)
- 1c (lotcap_feasibility_check.py, execute separement) : le cap broker 100
  lots + la contrainte de marge sont DEJA appliques a chaque trade via
  eng.feasible_risk_pct (process_trade), quel que soit le palier -- pas de
  correction necessaire. Mesure : a <=200k$ par compte, impact negligeable
  (0.38% de reduction moyenne de risque, 3.1% des trades touches) ; a 400k$
  par compte, deja notable (2.23%, 13%) ; a 500k$, franchement genant
  (5.83%, 29.6%). D'ou le choix de conception ci-dessous : GARDER chaque
  compte supplementaire a une taille unitaire modeste (palier de base x2,
  comme v3) et empiler plusieurs comptes plutot que d'ouvrir un seul gros
  compte -- across tous les runs 2a/2b, aucun compte individuel ne depasse
  100 000$ (FTMO/GFT) ou 50 000$ (Blueberry) ou 100 000$ (Fivers), donc
  l'impact du cap lot/marge par compte reste dans la zone negligeable
  mesuree ci-dessus.

VOLET 2 (le mecanisme actuel est-il trop conservateur) :
- 2a : deplafonne le nombre de comptes supplementaires par firm de
  croissance (Blueberry/FTMO/GFT), sous les VRAIS plafonds 1b (capital ET
  nombre de comptes), au lieu du plafond artificiel "1 seul" de v3.
- 2b : ajoute le meme mecanisme a The5%ers (actuellement fixe a 4x100k=400k,
  sous le plafond confirme 500k -- 1 compte de marge possible), active/
  desactivable via ENABLE_FIVERS_EXTRA pour comparer.
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
from corrected_scaling_mechanism import FEE_RATIO, BASE_PALIER
from scaling_simulation import CHALLENGE_COST_FTMO

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
FINAL_FLEET_RISK = 2.75  # releve de 2.5 a 2.75 le 08/08 (volet 2c, extra_account_v4_risk_sweep.py) :
# sous le mecanisme "compte supplementaire" deplafonne, 2.75% domine 2.5% (meme ruine/annee1<0, +185k$ de profit)
FINAL_GFT_EVAL_RISK = 1.75  # override adopte le 08/08 (extra_account_v3_gft_risk.py, section 0.1 v5)
GROWTH_FIRMS_EXTRA = ("Blueberry", "FTMO", "GFT")
FUNDEDNEXT_FIXED_PALIER = 200000.0
FUNDEDNEXT_FIXED_COST = CHALLENGE_COST_FTMO[200000]
EXTRA_ACCOUNT_MULT = 2.0
EXTRA_THRESHOLD_MULT = 3.0

# --- Volet 1b : vrais plafonds (remplacent le plafond generique 400000 de GROUP_DEFS["cap"]) ---
FIRM_CAPITAL_CAP = {"Blueberry": 450000.0, "FTMO": 400000.0, "GFT": 400000.0, "Fivers": 500000.0}
FIRM_MAX_ACCOUNTS = {"Blueberry": 3, "FTMO": None, "GFT": None, "Fivers": 5}
EXTRA_UNIT_PALIER = {"Blueberry": BASE_PALIER["Blueberry"] * EXTRA_ACCOUNT_MULT,
                      "FTMO": BASE_PALIER["FTMO"] * EXTRA_ACCOUNT_MULT,
                      "GFT": BASE_PALIER["GFT"] * EXTRA_ACCOUNT_MULT,
                      "Fivers": eng.PALIER_5ERS}


def make_growth_acc(palier, cost, active=False):
    a = eng.make_acc(palier, cost, active=active)
    a["base_palier"] = palier
    a["base_cost"] = cost
    return a


def cost_for_extra(gname, palier):
    if gname in ("FTMO", "GFT") and palier == 100000:
        return CHALLENGE_COST_FTMO[100000]  # 500$, corrige (etait 666$ via FEE_RATIO)
    return round(palier * FEE_RATIO)


def run_one(trades, slot_arrivals, market_data, excluded_map, order, ceiling, min_reserve_for_unlock,
            emergency_capital, target_risk_override, eval_risk_override, gft_eval_risk_override,
            reserve_share, extra_threshold_mult, enable_fivers_extra, log_gft_diag=False):
    accounts_by_group = {}
    active0_cost = 0.0
    for group_names, trigger in SEQ_GROUPED:
        for gname in group_names:
            gdef = GROUP_DEFS[gname]
            is_day0 = trigger == "day0"
            if gdef["kind"] == "fivers":
                accs = [eng.make_acc(eng.PALIER_5ERS, eng.SUMMER_COST, active=is_day0) for _ in range(gdef["n_accounts"])]
            elif gname == "FundedNext":
                accs = [make_growth_acc(FUNDEDNEXT_FIXED_PALIER, FUNDEDNEXT_FIXED_COST, active=is_day0)]
            else:
                accs = [make_growth_acc(BASE_PALIER[gname], round(BASE_PALIER[gname] * FEE_RATIO), active=is_day0)
                        for _ in range(gdef["n_accounts"])]
            for a in accs:
                a["_gname"] = gname
            accounts_by_group[gname] = accs
            if is_day0:
                active0_cost += sum(a["cost"] for a in accs)

    extra_growth_firms = list(GROWTH_FIRMS_EXTRA) + (["Fivers"] if enable_fivers_extra else [])
    gft_diag = {}  # id(acc) -> dict, pour TOUT compte GFT (base + supplementaire)
    target_risk = target_risk_override if target_risk_override is not None else TARGET_RISK
    fleet_unlocked = False
    state = {"reserve": 0.0, "ever_funded": False, "real_cash_paid": active0_cost, "total_breaks": 0,
             "group_funded_count": 0, "group_own_funded": set(), "hit_ceiling": False,
             "emergency_remaining": emergency_capital, "is_paid_cum": 0.0,
             "tax_breach_count": 0, "tax_breach_total": 0.0, "tax_breach_max": 0.0,
             "tax_breach_concurrent_with_repurchase": 0, "tax_breach_events": [],
             "extra_accounts_opened": {g: 0 for g in extra_growth_firms}}
    pending_group_trigger = [(names, trig) for names, trig in SEQ_GROUPED if trig != "day0"]
    pending_reopen = []
    pending_group_open = []

    if log_gft_diag:
        for a in accounts_by_group["GFT"]:
            gft_diag[id(a)] = dict(n_challenge_breaks=0, cash_lost_before_funded=0.0, funded=False,
                                    month_opened=0.0, month_funded=None, is_extra=False)

    def combined_net():
        return sum(a["total_funded_pnl"] - a["total_fees_paid"] for accs in accounts_by_group.values() for a in accs)

    def n_active_accounts():
        return sum(1 for accs in accounts_by_group.values() for a in accs if a["active"])

    def downgrade_active():
        return not fleet_unlocked

    def cost_for_palier(gname, palier):
        if gname == "Fivers":
            return None
        if gname == "FundedNext":
            return FUNDEDNEXT_FIXED_COST
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
            if gname == "GFT" and gft_eval_risk_override is not None:
                current_risk = gft_eval_risk_override
            elif eval_risk_override is not None:
                current_risk = eval_risk_override
            else:
                current_risk = RAMP_RISK if acc["trades_taken"] < RAMP_N else target_risk
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
            elif gname in ("FTMO", "GFT"):
                cost = cost_for_extra(gname, acc["palier"]) if acc["palier"] == 100000 else cost_for_palier(gname, acc["palier"])
            else:
                cost = cost_for_palier(gname, acc["palier"])
            was_challenge = acc["phase"] == "challenge"
            if log_gft_diag and gname == "GFT" and was_challenge and id(acc) in gft_diag:
                gft_diag[id(acc)]["n_challenge_breaks"] += 1
                gft_diag[id(acc)]["cash_lost_before_funded"] += cost
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
            if log_gft_diag and gname == "GFT" and id(acc) in gft_diag and not gft_diag[id(acc)]["funded"]:
                gft_diag[id(acc)]["funded"] = True
                gft_diag[id(acc)]["month_funded"] = now / MONTH_SECONDS
            return True
        return False

    def fivers_cost_now(now):
        return eng.SUMMER_COST if now < eng.PRICE_CUTOFF_SECONDS else eng.POST_SUMMER_COST_REAL

    def process_extra_account(now):
        # Volet 2a/2b : plusieurs comptes supplementaires successifs par firm,
        # plafonnes par le vrai capital combine ET le vrai nombre de comptes
        # (1b), au lieu du plafond artificiel "1 seul" de v3.
        if not fleet_unlocked:
            return
        for gname in extra_growth_firms:
            accs = accounts_by_group[gname]
            max_acc = FIRM_MAX_ACCOUNTS.get(gname)
            if max_acc is not None and len(accs) >= max_acc:
                continue
            unit_palier = EXTRA_UNIT_PALIER[gname]
            current_capital = sum(a["palier"] for a in accs)
            if current_capital + unit_palier > FIRM_CAPITAL_CAP[gname]:
                continue
            if gname == "Fivers":
                extra_cost = fivers_cost_now(now)
            elif gname in ("FTMO", "GFT"):
                extra_cost = cost_for_extra(gname, unit_palier)
            else:
                extra_cost = round(unit_palier * FEE_RATIO)
            if state["reserve"] >= extra_threshold_mult * extra_cost:
                state["reserve"] -= extra_cost
                new_acc = make_growth_acc(unit_palier, extra_cost, active=True)
                new_acc["total_fees_paid"] = extra_cost
                new_acc["_gname"] = gname
                accs.append(new_acc)
                state["extra_accounts_opened"][gname] += 1
                if log_gft_diag and gname == "GFT":
                    gft_diag[id(new_acc)] = dict(n_challenge_breaks=0, cash_lost_before_funded=0.0, funded=False,
                                                  month_opened=now / MONTH_SECONDS, month_funded=None, is_extra=True)

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

        process_extra_account(now)
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
        "gft_diag": list(gft_diag.values()),
        "extra_accounts_opened": dict(state["extra_accounts_opened"]),
    }


def run_propagated(pop, market_data, excluded_map, ceiling, min_reserve, emergency, target_risk_ov, eval_risk_ov,
                    gft_eval_risk_ov, reserve_share, extra_threshold_mult, enable_fivers_extra, n_sims, seed,
                    log_gft_diag=False):
    rng_wr = random.Random(seed)
    rng_boot = random.Random(seed + 1)
    rows = []
    all_diag = []
    for _ in range(n_sims):
        wr_draw = rng_wr.betavariate(ALPHA_POST, BETA_POST)
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_draw, 1.0, False, random.Random(rng_wr.random()))
        block_seconds = 2 * DAYS_PER_MONTH * DAY_SECONDS
        blocks = build_blocks(trades, slot_arrivals, block_seconds)
        target_duration = slot_arrivals[-1]
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot, target_duration)
        order = list(range(len(raw_trades)))
        res = run_one(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, min_reserve, emergency,
                       target_risk_ov, eval_risk_ov, gft_eval_risk_ov, reserve_share, extra_threshold_mult,
                       enable_fivers_extra, log_gft_diag=log_gft_diag)
        all_diag.extend(res.pop("gft_diag"))
        rows.append(res)
    return pd.DataFrame(rows), all_diag


if __name__ == "__main__":
    import sys
    t_start = time.time()
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300

    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

    # baseline v3 = 1 seul compte supplementaire par firm => max_accounts = n_accounts de base + 1
    # (Blueberry base=1 -> max 2, FTMO base=2 -> max 3, GFT base=1 -> max 2)
    configs = [
        ("v3_baseline_1_extra_max", False, {"Blueberry": 2, "FTMO": 3, "GFT": 2}),
        ("v4_2a_multi_extra_no_fivers", False, None),
        ("v4_2b_multi_extra_plus_fivers", True, None),
    ]

    rows = []
    for ceiling in (1000.0, 3000.0):
        print(f"\n{'='*100}\nPlafond {ceiling:.0f}$\n{'='*100}")
        for label, enable_fivers, override_max_acc in configs:
            saved_max = dict(FIRM_MAX_ACCOUNTS)
            if override_max_acc is not None:
                for k, v in override_max_acc.items():
                    FIRM_MAX_ACCOUNTS[k] = v
            t0 = time.time()
            df, diag = run_propagated(pop, market_data, excluded_map, ceiling, DEFAULT_RESERVE, DEFAULT_EMERGENCY,
                                       FINAL_FLEET_RISK, FINAL_EVAL_RISK, FINAL_GFT_EVAL_RISK, FINAL_RESERVE_SHARE,
                                       EXTRA_THRESHOLD_MULT, enable_fivers, n_sims, seed=4000, log_gft_diag=True)
            FIRM_MAX_ACCOUNTS.clear()
            FIRM_MAX_ACCOUNTS.update(saved_max)
            net = df["final_net_split"] - df["is_paid_cum"]
            extra_df = pd.DataFrame(list(df["extra_accounts_opened"]))
            avg_extra = {f"extra_{g}_mean": extra_df[g].mean() if g in extra_df else 0.0 for g in
                         ("Blueberry", "FTMO", "GFT", "Fivers")}
            row = dict(ceiling=ceiling, config=label, profit=net.mean(),
                       ruine=(net < 0).sum() / len(df) * 100,
                       annee1_neg=(df["year1_net_split"] < 0).sum() / len(df) * 100,
                       **avg_extra)
            rows.append(row)
            print(f"[{label}] profit={row['profit']:+,.0f}$ | ruine={row['ruine']:.2f}% | "
                  f"P(annee1<0)={row['annee1_neg']:.2f}% | extra moy BB={avg_extra['extra_Blueberry_mean']:.2f} "
                  f"FTMO={avg_extra['extra_FTMO_mean']:.2f} GFT={avg_extra['extra_GFT_mean']:.2f} "
                  f"Fivers={avg_extra['extra_Fivers_mean']:.2f} ({time.time()-t0:.0f}s)")
        pd.DataFrame(rows).to_csv("extra_account_v4_multi.csv", index=False)

    pd.DataFrame(rows).to_csv("extra_account_v4_multi.csv", index=False)
    print(f"\nTermine en {time.time()-t_start:.0f}s.")
