"""
Suite du split_tax_model.py (07/08) : 2 volets.

PARTIE A -- stress-test cible sur la fenetre du 1er solde d'IS (fin annee 1,
~105j apres cloture, soit ~1an+3,5mois apres le lancement) : c'est le moment
ou la reserve poolee est structurellement la plus mince alors qu'un premier
gros paiement fiscal tombe. L'agregat "0/6400 breach sur l'horizon complet"
du script precedent dilue cette fenetre (les annees 2-4, ou la reserve est
enorme, noient le signal). Ce script isole l'etat exact (reserve, plafond
personnel deja consomme) au moment precis du 1er solde, sur distribution
complete (pas juste le pire cas), puis rejoue un stress "what-if" : une/deux
casses de compte reelles (couts reels du projet, pas inventes) survenant
dans les +/-30 jours autour de cette date, en plus du solde deja du.

PARTIE B -- transition vers une structure holding (SASU mere / SASU fille
trading), declenchee par un SEUIL DE RESERVE (jamais un delai calendaire,
coherent avec la logique deja validee pour FXIFY/Ment Funding), teste a
5x/10x/20x le plafond de tresorerie personnelle. Une fois active, la fille
distribue -- au meme rythme que le scenario "retraits reguliers" deja teste
(50%/an) -- vers la holding au lieu de la personne. Regime mere-fille :
quote-part de 5% du dividende recu par la holding reintegree a SON resultat
imposable, taxee au bareme IS normal (PAS 1,5% forfaitaire -- calcule via le
meme compute_is() que la fille, sur le montant reel de la quote-part, qui
peut depasser le seuil 42500 les grosses annees). Deux sous-scenarios :
  a) capitalisation pure : la holding ne redistribue rien, l'argent reste
     "capital disponible" pour reinvestissement groupe.
  b) distribution : la holding redistribue ensuite a la personne, PFU 30%
     sur ce dernier etage.
Compare aux memes baselines DEJA calculees dans split_tax_model.py
(reserve_max = "sans holding, capitalisation" ; retraits_reguliers = "sans
holding, distribution directe") -- pas de reexecution de ces deux-la.

Reserve legale non modelisee ici (SASU n'a pas d'obligation de reserve legale
comme la SA, donc omise a raison -- mais a confirmer par l'expert-comptable).
Conditions du regime mere-fille (detention >=5%, conservation >=2 ans) NON
verifiees juridiquement ici -- flag explicite dans le livrable.
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
from split_tax_model import (compute_is, split_rate_for, handle_cost_hybrid, process_pending,
                              Q_OFFSETS_DAYS, SOLDE_OFFSET_DAYS, IS_THRESHOLD_ACOMPTE, ACOMPTE_FRACTION,
                              PFU_RATE)

POP_CONSTRUCT_SEED = 123
DAY_SECONDS = 86400
YEAR_SECONDS = 365.25 * DAY_SECONDS
MONTH_SECONDS = DAYS_PER_MONTH * DAY_SECONDS
DIVIDEND_FRAC_ACTIVE = 0.5  # meme cadence que "retraits reguliers" du script precedent

# couts REELS de rachat/challenge utilises pour le stress-test Partie A (cf.
# point2_sequencing_engine.GROUP_DEFS + POST_SUMMER_COST_REAL) -- pas inventes
STRESS_SINGLE_COSTS = {"Blueberry_50k": 333, "FTMO/GFT/FundedNext_50k": 333, "Fivers_100k": 545}
STRESS_DOUBLE_COMBOS = {
    "2x growth (333+333)": 333 + 333,
    "growth+Fivers (333+545)": 333 + 545,
    "3 comptes correles (333+333+545)": 333 + 333 + 545,
}


def run_one(trades, slot_arrivals, market_data, excluded_map, order, ceiling, dividend_frac,
            holding_threshold_mult=None, holding_distributes=False, capture_solde_window_days=30):
    """holding_threshold_mult=None -> pas de holding (comportement identique a
    split_tax_model.run_one). Sinon : bascule holding declenchee quand
    reserve >= holding_threshold_mult * ceiling (evenementiel)."""
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
             "full_structure_month": None, "is_paid_cum": 0.0,
             "holding_active": False, "holding_activation_time": None,
             "capital_disponible_holding": 0.0, "dividendes_net_personne_cum": 0.0,
             "friction_fiscale_cum": 0.0}
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
            net_pnl = pnl * split_rate_for(acc) if pnl > 0 else pnl
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

    fy_start_net = {0: 0.0}
    is_by_year = {}
    acomptes_paid_by_year = {}
    next_fy_to_close = 0
    tax_events = []
    solde_snapshot = {}

    def close_fiscal_year(y, now_close):
        profit_y = combined_net() - fy_start_net.get(y, 0.0)
        is_y = compute_is(profit_y)
        is_by_year[y] = is_y
        fy_start_net[y + 1] = combined_net()
        acomptes_y = acomptes_paid_by_year.get(y, 0.0)
        solde = max(0.0, is_y - acomptes_y)
        solde_time = (y + 1) * YEAR_SECONDS + SOLDE_OFFSET_DAYS * DAY_SECONDS
        label = f"solde_annee{y}"
        tax_events.append((solde_time, solde, label))
        if dividend_frac > 0 or holding_threshold_mult is not None:
            after_tax = max(0.0, profit_y - is_y)
            eff_frac = dividend_frac if holding_threshold_mult is None else (DIVIDEND_FRAC_ACTIVE if state["holding_active"] else 0.0)
            target = after_tax * eff_frac
            if target > 0:
                tax_events.append((solde_time, -target, f"dividende_annee{y}"))
        if is_y > IS_THRESHOLD_ACOMPTE:
            for q_off in Q_OFFSETS_DAYS:
                t_acompte = (y + 1) * YEAR_SECONDS + q_off * DAY_SECONDS
                amt = ACOMPTE_FRACTION * is_y
                tax_events.append((t_acompte, amt, f"acompte_annee{y+1}"))
                acomptes_paid_by_year[y + 1] = acomptes_paid_by_year.get(y + 1, 0.0) + amt
        tax_events.sort(key=lambda e: e[0])

    def handle_tax_payment(amount, now):
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
            state["real_cash_paid"] += overflow

    def distribute(available, now):
        """available = montant reellement preleve sur la reserve. Route vers
        la personne directement (pas de holding) ou vers la holding (regime
        mere-fille) selon l'etat courant."""
        if holding_threshold_mult is None or not state["holding_active"]:
            state["dividendes_net_personne_cum"] += available * (1 - PFU_RATE)
            state["friction_fiscale_cum"] += available * PFU_RATE
        else:
            quote_part = 0.05 * available
            holding_is = compute_is(quote_part)
            net_to_holding = available - holding_is
            state["friction_fiscale_cum"] += holding_is
            if holding_distributes:
                pfu = net_to_holding * PFU_RATE
                state["dividendes_net_personne_cum"] += net_to_holding - pfu
                state["friction_fiscale_cum"] += pfu
            else:
                state["capital_disponible_holding"] += net_to_holding

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]

        if holding_threshold_mult is not None and not state["holding_active"] and state["reserve"] >= holding_threshold_mult * ceiling:
            state["holding_active"] = True
            state["holding_activation_time"] = now

        while (next_fy_to_close + 1) * YEAR_SECONDS <= now:
            close_fiscal_year(next_fy_to_close, now)
            next_fy_to_close += 1

        i = 0
        while i < len(tax_events):
            t_ev, amt, label = tax_events[i]
            if t_ev > now:
                i += 1
                continue
            tax_events.pop(i)
            if label.startswith("solde_annee0") and not solde_snapshot:
                active_costs = []
                for gname, accs in accounts_by_group.items():
                    for a in accs:
                        if a["active"]:
                            active_costs.append(a["cost"])
                solde_snapshot["t"] = t_ev
                solde_snapshot["reserve_before"] = state["reserve"]
                solde_snapshot["real_cash_paid_before"] = state["real_cash_paid"]
                solde_snapshot["room_before"] = max(0.0, ceiling - state["real_cash_paid"])
                solde_snapshot["is_due"] = amt
                solde_snapshot["combined_before_shortfall"] = state["reserve"] + solde_snapshot["room_before"] - amt
                solde_snapshot["active_account_costs"] = sorted(active_costs)
            if amt >= 0:
                handle_tax_payment(amt, now)
                state["is_paid_cum"] += amt
            else:
                div_target = -amt
                available = min(state["reserve"], div_target)
                if available > 0:
                    state["reserve"] -= available
                    distribute(available, now)

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
    return {
        "final_net_company": final_net,
        "real_cash_paid": state["real_cash_paid"],
        "is_paid_cum": state["is_paid_cum"],
        "capital_disponible_holding": state["capital_disponible_holding"],
        "dividendes_net_personne_cum": state["dividendes_net_personne_cum"],
        "friction_fiscale_cum": state["friction_fiscale_cum"],
        "holding_activation_month": (state["holding_activation_time"] / MONTH_SECONDS) if state["holding_activation_time"] else None,
        "solde_reserve_before": solde_snapshot.get("reserve_before"),
        "solde_room_before": solde_snapshot.get("room_before"),
        "solde_is_due": solde_snapshot.get("is_due"),
        "solde_combined_before_shortfall": solde_snapshot.get("combined_before_shortfall"),
        "solde_min_active_cost": min(solde_snapshot["active_account_costs"]) if solde_snapshot.get("active_account_costs") else None,
    }


