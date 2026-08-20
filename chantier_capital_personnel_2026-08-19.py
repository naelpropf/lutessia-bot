"""
Chantier "viabilite capital personnel" (hors prop firm), session 2026-08-19.

Exploration de curiosite (pas un chantier d'optimisation) : la strategie
(edge Lutessia + gestion de position) appliquee en trading direct sur
capital personnel ~500k$ de reinvestissement futur, SANS mecanique prop
firm (palier, phase challenge/funded, DD journalier reglementaire, split,
cout de challenge -- tout ca est hors sujet ici et volontairement absent).

Briques reutilisees TELLES QUELLES (citations exactes) :
- Population A (RR>=1.35, indices inclus depuis le correctif forex-only du
  08/18) + trailing stop post-TP2 0.15xSL :
  trailing_payoff_population.build_population_with_trailing("fixed", 0.15,
  min_rr=1.35) -> trailing_payoff_population.build_trades_trailing(pop)
  (trailing_payoff_population.py:36-92). r_trailing/outcome_r vaut deja
  -1.0 pour les perdants (herite de r_realiste, tp2_realistic_payoff.py).
- Blocage correlation + regle JPY-JPY : monte_carlo_simulation.
  precompute_correlation_pairs (monte_carlo_simulation.py:74-86), is_jpy
  (scaling_simulation.py:78-79), MAX_POSITIONS=3 / CORR_THRESHOLD=0.80
  (scaling_simulation.py:46-47), correlation_matrix.csv (etendu 19x19 aux
  indices le 08/18 par extend_correlation_matrix_indices_2026-08-18.py).
- any-RR (routage RR planifie au conflit de correlation a 1 occupant) :
  logique portee de process_trade_corr_swap_rr
  (chantier_correlation_swap_2026-08-16.py:298-341), reecrite ici pour un
  compte unique en compounding (le fichier source est fleet/palier-only,
  pas importable tel quel).
- Sizing RR eleve : CORRECTION -- §2.34 (rr_tp1 lineaire x1.30) est REJETE
  en contexte fleet, ce n'est PAS le mecanisme a reprendre. Le mecanisme
  reellement ADOPTE (registre_strategie_trading.md:1651-1806, §2.35,
  "variante A" -- routage any-RR inchange sur rr_tp1, sizing seul module
  separement) est un SEUIL simple sur rr_tp2 (pas rr_tp1, pas continu) :
  rr_tp2>8 -> multiplicateur x1.6, sinon x1.0
  (chantier_rrtp2_sizing_2026-08-16.py, "3000$/5000$ : DOMINANCE STRICTE
  confirmee n=600 (+15,9%)", "960$/1000$ : arbitrage, hit_ceiling double").
  §2.35 est verifie/confirme (anti-lookahead, stabilite 6/6 sous-periodes,
  chevauchement any-RR 10.4%) mais PAS FORMELLEMENT ADOPTE dans la
  reference officielle §1.8 -- meme statut "valide, decision utilisateur
  en attente" qu'any-RR, teste ici comme 3e interrupteur independant pour
  la meme raison.
- Capacite/liquidite forex : scaling_simulation.feasible_risk_pct
  (scaling_simulation.py:121-147) + load_market_data (forex_market_data.
  json, 14 paires). N'existe PAS pour les indices (aucune entree dans
  forex_market_data.json) -- verifie par grep, cf. Etape 2 ci-dessous :
  traite separement (pas de clampage de capacite applique aux indices
  dans le moteur, sanity-check manuel a la place).
- Bootstrap par blocs 2 mois : build_blocks (real_cash_risk_year1_block_
  bootstrap.py:35-49) + build_full_block_bootstrap_sequence
  (reference_metrics_final.py:55-64), BLOCK_MONTHS=2 (convention projet).
  Horizon = duree reelle de la population (slot_arrivals[-1], meme
  convention que reference_metrics_final.py:198-199), pas une constante
  arbitraire.

Cout d'execution (Etape 1) -- DEUX composantes distinctes, appliquees a
CHAQUE trade (gagnant ou perdant, simplification volontaire vs la formule
projet qui ne l'applique qu'aux sorties stop -- documente ci-dessous) :
  1. Slippage force (forex uniquement) : -0.939 pip moyenne mesuree
     Dukascopy (n=628 forex, chantier_b_ev1_slippage_trailing_2026-08-19.
     py:124-131 pour la formule slip_r = pips*pip_size/sl_distance).
     AUCUNE mesure Dukascopy equivalente pour les indices -- gap
     documente, pas comble par une extrapolation forex.
  2. Spread retail standard assume (PAS mesure, ordre de grandeur
     documente) : 1.0 pip forex (compatible ECN/standard retail courant),
     1.5 point indices (CFD retail typique DAX40/NASDAQ100/S&P500).
Simplification assumee : cout applique en R a CHAQUE trade (pas seulement
aux sorties stop comme dans chantier_b_ev1) -- un spread/slippage se paie
a l'entree ET a la sortie sur un round-trip reel, quel que soit le sens de
sortie ; appliquer le cout uniquement aux pertes sous-estimerait le cout
reel d'un gagnant. Direction JAMAIS favorable au resultat (toujours
soustrait), donc conservateur.

Elements prop-firm explicitement IGNORES ici (hors sujet capital
personnel, cf. prompt utilisateur) : palier de scaling, DD journalier
reglementaire, phases challenge/funded, cout de challenge, split 80/20,
plafond de capital combine par firm, routage multi-comptes de flotte.
"""
import random
import time

