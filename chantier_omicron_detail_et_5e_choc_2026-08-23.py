"""chantier_omicron_detail_et_5e_choc_2026-08-23.py

Suite au constat que le test Omicron deja fait (chantier_omicron_test_2026-
08-23.py) est structurellement non concluant (pop A demarre 2022-01-31,
apres la fenetre Omicron quelle que soit sa largeur -- verifie directement)
et confondu sur B (100% metaux), ce script fait 3 choses (feu vert
utilisateur explicite pour les 3) :

  1. Reproduit le detail complet (trades individuels, mecanisme -1R vs
     trailing) de l'ancien test Omicron large (2021-11-24->2022-01-07,
     B seule, n=15) -- extrait des donnees, pas juste relu du log.
  2. Refait le test sur B seule avec la fenetre RESSERREE demandee
     (2021-11-24->2021-12-10, centree sur le crash + rebond rapide), meme
     protocole, + Welch t-test et Mann-Whitney (scipy) en plus du z-approx
     deja utilise, comme demande.
  3. Cherche un 5e choc alternatif -- candidat retenu : le krach du 5 aout
     2024 (debouclage du carry trade JPY suite hausse taux BoJ 31/07 +
     regle de Sahm declenchee par le rapport emploi US du 02/08, panique de
     recession pure, Nikkei -12,4% en 1 jour, VIX pic a 65 -- PAS un choc
     Fed direct ni geopolitique, rebond quasi complet en ~10 jours) --
     seul choc en V pur identifie qui tombe dans la fenetre couverte par
     LES DEUX populations (A demarre 2022-01-31). Meme protocole complet
     (les 2 populations, delta vs bloc englobant, Welch/MWU, detail trades).

Reutilise integralement chocs = chantier_fenetres_macro_chocs_2026-08-23.py
(stats_block, common_bloc_edges, load_pop_a/b).
"""
import importlib.util

import numpy as np
import pandas as pd
from scipy import stats as sps

_spec = importlib.util.spec_from_file_location("chocs", "chantier_fenetres_macro_chocs_2026-08-23.py")
chocs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chocs)

OMICRON_WIDE = ("omicron_large_ancien", "2021-11-24", "2022-01-07")
OMICRON_TIGHT = ("omicron_resserre", "2021-11-24", "2021-12-10")
CARRY_UNWIND = ("aout2024_carry_unwind", "2024-08-01", "2024-08-16")


def full_detail(df, ref_ev, label):
    """Liste complete (gagnants+perdants), mecanisme -1R vs trailing, tests
    Welch + Mann-Whitney contre un echantillon 'reste du bloc' passe en ref_ev
    (ici on teste directement contre les r_trailing du bloc englobant complet,
    pas juste son EV scalaire -- plus correct pour Welch/MWU)."""
    print(f"\n  --- Detail complet {label} (n={len(df)}) ---")
    if len(df) == 0:
        print("    (vide)")
        return
    show = df[["date_creation", "ticker", "statut_final", "rr_tp1", "r_trailing"]].sort_values("date_creation")
    print(show.to_string(index=False))
    losses = df[df["statut_final"] != "OBJECTIF ATTEINT"]
    n_classic = int((losses["r_trailing"] == -1.0).sum())
    print(f"    Pertes ({len(losses)}) : {n_classic}/{len(losses)} exactement -1,00R (SL initial, mecanisme classique) "
          f"-- {len(losses)-n_classic} avec r_trailing != -1 (a examiner comme candidat 'echec trailing')")
    if len(losses) and n_classic < len(losses):
        print(losses[losses["r_trailing"] != -1.0][["date_creation", "ticker", "r_trailing"]].to_string(index=False))

    wins = df[df["statut_final"] == "OBJECTIF ATTEINT"]
    if len(wins) and "rr_tp1" in wins.columns:
        cut_near = wins[wins["r_trailing"] <= wins["rr_tp1"] * 1.1]
        print(f"    Gagnants coupes pres de TP1 (r_trailing<=1.1x rr_tp1) : {len(cut_near)}/{len(wins)}")

    if len(df) > 1 and ref_ev is not None and len(ref_ev) > 1:
        w, p_welch = sps.ttest_ind(df["r_trailing"], ref_ev, equal_var=False)
        u, p_mwu = sps.mannwhitneyu(df["r_trailing"], ref_ev, alternative="two-sided")
        print(f"    Welch t-test vs bloc englobant complet : t={w:+.3f} p={p_welch:.4f}")
        print(f"    Mann-Whitney U vs bloc englobant complet : U={u:.1f} p={p_mwu:.4f}")


