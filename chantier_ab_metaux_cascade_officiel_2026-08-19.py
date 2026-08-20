"""chantier_ab_metaux_cascade_officiel_2026-08-19.py

Objectif (demande utilisateur, session du 19/08 soir) : rejouer Config 2
(metaux -> B par defaut, overflow vers A si bloque-CORRELATION dans B,
PAS si plafond position) dans le moteur CASCADE OFFICIEL (5 firms,
paliers/DD/split/payout complets, 4 plafonds de capital reels) -- pas le
moteur reduit 2-comptes utilise jusqu'ici (chantier_gold_silver_ab_engine_
2026-08-19.py, hit_ceiling=100% partout, non-discriminant).

Genealogie / bases reutilisees SANS reinvention (verifie par lecture,
citations dans les commentaires ci-dessous) :
- Architecture double-flotte (2 traders paralleles, plafond personnel
  COMBINE partage, reserve SEPAREE par trader -- architecture "separee"
  gagnante en n=300, S2.50 registre_parametres_projet.md) :
  dual_trader_2026-08-11.py:run_dual (structure reprise et etendue).
- Mecanique par-compte officielle A JOUR (S1.8, absente de dual_trader
  08/11) portee depuis chantier_S1_8_regen_population_2026-08-19.py :
    1. Bascule dynamique Blueberry Instant/Classic (bb_choose_fmt_key,
       lignes 185-186/204-208/357-359/578-587).
    2. Cap risque Instant 1,5%/trade reel (lignes 494-498,
       BB_INSTANT_RISK_CAP -- decouverte 08/17, "Instant risk cap
       CORRECTED").
    3. any-RR = process_trade_corr_swap_rr (swap-eviction par
       correlation, lignes 136-171) -- IMPORTE TEL QUEL depuis le module
       S1.8, pas redefini, pour eviter toute derive.
- Population A : IDENTIQUE a l'officielle (load_common() du module S1.8,
  min_rr=1,35, trailing 0,15x, deja post forex-only-fix car
  build_population_with_trailing appelle le code partage corrige).
- Population B : chantier_gold_silver_pop_B_config0_2026-08-19.csv (deja
  construite = forex/indices rr_tp1<1,35 trailing 0,10x + TOUS les
  metaux -- chantier_gold_silver_configs_2026-08-19.py:46-47 /
  chantier_b6_montecarlo_2026-08-19.py:728-752 build_pop_B_variant).
- Bootstrap winrate : meme convention que chantier_b6_montecarlo_2026-08-
  19.py:625 -- ALPHA_POST/BETA_POST partage entre A et B (aucune
  derivation B-specifique trouvee dans le projet ; signale separement
  -- task spawnee cette session, PAS bloquant ici, suit la convention
  deja en usage plutot que d'en inventer une nouvelle a la volee).
- Bootstrap temporel : bloc-bootstrap CONJOINT, MEME tirage de blocs pour
  A et B (chantier_gold_silver_ab_engine_2026-08-19.py:90-101
  build_joint_bootstrap_sequence) -- INDISPENSABLE pour mesurer le point
  de vigilance de la session precedente (correlation P&L(A)<->P&L(B)) :
  des tirages independants laveraient artificiellement cette correlation.

Routage metaux Config 2, generalise du moteur reduit (1 compte A, 1 compte
B) au moteur flotte (N comptes par firm, ouverts au fil de la croissance
et des comptes extra) : route_metal_config2 (chantier_gold_silver_ab_
engine_2026-08-19.py:104-115) decidait sur UN SEUL compte B vs UN SEUL
compte A. Ici, chaque compte B actif d'une firm g est apparie PAR INDEX
D'OUVERTURE au compte A de LA MEME firm g (pas de melange inter-firms,
coherence palier/format/DD) -- si ce compte B rejette le trade metal PAR
CORRELATION (pas plafond) ET qu'un compte A de meme firm/index existe et
est actif, ce dernier tente le meme trade en overflow. CHOIX DE
MODELISATION EXPLICITE (aucune specification officielle au niveau
multi-comptes n'existait avant ce chantier) -- extension la plus fidele
et la plus simple de la regle 2-comptes d'origine, a lire comme telle,
pas comme une decouverte.

MAX_POSITIONS reste le defaut projet (eng.MAX_POSITIONS, scaling_
simulation.py:47) sauf override explicite -- monkeypatchable via
`eng.MAX_POSITIONS = N` avant l'appel (verifie : engine_multiformat.py:
324 lit eng.MAX_POSITIONS a CHAQUE appel, pas de valeur figee a l'import,
donc l'override est bien pris en compte).
"""
import importlib.util
import random
import sys
import time

import numpy as np
import pandas as pd

import robustness_5ers_risk_challenge as eng
from point_liquidity_rules import DAY_SECONDS
from monte_carlo_simulation import precompute_correlation_pairs
from real_cash_risk_year1_block_bootstrap import DAYS_PER_MONTH
from split_tax_model import compute_is, handle_tax_payment, IS_THRESHOLD_ACOMPTE, Q_OFFSETS_DAYS, \
    SOLDE_OFFSET_DAYS, ACOMPTE_FRACTION
from corrected_scaling_mechanism import BASE_PALIER
from engine_multiformat import FORMATS, make_acc_mf, _current_phase
import etape_e_fleet_integration as ei

_spec_s18 = importlib.util.spec_from_file_location("s18", "chantier_S1_8_regen_population_2026-08-19.py")
s18 = importlib.util.module_from_spec(_spec_s18)
_spec_s18.loader.exec_module(s18)
process_trade_corr_swap_rr = s18.process_trade_corr_swap_rr
build_flexible_population_with_rr = s18.build_flexible_population_with_rr
load_common_A = s18.load_common

YEAR_SECONDS = 365.25 * DAY_SECONDS
MONTH_SECONDS = DAYS_PER_MONTH * DAY_SECONDS
SIX_MONTHS_SECONDS = 6 * MONTH_SECONDS
FIRMS = ("Blueberry", "FTMO", "Fivers", "GFT", "FundedNext")
TRADERS = ("A", "B")

HYSTERESIS = 0.10
FTMO_DISCOUNT_FACTOR = 0.90
GOAT_GUARD_SPLIT_DAYS = 30
GOAT_GUARD_SPLIT_FLAT = 0.50
PAYOUT_CYCLE_FIRMS = ("Blueberry", "GFT", "Fivers")
PAYOUT_CYCLE_DAYS_FIRST = {"Blueberry": 14, "GFT": 3, "Fivers": 14}
PAYOUT_CYCLE_DAYS_SUBSEQUENT = {"Blueberry": 14, "GFT": 1.5, "Fivers": 14}

BB_CLASSIC_KEY = "Blueberry_Prime2Step"
BB_INSTANT_KEY = "Blueberry_InstantElite"
MIN_RR_NEW, CORR_TH_NEW = 1.35, 0.80
EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK = 1.25, 1.90, 1.75

