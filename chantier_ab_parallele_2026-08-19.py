"""
Chantier moteur joint A+B, Etape 2-3, session 2026-08-19. Premier moteur du
projet a faire tourner 2 comptes independants (A dedie, B dedie) en
parallele des le lancement, au lieu du pivot unique A-seul actuel.

ARCHITECTURE (Etape 2) :
- 2 comptes independants (make_acc_mf/process_trade_mf, engine_multiformat.
  py:246-390, REUTILISES SANS MODIFICATION) sur 2 flux de trades DISTINCTS
  (population A -> compte A uniquement, population B -> compte B
  uniquement) -- jamais melanges, contrairement aux scripts B existants
  qui SUBSTITUENT B a A dans la meme flotte (cf. session_handoff_2026-08-
  19.md, decision bloquante #4).
- RESERVE COMMUNE (pas separee) : reutilise le mecanisme deja interne a
  process_trade_mf (state["reserve"]/state["real_cash_paid"]/state[
  "ever_funded"], engine_multiformat.py:343-347,355-365), qui accepte deja
  un state PARTAGE entre appels sur des comptes differents -- c'est
  exactement le design "reserve poolee" deja adopte au niveau du projet
  (registre_parametres_projet.md:722, "Reserve poolee (vs par compte) :
  -27577eur cash pire-cas, plus gros levier des 3"). Retenu ici pour
  coherence avec cette decision deja validee : un trader reel n'a qu'une
  seule tresorerie personnelle, pas 2 poches etanches par strategie.
- ALIGNEMENT TEMPOREL DES 2 FLUX (le point de verification demande par le
  prompt) : build_blocks (real_cash_risk_year1_block_bootstrap.py:35-49)
  construit des blocs indexes par temps ECOULE DEPUIS LE PREMIER TRADE DE
  CETTE POPULATION -- si applique separement a A et B, le bloc n de A et
  le bloc n de B ne correspondraient PAS a la meme fenetre calendaire
  reelle (A et B n'ont pas exactement la meme date de premier trade). Ici,
  build_aligned_blocks() ancre les deux flux sur un t=0 COMMUN (le plus
  ancien des deux premiers trades), et build_joint_bootstrap_sequence()
  tire UNE SEULE sequence d'indices de bloc, appliquee IDENTIQUEMENT aux
  deux flux -- preserve la co-occurrence reelle des regimes de marche
  (un trimestre difficile qui touchait A ET B historiquement le fait a
  nouveau ensemble dans le tirage synthetique), plutot que de traiter A et
  B comme deux processus aleatoires totalement independants (ce qui
  detruirait cette correlation reelle).

CONFIG DES COMPTES :
- A = REF actuelle : Blueberry_InstantElite (engine_multiformat.py:142-
  148, phases=[] -> funded des l'ouverture), trailing 0.15x (deja la
  config de production), risque FLEET_RISK=1.90% (chantier_rr_sizing_
  2026-08-16.py:60, funded des l'ouverture donc toujours ce risque).
- B = config la plus aboutie de cette session : build_pop_B_variant(0.10)
  (trailing 0.10x, chantier_b6_montecarlo_2026-08-19.py:728-752) --
  any-RR NON applique (diagnostic seul, pas encore un mecanisme a tester
  ici), sizing rr_tp1 NON applique (REJETE en flotte, registre_strategie_
  trading.md:1581-1649 §2.34). Risque : meme convention EVAL_RISK=1.25%
  en challenge / FLEET_RISK=1.90% en funded que le reste du projet
  (chantier_rr_sizing_2026-08-16.py:60) -- PAS de recalibration B
  specifique ici (c'etait le point differe #4, ce moteur le debloque mais
  ne le resout pas dans ce chantier).
- 2 formats testes pour B (Etape 2.3) : Blueberry_InstantElite (identique
  a A, 0 risque de delai, prix 800$/25k) vs Blueberry_2StepStandard
  (engine_multiformat.py:128-133, min_days=[3,3], prix 170$/25k --
  4.7x moins cher, mais delai de financement mesure Etape 1 : p50=59j,
  p90=163j).

METRIQUES SIMPLIFIEES (a documenter clairement, PAS la cascade complete
multi-firm/staggered-unlock/tax/payout-cycle du §1.8 officiel -- premier
banc d'essai A+B, pas une regeneration de la reference officielle) :
- profit_net = (accA.total_funded_pnl + accB.total_funded_pnl) -
  state.real_cash_paid (cash reellement gagne moins cash reellement
  depense de la poche, la reserve elle-meme est un tampon interne, pas
  une depense).
- solde_negatif / annee1<0 : profit_net a l'horizon complet / a 1 an < 0.
- hit_ceiling_pct : state.reserve a un jour atteint le plafond teste
  (indicateur simple, pas un plafond dur applique -- cette version ne
  modelise pas le deblocage en cascade de nouveaux comptes au
  franchissement du plafond, hors-sujet ici : scenario a 2 comptes FIXES).
"""
import random
import time
import importlib.util

import numpy as np
import pandas as pd

