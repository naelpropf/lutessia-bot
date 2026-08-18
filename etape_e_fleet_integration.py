"""
Etape E (08/08) : integration des formats de l'Etape D dans le moteur de
PRODUCTION complet (deblocage echelonne + compte supplementaire + fiscalite),
pour comparer honnetement config actuelle (100% 2-step) vs combo gagnant sous
le MEME mecanisme de croissance -- contrairement au criblage simplifie de
l'Etape D (etape_d_fleet_format_search.py), qui n'avait ni croissance ni
fiscalite.

Ne touche a AUCUN script existant (engine_multiformat.py, extra_account_v4_
multi.py, extra_account_v4_multi_stagger.py restent intacts). Nouveau script
autonome qui importe leurs briques reutilisables (fiscalite, GROUP_DEFS des
plafonds reels) et remplace process_trade par process_trade_mf.

=====================================================================
DECISIONS DE CONCEPTION -- documentees avec niveau de confiance explicite
=====================================================================

1. MECANISME "COMPTE SUPPLEMENTAIRE" PAR FORMAT (demande explicite du
   prompt : verifier si le mecanisme se transpose tel quel aux formats
   instant funding).
   Fait verifie dans le code existant (extra_account_v4_multi.py,
   extra_account_v4_multi_stagger.py) : AUCUNE croissance individuelle de
   palier n'existe dans le moteur de reference -- aucun appel a un
   equivalent de process_growth_upgrade_seq dans le chemin execute. La
   SEULE croissance vient de l'ouverture de comptes SUPPLEMENTAIRES a
   taille FIXE (EXTRA_UNIT_PALIER = BASE_PALIER x2, cf. extra_account_v4_
   multi.py:87-90), plafonnee par FIRM_CAPITAL_CAP/FIRM_MAX_ACCOUNTS.
   CONSEQUENCE (confiance ELEVEE -- verification de code, pas une
   hypothese) : ce mecanisme transpose IDENTIQUEMENT aux formats instant
   funding retenus (Blueberry Instant Elite, GFT Instant GOAT) -- une
   "extra account" instant est exactement le meme concept qu'une extra
   account 2-step aujourd'hui (un slot de plus a prix fixe, capacite
   immediate au lieu de passer par une evaluation). AUCUNE adaptation de
   mecanisme n'est necessaire au niveau structurel.

2. DOWNGRADE-ON-REOPEN (rachat au palier de base pour le STARTER Blueberry
   avant deblocage complet).
   Verifie dans reopen_account() : ce mecanisme fait acc["palier"] =
   acc["base_palier"], qui est DEJA la valeur de creation du compte
   puisqu'aucune croissance individuelle n'existe (point 1). C'est un
   NO-OP dans le design actuel (confiance ELEVEE, meme verification de
   code) -- reste un no-op de la meme facon si le STARTER est en Instant
   Elite. Conserve tel quel, aucune adaptation necessaire.

3. PLAFONDS PAR FIRM (demande explicite : verifier qu'ils s'appliquent
   identiquement aux formats instant/1-step).
   Les reponses support obtenues le 08/08 (etape_a_formats_comptes_
   propfirms_2026-08-08.md §6bis) confirment explicitement que les
   plafonds portent sur TOUT le capital du trader ("per trader", "across
   all accounts and programs"), PAS par format -- FTMO (400k, reponse
   support explicite sans carve-out 1-Step), The5%ers (500k, reponse
   support explicite "across all accounts and programs"), GFT (400k,
   page officielle "tous modeles confondus"). Memes valeurs FIRM_CAPITAL_
   CAP/FIRM_MAX_ACCOUNTS que le moteur actuel, confiance ELEVEE qu'elles
   s'appliquent identiquement aux formats retenus. Exception : Blueberry
   reste sur l'ambiguite deja connue et non affectee par cette session
   (450k code vs 2M$ officiel "per trader", jamais tranchee) -- valeur
   conservatrice 450k conservee par prudence, confiance MOYENNE (inchangee
   par ce travail).

4. PRIX REELS PAR FORMAT (amelioration vs le moteur actuel qui approxime
   via FEE_RATIO generique ou un proxy FTMO pour FundedNext).
   Utilise le prix reel de engine_multiformat.FORMATS[...]["price"] pour
   le palier de base et le palier extra-compte quand disponible ; fallback
   FEE_RATIO si le palier precis n'est pas dans la grille de prix connue
   (meme convention de repli que le moteur actuel).

5. THE5%ERS HYPER GROWTH -- pas de mecanisme de croissance calendaire
   connu (contrairement a High Stakes SUMMER_COST/POST_SUMMER_COST_REAL).
   Prix fixe a son tarif connu au palier 40 000$ (850$, le plus gros
   palier confirme teste dans la recherche Etape A), 4 comptes fixes comme
   aujourd'hui (pas de mecanisme "extra compte" pour Fivers, identique au
   design actuel). CONFIANCE FAIBLE-MOYENNE explicite : le vrai mecanisme
   Hyper Growth (doublement reel du compte a chaque palier de profit
   atteint) n'est PAS modelise finement ici -- simplifie en compte a
   taille fixe pour rester coherent et comparable au reste du moteur.
   Signale comme point ouvert, pas une decouverte tranchee.

=====================================================================
POINT 1 (risque) : traite dans etape_e_risk_sweep.py, pas dans ce fichier.
=====================================================================
"""
import random
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
from corrected_scaling_mechanism import FEE_RATIO, BASE_PALIER