BB_INSTANT_RISK_CAP = 1.5
BB_INSTANT_FORMAT_KEYS = {"Blueberry_InstantElite", "Blueberry_InstantLite"}

BB_PAYOUT_ADDON_MULT = 1.20
BB_PAYOUT_7J_CEILINGS = {3000.0}

BB_THRESHOLD_BY_CEILING = {960.0: 5000.0, 1000.0: 5000.0, 3000.0: 0.0, 5000.0: 0.0}

# <<< CORRECTIF (registre_parametres_projet.md S9.6, bug confirme 08/19) :
# ei.ALPHA_POST/BETA_POST=260/388 est calibre sur la population A (winrate
# ~40,1%) -- le reutiliser tel quel pour B force CHAQUE tirage MC vers
# ~40% au lieu du vrai winrate de B, quel qu'il soit. La derivation deja
# posee pour B (ALPHA_POST_B=276/297) porte sur build_pop_B_variant() SANS
# metaux (n=571, 48,16%) -- PAS la population B Config 2 utilisee ici
# (chantier_gold_silver_pop_B_config0_2026-08-19.csv, n=1505, AVEC
# metaux+routage, winrate 50,56%) -- le registre signale explicitement que
# 276/297 devient perime des que metaux+routage sont adoptes et qu'un
# retour est necessaire a ce moment (S9.6, "Point de reouverture"). Ce
# chantier EST ce moment -- derivation propre ci-dessous, meme methode
# (prior Beta(1,1) + wins/losses observes) : n=1505, wins=761, losses=744
# -> Beta(762, 745), moyenne 50,56% (verifie par calcul direct sur le CSV).
ALPHA_POST, BETA_POST = ei.ALPHA_POST, ei.BETA_POST  # Strategie A -- inchange (perimetre A hors scope ici)
ALPHA_POST_B_METAUX, BETA_POST_B_METAUX = 762, 745    # Strategie B Config2 (metaux+routage) -- derive ici


def price_for_bb(fmt_key, palier, ceiling):
    price = ei.price_for(fmt_key, palier)
    bb_7j_active = (fmt_key == BB_CLASSIC_KEY and ceiling in BB_PAYOUT_7J_CEILINGS)
    return price * BB_PAYOUT_ADDON_MULT if bb_7j_active else price


def bb_payout_days(fmt_key, ceiling, first_payout_done):
    if fmt_key == BB_CLASSIC_KEY and ceiling in BB_PAYOUT_7J_CEILINGS:
        return 7
    table = PAYOUT_CYCLE_DAYS_SUBSEQUENT if first_payout_done else PAYOUT_CYCLE_DAYS_FIRST
    return table["Blueberry"]


def payout_cycle_days(gname, first_payout_done):
    table = PAYOUT_CYCLE_DAYS_SUBSEQUENT if first_payout_done else PAYOUT_CYCLE_DAYS_FIRST
    return table[gname]


