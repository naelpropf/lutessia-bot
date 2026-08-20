"""
Chantier B-EV, Chantier 2 (2026-08-19) -- relance le diagnostic "bloque
par correlation" sur B avec la population ACTUELLE et complete (forex
RR[1,00;1,35) + tous les indices routes, 571 trades, "tout-indices->B"
deja adopte) -- le dernier essai (chantier_strategie_b_correlation_
elargi_2026-08-18.py, meme jour, bande 0,50<=rr_tp1<1,35 SANS indices)
donnait n=16 bloques-correlation, Delta=+0,6678R, juge trop fragile
(3 trades portent l'essentiel).

Reutilise EXACTEMENT la meme methode (walkthrough_blocking, 1 compte,
MAX_POSITIONS, excluded_map CORR_TH=0,80) que chantier_strategie_b_
correlation_elargi_2026-08-18.py -- copie fidele des fonctions, seule la
population source change (tout-indices->B au lieu de la bande elargie
0,50-1,35 sans indices).

N'importe pas ce script directement (convention du projet).
"""
import importlib.util

import numpy as np
import pandas as pd

import robustness_5ers_risk_challenge as eng
from monte_carlo_simulation import precompute_correlation_pairs

CORR_TH = 0.80
ISO_SCRIPT = "chantier_strategie_b_isolation_indices_2026-08-18.py"

spec = importlib.util.spec_from_file_location("iso_b_ev2", ISO_SCRIPT)
iso = importlib.util.module_from_spec(spec)
spec.loader.exec_module(iso)


def load_excluded_map(pop):
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    return precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)


def walkthrough_blocking(pop, excluded_map):
    pop = pop.sort_values("date_creation").reset_index(drop=True)
    open_positions = []
    rows = []
    for _, row in pop.iterrows():
        now = row["date_creation"]
        close_time = row["resolution_time_est"]
        ticker = row["ticker"]
        r = row["r_trailing"] if row["statut_final"] == "OBJECTIF ATTEINT" else -1.0

        open_positions = [(t, c) for (t, c) in open_positions if c > now]

        blocked_reason = None
        if len(open_positions) >= eng.MAX_POSITIONS:
            blocked_reason = "cap_position"
        elif any(t in excluded_map[ticker] for (t, _) in open_positions):
            blocked_reason = "correlation"

        rows.append({"date_creation": now, "ticker": ticker, "r": r,
                      "blocked_reason": blocked_reason})

        if blocked_reason is None:
            open_positions.append((ticker, close_time))

    return pd.DataFrame(rows)


def stresstest(df):
    print("\n" + "=" * 70)
    print("STRESS-TEST H1/H2+4 blocs (bloques-correlation vs admis)")
    print("=" * 70)
    mid = len(df) // 2
    subperiods = {"H1": df.iloc[:mid], "H2": df.iloc[mid:]}
    for i, b in enumerate(np.array_split(df, 4)):
        subperiods[f"bloc{i}"] = b

    all_consistent = True
    n_evaluable = 0
    for name, sp in subperiods.items():
        admitted_sp = sp[sp["blocked_reason"].isna()]["r"]
        corr_sp = sp[sp["blocked_reason"] == "correlation"]["r"]
        if len(corr_sp) < 3 or len(admitted_sp) == 0:
            print(f"  [{name}] n_bloques={len(corr_sp)} insuffisant -- ininterpretable")
            continue
        n_evaluable += 1
        better = corr_sp.mean() > admitted_sp.mean()
        all_consistent = all_consistent and better
        flag = "OK (bloques>admis)" if better else "INVERSION (bloques<=admis)"
        print(f"  [{name}] n_bloques={len(corr_sp)} EV_bloques={corr_sp.mean():+.3f}R | "
              f"n_admis={len(admitted_sp)} EV_admis={admitted_sp.mean():+.3f}R -- {flag}")
    print(f"\n  Sous-periodes evaluables (n_bloques>=3) : {n_evaluable}/6")
    print(f"  Direction constante dans toutes les sous-periodes evaluables : {all_consistent}")
    return all_consistent, n_evaluable


