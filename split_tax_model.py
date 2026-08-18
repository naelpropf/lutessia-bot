"""
Reponse aux 4 questions du 07/08 (session split + fiscalite SASU) :

1. Le split prop firm (profit share verse au trader, typiquement 80/20 ->
   90/10 avec le scaling) N'EST PAS applique dans les moteurs existants
   (point123, point_liquidity_hybrid, point_roadmap, hybrid_reserve_switch...) :
   `total_funded_pnl` et l'accumulation de `reserve` (via RESERVE_SHARE=0.80,
   qui est un ratio d'allocation INTERNE reserve/dispo, pas le split prop
   firm) utilisent le P&L brut de trading, 100% conserve. Confirme par lecture
   de robustness_5ers_risk_challenge.process_trade et
   point_liquidity_hybrid.run_one (aucune reference a un split/payout %
   nulle part dans le repo). Ce script corrige ca.

2. Modelise le calendrier IS SASU reel (annee 1 sans acompte, solde au 15 du
   4e mois suivant cloture ; annee 2+ 4 acomptes trimestriels sur l'IS N-1 si
   IS N-1 > 3000e, puis regularisation) et le risque de conflit de tresorerie
   avec les rachats de comptes casses, en partageant EXACTEMENT le meme
   plafond hybride (ceiling) que les rachats -- mais SANS la regle "wait" pour
   l'impot (une dette fiscale ne peut pas etre reportee indefiniment sans
   penalite, contrairement a la reouverture d'un compte) : tout depassement
   du plafond par un paiement d'IS est donc compte comme une VRAIE breche
   (au lieu d'etre absorbe silencieusement), ce qui quantifie directement le
   risque demande.

3. Deux politiques de dividendes (reserve maximale vs retraits reguliers),
   comparees sur le profit net reellement percu par la personne (apres IS +
   PFU 30%), le cash pire cas, et la vitesse de reconstitution de la reserve.

4. Simulation combinee cas probable / pire cas plausible.

Approximations explicitement assumees (a faire confirmer par expert-comptable
/ avocat fiscaliste, cf. section 0 du document de contexte) :
  - Split modelise comme un barreme croissant par palier de compte
    (80% -> +5pt par upgrade, plafonne a 90%), applique UNIQUEMENT sur les
    trades gagnants (un profit-share ne prelève rien sur les pertes) --
    aucun barreme exact par firm/palier n'est source dans ce projet.
  - Bareme IS applique tel quel sur les montants en $ du modele (pas de
    conversion EUR/USD -- le projet raisonne deja en $ partout).
  - Annee fiscale alignee sur le lancement (t=0 = debut d'exercice), duree
    365,25j.
  - Dates d'acomptes/solde approximees par offsets calendaires fixes
    (15 mars/juin/sept/dec = ~73,5/165,5/257,5/348,5j apres le debut
    d'exercice ; solde = ~105j apres la cloture, soit mi-avril).
  - Deficit reportable / credit d'IS non modelise (regularisation negative
    plafonnee a 0 -- volontairement conservateur, ne cree pas de credit
    d'impot reutilisable).
  - Dividendes preleves uniquement sur la reserve disponible (jamais forces
    au-dela -- decision discretionnaire, coherente avec l'enonce).
"""
import random
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
from point123_startingfirm_optimization import GROUP_DEFS, build_group_seq_map, make_accounts_for_group
from point_liquidity_rules import STARTER, FIRST_TIER_OVERRIDES, REST_GROUPS, SEQUENCE, build_ctx, RAMP_RISK, RAMP_N, TARGET_RISK, CORR_TH
from real_cash_risk_year1_block_bootstrap import DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs

POP_CONSTRUCT_SEED = 123
DAY_SECONDS = 86400
YEAR_SECONDS = 365.25 * DAY_SECONDS
MONTH_SECONDS = DAYS_PER_MONTH * DAY_SECONDS

# --- Split prop firm (approximation documentee, cf. docstring) ---
SPLIT_BASE, SPLIT_STEP, SPLIT_CAP = 0.80, 0.05, 0.90

