"""
Chantier 2026-08-15 : plafond de 3 positions simultanees vs signaux a haut RR
rejetes faute de place. Base actuelle du projet (registre_parametres_projet.md
S1.8, adoptee 08/12) : population RR>=1,35, seuil de correlation 0,80,
eval_risk=1,25% (confirme par l'utilisateur 08/15).

SECTION 1 : mesure de l'ampleur reelle (replay chronologique 1-compte, la
meme methodologie/convention que missed_signals_replay.py -- upper bound du
cout d'opportunite PAR COMPTE, puisque la structure reelle copytrade le meme
signal sur plusieurs comptes en parallele : un signal bloque sur un compte
peut etre pris par un autre, cf. docstring missed_signals_replay.py).

SECTION 2 : plafond releve a 4 positions, sans logique de coupe -- simple
monkeypatch de eng.MAX_POSITIONS, moteur de flotte complet inchange sinon.

SECTION 3 : remplacement preventif (swap) -- si un signal arrive avec RR
(rr_tp1, ratio plafonne) >= X fois le RR le plus faible parmi les positions
ouvertes ET que les 3 slots sont pleins, on libere le slot du RR le plus
faible pour admettre le nouveau signal.

LIMITE DE MODELISATION EXPLICITE (Section 3) : le moteur (engine_multiformat.
process_trade_mf) applique le PnL d'un trade INTEGRALEMENT au moment de son
OUVERTURE (resolution instantanee, pas de suivi de prix intraday/flottant --
seul le luster ticker+heure de cloture sert a la logique de plafond/
correlation). Il n'existe donc AUCUNE donnee de prix intra-position dans ce
projet permettant de simuler fidelement "on coupe la position en cours de
route a son prix actuel". La coupe est donc modelisee comme la liberation du
SLOT D'OCCUPATION uniquement (permet au nouveau signal d'entrer) SANS toucher
au PnL deja applique de la position coupee -- c'est-a-dire que la position
coupee continue de compter son resultat final reel dans le P&L du compte.
Consequence attendue : ceci SURESTIME probablement le gain reel d'un vrai
swap (dans la vraie vie, couper une position avant son terme change son R
reel, generalement vers un resultat moins extreme que le sec de son issue
finale) -- a lire comme une borne HAUTE de l'effet, pas une estimation
centree. Signale explicitement plutot que suppose neutre.

SECTION 4 (4e position temporaire + retour a 3) : NON FAITE a ce stade --
gating explicite du prompt ("seulement si Section 3 decoit"), voir la
conclusion en bas de Section 3 pour la decision.
"""
import sys
import time

import numpy as np
import pandas as pd

import robustness_5ers_risk_challenge as eng
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs, is_jpy
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from split_tax_model import compute_is, handle_tax_payment, IS_THRESHOLD_ACOMPTE, Q_OFFSETS_DAYS, \
    SOLDE_OFFSET_DAYS, ACOMPTE_FRACTION
from corrected_scaling_mechanism import BASE_PALIER
from engine_multiformat import FORMATS, make_acc_mf, process_trade_mf, _current_phase
import etape_e_fleet_integration as ei
from point_liquidity_rules import DAY_SECONDS

YEAR_SECONDS = 365.25 * DAY_SECONDS
MONTH_SECONDS = DAYS_PER_MONTH * DAY_SECONDS
SIX_MONTHS_SECONDS = 6 * MONTH_SECONDS
FIRMS = ("Blueberry", "FTMO", "Fivers", "GFT", "FundedNext")

MIN_RR = 1.35
CORR_TH = 0.80
EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK = 1.25, 1.90, 1.75

HYSTERESIS = 0.10
FTMO_DISCOUNT_FACTOR = 0.90
GOAT_GUARD_SPLIT_DAYS = 30
GOAT_GUARD_SPLIT_FLAT = 0.50
PAYOUT_CYCLE_FIRMS = ("Blueberry", "GFT", "Fivers")
PAYOUT_CYCLE_DAYS_FIRST = {"Blueberry": 14, "GFT": 3, "Fivers": 14}
PAYOUT_CYCLE_DAYS_SUBSEQUENT = {"Blueberry": 14, "GFT": 1.5, "Fivers": 14}