def run_dual_ab(trades_A, slots_A, trades_B, slots_B, market_data, excluded_map,
                 ceiling_combined, seq_grouped, format_by_firm, emergency_capital,
                 metal_set, sequential_b_threshold=None):
    """Moteur cascade double-flotte A/B avec routage metaux Config 2.
    Reserve TOUJOURS separee par trader (architecture gagnante, cf.
    docstring module). Ceiling personnel TOUJOURS combine (meme argent
    reel, une seule poche de secours -- convention dual_trader 08/12).

    sequential_b_threshold : None (defaut) -> lancement simultane jour0
    (comportement original inchange). Sinon -> A demarre COMPLETEMENT
    dormant (aucun compte actif, cout jour0 NON paye) et s'active des que
    st["B"]["reserve"] franchit ce seuil -- <<< CHANTIER LANCEMENT
    SEQUENTIEL (2026-08-20). Adaptation du mecanisme de declenchement par
    seuil de reserve DEJA utilise pour debloquer les groupes de firms
    (pending_group_trigger, ligne ~570 plus bas, identique a chantier_
    S1_8_regen_population_2026-08-19.py:609-617 "if state['group_funded_
    count']>=n_req and state['reserve']>=thresh") -- PAS try_gft_delayed_
    trigger (chantier_pisteB_delayed_start_2026-08-17.py:413-417), qui
    est un declencheur TEMPOREL (now<gft_delay_fire_time), pas un seuil
    de tresorerie, donc non reutilisable tel quel ici. open_group() n'est
    PAS reutilise pour l'activation de Blueberry car il verifie fmt_by_
    firm[gname]["phases"] (format STATIQUE Blueberry_Prime2Step,
    etape_e_fleet_integration.py:124, TOUJOURS avec phases) au lieu du
    format DYNAMIQUE reellement choisi par bb_choose_fmt_key() -- aurait
    imite un lancement Blueberry Classic force, jamais Instant, meme aux
    plafonds 3000$/5000$ ou bb_threshold=0."""
    fmt_by_firm = {g: FORMATS[k] for g, k in format_by_firm.items()}

    st = {tid: {"reserve": 0.0} for tid in TRADERS}
    accounts = {tid: {} for tid in TRADERS}
    active0_cost = {tid: 0.0 for tid in TRADERS}

    def bb_choose_fmt_key(tid):
        return BB_INSTANT_KEY if st[tid]["reserve"] >= bb_threshold_current[0] else BB_CLASSIC_KEY

    bb_threshold_current = [BB_THRESHOLD_BY_CEILING[ceiling_combined]]

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

    for tid in TRADERS:
        for gname in FIRMS:
            is_day0 = (gname == ei.STARTER) and not (tid == "A" and sequential_b_threshold is not None)
            if gname == "Blueberry":
                fmt_key = bb_choose_fmt_key(tid) if is_day0 else BB_CLASSIC_KEY
                fmt = FORMATS[fmt_key]
                palier = BASE_PALIER["Blueberry"]
                cost = price_for_bb(fmt_key, palier, ceiling_combined)
            else:
                fmt_key = format_by_firm[gname]
                palier, cost = base_palier_cost(gname)
                fmt = fmt_by_firm[gname]
            accs = [make_acc_mf(fmt, palier, cost=cost, active=is_day0) for _ in range(ei.N_ACCOUNTS_DAY0[gname])]
            if not is_day0 and tid == "A" and gname == "Blueberry" and sequential_b_threshold is not None:
                # <<< CORRECTIF (2026-08-20) : make_acc (robustness_5ers_
                # risk_challenge.py:51-55) initialise total_fees_paid=cost
                # INCONDITIONNELLEMENT (meme si active=False, un simple
                # PLACEHOLDER jamais reellement paye -- coherent avec
                # active0_cost qui l'exclut deja de real_cash_paid). Le
                # flux normal (open_group(), ligne ~319, "total_fees_paid
                # = cost" par ASSIGNATION) ecrase ce placeholder sans
                # probleme a l'ouverture reelle. MAIS try_sequential_
                # activation() reutilise reopen_account() (ligne ~293,
                # "total_fees_paid += cost" par ACCUMULATION, concu pour
                # une VRAIE reouverture apres casse ou total_fees_paid
                # reflete deja un cout reel anterieur) -- sans ce reset a
                # 0.0, le placeholder jamais paye serait compte EN PLUS du
                # cout reel d'activation, un double-comptage.
                for a in accs:
                    a["total_fees_paid"] = 0.0
            for a in accs:
                a["_gname"] = gname
                a["_fmt_key"] = fmt_key
                a["base_palier"] = palier
                a["base_cost"] = cost
                a["_reset_used"] = False
                a["last_open_time"] = 0.0 if is_day0 else None
                a["_dd_reduced"] = False
                a["_gg_triggered_count"] = 0
                a["_gg_split_until"] = None
                a["pending_payout"] = 0.0
                a["last_payout_time"] = 0.0 if is_day0 else None
                a["_first_payout_done"] = False
            accounts[tid][gname] = accs
            if is_day0:
                active0_cost[tid] += sum(a["cost"] for a in accs)

    combined_cash = {"real_cash_paid": active0_cost["A"] + active0_cost["B"], "hit_ceiling": False}

    for tid in TRADERS:
        _init_own_funded = {g for g in ("Blueberry",) if not FORMATS[accounts[tid][g][0]["_fmt_key"]]["phases"]}
        st[tid].update({
            "ever_funded": False, "total_breaks": 0,
            "group_funded_count": len(_init_own_funded), "group_own_funded": set(_init_own_funded),
            "emergency_remaining": emergency_capital, "is_paid_cum": 0.0,
            "extra_accounts_opened": {g: 0 for g in ei.GROWTH_FIRMS_EXTRA}, "_now": 0.0,
            "total_opens": sum(1 for accs in accounts[tid].values() for a in accs if a["last_open_time"] == 0.0),
            "forfeited_pre": {g: 0.0 for g in PAYOUT_CYCLE_FIRMS}, "forfeited_post": {g: 0.0 for g in PAYOUT_CYCLE_FIRMS},
            "forfeit_events_pre": {g: 0 for g in PAYOUT_CYCLE_FIRMS}, "forfeit_events_post": {g: 0 for g in PAYOUT_CYCLE_FIRMS},
            "bb_instant_opens": 0, "bb_classic_opens": 0,
            "instant_trades_total": 0, "instant_risk_capped_trades": 0,
            "pending_group_trigger": [(names, trig, thresh, final) for names, trig, thresh, final in seq_grouped if trig != "day0"],
            "pending_reopen": [], "pending_group_open": [],
            "fy_start_net": {0: 0.0}, "acomptes_paid_by_year": {}, "next_fy_to_close": 0, "tax_events": [],
            "fleet_unlocked": False, "full_structure_month": None, "year1_net_split": None,
            "overflow_to_A_count": 0,
            "_seq_activated": sequential_b_threshold is None or tid == "B",
        })

    def combined_net_trader(tid):
        return sum(a["total_funded_pnl"] - a["total_fees_paid"] for accs in accounts[tid].values() for a in accs)

    def combined_net_all():
        return combined_net_trader("A") + combined_net_trader("B")

    def n_active_accounts(tid):
        return sum(1 for accs in accounts[tid].values() for a in accs if a["active"])

    def downgrade_active(tid):
        return not st[tid]["fleet_unlocked"]

    def handle_cost_hybrid(tid, cost, pending_list, pending_key, on_success):
        s = st[tid]
        if s["reserve"] >= cost:
            s["reserve"] -= cost
            on_success()
            return
        shortfall = cost - s["reserve"]
        s["reserve"] = 0.0
        room = max(0.0, ceiling_combined - combined_cash["real_cash_paid"])
        if shortfall <= room:
            combined_cash["real_cash_paid"] += shortfall
            on_success()
        else:
            paid_now = room
            remaining = shortfall - paid_now
            combined_cash["real_cash_paid"] += paid_now
            combined_cash["hit_ceiling"] = True
            pending_list.append({"key": pending_key, "cost_remaining": remaining, "on_success": on_success})

    def process_pending(tid, pending_list):
        i = 0
        while i < len(pending_list):
            item = pending_list[i]
            if st[tid]["reserve"] >= item["cost_remaining"]:
                st[tid]["reserve"] -= item["cost_remaining"]
                item["on_success"]()
                pending_list.pop(i)
            else:
                i += 1

    def reopen_account(tid, acc, cost, fmt, skip_to_funded=False):
        acc["active"] = True
        acc["total_fees_paid"] += cost
        acc["cost"] = cost
        acc["phase"] = "funded" if (skip_to_funded or not fmt["phases"]) else "challenge"
        acc["phase_index"] = 0
        acc["cumulative_since_reset"] = 0.0
        acc["peak_since_reset"] = 0.0
        acc["trading_days_since_reset"] = set()
        acc["daily_pnl"] = {}
        acc["locked_peak"] = None
        acc["eod_peak"] = 0.0
        acc["last_day_seen"] = None
        acc["last_open_time"] = st[tid]["_now"]
        acc["_dd_reduced"] = False
        acc["_gg_triggered_count"] = 0
        acc["_gg_split_until"] = None
        acc["pending_payout"] = 0.0
        acc["last_payout_time"] = st[tid]["_now"]
        acc["_first_payout_done"] = False
        st[tid]["total_opens"] += 1
        if downgrade_active(tid) and acc.get("_gname") == ei.STARTER and acc.get("_fmt_key") == BB_CLASSIC_KEY:
            acc["palier"] = acc["base_palier"]

    def open_group(tid, gname, is_final):
        for a in accounts[tid][gname]:
            a["active"] = True
            a["total_fees_paid"] = a["cost"]
            a["last_open_time"] = st[tid]["_now"]
            a["_dd_reduced"] = False
            a["_gg_triggered_count"] = 0
            a["_gg_split_until"] = None
            a["pending_payout"] = 0.0
            a["last_payout_time"] = st[tid]["_now"]
            a["_first_payout_done"] = False
            st[tid]["total_opens"] += 1
        if not fmt_by_firm[gname]["phases"]:
            if gname not in st[tid]["group_own_funded"]:
                st[tid]["group_own_funded"].add(gname)
                st[tid]["group_funded_count"] += 1
        if is_final:
            st[tid]["fleet_unlocked"] = True

    def try_emergency_bootstrap(tid):
        s = st[tid]
        if n_active_accounts(tid) != 0 or emergency_capital <= 0 or s["emergency_remaining"] <= 0:
            return
        bb_acc = accounts[tid][ei.STARTER][0]
        cost = bb_acc["base_cost"] if downgrade_active(tid) else bb_acc["cost"]
        if s["emergency_remaining"] >= cost:
            s["emergency_remaining"] -= cost
            reopen_account(tid, bb_acc, cost, FORMATS[bb_acc["_fmt_key"]])
            s["pending_reopen"][:] = [p for p in s["pending_reopen"] if p["key"] != id(bb_acc)]

    def process_extra_account(tid, now):
        s = st[tid]
        if not s["fleet_unlocked"]:
            return
        for gname in ei.GROWTH_FIRMS_EXTRA:
            accs = accounts[tid][gname]
            max_acc = ei.FIRM_MAX_ACCOUNTS.get(gname)
            if max_acc is not None and len(accs) >= max_acc:
                continue
            unit_palier = BASE_PALIER[gname] * ei.EXTRA_ACCOUNT_MULT
            current_capital = sum(a["palier"] for a in accs)
            if current_capital + unit_palier > ei.FIRM_CAPITAL_CAP[gname]:
                continue
            if gname == "Blueberry":
                extra_fmt_key = bb_choose_fmt_key(tid)
                extra_fmt = FORMATS[extra_fmt_key]
                extra_cost = price_for_bb(extra_fmt_key, unit_palier, ceiling_combined)
            else:
                extra_fmt_key = format_by_firm[gname]
                extra_fmt = fmt_by_firm[gname]
                extra_cost = ei.price_for(extra_fmt_key, unit_palier)
            if s["reserve"] >= ei.EXTRA_THRESHOLD_MULT * extra_cost:
                s["reserve"] -= extra_cost
                new_acc = make_acc_mf(extra_fmt, unit_palier, cost=extra_cost, active=True)
                new_acc["total_fees_paid"] = extra_cost
                new_acc["_gname"] = gname
                new_acc["_fmt_key"] = extra_fmt_key
                new_acc["base_palier"] = unit_palier
                new_acc["base_cost"] = extra_cost
                new_acc["_reset_used"] = False
                new_acc["last_open_time"] = now
                new_acc["_dd_reduced"] = False
                new_acc["_gg_triggered_count"] = 0
                new_acc["_gg_split_until"] = None
                new_acc["pending_payout"] = 0.0
                new_acc["last_payout_time"] = now
                new_acc["_first_payout_done"] = False
                accs.append(new_acc)
                s["extra_accounts_opened"][gname] += 1
                s["total_opens"] += 1
                if gname == "Blueberry":
                    if extra_fmt_key == BB_INSTANT_KEY:
                        s["bb_instant_opens"] += 1
                    else:
                        s["bb_classic_opens"] += 1

    def structure_complete(tid):
        for g in FIRMS:
            if not accounts[tid][g][0]["active"]:
                return False
        return True

    def dd_distance_pct(acc, pdef):
        if pdef["dd_max_pct"] is None:
            return float("inf")
        if pdef["dd_max_mode"] == "static":
            current_dd = max(0.0, -acc["cumulative_since_reset"])
        elif pdef["dd_max_mode"] == "trailing_peak":
            ref = acc["locked_peak"] if acc["locked_peak"] is not None else acc["peak_since_reset"]
            current_dd = max(0.0, ref - acc["cumulative_since_reset"])
        else:
            current_dd = max(0.0, acc["eod_peak"] - acc["cumulative_since_reset"])
        return max(0.0, pdef["dd_max_pct"] - current_dd / acc["palier"] * 100)

    def effective_risk(acc, pdef, base_r, fleet_unlocked):
        dd_max = pdef["dd_max_pct"]
        if dd_max is None:
            return base_r
        if fleet_unlocked:
            return base_r
        distance = dd_distance_pct(acc, pdef)
        frac = distance / dd_max if dd_max > 0 else 1.0
        was_reduced = acc["_dd_reduced"]
        if not was_reduced and frac <= 0.20:
            acc["_dd_reduced"] = True
        elif was_reduced and frac >= 0.20 + HYSTERESIS:
            acc["_dd_reduced"] = False
        mult = 0.5 if acc["_dd_reduced"] else 1.0
        return base_r * mult

    def close_fiscal_year(tid, y):
        s = st[tid]
        profit_y = combined_net_trader(tid) - s["fy_start_net"].get(y, 0.0)
        is_y = compute_is(profit_y)
        s["fy_start_net"][y + 1] = combined_net_trader(tid)
        acomptes_y = s["acomptes_paid_by_year"].get(y, 0.0)
        solde = max(0.0, is_y - acomptes_y)
        solde_time = (y + 1) * YEAR_SECONDS + SOLDE_OFFSET_DAYS * DAY_SECONDS
        s["tax_events"].append((solde_time, solde))
        if is_y > IS_THRESHOLD_ACOMPTE:
            for q_off in Q_OFFSETS_DAYS:
                t_acompte = (y + 1) * YEAR_SECONDS + q_off * DAY_SECONDS
                amt = ACOMPTE_FRACTION * is_y
                s["tax_events"].append((t_acompte, amt))
                s["acomptes_paid_by_year"][y + 1] = s["acomptes_paid_by_year"].get(y + 1, 0.0) + amt
        s["tax_events"].sort(key=lambda e: e[0])

    def process_one_account(tid, gname, acc, fmt, trade, now):
        """Retourne (just_funded, admitted, at_cap) -- les 2 derniers
        champs pilotent l'overflow Config 2 pour les trades metaux."""
        s = st[tid]
        if not acc["active"]:
            return False, False, False
        acc["open_positions"] = [(t, c) for (t, c) in acc["open_positions"] if c > now]
        at_cap = len(acc["open_positions"]) >= eng.MAX_POSITIONS
        n_before = len(acc["open_positions"])

        base_risk = GFT_EVAL_RISK if gname == "GFT" else EVAL_RISK
        base_r = FLEET_RISK if acc["phase"] == "funded" else base_risk
        pdef = _current_phase(fmt, acc)
        r = effective_risk(acc, pdef, base_r, s["fleet_unlocked"])
        if gname == "Blueberry" and acc["_fmt_key"] in BB_INSTANT_FORMAT_KEYS:
            s["instant_trades_total"] += 1
            if r > BB_INSTANT_RISK_CAP:
                r = BB_INSTANT_RISK_CAP
                s["instant_risk_capped_trades"] += 1

        was_challenge = acc["active"] and acc["phase"] == "challenge"
        was_funded = acc["active"] and acc["phase"] == "funded"
        phase_before, idx_before = acc["phase"], acc["phase_index"]
        split_this = GOAT_GUARD_SPLIT_FLAT if (gname == "GFT" and acc["_gg_split_until"] is not None
                                                and now < acc["_gg_split_until"]) else 0.80
        use_payout_cycle = gname in PAYOUT_CYCLE_FIRMS
        funded_pnl_before = acc["total_funded_pnl"] if was_funded else None

        proxy = {"reserve": s["reserve"], "ever_funded": s["ever_funded"], "total_breaks": 0}
        just_funded = process_trade_corr_swap_rr(acc, trade, now, fmt, proxy, r, market_data, excluded_map,
                                                   split_flat=split_this, reserve_share=ei.FINAL_RESERVE_SHARE,
                                                   cost_override=0.0)
        s["ever_funded"] = proxy["ever_funded"]
        s["reserve"] = proxy["reserve"]
        admitted = len(acc["open_positions"]) > n_before
        # <<< INSTRUMENTATION MAX_POSITIONS (chantier etape0/1, 2026-08-19) :
        # comptage brut, ne modifie aucun comportement.
        if admitted:
            s["trades_admitted_count"] = s.get("trades_admitted_count", 0) + 1
        elif at_cap:
            s["cap_blocked_count"] = s.get("cap_blocked_count", 0) + 1
        else:
            s["corr_blocked_count"] = s.get("corr_blocked_count", 0) + 1

        if use_payout_cycle and was_funded:
            delta = acc["total_funded_pnl"] - funded_pnl_before
            if delta > 0:
                acc["total_funded_pnl"] -= delta
                s["reserve"] -= delta * ei.FINAL_RESERVE_SHARE
                acc["pending_payout"] += delta

        if use_payout_cycle and acc["active"] and acc["last_payout_time"] is not None \
                and now - acc["last_payout_time"] >= (bb_payout_days(acc["_fmt_key"], ceiling_combined, acc["_first_payout_done"])
                                                        if gname == "Blueberry" else
                                                        payout_cycle_days(gname, acc["_first_payout_done"])) * 86400:
            acc["total_funded_pnl"] += acc["pending_payout"]
            if acc["pending_payout"] > 0:
                s["reserve"] += acc["pending_payout"] * ei.FINAL_RESERVE_SHARE
            acc["pending_payout"] = 0.0
            acc["last_payout_time"] = now
            acc["_first_payout_done"] = True

        progressed = (fmt["phases"] and (
            (acc["phase"] == "challenge" and acc["phase_index"] == idx_before + 1) or
            (acc["phase"] == "funded" and phase_before == "challenge")))
        reset_happened = (acc["cumulative_since_reset"] == 0.0 and acc["peak_since_reset"] == 0.0
                          and len(acc["trading_days_since_reset"]) == 0)
        broke = reset_happened and not progressed

        use_goat_guard = (broke and gname == "GFT" and was_funded and acc["_gg_triggered_count"] < 1)
        if use_goat_guard:
            acc["_gg_triggered_count"] += 1
            acc["_gg_split_until"] = now + GOAT_GUARD_SPLIT_DAYS * 86400
            acc["phase"] = "funded"
        elif broke:
            s["total_breaks"] += 1
            if use_payout_cycle and acc["pending_payout"] != 0.0:
                forfeited = max(0.0, acc["pending_payout"])
                bucket = s["forfeited_post"] if s["fleet_unlocked"] else s["forfeited_pre"]
                events = s["forfeit_events_post"] if s["fleet_unlocked"] else s["forfeit_events_pre"]
                if forfeited > 0:
                    bucket[gname] += forfeited
                    events[gname] += 1
                acc["pending_payout"] = 0.0
            use_bb_reset = (gname == "Blueberry" and was_funded and not acc["_reset_used"]
                             and acc["_fmt_key"] == BB_CLASSIC_KEY)
            if use_bb_reset:
                cost = 2.0 * acc["base_cost"]
                acc["active"] = False
                acc["_reset_used"] = True
                handle_cost_hybrid(tid, cost, s["pending_reopen"], id(acc),
                                    lambda a=acc, c=cost, f=fmt: reopen_account(tid, a, c, f, skip_to_funded=True))
            else:
                if gname == "Blueberry":
                    new_fmt_key = bb_choose_fmt_key(tid)
                    acc["_fmt_key"] = new_fmt_key
                    new_fmt = FORMATS[new_fmt_key]
                    palier_for_cost = acc["base_palier"] if downgrade_active(tid) else acc["palier"]
                    cost = price_for_bb(new_fmt_key, palier_for_cost, ceiling_combined)
                    if new_fmt_key == BB_INSTANT_KEY:
                        s["bb_instant_opens"] += 1
                    else:
                        s["bb_classic_opens"] += 1
                elif downgrade_active(tid) and gname == ei.STARTER:
                    new_fmt = fmt
                    cost = acc["base_cost"]
                else:
                    new_fmt = fmt
                    cost = ei.price_for(format_by_firm[gname], acc["palier"])
                    if gname == "FTMO":
                        cost *= FTMO_DISCOUNT_FACTOR
                acc["active"] = False
                handle_cost_hybrid(tid, cost, s["pending_reopen"], id(acc),
                                    lambda a=acc, c=cost, f=new_fmt: reopen_account(tid, a, c, f, skip_to_funded=False))
        else:
            if was_challenge and just_funded and gname not in s["group_own_funded"]:
                s["group_own_funded"].add(gname)
                s["group_funded_count"] += 1

        return just_funded, admitted, at_cap

    def advance_trader_pre(tid, now):
        """<<< CORRECTIF ORDONNANCEMENT (2026-08-20) : partie fiscale/tax
        UNIQUEMENT, execute AVANT le trade de l'evenement -- fidele a
        chantier_S1_8_regen_population_2026-08-19.py:460-478 (le bloc
        fiscal_year/tax_events precede la boucle de traitement du trade,
        lignes 480-602). L'ancienne version (heritee de dual_trader_2026-
        08-11.py:515-544, MEME ordre que ci-dessous mais SANS split)
        executait aussi process_extra_account/pending/group_trigger ICI,
        soit un cran EN AVANCE sur S1.8 -- source probable de l'ecart
        mesure (annee1<0 A-seule ~21-33% vs ~15,5-23,8% officiel)."""
        s = st[tid]
        while (s["next_fy_to_close"] + 1) * YEAR_SECONDS <= now:
            close_fiscal_year(tid, s["next_fy_to_close"])
            s["next_fy_to_close"] += 1
        i = 0
        while i < len(s["tax_events"]):
            t_ev, amt = s["tax_events"][i]
            if t_ev > now:
                i += 1
                continue
            s["tax_events"].pop(i)
            proxy = {"reserve": s["reserve"], "real_cash_paid": combined_cash["real_cash_paid"],
                     "tax_breach_count": 0, "tax_breach_total": 0.0, "tax_breach_max": 0.0,
                     "tax_breach_concurrent_with_repurchase": 0, "tax_breach_events": []}
            handle_tax_payment(amt, proxy, ceiling_combined, now, s["pending_reopen"], s["pending_group_open"])
            s["reserve"] = proxy["reserve"]
            combined_cash["real_cash_paid"] = proxy["real_cash_paid"]
            s["is_paid_cum"] += amt

    def try_sequential_activation(now):
        """<<< CHANTIER LANCEMENT SEQUENTIEL : declenche l'ouverture du
        compte Blueberry jour0 de A des que st['B']['reserve'] franchit
        sequential_b_threshold. Ne reutilise PAS open_group() (cf.
        docstring run_dual_ab pour la raison exacte) -- reevalue le
        format Blueberry dynamique (bb_choose_fmt_key) au moment REEL du
        declenchement, comme le fait l'initialisation jour0 normale de
        B, au lieu de figer BB_CLASSIC_KEY choisi arbitrairement a
        l'initialisation (ligne ~203, is_day0=False pour A en mode
        sequentiel)."""
        if st["A"]["_seq_activated"]:
            return
        if st["B"]["reserve"] < sequential_b_threshold:
            return
        st["A"]["_seq_activated"] = True
        acc = accounts["A"]["Blueberry"][0]
        fmt_key = bb_choose_fmt_key("A")
        acc["_fmt_key"] = fmt_key
        cost = price_for_bb(fmt_key, acc["base_palier"], ceiling_combined)
        acc["base_cost"] = cost

        def _activate():
            # <<< reopen_account() (ligne ~293) REUTILISEE TELLE QUELLE --
            # gere correctement phase/phase_index selon fmt["phases"]
            # (bug initial : activation ad-hoc oubliait ce reset, IndexError
            # sur _current_phase quand le format choisi differait de celui
            # fige a l'initialisation, cf. engine_multiformat.py:262).
            reopen_account("A", acc, cost, FORMATS[fmt_key], skip_to_funded=False)
            if not FORMATS[fmt_key]["phases"]:
                st["A"]["group_own_funded"].add("Blueberry")
                st["A"]["group_funded_count"] += 1

        handle_cost_hybrid("A", cost, st["A"]["pending_reopen"], id(acc), _activate)

    def advance_trader_post(tid, now):
        """<<< CORRECTIF ORDONNANCEMENT : mecanismes de croissance
        (comptes extra, pending, bootstrap urgence, declenchement de
        groupe), executes APRES le trade de l'evenement -- fidele a
        chantier_S1_8_regen_population_2026-08-19.py:604-623 (bloc
        process_extra_account/process_pending/try_emergency_bootstrap/
        pending_group_trigger APRES la boucle de traitement du trade)."""
        s = st[tid]
        if tid == "A" and sequential_b_threshold is not None:
            try_sequential_activation(now)
            if not s["_seq_activated"]:
                return
        process_extra_account(tid, now)
        process_pending(tid, s["pending_reopen"])
        process_pending(tid, s["pending_group_open"])
        try_emergency_bootstrap(tid)
        still_pending = []
        for group_names, trig, thresh, is_final in s["pending_group_trigger"]:
            _, n_req = trig
            if s["group_funded_count"] >= n_req and s["reserve"] >= thresh:
                for gname in group_names:
                    cost0 = sum(a["cost"] for a in accounts[tid][gname])
                    handle_cost_hybrid(tid, cost0, s["pending_group_open"], gname,
                                        lambda g=gname, f=is_final: open_group(tid, g, f))
            else:
                still_pending.append((group_names, trig, thresh, is_final))
        s["pending_group_trigger"] = still_pending
        if s["full_structure_month"] is None and structure_complete(tid):
            s["full_structure_month"] = now / MONTH_SECONDS

    # --- boucle principale : fusion chronologique des 2 flux A et B ---
    events = ([(t, "A", tr) for tr, t in zip(trades_A, slots_A)] +
              [(t, "B", tr) for tr, t in zip(trades_B, slots_B)])
    events.sort(key=lambda e: e[0])

    for now, tid_src, trade in events:
        for tid in TRADERS:
            st[tid]["_now"] = now
        if st["A"]["year1_net_split"] is None and now >= YEAR_SECONDS:
            st["A"]["year1_net_split"] = combined_net_trader("A")
        if st["B"]["year1_net_split"] is None and now >= YEAR_SECONDS:
            st["B"]["year1_net_split"] = combined_net_trader("B")

        advance_trader_pre("A", now)
        advance_trader_pre("B", now)

        is_metal_B_trade = (tid_src == "B" and trade["ticker"] in metal_set)

        if is_metal_B_trade:
            for gname in FIRMS:
                fmtB, fmtA = fmt_by_firm[gname], fmt_by_firm[gname]
                accsB, accsA = accounts["B"][gname], accounts["A"][gname]
                for i, accB in enumerate(list(accsB)):
                    if not accB["active"]:
                        continue
                    fmt_b_eff = FORMATS[accB["_fmt_key"]] if gname == "Blueberry" else fmtB
                    _, admitted, at_cap = process_one_account("B", gname, accB, fmt_b_eff, trade, now)
                    if admitted or at_cap:
                        continue
                    st["B"]["overflow_to_A_count"] += 1
                    if i < len(accsA) and accsA[i]["active"]:
                        accA = accsA[i]
                        fmt_a_eff = FORMATS[accA["_fmt_key"]] if gname == "Blueberry" else fmtA
                        process_one_account("A", gname, accA, fmt_a_eff, trade, now)
        else:
            tid = tid_src
            for gname, accs in accounts[tid].items():
                fmt_default = fmt_by_firm[gname]
                for acc in list(accs):
                    if not acc["active"]:
                        continue
                    fmt_eff = FORMATS[acc["_fmt_key"]] if gname == "Blueberry" else fmt_default
                    process_one_account(tid, gname, acc, fmt_eff, trade, now)

        advance_trader_post("A", now)
        advance_trader_post("B", now)

    for tid in TRADERS:
        if st[tid]["year1_net_split"] is None:
            st[tid]["year1_net_split"] = combined_net_trader(tid)

    result = {}
    for tid in TRADERS:
        s = st[tid]
        result[f"{tid}_net"] = combined_net_trader(tid)
        result[f"{tid}_is_paid"] = s["is_paid_cum"]
        result[f"{tid}_year1_net"] = s["year1_net_split"]
        result[f"{tid}_total_breaks"] = s["total_breaks"]
        result[f"{tid}_overflow_to_A"] = s.get("overflow_to_A_count", 0)
        result[f"{tid}_trades_admitted"] = s.get("trades_admitted_count", 0)
        result[f"{tid}_cap_blocked"] = s.get("cap_blocked_count", 0)
        result[f"{tid}_corr_blocked"] = s.get("corr_blocked_count", 0)
    result["combined_net"] = combined_net_all()
    result["combined_is_paid"] = st["A"]["is_paid_cum"] + st["B"]["is_paid_cum"]
    result["combined_year1_net"] = st["A"]["year1_net_split"] + st["B"]["year1_net_split"]
    result["combined_hit_ceiling"] = combined_cash["hit_ceiling"]
    result["sim_duration_months"] = (events[-1][0] if events else 0.0) / MONTH_SECONDS
    return result