# --- Calendrier fiscal SASU/IS (offsets en jours depuis le debut d'exercice) ---
Q_OFFSETS_DAYS = [73.5, 165.5, 257.5, 348.5]   # 15 mars / juin / sept / dec
SOLDE_OFFSET_DAYS = 105.0                       # ~15 avril, 4e mois apres cloture
IS_THRESHOLD_ACOMPTE = 3000.0
IS_RATE_LOW, IS_RATE_HIGH, IS_BRACKET = 0.15, 0.25, 42500.0
ACOMPTE_FRACTION = 0.25

# --- Dividendes ---
DIVIDEND_POLICIES = {
    "reserve_max": 0.0,      # 3a : ~0 distribue, tout capitalise
    "retraits_reguliers": 0.5,  # 3b : 50% du profit apres-IS distribue chaque annee
}
PFU_RATE = 0.30


def compute_is(profit):
    profit = max(0.0, profit)
    if profit <= IS_BRACKET:
        return profit * IS_RATE_LOW
    return IS_BRACKET * IS_RATE_LOW + (profit - IS_BRACKET) * IS_RATE_HIGH


def split_rate_for(acc):
    return min(SPLIT_CAP, SPLIT_BASE + SPLIT_STEP * acc.get("upgrades", 0))


def handle_cost_hybrid(cost, state, ceiling, pending_list, pending_key, on_success):
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
        remaining = shortfall - room
        state["real_cash_paid"] += paid_now
        state["hit_ceiling"] = True
        pending_list.append({"key": pending_key, "cost_remaining": remaining, "on_success": on_success})


def handle_tax_payment(amount, state, ceiling, now, pending_reopen, pending_group_open):
    """Paye un impot depuis la reserve, puis (si insuffisant) depuis la place
    encore libre sous le plafond -- et, contrairement aux couts de compte, ne
    reporte JAMAIS l'excedent (une dette fiscale ne se met pas en 'attente') :
    tout depassement est facture comme une VRAIE breche du plafond, enregistree."""
    if amount <= 0:
        return
    if state["reserve"] >= amount:
        state["reserve"] -= amount
        return
    shortfall = amount - state["reserve"]
    state["reserve"] = 0.0
    room = max(0.0, ceiling - state["real_cash_paid"])
    paid_within = min(shortfall, room)
    state["real_cash_paid"] += paid_within
    overflow = shortfall - paid_within
    if overflow > 1e-9:
        state["real_cash_paid"] += overflow  # force paye au-dela du plafond -> vraie breche
        concurrent = bool(pending_reopen) or bool(pending_group_open)
        state["tax_breach_count"] += 1
        state["tax_breach_total"] += overflow
        state["tax_breach_max"] = max(state["tax_breach_max"], overflow)
        state["tax_breach_concurrent_with_repurchase"] += 1 if concurrent else 0
        state["tax_breach_events"].append((now, overflow, concurrent))


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


