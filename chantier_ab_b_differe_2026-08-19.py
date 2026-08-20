"""
B en deblocage differe (seuil de reserve accumulee par A), session
2026-08-19. Reutilise chantier_ab_taille_pivot_2026-08-19.py (import via
importlib) pour la population/blocs/marche/correlation ; meme principe de
declenchement par seuil que le staggered unlock deja adopte pour la
flotte multi-firms (`ei.seq_grouped_multi`, etape_e_fleet_integration.py:
144-151, declenchement "after_count" sur franchissement de seuil de
reserve) -- adapte ici a un seuil UNIQUE pour l'ouverture de B (pas une
cascade multi-firms).

Mecanique : B n'existe pas tant que state["reserve"] (alimentee
uniquement par A tant que B n'existe pas -- meme state partage que le
moteur simultane, chantier_ab_parallele_2026-08-19.py, reserve poolee
deja retenue) n'a pas atteint le seuil. A ce moment, accB est cree
(make_acc_mf, engine_multiformat.py:246-256), son cout d'ouverture est
preleve sur la reserve (ou sur real_cash_paid si insuffisante, meme
logique que process_trade_mf:355-365), et ses trades commencent a etre
traites normalement a partir de cet instant. Les evenements B survenus
AVANT le declenchement sont perdus (B n'existait pas), pas rattrapes.
"""
import random
import time
import importlib.util

import numpy as np
import pandas as pd

_spec = importlib.util.spec_from_file_location("piv", "chantier_ab_taille_pivot_2026-08-19.py")
piv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(piv)
ab = piv.ab

THRESHOLDS = [1000.0, 2000.0, 3000.0, 5000.0]
PALIER_B_BEST = 25_000


def run_one_deferred(fmt_A, fmt_B, blocks_A, blocks_B, market_data, excluded_map, rng, horizon_seconds,
                      cost_A, cost_B, threshold, palier_A=25_000, palier_B=PALIER_B_BEST, block_indices=None):
    (trA, slA), (trB, slB) = piv._bootstrap_sequence(blocks_A, blocks_B, rng, horizon_seconds, block_indices)
    accA = ab.make_acc_mf(fmt_A, palier_A, cost_A)
    accB = None
    state = {"reserve": 0.0, "total_breaks": 0, "real_cash_paid": cost_A}

    events = [(t, "A", tr) for tr, t in zip(trA, slA)] + [(t, "B", tr) for tr, t in zip(trB, slB)]
    events.sort(key=lambda e: e[0])

    b_open_day = None
    b_first_profit_day = None
    snapshot_1y = None

    for now, which, trade in events:
        if which == "B":
            if accB is None:
                if state["reserve"] < threshold:
                    continue  # B pas encore debloque, evenement perdu
                # Declenchement : ouverture de B, cout preleve (reserve puis cash reel).
                accB = ab.make_acc_mf(fmt_B, palier_B, cost_B)
                if state["reserve"] >= cost_B:
                    state["reserve"] -= cost_B
                else:
                    shortfall = cost_B - state["reserve"]
                    state["reserve"] = 0.0
                    state["real_cash_paid"] += shortfall
                b_open_day = now / ab.DAY_SECONDS
            acc, fmt = accB, fmt_B
        else:
            acc, fmt = accA, fmt_A

        ab.process_trade_mf(acc, trade, now, fmt, state, ab.trade_risk(acc), market_data, excluded_map,
                             split_flat=ab.SPLIT_FLAT, reserve_share=ab.RESERVE_SHARE)

        if accB is not None and b_first_profit_day is None and accB["phase"] == "funded" and accB["total_funded_pnl"] > 0:
            b_first_profit_day = now / ab.DAY_SECONDS
        if snapshot_1y is None and now >= ab.YEAR_SECONDS:
            fpnl = accA["total_funded_pnl"] + (accB["total_funded_pnl"] if accB else 0.0)
            snapshot_1y = fpnl - state["real_cash_paid"]

    fpnl_final = accA["total_funded_pnl"] + (accB["total_funded_pnl"] if accB else 0.0)
    profit_net = fpnl_final - state["real_cash_paid"]
    if snapshot_1y is None:
        snapshot_1y = profit_net
    return dict(profit_net=profit_net, annee1=snapshot_1y, b_open_day=b_open_day,
                b_first_profit_day=b_first_profit_day, b_ever_opened=accB is not None)


