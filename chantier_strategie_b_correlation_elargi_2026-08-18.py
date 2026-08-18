"""
Suite de chantier_strategie_b_baseline_2026-08-18.py (meme jour) --
approfondissement du SEUL candidat prometteur trouve (diagnostic
correlation, +0,668R bloques vs admis, mais n=16 fragile, 3 outliers).
Consigne explicite : PAS de nouvelle recherche exploratoire large (Force/
ADX/ATR/paires/session/asset_class/distance_SL% deja rejetes sur A pour
des raisons tenant aux instruments, pas a la population -- peu de raison
que ca marche mieux sur B). Uniquement : population B ELARGIE a
0,50<=rr_tp1<1,35 (au lieu de 0,75-1,35), re-mesure du diagnostic
correlation avec ce n plus grand.

TACHE 1 : re-diagnostic correlation sur B elargi -- n suffisant ? signal
tient ou s'effondre ?
TACHE 2 : si n>=40-50 (meme gamme que le diagnostic A original, n=44) --
stress-test H1/H2+4 blocs sur le sous-groupe bloques-correlation vs admis.
TACHE 3 : seulement si 1-2 concluants -- mecanique de sizing proposee,
PAS juste un ratio (voir texte de sortie).

Copie de la fonction diagnostic de chantier_correlation_swap_2026-08-16.py
Section 0 (deja reutilisee dans chantier_strategie_b_baseline_2026-08-18.py
Tache 3), meme walkthrough 1 compte (MAX_POSITIONS, excluded_map
CORR_TH=0,80).

N'importe pas ce script directement (convention du projet).
"""
import numpy as np
import pandas as pd

import robustness_5ers_risk_challenge as eng
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs

MIN_RR_A = 1.35
CORR_TH = 0.80


def load_pop_B_wide(min_rr_low=0.50):
    pop = build_population_with_trailing("fixed", 0.15, min_rr=min_rr_low, verbose=False)
    return pop[pop["rr_tp1"] < MIN_RR_A].reset_index(drop=True)


def outcome_r_col(pop):
    return np.where(pop["statut_final"] == "OBJECTIF ATTEINT", pop["r_trailing"], -1.0)


def load_excluded_map(pop):
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    return precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)


def walkthrough_blocking(pop, excluded_map):
    """Meme walkthrough que Section 0 de chantier_correlation_swap_2026-08-16.py
    -- 1 compte, MAX_POSITIONS, excluded_map. Retourne le DataFrame annote
    (blocked_reason) trie chronologiquement."""
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


def tache1(pop_wide):
    print("=" * 70)
    print("TACHE 1 -- re-diagnostic correlation sur B elargi (0,50<=rr_tp1<1,35)")
    print("=" * 70)

    r = outcome_r_col(pop_wide)
    print(f"\n[Baseline B elargi] n={len(pop_wide)} trades (vs n=401 pour 0,75-1,35, "
          f"vs n=631 pour A)")
    print(f"  winrate = {(r>0).mean()*100:.1f}%  EV moyenne = {r.mean():+.4f}R")

    excluded_map = load_excluded_map(pop_wide)
    df = walkthrough_blocking(pop_wide, excluded_map)
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
              f"(rappel : +0,6678R sur B etroit n=16, +2,029R sur A n=44)")
    return df, admitted, corr


def tache2_stresstest(pop_wide, excluded_map_full):
    print("\n" + "=" * 70)
    print("TACHE 2 -- stress-test H1/H2+4 blocs (bloques-correlation vs admis)")
    print("=" * 70)
    print("\nMethode : le walkthrough (ordre d'ouverture des positions, etat de la")
    print("flotte) est chronologique et cumulatif -- on ne peut pas re-simuler")
    print("independamment chaque sous-periode sans perdre l'etat des positions")
    print("ouvertes a la frontiere. On reutilise donc l'annotation blocked_reason")
    print("calculee sur la population ENTIERE (walkthrough continu), puis on")
    print("decoupe le resultat annote par sous-periode chronologique -- coherent")
    print("avec la methode deja utilisee pour rr_tp2 (tranches calculees globalement,")
    print("testees ensuite par sous-periode).")

    pop_sorted = pop_wide.sort_values("date_creation").reset_index(drop=True)
    df = walkthrough_blocking(pop_sorted, excluded_map_full)

    mid = len(df) // 2
    subperiods = {"H1": df.iloc[:mid], "H2": df.iloc[mid:]}
    blocks4 = np.array_split(df, 4)
    for i, b in enumerate(blocks4):
        subperiods[f"bloc{i}"] = b

    all_consistent = True
    for name, sp in subperiods.items():
        admitted_sp = sp[sp["blocked_reason"].isna()]["r"]
        corr_sp = sp[sp["blocked_reason"] == "correlation"]["r"]
        if len(corr_sp) < 3 or len(admitted_sp) == 0:
            print(f"  [{name}] n_bloques={len(corr_sp)} insuffisant -- ininterpretable")
            continue
        better = corr_sp.mean() > admitted_sp.mean()
        all_consistent = all_consistent and better
        flag = "OK (bloques>admis)" if better else "INVERSION (bloques<=admis)"
        print(f"  [{name}] n_bloques={len(corr_sp)} EV_bloques={corr_sp.mean():+.3f}R | "
              f"n_admis={len(admitted_sp)} EV_admis={admitted_sp.mean():+.3f}R -- {flag}")

    print(f"\n  Direction constante dans TOUTES les sous-periodes evaluables : {all_consistent}")
    return all_consistent


if __name__ == "__main__":
    print("Chargement population B elargie (0,50<=rr_tp1<1,35)...")
    pop_wide = load_pop_B_wide(0.50)
    print(f"n = {len(pop_wide)} trades")

    df, admitted, corr = tache1(pop_wide)

    N_MIN = 40
    if len(corr) >= N_MIN:
        print(f"\n[Seuil n>={N_MIN} atteint (n={len(corr)})] -- passage a la Tache 2.")
        excluded_map = load_excluded_map(pop_wide)
        stable = tache2_stresstest(pop_wide, excluded_map)
        print(f"\n[Statut final] n suffisant={True}, stress-test stable={stable}")
    else:
        print(f"\n[Seuil n>={N_MIN} NON atteint (n={len(corr)})] -- Tache 2 non lancee, "
              f"pas assez de donnees. Statut : EN ATTENTE DE PLUS DE DONNEES, "
              f"pas un chantier ferme.")