def payout_cycle_days(gname, first_payout_done):
    table = PAYOUT_CYCLE_DAYS_SUBSEQUENT if first_payout_done else PAYOUT_CYCLE_DAYS_FIRST
    return table[gname]


# ============================================================
# SECTION 1 -- mesure de l'ampleur (replay 1-compte, upper bound)
# ============================================================

def section1_replay():
    print("=" * 70)
    print("SECTION 1 -- ampleur du probleme (replay chronologique 1-compte,")
    print(f"population reelle RR>={MIN_RR}, seuil correlation {CORR_TH})")
    print("=" * 70)

    pop = build_population_with_trailing("fixed", 0.15, min_rr=MIN_RR, verbose=False)
    pop = pop.sort_values("date_creation").reset_index(drop=True)
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

    open_positions = []  # (ticker, close_time, rr_tp1)
    rows = []
    for _, row in pop.iterrows():
        now = row["date_creation"]
        close_time = row["resolution_time_est"]
        ticker = row["ticker"]
        rr = row["rr_tp1"]
        r = row["r_trailing"] if row["statut_final"] == "OBJECTIF ATTEINT" else -1.0

        open_positions = [(t, c, x) for (t, c, x) in open_positions if c > now]

        blocked_reason = None
        weakest_open_rr = min((x for (_, _, x) in open_positions), default=float("nan"))
        if len(open_positions) >= eng.MAX_POSITIONS:
            blocked_reason = "cap_position"
        elif any(t in excluded_map[ticker] for (t, _, _) in open_positions):
            blocked_reason = "correlation"

        rows.append({"date_creation": now, "ticker": ticker, "rr_tp1": rr, "r_trailing": r,
                      "n_open_at_signal": len(open_positions), "blocked_reason": blocked_reason,
                      "weakest_open_rr_at_signal": weakest_open_rr})

        if blocked_reason is None:
            open_positions.append((ticker, close_time, rr))

    df = pd.DataFrame(rows)
    df.to_csv("chantier_position_cap_section1_detail_2026-08-15.csv", index=False)

    n = len(df)
    taken = df[df["blocked_reason"].isna()]
    cap = df[df["blocked_reason"] == "cap_position"]
    corr = df[df["blocked_reason"] == "correlation"]

    def fmt_block(label, sub):
        if len(sub) == 0:
            print(f"  {label:16s}:    0 ( 0.0%)")
            return
        print(f"  {label:16s}: {len(sub):4d} ({len(sub) / n * 100:5.1f}%) | "
              f"R_trailing moyen={sub['r_trailing'].mean():+.3f} | "
              f"winrate={(sub['r_trailing'] > 0).mean() * 100:5.1f}% | "
              f"RR(rr_tp1) moyen={sub['rr_tp1'].mean():.2f} | RR median={sub['rr_tp1'].median():.2f}")

    print(f"\nPopulation rejouee (ordre chronologique reel, 1 compte) : n={n}")
    fmt_block("Pris", taken)
    fmt_block("Bloque (cap)", cap)
    fmt_block("Bloque (correl)", corr)

    print(f"\n  RR (rr_tp1) des signaux bloques par le CAP -- distribution :")
    if len(cap):
        print(f"    min={cap['rr_tp1'].min():.2f}  p25={cap['rr_tp1'].quantile(.25):.2f}  "
              f"median={cap['rr_tp1'].median():.2f}  p75={cap['rr_tp1'].quantile(.75):.2f}  "
              f"max={cap['rr_tp1'].max():.2f}")
        print(f"    part avec RR>=2,0 : {(cap['rr_tp1'] >= 2.0).mean() * 100:.1f}%  "
              f"part avec RR>=3,0 : {(cap['rr_tp1'] >= 3.0).mean() * 100:.1f}%  "
              f"part avec RR>=5,0 : {(cap['rr_tp1'] >= 5.0).mean() * 100:.1f}%")
        # comparaison au RR du signal le plus faible deja en place au moment du rejet
        cmp = cap.dropna(subset=["weakest_open_rr_at_signal"])
        better = cmp[cmp["rr_tp1"] > cmp["weakest_open_rr_at_signal"]]
        print(f"\n  Parmi les {len(cap)} signaux bloques par le cap : {len(cmp)} avaient bien 3 positions "
              f"ouvertes avec un RR connu au moment du rejet.")
        print(f"    Signaux rejetes AVEC un RR strictement superieur au plus faible RR deja en place : "
              f"{len(better)} ({len(better) / max(len(cmp), 1) * 100:.1f}% des cas comparables)")
        if len(better):
            print(f"    Ecart moyen (RR rejete - RR le plus faible en place) sur ces cas : "
                  f"{(better['rr_tp1'] - better['weakest_open_rr_at_signal']).mean():+.2f}")
            ratio = (better['rr_tp1'] / better['weakest_open_rr_at_signal'])
            print(f"    Ratio moyen (RR rejete / RR le plus faible en place) : {ratio.mean():.2f}x "
                  f"(median {ratio.median():.2f}x)")

    total_blocked_r = cap["r_trailing"].sum() + corr["r_trailing"].sum()
    print(f"\n  R cumule LAISSE SUR LA TABLE (signaux bloques, 1 seul compte) = {total_blocked_r:+.2f}R "
          f"sur {len(cap) + len(corr)} signaux")
    print(f"  R cumule REELLEMENT PRIS (1 compte)                          = {taken['r_trailing'].sum():+.2f}R "
          f"sur {len(taken)} signaux")
    print(f"  -> cap seul : {cap['r_trailing'].sum():+.2f}R sur {len(cap)} signaux "
          f"({len(cap) / n * 100:.1f}% de la population)")

    print(f"\n  NOTE (identique a missed_signals_replay.py) : ce replay 1-compte MAJORE le taux de blocage "
          f"reel de la flotte (structure copytrade multi-comptes/multi-firms, un signal bloque sur un compte "
          f"peut etre pris par un autre) -- a lire comme une borne HAUTE du cout d'opportunite par compte, "
          f"utile pour Section 1 (ampleur relative) mais PAS directement comparable aux $ de la reference "
          f"officielle (S1.8, moteur de flotte complet, Sections 2-3 ci-dessous).")

    return df


