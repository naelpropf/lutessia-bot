"""Moteur A+B avec routage metaux, 3 configs (chantier routage A/B metaux,
2026-08-19). Base = chantier_ab_parallele_2026-08-19.py (premier moteur
2-comptes independants + reserve commune, cf. sa docstring:1-68 pour
l'architecture complete, reprise A L'IDENTIQUE ici), DEUX changements :

1. <<< any-RR CABLE (absent du moteur de base, cf. Etape 0 de ce chantier --
   chantier_ab_parallele_2026-08-19.py:168 appelait process_trade_mf nu) :
   process_trade_corr_swap_rr (chantier_b6_montecarlo_2026-08-19.py:116-144,
   deja generique/reutilise sans modification) applique aux DEUX comptes
   independamment (chacun son propre acc["_open_meta_rr"]), routing_field=
   "rr_tp1" (critere any-RR "brut" deja en production sur A, PAS le boost
   rr_tp2 S2.35 -- hors scope de ce chantier).
2. <<< ROUTAGE METAUX CONFIG 2 (overflow conditionnel) : route_metal_config2()
   tente B en premier (avec any-RR/swap deja inclus) ; si le trade n'est PAS
   admis ET que B n'etait PAS a son plafond de 3 positions (donc rejet
   specifiquement CORRELATION, pas plafond -- fidelite exacte a la
   specification utilisateur "bloque-correlation... redirige vers A", pas
   un rejet plafond) -> tente A. Rejet plafond B = perdu normalement (PAS
   overflow), coherent avec la lecture stricte de la demande.

Config 0/1 : routage deja resolu a la CONSTRUCTION de la population
(chantier_gold_silver_configs_2026-08-19.py) -- pas de logique runtime
speciale, chaque flux va simplement a son compte assigne.
"""
import random
import time
import importlib.util

import numpy as np
import pandas as pd

from monte_carlo_simulation import precompute_correlation_pairs
from scaling_simulation import CORR_THRESHOLD
import robustness_5ers_risk_challenge as eng
from real_cash_risk_year1_block_bootstrap import DAYS_PER_MONTH
from engine_multiformat import FORMATS, make_acc_mf

DAY_SECONDS = 86400
YEAR_SECONDS = 365.25 * DAY_SECONDS
BLOCK_MONTHS = 2
BLOCK_SECONDS = BLOCK_MONTHS * DAYS_PER_MONTH * DAY_SECONDS

EVAL_RISK, FLEET_RISK = 1.25, 1.90
RESERVE_SHARE = 0.95
SPLIT_FLAT = 0.80
PALIER = 25_000
CEILINGS = [960.0, 1000.0, 3000.0, 5000.0]
HORIZON_YEARS = 4.0
ROUTING_FIELD = "rr_tp1"

_spec = importlib.util.spec_from_file_location("b6", "chantier_b6_montecarlo_2026-08-19.py")
b6 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(b6)
process_trade_corr_swap_rr = b6.process_trade_corr_swap_rr


def trade_risk(acc):
    return EVAL_RISK if acc["phase"] == "challenge" else FLEET_RISK


