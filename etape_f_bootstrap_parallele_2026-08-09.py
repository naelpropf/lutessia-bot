"""
Etape F (08/09 soir) : premier LEVIER STRUCTUREL (pas parametrique) teste sur
le chantier -- bootstrap parallele jour 0.

Constat de depart (diagnostic annee1<0 du 08/09, registre section 2.5) : sous
le moteur actuel, 57% des cas annee1<0 sont PRE-deblocage. Mecanisme :
UN SEUL compte (Blueberry STARTER) porte toute la generation de reserve avant
que le seuil de deblocage FTMO (1000$) soit atteint -- si ce compte casse, la
generation de reserve s'arrete NET jusqu'a sa reouverture (payee sur le
plafond de cash restant, ou en dernier recours le capital d'urgence
DEFAULT_EMERGENCY=300$). C'est un point de defaillance unique structurel :
tous les 9 leviers testes jusqu'ici (registre section 2.5) etaient des
REGLAGES du meme mecanisme (seuils, rampes, plafonds) -- aucun n'a change la
structure elle-meme.

IDEE TESTEE ICI : au lieu d'un seul starter Blueberry (166$), ouvrir
PLUSIEURS starters bon marche chez des firms DIFFERENTES des le jour 0, en
parallele. Si l'un casse, les autres continuent de generer de la reserve --
diversification du risque de "temps mort" pre-deblocage. Le cout : le meme
plafond de cash personnel (1000$/3000$) doit desormais couvrir PLUSIEURS
couts d'ouverture jour 0 au lieu d'un seul, ce qui reduit la marge disponible
pour les reouvertures ulterieures. C'est un vrai arbitrage a mesurer, pas un
free lunch suppose.

===========================================================================
1. SCOPING -- prix reels des starters les moins chers (source :
   engine_multiformat.FORMATS[...]["price"], meme grille que le reste du
   projet, formats REF actuels uniquement -- changer de format n'est PAS
   dans le perimetre de ce test, cf. Chantier 2 deja rejete pour cette
   raison).
===========================================================================

Prix du palier de base REELLEMENT utilise par le moteur (BASE_PALIER,
corrected_scaling_mechanism.py -- PAS le plus petit palier liste dans la
grille de prix, verifie empiriquement par un run de controle : GFT et FTMO
utilisent tous deux palier=50 000$, pas 25 000$) :
    Blueberry  (Prime2Step,   25 000$)  :  165$
    GFT        (2Step_GOAT,   50 000$)  :  288$
    FTMO       (2Step_Swing,  50 000$)  :  345$
    Fivers     (HighStakes,  100 000$)  :  545$
    FundedNext (StellarLite, 200 000$)  :  799$ (798.99$)

Fivers et FundedNext ecartes du perimetre "starter bon marche" : Fivers
(545$) a lui seul mange plus de la moitie du plafond 1000$, FundedNext
(799$) le mange presque en entier -- aucune combinaison a 2-3 firms ne reste
"bon marche" en les incluant, et leur propre seuil de deblocage (15000$/
25000$) est deja le plus eleve de la flotte (peu de benefice a les avancer).

Combinaisons realistes retenues sous plafond=1000$ (budget jour 0, avant
tout profit, confirme par un run de controle -- couts jour 0 verifies au
centime pres dans le CSV de sortie, colonne active0_cost) :
    (i)   Blueberry + GFT             = 165+288 = 453$  (marge 547$)
    (ii)  Blueberry + FTMO            = 165+345 = 510$  (marge 490$)
    (iii) Blueberry + FTMO + GFT      = 165+345+288 = 798$ (marge 202$, tres tendu)
Sous plafond=3000$, les memes 3 combinaisons laissent 2202$ a 2547$ de marge
(bien moins contraignant -- l'arbitrage marge-vs-diversification devrait
etre beaucoup plus favorable a ce plafond).
    Reference (baseline, inchangee) : Blueberry seul = 165$ (marge 835$/2835$).

===========================================================================
2. REGLE DE DEBLOCAGE COMBINE -- "premier finance suffit"
===========================================================================
Choix documente : le mecanisme de seuil existant (seq_grouped_multi) exige
deja group_funded_count>=1 ET reserve>=seuil_firm pour chaque etape de
deblocage -- avec un seul starter, cette condition de comptage etait
TRIVIALEMENT vraie des que Blueberry finance une fois (aucun autre choix
possible). Avec plusieurs starters, cette meme condition (n_req=1, inchangee
dans le code) devient un vrai OU logique : N'IMPORTE LEQUEL des starters
finance suffit a satisfaire le comptage -- exactement "premier finance
suffit", sans modification du seuil de reserve lui-meme (qui reste le vrai
goulot). Choisi plutot que "tous finances" car ce dernier annulerait le
benefice de diversification vise (attendre le plus lent des N comptes
revient a ne pas avoir de redondance du tout).

===========================================================================
3. IMPLEMENTATION -- delta vs etape_e_final_lock_bbreset_2026-08-09.py
===========================================================================
- STARTERS (tuple de firms) remplace ei.STARTER (un seul nom) partout ou il
  intervenait : ouverture jour 0, downgrade-on-reopen (no-op deja confirme,
  generalise par coherence), capital d'urgence.
- Ouverture jour 0 PARTIELLE par firm starter : seul le slot d'index 0 de
  chaque firm de STARTERS ouvre au jour 0 (le "starter" au sens strict) --
  les comptes additionnels eventuels de cette meme firm (N_ACCOUNTS_DAY0
  FTMO=2) restent inactifs et s'ouvrent plus tard via le declencheur de
  deblocage normal de cette firm (deja present dans seq_grouped_multi, aucun
  changement necessaire la -- juste correction de open_group()/cost0 pour ne
  plus re-facturer un compte deja actif, bug qui n'existait pas avant car un
  seul compte etait jamais actif avant son propre declencheur).
- Capital d'urgence (emergency_capital) : reouvre desormais le moins cher
  des starters INACTIFS (pas seulement Blueberry), triee par cout croissant
  -- seul le slot starter (index 0) de chaque firm de STARTERS est eligible,
  jamais un compte additionnel pas encore active par son propre declencheur.

N'importe pas ce script directement (convention du projet -- copie
autonome, cf. tous les etape_e_*.py).
"""
import random
import sys
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
from point_liquidity_rules import CORR_TH, DAY_SECONDS
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from split_tax_model import compute_is, handle_tax_payment, IS_THRESHOLD_ACOMPTE, Q_OFFSETS_DAYS, \
    SOLDE_OFFSET_DAYS, ACOMPTE_FRACTION