# ============================================================
# Moteur de flotte complet (copie de etape_aq_run_c_rr135_corr080_2026-08-12.py,
# convention du projet : copie figee, seuls les points marques <<< CHANTIER
# sont ajoutes/changes pour ce chantier)
# ============================================================

def build_flexible_population_with_rr(pop, target_winrate, rr_stress_factor, use_slippage, rng):
    """<<< CHANTIER : identique a eng.build_flexible_population, avec en plus
    le champ rr_tp1 (RR PLANIFIE, pas le R realise) attache a chaque trade,
    necessaire a la logique de swap Section 3. L'ordre de tri interne
    (date_creation) est reproduit ici pour aligner les deux structures --
    verifie par assert (longueur + 1ere/derniere date identiques)."""
    trades, slot_arrivals = eng.build_flexible_population(pop, target_winrate, rr_stress_factor, use_slippage, rng)
    sub = pop.sort_values("date_creation").reset_index(drop=True)
    assert len(sub) == len(trades), "desynchronisation build_flexible_population_with_rr"
    for t, rr in zip(trades, sub["rr_tp1"]):
        t["rr_tp1"] = float(rr)
    return trades, slot_arrivals


def process_trade_swap(acc, trade, now, fmt, state, risk_pct, market_data, excluded_map, swap_x,
                        split_flat=0.80, reserve_share=0.95, cost_override=None):
    """<<< CHANTIER (Section 3) : wrapper autour de process_trade_mf (INCHANGE,
    reutilise tel quel) qui, AVANT l'appel, libere le slot du RR le plus faible
    si (a) le compte est deja au plafond ET (b) le nouveau signal a un RR
    (rr_tp1) >= swap_x fois le RR le plus faible actuellement en place. Ne
    duplique aucune logique de DD/casse/phase -- seule la liste
    acc['open_positions'] est mutee en amont, exactement comme le ferait
    l'expiration naturelle d'une position (meme mecanisme, juste declenche
    plus tot). Limite de modelisation : voir docstring de module (le PnL de
    la position coupee reste celui de son issue reelle, deja applique a son
    ouverture -- borne HAUTE de l'effet)."""
    if not acc["active"]:
        return False

    acc["open_positions"] = [(t, c) for (t, c) in acc["open_positions"] if c > now]
    acc["_open_meta"] = [m for m in acc.get("_open_meta", []) if m["close_time"] > now]

    if len(acc["open_positions"]) >= eng.MAX_POSITIONS and acc["_open_meta"]:
        weakest = min(acc["_open_meta"], key=lambda m: m["rr"])
        if trade["rr_tp1"] >= swap_x * weakest["rr"]:
            acc["open_positions"] = [p for p in acc["open_positions"]
                                      if not (p[0] == weakest["ticker"] and p[1] == weakest["close_time"])]
            acc["_open_meta"].remove(weakest)
            state["swap_evictions"] = state.get("swap_evictions", 0) + 1

    n_before = len(acc["open_positions"])
    result = process_trade_mf(acc, trade, now, fmt, state, risk_pct, market_data, excluded_map,
                               split_flat=split_flat, reserve_share=reserve_share, cost_override=cost_override)
    if len(acc["open_positions"]) > n_before:
        new_ticker, new_close = acc["open_positions"][-1]
        acc.setdefault("_open_meta", []).append({"ticker": new_ticker, "close_time": new_close, "rr": trade["rr_tp1"]})
        state["swap_admits"] = state.get("swap_admits", 0) + 1
    return result


