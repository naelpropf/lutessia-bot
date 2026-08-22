"""chantier_cluster_budget_verification_2026-08-23.py

Extension du test cluster metaux a 3 familles (metaux/FX Majors/Indices US),
demande explicite : verification code (le moteur modelise-t-il un budget de
cluster partage, ou seulement le cap 1,5%/trade individuel ?) + frequence de
co-occurrence + perte combinee sur B_tradable_pgp complet.

PARTIE 1 -- VERIFICATION CODE (citation directe, pas de supposition) :
  - engine_multiformat.py::process_trade_mf ligne 326 :
    `if any(t in excluded_map[trade["ticker"]] for (t,_) in acc["open_positions"]): return False`
    -- BLOCAGE BINAIRE (le 2e trade est simplement REJETE, pas d'ouverture),
    PAS un budget de risque partage. S'applique uniquement si |correlation|
    STRICTEMENT > seuil (0,80, monte_carlo_simulation.py::precompute_
    correlation_pairs ligne 83 : `abs(corr_matrix.loc[a,b]) > threshold`)
    OU regle JPY-JPY speciale (deux paires JPY toujours exclues entre elles).
  - chantier_S1_8_regen_population_2026-08-19.py lignes 494-498 :
    BB_INSTANT_RISK_CAP=1,5% applique APRES tout multiplicateur, mais
    TOUJOURS par trade individuel -- aucune reference a un cluster ou a la
    somme des positions ouvertes ailleurs dans tout run_one() (verifie par
    lecture complete des ~500 lignes, aucune occurrence de "cluster" ni de
    logique d'agregation de risque inter-positions).
  CONCLUSION CODE (les 3 familles) : AUCUN budget de cluster modelise nulle
  part -- seulement (a) cap fixe 1,5%/trade Instant seul, (b) exclusion
  binaire |corr|>0,80 qui BLOQUE l'ouverture simultanee pour les paires
  au-dessus du seuil, mais laisse les paires EN-DESSOUS du seuil totalement
  libres et non plafonnees en risque combine.

PARTIE 2 -- FREQUENCE DE CO-OCCURRENCE + PERTE COMBINEE (donnees, pas de
simulation moteur) : intervalles [date_creation, resolution_time_est] par
trade, recherche de chevauchements PAR PAIRE au sein de chaque cluster,
report n occurrences / % jours de trading / R combine moyen-pire.
"""
import itertools

import pandas as pd

POP_B_PATH = "chantier_gold_silver_pop_B_tradable_pgp_2026-08-20.csv"

