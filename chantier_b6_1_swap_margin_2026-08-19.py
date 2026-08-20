"""
Chantier B6-1.1 (2026-08-19) -- sweep de marge RR minimale sur le mecanisme
swap corrélation (any-RR) de B, applique aux 15 evenements de swap reels
deja identifies (chantier_b5_swap_trace equivalent, retrace ici avec le
parametre marge en plus).

N'importe pas ce script directement (convention du projet).
"""
import importlib.util

import pandas as pd

import robustness_5ers_risk_challenge as eng
from monte_carlo_simulation import precompute_correlation_pairs

ISO_SCRIPT = "chantier_strategie_b_isolation_indices_2026-08-18.py"
spec = importlib.util.spec_from_file_location("iso_b61", ISO_SCRIPT)
iso = importlib.util.module_from_spec(spec)
spec.loader.exec_module(iso)

CORR_TH = 0.80
MARGINS = [1.00, 1.05, 1.10, 1.20, 1.30, 1.50]


def run_with_margin(pop_B, excluded_map, margin):
    open_positions = []
    admitted_r = {}
    swap_log = []
    for i, row in pop_B.iterrows():
        now = row["date_creation"]; close_time = row["resolution_time_est"]
        ticker = row["ticker"]
        r = row["r_trailing"] if row["statut_final"] == "OBJECTIF ATTEINT" else -1.0
        rr = row["rr_tp1"]
        open_positions = [p for p in open_positions if p[1] > now]
        at_cap = len(open_positions) >= eng.MAX_POSITIONS
        conflicts = [p for p in open_positions if p[0] in excluded_map[ticker]]
        admitted = False
        if not at_cap:
            if not conflicts:
                admitted = True
            elif len(conflicts) == 1 and rr > conflicts[0][3] * margin:
                occ = conflicts[0]
                evicted_r = admitted_r.get(occ[4])
                swap_log.append(dict(date_creation=now, ticker=ticker, rr_new=rr, r_new=r,
                                      occ_ticker=occ[0], occ_rr=occ[3], r_evicted=evicted_r,
                                      gain=(r - evicted_r) if evicted_r is not None else None))
                open_positions = [p for p in open_positions if p is not occ]
                admitted_r.pop(occ[4], None)
                admitted = True
        if admitted:
            open_positions.append((ticker, close_time, rr, r, i))
            admitted_r[i] = r
    return pd.DataFrame(swap_log), admitted_r


def stresstest_margin(pop_B, excluded_map, margin, label):
    pop_sorted = pop_B.sort_values("date_creation").reset_index(drop=True)
    mid = len(pop_sorted) // 2
    subperiods = {"H1": pop_sorted.iloc[:mid], "H2": pop_sorted.iloc[mid:]}
    import numpy as np
    for i, b in enumerate(np.array_split(pop_sorted, 4)):
        subperiods[f"bloc{i}"] = b
    print(f"\n  --- Stress-test H1/H2+4blocs, marge={margin:.2f} ---")
    for name, sp in subperiods.items():
        sp = sp.sort_values("date_creation").reset_index(drop=True)
        tickers_sp = sorted(sp["ticker"].unique())
        excl_sp = precompute_correlation_pairs(tickers_sp, pd.read_csv("correlation_matrix.csv", index_col=0), CORR_TH)
        swap_df, _ = run_with_margin(sp, excl_sp, margin)
        valid = swap_df.dropna(subset=["gain"]) if len(swap_df) else swap_df
        if len(valid) == 0:
            print(f"    [{name}] 0 swap avec gain connu -- non evaluable")
            continue
        total_gain = valid["gain"].sum()
        n_pos = (valid["gain"] > 0).sum()
        print(f"    [{name}] n_swaps={len(valid)} gain_total={total_gain:+.3f}R "
              f"({n_pos}/{len(valid)} positifs) -- {'OK (positif)' if total_gain > 0 else 'NEGATIF'}")


if __name__ == "__main__":
    pop_B = iso.build_pop_B("tout_indices").sort_values("date_creation").reset_index(drop=True)
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop_B["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

    print("=" * 78)
    print("SWEEP DE MARGE -- 15 evenements de swap historiques (population B complete)")
    print("=" * 78)
    rows = []
    for margin in MARGINS:
        swap_df, admitted_r = run_with_margin(pop_B, excluded_map, margin)
        valid = swap_df.dropna(subset=["gain"])
        total_gain = valid["gain"].sum() if len(valid) else 0.0
        n_pos = (valid["gain"] > 0).sum() if len(valid) else 0
        n_zero = (valid["gain"] == 0).sum() if len(valid) else 0
        n_neg = (valid["gain"] < 0).sum() if len(valid) else 0
        print(f"\nMarge={margin:.2f} : n_swaps_total={len(swap_df)} (n_gain_connu={len(valid)}) "
              f"gain_net_total={total_gain:+.4f}R  [{n_pos} positifs / {n_zero} nuls / {n_neg} negatifs]")
        if len(valid) > 0 and len(valid) <= 5:
            print("  ATTENTION : n<=5 evenements -- non tranchable statistiquement, signale explicitement.")
        rows.append(dict(margin=margin, n_swaps=len(swap_df), n_gain_connu=len(valid),
                          gain_net_total=total_gain, n_positifs=n_pos, n_nuls=n_zero, n_negatifs=n_neg))

    df_sweep = pd.DataFrame(rows)
    df_sweep.to_csv("chantier_b6_1_swap_margin_sweep_2026-08-19.csv", index=False)

    print("\n" + "=" * 78)
    print("TABLEAU RECAPITULATIF")
    print("=" * 78)
    print(df_sweep.to_string(index=False))

    # Choix du meilleur compromis : marge avec le meilleur gain_net_total ET n_gain_connu >= 5 (repere)
    candidates = df_sweep[df_sweep["n_gain_connu"] >= 5]
    if len(candidates) > 0:
        best = candidates.loc[candidates["gain_net_total"].idxmax()]
        print(f"\n[verif] meilleur compromis (n>=5) : marge={best['margin']:.2f}, "
              f"gain_net={best['gain_net_total']:+.4f}R, n={best['n_gain_connu']:.0f}")
        stresstest_margin(pop_B, excluded_map, best["margin"], "meilleure marge")
    else:
        print("\nAucune marge ne garde n>=5 evenements a gain connu -- toutes trop fragiles pour stress-test fiable.")
