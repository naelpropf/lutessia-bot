"""Etape 2 : retest ADX>32,27 et sizing rr_tp1<=1,25 sur Config 2 (chantier
routage A/B metaux, 2026-08-19) -- ces 2 leviers avaient ete REJETES le
19/08 UNIQUEMENT a cause de la contrainte de frequence sur B seul (76,7% de
A, registre_strategie_trading.md S5.9) ; Config 2 porte B a ~171,6% (meme
population que Config 0, l'overflow ne fait que rediriger l'exces
bloque-correlation vers A). Retest objectif, sans presumer du resultat.

Definition ADX -- IDENTIQUE, aucune modification, a celle deja utilisee sur
B forex/indices (chantier_b6_montecarlo_2026-08-19.py:796-827) :
  - compute_adx(candles, period=14) (edge_adx_atr_filters_2026-08-11.py:48-
    70), Wilder standard (+DI/-DI/DX/ADX en EMA alpha=1/14), APPLIQUE ICI TEL
    QUEL aux bougies H1 synthetiques metaux (gold_silver_yahoo_mapping_2026-
    08-19.py) -- aucune adaptation de la formule, seule la SOURCE de bougies
    change (synthetique au lieu de directe Yahoo, deja verifiee/cachee).
  - adx_at_entry = derniere valeur ADX connue A OU AVANT date_creation
    (pas de lookahead, edge_adx_atr_filters_2026-08-11.py:100-109 /
    chantier_b6_montecarlo_2026-08-19.py:818-821).
  - Seuil ADX_TH=32,268 (chantier_b6_montecarlo_2026-08-19.py:813), EXCLUSION
    stricte si adx_at_entry>seuil ; trade SANS donnee ADX = PAS exclu (choix
    deja explicite, chantier_b6_montecarlo_2026-08-19.py:816-817).

Definition sizing rr_tp1<=1,25 -- ISOLE (pas empile sur le boost rr_tp2>=8
->x1,6 de S2.35 comme dans le test original 19/08, chantier_b6_montecarlo_
2026-08-19.py:836-837) : le moteur A+B simplifie de ce chantier (chantier_
gold_silver_ab_engine_2026-08-19.py) N'A PAS cette couche de sizing dans SA
PROPRE baseline Config 0/1/2 deja mesuree -- l'ajouter ici la ferait
apparaitre comme un gain artefactuel du sizing rr_tp1 combine avec un
mecanisme jamais teste dans ce chantier. Isole = comparaison correcte au
sein de CE chantier, mais PAS un remplacement du protocole officiel S1.8.
Multiplicateur x0,7 (identique a S5.9) sur B UNIQUEMENT (A n'est jamais
concerne par ce levier, ni dans le test original ni ici).

Protocole : n=600, 4 plafonds (non-discriminants dans ce moteur, deja
documente/verifie a l'Etape 3), 4 axes, stress-test H1/H2+4blocs.
"""
import importlib.util
import time

import numpy as np
import pandas as pd

import tp_sequence_analysis as tpseq

_spec_gs = importlib.util.spec_from_file_location("gsmap", "gold_silver_yahoo_mapping_2026-08-19.py")
gsmap = importlib.util.module_from_spec(_spec_gs)
_spec_gs.loader.exec_module(gsmap)

_spec_adx = importlib.util.spec_from_file_location("adxmod", "edge_adx_atr_filters_2026-08-11.py")
adxmod = importlib.util.module_from_spec(_spec_adx)
_spec_adx.loader.exec_module(adxmod)

_spec_eng = importlib.util.spec_from_file_location("gsengine", "chantier_gold_silver_ab_engine_2026-08-19.py")
gse = importlib.util.module_from_spec(_spec_eng)
_spec_eng.loader.exec_module(gse)

ADX_TH = 32.268
RR_TP1_SIZING_TH = 1.25
RR_TP1_SIZING_MULT = 0.7


