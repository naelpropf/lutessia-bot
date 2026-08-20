"""
Sweep tailles de pivot A+B (reduire le cout d'ouverture), session 2026-08-19.
Reutilise chantier_ab_parallele_2026-08-19.py (import via importlib, nom
de fichier date non importable directement, meme convention que le reste
du projet) -- make_acc_mf/process_trade_mf/build_aligned_blocks/
build_joint_bootstrap_sequence tels quels, RIEN reimplemente hormis
run_one_joint_sized/run_scenario_sized ci-dessous, copies adaptees de
run_one_joint/run_scenario (chantier_ab_parallele_2026-08-19.py:141-186)
avec palier_A/palier_B PARAMETRES au lieu de la constante module PALIER
unique -- necessaire pour tester des combinaisons asymetriques (A25k+B10k
etc.), impossible avec la version d'origine qui suppose un seul palier
partage par les 2 comptes.

Point 4 (registre_parametres_projet.md:9.4, session precedente) a deja
teste des paliers 5k/10k en PIVOT UNIQUE (A seul, pas de reserve
partagee entre 2 comptes) -- PAS reutilise ici tel quel, uniquement comme
point de comparaison qualitatif (cf. Etape 2 : le cout structurel
solde_neg/hit_ceiling 0,00%->0,17% invisible en n=300, visible seulement
n=600, y avait ete trouve a 5k$ isole).

Couts de reference (fournis, pas retrouves dans FORMATS -- price dict de
Blueberry_InstantElite, engine_multiformat.py:146, ne contient que
{25000: 800}, aucune entree 5k/10k dans le code) : 5k$=200$, 10k$=400$,
25k$=800$.
"""
import random
import time
import importlib.util

import numpy as np
import pandas as pd

_spec = importlib.util.spec_from_file_location("ab", "chantier_ab_parallele_2026-08-19.py")
ab = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ab)

COST_BY_PALIER = {5_000: 200.0, 10_000: 400.0, 25_000: 800.0}

COMBOS = [
    ("A25k+B25k (ref)", 25_000, 25_000),
    ("A25k+B10k", 25_000, 10_000),
    ("A25k+B5k", 25_000, 5_000),
    ("A10k+B10k", 10_000, 10_000),
    ("A10k+B5k", 10_000, 5_000),
    ("A5k+B5k", 5_000, 5_000),
]


def _bootstrap_sequence(blocks_A, blocks_B, rng, horizon_seconds, block_indices=None):
    """block_indices=None -> tire sur tout le pool (identique a ab.build_joint_
    bootstrap_sequence). Sinon restreint le pool tirable au sous-echantillon
    (meme principe que chantier_ab_stresstest_2026-08-19.py:29-38, copie
    inline ici pour eviter un 2e import croise entre scripts a nom date)."""
    if block_indices is None:
        return ab.build_joint_bootstrap_sequence(blocks_A, blocks_B, ab.BLOCK_SECONDS, rng, horizon_seconds)
    n = len(block_indices)
    synA_t, synA_s, synB_t, synB_s = [], [], [], []
    cursor = 0.0
    while cursor < horizon_seconds:
        idx = block_indices[rng.randrange(n)]
        for trade, offset in blocks_A[idx]:
            synA_t.append(trade); synA_s.append(cursor + offset)
        for trade, offset in blocks_B[idx]:
            synB_t.append(trade); synB_s.append(cursor + offset)
        cursor += ab.BLOCK_SECONDS
    return (synA_t, synA_s), (synB_t, synB_s)


