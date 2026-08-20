"""
Stress-test H1/H2+4blocs du moteur A+B parallele, session 2026-08-19.
Reutilise integralement chantier_ab_parallele_2026-08-19.py (import via
importlib, nom de fichier date non importable directement -- meme
convention que le reste du projet).

Methode (meme principe que les stress-tests deja utilises partout dans le
projet, ex. registre_parametres_projet.md:4511-4513 pour le staggered
unlock, registre_strategie_trading.md:1740-1741 pour rr_tp2) : restreint
le POOL de blocs tirable au sous-echantillon temporel (H1/H2/bloc0-3),
mais garde le MEME horizon synthetique de 4 ans que le test principal --
la question posee est "si le marche s'etait comporte comme UNIQUEMENT
cette sous-periode, la dominance tiendrait-elle sur un horizon complet ?",
pas une simulation courte sur la duree reelle de la sous-periode.
"""
import random
import time
import importlib.util

import numpy as np
import pandas as pd

_spec = importlib.util.spec_from_file_location("ab", "chantier_ab_parallele_2026-08-19.py")
ab = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ab)

N_STRESS = 300


def build_joint_bootstrap_sequence_subset(blocks_A, blocks_B, block_indices, block_seconds, rng, target_duration):
    synA_t, synA_s, synB_t, synB_s = [], [], [], []
    cursor = 0.0
    while cursor < target_duration:
        idx = block_indices[rng.randrange(len(block_indices))]
        for trade, offset in blocks_A[idx]:
            synA_t.append(trade); synA_s.append(cursor + offset)
        for trade, offset in blocks_B[idx]:
            synB_t.append(trade); synB_s.append(cursor + offset)
        cursor += block_seconds
    return (synA_t, synA_s), (synB_t, synB_s)


def run_one_joint_subset(fmt_A, fmt_B, blocks_A, blocks_B, block_indices, market_data, excluded_map, rng,
                          horizon_seconds, cost_A, cost_B, b_active):
    (trA, slA), (trB, slB) = build_joint_bootstrap_sequence_subset(
        blocks_A, blocks_B, block_indices, ab.BLOCK_SECONDS, rng, horizon_seconds)
    accA = ab.make_acc_mf(fmt_A, ab.PALIER, cost_A)
    accB = ab.make_acc_mf(fmt_B, ab.PALIER, cost_B, active=b_active) if b_active else None
    state = {"reserve": 0.0, "total_breaks": 0, "real_cash_paid": cost_A + (cost_B if b_active else 0.0)}

    events = [(t, "A", tr) for tr, t in zip(trA, slA)]
    if b_active:
        events += [(t, "B", tr) for tr, t in zip(trB, slB)]
    events.sort(key=lambda e: e[0])

    snapshot_1y = None
    for now, which, trade in events:
        acc = accA if which == "A" else accB
        fmt = fmt_A if which == "A" else fmt_B
        ab.process_trade_mf(acc, trade, now, fmt, state, ab.trade_risk(acc), market_data, excluded_map,
                             split_flat=ab.SPLIT_FLAT, reserve_share=ab.RESERVE_SHARE)
        if snapshot_1y is None and now >= ab.YEAR_SECONDS:
            fpnl = accA["total_funded_pnl"] + (accB["total_funded_pnl"] if b_active else 0.0)
            snapshot_1y = fpnl - state["real_cash_paid"]

    fpnl_final = accA["total_funded_pnl"] + (accB["total_funded_pnl"] if b_active else 0.0)
    profit_net = fpnl_final - state["real_cash_paid"]
    if snapshot_1y is None:
        snapshot_1y = profit_net
    return profit_net, snapshot_1y


def run_scenario_subset(fmt_A, fmt_B, blocks_A, blocks_B, block_indices, market_data, excluded_map,
                         n_sims, horizon_seconds, cost_A, cost_B, b_active, seed):
    rng = random.Random(seed)
    profits, annee1s = [], []
    for _ in range(n_sims):
        p, a1 = run_one_joint_subset(fmt_A, fmt_B, blocks_A, blocks_B, block_indices, market_data,
                                      excluded_map, rng, horizon_seconds, cost_A, cost_B, b_active)
        profits.append(p); annee1s.append(a1)
    return dict(profit_moyen=np.mean(profits), solde_negatif=100 * np.mean([p < 0 for p in profits]),
                annee1_neg=100 * np.mean([a < 0 for a in annee1s]))