from monte_carlo_simulation import precompute_correlation_pairs
from scaling_simulation import CORR_THRESHOLD
from real_cash_risk_year1_block_bootstrap import DAYS_PER_MONTH
from engine_multiformat import FORMATS, make_acc_mf, process_trade_mf
from trailing_payoff_population import build_population_with_trailing, build_trades_trailing

DAY_SECONDS = 86400
YEAR_SECONDS = 365.25 * DAY_SECONDS
BLOCK_MONTHS = 2
BLOCK_SECONDS = BLOCK_MONTHS * DAYS_PER_MONTH * DAY_SECONDS

EVAL_RISK, FLEET_RISK = 1.25, 1.90        # chantier_rr_sizing_2026-08-16.py:60
RESERVE_SHARE = 0.95                       # etape_e_fleet_integration.py:110
SPLIT_FLAT = 0.80
PALIER = 25_000
CEILINGS = [960.0, 1000.0, 3000.0, 5000.0]
HORIZON_YEARS = 4.0

_spec = importlib.util.spec_from_file_location("b6", "chantier_b6_montecarlo_2026-08-19.py")
b6 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(b6)


def trade_risk(acc):
    return EVAL_RISK if acc["phase"] == "challenge" else FLEET_RISK


def build_trades_A():
    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.35, verbose=False)
    sub, trades, slot_arrivals = build_trades_trailing(pop)
    dates = sub["date_creation"]
    return trades, dates


def build_trades_B():
    pop = b6.build_pop_B_variant(trailing_factor=0.10)
    pop = pop.sort_values("date_creation").reset_index(drop=True)
    trades = []
    for _, row in pop.iterrows():
        outcome_r = row["r_trailing"] if row["statut_final"] == "OBJECTIF ATTEINT" else -1.0
        trades.append({
            "ticker": row["ticker"],
            "outcome_r": float(outcome_r),
            "sl_distance": abs(row["prix_entree"] - row["stop_loss_init"]),
            "hold_seconds": (row["resolution_time_est"] - row["date_creation"]).total_seconds(),
        })
    return trades, pop["date_creation"]