def build_pop_B():
    pop_B = pd.read_csv("chantier_gold_silver_pop_B_config0_2026-08-19.csv")
    pop_B["date_creation"] = pd.to_datetime(pop_B["date_creation"])
    pop_B["resolution_time_est"] = pd.to_datetime(pop_B["resolution_time_est"])
    return pop_B


GOLD_SILVER_LABELS = [f"{m} - {c}" for m in ("GOLD", "SILVER")
                       for c in ("USD", "EUR", "GBP", "CHF", "CAD", "AUD", "NZD")]


def build_market_data_and_excluded_map(pop_A, pop_B):
    _, market_data, _ = load_common_A()
    # <<< CORRECTIF (meme raison que chantier_gold_silver_ab_engine_2026-08-
    # 19.py:173-184) : build_market_data_with_indices() du module S1.8 ne
    # couvre que les 5 labels indices, pas les 14 labels GOLD/SILVER --
    # feasible_risk_pct() plante (KeyError) sinon des que B traite un trade
    # metal. Meme contrainte de capacite desactivee ("unconstrained").
    unconstrained = {"tick_size": 1.0, "tick_value": 1.0, "volume_min": 0.0001,
                      "volume_max": 1e9, "volume_step": 0.0001, "margin_per_lot": 0.0001, "price": 1.0}
    for label in GOLD_SILVER_LABELS:
        market_data[label] = dict(unconstrained)
    all_tickers = sorted(set(pop_A["ticker"].unique()) | set(pop_B["ticker"].unique()))
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    excluded_map = precompute_correlation_pairs(all_tickers, corr_matrix, CORR_TH_NEW)
    return market_data, excluded_map


