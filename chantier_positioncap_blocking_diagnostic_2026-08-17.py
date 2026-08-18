"""
Sections A/B (2026-08-17) - Etape 0 commune : taux de blocage REEL du
plafond de 3 positions simultanees, REVERIFIE sous la pile actuelle
(RR>=1,35/corr0,80, S1.8, S2.35 -- l'ancienne mesure 0,79-1,11% date
d'avant cette pile, S2.28 registre_parametres_projet.md).

Le blocage par PLAFOND (len(open_positions)>=MAX_POSITIONS) est un early
return de `process_trade_mf` (engine_multiformat.py:324), AVANT le check
de correlation -- non affecte par any-RR (le swap ne s'applique que
`if not at_cap`, chantier_*_2026-08-16.py). Donc la mecanique de blocage
plafond elle-meme est INCHANGEE depuis avant any-RR ; ce qui change sous
la pile actuelle, c'est la SEQUENCE/frequence des trades admis (rr_tp2
sizing ne change pas l'admission, seulement la taille) et la population
(721->631, RR>=1,35 au lieu de >=1,25).

Simule UNIQUEMENT l'admission de positions (pas la partie financiere/DD)
pour un compte representatif, sur bootstrap identique aux chantiers fleet
(build_flexible_population + block-bootstrap), et distingue :
- blocage plafond AVEC un doublon meme ticker parmi les 3 positions ouvertes
- blocage plafond SANS doublon (3 paires differentes deja ouvertes)
"""
import random
import sys
import time
from collections import Counter

import pandas as pd

import robustness_5ers_risk_challenge as eng
from point_liquidity_rules import DAY_SECONDS
from trailing_payoff_population import build_population_with_trailing
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH

MIN_RR_NEW = 1.35
YEAR_SECONDS = 365.25 * DAY_SECONDS
MONTH_SECONDS = DAYS_PER_MONTH * DAY_SECONDS
SIM_YEARS = 4


def simulate_admission(trades, slot_arrivals, order):
    open_positions = []  # (ticker, close_time)
    n_offered = 0
    n_admitted = 0
    n_cap_blocked = 0
    n_cap_blocked_same_ticker = 0

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]
        close_time = now + trade["hold_seconds"]
        open_positions = [(t, c) for (t, c) in open_positions if c > now]
        n_offered += 1
        if len(open_positions) >= eng.MAX_POSITIONS:
            n_cap_blocked += 1
            if any(t == trade["ticker"] for (t, c) in open_positions):
                n_cap_blocked_same_ticker += 1
            continue
        open_positions.append((trade["ticker"], close_time))
        n_admitted += 1

    return n_offered, n_admitted, n_cap_blocked, n_cap_blocked_same_ticker


if __name__ == "__main__":
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    t_start = time.time()

    pop = build_population_with_trailing("fixed", 0.15, min_rr=MIN_RR_NEW, verbose=False)
    print(f"[verif] population (RR>={MIN_RR_NEW}) : {len(pop)} trades")

    rng_wr = random.Random(9999)
    rng_boot = random.Random(10000)

    tot_offered = tot_admitted = tot_cap_blocked = tot_cap_same_ticker = 0
    for sim_i in range(n_sims):
        wr_draw = rng_wr.betavariate(260, 388)
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_draw, 1.0, False, random.Random(rng_boot.random()))
        block_seconds = 2 * 30 * DAY_SECONDS
        blocks = build_blocks(trades, slot_arrivals, block_seconds)
        target_duration = slot_arrivals[-1]
        from reference_metrics_final import build_full_block_bootstrap_sequence
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot, SIM_YEARS * YEAR_SECONDS)
        order = list(range(len(raw_trades)))

        n_off, n_adm, n_cap, n_cap_same = simulate_admission(raw_trades, raw_slots, order)
        tot_offered += n_off
        tot_admitted += n_adm
        tot_cap_blocked += n_cap
        tot_cap_same_ticker += n_cap_same

        if (sim_i + 1) % 50 == 0:
            print(f"  sim {sim_i+1}/{n_sims} ({time.time()-t_start:.0f}s)")

    print(f"\n=== Resultats sur {n_sims} sims, {tot_offered} trades offerts (1 compte représentatif) ===")
    print(f"Taux de blocage plafond (global) : {tot_cap_blocked}/{tot_offered} = {tot_cap_blocked/tot_offered*100:.2f}%")
    print(f"Parmi les blocages plafond, part AVEC doublon meme ticker deja ouvert : "
          f"{tot_cap_same_ticker}/{tot_cap_blocked} = {tot_cap_same_ticker/tot_cap_blocked*100:.1f}% "
          f"(soit {tot_cap_same_ticker/tot_offered*100:.3f}% de TOUS les trades offerts)")
    print(f"Parmi les blocages plafond, part SANS doublon (3 paires differentes) : "
          f"{tot_cap_blocked-tot_cap_same_ticker}/{tot_cap_blocked} = "
          f"{(tot_cap_blocked-tot_cap_same_ticker)/tot_cap_blocked*100:.1f}%")

    print(f"\nTermine en {time.time()-t_start:.0f}s.")
