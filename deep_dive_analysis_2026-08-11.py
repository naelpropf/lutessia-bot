"""
Analyse distributionnelle (08/11) des 10 journaux de runs negatifs extraits
par etape_am_deep_dive_negative_runs_2026-08-11.py (n=600x2 plafonds,
moteur cadence-corrigee). n tres petit (9 runs @1000$, 1 @3000$) -- toutes
les statistiques sont rapportees en EFFECTIFS BRUTS, pas en moyennes
lissees, comme demande.

CAVEAT IMPORTANT sur le "trade declencheur" logue a chaque casse : le
ticker/R rapporte est celui du DERNIER trade traite pour ce compte au
moment ou le breach est detecte -- pas necessairement "la cause" du
breach. Avec max 3 positions simultanees, plusieurs trades peuvent
clore le meme jour calendaire sur le meme compte ; le DD journalier/max
est une fonction de l'etat CUMULE du compte, pas de ce seul trade. Un
trade gagnant peut donc apparaitre comme "declencheur" si des pertes
anterieures le meme jour avaient deja fait basculer le compte. A garder
en tete en lisant les tickers/R individuels ci-dessous.

N'importe pas ce script directement (convention du projet).
"""
import json
import os
from collections import defaultdict

LOG_DIR = "deep_dive_logs"


def load_all_runs():
    runs = []
    for fname in sorted(os.listdir(LOG_DIR)):
        with open(os.path.join(LOG_DIR, fname), encoding="utf-8") as f:
            runs.append(json.load(f))
    return runs