from corrected_scaling_mechanism import BASE_PALIER

from engine_multiformat import FORMATS, make_acc_mf, process_trade_mf
import etape_e_fleet_integration as ei

YEAR_SECONDS = 365.25 * DAY_SECONDS
MONTH_SECONDS = DAYS_PER_MONTH * DAY_SECONDS
SIX_MONTHS_SECONDS = 6 * MONTH_SECONDS
FIRMS = ("Blueberry", "FTMO", "Fivers", "GFT", "FundedNext")

STARTER_COMBOS = {
    "solo_BB": ("Blueberry",),
    "BB_GFT": ("Blueberry", "GFT"),
    "BB_FTMO": ("Blueberry", "FTMO"),
    "BB_FTMO_GFT": ("Blueberry", "FTMO", "GFT"),
}


def run_one(trades, slot_arrivals, market_data, excluded_map, order, ceiling, seq_grouped, format_by_firm,
            emergency_capital, eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult,
            starters=("Blueberry",)):
    """Blueberry reset toujours actif. STARTERS = tuple de firms ouvertes en parallele au jour 0."""
    fmt_by_firm = {g: FORMATS[k] for g, k in format_by_firm.items()}

    def base_palier_cost(gname):
        if gname == "FundedNext":
            fmt_key = format_by_firm["FundedNext"]
            return ei.FUNDEDNEXT_PALIER, ei.price_for(fmt_key, ei.FUNDEDNEXT_PALIER)
        if gname == "Fivers":
            fmt_key = format_by_firm["Fivers"]
            palier = ei.FIVERS_PALIER[fmt_key]
            return palier, ei.price_for(fmt_key, palier)
        palier = BASE_PALIER[gname]
        return palier, ei.price_for(format_by_firm[gname], palier)

    accounts_by_group = {}
    active0_cost = 0.0
    for gname in FIRMS:
        is_starter = gname in starters
        palier, cost = base_palier_cost(gname)
        fmt = fmt_by_firm[gname]
        n_accs = ei.N_ACCOUNTS_DAY0[gname]
        accs = []
        for i in range(n_accs):
            active_i = is_starter and i == 0
            acc = make_acc_mf(fmt, palier, cost=cost, active=active_i)
            acc["_gname"] = gname
            acc["base_palier"] = palier
            acc["base_cost"] = cost
            acc["_reset_used"] = False
            acc["last_open_time"] = 0.0 if active_i else None
            accs.append(acc)
        accounts_by_group[gname] = accs
        if is_starter:
            active0_cost += accs[0]["cost"]

    fleet_unlocked = False
    _init_own_funded = {g for g in starters if not fmt_by_firm[g]["phases"]}
    state = {"reserve": 0.0, "ever_funded": False, "real_cash_paid": active0_cost, "total_breaks": 0,
             "group_funded_count": len(_init_own_funded), "group_own_funded": set(_init_own_funded),
             "hit_ceiling": False, "emergency_remaining": emergency_capital, "is_paid_cum": 0.0,
             "extra_accounts_opened": {g: 0 for g in ei.GROWTH_FIRMS_EXTRA},
             "tax_breach_count": 0, "tax_breach_total": 0.0, "tax_breach_max": 0.0,
             "tax_breach_concurrent_with_repurchase": 0, "tax_breach_events": [], "_now": 0.0,
             "total_opens": sum(1 for accs in accounts_by_group.values() for a in accs if a["last_open_time"] == 0.0),
             "breaks_within_30d": 0, "breaks_within_60d": 0, "blueberry_resets_used": 0}
    pending_group_trigger = [(names, trig, thresh, final) for names, trig, thresh, final in seq_grouped if trig != "day0"]
    pending_reopen = []
    pending_group_open = []

    def mark_group_funded_if_needed(gname):
        if gname not in state["group_own_funded"]:
            state["group_own_funded"].add(gname)
            state["group_funded_count"] += 1

    def combined_net():
        return sum(a["total_funded_pnl"] - a["total_fees_paid"] for accs in accounts_by_group.values() for a in accs)

    def n_active_accounts():
        return sum(1 for accs in accounts_by_group.values() for a in accs if a["active"])

    def downgrade_active():
        return not fleet_unlocked

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

    def reopen_account(acc, cost, fmt, skip_to_funded=False):
        acc["active"] = True
        acc["total_fees_paid"] += cost
        acc["phase"] = "funded" if (skip_to_funded or not fmt["phases"]) else "challenge"
        acc["phase_index"] = 0
        acc["cumulative_since_reset"] = 0.0
        acc["peak_since_reset"] = 0.0
        acc["trading_days_since_reset"] = set()
        acc["daily_pnl"] = {}
        acc["locked_peak"] = None
        acc["eod_peak"] = 0.0
        acc["last_day_seen"] = None
        acc["last_open_time"] = state["_now"]
        state["total_opens"] += 1
        if downgrade_active() and acc.get("_gname") in starters:
            acc["palier"] = acc["base_palier"]
            acc["cost"] = acc["base_cost"]

    def open_group(gname, is_final):
        for a in accounts_by_group[gname]:
            if a["active"]:
                continue
            a["active"] = True
            a["total_fees_paid"] = a["cost"]
            a["last_open_time"] = state["_now"]
            state["total_opens"] += 1
        if not fmt_by_firm[gname]["phases"]:
            mark_group_funded_if_needed(gname)

    def try_emergency_bootstrap():
        if n_active_accounts() != 0 or emergency_capital <= 0 or state["emergency_remaining"] <= 0:
            return
        candidates = [accounts_by_group[g][0] for g in starters if not accounts_by_group[g][0]["active"]]
        candidates.sort(key=lambda a: a["base_cost"] if downgrade_active() else a["cost"])
        for acc in candidates:
            cost = acc["base_cost"] if downgrade_active() else acc["cost"]
            if state["emergency_remaining"] < cost:
                break
            state["emergency_remaining"] -= cost
            reopen_account(acc, cost, fmt_by_firm[acc["_gname"]])
            pending_reopen[:] = [p for p in pending_reopen if p["key"] != id(acc)]

    def process_extra_account(now):
        if not fleet_unlocked:
            return
        for gname in ei.GROWTH_FIRMS_EXTRA:
            accs = accounts_by_group[gname]
            max_acc = ei.FIRM_MAX_ACCOUNTS.get(gname)
            if max_acc is not None and len(accs) >= max_acc:
                continue
            unit_palier = BASE_PALIER[gname] * ei.EXTRA_ACCOUNT_MULT
            current_capital = sum(a["palier"] for a in accs)
            if current_capital + unit_palier > ei.FIRM_CAPITAL_CAP[gname]:
                continue
            extra_cost = ei.price_for(format_by_firm[gname], unit_palier)
            if state["reserve"] >= extra_threshold_mult * extra_cost:
                state["reserve"] -= extra_cost
                new_acc = make_acc_mf(fmt_by_firm[gname], unit_palier, cost=extra_cost, active=True)
                new_acc["total_fees_paid"] = extra_cost
                new_acc["_gname"] = gname
                new_acc["base_palier"] = unit_palier
                new_acc["base_cost"] = extra_cost
                new_acc["_reset_used"] = False
                new_acc["last_open_time"] = now
                accs.append(new_acc)
                state["extra_accounts_opened"][gname] += 1
                state["total_opens"] += 1

    def structure_complete():
        for g in FIRMS:
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
    year1_net_split = None
    reserve_min_6mo = float("inf")
    reserve_min_after_unlock = float("inf")

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]
        state["_now"] = now

        if now <= SIX_MONTHS_SECONDS:
            reserve_min_6mo = min(reserve_min_6mo, state["reserve"])
            if state["total_opens"] > 1:
                reserve_min_after_unlock = min(reserve_min_after_unlock, state["reserve"])

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
            fmt = fmt_by_firm[gname]
            base_risk = gft_eval_risk if gname == "GFT" else eval_risk
            for acc in list(accs):
                if not acc["active"]:
                    continue
                r = fleet_risk if acc["phase"] == "funded" else base_risk
                was_challenge = acc["active"] and acc["phase"] == "challenge"
                was_funded = acc["active"] and acc["phase"] == "funded"
                phase_before, idx_before = acc["phase"], acc["phase_index"]
                just_funded = process_trade_mf(acc, trade, now, fmt, state, r, market_data, excluded_map,
                                                split_flat=0.80, reserve_share=reserve_share, cost_override=0.0)

                progressed = (fmt["phases"] and (
                    (acc["phase"] == "challenge" and acc["phase_index"] == idx_before + 1) or
                    (acc["phase"] == "funded" and phase_before == "challenge")))
                reset_happened = (acc["cumulative_since_reset"] == 0.0 and acc["peak_since_reset"] == 0.0
                                  and len(acc["trading_days_since_reset"]) == 0)
                broke = reset_happened and not progressed

                if broke:
                    state["total_breaks"] += 1
                    t_since_open = now - acc["last_open_time"] if acc["last_open_time"] is not None else None
                    if t_since_open is not None:
                        if t_since_open <= 30 * 86400:
                            state["breaks_within_30d"] += 1
                        if t_since_open <= 60 * 86400:
                            state["breaks_within_60d"] += 1
                    use_bb_reset = (gname == "Blueberry" and was_funded and not acc["_reset_used"])
                    if use_bb_reset:
                        cost = 2.0 * acc["base_cost"]
                        acc["active"] = False
                        acc["_reset_used"] = True
                        state["blueberry_resets_used"] += 1
                        handle_cost_hybrid(cost, pending_reopen, id(acc),
                                            lambda a=acc, c=cost, f=fmt: reopen_account(a, c, f, skip_to_funded=True))
                    else:
                        if downgrade_active() and gname in starters:
                            cost = acc["base_cost"]
                        else:
                            cost = ei.price_for(format_by_firm[gname], acc["palier"])
                        acc["active"] = False
                        handle_cost_hybrid(cost, pending_reopen, id(acc),
                                            lambda a=acc, c=cost, f=fmt: reopen_account(a, c, f, skip_to_funded=False))
                else:
                    if was_challenge and just_funded and gname not in state["group_own_funded"]:
                        state["group_own_funded"].add(gname)
                        state["group_funded_count"] += 1

        process_extra_account(now)
        process_pending(pending_reopen)
        process_pending(pending_group_open)
        try_emergency_bootstrap()

        still_pending = []
        for group_names, trig, thresh, is_final in pending_group_trigger:
            _, n_req = trig
            if state["group_funded_count"] >= n_req and state["reserve"] >= thresh:
                for gname in group_names:
                    cost0 = sum(a["cost"] for a in accounts_by_group[gname] if not a["active"])
                    handle_cost_hybrid(cost0, pending_group_open, gname, lambda g=gname, f=is_final: open_group(g, f))
                if is_final:
                    fleet_unlocked = True
            else:
                still_pending.append((group_names, trig, thresh, is_final))
        pending_group_trigger = still_pending

        if full_structure_month is None and structure_complete():
            full_structure_month = now / MONTH_SECONDS

    if year1_net_split is None:
        year1_net_split = combined_net()

    pre = full_structure_month is None or full_structure_month > 12
    return {"final_net_split": combined_net(), "is_paid_cum": state["is_paid_cum"],
            "year1_net_split": year1_net_split, "total_breaks": state["total_breaks"], "pre_deblocage": pre,
            "total_opens": state["total_opens"], "breaks_within_30d": state["breaks_within_30d"],
            "breaks_within_60d": state["breaks_within_60d"], "blueberry_resets_used": state["blueberry_resets_used"],
            "reserve_min_6mo": reserve_min_6mo if reserve_min_6mo != float("inf") else 0.0,
            "reserve_min_after_unlock": (reserve_min_after_unlock if reserve_min_after_unlock != float("inf") else None),
            "final_reserve": state["reserve"],
            "full_structure_month": full_structure_month if full_structure_month is not None else float("nan"),
            "active0_cost": active0_cost}