def df_to_trades(pop):
    """Meme convention que chantier_ab_parallele_2026-08-19.py:build_trades_B
    -- outcome_r=r_trailing, sl_distance=|prix_entree-stop_loss_init| REEL
    (necessaire : feasible_risk_pct, scaling_simulation.py:121-147, l'utilise
    pour la contrainte de marge/lot reelle des trades FOREX -- un proxy
    neutre corromprait leur sizing, meme si les tickers metaux/indices sont
    de toute facon 'unconstrained' via build_market_data_with_indices)."""
    trades = []
    for _, row in pop.iterrows():
        trades.append({
            "ticker": row["ticker"],
            "outcome_r": float(row["r_trailing"]),
            "rr_tp1": float(row["rr_tp1"]),
            "rr_tp2": float(row["rr_tp2"]) if pd.notna(row["rr_tp2"]) else float(row["rr_tp1"]),
            "sl_distance": abs(float(row["prix_entree"]) - float(row["stop_loss_init"])),
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


def route_metal_config2(accA, accB, trade, now, fmtA, fmtB, state, market_data, excluded_map):
    accB["open_positions"] = [(t, c) for (t, c) in accB["open_positions"] if c > now]
    at_cap_B = len(accB["open_positions"]) >= eng.MAX_POSITIONS
    n_before = len(accB["open_positions"])
    process_trade_corr_swap_rr(accB, trade, now, fmtB, state, trade_risk(accB), market_data, excluded_map,
                                split_flat=SPLIT_FLAT, reserve_share=RESERVE_SHARE, routing_field=ROUTING_FIELD)
    admitted_B = len(accB["open_positions"]) > n_before
    if admitted_B or at_cap_B:
        return
    state["overflow_to_A"] = state.get("overflow_to_A", 0) + 1
    process_trade_corr_swap_rr(accA, trade, now, fmtA, state, trade_risk(accA), market_data, excluded_map,
                                split_flat=SPLIT_FLAT, reserve_share=RESERVE_SHARE, routing_field=ROUTING_FIELD)


def run_one_joint(fmt_A, fmt_B, blocks_A, blocks_B, market_data, excluded_map, rng, horizon_seconds,
                   cost_A, cost_B, config, metal_ticker_set=None):
    (trA, slA), (trB, slB) = build_joint_bootstrap_sequence(blocks_A, blocks_B, BLOCK_SECONDS, rng, horizon_seconds)
    accA = make_acc_mf(fmt_A, PALIER, cost_A)
    accB = make_acc_mf(fmt_B, PALIER, cost_B)
    state = {"reserve": 0.0, "total_breaks": 0, "real_cash_paid": cost_A + cost_B, "overflow_to_A": 0}

    events = [(t, "A", tr) for tr, t in zip(trA, slA)] + [(t, "B", tr) for tr, t in zip(trB, slB)]
    events.sort(key=lambda e: e[0])

    hit_ceiling = {c: False for c in CEILINGS}
    snapshot_1y = None

    for now, which, trade in events:
        if config == "2" and which == "B" and metal_ticker_set is not None and trade["ticker"] in metal_ticker_set:
            route_metal_config2(accA, accB, trade, now, fmt_A, fmt_B, state, market_data, excluded_map)
        else:
            acc = accA if which == "A" else accB
            fmt = fmt_A if which == "A" else fmt_B
            process_trade_corr_swap_rr(acc, trade, now, fmt, state, trade_risk(acc), market_data, excluded_map,
                                        split_flat=SPLIT_FLAT, reserve_share=RESERVE_SHARE, routing_field=ROUTING_FIELD)
        for c in CEILINGS:
            if state["reserve"] >= c:
                hit_ceiling[c] = True
        if snapshot_1y is None and now >= YEAR_SECONDS:
            snapshot_1y = accA["total_funded_pnl"] + accB["total_funded_pnl"] - state["real_cash_paid"]

    fpnl_final = accA["total_funded_pnl"] + accB["total_funded_pnl"]
    profit_net = fpnl_final - state["real_cash_paid"]
    if snapshot_1y is None:
        snapshot_1y = profit_net
    return dict(profit_net=profit_net, annee1=snapshot_1y, hit_ceiling=hit_ceiling,
                overflow_to_A=state["overflow_to_A"])


def run_scenario(label, fmt_A, fmt_B, blocks_A, blocks_B, market_data, excluded_map, n_sims,
                  horizon_seconds, cost_A, cost_B, config, metal_ticker_set, seed=13579):
    rng = random.Random(seed)
    rows = [run_one_joint(fmt_A, fmt_B, blocks_A, blocks_B, market_data, excluded_map, rng,
                           horizon_seconds, cost_A, cost_B, config, metal_ticker_set) for _ in range(n_sims)]
    profits = [r["profit_net"] for r in rows]
    annee1 = [r["annee1"] for r in rows]
    out = dict(label=label, n=n_sims, profit_moyen=np.mean(profits), profit_median=np.median(profits),
               solde_negatif=100 * np.mean([p < 0 for p in profits]),
               annee1_neg=100 * np.mean([a < 0 for a in annee1]),
               overflow_to_A_moy=np.mean([r["overflow_to_A"] for r in rows]))
    for c in CEILINGS:
        out[f"hit_ceiling_{c:.0f}"] = 100 * np.mean([r["hit_ceiling"][c] for r in rows])
    return out


GOLD_SILVER_LABELS = [f"{m} - {c}" for m in ("GOLD", "SILVER")
                       for c in ("USD", "EUR", "GBP", "CHF", "CAD", "AUD", "NZD")]


def load_common():
    """<<< CORRECTIF (meme raison que chantier_S1_8_regen_population_2026-08-
    19.py/chantier_rrtp2_sizing_2026-08-19.py) : b6.build_market_data_with_
    indices() ne couvre que les 5 labels indices, pas les 14 labels GOLD/
    SILVER -- feasible_risk_pct() plante sinon (KeyError). Meme contrainte
    de capacite desactivee ('unconstrained')."""
    market_data = b6.build_market_data_with_indices()
    unconstrained = {"tick_size": 1.0, "tick_value": 1.0, "volume_min": 0.0001,
                      "volume_max": 1e9, "volume_step": 0.0001, "margin_per_lot": 0.0001, "price": 1.0}
    for label in GOLD_SILVER_LABELS:
        market_data[label] = dict(unconstrained)
    return market_data


if __name__ == "__main__":
    import sys
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    config = sys.argv[2] if len(sys.argv) > 2 else "0"
    ceiling_filter = sys.argv[3] if len(sys.argv) > 3 else "all"

    t0 = time.time()
    if config == "baseline":
        pop_A = pd.read_csv("chantier_gold_silver_pop_A_config0_2026-08-19.csv")
        pop_B = pd.read_csv("chantier_gold_silver_pop_B_config0_2026-08-19.csv")
        pop_B = pop_B[~pop_B["ticker"].str.match(r"^(GOLD|SILVER) - ")].reset_index(drop=True)
        metal_set = set()
    elif config == "0":
        pop_A = pd.read_csv("chantier_gold_silver_pop_A_config0_2026-08-19.csv")
        pop_B = pd.read_csv("chantier_gold_silver_pop_B_config0_2026-08-19.csv")
        metal_set = set()
    elif config == "1":
        pop_A = pd.read_csv("chantier_gold_silver_pop_A_config1_2026-08-19.csv")
        pop_B = pd.read_csv("chantier_gold_silver_pop_B_config1_2026-08-19.csv")
        metal_set = set()
    elif config == "2":
        pop_A = pd.read_csv("chantier_gold_silver_pop_A_config0_2026-08-19.csv")
        pop_B = pd.read_csv("chantier_gold_silver_pop_B_config0_2026-08-19.csv")
        oa = pd.read_csv("chantier_gold_silver_pop_metaux_all_2026-08-19.csv")
        metal_set = set(oa["ticker"].unique())
    else:
        raise ValueError(config)

    pop_A["date_creation"] = pd.to_datetime(pop_A["date_creation"])
    pop_A["resolution_time_est"] = pd.to_datetime(pop_A["resolution_time_est"])
    pop_B["date_creation"] = pd.to_datetime(pop_B["date_creation"])
    pop_B["resolution_time_est"] = pd.to_datetime(pop_B["resolution_time_est"])

    trades_A, dates_A = df_to_trades(pop_A)
    trades_B, dates_B = df_to_trades(pop_B)
    anchor = min(dates_A.min(), dates_B.min())
    slots_A = [(d - anchor).total_seconds() for d in dates_A]
    slots_B = [(d - anchor).total_seconds() for d in dates_B]
    horizon_seconds = HORIZON_YEARS * YEAR_SECONDS
    n_blocks = int(max(slots_A[-1], slots_B[-1]) // BLOCK_SECONDS) + 1

    blocks_A = build_aligned_blocks(trades_A, slots_A, BLOCK_SECONDS, n_blocks)
    blocks_B = build_aligned_blocks(trades_B, slots_B, BLOCK_SECONDS, n_blocks)
    print(f"[config={config}] A: {len(trades_A)} trades, B: {len(trades_B)} trades, "
          f"{n_blocks} blocs ({time.time()-t0:.0f}s)")

    market_data = load_common()
    all_tickers = sorted(set(t["ticker"] for t in trades_A) | set(t["ticker"] for t in trades_B))
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    excluded_map = precompute_correlation_pairs(all_tickers, corr_matrix, CORR_THRESHOLD)

    fmt_A = FORMATS["Blueberry_InstantElite"]
    fmt_B = FORMATS["Blueberry_InstantElite"]
    cost = fmt_A["price"][PALIER]

    rows = []
    t1 = time.time()
    res = run_scenario(f"config_{config}", fmt_A, fmt_B, blocks_A, blocks_B, market_data, excluded_map,
                        n_sims, horizon_seconds, cost, cost, config, metal_set)
    rows.append(res)
    print(f"  profit_moy={res['profit_moyen']:+,.0f}$ profit_med={res['profit_median']:+,.0f}$ "
          f"solde_neg={res['solde_negatif']:.2f}% annee1<0={res['annee1_neg']:.2f}% "
          f"hit_ceiling(1000/3000)={res['hit_ceiling_1000']:.2f}%/{res['hit_ceiling_3000']:.2f}% "
          f"overflow_A_moy={res['overflow_to_A_moy']:.1f} ({time.time()-t1:.0f}s)")

    pd.DataFrame(rows).to_csv(f"chantier_gold_silver_mc_config{config}_n{n_sims}_{ceiling_filter}_2026-08-19.csv", index=False)
    print(f"Termine en {time.time()-t0:.0f}s.")