def run_one(trades, slot_arrivals, market_data, excluded_map, order, ceiling, dividend_frac,
            apply_split=True, apply_tax=True, horizon_marks=None):
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

    state = {"reserve": 0.0, "ever_funded": False, "real_cash_paid": active0_cost, "total_breaks": 0,
             "group_funded_count": 0, "group_own_funded": set(), "hit_ceiling": False,
             "full_structure_month": None,
             "tax_breach_count": 0, "tax_breach_total": 0.0, "tax_breach_max": 0.0,
             "tax_breach_concurrent_with_repurchase": 0, "tax_breach_events": [],
             "dividends_gross_cum": 0.0, "dividends_net_personal_cum": 0.0,
             "is_paid_cum": 0.0}
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
            if apply_split and pnl > 0:
                net_pnl = pnl * split_rate_for(acc)
            else:
                net_pnl = pnl
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
            handle_cost_hybrid(cost, state, ceiling, pending_reopen, id(acc), lambda a=acc, c=cost: reopen_account(a, c))
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

    # --- etat fiscal ---
    fy_start_net = {0: 0.0}
    fy_closed = set()
    is_by_year = {}
    acomptes_paid_by_year = {}
    next_fy_to_close = 0

    def close_fiscal_year(y, now_close):
        profit_y = combined_net() - fy_start_net.get(y, 0.0)
        is_y = compute_is(profit_y) if apply_tax else 0.0
        is_by_year[y] = is_y
        state["is_paid_cum"] += 0.0  # comptabilise au paiement reel, pas ici
        fy_start_net[y + 1] = combined_net()
        # solde de l'annee y, du (deja) verse en acomptes pendant l'annee y+1
        acomptes_y = acomptes_paid_by_year.get(y, 0.0)
        solde = max(0.0, is_y - acomptes_y)
        solde_time = (y + 1) * YEAR_SECONDS + SOLDE_OFFSET_DAYS * DAY_SECONDS
        tax_events.append((solde_time, solde, f"solde_annee{y}"))
        # dividende decide a la cloture (politique fixe), preleve sur la reserve disponible
        if dividend_frac > 0:
            after_tax = max(0.0, profit_y - is_y)
            target = after_tax * dividend_frac
            div_time = solde_time  # decision au meme moment que le solde (resultat connu)
            tax_events.append((div_time, -target, f"dividende_annee{y}"))  # montant negatif = marque dividende
        # programme les 4 acomptes de l'annee y+1 si IS(y) > seuil
        if is_y > IS_THRESHOLD_ACOMPTE:
            for q_off in Q_OFFSETS_DAYS:
                t_acompte = (y + 1) * YEAR_SECONDS + q_off * DAY_SECONDS
                amt = ACOMPTE_FRACTION * is_y
                tax_events.append((t_acompte, amt, f"acompte_annee{y+1}"))
                acomptes_paid_by_year[y + 1] = acomptes_paid_by_year.get(y + 1, 0.0) + amt
        tax_events.sort(key=lambda e: e[0])

    tax_events = []  # (time, amount, label) ; amount<0 => dividende (traite a part)
    year1_snapshot = {}

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]

        if not year1_snapshot and now >= YEAR_SECONDS:
            year1_snapshot["final_net_company"] = combined_net()
            year1_snapshot["real_cash_paid"] = state["real_cash_paid"]
            year1_snapshot["is_paid_cum"] = state["is_paid_cum"]
            year1_snapshot["dividends_net_personal_cum"] = state["dividends_net_personal_cum"]

        while (next_fy_to_close + 1) * YEAR_SECONDS <= now:
            close_fiscal_year(next_fy_to_close, now)
            next_fy_to_close += 1

        # traite les evenements fiscaux dus
        i = 0
        while i < len(tax_events):
            t_ev, amt, label = tax_events[i]
            if t_ev > now:
                i += 1
                continue
            tax_events.pop(i)
            if amt >= 0:
                if apply_tax:
                    handle_tax_payment(amt, state, ceiling, now, pending_reopen, pending_group_open)
                    state["is_paid_cum"] += amt
            else:
                div_target = -amt
                available = min(state["reserve"], div_target)
                if available > 0:
                    state["reserve"] -= available
                    state["dividends_gross_cum"] += available
                    state["dividends_net_personal_cum"] += available * (1 - PFU_RATE)

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
                    handle_cost_hybrid(cost0, state, ceiling, pending_group_open, gname,
                                       lambda g=gname: open_group(g))
            else:
                still_pending.append((group_names, trig))
        pending_group_trigger = still_pending

        if state["full_structure_month"] is None and structure_complete():
            state["full_structure_month"] = now / MONTH_SECONDS

    final_net = combined_net()
    if not year1_snapshot:
        year1_snapshot = {"final_net_company": final_net, "real_cash_paid": state["real_cash_paid"],
                           "is_paid_cum": state["is_paid_cum"], "dividends_net_personal_cum": state["dividends_net_personal_cum"]}
    return {
        "final_net_company": final_net,
        "year1_net_company": year1_snapshot["final_net_company"],
        "year1_cash_paid": year1_snapshot["real_cash_paid"],
        "year1_is_paid": year1_snapshot["is_paid_cum"],
        "real_cash_paid": state["real_cash_paid"],
        "hit_ceiling": state["hit_ceiling"],
        "total_breaks": state["total_breaks"],
        "full_structure_month": state["full_structure_month"],
        "is_paid_cum": state["is_paid_cum"],
        "dividends_gross_cum": state["dividends_gross_cum"],
        "dividends_net_personal_cum": state["dividends_net_personal_cum"],
        "tax_breach_count": state["tax_breach_count"],
        "tax_breach_total": state["tax_breach_total"],
        "tax_breach_max": state["tax_breach_max"],
        "tax_breach_concurrent": state["tax_breach_concurrent_with_repurchase"],
    }