def run_propagated(pop, market_data, excluded_map, ceiling, seq_grouped, format_by_firm, emergency,
                    eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult, n_sims, seed,
                    starters=("Blueberry",)):
    rng_wr = random.Random(seed)
    rng_boot = random.Random(seed + 1)
    rows = []
    for _ in range(n_sims):
        wr_draw = rng_wr.betavariate(ei.ALPHA_POST, ei.BETA_POST)
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_draw, 1.0, False, random.Random(rng_boot.random()))
        block_seconds = 2 * 30 * DAY_SECONDS
        blocks = build_blocks(trades, slot_arrivals, block_seconds)
        target_duration = slot_arrivals[-1]
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot, target_duration)
        order = list(range(len(raw_trades)))
        res = run_one(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, seq_grouped, format_by_firm,
                      emergency, eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult,
                      starters=starters)
        rows.append(res)
    return pd.DataFrame(rows)


def summarize(df, label, ceiling):
    net = df["final_net_split"] - df["is_paid_cum"]
    year1_neg = df["year1_net_split"] < 0
    pre_mask = df["pre_deblocage"]
    n_pre = (year1_neg & pre_mask).sum()
    n_post = (year1_neg & ~pre_mask).sum()
    break_rate_30d = df["breaks_within_30d"].sum() / df["total_opens"].sum() * 100
    break_rate_60d = df["breaks_within_60d"].sum() / df["total_opens"].sum() * 100
    quasi_frozen = (df["final_reserve"] < 100).mean() * 100
    return dict(config=label, ceiling=ceiling, n=len(df), active0_cost=df["active0_cost"].iloc[0],
                profit=net.mean(), ruine=(net < 0).mean() * 100,
                annee1_neg=year1_neg.mean() * 100, annee1_neg_pre=n_pre / len(df) * 100,
                annee1_neg_post=n_post / len(df) * 100, mean_breaks=df["total_breaks"].mean(),
                mean_bb_resets=df["blueberry_resets_used"].mean(),
                break_rate_30d_pct=break_rate_30d, break_rate_60d_pct=break_rate_60d,
                reserve_min_6mo_worst=df["reserve_min_6mo"].min(),
                mean_full_structure_month=df["full_structure_month"].dropna().mean(),
                quasi_frozen_pct=quasi_frozen)