def walkthrough_swap_rr(pop, excluded_map):
    """Variante 'any-RR equivalent pour B' -- meme walkthrough, mais quand
    un nouveau signal est bloque par correlation ET a un rr_tp1 plus eleve
    que l'occupant en conflit, EVICTE l'occupant (retire son gain deja
    compte, le remplace par le nouveau) -- meme principe que
    process_trade_corr_swap_rr (chantier_correlation_swap_2026-08-16.py),
    en walkthrough 1 compte statistique (pas de Monte Carlo fleet)."""
    pop = pop.sort_values("date_creation").reset_index(drop=True)
    open_positions = []  # (ticker, close_time, r, rr, idx)
    admitted_r = {}
    for i, row in pop.iterrows():
        now = row["date_creation"]
        close_time = row["resolution_time_est"]
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
            elif len(conflicts) == 1 and rr > conflicts[0][3]:
                occ = conflicts[0]
                open_positions = [p for p in open_positions if p is not occ]
                admitted_r.pop(occ[4], None)
                admitted = True
        if admitted:
            open_positions.append((ticker, close_time, r, rr, i))
            admitted_r[i] = r
    return admitted_r


if __name__ == "__main__":
    print("=" * 70)
    print("Chantier B-EV-2 -- diagnostic correlation sur B ACTUEL (571 trades, avec indices)")
    print("=" * 70)

    pop_B = iso.build_pop_B("tout_indices")
    print(f"\nPopulation B actuelle : n={len(pop_B)}")

    r = np.where(pop_B["statut_final"] == "OBJECTIF ATTEINT", pop_B["r_trailing"], -1.0)
    print(f"winrate={(r>0).mean()*100:.1f}%  EV={r.mean():+.4f}R")

    excluded_map = load_excluded_map(pop_B)
    df = walkthrough_blocking(pop_B, excluded_map)
    admitted = df[df["blocked_reason"].isna()]
    corr = df[df["blocked_reason"] == "correlation"]
    cap = df[df["blocked_reason"] == "cap_position"]

    print(f"\nAdmis={len(admitted)} ({len(admitted)/len(df)*100:.1f}%), "
          f"bloques CORRELATION={len(corr)} ({len(corr)/len(df)*100:.1f}%), "
          f"bloques cap_position={len(cap)} ({len(cap)/len(df)*100:.1f}%)")
    print(f"\nEV admis = {admitted['r'].mean():+.4f}R (n={len(admitted)})")

    if len(corr) > 0:
        print(f"EV bloques CORRELATION = {corr['r'].mean():+.4f}R (n={len(corr)}, "
              f"mediane={corr['r'].median():+.4f}R, winrate={((corr['r']>0).mean()*100):.1f}%)")
        vals = corr["r"].sort_values(ascending=False).reset_index(drop=True)
        print(f"  Distribution complete (triee) : " + ", ".join(f"{v:+.2f}" for v in vals.tolist()))
        for k in (3, 5):
            if len(vals) > k:
                rest = vals.iloc[k:]
                print(f"  Retrait du top {k} : n_restant={len(rest)} moyenne={rest.mean():+.4f}R "
                      f"(vs {vals.mean():+.4f}R avec, delta={rest.mean()-vals.mean():+.4f}R)")
        delta = corr["r"].mean() - admitted["r"].mean()
        print(f"\n[Delta] EV(bloques_correlation) - EV(admis) = {delta:+.4f}R "
              f"(rappel : +0,6678R sur B etroit n=16 sans indices 08/18, +2,029R sur A n=44)")

        if len(corr) >= 30:
            print(f"\nn={len(corr)} >= 30 -- echantillon juge suffisant pour un stress-test.")
            stresstest(df)
        else:
            print(f"\nn={len(corr)} < 30 -- meme seuil de prudence que le diagnostic precedent "
                  f"(n~44 sur A jugé exploitable, n=16 sur B jugé trop fragile) -- ")
    else:
        print("\nAucun trade bloque par correlation dans cette population -- diagnostic non applicable.")

    # --- Test statistique "any-RR equivalent pour B" (pas de Monte Carlo fleet) ---
    if len(corr) >= 30:
        print("\n" + "=" * 70)
        print("TEST STATISTIQUE -- any-RR equivalent pour B (swap si rr_tp1 superieur)")
        print("=" * 70)
        admitted_r_swap = walkthrough_swap_rr(pop_B, excluded_map)
        ev_swap = np.mean(list(admitted_r_swap.values()))
        n_swap = len(admitted_r_swap)
        ev_baseline_admis_only = admitted["r"].mean()
        print(f"  Baseline (admis sans swap) : n={len(admitted)} EV={ev_baseline_admis_only:+.4f}R")
        print(f"  Avec swap any-RR : n={n_swap} EV={ev_swap:+.4f}R "
              f"(delta vs baseline {ev_swap-ev_baseline_admis_only:+.4f}R, "
              f"{n_swap-len(admitted):+d} trades admis en plus)")