def run_variant(trades, slot_arrivals, blocks, block_seconds, target_duration, ceiling, dividend_frac,
                apply_split, apply_tax, n_sims, seed):
    rng = random.Random(seed)
    rows = []
    for _ in range(n_sims):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, target_duration)
        order = list(range(len(raw_trades)))
        rows.append(run_one(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, dividend_frac,
                             apply_split, apply_tax))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    import sys
    t_start = time.time()
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    ceilings = [float(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [1000.0]

    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

    scenarios = [
        ("brut_sans_split_sans_tax", False, False, 0.0),
        ("net_split_sans_tax", True, False, 0.0),
        ("net_split_tax_reserve_max", True, True, DIVIDEND_POLICIES["reserve_max"]),
        ("net_split_tax_retraits_reguliers", True, True, DIVIDEND_POLICIES["retraits_reguliers"]),
    ]

    all_rows = []
    for wr_label, wr_target in [("40.09%_reel", None), ("37.66%_P10bayesien", 0.3766)]:
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_target, 1.0, False, random.Random(POP_CONSTRUCT_SEED))
        total_h, marks, block_s, blocks = build_ctx(trades, slot_arrivals)
        print(f"\n{'='*100}\nWINRATE {wr_label}\n{'='*100}")

        for ceiling in ceilings:
            for label, use_split, use_tax, div_frac in scenarios:
                t0 = time.time()
                df = run_variant(trades, slot_arrivals, blocks, block_s, total_h, ceiling, div_frac,
                                  use_split, use_tax, n_sims=n_sims, seed=42)
                df.to_csv(f"split_tax_model_{label}_ceiling{int(ceiling)}_{wr_label.split('%')[0].replace('.', '_')}.csv", index=False)
                row = dict(
                    winrate=wr_label, scenario=label, ceiling=ceiling, n_sims=n_sims,
                    profit_year1_company_mean=df["year1_net_company"].mean(),
                    profit_final_company_mean=df["final_net_company"].mean(),
                    profit_final_company_median=df["final_net_company"].median(),
                    cash_pire_cas_max=df["real_cash_paid"].max(),
                    cash_p95=df["real_cash_paid"].quantile(0.95),
                    p_hit_ceiling_pct=df["hit_ceiling"].mean() * 100,
                    is_paid_cum_mean=df["is_paid_cum"].mean(),
                    dividendes_bruts_mean=df["dividends_gross_cum"].mean(),
                    dividendes_net_personne_mean=df["dividends_net_personal_cum"].mean(),
                    p_tax_breach_pct=(df["tax_breach_count"] > 0).mean() * 100,
                    tax_breach_amount_mean_when_occurs=(df.loc[df["tax_breach_count"] > 0, "tax_breach_total"].mean()
                                                         if (df["tax_breach_count"] > 0).any() else 0.0),
                    tax_breach_amount_max=df["tax_breach_max"].max(),
                    p_tax_breach_concurrent_pct=(df["tax_breach_concurrent"] > 0).mean() * 100,
                    full_structure_month_median=df["full_structure_month"].median(),
                )
                all_rows.append(row)
                print(f"[ceiling={ceiling:.0f}$][{label}] profit final (moy) {row['profit_final_company_mean']:+,.0f}$ | "
                      f"cash pire cas {row['cash_pire_cas_max']:,.0f}$ (P95={row['cash_p95']:,.0f}$) | "
                      f"P(plafond atteint pour rachats)={row['p_hit_ceiling_pct']:.1f}% | "
                      f"IS paye (moy)={row['is_paid_cum_mean']:,.0f}$ | div. net perso (moy)={row['dividendes_net_personne_mean']:,.0f}$ | "
                      f"P(breche fiscale du plafond)={row['p_tax_breach_pct']:.1f}% (montant moy si breche="
                      f"{row['tax_breach_amount_mean_when_occurs']:,.0f}$, max={row['tax_breach_amount_max']:,.0f}$, "
                      f"concurrent rachat={row['p_tax_breach_concurrent_pct']:.1f}%) ({time.time()-t0:.0f}s)")
                pd.DataFrame(all_rows).to_csv("split_tax_model_summary.csv", index=False)

    pd.DataFrame(all_rows).to_csv("split_tax_model_summary.csv", index=False)
    print(f"\nTermine en {time.time()-t_start:.0f}s.")