import numpy as np
import pandas as pd

from trailing_payoff_population import build_population_with_trailing, build_trades_trailing
from scaling_simulation import is_jpy, CORR_THRESHOLD, MAX_POSITIONS, load_market_data, feasible_risk_pct
from monte_carlo_simulation import precompute_correlation_pairs
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence

DAY_SECONDS = 86400
YEAR_SECONDS = 365.25 * DAY_SECONDS
BLOCK_MONTHS = 2
BLOCK_SECONDS = BLOCK_MONTHS * DAYS_PER_MONTH * DAY_SECONDS

# ---------------------------------------------------------------------------
# Cout d'execution -- ordres de grandeur documentes (pas mesures pour la
# partie spread/commission, cf. docstring).
# ---------------------------------------------------------------------------
SLIPPAGE_PIPS_FX = 0.939      # mesure Dukascopy, n=628 forex
SPREAD_PIPS_FX = 1.0          # hypothese retail standard (ordre de grandeur)
SPREAD_POINTS_INDEX = 1.5     # hypothese retail CFD indices (ordre de grandeur)

# Memes labels que scraper.py:94 (TARGET_INDEX_KEYWORDS) -- tickers indices
# Lutessia partagent ces sous-chaines.
INDEX_KEYWORDS = ("DAX40", "DJ30", "NASDAQ100", "S&P500", "FTSE100")

# Sizing RR eleve, §2.35 (ADOPTE, seuil simple sur rr_tp2, PAS rr_tp1) --
# registre_strategie_trading.md:1651-1806, chantier_rrtp2_sizing_2026-08-16.py
RR_TP2_SIZING_THRESHOLD, RR_TP2_SIZING_MULT = 8.0, 1.6

RUIN_FRACTION = 0.50  # seuil de ruine : capital <= 50% du capital initial


def is_index_ticker(ticker):
    upper = ticker.upper()
    return any(k in upper for k in INDEX_KEYWORDS)


def pip_size(ticker):
    return 0.01 if is_jpy(ticker) else 0.0001


def size_func_rrtp2(rr_tp2):
    """§2.35 : seuil simple, PAS de fonction continue (voir §2.36, tout
    sizing gradue/continu sur rr_tp2 a ete REJETE -- seul le seuil >8
    plat est retenu)."""
    return RR_TP2_SIZING_MULT if rr_tp2 > RR_TP2_SIZING_THRESHOLD else 1.0