def compute_adx_at_entry(pop, candles_by_ticker):
    """Meme logique EXACTE que chantier_b6_montecarlo_2026-08-19.py:814-823,
    generalisee a une source de bougies dict-par-ticker (pas seulement
    yahoo_symbol -- les tickers metaux n'ont pas de yahoo_symbol standard,
    cf. Etape 0 de la session precedente)."""
    adx_vals = []
    for _, row in pop.iterrows():
        candles = candles_by_ticker.get(row["ticker"])
        if candles is None or candles.empty:
            adx_vals.append(np.nan)
            continue
        prior = candles[candles["datetime"] <= row["date_creation"]]
        if prior.empty or "adx" not in prior:
            adx_vals.append(np.nan)
            continue
        adx_vals.append(prior["adx"].iloc[-1])
    pop = pop.copy()
    pop["adx_at_entry"] = adx_vals
    return pop


def build_candles_with_adx_forex_indices(pop):
    unique_symbols = sorted(set(tpseq.ticker_to_yahoo_symbol(t) for t in pop["ticker"].unique()) - {None})
    by_ticker = {}
    ticker_to_symbol = {t: tpseq.ticker_to_yahoo_symbol(t) for t in pop["ticker"].unique()}
    candles_by_symbol = {}
    for symbol in unique_symbols:
        c = tpseq.fetch_h1_history(symbol, pop["date_creation"].min().to_pydatetime(),
                                    pd.Timestamp.utcnow().tz_localize(None).to_pydatetime())
        if c is None or c.empty:
            continue
        candles_by_symbol[symbol] = adxmod.compute_adx(c).sort_values("datetime").reset_index(drop=True)
    for t, sym in ticker_to_symbol.items():
        if sym in candles_by_symbol:
            by_ticker[t] = candles_by_symbol[sym]
    return by_ticker


def build_candles_with_adx_metaux(pop):
    unique_tickers = sorted(pop["ticker"].unique())
    start_dt = pop["date_creation"].min().to_pydatetime()
    end_dt = pd.Timestamp.utcnow().tz_localize(None).to_pydatetime()
    by_ticker = {}
    for t in unique_tickers:
        c = gsmap.build_synthetic_candles(t, start_dt, end_dt)
        if c is None or c.empty:
            continue
        by_ticker[t] = adxmod.compute_adx(c).sort_values("datetime").reset_index(drop=True)
    return by_ticker


