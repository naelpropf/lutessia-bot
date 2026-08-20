"""Stress-test H1/H2+4blocs pour le retest ADX/rr_tp1-sizing sur Config 2
(chantier routage A/B metaux, 2026-08-19). Reutilise les populations deja
construites par chantier_gold_silver_adx_sizing_retest_2026-08-19.py
(baseline_config2 avec adx_at_entry NON retire cette fois, pour pouvoir
refiltrer par sous-periode -- le filtre ADX doit etre APPLIQUE PAR
sous-periode, pas globalement puis tronque, pour rester fidele a la
methode habituelle du projet)."""
import importlib.util
import time

import numpy as np
import pandas as pd

_spec_retest = importlib.util.spec_from_file_location("gsretest", "chantier_gold_silver_adx_sizing_retest_2026-08-19.py")
gsr = importlib.util.module_from_spec(_spec_retest)
_spec_retest.loader.exec_module(gsr)

gse = gsr.gse


def subperiod_split(pop, n_parts):
    pop = pop.sort_values("date_creation").reset_index(drop=True)
    return [p.reset_index(drop=True) for p in np.array_split(pop, n_parts)]


def run_lever_on_pop(pop_A, pop_B, size_func_B=None, n_sims=100, seed=13579):
    if len(pop_A) == 0 or len(pop_B) == 0:
        return None
    trades_A, dates_A = gse.df_to_trades(pop_A)
    trades_B, dates_B = gse.df_to_trades(pop_B)
    anchor = min(dates_A.min(), dates_B.min())
    slots_A = [(d - anchor).total_seconds() for d in dates_A]
    slots_B = [(d - anchor).total_seconds() for d in dates_B]
    horizon_seconds = max(slots_A[-1], slots_B[-1])
    n_blocks = int(horizon_seconds // gse.BLOCK_SECONDS) + 1
    if n_blocks < 2:
        return None
    blocks_A = gse.build_aligned_blocks(trades_A, slots_A, gse.BLOCK_SECONDS, n_blocks)
    blocks_B = gse.build_aligned_blocks(trades_B, slots_B, gse.BLOCK_SECONDS, n_blocks)

    market_data = gse.load_common()
    all_tickers = sorted(set(t["ticker"] for t in trades_A) | set(t["ticker"] for t in trades_B))
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    from monte_carlo_simulation import precompute_correlation_pairs
    from scaling_simulation import CORR_THRESHOLD
    excluded_map = precompute_correlation_pairs(all_tickers, corr_matrix, CORR_THRESHOLD)
    from engine_multiformat import FORMATS, make_acc_mf
    fmt = FORMATS["Blueberry_InstantElite"]
    cost = fmt["price"][gse.PALIER]

    import random
    rng = random.Random(seed)
    profits = []
    for _ in range(n_sims):
        (trA, slA), (trB, slB) = gse.build_joint_bootstrap_sequence(blocks_A, blocks_B, gse.BLOCK_SECONDS, rng, horizon_seconds)
        accA = make_acc_mf(fmt, gse.PALIER, cost)
        accB = make_acc_mf(fmt, gse.PALIER, cost)
        state = {"reserve": 0.0, "total_breaks": 0, "real_cash_paid": 2 * cost, "overflow_to_A": 0}
        events = [(t, "A", tr) for tr, t in zip(trA, slA)] + [(t, "B", tr) for tr, t in zip(trB, slB)]
        events.sort(key=lambda e: e[0])
        for now, which, trade in events:
            if which == "B" and trade["ticker"] in gsr.metal_set_global:
                gse.route_metal_config2(accA, accB, trade, now, fmt, fmt, state, market_data, excluded_map)
            else:
                acc = accA if which == "A" else accB
                risk = gse.trade_risk(acc)
                if which == "B" and size_func_B is not None:
                    risk *= size_func_B(trade)
                gse.process_trade_corr_swap_rr(acc, trade, now, fmt, state, risk, market_data, excluded_map,
                                                split_flat=gse.SPLIT_FLAT, reserve_share=gse.RESERVE_SHARE,
                                                routing_field=gse.ROUTING_FIELD)
        profits.append(accA["total_funded_pnl"] + accB["total_funded_pnl"] - state["real_cash_paid"])
    return dict(n=n_sims, profit_moyen=np.mean(profits))


def main():
    import sys
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 100

    pop_A = pd.read_csv("chantier_gold_silver_pop_A_config0_2026-08-19.csv")
    pop_B_full = pd.concat([
        pd.read_csv("chantier_gold_silver_pop_B_config2_adx_baseline_2026-08-19.csv"),
    ], ignore_index=True)
    for df in (pop_A, pop_B_full):
        df["date_creation"] = pd.to_datetime(df["date_creation"])
        df["resolution_time_est"] = pd.to_datetime(df["resolution_time_est"])

    oa_all = pd.read_csv("chantier_gold_silver_pop_metaux_all_2026-08-19.csv")
    gsr.metal_set_global = set(oa_all["ticker"].unique())

    # Re-attache adx_at_entry par sous-periode (recalcul fidele : ADX doit
    # etre recalcule sur CHAQUE sous-population tronquee, pas un simple
    # decoupage d'une colonne globale precalculee sur toute la population --
    # meme convention que le reste du projet, cf. chantier_stresstest_
    # pisteAB_2026-08-19.py:753-761, ou les sous-periodes sont des tranches
    # chronologiques de la population COMPLETE avant tout traitement).
    is_metal = pop_B_full["ticker"].isin(gsr.metal_set_global)
    pop_B_fx = pop_B_full[~is_metal].copy()
    pop_B_metaux = pop_B_full[is_metal].copy()

    def size_func_rrtp1(trade):
        return gsr.RR_TP1_SIZING_MULT if trade["rr_tp1"] <= gsr.RR_TP1_SIZING_TH else 1.0

    subsA = {"H1": subperiod_split(pop_A, 2)[0], "H2": subperiod_split(pop_A, 2)[1]}
    for i, p in enumerate(subperiod_split(pop_A, 4)):
        subsA[f"bloc{i}"] = p
    subsB_fx = {"H1": subperiod_split(pop_B_fx, 2)[0], "H2": subperiod_split(pop_B_fx, 2)[1]}
    for i, p in enumerate(subperiod_split(pop_B_fx, 4)):
        subsB_fx[f"bloc{i}"] = p
    subsB_metaux = {"H1": subperiod_split(pop_B_metaux, 2)[0], "H2": subperiod_split(pop_B_metaux, 2)[1]}
    for i, p in enumerate(subperiod_split(pop_B_metaux, 4)):
        subsB_metaux[f"bloc{i}"] = p

    print("Calcul ADX par sous-periode (forex/indices + metaux)...")
    all_rows = []
    t0 = time.time()
    for sp in subsA:
        candles_fx = gsr.build_candles_with_adx_forex_indices(subsB_fx[sp]) if len(subsB_fx[sp]) else {}
        candles_mx = gsr.build_candles_with_adx_metaux(subsB_metaux[sp]) if len(subsB_metaux[sp]) else {}
        fx_adx = gsr.compute_adx_at_entry(subsB_fx[sp], candles_fx) if len(subsB_fx[sp]) else subsB_fx[sp]
        mx_adx = gsr.compute_adx_at_entry(subsB_metaux[sp], candles_mx) if len(subsB_metaux[sp]) else subsB_metaux[sp]
        pop_B_sp_full = pd.concat([fx_adx, mx_adx], ignore_index=True).sort_values("date_creation").reset_index(drop=True)
        pop_B_sp_baseline = pop_B_sp_full.drop(columns=["adx_at_entry"], errors="ignore")
        pop_B_sp_adx = pop_B_sp_full[~(pop_B_sp_full.get("adx_at_entry", pd.Series(dtype=float)) > gsr.ADX_TH)].drop(
            columns=["adx_at_entry"], errors="ignore").reset_index(drop=True)

        res_base = run_lever_on_pop(subsA[sp], pop_B_sp_baseline, n_sims=n_sims)
        res_adx = run_lever_on_pop(subsA[sp], pop_B_sp_adx, n_sims=n_sims)
        res_rrtp1 = run_lever_on_pop(subsA[sp], pop_B_sp_baseline, size_func_B=size_func_rrtp1, n_sims=n_sims)

        if res_base is None:
            print(f"  [{sp}] insuffisant, ignore")
            continue
        d_adx = (res_adx["profit_moyen"] - res_base["profit_moyen"]) / abs(res_base["profit_moyen"]) * 100 if res_adx else float("nan")
        d_rrtp1 = (res_rrtp1["profit_moyen"] - res_base["profit_moyen"]) / abs(res_base["profit_moyen"]) * 100 if res_rrtp1 else float("nan")
        print(f"  [{sp}, n={n_sims}] baseline={res_base['profit_moyen']:+,.0f}$ | "
              f"adx={res_adx['profit_moyen']:+,.0f}$ ({d_adx:+.1f}%) | "
              f"rrtp1={res_rrtp1['profit_moyen']:+,.0f}$ ({d_rrtp1:+.1f}%)")
        all_rows.append(dict(subperiod=sp, baseline=res_base["profit_moyen"],
                              adx=res_adx["profit_moyen"] if res_adx else None, d_adx_pct=d_adx,
                              rrtp1=res_rrtp1["profit_moyen"] if res_rrtp1 else None, d_rrtp1_pct=d_rrtp1))
        pd.DataFrame(all_rows).to_csv("chantier_gold_silver_adx_sizing_stresstest_2026-08-19.csv", index=False)

    print(f"\nTermine en {time.time()-t0:.0f}s.")


if __name__ == "__main__":
    main()