def apply_execution_costs(trades):
    """Cout deterministe (independant du capital/risque) : soustrait de
    outcome_r une fois pour toutes, avant Monte Carlo -- le cout en R est
    une fraction fixe de sl_distance, ne depend pas de la taille de
    position choisie ensuite."""
    adjusted = []
    n_missing_sl = 0
    for t in trades:
        sl = t["sl_distance"]
        if sl <= 0:
            n_missing_sl += 1
            adjusted.append(dict(t))
            continue
        if is_index_ticker(t["ticker"]):
            cost_price = SPREAD_POINTS_INDEX
        else:
            cost_price = (SLIPPAGE_PIPS_FX + SPREAD_PIPS_FX) * pip_size(t["ticker"])
        cost_r = cost_price / sl
        t2 = dict(t)
        t2["outcome_r"] = t["outcome_r"] - cost_r
        adjusted.append(t2)
    if n_missing_sl:
        print(f"[avertissement] {n_missing_sl} trades a sl_distance<=0, cout non applique.")
    return adjusted


def load_population_and_trades():
    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.35, verbose=True)
    sub, trades, slot_arrivals = build_trades_trailing(pop)
    for i, t in enumerate(trades):
        t["rr_tp1"] = float(sub["rr_tp1"].iloc[i])
        t["rr_tp2"] = float(sub["rr_tp2"].iloc[i])
    trades = apply_execution_costs(trades)
    return sub, trades, slot_arrivals


def build_correlation_context(trades):
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(set(t["ticker"] for t in trades))
    missing = [t for t in tickers if t not in corr_matrix.index]
    if missing:
        raise RuntimeError(f"tickers absents de correlation_matrix.csv : {missing}")
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)
    return market_data, excluded_map


# ---------------------------------------------------------------------------
# Moteur compte unique, compounding pur
# ---------------------------------------------------------------------------

def simulate_account(trades, slot_arrivals, risk_pct, use_any_rr, use_rr_sizing,
                      initial_capital, excluded_map, market_data):
    capital = initial_capital
    open_positions = []   # (ticker, close_time)
    open_meta_rr = []     # {"ticker","close_time","rr"} -- seulement si use_any_rr
    peak = capital
    max_dd_pct = 0.0
    ruined = False
    ruin_threshold = initial_capital * RUIN_FRACTION
    capacity_reduced_count = 0
    trades_taken = 0

    for trade, now in zip(trades, slot_arrivals):
        close_time = now + trade["hold_seconds"]
        open_positions = [(t, c) for (t, c) in open_positions if c > now]
        if use_any_rr:
            open_meta_rr = [m for m in open_meta_rr if m["close_time"] > now]

        ticker = trade["ticker"]
        rr = trade["rr_tp1"]        # routage any-RR : rr_tp1 (§2.33, "variante A" de §2.35)
        rr_tp2 = trade["rr_tp2"]    # sizing : rr_tp2>8 (§2.35)

        if len(open_positions) >= MAX_POSITIONS:
            continue

        blocked = any(t in excluded_map[ticker] for (t, _) in open_positions)
        admitted = not blocked

        if blocked and use_any_rr:
            conflicts = [m for m in open_meta_rr if m["ticker"] in excluded_map[ticker]]
            if len(conflicts) == 1 and rr > conflicts[0]["rr"]:
                occ = conflicts[0]
                open_positions = [p for p in open_positions
                                   if not (p[0] == occ["ticker"] and p[1] == occ["close_time"])]
                open_meta_rr = [m for m in open_meta_rr if m is not occ]
                admitted = True

        if not admitted:
            continue

        eff_risk_pct = risk_pct * size_func_rrtp2(rr_tp2) if use_rr_sizing else risk_pct

        if ticker in market_data:
            realized_risk_pct, was_reduced = feasible_risk_pct(
                ticker, trade["sl_distance"], capital, eff_risk_pct, market_data)
            eff_risk_pct = realized_risk_pct
            if was_reduced:
                capacity_reduced_count += 1
        # indices : pas de clampage de capacite (aucune entree market_data,
        # cf. docstring -- traite separement en Etape 2).

        risk_amount = eff_risk_pct / 100 * capital
        pnl = trade["outcome_r"] * risk_amount
        capital += pnl
        trades_taken += 1

        open_positions.append((ticker, close_time))
        if use_any_rr:
            open_meta_rr.append({"ticker": ticker, "close_time": close_time, "rr": rr})

        peak = max(peak, capital)
        dd_pct = (peak - capital) / peak * 100 if peak > 0 else 0.0
        max_dd_pct = max(max_dd_pct, dd_pct)
        if capital <= ruin_threshold:
            ruined = True

    return dict(final_capital=capital, max_dd_pct=max_dd_pct, ruined=ruined,
                trades_taken=trades_taken, capacity_reduced_count=capacity_reduced_count)