def build_aligned_blocks(trades, slot_arrivals, block_seconds, n_blocks):
    blocks = [[] for _ in range(n_blocks)]
    for trade, t in zip(trades, slot_arrivals):
        idx = int(t // block_seconds)
        if 0 <= idx < n_blocks:
            blocks[idx].append((trade, t - idx * block_seconds))
    return blocks


def build_joint_bootstrap_sequence(blocks_A, blocks_B, block_seconds, rng, target_duration):
    n_blocks = len(blocks_A)
    synA_t, synA_s, synB_t, synB_s = [], [], [], []
    cursor = 0.0
    while cursor < target_duration:
        idx = rng.randrange(n_blocks)
        for trade, offset in blocks_A[idx]:
            synA_t.append(trade); synA_s.append(cursor + offset)
        for trade, offset in blocks_B[idx]:
            synB_t.append(trade); synB_s.append(cursor + offset)
        cursor += block_seconds
    return (synA_t, synA_s), (synB_t, synB_s)


def run_one_joint(fmt_A, fmt_B, blocks_A, blocks_B, market_data, excluded_map, rng, horizon_seconds,
                   cost_A, cost_B, b_active=True):
    (trA, slA), (trB, slB) = build_joint_bootstrap_sequence(blocks_A, blocks_B, BLOCK_SECONDS, rng, horizon_seconds)
    accA = make_acc_mf(fmt_A, PALIER, cost_A)
    accB = make_acc_mf(fmt_B, PALIER, cost_B, active=b_active) if b_active else None
    state = {"reserve": 0.0, "total_breaks": 0, "real_cash_paid": cost_A + (cost_B if b_active else 0.0)}

    events = [(t, "A", tr) for tr, t in zip(trA, slA)]
    if b_active:
        events += [(t, "B", tr) for tr, t in zip(trB, slB)]
    events.sort(key=lambda e: e[0])

    hit_ceiling = {c: False for c in CEILINGS}
    b_first_profit_day = None
    snapshot_1y = None

    for now, which, trade in events:
        acc = accA if which == "A" else accB
        fmt = fmt_A if which == "A" else fmt_B
        process_trade_mf(acc, trade, now, fmt, state, trade_risk(acc), market_data, excluded_map,
                          split_flat=SPLIT_FLAT, reserve_share=RESERVE_SHARE)
        for c in CEILINGS:
            if state["reserve"] >= c:
                hit_ceiling[c] = True
        if b_active and b_first_profit_day is None and accB["phase"] == "funded" and accB["total_funded_pnl"] > 0:
            b_first_profit_day = now / DAY_SECONDS
        if snapshot_1y is None and now >= YEAR_SECONDS:
            fpnl = accA["total_funded_pnl"] + (accB["total_funded_pnl"] if b_active else 0.0)
            snapshot_1y = fpnl - state["real_cash_paid"]

    fpnl_final = accA["total_funded_pnl"] + (accB["total_funded_pnl"] if b_active else 0.0)
    profit_net = fpnl_final - state["real_cash_paid"]
    if snapshot_1y is None:
        snapshot_1y = profit_net
    return dict(profit_net=profit_net, annee1=snapshot_1y, hit_ceiling=hit_ceiling,
                b_first_profit_day=b_first_profit_day)


def run_scenario(label, fmt_A, fmt_B, blocks_A, blocks_B, market_data, excluded_map, n_sims,
                  horizon_seconds, cost_A, cost_B, b_active, seed=13579):
    rng = random.Random(seed)
    rows = []
    for _ in range(n_sims):
        rows.append(run_one_joint(fmt_A, fmt_B, blocks_A, blocks_B, market_data, excluded_map, rng,
                                   horizon_seconds, cost_A, cost_B, b_active))
    profits = [r["profit_net"] for r in rows]
    annee1 = [r["annee1"] for r in rows]
    b_days = [r["b_first_profit_day"] for r in rows if r["b_first_profit_day"] is not None]
    out = dict(label=label, profit_moyen=np.mean(profits), profit_median=np.median(profits),
               solde_negatif=100 * np.mean([p < 0 for p in profits]),
               annee1_neg=100 * np.mean([a < 0 for a in annee1]),
               b_never_profitable=100 * (1 - len(b_days) / n_sims) if b_active else None,
               b_first_profit_p50=np.median(b_days) if b_days else None,
               b_first_profit_p90=np.percentile(b_days, 90) if b_days else None)
    for c in CEILINGS:
        out[f"hit_ceiling_{c:.0f}"] = 100 * np.mean([r["hit_ceiling"][c] for r in rows])
    return out


if __name__ == "__main__":
    import sys
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300

    t0 = time.time()
    trades_A, dates_A = build_trades_A()
    trades_B, dates_B = build_trades_B()
    anchor = min(dates_A.min(), dates_B.min())
    slots_A = [(d - anchor).total_seconds() for d in dates_A]
    slots_B = [(d - anchor).total_seconds() for d in dates_B]
    horizon_seconds = HORIZON_YEARS * YEAR_SECONDS
    n_blocks = int(max(slots_A[-1], slots_B[-1]) // BLOCK_SECONDS) + 1

    blocks_A = build_aligned_blocks(trades_A, slots_A, BLOCK_SECONDS, n_blocks)
    blocks_B = build_aligned_blocks(trades_B, slots_B, BLOCK_SECONDS, n_blocks)
    print(f"A: {len(trades_A)} trades, B: {len(trades_B)} trades, {n_blocks} blocs alignes "
          f"(ancre commune {anchor.date()}) ({time.time()-t0:.0f}s)")

    market_data = b6.build_market_data_with_indices()
    all_tickers = sorted(set(t["ticker"] for t in trades_A) | set(t["ticker"] for t in trades_B))
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    excluded_map = precompute_correlation_pairs(all_tickers, corr_matrix, CORR_THRESHOLD)

    fmt_A = FORMATS["Blueberry_InstantElite"]
    cost_InstantElite = fmt_A["price"][PALIER]
    cost_2Step = FORMATS["Blueberry_2StepStandard"]["price"][PALIER]

    scenarios = [
        ("1. REF (A seul, InstantElite)", fmt_A, fmt_A, cost_InstantElite, 0.0, False),
        ("2a. A+B (B=InstantElite)", fmt_A, FORMATS["Blueberry_InstantElite"], cost_InstantElite, cost_InstantElite, True),
        ("2b. A+B (B=2StepStandard)", fmt_A, FORMATS["Blueberry_2StepStandard"], cost_InstantElite, cost_2Step, True),
    ]

    print(f"\n=== Monte Carlo n={n_sims} ===")
    all_rows = []
    for label, fA, fB, cA, cB, active in scenarios:
        t1 = time.time()
        res = run_scenario(label, fA, fB, blocks_A, blocks_B, market_data, excluded_map, n_sims,
                            horizon_seconds, cA, cB, active)
        all_rows.append(res)
        b_line = ""
        if active:
            b_line = (f" | B 1er profit net: p50={res['b_first_profit_p50']:.0f}j "
                       f"p90={res['b_first_profit_p90']:.0f}j jamais={res['b_never_profitable']:.1f}%")
        print(f"  {label:32s} profit_moy={res['profit_moyen']:+,.0f}$ profit_med={res['profit_median']:+,.0f}$ "
              f"solde_neg={res['solde_negatif']:.2f}% annee1<0={res['annee1_neg']:.2f}% "
              f"hit_ceiling(1000$/3000$)={res['hit_ceiling_1000']:.2f}%/{res['hit_ceiling_3000']:.2f}%"
              f"{b_line} ({time.time()-t1:.0f}s)")

    out = pd.DataFrame(all_rows)
    out.to_csv(f"ab_parallele_sweep_n{n_sims}_2026-08-19.csv", index=False)
    print(f"\nSauvegarde : ab_parallele_sweep_n{n_sims}_2026-08-19.csv")