if __name__ == "__main__":
    t0 = time.time()
    trades_A, dates_A = ab.build_trades_A()
    trades_B, dates_B = ab.build_trades_B()
    anchor = min(dates_A.min(), dates_B.min())
    slots_A = [(d - anchor).total_seconds() for d in dates_A]
    slots_B = [(d - anchor).total_seconds() for d in dates_B]
    horizon_seconds = ab.HORIZON_YEARS * ab.YEAR_SECONDS
    n_blocks = int(max(slots_A[-1], slots_B[-1]) // ab.BLOCK_SECONDS) + 1
    blocks_A = ab.build_aligned_blocks(trades_A, slots_A, ab.BLOCK_SECONDS, n_blocks)
    blocks_B = ab.build_aligned_blocks(trades_B, slots_B, ab.BLOCK_SECONDS, n_blocks)
    print(f"{n_blocks} blocs alignes (ancre {anchor.date()}) ({time.time()-t0:.0f}s)")

    market_data = ab.b6.build_market_data_with_indices()
    all_tickers = sorted(set(t["ticker"] for t in trades_A) | set(t["ticker"] for t in trades_B))
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    excluded_map = ab.precompute_correlation_pairs(all_tickers, corr_matrix, ab.CORR_THRESHOLD)

    fmt_A = ab.FORMATS["Blueberry_InstantElite"]
    fmt_B = ab.FORMATS["Blueberry_InstantElite"]
    cost = fmt_A["price"][ab.PALIER]

    half = n_blocks // 2
    quarter = n_blocks // 4
    folds = {
        "H1": list(range(0, half)),
        "H2": list(range(half, n_blocks)),
        "bloc0": list(range(0, quarter)),
        "bloc1": list(range(quarter, 2 * quarter)),
        "bloc2": list(range(2 * quarter, 3 * quarter)),
        "bloc3": list(range(3 * quarter, n_blocks)),
    }
    print(f"n_blocks={n_blocks}, decoupage : " + ", ".join(f"{k}={v}" for k, v in folds.items()))

    rows = []
    print(f"\n=== Stress-test n={N_STRESS}/sous-periode/scenario ===")
    for fold_name, block_indices in folds.items():
        ref = run_scenario_subset(fmt_A, fmt_A, blocks_A, blocks_B, block_indices, market_data, excluded_map,
                                   N_STRESS, horizon_seconds, cost, 0.0, False, seed=hash(("ref", fold_name)) % (2**31))
        ab_scn = run_scenario_subset(fmt_A, fmt_B, blocks_A, blocks_B, block_indices, market_data, excluded_map,
                                      N_STRESS, horizon_seconds, cost, cost, True, seed=hash(("ab", fold_name)) % (2**31))
        delta_pct = 100 * (ab_scn["profit_moyen"] - ref["profit_moyen"]) / abs(ref["profit_moyen"]) if ref["profit_moyen"] else float("nan")
        row = dict(fold=fold_name, n_blocs=len(block_indices),
                   ref_profit=ref["profit_moyen"], ref_solde_neg=ref["solde_negatif"], ref_annee1=ref["annee1_neg"],
                   ab_profit=ab_scn["profit_moyen"], ab_solde_neg=ab_scn["solde_negatif"], ab_annee1=ab_scn["annee1_neg"],
                   delta_pct=delta_pct)
        rows.append(row)
        flag = "  <<< INVERSION" if delta_pct < 0 else ""
        print(f"  {fold_name:6s} (n_blocs={len(block_indices):2d}) REF={ref['profit_moyen']:+10,.0f}$ "
              f"(sn={ref['solde_negatif']:.1f}% a1={ref['annee1_neg']:.1f}%) | "
              f"A+B={ab_scn['profit_moyen']:+10,.0f}$ (sn={ab_scn['solde_negatif']:.1f}% a1={ab_scn['annee1_neg']:.1f}%) "
              f"| delta={delta_pct:+.1f}%{flag}")

    out = pd.DataFrame(rows)
    out.to_csv("ab_parallele_stresstest_2026-08-19.csv", index=False)
    n_inversions = sum(1 for r in rows if r["delta_pct"] < 0)
    print(f"\n{6-n_inversions}/6 sous-periodes coherentes (A+B > REF), {n_inversions}/6 inversions.")
    print(f"({time.time()-t0:.0f}s total)")