def main():
    import sys
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 600

    print("Construction population B Config 2 (identique a Config 0 : B0 + tous metaux)...")
    pop_B = pd.read_csv("chantier_gold_silver_pop_B_config0_2026-08-19.csv")
    pop_A = pd.read_csv("chantier_gold_silver_pop_A_config0_2026-08-19.csv")
    oa_all = pd.read_csv("chantier_gold_silver_pop_metaux_all_2026-08-19.csv")
    metal_set = set(oa_all["ticker"].unique())
    for df in (pop_A, pop_B):
        df["date_creation"] = pd.to_datetime(df["date_creation"])
        df["resolution_time_est"] = pd.to_datetime(df["resolution_time_est"])

    is_metal = pop_B["ticker"].isin(metal_set)
    pop_B_fximd = pop_B[~is_metal].copy()
    pop_B_metaux = pop_B[is_metal].copy()

    print(f"B forex/indices : {len(pop_B_fximd)} | B metaux : {len(pop_B_metaux)}")

    print("\nCalcul ADX(14) forex/indices (formule inchangee, edge_adx_atr_filters_2026-08-11.py:48-70)...")
    candles_fx = build_candles_with_adx_forex_indices(pop_B_fximd)
    pop_B_fximd = compute_adx_at_entry(pop_B_fximd, candles_fx)

    print("\nCalcul ADX(14) metaux (memes bougies synthetiques que le pipeline duree/trailing)...")
    candles_metaux = build_candles_with_adx_metaux(pop_B_metaux)
    pop_B_metaux = compute_adx_at_entry(pop_B_metaux, candles_metaux)

    pop_B_adx_full = pd.concat([pop_B_fximd, pop_B_metaux], ignore_index=True).sort_values("date_creation").reset_index(drop=True)
    n_couverts = pop_B_adx_full["adx_at_entry"].notna().sum()
    n_exclus = (pop_B_adx_full["adx_at_entry"] > ADX_TH).sum()
    print(f"\n[verif] ADX couvert : {n_couverts}/{len(pop_B_adx_full)} "
          f"({n_couverts/len(pop_B_adx_full)*100:.1f}%) -- dont metaux couverts : "
          f"{pop_B_metaux['adx_at_entry'].notna().sum()}/{len(pop_B_metaux)}")
    print(f"[verif] Trades identifies a exclure (adx_at_entry>{ADX_TH}) : {n_exclus}/{len(pop_B_adx_full)}")

    pop_B_baseline = pop_B_adx_full.drop(columns=["adx_at_entry"])
    pop_B_adx_filtered = pop_B_adx_full[~(pop_B_adx_full["adx_at_entry"] > ADX_TH)].drop(columns=["adx_at_entry"]).reset_index(drop=True)
    print(f"[verif] Population apres filtre ADX : {len(pop_B_adx_filtered)}/{len(pop_B_baseline)} "
          f"({len(pop_B_baseline)-len(pop_B_adx_filtered)} exclus)")

    pop_B_baseline.to_csv("chantier_gold_silver_pop_B_config2_adx_baseline_2026-08-19.csv", index=False)
    pop_B_adx_filtered.to_csv("chantier_gold_silver_pop_B_config2_adx_filtered_2026-08-19.csv", index=False)

    print(f"\n{'='*78}\nMonte Carlo n={n_sims} : baseline vs ADX-filtre vs rr_tp1-sizing (Config 2, A+B)\n{'='*78}")

    def run_lever(lever_name, pop_B_variant, size_func_B=None):
        trades_A, dates_A = gse.df_to_trades(pop_A)
        trades_B, dates_B = gse.df_to_trades(pop_B_variant)
        anchor = min(dates_A.min(), dates_B.min())
        slots_A = [(d - anchor).total_seconds() for d in dates_A]
        slots_B = [(d - anchor).total_seconds() for d in dates_B]
        horizon_seconds = gse.HORIZON_YEARS * gse.YEAR_SECONDS
        n_blocks = int(max(slots_A[-1], slots_B[-1]) // gse.BLOCK_SECONDS) + 1
        blocks_A = gse.build_aligned_blocks(trades_A, slots_A, gse.BLOCK_SECONDS, n_blocks)
        blocks_B = gse.build_aligned_blocks(trades_B, slots_B, gse.BLOCK_SECONDS, n_blocks)

        market_data = gse.load_common()
        all_tickers = sorted(set(t["ticker"] for t in trades_A) | set(t["ticker"] for t in trades_B))
        corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
        from monte_carlo_simulation import precompute_correlation_pairs
        from scaling_simulation import CORR_THRESHOLD
        excluded_map = precompute_correlation_pairs(all_tickers, corr_matrix, CORR_THRESHOLD)

        from engine_multiformat import FORMATS
        fmt = FORMATS["Blueberry_InstantElite"]
        cost = fmt["price"][gse.PALIER]

        import random
        rng = random.Random(13579)
        rows = []
        for _ in range(n_sims):
            (trA, slA), (trB, slB) = gse.build_joint_bootstrap_sequence(blocks_A, blocks_B, gse.BLOCK_SECONDS, rng, horizon_seconds)
            from engine_multiformat import make_acc_mf
            accA = make_acc_mf(fmt, gse.PALIER, cost)
            accB = make_acc_mf(fmt, gse.PALIER, cost)
            state = {"reserve": 0.0, "total_breaks": 0, "real_cash_paid": 2 * cost, "overflow_to_A": 0}
            events = [(t, "A", tr) for tr, t in zip(trA, slA)] + [(t, "B", tr) for tr, t in zip(trB, slB)]
            events.sort(key=lambda e: e[0])
            hit_ceiling = {c: False for c in gse.CEILINGS}
            snapshot_1y = None
            for now, which, trade in events:
                if which == "B" and trade["ticker"] in metal_set:
                    gse.route_metal_config2(accA, accB, trade, now, fmt, fmt, state, market_data, excluded_map)
                else:
                    acc = accA if which == "A" else accB
                    risk = gse.trade_risk(acc)
                    if which == "B" and size_func_B is not None:
                        risk *= size_func_B(trade)
                    gse.process_trade_corr_swap_rr(acc, trade, now, fmt, state, risk, market_data, excluded_map,
                                                    split_flat=gse.SPLIT_FLAT, reserve_share=gse.RESERVE_SHARE,
                                                    routing_field=gse.ROUTING_FIELD)
                for c in gse.CEILINGS:
                    if state["reserve"] >= c:
                        hit_ceiling[c] = True
                if snapshot_1y is None and now >= gse.YEAR_SECONDS:
                    snapshot_1y = accA["total_funded_pnl"] + accB["total_funded_pnl"] - state["real_cash_paid"]
            fpnl = accA["total_funded_pnl"] + accB["total_funded_pnl"]
            profit_net = fpnl - state["real_cash_paid"]
            rows.append(dict(profit_net=profit_net, annee1=snapshot_1y if snapshot_1y is not None else profit_net,
                              hit_ceiling=hit_ceiling))
        profits = np.array([r["profit_net"] for r in rows])
        annee1 = np.array([r["annee1"] for r in rows])
        out = dict(lever=lever_name, n=n_sims, profit_moyen=profits.mean(), profit_median=np.median(profits),
                   solde_negatif=100 * np.mean(profits < 0), annee1_neg=100 * np.mean(annee1 < 0))
        for c in gse.CEILINGS:
            out[f"hit_ceiling_{c:.0f}"] = 100 * np.mean([r["hit_ceiling"][c] for r in rows])
        return out

    def size_func_rrtp1(trade):
        return RR_TP1_SIZING_MULT if trade["rr_tp1"] <= RR_TP1_SIZING_TH else 1.0

    results = []
    t0 = time.time()
    r = run_lever("baseline_config2", pop_B_baseline)
    results.append(r)
    print(f"[baseline_config2] profit_moy={r['profit_moyen']:+,.0f}$ solde_neg={r['solde_negatif']:.2f}% "
          f"annee1<0={r['annee1_neg']:.2f}% ({time.time()-t0:.0f}s)")

    t0 = time.time()
    r = run_lever("adx_filtre", pop_B_adx_filtered)
    results.append(r)
    print(f"[adx_filtre] profit_moy={r['profit_moyen']:+,.0f}$ solde_neg={r['solde_negatif']:.2f}% "
          f"annee1<0={r['annee1_neg']:.2f}% ({time.time()-t0:.0f}s)")

    t0 = time.time()
    r = run_lever("rrtp1_sizing", pop_B_baseline, size_func_B=size_func_rrtp1)
    results.append(r)
    print(f"[rrtp1_sizing] profit_moy={r['profit_moyen']:+,.0f}$ solde_neg={r['solde_negatif']:.2f}% "
          f"annee1<0={r['annee1_neg']:.2f}% ({time.time()-t0:.0f}s)")

    pd.DataFrame(results).to_csv(f"chantier_gold_silver_adx_sizing_retest_n{n_sims}_2026-08-19.csv", index=False)
    print("\nSauvegarde : chantier_gold_silver_adx_sizing_retest_n{}_2026-08-19.csv".format(n_sims))


if __name__ == "__main__":
    main()