if __name__ == "__main__":
    runs = load_all_runs()
    print(f"Runs negatifs charges : {len(runs)}")
    for r in runs:
        print(f"  {r['run_id']} : net_final={r['net_final']:+.0f}$, {len(r['events'])} evenements")

    # --- Point 1 : distribution des casses par firm, position dans la sequence ---
    print("\n=== POINT 1 : casses par firm, position dans la sequence de casses du run ===")
    firm_first_break = defaultdict(int)
    firm_any_break = defaultdict(int)
    firm_break_positions = defaultdict(list)  # rang (1=premiere casse du run) par firm
    for r in runs:
        casses = [e for e in r["events"] if e["type_evenement"] == "casse"]
        casses.sort(key=lambda e: e["jour_simulation"])
        for i, c in enumerate(casses, start=1):
            firm_any_break[c["firm"]] += 1
            firm_break_positions[c["firm"]].append(i)
        if casses:
            firm_first_break[casses[0]["firm"]] += 1
    print(f"{'Firm':12s} {'1ere casse du run (compte)':28s} {'Total casses (toutes positions)':32s} {'Rangs observes'}")
    all_firms = sorted(set(list(firm_first_break.keys()) + list(firm_any_break.keys())))
    for firm in all_firms:
        ranks = firm_break_positions[firm]
        print(f"{firm:12s} {firm_first_break[firm]:28d} {firm_any_break[firm]:32d} {sorted(ranks)}")

    # --- Point 2 : jours depuis dernier flush au moment des casses ---
    print("\n=== POINT 2 : distribution 'jours depuis dernier flush' au moment des casses ===")
    print("(uniquement les casses sur firms a cycle de payout : Blueberry/GFT/Fivers -- "
          "FTMO/FundedNext n'ont pas de cycle, valeur toujours None pour elles)")
    jours_par_firm = defaultdict(list)
    for r in runs:
        for e in r["events"]:
            if e["type_evenement"] == "casse" and e.get("jours_depuis_dernier_flush") is not None:
                jours_par_firm[e["firm"]].append(e["jours_depuis_dernier_flush"])
    for firm, vals in sorted(jours_par_firm.items()):
        vals_sorted = sorted(vals)
        print(f"{firm:12s} n={len(vals):3d} valeurs (jours) = {[round(v,2) for v in vals_sorted]}")
    print("Pour reference, cadence de cycle par firm (jours) : Blueberry=7 (1er)/7 (suiv, "
          "Run F) ou 14/14 (Run C standard -- CE journal vient de Run C standard, cadence "
          "14j/14j Blueberry, 3j/1,5j GFT, 14j/14j Fivers) -- une concentration proche de la "
          "borne haute de cette cadence signalerait un probleme de timing, une repartition "
          "uniforme sur [0, cadence] signalerait une pure variance independante du cycle.")

    # --- Point 3 : ecart temporel entre casses consecutives dans un meme run ---
    print("\n=== POINT 3 : ecarts (jours) entre casses consecutives, par run ===")
    for r in runs:
        casses = sorted([e for e in r["events"] if e["type_evenement"] == "casse"], key=lambda e: e["jour_simulation"])
        if len(casses) < 2:
            print(f"{r['run_id']:24s} : {len(casses)} casse(s), pas d'ecart calculable")
            continue
        gaps = [round(casses[i+1]["jour_simulation"] - casses[i]["jour_simulation"], 2) for i in range(len(casses)-1)]
        print(f"{r['run_id']:24s} : {len(casses)} casses, ecarts (jours) = {gaps}")

    # --- Point 4 : forfeiture reelle vs simple exposition au delai ---
    print("\n=== POINT 4 : forfeiture reelle (pending_payout perdu) vs casses sans pending en attente ===")
    total_forfeited = 0.0
    n_casse_avec_pending = 0
    n_casse_sans_pending = 0
    n_casse_total_payout_firms = 0
    forfeited_by_firm = defaultdict(float)
    for r in runs:
        for e in r["events"]:
            if e["type_evenement"] == "casse" and e["firm"] in ("Blueberry", "GFT", "Fivers"):
                n_casse_total_payout_firms += 1
                perdu = e.get("pending_payout_perdu", 0.0) or 0.0
                total_forfeited += perdu
                forfeited_by_firm[e["firm"]] += perdu
                if perdu > 0:
                    n_casse_avec_pending += 1
                else:
                    n_casse_sans_pending += 1
    print(f"Casses sur firms a cycle de payout (Blueberry/GFT/Fivers) : {n_casse_total_payout_firms}")
    print(f"  dont AVEC pending_payout perdu (forfeiture reelle survenue) : {n_casse_avec_pending}")
    print(f"  dont SANS aucun pending_payout en attente (casse 'propre', aucun angle de timing) : {n_casse_sans_pending}")
    print(f"Total $ forfeite sur ces 10 runs negatifs : {total_forfeited:,.2f}$")
    for firm, amt in sorted(forfeited_by_firm.items()):
        print(f"  {firm:12s} : {amt:,.2f}$")

    # --- Point 5 : nombre de casses par run negatif, firms distinctes ---
    print("\n=== POINT 5 : casses par run negatif et firms distinctes touchees ===")
    for r in runs:
        casses = [e for e in r["events"] if e["type_evenement"] == "casse"]
        firms_touched = sorted(set(e["firm"] for e in casses))
        print(f"{r['run_id']:24s} : {len(casses):3d} casses, {len(firms_touched)} firms distinctes {firms_touched}")

    # --- Point 6 : pre/post-deblocage du moment de bascule (1er hit_ceiling) ---
    print("\n=== POINT 6 : moment du 1er hit_ceiling (pre vs post-deblocage) ===")
    n_pre, n_post, n_never = 0, 0, 0
    for r in runs:
        hc_events = [e for e in r["events"] if e["type_evenement"] == "hit_ceiling_touche"]
        if not hc_events:
            n_never += 1
            print(f"{r['run_id']:24s} : jamais de hit_ceiling")
            continue
        first_hc = hc_events[0]
        phase = first_hc["phase_deblocage"]
        if phase == "pre":
            n_pre += 1
        else:
            n_post += 1
        print(f"{r['run_id']:24s} : 1er hit_ceiling au jour {first_hc['jour_simulation']:.1f} ({phase}-deblocage)")
    print(f"\nTotal : {n_pre} pre-deblocage, {n_post} post-deblocage, {n_never} sans hit_ceiling (sur {len(runs)} runs)")
