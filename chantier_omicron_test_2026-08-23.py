"""chantier_omicron_test_2026-08-23.py

QUESTION 3 (session du 23/08, feu vert donne suite au handoff 23/08 S5.4) :
teste le choc Omicron (fin novembre 2021) avec le meme protocole que les 4
fenetres macro deja testees (chantier_fenetres_macro_chocs_2026-08-23.py),
pour A et B separement.

Omicron = choc de sentiment risk-off pur, sans lien avec les taux ni la
geopolitique -- l'OMS classe le variant "preoccupant" le 26/11/2021, chute
brutale ce jour-la (S&P -2,3%, plus forte baisse en 1 jour depuis fevrier
2021) et les jours suivants, rebond rapide mi-decembre une fois le risque
clinique revu a la baisse. Fenetre : 2021-11-24 (2j avant l'annonce, pour
capter l'anticipation/la purge immediate) -> 2022-01-07 (retour proche des
plus hauts, avant que la remontee des taux Fed ne devienne le narratif
dominant de janvier 2022).

Reutilise integralement l'infrastructure de chantier_fenetres_macro_chocs_
2026-08-23.py (memes populations corrigees post-fix r_trailing, meme
decoupage bloc1/bloc2/bloc3/bloc4, meme fonction stats_block/trailing_detail).
"""
import importlib.util

import pandas as pd

_spec = importlib.util.spec_from_file_location("chocs", "chantier_fenetres_macro_chocs_2026-08-23.py")
chocs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chocs)

OMICRON_WINDOW = ("5_omicron", "2021-11-24", "2022-01-07")


def analyze_omicron(pop, label, edges):
    print(f"\n{'#'*95}\n# Population {label} (n={len(pop)}, {pop['date_creation'].min()} -> {pop['date_creation'].max()})\n{'#'*95}")
    bloc1 = pop[(pop["date_creation"] >= edges[0]) & (pop["date_creation"] < edges[1])]
    ref_bloc1 = chocs.stats_block(bloc1, "bloc1 ENTIER (reference)")
    chocs.print_stats(ref_bloc1)

    name, start, end = OMICRON_WINDOW
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    w = pop[(pop["date_creation"] >= start_ts) & (pop["date_creation"] < end_ts)]
    s = chocs.stats_block(w, f"fenetre {name} [{start}->{end}]")
    print()
    chocs.print_stats(s)
    if s["n"]:
        print(f"    vs {ref_bloc1['label']} : EV={ref_bloc1['ev']:+.4f}R (delta {s['ev']-ref_bloc1['ev']:+.4f}R)")
        import numpy as np
        # z-test approx (meme convention que le script de base : indicatif, pas de conclusion formelle a ces n)
        if s["n"] > 1 and not pd.isna(s["se"]) and not pd.isna(ref_bloc1["se"]):
            se_diff = (s["se"] ** 2 + ref_bloc1["se"] ** 2) ** 0.5
            z = (s["ev"] - ref_bloc1["ev"]) / se_diff if se_diff > 0 else float("nan")
            print(f"    z (approx, se combinees) = {z:+.3f}")
    else:
        print("    (aucun trade dans la fenetre)")
    chocs.trailing_detail(w)
    return s, ref_bloc1


def main():
    pop_a = chocs.load_pop_a()
    pop_b = chocs.load_pop_b()
    edges = chocs.common_bloc_edges(pop_a, pop_b)
    print("Bloc edges (communs A/B) :", list(edges))
    print(f"Fenetre Omicron testee : {OMICRON_WINDOW}")

    print("\n" + "=" * 95)
    print("VERIFICATION COUVERTURE DE DONNEES (la fenetre est-elle meme couverte ?)")
    print("=" * 95)
    print(f"  pop A   : min={pop_a['date_creation'].min()}  (fenetre commence 2021-11-24)")
    print(f"  pop B   : min={pop_b['date_creation'].min()}  (fenetre commence 2021-11-24)")

    res_a = analyze_omicron(pop_a, "A (0.15x trailing)", edges)
    res_b = analyze_omicron(pop_b, "B_tradable_pgp (n=1248, 0.10x trailing)", edges)

    print("\n" + "=" * 95)
    print("SYNTHESE -- comparaison au pattern des 4 chocs deja testes")
    print("=" * 95)
    print("Rappel (chantier_fenetres_macro_chocs_log_2026-08-23.txt) :")
    print("  SVB            : A delta=+0.82R | B delta=-1.01R  (A resiste, B souffre)")
    print("  Dette US/Fitch : A delta=+0.61R | B delta=-0.04R  (neutre les 2)")
    print("  Ukraine        : A delta=+2.51R | B delta=+0.91R  (positif les 2)")
    print("  Israel-Hamas   : A delta=+0.00R | B delta=-1.03R  (A neutre, B souffre)")
    sa, ref_a = res_a
    sb, ref_b = res_b
    da = sa["ev"] - ref_a["ev"] if sa["n"] else float("nan")
    db = sb["ev"] - ref_b["ev"] if sb["n"] else float("nan")
    print(f"  Omicron (NOUVEAU) : A delta={da:+.2f}R (n={sa['n']}) | B delta={db:+.2f}R (n={sb['n']})")
    print()
    if sb["n"] and sa["n"]:
        if db < -0.3 and da > -0.3:
            print("  -> Meme pattern que SVB/Israel-Hamas (A resiste/neutre, B souffre) : renforce")
            print("     l'hypothese 'forme du choc' (retournement en V) plutot que 'cause du choc'.")
        elif db > -0.3 and da > -0.3:
            print("  -> Pattern different de SVB/Israel-Hamas (B NE souffre PAS ici) : affaiblit")
            print("     l'hypothese generale, suggere que SVB/Israel-Hamas etaient plutot")
            print("     specifiques a une periode B (fin 2023) qu'a la forme 'retournement en V'.")
        else:
            print("  -> Pattern mixte/ambigu, a interpreter avec prudence (n petit).")


if __name__ == "__main__":
    main()