def run_scenario_deferred(blocks_A, blocks_B, market_data, excluded_map, n_sims, horizon_seconds,
                           threshold, seed, block_indices=None, palier_B=PALIER_B_BEST):
    fmt = ab.FORMATS["Blueberry_InstantElite"]
    cost_A = piv.COST_BY_PALIER[25_000]
    cost_B = piv.COST_BY_PALIER[palier_B]
    rng = random.Random(seed)
    rows = [run_one_deferred(fmt, fmt, blocks_A, blocks_B, market_data, excluded_map, rng, horizon_seconds,
                              cost_A, cost_B, threshold, 25_000, palier_B, block_indices) for _ in range(n_sims)]
    profits = [r["profit_net"] for r in rows]
    annee1 = [r["annee1"] for r in rows]
    open_days = [r["b_open_day"] for r in rows if r["b_open_day"] is not None]
    b_days = [r["b_first_profit_day"] for r in rows if r["b_first_profit_day"] is not None]
    return dict(profit_moyen=np.mean(profits), solde_negatif=100 * np.mean([p < 0 for p in profits]),
                annee1_neg=100 * np.mean([a < 0 for a in annee1]),
                b_never_opened=100 * (1 - len(open_days) / n_sims),
                b_open_p50=np.median(open_days) if open_days else None,
                b_open_p90=np.percentile(open_days, 90) if open_days else None,
                b_first_profit_p50=np.median(b_days) if b_days else None,
                b_first_profit_p90=np.percentile(b_days, 90) if b_days else None)


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
    quarter = n_blocks // 4
    bloc1 = list(range(quarter, 2 * quarter))
    print(f"{n_blocks} blocs alignes (ancre {anchor.date()}), bloc1={bloc1} ({time.time()-t0:.0f}s)")

    market_data = ab.b6.build_market_data_with_indices()
    all_tickers = sorted(set(t["ticker"] for t in trades_A) | set(t["ticker"] for t in trades_B))
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    excluded_map = ab.precompute_correlation_pairs(all_tickers, corr_matrix, ab.CORR_THRESHOLD)

    print(f"\n=== Sweep seuils de declenchement B (n={n_sims}), plein horizon ===")
    rows = []
    for th in THRESHOLDS:
        t1 = time.time()
        res = run_scenario_deferred(blocks_A, blocks_B, market_data, excluded_map, n_sims, horizon_seconds,
                                     th, seed=5555 + int(th))
        res["threshold"] = th
        rows.append(res)
        print(f"  seuil={th:6.0f}$ profit_moy={res['profit_moyen']:+9,.0f}$ solde_neg={res['solde_negatif']:5.2f}% "
              f"annee1<0={res['annee1_neg']:5.2f}% B_ouverture p50/p90={res['b_open_p50']}/{res['b_open_p90']}j "
              f"jamais_ouvert={res['b_never_opened']:.1f}% ({time.time()-t1:.0f}s)")

    print(f"\n=== Meme sweep, bloc1 seul (regime dur) ===")
    rows_bloc1 = []
    for th in THRESHOLDS:
        t1 = time.time()
        res = run_scenario_deferred(blocks_A, blocks_B, market_data, excluded_map, n_sims, horizon_seconds,
                                     th, seed=6666 + int(th), block_indices=bloc1)
        res["threshold"] = th
        rows_bloc1.append(res)
        print(f"  seuil={th:6.0f}$ profit_moy={res['profit_moyen']:+9,.0f}$ solde_neg={res['solde_negatif']:5.2f}% "
              f"annee1<0={res['annee1_neg']:5.2f}% B_ouverture p50/p90={res['b_open_p50']}/{res['b_open_p90']}j "
              f"jamais_ouvert={res['b_never_opened']:.1f}% ({time.time()-t1:.0f}s)")

    pd.DataFrame(rows).to_csv(f"ab_b_differe_full_n{n_sims}_2026-08-19.csv", index=False)
    pd.DataFrame(rows_bloc1).to_csv(f"ab_b_differe_bloc1_n{n_sims}_2026-08-19.csv", index=False)
    print(f"\nSauvegardes. ({time.time()-t0:.0f}s total)")
