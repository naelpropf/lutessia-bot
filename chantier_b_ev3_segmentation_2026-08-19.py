"""
Chantier B-EV, Chantier 3 (2026-08-19) -- segmentation EV sur B (population
actuelle, 571 trades, avec indices) pour les 4 variables deja testees sur A
(chantier_segmentation_variables_2026-08-17.py) : session horaire, asset_class,
distance_SL%, ADX(14). B a un profil different de A (winrate 49,6% vs 39,5%,
EV +0,801R vs +0,893R) -- verifie si un signal invisible sur A apparait ici.

asset_class ECARTE IMMEDIATEMENT (pas de calcul necessaire) : verifie sur le
CSV source (`historique_lutessia_15k_force.csv`), colonne 'asset_class' a une
SEULE valeur ('FX/Indices') sur les 1966 lignes -- non discriminant par
construction, meme conclusion que sur A (registre : "asset_class
inutilisable/une seule categorie").

Reutilise build_pop_B("tout_indices") (chantier_strategie_b_isolation_
indices_2026-08-18.py, deja valide/deduplique) pour la population de base.

N'importe pas ce script directement (convention du projet).
"""
import importlib.util

import numpy as np
import pandas as pd

import tp_sequence_analysis as tpseq

ISO_SCRIPT = "chantier_strategie_b_isolation_indices_2026-08-18.py"
spec = importlib.util.spec_from_file_location("iso_b_ev3", ISO_SCRIPT)
iso = importlib.util.module_from_spec(spec)
spec.loader.exec_module(iso)

ADX_SCRIPT = "edge_adx_atr_filters_2026-08-11.py"
spec2 = importlib.util.spec_from_file_location("adx_mod_ev3", ADX_SCRIPT)
adx_mod = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(adx_mod)


def bootstrap_ci(values, n_boot=5000, seed=9999):
    rng = np.random.default_rng(seed)
    arr = values.to_numpy()
    n = len(arr)
    if n == 0:
        return (float("nan"), float("nan"))
    means = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, n, n)
        means[i] = arr[idx].mean()
    return np.percentile(means, 2.5), np.percentile(means, 97.5)


def outcome_r(pop):
    return np.where(pop["statut_final"] == "OBJECTIF ATTEINT", pop["r_trailing"], -1.0)


def report_segment_ev(pop, r_col, col, is_categorical=False, bins=None):
    global_ev = pop[r_col].mean()
    ci_low, ci_high = bootstrap_ci(pop[r_col])
    print(f"EV globale (n={len(pop)}) = {global_ev:+.3f}R  IC95%=[{ci_low:+.3f},{ci_high:+.3f}]")
    if is_categorical:
        groups = pop.groupby(col, observed=True)
    else:
        pop = pop.copy()
        if isinstance(bins, list):
            pop["_bin"] = pd.cut(pop[col], bins)
        elif bins:
            pop["_bin"] = pd.qcut(pop[col], bins, duplicates="drop")
        else:
            pop["_bin"] = pop[col]
        groups = pop.groupby("_bin", observed=True)
    flagged = []
    for name, sub in groups:
        n = len(sub)
        ev = sub[r_col].mean()
        flag = ""
        if ev < 0:
            flag = " <-- EV NEGATIVE"
        elif ev < ci_low:
            flag = " <-- sous IC95% bas"
        small = " [n<20]" if n < 20 else ""
        print(f"  {str(name):>28s} n={n:4d} EV={ev:+.3f}R{flag}{small}")
        if flag and n >= 20:
            flagged.append(name)
    return flagged


def h1_h2_4blocs(pop, r_col, mask_fn, label):
    pop_sorted = pop.sort_values("date_creation").reset_index(drop=True)
    mid = len(pop_sorted) // 2
    subperiods = {"H1": pop_sorted.iloc[:mid], "H2": pop_sorted.iloc[mid:]}
    for i, b in enumerate(np.array_split(pop_sorted, 4)):
        subperiods[f"bloc{i}"] = b
    print(f"\n  --- Stress-test H1/H2+4blocs pour segment '{label}' ---")
    all_below = True
    n_evaluable = 0
    for name, sp in subperiods.items():
        seg = sp[mask_fn(sp)]
        rest = sp[~mask_fn(sp)]
        if len(seg) < 5:
            print(f"    [{name}] n_segment={len(seg)} insuffisant -- ininterpretable")
            continue
        n_evaluable += 1
        ev_seg, ev_rest = seg[r_col].mean(), rest[r_col].mean()
        below = ev_seg < ev_rest
        all_below = all_below and below
        flag = "OK (segment < reste, coherent)" if below else "INVERSION (segment >= reste)"
        print(f"    [{name}] n_segment={len(seg)} EV_segment={ev_seg:+.3f}R | "
              f"n_reste={len(rest)} EV_reste={ev_rest:+.3f}R -- {flag}")
    print(f"  Sous-periodes evaluables : {n_evaluable}/6, coherent partout : {all_below}")
    return all_below, n_evaluable


