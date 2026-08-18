"""
Partie 1 (2026-08-17) : recherche de variable(s) de segmentation alternative(s)
a RR (tp1/tp2 deja explores a granularite fine, aucun segment EV-negatif
trouve, cf. chantier_A_rr_sizing_diagnostic2_2026-08-17.py).

Etape 0 -- variables EXCLUES car deja testees EXACTEMENT comme base de
sizing/segmentation EV (pas juste comme filtre) :
- score_force : `registre_strategie_trading.md` S2.1 mecanisme (b)
  "ponderateur de taille de position" (Force<7->0,5x, Force>=8,5->1,5x) --
  REJETE ("Force non exploitable", gain apparent trace a un segment
  Force>=8,5 dont la correlation sous-jacente echoue le test de
  significativite, t=1,55).
- ATR ratio (sizing) : S2.6 "Sizing ajuste ATR -- quasi NEUTRE" -- deja
  teste comme base de sizing (pas seulement filtre), meme si sous un
  moteur ancien jamais recalcule avec la correction funded/challenge
  (point ouvert #4 du registre). Exclu par la lettre de la regle malgre
  la reserve de fraicheur.

Variables ELIGIBLES retenues (jamais testees comme base de sizing EV,
seulement comme filtre binaire ou comme confondant verifie) :
- ADX(14) a l'entree : S2.13/S2.31 -- filtre seuil uniquement. Reutilise
  `edge_adx_atr_filters_2026-08-11.py:build_population_with_indicators`
  (meme methodologie Wilder deja validee dans le projet). Couverture
  ~52% (limite yfinance H1 ~729j), signale explicitement.
- Session horaire (UTC) : S2.3 -- filtre d'exclusion Asie uniquement.
  Couverture 100% (date_creation deja UTC, memoire projet).
- asset_class : jamais teste independamment, seulement verifie comme
  confondant dans S2.35 (identique entre tranches rr_tp2). Couverture 100%.
- distance_SL% ((entree-SL)/entree*100) : S2.35 mentionne une correlation
  quasi nulle avec le WINRATE (confondant du rebond rr_tp2), mais jamais
  teste comme base de segmentation EV a part entiere, avec granularite
  dediee. Couverture 100%.

EXCLU de la shortlist (pas une nouvelle variable) : distance_TP2% --
correle +0,45 a rr_tp2 (S2.35), trop proche de "RR sous une autre forme"
explicitement exclu par le prompt.
"""
import numpy as np
import pandas as pd

import importlib.util as _ilu

import tp_sequence_analysis as tpseq
from trailing_payoff_population import build_population_with_trailing

_spec = _ilu.spec_from_file_location("_adx_atr", "edge_adx_atr_filters_2026-08-11.py")
_adx_atr_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_adx_atr_mod)
build_population_with_indicators = _adx_atr_mod.build_population_with_indicators

MIN_RR_NEW = 1.35


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


def report_segment_ev(pop, col, bins_or_labels, label, is_categorical=False):
    print(f"\n=== {label} (col={col}) ===")
    global_ev = pop["r_trailing"].mean()
    ci_low, ci_high = bootstrap_ci(pop["r_trailing"])
    print(f"EV globale (sous-population avec {col} disponible, n={len(pop)}) = {global_ev:+.3f}R "
          f"IC95%={[round(ci_low,3), round(ci_high,3)]}")
    if is_categorical:
        groups = pop.groupby(col, observed=True)
    else:
        pop = pop.copy()
        pop["_bin"] = pd.cut(pop[col], bins_or_labels)
        groups = pop.groupby("_bin", observed=True)
    rows = []
    for name, sub in groups:
        n = len(sub)
        ev = sub["r_trailing"].mean()
        flag = ""
        if ev < 0:
            flag += " <-- EV NEGATIVE"
        elif ev < ci_low:
            flag += " <-- sous IC95% bas"
        small = " [n<20, peu fiable]" if n < 20 else ""
        print(f"  {str(name):>25s} n={n:4d} EV={ev:+.3f}R{flag}{small}")
        rows.append((name, n, ev))
    return rows