def run_n_sims(pop_A, pop_B, ceiling, n_sims, seed, include_B, market_data, excluded_map, metal_set,
                sequential_b_threshold=None):
    """Coeur reutilise par run_sweep (population complete) ET le stress-test
    (sous-populations par sous-periode) -- ancrage calendaire commun +
    bloc-bootstrap CONJOINT (cf. docstring module), include_B=False ->
    B totalement absent des evenements (baseline A-seul, meme moteur)."""
    seq = ei.seq_grouped_multi(1000, 15000, 25000, 25000)
    config = ei.CONFIG_REF
    block_seconds = 2 * 30 * DAY_SECONDS

    # <<< CORRECTIF (2026-08-20) : l'ancrage calendaire commun ne doit
    # s'appliquer QUE si B participe reellement -- B (metaux) demarre le
    # 2021-04-22, A le 2022-01-31 (284,5 jours plus tard, verifie), donc en
    # mode include_B=False (baseline A-seule) calculer quand meme l'ancrage
    # sur pop_B decalait A de 284,5 jours dans un prefixe de blocs VIDES
    # (aucun trade A avant son propre debut), gonflant artificiellement
    # n_blocks et target_duration, et diluant la 1ere annee simulee avec des
    # tirages de blocs vides -- c'est ce qui expliquait l'ecart annee1<0
    # vs la reference officielle S1.8 (confirme par comparaison directe
    # sur une sequence bootstrappee identique, s18.run_one vs run_dual_ab :
    # resultats identiques au $ pres une fois l'ancrage neutralise).
    if include_B:
        common_anchor = min(pop_A["date_creation"].min(), pop_B["date_creation"].min())
        offset_A = (pop_A["date_creation"].min() - common_anchor).total_seconds()
        offset_B = (pop_B["date_creation"].min() - common_anchor).total_seconds()
    else:
        offset_A = 0.0
        offset_B = 0.0

    rng_wr_A = random.Random(seed)
    rng_boot_A = random.Random(seed + 1)
    rng_wr_B = random.Random(seed + 2)
    rng_boot_B = random.Random(seed + 3)
    rng_block_join = random.Random(seed + 4)
    recs = []
    for _ in range(n_sims):
        wr_A = rng_wr_A.betavariate(ALPHA_POST, BETA_POST)
        trades_A, slots_A = build_flexible_population_with_rr(pop_A, wr_A, 1.0, False, random.Random(rng_boot_A.random()))
        slots_A_abs = [s + offset_A for s in slots_A]

        if include_B:
            wr_B = rng_wr_B.betavariate(ALPHA_POST_B_METAUX, BETA_POST_B_METAUX)
            trades_B, slots_B = build_flexible_population_with_rr(pop_B, wr_B, 1.0, False, random.Random(rng_boot_B.random()))
            slots_B_abs = [s + offset_B for s in slots_B]
        else:
            trades_B, slots_B_abs = [], [0.0]

        n_blocks = max(int(slots_A_abs[-1] // block_seconds), int(slots_B_abs[-1] // block_seconds)) + 1
        blocks_A = [[] for _ in range(n_blocks)]
        for tr, t in zip(trades_A, slots_A_abs):
            idx = int(t // block_seconds)
            if 0 <= idx < n_blocks:
                blocks_A[idx].append((tr, t - idx * block_seconds))
        blocks_B = [[] for _ in range(n_blocks)]
        if include_B:
            for tr, t in zip(trades_B, slots_B_abs):
                idx = int(t // block_seconds)
                if 0 <= idx < n_blocks:
                    blocks_B[idx].append((tr, t - idx * block_seconds))

        target_duration = max(slots_A_abs[-1], slots_B_abs[-1])
        raw_A_t, raw_A_s, raw_B_t, raw_B_s = [], [], [], []
        cursor = 0.0
        while cursor < target_duration:
            idx = rng_block_join.randrange(n_blocks)
            for trade, offset in blocks_A[idx]:
                raw_A_t.append(trade); raw_A_s.append(cursor + offset)
            for trade, offset in blocks_B[idx]:
                raw_B_t.append(trade); raw_B_s.append(cursor + offset)
            cursor += block_seconds

        res = run_dual_ab(raw_A_t, raw_A_s, raw_B_t, raw_B_s, market_data, excluded_map,
                           ceiling, seq, config, ei.DEFAULT_EMERGENCY, metal_set if include_B else set(),
                           sequential_b_threshold=sequential_b_threshold)
        recs.append(res)
    return pd.DataFrame(recs)


def summarize_df(df, label, ceiling):
    combined_net = df["combined_net"] - df["combined_is_paid"]
    year1_neg = df["combined_year1_net"] < 0
    corr_AB = np.nan
    if df["B_net"].std() > 0 and df["A_net"].std() > 0:
        corr_AB = np.corrcoef(df["A_net"] - df["A_is_paid"], df["B_net"] - df["B_is_paid"])[0, 1]
    return dict(config=label, ceiling=ceiling, n=len(df),
                profit_moyen=combined_net.mean(), profit_median=combined_net.median(),
                solde_negatif_annee4=(combined_net < 0).mean() * 100,
                hit_ceiling_pct=df["combined_hit_ceiling"].mean() * 100,
                annee1_neg=year1_neg.mean() * 100,
                overflow_to_A_moy=df["B_overflow_to_A"].mean(),
                corr_PnL_A_B=corr_AB)


def run_sweep(n_sims, ceilings, out_tag, seed=9999, config2_only=False):
    pop_A, _, _ = load_common_A()
    pop_B = build_pop_B()
    oa_all = pd.read_csv("chantier_gold_silver_pop_metaux_all_2026-08-19.csv")
    metal_set = set(oa_all["ticker"].unique())
    market_data, excluded_map = build_market_data_and_excluded_map(pop_A, pop_B)

    rows = []
    for ceiling in ceilings:
        if config2_only:
            t0 = time.time()
            df_c2 = run_n_sims(pop_A, pop_B, ceiling, n_sims, seed, True, market_data, excluded_map, metal_set)
            row_c2 = summarize_df(df_c2, "Config2_AB_metaux", ceiling)
            rows.append(row_c2)
            print(f"[Config2_AB   plafond={ceiling:.0f}$] profit_moy={row_c2['profit_moyen']:+,.0f}$ "
                  f"solde_neg_an4={row_c2['solde_negatif_annee4']:.2f}% hit_ceiling={row_c2['hit_ceiling_pct']:.2f}% "
                  f"annee1<0={row_c2['annee1_neg']:.2f}% overflow_moy={row_c2['overflow_to_A_moy']:.1f} "
                  f"corr_PnL(A,B)={row_c2['corr_PnL_A_B']:.3f} ({time.time()-t0:.0f}s)")
            pd.DataFrame(rows).to_csv(f"chantier_ab_metaux_cascade_officiel_{out_tag}_2026-08-19.csv", index=False)
            continue
        t0 = time.time()
        df_a = run_n_sims(pop_A, pop_B, ceiling, n_sims, seed, False, market_data, excluded_map, metal_set)
        row_a = summarize_df(df_a, "A_seul_sans_metaux", ceiling)
        rows.append(row_a)
        print(f"[A_seul       plafond={ceiling:.0f}$] profit_moy={row_a['profit_moyen']:+,.0f}$ "
              f"solde_neg_an4={row_a['solde_negatif_annee4']:.2f}% hit_ceiling={row_a['hit_ceiling_pct']:.2f}% "
              f"annee1<0={row_a['annee1_neg']:.2f}% ({time.time()-t0:.0f}s)")

        t0 = time.time()
        df_c2 = run_n_sims(pop_A, pop_B, ceiling, n_sims, seed, True, market_data, excluded_map, metal_set)
        row_c2 = summarize_df(df_c2, "Config2_AB_metaux", ceiling)
        rows.append(row_c2)
        print(f"[Config2_AB   plafond={ceiling:.0f}$] profit_moy={row_c2['profit_moyen']:+,.0f}$ "
              f"solde_neg_an4={row_c2['solde_negatif_annee4']:.2f}% hit_ceiling={row_c2['hit_ceiling_pct']:.2f}% "
              f"annee1<0={row_c2['annee1_neg']:.2f}% overflow_moy={row_c2['overflow_to_A_moy']:.1f} "
              f"corr_PnL(A,B)={row_c2['corr_PnL_A_B']:.3f} ({time.time()-t0:.0f}s)")

        pd.DataFrame(rows).to_csv(f"chantier_ab_metaux_cascade_officiel_{out_tag}_2026-08-19.csv", index=False)
    return pd.DataFrame(rows)


def date_subperiods(pop_A, pop_B, n_parts):
    """Sous-periodes CALENDAIRES communes a A et B (pas un split independant
    par population -- H1/H2 ou les 4 blocs doivent designer la MEME fenetre
    calendaire pour les deux flottes, meme logique que l'ancrage commun de
    run_n_sims)."""
    lo = min(pop_A["date_creation"].min(), pop_B["date_creation"].min())
    hi = max(pop_A["date_creation"].max(), pop_B["date_creation"].max())
    edges = pd.date_range(lo, hi, periods=n_parts + 1)
    parts = []
    for i in range(n_parts):
        a0, a1 = edges[i], edges[i + 1]
        sub_A = pop_A[(pop_A["date_creation"] >= a0) & (pop_A["date_creation"] < a1)].reset_index(drop=True)
        sub_B = pop_B[(pop_B["date_creation"] >= a0) & (pop_B["date_creation"] < a1)].reset_index(drop=True)
        parts.append((sub_A, sub_B))
    return parts


def run_stress_test(n_sims, ceilings, out_tag, seed=13579, with_a_seul=True):
    pop_A, _, _ = load_common_A()
    pop_B = build_pop_B()
    oa_all = pd.read_csv("chantier_gold_silver_pop_metaux_all_2026-08-19.csv")
    metal_set = set(oa_all["ticker"].unique())
    market_data, excluded_map = build_market_data_and_excluded_map(pop_A, pop_B)

    rows = []
    for n_parts, tag in ((2, "H"), (4, "bloc")):
        parts = date_subperiods(pop_A, pop_B, n_parts)
        for i, (sub_A, sub_B) in enumerate(parts):
            if len(sub_A) < 10 or len(sub_B) < 10:
                print(f"[{tag}{i+1}] sous-population trop petite (A={len(sub_A)}, B={len(sub_B)}) -- ignore")
                continue
            for ceiling in ceilings:
                if with_a_seul:
                    t0 = time.time()
                    df_a = run_n_sims(sub_A, sub_B, ceiling, n_sims, seed, False, market_data, excluded_map, metal_set)
                    row_a = summarize_df(df_a, f"A_seul_{tag}{i+1}", ceiling)
                    row_a["n_trades_A"] = len(sub_A)
                    row_a["n_trades_B"] = len(sub_B)
                    rows.append(row_a)
                    print(f"[{tag}{i+1} plafond={ceiling:.0f}$ A_seul] profit_moy={row_a['profit_moyen']:+,.0f}$ "
                          f"solde_neg_an4={row_a['solde_negatif_annee4']:.2f}% annee1<0={row_a['annee1_neg']:.2f}% "
                          f"({time.time()-t0:.0f}s)")

                t0 = time.time()
                df_c2 = run_n_sims(sub_A, sub_B, ceiling, n_sims, seed, True, market_data, excluded_map, metal_set)
                row = summarize_df(df_c2, f"Config2_AB_{tag}{i+1}", ceiling)
                row["n_trades_A"] = len(sub_A)
                row["n_trades_B"] = len(sub_B)
                rows.append(row)
                print(f"[{tag}{i+1} plafond={ceiling:.0f}$ Config2] profit_moy={row['profit_moyen']:+,.0f}$ "
                      f"solde_neg_an4={row['solde_negatif_annee4']:.2f}% annee1<0={row['annee1_neg']:.2f}% "
                      f"corr_PnL(A,B)={row['corr_PnL_A_B']:.3f} ({time.time()-t0:.0f}s)")
                pd.DataFrame(rows).to_csv(f"chantier_ab_metaux_cascade_officiel_stresstest_{out_tag}_2026-08-19.csv", index=False)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "sweep"
    n_sims = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    ceilings_arg = [float(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else [960.0, 1000.0, 3000.0, 5000.0]
    out_tag = sys.argv[4] if len(sys.argv) > 4 else "screen"
    if mode == "sweep":
        run_sweep(n_sims, ceilings_arg, out_tag)
    elif mode == "sweep_config2only":
        run_sweep(n_sims, ceilings_arg, out_tag, config2_only=True)
    elif mode == "stress":
        run_stress_test(n_sims, ceilings_arg, out_tag)
