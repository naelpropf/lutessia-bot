"""
Chantier B4-E (2026-08-19) -- caracterisation structurelle complete A vs B,
8 axes, population complete (indices inclus) des deux cotes : A=742
(RR>=1,35, reconstruite comme chantier_reference_A_indices_2026-08-18.py),
B=571 (tout-indices->B, build_pop_B deja valide).

Objectif : cartographier, pas trancher -- signale toute divergence notable
sans juger de son exploitabilite ici.

N'importe pas ce script directement (convention du projet).
"""
import importlib.util

import numpy as np
import pandas as pd
from scipy import stats

import tp_sequence_analysis as tpseq

ISO_SCRIPT = "chantier_strategie_b_isolation_indices_2026-08-18.py"
spec = importlib.util.spec_from_file_location("iso_b4e", ISO_SCRIPT)
iso = importlib.util.module_from_spec(spec)
spec.loader.exec_module(iso)

REFA_SCRIPT = "chantier_reference_A_indices_2026-08-18.py"
spec2 = importlib.util.spec_from_file_location("refa_b4e", REFA_SCRIPT)
refa = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(refa)

ADX_SCRIPT = "edge_adx_atr_filters_2026-08-11.py"
spec3 = importlib.util.spec_from_file_location("adx_b4e", ADX_SCRIPT)
adx_mod = importlib.util.module_from_spec(spec3)
spec3.loader.exec_module(adx_mod)

INDEX_KEYWORDS = ["DAX40", "S&P500", "NASDAQ100"]

RAW = pd.read_csv("historique_lutessia_15k_force.csv")
RAW["date_creation"] = pd.to_datetime(RAW["date_creation"])
RAW_MAP = RAW.drop_duplicates(subset=["ticker", "date_creation"]).set_index(["ticker", "date_creation"])


def attach_raw_cols(pop, cols):
    pop = pop.copy()
    idx = pd.MultiIndex.from_arrays([pop["ticker"], pop["date_creation"]])
    for c in cols:
        if c not in pop.columns:
            pop[c] = idx.map(RAW_MAP[c])
    return pop


def outcome_r(pop):
    return np.where(pop["statut_final"] == "OBJECTIF ATTEINT", pop["r_trailing"], -1.0)


def build_pop_A():
    pop_A_fx = refa.build_population_with_trailing("fixed", 0.15, min_rr=1.35, verbose=False)
    pop_idx_all = refa.compute_payoff(refa.load_index_population_full())
    pop_idx_high = pop_idx_all[pop_idx_all["rr_tp1"] >= 1.35].reset_index(drop=True)
    keep_cols = ["date_creation", "ticker", "rr_tp1", "rr_tp2", "statut_final", "r_trailing"]
    pop_A = pd.concat([pop_A_fx[keep_cols], pop_idx_high[keep_cols]], ignore_index=True)
    return pop_A


def dist_stats(series, label):
    return dict(label=label, n=len(series), moyenne=series.mean(), mediane=series.median(),
                ecart_type=series.std(), skew=series.skew(), p10=series.quantile(.10),
                p90=series.quantile(.90))


def print_dist_row(d):
    print(f"  {d['label']:12s} n={d['n']:4d}  moyenne={d['moyenne']:+.4f}  mediane={d['mediane']:+.4f}  "
          f"ecart-type={d['ecart_type']:.4f}  skew={d['skew']:+.3f}  P10={d['p10']:+.4f}  P90={d['p90']:+.4f}")


