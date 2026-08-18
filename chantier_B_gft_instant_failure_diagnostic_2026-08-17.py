"""
Section B - Etape 0 (2026-08-17) : diagnostic du MODE DE CASSE des comptes
GFT Instant (`GFT_InstantGOAT`, funded=phase(None,None,3.0,6.0,"trailing_peak")),
pour informer la conception d'une strategie adaptee (pas la classique
rejouee telle quelle, deja rejetee en S2.37/registre_strategie_trading.md).

Question posee : une casse vient-elle (a) d'une EXCURSION ISOLEE (perte
d'un seul jour >=3,0% -- le DD JOURNALIER) ou (b) d'une DERIVE CUMULATIVE
depuis le dernier pic (le DD MAX 6,0% trailing_peak, JAMAIS verrouille --
`lock_after_pct=None` pour ce format precisement, contrairement a
Blueberry_InstantElite qui a lock_after_pct=10.0) ?

Verification prealable (documentee, pas suppposee) : les 2 fichiers
suggeres par le prompt (`daily_dd_trade_days_288.csv`,
`daily_dd_pair_ranking_288.csv`) sont INADAPTES a cette question -- verifie
par lecture directe : `daily_dd_trade_days_288.csv` est indexe par
trade_id/date/excursion_r/is_final_sl_day, structure de la simulation
TRAILING-STOP PAR TRADE (`trailing_payoff_population.simulate_trailing`),
pas du DD de COMPTE ; date le 30/07 (avant la population RR>=1,35 actuelle,
631 trades) ; n=277 lignes seulement. `daily_dd_pair_ranking_288.csv` deja
documente et ECARTE en S6.3 (`registre_parametres_projet.md`) pour la meme
raison (perime, metrique paire-de-paires, quasi vide). Aucun des deux ne
permet de repondre a la question posee -- diagnostic reconstruit ICI par
simulation directe et instrumentee d'un compte GFT Instant isole (meme
convention "compte isole, tresorerie infinie" que S6.2/S6.3,
`chantier_gft_instant_exploration_2026-08-15.py:run_variant`), avec sizing
rr_tp2 actif (routing rr_tp2>=8 -> x1,6, config exacte deja testee en S2.37
pour rester fidele au mecanisme observe -- gft_instant_breaks_moy=108-113).

Duplication ASSUMEE de la logique DD de `engine_multiformat.process_trade_mf`/
`_dd_max_breached` (pas un import direct) car ces fonctions ne retournent
pas le TYPE de casse (journalier vs max) ni la longueur de la sequence
depuis le dernier pic -- necessaire ici, absent de l'API existante.
"""
import random
import sys
import time
from collections import Counter

import numpy as np
import pandas as pd

import robustness_5ers_risk_challenge as eng
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from engine_multiformat import FORMATS, make_acc_mf
from corrected_scaling_mechanism import BASE_PALIER

DAY_SECONDS = 86400
YEAR_SECONDS = 365.25 * DAY_SECONDS
MONTH_SECONDS = DAYS_PER_MONTH * DAY_SECONDS
SIM_YEARS = 4
MIN_RR = 1.35
CORR_TH = 0.80
FLEET_RISK = 1.90
GFT_PALIER = BASE_PALIER["GFT"]
GFT_INSTANT_FMT = FORMATS["GFT_InstantGOAT"]
RR_TP2_THRESHOLD = 8.0
RR_TP2_MULT = 1.6


def size_mult(rr_tp2):
    return RR_TP2_MULT if rr_tp2 >= RR_TP2_THRESHOLD else 1.0


def build_flexible_population_with_rr(pop, target_winrate, rr_stress_factor, use_slippage, rng):
    trades, slot_arrivals = eng.build_flexible_population(pop, target_winrate, rr_stress_factor, use_slippage, rng)
    sub = pop.sort_values("date_creation").reset_index(drop=True)
    assert len(sub) == len(trades)
    for t, rr2 in zip(trades, sub["rr_tp2"]):
        t["rr_tp2"] = float(rr2)
    return trades, slot_arrivals