if __name__ == "__main__":
    pop = iso.build_pop_B("tout_indices")
    pop["r"] = outcome_r(pop)
    print(f"[verif] population B actuelle : n={len(pop)}, EV globale={pop['r'].mean():+.4f}R")

    print("\n" + "=" * 78)
    print("VARIABLE 0 : asset_class -- ECARTE SANS CALCUL (1 seule categorie, cf. docstring)")
    print("=" * 78)

    print("\n" + "=" * 78)
    print("VARIABLE 1 : SESSION HORAIRE UTC")
    print("=" * 78)
    pop["hour_utc"] = pop["date_creation"].dt.hour
    pop["_session3"] = pd.cut(pop["hour_utc"], [-1, 8, 16, 24], labels=["Asie(0-8)", "London(8-16)", "US(16-24)"])
    print("-- 6 tranches 4h --")
    flagged1a = report_segment_ev(pop, "r", "hour_utc", bins=[-1, 3, 7, 11, 15, 19, 24])
    print("\n-- 3 blocs session (convention S2.3) --")
    flagged1b = report_segment_ev(pop, "r", "_session3", is_categorical=True)

    print("\n" + "=" * 78)
    print("VARIABLE 2 : distance_SL%")
    print("=" * 78)
    pop["distance_sl_pct"] = (pop["prix_entree"] - pop["stop_loss_init"]).abs() / pop["prix_entree"] * 100
    print(f"[verif] range=[{pop['distance_sl_pct'].min():.3f},{pop['distance_sl_pct'].max():.3f}]")
    flagged2 = report_segment_ev(pop, "r", "distance_sl_pct", bins=5)
    pear_sl = pop["distance_sl_pct"].corr(pop["r"])
    print(f"  Pearson(distance_sl_pct, r) = {pear_sl:+.3f}")

    print("\n" + "=" * 78)
    print("VARIABLE 3 : ADX(14) a l'entree")
    print("=" * 78)
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
    covered = pop.dropna(subset=["adx_at_entry"]).copy()
    print(f"[verif] couverture ADX : {len(covered)}/{len(pop)} ({len(covered)/len(pop)*100:.1f}%)")
    flagged3 = report_segment_ev(covered, "r", "adx_at_entry", bins=5)
    pear_adx = covered["adx_at_entry"].corr(covered["r"])
    print(f"  Pearson(adx_at_entry, r) = {pear_adx:+.3f}")

    # --- Stress-test immediat sur tout signal detecte (EV<0 ou <IC95% bas, n>=20) ---
    print("\n" + "=" * 78)
    print("STRESS-TEST IMMEDIAT sur les segments signales")
    print("=" * 78)
    any_flagged = False
    if flagged1b:
        any_flagged = True
        for name in flagged1b:
            h1_h2_4blocs(pop, "r", lambda sp, n=name: sp["_session3"] == n, f"session={name}")
    if flagged2:
        any_flagged = True
        pop["_slbin"] = pd.qcut(pop["distance_sl_pct"], 5, duplicates="drop")
        for name in flagged2:
            h1_h2_4blocs(pop, "r", lambda sp, n=name: sp["_slbin"] == n, f"distance_SL bin={name}")
    if flagged3:
        any_flagged = True
        covered["_adxbin"] = pd.qcut(covered["adx_at_entry"], 5, duplicates="drop")
        for name in flagged3:
            h1_h2_4blocs(covered, "r", lambda sp, n=name: sp["_adxbin"] == n, f"ADX bin={name}")
    if not any_flagged:
        print("Aucun segment signale (EV negative ou sous IC95% bas avec n>=20) -- rien a stress-tester.")

    print("\nTermine.")