def run_one(trades, slot_arrivals, market_data, excluded_map, order, ceiling, seq_grouped, format_by_firm,
            emergency_capital, eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult,
            b_entry_frac=None, b_reduction=None, pre_unlock_only=False,
            ftmo_discount=False, gft_goat_guard=False, payout_cycle=False,
            position_mode="baseline", swap_x=None):
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
        is_day0 = (gname == ei.STARTER)
        palier, cost = base_palier_cost(gname)
        fmt = fmt_by_firm[gname]
        accs = [make_acc_mf(fmt, palier, cost=cost, active=is_day0) for _ in range(ei.N_ACCOUNTS_DAY0[gname])]
        for a in accs:
            a["_gname"] = gname
            a["base_palier"] = palier
            a["base_cost"] = cost
            a["_reset_used"] = False
            a["last_open_time"] = 0.0 if is_day0 else None
            a["_dd_reduced"] = False
            a["_dd_oscillations"] = 0
            a["_gg_triggered_count"] = 0
            a["_gg_split_until"] = None
            a["pending_payout"] = 0.0
            a["last_payout_time"] = 0.0 if is_day0 else None
            a["_first_payout_done"] = False
        accounts_by_group[gname] = accs
        if is_day0:
            active0_cost += sum(a["cost"] for a in accs)

    fleet_unlocked = False
    _init_own_funded = {g for g in ("Blueberry",) if not fmt_by_firm[g]["phases"]}
    state = {"reserve": 0.0, "ever_funded": False, "real_cash_paid": active0_cost, "total_breaks": 0,
             "group_funded_count": len(_init_own_funded), "group_own_funded": set(_init_own_funded),
             "hit_ceiling": False, "emergency_remaining": emergency_capital, "is_paid_cum": 0.0,
             "extra_accounts_opened": {g: 0 for g in ei.GROWTH_FIRMS_EXTRA},
             "tax_breach_count": 0, "tax_breach_total": 0.0, "tax_breach_max": 0.0,
             "tax_breach_concurrent_with_repurchase": 0, "tax_breach_events": [], "_now": 0.0,
             "total_opens": sum(1 for accs in accounts_by_group.values() for a in accs if a["last_open_time"] == 0.0),
             "breaks_within_30d": 0, "breaks_within_60d": 0, "blueberry_resets_used": 0,
             "dd_reduced_obs": 0, "dd_total_obs": 0, "funding_delays": [], "gft_soft_breaches": 0,
             "forfeited_pre": {g: 0.0 for g in PAYOUT_CYCLE_FIRMS}, "forfeited_post": {g: 0.0 for g in PAYOUT_CYCLE_FIRMS},
             "forfeit_events_pre": {g: 0 for g in PAYOUT_CYCLE_FIRMS}, "forfeit_events_post": {g: 0 for g in PAYOUT_CYCLE_FIRMS},
             "swap_evictions": 0, "swap_admits": 0}
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
        acc["_dd_reduced"] = False
        acc["_gg_triggered_count"] = 0
        acc["_gg_split_until"] = None
        acc["pending_payout"] = 0.0
        acc["last_payout_time"] = state["_now"]
        acc["_first_payout_done"] = False
        state["total_opens"] += 1
        if downgrade_active() and acc.get("_gname") == ei.STARTER:
            acc["palier"] = acc["base_palier"]
            acc["cost"] = acc["base_cost"]

    def open_group(gname, is_final):
        for a in accounts_by_group[gname]:
            a["active"] = True
            a["total_fees_paid"] = a["cost"]
            a["last_open_time"] = state["_now"]
            a["_dd_reduced"] = False
            a["_gg_triggered_count"] = 0
            a["_gg_split_until"] = None
            a["pending_payout"] = 0.0
            a["last_payout_time"] = state["_now"]
            a["_first_payout_done"] = False
            state["total_opens"] += 1
        if not fmt_by_firm[gname]["phases"]:
            mark_group_funded_if_needed(gname)

    def try_emergency_bootstrap():
        if n_active_accounts() != 0 or emergency_capital <= 0 or state["emergency_remaining"] <= 0:
            return
        bb_acc = accounts_by_group[ei.STARTER][0]
        cost = bb_acc["base_cost"] if downgrade_active() else bb_acc["cost"]
        if state["emergency_remaining"] >= cost:
            state["emergency_remaining"] -= cost
            reopen_account(bb_acc, cost, fmt_by_firm[ei.STARTER])
            pending_reopen[:] = [p for p in pending_reopen if p["key"] != id(bb_acc)]

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
                new_acc["_dd_reduced"] = False
                new_acc["_dd_oscillations"] = 0
                new_acc["_gg_triggered_count"] = 0
                new_acc["_gg_split_until"] = None
                new_acc["pending_payout"] = 0.0
                new_acc["last_payout_time"] = now
                new_acc["_first_payout_done"] = False
                accs.append(new_acc)
                state["extra_accounts_opened"][gname] += 1
                state["total_opens"] += 1

    def structure_complete():
        for g in FIRMS:
            if not accounts_by_group[g][0]["active"]:
                return False
        return True

    def effective_risk(acc, pdef, base_r):
        if b_entry_frac is None:
            return base_r
        if pre_unlock_only and fleet_unlocked:
            return base_r
        dd_max = pdef["dd_max_pct"]
        if dd_max is None:
            return base_r
        distance = dd_distance_pct(acc, pdef)
        frac = distance / dd_max if dd_max > 0 else 1.0
        state["dd_total_obs"] += 1
        was_reduced = acc["_dd_reduced"]
        if not was_reduced and frac <= b_entry_frac:
            acc["_dd_reduced"] = True
            acc["_dd_oscillations"] += 1
        elif was_reduced and frac >= b_entry_frac + HYSTERESIS:
            acc["_dd_reduced"] = False
        mult = b_reduction if acc["_dd_reduced"] else 1.0
        if mult < 1.0:
            state["dd_reduced_obs"] += 1
        return base_r * mult

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

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]
        state["_now"] = now

        if now <= SIX_MONTHS_SECONDS:
            reserve_min_6mo = min(reserve_min_6mo, state["reserve"])

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
            use_payout_cycle = payout_cycle and gname in PAYOUT_CYCLE_FIRMS
            for acc in list(accs):
                if not acc["active"]:
                    continue
                base_r = fleet_risk if acc["phase"] == "funded" else base_risk
                pdef = _current_phase(fmt, acc)
                r = effective_risk(acc, pdef, base_r)
                was_challenge = acc["active"] and acc["phase"] == "challenge"
                was_funded = acc["active"] and acc["phase"] == "funded"
                phase_before, idx_before = acc["phase"], acc["phase_index"]
                split_this = GOAT_GUARD_SPLIT_FLAT if (gft_goat_guard and gname == "GFT"
                                                        and acc["_gg_split_until"] is not None
                                                        and now < acc["_gg_split_until"]) else 0.80

                funded_pnl_before = acc["total_funded_pnl"] if was_funded else None
                if position_mode == "swap":
                    just_funded = process_trade_swap(acc, trade, now, fmt, state, r, market_data, excluded_map,
                                                      swap_x, split_flat=split_this, reserve_share=reserve_share,
                                                      cost_override=0.0)
                else:
                    just_funded = process_trade_mf(acc, trade, now, fmt, state, r, market_data, excluded_map,
                                                    split_flat=split_this, reserve_share=reserve_share,
                                                    cost_override=0.0)

                if use_payout_cycle and was_funded:
                    delta = acc["total_funded_pnl"] - funded_pnl_before
                    if delta > 0:
                        acc["total_funded_pnl"] -= delta
                        state["reserve"] -= delta * reserve_share
                        acc["pending_payout"] += delta

                if just_funded and acc["last_open_time"] is not None:
                    state["funding_delays"].append((now - acc["last_open_time"]) / 86400.0)

                if use_payout_cycle and acc["active"] and acc["last_payout_time"] is not None \
                        and now - acc["last_payout_time"] >= payout_cycle_days(gname, acc["_first_payout_done"]) * 86400:
                    acc["total_funded_pnl"] += acc["pending_payout"]
                    if acc["pending_payout"] > 0:
                        state["reserve"] += acc["pending_payout"] * reserve_share
                    acc["pending_payout"] = 0.0
                    acc["last_payout_time"] = now
                    acc["_first_payout_done"] = True

                progressed = (fmt["phases"] and (
                    (acc["phase"] == "challenge" and acc["phase_index"] == idx_before + 1) or
                    (acc["phase"] == "funded" and phase_before == "challenge")))
                reset_happened = (acc["cumulative_since_reset"] == 0.0 and acc["peak_since_reset"] == 0.0
                                  and len(acc["trading_days_since_reset"]) == 0)
                broke = reset_happened and not progressed

                use_goat_guard = (broke and gft_goat_guard and gname == "GFT" and was_funded
                                  and acc["_gg_triggered_count"] < 1)
                if use_goat_guard:
                    acc["_gg_triggered_count"] += 1
                    acc["_gg_split_until"] = now + GOAT_GUARD_SPLIT_DAYS * 86400
                    acc["phase"] = "funded"
                    state["gft_soft_breaches"] += 1
                elif broke:
                    state["total_breaks"] += 1
                    if use_payout_cycle and acc["pending_payout"] != 0.0:
                        forfeited = max(0.0, acc["pending_payout"])
                        bucket = state["forfeited_post"] if fleet_unlocked else state["forfeited_pre"]
                        events = state["forfeit_events_post"] if fleet_unlocked else state["forfeit_events_pre"]
                        if forfeited > 0:
                            bucket[gname] += forfeited
                            events[gname] += 1
                        acc["pending_payout"] = 0.0
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
                        if downgrade_active() and gname == ei.STARTER:
                            cost = acc["base_cost"]
                        else:
                            cost = ei.price_for(format_by_firm[gname], acc["palier"])
                            if ftmo_discount and gname == "FTMO":
                                cost *= FTMO_DISCOUNT_FACTOR
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

    pre = full_structure_month is None or full_structure_month > 12
    result = {"final_net_split": combined_net(), "is_paid_cum": state["is_paid_cum"],
              "year1_net_split": year1_net_split, "total_breaks": state["total_breaks"], "pre_deblocage": pre,
              "total_opens": state["total_opens"], "breaks_within_30d": state["breaks_within_30d"],
              "breaks_within_60d": state["breaks_within_60d"], "blueberry_resets_used": state["blueberry_resets_used"],
              "reserve_min_6mo": reserve_min_6mo if reserve_min_6mo != float("inf") else 0.0,
              "final_reserve": state["reserve"], "hit_ceiling": state["hit_ceiling"],
              "swap_evictions": state["swap_evictions"], "swap_admits": state["swap_admits"]}
    for g in PAYOUT_CYCLE_FIRMS:
        result[f"forfeited_pre_{g}"] = state["forfeited_pre"][g]
        result[f"forfeited_post_{g}"] = state["forfeited_post"][g]
        result[f"forfeit_events_pre_{g}"] = state["forfeit_events_pre"][g]
        result[f"forfeit_events_post_{g}"] = state["forfeit_events_post"][g]
    return result