def run_instrumented(trades, slot_arrivals, market_data, excluded_map, order, palier=GFT_PALIER,
                      risk_funded=FLEET_RISK):
    fmt = GFT_INSTANT_FMT
    pdef = fmt["funded"]
    acc = make_acc_mf(fmt, palier, cost=0.0, active=True)
    acc["phase"] = "funded"

    episode_trades = []  # (rr_tp2, pnl) depuis le dernier pic
    breaks = []  # dicts : type, n_trades_in_episode, rr_tp2_list, trigger_pnl_pct

    open_positions = []
    daily_pnl = {}

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]
        close_time = now + trade["hold_seconds"]
        open_positions = [(t, c) for (t, c) in open_positions if c > now]
        if len(open_positions) >= eng.MAX_POSITIONS:
            continue
        if any(t in excluded_map[trade["ticker"]] for (t, _) in open_positions):
            continue

        eff_risk, _ = eng.feasible_risk_pct(trade["ticker"], trade["sl_distance"], palier, risk_funded, market_data)
        eff_risk = eff_risk * size_mult(trade["rr_tp2"])
        risk_amount = eff_risk / 100 * palier
        pnl = trade["outcome_r"] * risk_amount

        open_positions.append((trade["ticker"], close_time))
        acc["cumulative_since_reset"] += pnl
        acc["peak_since_reset"] = max(acc["peak_since_reset"], acc["cumulative_since_reset"])
        close_day = int(close_time // DAY_SECONDS)
        daily_pnl[close_day] = daily_pnl.get(close_day, 0.0) + pnl
        episode_trades.append((trade["rr_tp2"], pnl))

        net_pnl = pnl * 0.80 if pnl > 0 else pnl
        acc["total_funded_pnl"] += net_pnl

        daily_dd = -daily_pnl[close_day]
        daily_broke = daily_dd >= pdef["dd_daily_pct"] / 100 * palier
        trailing_dd = acc["peak_since_reset"] - acc["cumulative_since_reset"]
        max_broke = trailing_dd >= pdef["dd_max_pct"] / 100 * palier

        if daily_broke or max_broke:
            btype = "daily" if daily_broke and not max_broke else ("max" if max_broke and not daily_broke else "both")
            breaks.append(dict(
                type=btype,
                n_trades_in_episode=len(episode_trades),
                rr_tp2_list=[e[0] for e in episode_trades],
                losing_rr_tp2_list=[e[0] for e in episode_trades if e[1] < 0],
                trigger_trade_rr_tp2=trade["rr_tp2"],
                trigger_trade_pnl_pct_of_palier=pnl / palier * 100,
            ))
            acc["cumulative_since_reset"] = 0.0
            acc["peak_since_reset"] = 0.0
            episode_trades = []
            open_positions = []
            daily_pnl = {}

    return breaks


if __name__ == "__main__":
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    t_start = time.time()

    pop = build_population_with_trailing("fixed", 0.15, min_rr=MIN_RR, verbose=False)
    print(f"[verif] population (RR>={MIN_RR}) : {len(pop)} trades, "
          f"rr_tp2>=8 : {(pop['rr_tp2'] >= 8).sum()} trades ({(pop['rr_tp2'] >= 8).mean()*100:.1f}%)")
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

    rng_wr = random.Random(9999)
    rng_boot = random.Random(10000)

    all_breaks = []
    for sim_i in range(n_sims):
        wr_draw = rng_wr.betavariate(260, 388)
        trades, slot_arrivals = build_flexible_population_with_rr(pop, wr_draw, 1.0, False, random.Random(rng_boot.random()))
        block_seconds = 2 * 30 * DAY_SECONDS
        blocks = build_blocks(trades, slot_arrivals, block_seconds)
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot, SIM_YEARS * YEAR_SECONDS)
        order = list(range(len(raw_trades)))
        breaks = run_instrumented(raw_trades, raw_slots, market_data, excluded_map, order)
        all_breaks.extend(breaks)
        if (sim_i + 1) % 20 == 0:
            print(f"  sim {sim_i+1}/{n_sims}, {len(all_breaks)} casses cumulees ({time.time()-t_start:.0f}s)")

    print(f"\n=== {len(all_breaks)} casses sur {n_sims} sims ({len(all_breaks)/n_sims:.2f}/sim, "
          f"{len(all_breaks)/n_sims/SIM_YEARS:.2f}/an) ===")

    type_counts = Counter(b["type"] for b in all_breaks)
    print(f"\nType de declenchement : daily(seul)={type_counts['daily']} ({type_counts['daily']/len(all_breaks)*100:.1f}%) "
          f"max_trailing(seul)={type_counts['max']} ({type_counts['max']/len(all_breaks)*100:.1f}%) "
          f"les_deux_meme_trade={type_counts['both']} ({type_counts['both']/len(all_breaks)*100:.1f}%)")

    n_trades_dist = [b["n_trades_in_episode"] for b in all_breaks]
    print(f"\nNb de trades dans l'episode menant a la casse : "
          f"moyenne={np.mean(n_trades_dist):.2f} mediane={np.median(n_trades_dist):.0f} "
          f"P25={np.percentile(n_trades_dist,25):.0f} P75={np.percentile(n_trades_dist,75):.0f} "
          f"part episodes 1-seul-trade={sum(1 for n in n_trades_dist if n==1)/len(n_trades_dist)*100:.1f}%")

    trigger_pnl = [b["trigger_trade_pnl_pct_of_palier"] for b in all_breaks]
    print(f"PnL% du trade declencheur (palier) : moyenne={np.mean(trigger_pnl):+.2f}% "
          f"mediane={np.median(trigger_pnl):+.2f}% min={np.min(trigger_pnl):+.2f}%")

    # rr_tp2 des trades PERDANTS impliques dans les episodes de casse, vs population globale
    losing_rr_all = [rr for b in all_breaks for rr in b["losing_rr_tp2_list"]]
    print(f"\n=== rr_tp2 des trades PERDANTS dans les episodes de casse (n={len(losing_rr_all)}) "
          f"vs population globale (n={len(pop)}) ===")
    print(f"  Episodes -- rr_tp2 moyen={np.mean(losing_rr_all):.2f} median={np.median(losing_rr_all):.2f}")
    print(f"  Population -- rr_tp2 moyen={pop['rr_tp2'].mean():.2f} median={pop['rr_tp2'].median():.2f}")

    for lo, hi in [(1.7, 3), (3, 5), (5, 8), (8, 31)]:
        share_episodes = sum(1 for r in losing_rr_all if lo <= r < hi) / len(losing_rr_all) * 100
        share_pop = ((pop["rr_tp2"] >= lo) & (pop["rr_tp2"] < hi)).mean() * 100
        print(f"  rr_tp2 [{lo},{hi}) : part dans episodes de casse={share_episodes:.1f}% "
              f"vs part dans population={share_pop:.1f}%  (ratio={share_episodes/share_pop:.2f})")

    # <<< rr_tp2 du trade DECLENCHEUR specifiquement (celui qui fait passer
    # le seuil) -- teste si le sizing rr_tp2>=8 -> x1.6 (deja adopte S2.35)
    # est lui-meme surrepresente PARMI LES DECLENCHEURS (pas juste parmi
    # les perdants en general) -- hypothese : un trade sizee x1.6 (risque
    # effectif jusqu'a 3,04%) peut a lui seul depasser le DD journalier 3,0%.
    trigger_rr = [b["trigger_trade_rr_tp2"] for b in all_breaks]
    trigger_sized_pct = sum(1 for r in trigger_rr if r >= 8) / len(trigger_rr) * 100
    pop_sized_pct = (pop["rr_tp2"] >= 8).mean() * 100
    print(f"\n=== rr_tp2 du trade DECLENCHEUR (celui qui fait franchir le seuil, n={len(trigger_rr)}) ===")
    print(f"  Part rr_tp2>=8 (sizee x1,6) PARMI LES DECLENCHEURS={trigger_sized_pct:.1f}% "
          f"vs part dans la population globale={pop_sized_pct:.1f}%  (ratio={trigger_sized_pct/pop_sized_pct:.2f})")
    single_trade_breaks = [b for b in all_breaks if b["n_trades_in_episode"] == 1]
    if single_trade_breaks:
        st_sized = sum(1 for b in single_trade_breaks if b["trigger_trade_rr_tp2"] >= 8) / len(single_trade_breaks) * 100
        print(f"  Parmi les episodes a 1 SEUL trade (n={len(single_trade_breaks)}, casse en un coup) : "
              f"part rr_tp2>=8={st_sized:.1f}% (vs {pop_sized_pct:.1f}% population)")

    print(f"\nTermine en {time.time()-t_start:.0f}s.")