from engine_multiformat import FORMATS, make_acc_mf, process_trade_mf

ALPHA_POST, BETA_POST = 260, 388
YEAR_SECONDS = 365.25 * DAY_SECONDS
MONTH_SECONDS = DAYS_PER_MONTH * DAY_SECONDS

STARTER = "Blueberry"
GROWTH_FIRMS_EXTRA = ("Blueberry", "FTMO", "GFT")
EXTRA_ACCOUNT_MULT = 2.0
EXTRA_THRESHOLD_MULT = 3.0
DEFAULT_RESERVE = 30000.0
DEFAULT_EMERGENCY = 300.0
FINAL_RESERVE_SHARE = 0.95

# Blueberry : 400000.0$ agrege (pas de limite de nombre de comptes) confirme par
# contact direct support Blueberry (chat live, 2026-08-10) -- remplace l'ancien
# 450000.0$/3-comptes (jamais confirme par support de la meme facon, cf.
# project_blueberry_account_limit_conflict_2026-08-10.md). FTMO/GFT/Fivers
# INCHANGES -- leurs caps n'ont pas ete verifies par un contact support
# equivalent, ne pas generaliser cette correction sans verification propre.
FIRM_CAPITAL_CAP = {"Blueberry": 400000.0, "FTMO": 400000.0, "GFT": 400000.0, "Fivers": 500000.0}
FIRM_MAX_ACCOUNTS = {"Blueberry": None, "FTMO": None, "GFT": None, "Fivers": 5}
N_ACCOUNTS_DAY0 = {"FTMO": 2, "Fivers": 4, "Blueberry": 1, "GFT": 1, "FundedNext": 1}

# --- Config (i) : reference actuelle, 100% 2-step ---
CONFIG_REF = dict(FTMO="FTMO_2Step_Swing", Fivers="Fivers_HighStakes",
                   Blueberry="Blueberry_Prime2Step", GFT="GFT_2Step_GOAT",
                   FundedNext="FundedNext_StellarLite")

# --- Config (ii) : combo gagnant Etape D ---
CONFIG_WINNER = dict(FTMO="FTMO_1Step", Fivers="Fivers_HyperGrowth",
                      Blueberry="Blueberry_InstantElite", GFT="GFT_InstantGOAT",
                      FundedNext="FundedNext_Stellar1Step")

FUNDEDNEXT_PALIER = 200000.0
FIVERS_PALIER = {"Fivers_HighStakes": 100000.0, "Fivers_HyperGrowth": 40000.0}


def price_for(fmt_key, palier):
    fmt = FORMATS[fmt_key]
    known = fmt["price"].get(palier)
    if known is not None:
        return known
    return round(palier * FEE_RATIO)