def run_one_joint_sized(fmt_A, fmt_B, blocks_A, blocks_B, market_data, excluded_map, rng, horizon_seconds,
                         palier_A, palier_B, cost_A, cost_B, block_indices=None):
    (trA, slA), (trB, slB) = _bootstrap_sequence(blocks_A, blocks_B, rng, horizon_seconds, block_indices)
    accA = ab.make_acc_mf(fmt_A, palier_A, cost_A)
    accB = ab.make_acc_mf(fmt_B, palier_B, cost_B)
    state = {"reserve": 0.0, "total_breaks": 0, "real_cash_paid": cost_A + cost_B}

    events = [(t, "A", tr) for tr, t in zip(trA, slA)] + [(t, "B", tr) for tr, t in zip(trB, slB)]
    events.sort(key=lambda e: e[0])

    hit_ceiling = {c: False for c in ab.CEILINGS}
    b_first_profit_day = None
    snapshot_1y = None

    for now, which, trade in events:
        acc = accA if which == "A" else accB
        fmt = fmt_A if which == "A" else fmt_B
        ab.process_trade_mf(acc, trade, now, fmt, state, ab.trade_risk(acc), market_data, excluded_map,
                             split_flat=ab.SPLIT_FLAT, reserve_share=ab.RESERVE_SHARE)
        for c in ab.CEILINGS:
            if state["reserve"] >= c:
                hit_ceiling[c] = True
        if b_first_profit_day is None and accB["phase"] == "funded" and accB["total_funded_pnl"] > 0:
            b_first_profit_day = now / ab.DAY_SECONDS
        if snapshot_1y is None and now >= ab.YEAR_SECONDS:
            snapshot_1y = (accA["total_funded_pnl"] + accB["total_funded_pnl"]) - state["real_cash_paid"]

    profit_net = (accA["total_funded_pnl"] + accB["total_funded_pnl"]) - state["real_cash_paid"]
    if snapshot_1y is None:
        snapshot_1y = profit_net
    return dict(profit_net=profit_net, annee1=snapshot_1y, hit_ceiling=hit_ceiling,
                b_first_profit_day=b_first_profit_day)


def run_scenario_sized(blocks_A, blocks_B, market_data, excluded_map, n_sims, horizon_seconds,
                        palier_A, palier_B, seed=24680, block_indices=None):
    fmt = ab.FORMATS["Blueberry_InstantElite"]
    cost_A, cost_B = COST_BY_PALIER[palier_A], COST_BY_PALIER[palier_B]
    rng = random.Random(seed)
    rows = [run_one_joint_sized(fmt, fmt, blocks_A, blocks_B, market_data, excluded_map, rng, horizon_seconds,
                                 palier_A, palier_B, cost_A, cost_B, block_indices) for _ in range(n_sims)]
    profits = [r["profit_net"] for r in rows]
    annee1 = [r["annee1"] for r in rows]
    b_days = [r["b_first_profit_day"] for r in rows if r["b_first_profit_day"] is not None]
    out = dict(cost_total=cost_A + cost_B, profit_moyen=np.mean(profits), profit_median=np.median(profits),
               solde_negatif=100 * np.mean([p < 0 for p in profits]),
               annee1_neg=100 * np.mean([a < 0 for a in annee1]),
               b_first_profit_p50=np.median(b_days) if b_days else None,
               b_first_profit_p90=np.percentile(b_days, 90) if b_days else None,
               b_never_profitable=100 * (1 - len(b_days) / n_sims))
    for c in ab.CEILINGS:
        out[f"hit_ceiling_{c:.0f}"] = 100 * np.mean([r["hit_ceiling"][c] for r in rows])
    return out


def run_sweep(n_sims, blocks_A, blocks_B, market_data, excluded_map, horizon_seconds, seed_base):
    rows = []
    for label, pA, pB in COMBOS:
        t0 = time.time()
        res = run_scenario_sized(blocks_A, blocks_B, market_data, excluded_map, n_sims, horizon_seconds,
                                  pA, pB, seed=seed_base + hash(label) % 1000)
        res["label"] = label
        rows.append(res)
        print(f"  {label:18s} cout={res['cost_total']:5.0f}$ profit_moy={res['profit_moyen']:+9,.0f}$ "
              f"solde_neg={res['solde_negatif']:5.2f}% annee1<0={res['annee1_neg']:5.2f}% "
              f"hit_ceiling(1000/3000)={res['hit_ceiling_1000']:5.1f}%/{res['hit_ceiling_3000']:5.1f}% "
              f"B_1er_profit p50/p90={res['b_first_profit_p50']}/{res['b_first_profit_p90']} "
              f"({time.time()-t0:.0f}s)")
    return rows


if __name__ == "__main__":
    import sys
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300

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

    print(f"\n=== Sweep tailles pivot, n={n_sims} ===")
    rows = run_sweep(n_sims, blocks_A, blocks_B, market_data, excluded_map, horizon_seconds, seed_base=1000)

    out = pd.DataFrame(rows)
    out.to_csv(f"ab_taille_pivot_sweep_n{n_sims}_2026-08-19.csv", index=False)
    print(f"\nSauvegarde : ab_taille_pivot_sweep_n{n_sims}_2026-08-19.csv ({time.time()-t0:.0f}s total)")