def run_variant(trades, slot_arrivals, blocks, block_seconds, target_duration, ceiling, dividend_frac,
                holding_threshold_mult, holding_distributes, n_sims, seed):
    rng = random.Random(seed)
    rows = []
    for _ in range(n_sims):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, target_duration)
        order = list(range(len(raw_trades)))
        rows.append(run_one(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, dividend_frac,
                             holding_threshold_mult, holding_distributes))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    import sys
    t_start = time.time()
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    ceilings = [float(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [1000.0, 3000.0]

    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

    all_rows_a = []
    all_rows_b = []
    for wr_label, wr_target in [("40.09%_reel", None), ("37.66%_P10bayesien", 0.3766)]:
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_target, 1.0, False, random.Random(POP_CONSTRUCT_SEED))
        total_h, marks, block_s, blocks = build_ctx(trades, slot_arrivals)
        print(f"\n{'='*100}\nWINRATE {wr_label}\n{'='*100}")

        for ceiling in ceilings:
            # ---- PARTIE A : snapshot solde annee0, pas de holding ----
            t0 = time.time()
            df = run_variant(trades, slot_arrivals, blocks, block_s, total_h, ceiling, 0.0,
                              None, False, n_sims=n_sims, seed=42)
            df.to_csv(f"year1_solde_snapshot_{wr_label.split('%')[0].replace('.', '_')}_ceiling{int(ceiling)}.csv", index=False)
            snap = df.dropna(subset=["solde_reserve_before"])
            print(f"[Partie A][ceiling={ceiling:.0f}$] n snapshots valides={len(snap)}/{n_sims} ({time.time()-t0:.0f}s)")
            for pct in [10, 25, 50, 75, 90, 95, 99, 100]:
                r = np.percentile(snap["solde_reserve_before"], pct)
                room = np.percentile(snap["solde_room_before"], pct)
                due = np.percentile(snap["solde_is_due"], pct)
                comb = np.percentile(snap["solde_combined_before_shortfall"], pct)
                print(f"    P{pct:3d} : reserve={r:9,.0f}$ | room_plafond={room:7,.0f}$ | IS_du={due:9,.0f}$ | "
                      f"marge_apres_solde={comb:10,.0f}$")
            for label, cost in {**STRESS_SINGLE_COSTS, **STRESS_DOUBLE_COMBOS}.items():
                p_insuff = (snap["solde_combined_before_shortfall"] < cost).mean() * 100
                amt_if_insuff = (cost - snap.loc[snap["solde_combined_before_shortfall"] < cost, "solde_combined_before_shortfall"]).mean() if p_insuff > 0 else 0.0
                print(f"    Stress '{label}' ({cost}$) : P(insuffisant)={p_insuff:.2f}% | depassement moyen si insuffisant={amt_if_insuff:,.0f}$")
                all_rows_a.append(dict(winrate=wr_label, ceiling=ceiling, stress_label=label, stress_cost=cost,
                                        p_insuffisant_pct=p_insuff, depassement_moyen=amt_if_insuff,
                                        n=len(snap)))

            # ---- PARTIE B : holding a 5x/10x/20x (demande initiale) + 100x/500x/2000x
            # (ajoute -- avec la reserve qui grossit tres vite face au plafond perso de
            # 1000-3000$, 5x/10x/20x se declenchent en pratique des le mois ~1,5-2 (cf.
            # constat imprime plus bas) : quasi sans effet discriminant. Les seuils plus
            # larges permettent de voir un vrai etalement dans le temps.
            for mult in (5, 10, 20, 100, 500, 2000):
                for dist_label, holding_distributes in [("capitalisation", False), ("distribution", True)]:
                    t0 = time.time()
                    dfh = run_variant(trades, slot_arrivals, blocks, block_s, total_h, ceiling, 0.0,
                                       mult, holding_distributes, n_sims=n_sims, seed=42)
                    row = dict(
                        winrate=wr_label, ceiling=ceiling, threshold_mult=mult, structure=dist_label,
                        profit_final_company_mean=dfh["final_net_company"].mean(),
                        capital_disponible_holding_mean=dfh["capital_disponible_holding"].mean(),
                        dividendes_net_personne_mean=dfh["dividendes_net_personne_cum"].mean(),
                        friction_fiscale_mean=dfh["friction_fiscale_cum"].mean(),
                        holding_activation_month_median=dfh["holding_activation_month"].median(),
                        p_holding_never_active_pct=dfh["holding_activation_month"].isna().mean() * 100,
                    )
                    all_rows_b.append(row)
                    print(f"[Partie B][ceiling={ceiling:.0f}$][seuil={mult}x][{dist_label}] "
                          f"activation mediane mois={row['holding_activation_month_median']} | "
                          f"capital holding (moy)={row['capital_disponible_holding_mean']:,.0f}$ | "
                          f"div. net perso (moy)={row['dividendes_net_personne_mean']:,.0f}$ | "
                          f"friction fiscale cum (moy)={row['friction_fiscale_mean']:,.0f}$ | "
                          f"P(jamais active)={row['p_holding_never_active_pct']:.1f}% ({time.time()-t0:.0f}s)")

            pd.DataFrame(all_rows_a).to_csv("year1_solde_stress_summary.csv", index=False)
            pd.DataFrame(all_rows_b).to_csv("holding_transition_summary.csv", index=False)

    pd.DataFrame(all_rows_a).to_csv("year1_solde_stress_summary.csv", index=False)
    pd.DataFrame(all_rows_b).to_csv("holding_transition_summary.csv", index=False)
    print(f"\nTermine en {time.time()-t_start:.0f}s.")
