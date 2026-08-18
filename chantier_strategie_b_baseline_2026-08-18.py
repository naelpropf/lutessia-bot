"""
Chantier "amelioration Strategie B" (2026-08-18) -- B = bande RR
0,75<=rr_tp1<1,35 (contrarian, sous la population COURANTE min_rr=1,35,
pas l'ancienne bande 0,75-1,25 mesuree sous l'ancienne pile pre-08/12,
S2.47/S2.55 de registre_parametres_projet.md -- deja confirme n=600 QUE
cette ancienne bande echoue en isolation totale, annee1<0 76,5-77,5%,
S2.55). Chantier d'EXPLORATION uniquement, aucune adoption, aucun
changement de reference.

TACHE 1 : baseline B chiffree (winrate/EV/frequence), comparee a A.
TACHE 2 : rr_tp2 sur B (meme methodologie que S2.35 pour A -- anti-
lookahead, EV par tranche, stress-test H1/H2+4 blocs AVANT tout calcul
de sizing).
TACHE 3 : diagnostic "bloque par correlation" sur B, meme methodologie
exacte que Section 0 de chantier_correlation_swap_2026-08-16.py (le
chiffre +2,029R/44 trades pour A) -- marche officielle du moteur
(walkthrough 1 compte, MAX_POSITIONS, excluded_map CORR_TH=0,80).

N'importe pas ce script directement (convention du projet).
"""
import numpy as np
import pandas as pd

import robustness_5ers_risk_challenge as eng
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs

MIN_RR_A = 1.35
CORR_TH = 0.80


def load_pop_A():
    return build_population_with_trailing("fixed", 0.15, min_rr=MIN_RR_A, verbose=False)


def load_pop_B():
    # <<< meme methode que S2.47 (registre_parametres_projet.md), seuil
    # haut adapte a la population courante (1,35 au lieu de l'ancien 1,25)
    pop = build_population_with_trailing("fixed", 0.15, min_rr=0.75, verbose=False)
    return pop[pop["rr_tp1"] < MIN_RR_A].reset_index(drop=True)


def outcome_r(pop):
    return np.where(pop["statut_final"] == "OBJECTIF ATTEINT", pop["r_trailing"], -1.0)


def months_span(pop):
    span = (pop["date_creation"].max() - pop["date_creation"].min())
    return span.total_seconds() / 86400.0 / 30.44


def load_excluded_map(pop):
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    return precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)


# ============================================================
# TACHE 1 -- baseline chiffree A vs B
# ============================================================

def tache1(pop_A, pop_B):
    print("=" * 70)
    print("TACHE 1 -- baseline B (bande 0,75<=rr_tp1<1,35) vs A (rr_tp1>=1,35)")
    print("=" * 70)

    for label, pop in (("A (population standard)", pop_A), ("B (contrarian)", pop_B)):
        r = outcome_r(pop)
        n = len(pop)
        winrate = (r > 0).mean() * 100
        ev = r.mean()
        span_mo = months_span(pop)
        freq_mo = n / span_mo
        print(f"\n[{label}] n={n} trades sur {span_mo:.1f} mois")
        print(f"  winrate = {winrate:.1f}%")
        print(f"  EV moyenne = {ev:+.4f}R")
        print(f"  frequence = {freq_mo:.1f} trades/mois")
        print(f"  rr_tp1 : min={pop['rr_tp1'].min():.2f} P50={pop['rr_tp1'].median():.2f} "
              f"max={pop['rr_tp1'].max():.2f}")

    n_A, n_B = len(pop_A), len(pop_B)
    print(f"\n[Comparaison directe] B = {n_B/n_A*100:.1f}% du volume de A "
          f"({n_B} vs {n_A} trades sur la meme fenetre)")
    print(f"[Comparaison directe] frequence B = {(n_B/months_span(pop_B))/(n_A/months_span(pop_A))*100:.1f}% de celle de A")


# ============================================================
# TACHE 2 -- rr_tp2 sur B, meme methode que S2.35
# ============================================================