CLUSTERS = {
    "metaux_or_argent": None,  # rempli dynamiquement (tickers GOLD*/SILVER*)
    "fx_majors": {"EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "USD/CAD", "AUD/USD", "NZD/USD"},
    "indices_us": None,  # rempli dynamiquement (NASDAQ100*/S&P500*)
}


def load_pop(path):
    pop = pd.read_csv(path)
    pop["date_creation"] = pd.to_datetime(pop["date_creation"])
    pop["resolution_time_est"] = pd.to_datetime(pop["resolution_time_est"])
    return pop


def cluster_membership(pop, cluster_name, cluster_set):
    if cluster_name == "metaux_or_argent":
        return set(t for t in pop["ticker"].unique() if t.startswith("GOLD") or t.startswith("SILVER"))
    if cluster_name == "indices_us":
        return set(t for t in pop["ticker"].unique() if "NASDAQ" in t.upper() or "S&P" in t.upper())
    return cluster_set


def analyze_cluster(pop, label, cluster_name, cluster_set):
    members = cluster_membership(pop, cluster_name, cluster_set)
    present = sorted(t for t in members if t in set(pop["ticker"].unique()))
    absent_from_pop = sorted(t for t in members if t not in set(pop["ticker"].unique())) if cluster_set else []
    sub = pop[pop["ticker"].isin(present)].copy()
    sub = sub.sort_values("date_creation").reset_index(drop=True)
    n_trades = len(sub)

    print(f"\n{'='*90}\n[{label}] Cluster '{cluster_name}' -- membres presents dans la population : {present}", flush=True)
    if absent_from_pop:
        print(f"  membres NOMMES mais ABSENTS de la population (jamais tradables) : {absent_from_pop}", flush=True)
    print(f"  n trades sur ces tickers : {n_trades} / {len(pop)} ({100*n_trades/len(pop):.1f}% de la population)", flush=True)

    if n_trades < 2:
        print("  (pas assez de trades pour chercher des chevauchements)", flush=True)
        return

    intervals = list(zip(sub["date_creation"], sub["resolution_time_est"], sub["ticker"],
                          sub["r_trailing"], sub["statut_final"]))
    overlaps = []
    for (s1, e1, t1, r1, st1), (s2, e2, t2, r2, st2) in itertools.combinations(intervals, 2):
        if t1 == t2:
            continue
        if s1 < e2 and s2 < e1:
            r1_eff = r1 if st1 == "OBJECTIF ATTEINT" else -1.0
            r2_eff = r2 if st2 == "OBJECTIF ATTEINT" else -1.0
            overlaps.append(dict(t1=t1, t2=t2, s1=s1, s2=s2, r1=r1_eff, r2=r2_eff, combined_r=r1_eff + r2_eff))

    n_overlap = len(overlaps)
    trading_days = sub["date_creation"].dt.date.nunique()
    print(f"  co-occurrences (paires de tickers differents avec fenetres qui se chevauchent) : {n_overlap}", flush=True)
    print(f"  jours de trading distincts sur ce cluster : {trading_days} -- "
          f"{'N/A (0 trade)' if trading_days==0 else f'{100*min(n_overlap,trading_days)/trading_days:.1f}% (borne haute, un jour peut avoir plusieurs co-occurrences)'}", flush=True)

    if n_overlap:
        combined = [o["combined_r"] for o in overlaps]
        print(f"  R combine (2 positions) : moyenne={sum(combined)/len(combined):+.3f}R, "
              f"pire={min(combined):+.3f}R, meilleur={max(combined):+.3f}R", flush=True)
        both_neg = [o for o in overlaps if o["r1"] < 0 and o["r2"] < 0]
        print(f"  co-occurrences avec LES 2 positions perdantes simultanement (-1R chacune, pire cas reel) : "
              f"{len(both_neg)}/{n_overlap} ({100*len(both_neg)/n_overlap:.1f}%)", flush=True)
        worst5 = sorted(overlaps, key=lambda o: o["combined_r"])[:5]
        print("  5 pires co-occurrences (ticker1, ticker2, R1, R2, R combine) :", flush=True)
        for o in worst5:
            print(f"    {o['t1']:20s} / {o['t2']:20s} : R1={o['r1']:+.2f} R2={o['r2']:+.2f} combine={o['combined_r']:+.2f}", flush=True)


def main():
    pop_b = load_pop(POP_B_PATH)
    print(f"Population B_tradable_pgp : n={len(pop_b)}, {pop_b['date_creation'].min()} -> {pop_b['date_creation'].max()}", flush=True)

    for cname, cset in CLUSTERS.items():
        analyze_cluster(pop_b, "B_tradable_pgp", cname, cset)

    # Population A -- verifie separement si FX Majors y est present
    import importlib.util
    spec = importlib.util.spec_from_file_location("bsl", "chantier_gold_silver_B_seule_lancement_2026-08-19.py")
    bsl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bsl)
    pop_a, _, _, _, _, _ = bsl.load_scenario("A")
    pop_a = pop_a.copy()
    pop_a["date_creation"] = pd.to_datetime(pop_a["date_creation"])
    pop_a["resolution_time_est"] = pd.to_datetime(pop_a["resolution_time_est"])
    print(f"\n\nPopulation A : n={len(pop_a)}, {pop_a['date_creation'].min()} -> {pop_a['date_creation'].max()}", flush=True)
    for cname, cset in CLUSTERS.items():
        analyze_cluster(pop_a, "A", cname, cset)


if __name__ == "__main__":
    main()