if __name__ == "__main__":
    pop_A = build_pop_A()
    pop_B = iso.build_pop_B("tout_indices")
    print(f"[verif] population A : n={len(pop_A)} | population B : n={len(pop_B)}")

    # ================================================================
    print("\n" + "=" * 78)
    print("AXE 1 -- composition par actif")
    print("=" * 78)
    for label, pop in [("A", pop_A), ("B", pop_B)]:
        is_idx = pop["ticker"].str.contains("|".join(INDEX_KEYWORDS), case=False, na=False)
        print(f"\n  {label} : forex={ (~is_idx).sum()} ({(~is_idx).mean()*100:.1f}%)  "
              f"indices={is_idx.sum()} ({is_idx.mean()*100:.1f}%)")
        print(f"  {label} repartition par ticker :")
        vc = pop["ticker"].value_counts()
        for t, n in vc.items():
            print(f"    {t:<38s} n={n:4d} ({n/len(pop)*100:.1f}%)")

    # ================================================================
    print("\n" + "=" * 78)
    print("AXE 2 -- distribution rr_tp1")
    print("=" * 78)
    for label, pop in [("A", pop_A), ("B", pop_B)]:
        print_dist_row(dist_stats(pop["rr_tp1"], label))

    # ================================================================
    print("\n" + "=" * 78)
    print("AXE 3 -- distribution rr_tp2")
    print("=" * 78)
    for label, pop in [("A", pop_A), ("B", pop_B)]:
        print_dist_row(dist_stats(pop["rr_tp2"], label))

    # ================================================================
    print("\n" + "=" * 78)
    print("AXE 4 -- distances SL/TP1/TP2 en %")
    print("=" * 78)
    pop_A2 = attach_raw_cols(pop_A, ["prix_entree", "stop_loss_init", "tp1_init", "tp2_init"])
    pop_B2 = attach_raw_cols(pop_B, ["tp1_init", "tp2_init"])  # prix_entree/stop_loss_init deja presents
    for label, pop in [("A", pop_A2), ("B", pop_B2)]:
        d_sl = (pop["prix_entree"] - pop["stop_loss_init"]).abs() / pop["prix_entree"] * 100
        d_tp1 = (pop["tp1_init"] - pop["prix_entree"]).abs() / pop["prix_entree"] * 100
        d_tp2 = (pop["tp2_init"] - pop["prix_entree"]).abs() / pop["prix_entree"] * 100
        print(f"\n  {label} distance_SL%  :", end=" ")
        print_dist_row(dist_stats(d_sl, "SL%"))
        print(f"  {label} distance_TP1% :", end=" ")
        print_dist_row(dist_stats(d_tp1, "TP1%"))
        print(f"  {label} distance_TP2% :", end=" ")
        print_dist_row(dist_stats(d_tp2, "TP2%"))

    # ================================================================
    print("\n" + "=" * 78)
    print("AXE 5 -- repartition horaire/session (UTC)")
    print("=" * 78)
    for label, pop in [("A", pop_A), ("B", pop_B)]:
        hour = pop["date_creation"].dt.hour
        session3 = pd.cut(hour, [-1, 8, 16, 24], labels=["Asie(0-8)", "London(8-16)", "US(16-24)"])
        print(f"\n  {label} :")
        for name, n in session3.value_counts().sort_index().items():
            print(f"    {name:<15s} n={n:4d} ({n/len(pop)*100:.1f}%)")

    # ================================================================
    print("\n" + "=" * 78)
    print("AXE 6 -- score Force")
    print("=" * 78)
    pop_A3 = attach_raw_cols(pop_A, ["score_force"])
    pop_B3 = attach_raw_cols(pop_B, ["score_force"])
    for label, pop in [("A", pop_A3), ("B", pop_B3)]:
        print_dist_row(dist_stats(pop["score_force"], label))
    ks_force = stats.ks_2samp(pop_A3["score_force"], pop_B3["score_force"])
    print(f"  KS test (forme de distribution, A vs B) : stat={ks_force.statistic:.3f} p={ks_force.pvalue:.4f}")

    # ================================================================
    print("\n" + "=" * 78)
    print("AXE 7 -- duree de vie du trade (entree -> resolution)")
    print("=" * 78)
    pop_B4 = pop_B.copy()
    pop_B4["duree_h"] = (pop_B4["resolution_time_est"] - pop_B4["date_creation"]).dt.total_seconds() / 3600
    print_dist_row(dist_stats(pop_B4["duree_h"], "B (h)"))
    print("  A : resolution_time_est non conserve dans le pipeline standard -- calcul direct via "
          "build_population_with_trailing (colonne absente de build_realistic_payoff_population de base).")
    pop_A_full = refa.build_population_with_trailing("fixed", 0.15, min_rr=1.35, verbose=False)
    if "resolution_time_est" in pop_A_full.columns:
        pop_A_full["duree_h"] = (pop_A_full["resolution_time_est"] - pop_A_full["date_creation"]).dt.total_seconds() / 3600
        print_dist_row(dist_stats(pop_A_full["duree_h"], "A_fx (h)"))
        print("  (A_fx = forex seul, indices non recalcules ici -- ordre de grandeur suffisant pour la comparaison)")

    # ================================================================
    print("\n" + "=" * 78)
    print("AXE 8 -- volatilite au signal (ADX14 a l'entree)")
    print("=" * 78)
    for label, pop_src in [("A", pop_A), ("B", pop_B)]:
        pop = pop_src.copy()
        pop["yahoo_symbol"] = pop["ticker"].apply(tpseq.ticker_to_yahoo_symbol)
        unique_symbols = sorted(pop["yahoo_symbol"].dropna().unique())
        indic_by_symbol = {}
        for symbol in unique_symbols:
            candles = tpseq.fetch_h1_history(symbol, pop["date_creation"].min().to_pydatetime(),
                                              pd.Timestamp.utcnow().tz_localize(None).to_pydatetime())
            if candles is None or candles.empty:
                continue
            c = adx_mod.compute_atr(candles)
            c = adx_mod.compute_adx(c)
            indic_by_symbol[symbol] = c.sort_values("datetime").reset_index(drop=True)
        adx_vals = []
        for _, row in pop.iterrows():
            candles = indic_by_symbol.get(row["yahoo_symbol"])
            if candles is None:
                adx_vals.append(np.nan)
                continue
            prior = candles[candles["datetime"] <= row["date_creation"]]
            adx_vals.append(prior["adx"].iloc[-1] if not prior.empty and "adx" in prior else np.nan)
        pop["adx_at_entry"] = adx_vals
        covered = pop.dropna(subset=["adx_at_entry"])
        print(f"\n  {label} couverture ADX : {len(covered)}/{len(pop)} ({len(covered)/len(pop)*100:.1f}%)")
        print_dist_row(dist_stats(covered["adx_at_entry"], label))

    print("\nTermine.")