def run_propagated(pop, market_data, excluded_map, ceiling, seq_grouped, format_by_firm, emergency,
                    eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult, n_sims, seed,
                    b_entry_frac=None, b_reduction=None, pre_unlock_only=False,
                    ftmo_discount=False, gft_goat_guard=False, payout_cycle=False,
                    position_mode="baseline", swap_x=None):
    import random
    rng_wr = random.Random(seed)
    rng_boot = random.Random(seed + 1)
    rows = []
    for _ in range(n_sims):
        wr_draw = rng_wr.betavariate(ei.ALPHA_POST, ei.BETA_POST)
        trades, slot_arrivals = build_flexible_population_with_rr(pop, wr_draw, 1.0, False, random.Random(rng_boot.random()))
        block_seconds = 2 * 30 * DAY_SECONDS
        blocks = build_blocks(trades, slot_arrivals, block_seconds)
        target_duration = slot_arrivals[-1]
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot, target_duration)
        order = list(range(len(raw_trades)))
        res = run_one(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, seq_grouped, format_by_firm,
                      emergency, eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult,
                      b_entry_frac=b_entry_frac, b_reduction=b_reduction, pre_unlock_only=pre_unlock_only,
                      ftmo_discount=ftmo_discount, gft_goat_guard=gft_goat_guard, payout_cycle=payout_cycle,
                      position_mode=position_mode, swap_x=swap_x)
        rows.append(res)
    return pd.DataFrame(rows)