def run_window(pop, label, edges, window, ref_bloc_label=None):
    name, start, end = window
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    bloc_idx = None
    for i in range(4):
        if edges[i] <= start_ts < edges[i + 1]:
            bloc_idx = i
            break
    if bloc_idx is None:
        print(f"\n### {label} -- fenetre {name} : DEBUT DE FENETRE HORS DES 4 BLOCS COMMUNS ({start_ts} < {edges[0]}) ###")
        bloc_idx = 0
    ref_df = pop[(pop["date_creation"] >= edges[bloc_idx]) & (pop["date_creation"] < edges[bloc_idx + 1])]
    ref_stat = chocs.stats_block(ref_df, f"bloc{bloc_idx+1} ENTIER (reference)")

    w = pop[(pop["date_creation"] >= start_ts) & (pop["date_creation"] < end_ts)]
    s = chocs.stats_block(w, f"fenetre {name} [{start}->{end}]")
    print(f"\n### {label} -- fenetre {name} ###")
    chocs.print_stats(ref_stat)
    chocs.print_stats(s)
    if s["n"]:
        print(f"    delta EV vs {ref_stat['label']} = {s['ev']-ref_stat['ev']:+.4f}R")
        if s["n"] > 1 and ref_stat["n"] > 1:
            se_diff = (s["se"] ** 2 + ref_stat["se"] ** 2) ** 0.5
            z = (s["ev"] - ref_stat["ev"]) / se_diff if se_diff > 0 else float("nan")
            print(f"    z (approx, se combinees) = {z:+.3f}")
    full_detail(w, ref_df["r_trailing"] if len(ref_df) else None, f"{label} / {name}")
    return s, ref_stat, w


def main():
    pop_a = chocs.load_pop_a()
    pop_b = chocs.load_pop_b()
    edges = chocs.common_bloc_edges(pop_a, pop_b)
    print("Bloc edges (communs A/B) :", list(edges))
    print(f"Pop A : {pop_a['date_creation'].min()} -> {pop_a['date_creation'].max()} (n={len(pop_a)})")
    print(f"Pop B : {pop_b['date_creation'].min()} -> {pop_b['date_creation'].max()} (n={len(pop_b)})")

    print(f"\n{'='*95}\n1. DETAIL COMPLET -- ancien test Omicron LARGE (2021-11-24->2022-01-07)\n{'='*95}")
    print(f"  Pop A couverture : min={pop_a['date_creation'].min()} -- fenetre commence 2021-11-24 -> "
          f"{'NON COUVERTE' if pop_a['date_creation'].min() > pd.Timestamp('2022-01-07') else 'partiellement couverte'}")
    run_window(pop_b, "B_tradable_pgp", edges, OMICRON_WIDE)

    print(f"\n{'='*95}\n2. NOUVEAU -- Omicron RESSERRE (2021-11-24->2021-12-10), B seule\n{'='*95}")
    run_window(pop_b, "B_tradable_pgp", edges, OMICRON_TIGHT)

    print(f"\n{'='*95}\n3. 5e CHOC CANDIDAT -- debouclage carry trade JPY / regle de Sahm (aout 2024)\n{'='*95}")
    print(f"  Pop A couverture fenetre {CARRY_UNWIND[1]}->{CARRY_UNWIND[2]} : "
          f"{'COUVERTE' if pop_a['date_creation'].min() <= pd.Timestamp(CARRY_UNWIND[1]) else 'NON COUVERTE'}")
    print(f"  Pop B couverture fenetre {CARRY_UNWIND[1]}->{CARRY_UNWIND[2]} : "
          f"{'COUVERTE' if pop_b['date_creation'].min() <= pd.Timestamp(CARRY_UNWIND[1]) else 'NON COUVERTE'}")
    run_window(pop_a, "A (0.15x trailing)", edges, CARRY_UNWIND)
    run_window(pop_b, "B_tradable_pgp", edges, CARRY_UNWIND)


if __name__ == "__main__":
    main()