def h1_h2_stability(pop, col, threshold_or_cat, is_categorical, target_label):
    pop_sorted = pop.sort_values("date_creation").reset_index(drop=True)
    mid = len(pop_sorted) // 2
    H1, H2 = pop_sorted.iloc[:mid], pop_sorted.iloc[mid:]
    print(f"\n  --- Stabilite H1/H2 pour segment cible '{target_label}' ---")
    results = []
    for name, df in [("H1", H1), ("H2", H2), ("full", pop_sorted)]:
        if is_categorical:
            sub = df[df[col] == threshold_or_cat]
        else:
            sub = df[df[col] <= threshold_or_cat] if isinstance(threshold_or_cat, tuple) is False else \
                df[(df[col] >= threshold_or_cat[0]) & (df[col] < threshold_or_cat[1])]
        ev = sub["r_trailing"].mean() if len(sub) else float("nan")
        gev = df["r_trailing"].mean()
        direction = "SOUS" if (not np.isnan(ev) and ev < gev) else ("AU-DESSUS" if not np.isnan(ev) else "N/A (n=0)")
        print(f"    {name}: EV_segment={ev:+.3f}R (n={len(sub)}) vs EV_globale_periode={gev:+.3f}R -> {direction}")
        results.append((name, ev, len(sub), direction))
    return results


if __name__ == "__main__":
    pop = build_population_with_trailing("fixed", 0.15, min_rr=MIN_RR_NEW, verbose=False)
    print(f"[verif] population de base (RR>={MIN_RR_NEW}) : {len(pop)} trades")
    global_ev = pop["r_trailing"].mean()
    print(f"[verif] EV globale population complete = {global_ev:+.3f}R")

    # ============================================================
    # Variable 1 : session horaire (UTC), couverture 100%
    # ============================================================
    pop["hour_utc"] = pop["date_creation"].dt.hour
    print("\n" + "=" * 78)
    print("VARIABLE 1 : SESSION HORAIRE UTC (couverture 100%)")
    print("=" * 78)
    report_segment_ev(pop, "hour_utc", [-1, 3, 7, 11, 15, 19, 24],
                       "Session horaire (6 tranches 4h)")
    # Convention S2.3 : Asie 00-08 / London 08-16 / US 16-24
    pop["_session3"] = pd.cut(pop["hour_utc"], [-1, 8, 16, 24], labels=["Asie(0-8)", "London(8-16)", "US(16-24)"])
    report_segment_ev(pop, "_session3", None, "Session (3 blocs, convention S2.3)", is_categorical=True)

    # ============================================================
    # Variable 2 : asset_class, couverture 100%
    # ============================================================
    print("\n" + "=" * 78)
    print("VARIABLE 2 : ASSET_CLASS (couverture 100%)")
    print("=" * 78)
    report_segment_ev(pop, "asset_class", None, "asset_class", is_categorical=True)

    # ============================================================
    # Variable 3 : distance_SL% = (entree-SL)/entree*100, couverture 100%
    # ============================================================
    print("\n" + "=" * 78)
    print("VARIABLE 3 : distance_SL% (couverture 100%)")
    print("=" * 78)
    pop["distance_sl_pct"] = (pop["prix_entree"] - pop["stop_loss_init"]).abs() / pop["prix_entree"] * 100
    print(f"[verif] distance_sl_pct range=[{pop['distance_sl_pct'].min():.3f},{pop['distance_sl_pct'].max():.3f}]")
    pop["_slbin"] = pd.qcut(pop["distance_sl_pct"], 5, duplicates="drop")
    for name, sub in pop.groupby("_slbin", observed=True):
        n = len(sub)
        ev = sub["r_trailing"].mean()
        print(f"  {str(name):>25s} n={n:4d} EV={ev:+.3f}R")
    pear_sl = pop["distance_sl_pct"].corr(pop["r_trailing"])
    print(f"  Pearson(distance_sl_pct, r_trailing) = {pear_sl:+.3f}")

    # ============================================================
    # Variable 4 : ADX(14) a l'entree, couverture ~52%
    # ============================================================
    print("\n" + "=" * 78)
    print("VARIABLE 4 : ADX(14) a l'entree (couverture partielle, signale)")
    print("=" * 78)
    pop_adx = build_population_with_indicators(min_rr=MIN_RR_NEW)
    covered = pop_adx[pop_adx["has_indicators"]]
    print(f"[verif] couverture ADX : {len(covered)}/{len(pop_adx)} ({len(covered)/len(pop_adx)*100:.1f}%)")
    covered = covered.copy()
    covered["_adxbin"] = pd.qcut(covered["adx_at_entry"], 5, duplicates="drop")
    global_ev_adx_pop = covered["r_trailing"].mean()
    print(f"  EV globale (sous-pop ADX dispo) = {global_ev_adx_pop:+.3f}R")
    for name, sub in covered.groupby("_adxbin", observed=True):
        n = len(sub)
        ev = sub["r_trailing"].mean()
        flag = " <-- EV NEGATIVE" if ev < 0 else ""
        print(f"  {str(name):>25s} n={n:4d} EV={ev:+.3f}R{flag}")
    pear_adx = covered["adx_at_entry"].corr(covered["r_trailing"])
    print(f"  Pearson(adx_at_entry, r_trailing) = {pear_adx:+.3f}")

    print("\nTermine.")