def run_monte_carlo(trades, slot_arrivals, blocks, risk_pct, use_any_rr, use_rr_sizing,
                     initial_capital, excluded_map, market_data, n_sims, horizon_seconds, seed):
    rng = random.Random(seed)
    horizon_years = horizon_seconds / YEAR_SECONDS
    cagrs, dds, ruins, calmars = [], [], [], []
    capacity_hits = 0
    for _ in range(n_sims):
        synth_trades, synth_slots = build_full_block_bootstrap_sequence(
            blocks, BLOCK_SECONDS, rng, horizon_seconds)
        res = simulate_account(synth_trades, synth_slots, risk_pct, use_any_rr, use_rr_sizing,
                                initial_capital, excluded_map, market_data)
        cagr = (res["final_capital"] / initial_capital) ** (1.0 / horizon_years) - 1.0
        cagrs.append(cagr)
        dds.append(res["max_dd_pct"])
        ruins.append(res["ruined"])
        calmars.append(cagr / (res["max_dd_pct"] / 100.0) if res["max_dd_pct"] > 0 else np.nan)
        if res["capacity_reduced_count"] > 0:
            capacity_hits += 1
    return dict(
        cagr_p10=np.percentile(cagrs, 10), cagr_p50=np.percentile(cagrs, 50), cagr_p90=np.percentile(cagrs, 90),
        dd_p10=np.percentile(dds, 10), dd_p50=np.percentile(dds, 50), dd_p90=np.percentile(dds, 90),
        ruin_pct=100.0 * sum(ruins) / n_sims,
        calmar_p50=np.nanpercentile(calmars, 50),
        capacity_hit_pct=100.0 * capacity_hits / n_sims,
    )


# ---------------------------------------------------------------------------
# Etape 2 -- verification de capacite/liquidite (forex : mecanisme reel via
# feasible_risk_pct ; indices : pas de market_data, sanity-check manuel).
# ---------------------------------------------------------------------------

def capacity_check(trades, market_data, capitals=(250_000, 500_000, 1_000_000), risk_pcts=(0.01, 0.02, 0.03)):
    print("\n=== ETAPE 2 : verification de capacite ===")
    fx_tickers = sorted(set(t["ticker"] for t in trades if t["ticker"] in market_data))
    idx_tickers = sorted(set(t["ticker"] for t in trades if t["ticker"] not in market_data))
    print(f"Tickers forex avec market_data (capacite reelle testable) : {len(fx_tickers)}")
    print(f"Tickers indices SANS market_data (aucune clef de capacite dans forex_market_data.json) : {idx_tickers}")

    print("\n-- Forex : feasible_risk_pct reel, was_reduced = capacite/marge a bride le risque cible --")
    for capital in capitals:
        for risk_pct in risk_pcts:
            n_reduced, n_total = 0, 0
            for t in trades:
                if t["ticker"] not in market_data:
                    continue
                n_total += 1
                _, was_reduced = feasible_risk_pct(t["ticker"], t["sl_distance"], capital, risk_pct * 100, market_data)
                if was_reduced:
                    n_reduced += 1
            print(f"  capital={capital:>9,.0f}$ risque={risk_pct*100:.1f}% : "
                  f"{n_reduced}/{n_total} trades forex avec risque bride par capacite/marge "
                  f"({100*n_reduced/n_total:.1f}%)")

    print("\n-- Indices : pas de clamp integre au moteur, sanity-check manuel (ordre de grandeur) --")
    print("  Profondeur de marche des futures indiciels (E-mini S&P500/NASDAQ100, DAX40) : plusieurs")
    print("  dizaines de milliards $ de volume notionnel quotidien -- une exposition de quelques")
    print("  dizaines de milliers de $ de risque par trade (1-3% de 250k-1M$) est negligeable devant")
    print("  cette profondeur. Le CFD retail (pas le future) a une limite pratique differente : le")
    print("  plafond de LOT du broker, pas la liquidite du marche sous-jacent -- a verifier au cas par")
    print("  cas cote broker, ne peut pas etre affirme generiquement ici (cf. reponse precedente).")