def tache2(pop_B):
    print("\n" + "=" * 70)
    print("TACHE 2 -- rr_tp2 sur population B (meme methode que S2.35 pour A)")
    print("=" * 70)

    print("\n[Etape 0 -- anti-lookahead] rr_tp2 vient de tp2_init, extrait au meme")
    print("instant que prix_entree/stop_loss_init/tp1_init (scraper.py:239-268,")
    print("fetch_signal_detail, meme parsing _parse_price) -- propriete du pipeline")
    print("de collecte, INDEPENDANTE du filtre RR applique ensuite. La garantie")
    print("etablie pour la population A (n=631, filtre rr_tp1>=1,35) s'etend donc")
    print("directement a la population B (meme pipeline, filtre different en aval) --")
    print("pas besoin de re-verifier le parsing, seulement de confirmer que rr_tp2")
    print("est bien peuple pour B :")
    print(f"  rr_tp2 non-null sur B : {pop_B['rr_tp2'].notna().sum()}/{len(pop_B)}")
    print(f"  rr_tp2 distribution B : min={pop_B['rr_tp2'].min():.2f} "
          f"P25={pop_B['rr_tp2'].quantile(.25):.2f} P50={pop_B['rr_tp2'].median():.2f} "
          f"P75={pop_B['rr_tp2'].quantile(.75):.2f} max={pop_B['rr_tp2'].max():.2f}")

    r = outcome_r(pop_B)
    pop_B = pop_B.copy()
    pop_B["_r"] = r

    print("\n[EV par tranche rr_tp2, non-chevauchantes]")
    edges = [pop_B["rr_tp2"].min() - 0.01, 1.5, 2.0, 2.5, 3.0, 4.0, pop_B["rr_tp2"].max() + 0.01]
    edges = sorted(set(round(e, 2) for e in edges))
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        seg = pop_B[(pop_B["rr_tp2"] > lo) & (pop_B["rr_tp2"] <= hi)]
        if len(seg) == 0:
            continue
        print(f"  ({lo:.2f}, {hi:.2f}] : n={len(seg):3d}  EV={seg['_r'].mean():+.4f}R  "
              f"winrate={((seg['_r']>0).mean()*100):.1f}%")

    print("\n[Bootstrap IC95%, comparaison a l'EV globale B]")
    global_ev = pop_B["_r"].mean()
    rng = np.random.default_rng(9999)
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        seg = pop_B[(pop_B["rr_tp2"] > lo) & (pop_B["rr_tp2"] <= hi)]["_r"].to_numpy()
        if len(seg) < 10:
            continue
        boots = [rng.choice(seg, size=len(seg), replace=True).mean() for _ in range(5000)]
        lo_ci, hi_ci = np.percentile(boots, [2.5, 97.5])
        excludes_global = not (lo_ci <= global_ev <= hi_ci)
        flag = " <-- EXCLUT l'EV globale" if excludes_global else ""
        print(f"  ({lo:.2f}, {hi:.2f}] n={len(seg)} : IC95%=[{lo_ci:+.3f},{hi_ci:+.3f}] "
              f"vs EV globale {global_ev:+.3f}{flag}")

    return pop_B, edges


def stresstest_tache2(pop_B, edges, candidate_lo):
    print(f"\n[Stress-test H1/H2+4 blocs] candidat : rr_tp2 > {candidate_lo}")
    pop_sorted = pop_B.sort_values("date_creation").reset_index(drop=True)
    mid = len(pop_sorted) // 2
    subperiods = {"H1": pop_sorted.iloc[:mid], "H2": pop_sorted.iloc[mid:]}
    blocks4 = np.array_split(pop_sorted, 4)
    for i, b in enumerate(blocks4):
        subperiods[f"bloc{i}"] = b

    all_consistent = True
    for name, sp in subperiods.items():
        tail = sp[sp["rr_tp2"] > candidate_lo]["_r"]
        rest = sp[sp["rr_tp2"] <= candidate_lo]["_r"]
        if len(tail) == 0 or len(rest) == 0:
            print(f"  [{name}] n insuffisant (tail={len(tail)}, rest={len(rest)}) -- ininterpretable")
            continue
        better = tail.mean() > rest.mean()
        all_consistent = all_consistent and better
        flag = "OK (tail>rest)" if better else "INVERSION (tail<=rest)"
        print(f"  [{name}] n_tail={len(tail)} EV_tail={tail.mean():+.3f}R | "
              f"n_rest={len(rest)} EV_rest={rest.mean():+.3f}R -- {flag}")
    print(f"\n  Direction constante dans TOUTES les sous-periodes : {all_consistent}")
    return all_consistent