if __name__ == "__main__":
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    combos_arg = sys.argv[2].split(",") if len(sys.argv) > 2 else list(STARTER_COMBOS.keys())
    ceilings_arg = [float(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else [1000.0, 3000.0]

    t_start = time.time()
    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)
    seq = ei.seq_grouped_multi(1000, 15000, 25000, 25000)
    config = ei.CONFIG_REF
    EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK = 1.25, 1.90, 1.75

    rows = []
    for combo_name in combos_arg:
        starters = STARTER_COMBOS[combo_name]
        for ceiling in ceilings_arg:
            t0 = time.time()
            df = run_propagated(pop, market_data, excluded_map, ceiling, seq, config, ei.DEFAULT_EMERGENCY,
                                 EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                                 ei.EXTRA_THRESHOLD_MULT, n_sims=n_sims, seed=9999, starters=starters)
            row = summarize(df, combo_name, ceiling)
            rows.append(row)
            print(f"[{combo_name:14s} plafond={ceiling:.0f}$ cout_j0={row['active0_cost']:.0f}$] "
                  f"profit={row['profit']:+,.0f}$ ruine={row['ruine']:.2f}% "
                  f"annee1<0={row['annee1_neg']:.2f}% (pre={row['annee1_neg_pre']:.2f}% post={row['annee1_neg_post']:.2f}%) "
                  f"casse<=30j={row['break_rate_30d_pct']:.2f}% struct_complete={row['mean_full_structure_month']:.1f}mo "
                  f"reserve_min_6mo(pire)={row['reserve_min_6mo_worst']:,.0f}$ quasi_gele={row['quasi_frozen_pct']:.1f}% "
                  f"({time.time()-t0:.0f}s)")
            pd.DataFrame(rows).to_csv(f"etape_f_bootstrap_parallele_n{n_sims}.csv", index=False)

    print(f"\nTermine en {time.time()-t_start:.0f}s.")