def seq_grouped_multi(t_ftmo, t_fivers, t_gft, t_fundednext):
    return [
        ((STARTER,), "day0", None, False),
        (("FTMO",), ("after_count", 1), t_ftmo, False),
        (("Fivers",), ("after_count", 1), t_fivers, False),
        (("GFT",), ("after_count", 1), t_gft, False),
        (("FundedNext",), ("after_count", 1), t_fundednext, True),
    ]


def run_one(trades, slot_arrivals, market_data, excluded_map, order, ceiling, seq_grouped, format_by_firm,
            emergency_capital, eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult):
    fmt_by_firm = {g: FORMATS[k] for g, k in format_by_firm.items()}

    def base_palier_cost(gname):
        if gname == "FundedNext":
            fmt_key = format_by_firm["FundedNext"]
            return FUNDEDNEXT_PALIER, price_for(fmt_key, FUNDEDNEXT_PALIER)
        if gname == "Fivers":
            fmt_key = format_by_firm["Fivers"]
            palier = FIVERS_PALIER[fmt_key]
            return palier, price_for(fmt_key, palier)
        palier = BASE_PALIER[gname]
        return palier, price_for(format_by_firm[gname], palier)

    accounts_by_group = {}
    active0_cost = 0.0
    for gname in ("Blueberry", "FTMO", "Fivers", "GFT", "FundedNext"):
        is_day0 = (gname == STARTER)
        palier, cost = base_palier_cost(gname)
        fmt = fmt_by_firm[gname]
        accs = [make_acc_mf(fmt, palier, cost=cost, active=is_day0) for _ in range(N_ACCOUNTS_DAY0[gname])]
        for a in accs:
            a["_gname"] = gname
            a["base_palier"] = palier
            a["base_cost"] = cost
        accounts_by_group[gname] = accs
        if is_day0:
            active0_cost += sum(a["cost"] for a in accs)

    fleet_unlocked = False
    # Formats instant funding (0 phase) actives des le jour 0 sont deja
    # "funded" a la creation -- credites immediatement (cf.
    # mark_group_funded_if_needed) plutot que via la detection de
    # transition challenge->funded, qui ne se declenche jamais pour eux.
    _init_own_funded = {g for g in ("Blueberry",) if not fmt_by_firm[g]["phases"]}
    state = {"reserve": 0.0, "ever_funded": False, "real_cash_paid": active0_cost, "total_breaks": 0,
             "group_funded_count": len(_init_own_funded), "group_own_funded": set(_init_own_funded),
             "hit_ceiling": False, "emergency_remaining": emergency_capital, "is_paid_cum": 0.0,
             "extra_accounts_opened": {g: 0 for g in GROWTH_FIRMS_EXTRA},
             "tax_breach_count": 0, "tax_breach_total": 0.0, "tax_breach_max": 0.0,
             "tax_breach_concurrent_with_repurchase": 0, "tax_breach_events": []}
    pending_group_trigger = [(names, trig, thresh, final) for names, trig, thresh, final in seq_grouped if trig != "day0"]
    pending_reopen = []
    pending_group_open = []

    def mark_group_funded_if_needed(gname):
        # Necessaire pour les formats instant funding (0 phase, deja
        # "funded" a la creation) -- ils ne passent jamais par une
        # transition challenge->funded detectable dans la boucle de trade,
        # donc doivent etre credites au group_funded_count des leur
        # activation (day0 ou deblocage), pas via le mecanisme de detection
        # de transition utilise pour les formats avec evaluation.
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

    def reopen_account(acc, cost, fmt):
        acc["active"] = True
        acc["total_fees_paid"] += cost
        acc["phase"] = "funded" if not fmt["phases"] else "challenge"
        acc["phase_index"] = 0
        acc["cumulative_since_reset"] = 0.0
        acc["peak_since_reset"] = 0.0
        acc["trading_days_since_reset"] = set()
        acc["daily_pnl"] = {}
        acc["locked_peak"] = None
        acc["eod_peak"] = 0.0
        acc["last_day_seen"] = None
        if downgrade_active() and acc.get("_gname") == STARTER:
            acc["palier"] = acc["base_palier"]
            acc["cost"] = acc["base_cost"]

    def open_group(gname, is_final):
        for a in accounts_by_group[gname]:
            a["active"] = True
            a["total_fees_paid"] = a["cost"]
        if not fmt_by_firm[gname]["phases"]:
            mark_group_funded_if_needed(gname)

    def try_emergency_bootstrap():
        if n_active_accounts() != 0 or emergency_capital <= 0 or state["emergency_remaining"] <= 0:
            return
        bb_acc = accounts_by_group[STARTER][0]
        cost = bb_acc["base_cost"] if downgrade_active() else bb_acc["cost"]
        if state["emergency_remaining"] >= cost:
            state["emergency_remaining"] -= cost
            reopen_account(bb_acc, cost, fmt_by_firm[STARTER])
            pending_reopen[:] = [p for p in pending_reopen if p["key"] != id(bb_acc)]

    def process_extra_account(now):
        if not fleet_unlocked:
            return
        for gname in GROWTH_FIRMS_EXTRA:
            accs = accounts_by_group[gname]
            max_acc = FIRM_MAX_ACCOUNTS.get(gname)
            if max_acc is not None and len(accs) >= max_acc:
                continue
            unit_palier = BASE_PALIER[gname] * EXTRA_ACCOUNT_MULT
            current_capital = sum(a["palier"] for a in accs)
            if current_capital + unit_palier > FIRM_CAPITAL_CAP[gname]:
                continue
            extra_cost = price_for(format_by_firm[gname], unit_palier)
            if state["reserve"] >= extra_threshold_mult * extra_cost:
                state["reserve"] -= extra_cost
                new_acc = make_acc_mf(fmt_by_firm[gname], unit_palier, cost=extra_cost, active=True)
                new_acc["total_fees_paid"] = extra_cost
                new_acc["_gname"] = gname
                new_acc["base_palier"] = unit_palier
                new_acc["base_cost"] = extra_cost
                accs.append(new_acc)
                state["extra_accounts_opened"][gname] += 1

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
            fmt = fmt_by_firm[gname]
            risk = gft_eval_risk if gname == "GFT" else eval_risk
            for acc in list(accs):
                if not acc["active"]:
                    continue
                r = fleet_risk if acc["phase"] == "funded" else risk
                was_challenge = acc["active"] and acc["phase"] == "challenge"
                phase_before, idx_before = acc["phase"], acc["phase_index"]
                # cost_override=0.0 neutralise le cout/reserve gere en interne par
                # process_trade_mf (qui ne respecte pas le plafond "ceiling" ni la
                # file d'attente pending_reopen) -- le cout REEL et la logique de
                # reouverture differee sont geres ici, comme dans le moteur de
                # production original.
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
                    if downgrade_active() and gname == STARTER:
                        cost = acc["base_cost"]
                    else:
                        cost = price_for(format_by_firm[gname], acc["palier"])
                    acc["active"] = False
                    handle_cost_hybrid(cost, pending_reopen, id(acc), lambda a=acc, c=cost, f=fmt: reopen_account(a, c, f))
                elif was_challenge and just_funded and gname not in state["group_own_funded"]:
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
                    cost0 = sum(a["cost"] for a in accounts_by_group[gname])
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

    return {"final_net_split": combined_net(), "is_paid_cum": state["is_paid_cum"],
            "year1_net_split": year1_net_split, "total_breaks": state["total_breaks"]}


def run_propagated(pop, market_data, excluded_map, ceiling, seq_grouped, format_by_firm, emergency,
                    eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult, n_sims, seed):
    rng_wr = random.Random(seed)
    rng_boot = random.Random(seed + 1)
    rows = []
    for _ in range(n_sims):
        wr_draw = rng_wr.betavariate(ALPHA_POST, BETA_POST)
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_draw, 1.0, False, random.Random(rng_boot.random()))
        block_seconds = 2 * 30 * DAY_SECONDS
        blocks = build_blocks(trades, slot_arrivals, block_seconds)
        target_duration = slot_arrivals[-1]
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot, target_duration)
        order = list(range(len(raw_trades)))
        res = run_one(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, seq_grouped, format_by_firm,
                      emergency, eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult)
        rows.append(res)
    return pd.DataFrame(rows)
