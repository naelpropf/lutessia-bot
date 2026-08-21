"""chantier_fenetres_macro_chocs_2026-08-23.py

Demande utilisateur (session du 23/08) : isoler la performance de la
strategie sur 4 fenetres courtes correspondant a des chocs macro ponctuels
deja presents dans l'historique de trades, comme points de calibration
partiels face au contexte macro 2026 (guerre Iran/Golfe, dette US, Fed
volatile). Utilise les DEUX populations corrigees qui ont servi au Point D
n=600 (r_trailing recalcule sur donnees reelles, fix commit df261dc) :
- A : chantier_gold_silver_B_seule_lancement_2026-08-19.py::load_scenario("A")
  -> s18.load_common() (0.15x trailing, live, herite le fix primitif)
- B_tradable_pgp : chantier_gold_silver_pop_B_tradable_pgp_2026-08-20.csv
  (n=1248, deja corrigee, generee le 21/08 apres fix)

Les 4 blocs (mêmes bornes que point_d_bloc1_bloc2_2026-08-22.py, calendrier
COMMUN A/B) : bloc1 se termine 2022-08-20, bloc2 se termine 2023-12-17 --
fenetre 3 (Ukraine) tombe dans bloc1, fenetres 1/2/4 (SVB, dette US, Israel-
Hamas) tombent dans bloc2, confirme par l'utilisateur.
"""
import importlib.util

import numpy as np
import pandas as pd

_spec = importlib.util.spec_from_file_location("bsl", "chantier_gold_silver_B_seule_lancement_2026-08-19.py")
bsl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bsl)

POP_B_PATH = "chantier_gold_silver_pop_B_tradable_pgp_2026-08-20.csv"

WINDOWS = [
    ("1_SVB", "2023-03-08", "2023-03-24"),
    ("2_debt_ceiling_fitch", "2023-05-15", "2023-08-15"),
    ("3_ukraine_oil_shock", "2022-02-24", "2022-04-15"),
    ("4_israel_hamas", "2023-10-07", "2023-11-15"),
]


def load_pop_a():
    pop, _, _, alpha_post, beta_post, label = bsl.load_scenario("A")
    pop = pop.copy()
    pop["date_creation"] = pd.to_datetime(pop["date_creation"])
    return pop


def load_pop_b():
    pop = pd.read_csv(POP_B_PATH)
    pop["date_creation"] = pd.to_datetime(pop["date_creation"])
    pop["resolution_time_est"] = pd.to_datetime(pop["resolution_time_est"])
    return pop


def common_bloc_edges(pop_a, pop_b):
    lo = min(pop_a["date_creation"].min(), pop_b["date_creation"].min())
    hi = max(pop_a["date_creation"].max(), pop_b["date_creation"].max())
    return pd.date_range(lo, hi, periods=5)


def stats_block(df, label):
    n = len(df)
    if n == 0:
        return dict(label=label, n=0, wins=0, winrate=float("nan"), ev=float("nan"), se=float("nan"))
    wins = int((df["r_trailing"] > 0).sum())
    ev = df["r_trailing"].mean()
    se = df["r_trailing"].std(ddof=1) / np.sqrt(n) if n > 1 else float("nan")
    return dict(label=label, n=n, wins=wins, winrate=100 * wins / n, ev=ev, se=se)


def print_stats(d):
    print(f"  {d['label']:40s} n={d['n']:4d} wins={d['wins']:4d} winrate={d['winrate']:6.2f}% "
          f"EV={d['ev']:+.4f}R se={d['se']:.4f}")


def trailing_detail(df):
    if len(df) == 0 or "statut_final" not in df.columns:
        return
    print(f"    statuts : {df['statut_final'].value_counts().to_dict()}")
    hold_h = (df["resolution_time_est"] - df["date_creation"]).dt.total_seconds() / 3600
    print(f"    duree de detention (h) : median={hold_h.median():.1f} p25={hold_h.quantile(.25):.1f} p75={hold_h.quantile(.75):.1f}")
    oa = df[df["statut_final"] == "OBJECTIF ATTEINT"]
    if len(oa) and "rr_tp1" in oa.columns:
        ran_far = oa[oa["r_trailing"] > oa["rr_tp1"] * 1.5]
        cut_near_tp1 = oa[(oa["r_trailing"] > 0) & (oa["r_trailing"] <= oa["rr_tp1"] * 1.1)]
        print(f"    parmi OBJECTIF ATTEINT (n={len(oa)}) : {len(ran_far)} ont couru nettement au-dela de TP1 "
              f"(r_trailing > 1.5x rr_tp1), {len(cut_near_tp1)} coupes pres de TP1 (r_trailing <= 1.1x rr_tp1)")
        if len(ran_far):
            print(ran_far[["date_creation", "ticker", "rr_tp1", "r_trailing"]].to_string(index=False))


def analyze(pop, label, edges):
    print(f"\n{'#'*95}\n# Population {label} (n={len(pop)}, {pop['date_creation'].min()} -> {pop['date_creation'].max()})\n{'#'*95}")
    bloc1 = pop[(pop["date_creation"] >= edges[0]) & (pop["date_creation"] < edges[1])]
    bloc2 = pop[(pop["date_creation"] >= edges[1]) & (pop["date_creation"] < edges[2])]
    ref_bloc1 = stats_block(bloc1, "bloc1 ENTIER (reference)")
    ref_bloc2 = stats_block(bloc2, "bloc2 ENTIER (reference)")
    print_stats(ref_bloc1)
    print_stats(ref_bloc2)

    for name, start, end in WINDOWS:
        start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
        w = pop[(pop["date_creation"] >= start_ts) & (pop["date_creation"] < end_ts)]
        ref = ref_bloc1 if name.startswith("3_") else ref_bloc2
        s = stats_block(w, f"fenetre {name} [{start}->{end}]")
        print()
        print_stats(s)
        print(f"    vs {ref['label']} : EV={ref['ev']:+.4f}R (delta {s['ev']-ref['ev']:+.4f}R)" if s['n'] else "    (aucun trade dans la fenetre)")
        trailing_detail(w)


def main():
    pop_a = load_pop_a()
    pop_b = load_pop_b()
    edges = common_bloc_edges(pop_a, pop_b)
    print("Bloc edges (communs A/B) :", list(edges))

    analyze(pop_a, "A (0.15x trailing)", edges)
    analyze(pop_b, "B_tradable_pgp (n=1248, 0.10x trailing)", edges)


if __name__ == "__main__":
    main()