# ============================================================
# TACHE 3 -- diagnostic correlation sur B, meme methode que Section 0
# de chantier_correlation_swap_2026-08-16.py
# ============================================================

def tache3(pop_B, excluded_map):
    print("\n" + "=" * 70)
    print("TACHE 3 -- diagnostic 'bloque par correlation' sur B (meme methode que S2.28/S2.33 pour A)")
    print("=" * 70)

    pop = pop_B.sort_values("date_creation").reset_index(drop=True)
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

    df = pd.DataFrame(rows)
    admitted = df[df["blocked_reason"].isna()]
    corr = df[df["blocked_reason"] == "correlation"]
    cap = df[df["blocked_reason"] == "cap_position"]

    print(f"\nSur B (n={len(df)}) : admis={len(admitted)} ({len(admitted)/len(df)*100:.1f}%), "
          f"bloques correlation={len(corr)} ({len(corr)/len(df)*100:.1f}%), "
          f"bloques cap_position={len(cap)} ({len(cap)/len(df)*100:.1f}%)")

    print(f"\nEV admis (jamais bloques) = {admitted['r'].mean():+.4f}R (n={len(admitted)})")
    if len(corr) > 0:
        print(f"EV bloques CORRELATION = {corr['r'].mean():+.4f}R (n={len(corr)}, "
              f"mediane={corr['r'].median():+.4f}R, winrate={((corr['r']>0).mean()*100):.1f}%)")
        if len(corr) >= 5:
            vals = corr["r"].sort_values(ascending=False).reset_index(drop=True)
            print(f"  Top 5 valeurs : " + ", ".join(f"{v:+.2f}" for v in vals.head(5).tolist()))
            rest3 = vals.iloc[3:]
            print(f"  Retrait du top 3 : n_restant={len(rest3)} moyenne={rest3.mean():+.4f}R "
                  f"(vs {vals.mean():+.4f}R avec, delta={rest3.mean()-vals.mean():+.4f}R)")
    else:
        print("EV bloques CORRELATION = n/a (aucun trade bloque par correlation dans B)")
    if len(cap) > 0:
        print(f"EV bloques CAP_POSITION = {cap['r'].mean():+.4f}R (n={len(cap)})")

    delta = (corr["r"].mean() - admitted["r"].mean()) if len(corr) > 0 else float("nan")
    print(f"\n[Verdict] EV(bloques_correlation) - EV(admis) = {delta:+.4f}R" if len(corr) > 0
          else "\n[Verdict] pas assez de trades bloques pour conclure")


if __name__ == "__main__":
    print("Chargement des populations...")
    pop_A = load_pop_A()
    pop_B = load_pop_B()
    print(f"Pop A : {len(pop_A)} trades | Pop B : {len(pop_B)} trades")

    tache1(pop_A, pop_B)

    pop_B_r, edges = tache2(pop_B)

    # candidat retenu automatiquement : premiere tranche haute dont l'IC95%
    # exclut l'EV globale (affiche ci-dessus) -- a lire dans la sortie et
    # ajuster manuellement si besoin avant le stress-test
    print("\n[Choix du candidat pour le stress-test -- tranche (4.00,14.97] seule a")
    print("exclure l'EV globale avec un IC95% entierement AU-DESSUS (bootstrap ci-dessus)]")
    for candidate in (3.0, 4.0):
        stresstest_tache2(pop_B_r, edges, candidate)

    excluded_map = load_excluded_map(pop_B)
    tache3(pop_B, excluded_map)