def summarize(df, label, ceiling):
    net = df["final_net_split"] - df["is_paid_cum"]
    year1_neg = df["year1_net_split"] < 0
    pre_mask = df["pre_deblocage"]
    n_pre = (year1_neg & pre_mask).sum()
    n_post = (year1_neg & ~pre_mask).sum()
    solde_neg_mask = net < 0
    hc_mask = df["hit_ceiling"]
    row = dict(config=label, ceiling=ceiling, n=len(df),
               profit_moyen=net.mean(), profit_median=net.median(),
               solde_negatif_annee4=solde_neg_mask.mean() * 100,
               hit_ceiling_pct=hc_mask.mean() * 100,
               annee1_neg=year1_neg.mean() * 100, annee1_neg_pre=n_pre / len(df) * 100,
               annee1_neg_post=n_post / len(df) * 100)
    if "swap_admits" in df.columns:
        row["swap_admits_moy"] = df["swap_admits"].mean()
        row["swap_evictions_moy"] = df["swap_evictions"].mean()
    return row


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    ceilings_arg = [float(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [1000.0, 3000.0]

    t_start = time.time()

    section1_replay()

    print("\n" + "=" * 70)
    print(f"SECTIONS 2-3 -- moteur de flotte complet, n={n_sims}, plafonds={ceilings_arg}")
    print("=" * 70)

    pop = build_population_with_trailing("fixed", 0.15, min_rr=MIN_RR, verbose=False)
    print(f"[verif] population construite (RR>={MIN_RR}) : {len(pop)} trades")
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)
    seq = ei.seq_grouped_multi(1000, 15000, 25000, 25000)
    config = ei.CONFIG_REF

    common_kwargs = dict(emergency=ei.DEFAULT_EMERGENCY, eval_risk=EVAL_RISK, fleet_risk=FLEET_RISK,
                          gft_eval_risk=GFT_EVAL_RISK, reserve_share=ei.FINAL_RESERVE_SHARE,
                          extra_threshold_mult=ei.EXTRA_THRESHOLD_MULT, n_sims=n_sims, seed=9999,
                          b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True,
                          ftmo_discount=True, gft_goat_guard=True, payout_cycle=True)

    all_rows = []

    for ceiling in ceilings_arg:
        # --- REFERENCE (cap=3, baseline, Run C rr135/corr080) ---
        t0 = time.time()
        assert eng.MAX_POSITIONS == 3
        df_ref = run_propagated(pop, market_data, excluded_map, ceiling, seq, config, position_mode="baseline",
                                 **common_kwargs)
        row = summarize(df_ref, "REF_cap3 (RunC/F rr135corr080)", ceiling)
        all_rows.append(row)
        print(f"[REF cap=3  plafond={ceiling:.0f}$] profit_moy={row['profit_moyen']:+,.0f}$ "
              f"profit_med={row['profit_median']:+,.0f}$ solde_neg={row['solde_negatif_annee4']:.2f}% "
              f"hit_ceiling={row['hit_ceiling_pct']:.2f}% annee1<0={row['annee1_neg']:.2f}% ({time.time()-t0:.0f}s)")

        # --- SECTION 2 : cap=4, sans logique de coupe ---
        t0 = time.time()
        eng.MAX_POSITIONS = 4
        try:
            df_cap4 = run_propagated(pop, market_data, excluded_map, ceiling, seq, config, position_mode="baseline",
                                      **common_kwargs)
        finally:
            eng.MAX_POSITIONS = 3
        row = summarize(df_cap4, "SECTION2_cap4", ceiling)
        all_rows.append(row)
        print(f"[cap=4      plafond={ceiling:.0f}$] profit_moy={row['profit_moyen']:+,.0f}$ "
              f"profit_med={row['profit_median']:+,.0f}$ solde_neg={row['solde_negatif_annee4']:.2f}% "
              f"hit_ceiling={row['hit_ceiling_pct']:.2f}% annee1<0={row['annee1_neg']:.2f}% ({time.time()-t0:.0f}s)")

        # --- SECTION 3 : swap (cap reste 3), X = 1.5 / 2 / 3 ---
        for swap_x in (1.5, 2.0, 3.0):
            t0 = time.time()
            df_swap = run_propagated(pop, market_data, excluded_map, ceiling, seq, config,
                                      position_mode="swap", swap_x=swap_x, **common_kwargs)
            row = summarize(df_swap, f"SECTION3_swap_x{swap_x}", ceiling)
            all_rows.append(row)
            print(f"[swap x={swap_x:.1f}  plafond={ceiling:.0f}$] profit_moy={row['profit_moyen']:+,.0f}$ "
                  f"profit_med={row['profit_median']:+,.0f}$ solde_neg={row['solde_negatif_annee4']:.2f}% "
                  f"hit_ceiling={row['hit_ceiling_pct']:.2f}% annee1<0={row['annee1_neg']:.2f}% "
                  f"evictions_moy={row.get('swap_evictions_moy', float('nan')):.2f} ({time.time()-t0:.0f}s)")

        pd.DataFrame(all_rows).to_csv(f"chantier_position_cap_n{n_sims}_2026-08-15.csv", index=False)

    print(f"\nTermine en {time.time()-t_start:.0f}s.")