# ---------------------------------------------------------------------------
# Etape 3 -- sweep risque x any-RR x rr_tp2-sizing, 3 capitaux de depart
# ---------------------------------------------------------------------------

RISK_LEVELS = (0.005, 0.01, 0.015, 0.02, 0.03)
CAPITALS = (250_000, 500_000, 1_000_000)
N_SIMS = 2000


def run_sweep(trades, slot_arrivals, blocks, excluded_map, market_data, horizon_seconds,
              n_sims=N_SIMS, seed=20260819):
    print(f"\n=== ETAPE 3 : sweep Monte Carlo ({n_sims} runs/combinaison, "
          f"horizon={horizon_seconds/YEAR_SECONDS:.2f} ans) ===")
    rows = []
    for capital in CAPITALS:
        for risk_pct in RISK_LEVELS:
            for use_any_rr in (False, True):
                for use_rr_sizing in (False, True):
                    t0 = time.time()
                    res = run_monte_carlo(trades, slot_arrivals, blocks, risk_pct * 100, use_any_rr,
                                           use_rr_sizing, capital, excluded_map, market_data, n_sims,
                                           horizon_seconds, seed)
                    res.update(capital=capital, risk_pct=risk_pct, any_rr=use_any_rr, rr_sizing=use_rr_sizing)
                    rows.append(res)
                    print(f"  capital={capital:>9,.0f}$ risque={risk_pct*100:>4.1f}% any-RR={use_any_rr!s:5} "
                          f"rr2-sizing={use_rr_sizing!s:5} | CAGR p10/p50/p90="
                          f"{res['cagr_p10']*100:+6.1f}/{res['cagr_p50']*100:+6.1f}/{res['cagr_p90']*100:+6.1f}% "
                          f"DD p50/p90={res['dd_p50']:5.1f}/{res['dd_p90']:5.1f}% "
                          f"ruine={res['ruin_pct']:5.1f}% calmar_p50={res['calmar_p50']:5.2f} "
                          f"({time.time()-t0:.0f}s)")
    return rows


if __name__ == "__main__":
    sub, trades, slot_arrivals = load_population_and_trades()
    print(f"Population : {len(trades)} trades, horizon reel = {slot_arrivals[-1] / YEAR_SECONDS:.2f} ans")
    market_data, excluded_map = build_correlation_context(trades)
    blocks = build_blocks(trades, slot_arrivals, BLOCK_SECONDS)
    print(f"{len(blocks)} blocs de {BLOCK_MONTHS} mois construits.")

    capacity_check(trades, market_data)

    horizon_seconds = slot_arrivals[-1]
    rows = run_sweep(trades, slot_arrivals, blocks, excluded_map, market_data, horizon_seconds)

    import pandas as pd
    out = pd.DataFrame(rows)
    out.to_csv("capital_personnel_sweep_2026-08-19.csv", index=False)
    print("\nResultats sauvegardes : capital_personnel_sweep_2026-08-19.csv")
