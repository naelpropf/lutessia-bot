"""point_d_bloc1_bloc2_2026-08-22.py

Point D (session 21-22/08) : reproduit la comparaison bloc1/bloc2 du registre
§6.5 (B_tradable seule vs A-seule, solde_negatif%/profit, PAS juste le profit
moyen) qui a motive la decision de lancement sequentiel B->A -- mais sur les
donnees maintenant CORRIGEES (r_trailing metaux resolu a 100% sur bloc1/bloc2,
cf. chantier_bloc2_metaux_synthese_mt5_2026-08-21.py rerun du 22/08 + fix
primitif tp_sequence_analysis.py commit df261dc pour forex/indices, herite
automatiquement par s18.load_common()).

Reutilise TEL QUEL le moteur single-fleet officiel (chantier_gold_silver_
B_seule_lancement_2026-08-19.py : run_propagated_custom_alpha, s18.run_one,
s18.summarize, date_subperiods_single, common_calendar_bounds) -- seul ajout :
un scenario "B_tradable_pgp" qui pointe vers la population COURANTE
(chantier_gold_silver_pop_B_tradable_pgp_2026-08-20.csv, n=1248, corrigee ce
jour) + prior Beta(625,625), au lieu du scenario existant "B_tradable" fige
sur l'ancienne population Config0 (n=1051, SANS Palladium/Platinum, pre-fix).
"""
import importlib.util
import sys
import time

import pandas as pd

_spec = importlib.util.spec_from_file_location("bsl", "chantier_gold_silver_B_seule_lancement_2026-08-19.py")
bsl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bsl)
s18 = bsl.s18
abm = bsl.abm
ei = bsl.ei

POP_B_TRADABLE_PGP_PATH = "chantier_gold_silver_pop_B_tradable_pgp_2026-08-20.csv"
ALPHA_POST_B_PGP, BETA_POST_B_PGP = 625, 625


def load_scenario_pgp():
    from monte_carlo_simulation import precompute_correlation_pairs
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    unconstrained = {"tick_size": 1.0, "tick_value": 1.0, "volume_min": 0.0001,
                      "volume_max": 1e9, "volume_step": 0.0001, "margin_per_lot": 0.0001, "price": 1.0}
    pop = pd.read_csv(POP_B_TRADABLE_PGP_PATH)
    pop["date_creation"] = pd.to_datetime(pop["date_creation"])
    pop["resolution_time_est"] = pd.to_datetime(pop["resolution_time_est"])
    market_data = s18.build_market_data_with_indices()
    for label in list(abm.GOLD_SILVER_LABELS) + ["PALLADIUM", "PLATINUM"]:
        market_data[label] = dict(unconstrained)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, abm.CORR_TH_NEW)
    return pop, market_data, excluded_map, ALPHA_POST_B_PGP, BETA_POST_B_PGP, "B_seule_tradable_pgp_corrige"


def common_calendar_bounds_pgp():
    """Meme convention que bsl.common_calendar_bounds (ancrage commun A/B pour
    comparabilite directe des sous-periodes), mais avec la population B
    courante (pgp, n=1248) au lieu de l'ancienne Config0 14-tickers."""
    pop_A, _, _ = s18.load_common()
    pop_B = pd.read_csv(POP_B_TRADABLE_PGP_PATH)
    pop_B["date_creation"] = pd.to_datetime(pop_B["date_creation"])
    return min(pop_A["date_creation"].min(), pop_B["date_creation"].min()), \
        max(pop_A["date_creation"].max(), pop_B["date_creation"].max())


def run_stress_pgp(scenario, n_sims, ceilings, out_tag, seed=13579, common_window=True):
    if scenario == "A":
        pop, market_data, excluded_map, alpha_post, beta_post, label = bsl.load_scenario("A")
    elif scenario == "B_tradable_pgp":
        pop, market_data, excluded_map, alpha_post, beta_post, label = load_scenario_pgp()
    else:
        raise ValueError(scenario)

    lo, hi = common_calendar_bounds_pgp() if common_window else (None, None)
    rows = []
    parts = bsl.date_subperiods_single(pop, 4, lo=lo, hi=hi)
    for i, sub in enumerate(parts):
        tag = "bloc"
        if len(sub) < 10:
            print(f"[{tag}{i+1}] sous-population trop petite (n={len(sub)}) -- ignore")
            continue
        for ceiling in ceilings:
            bb_th = abm.BB_THRESHOLD_BY_CEILING[ceiling]
            common_kwargs = dict(emergency=ei.DEFAULT_EMERGENCY, eval_risk=abm.EVAL_RISK, fleet_risk=abm.FLEET_RISK,
                                  gft_eval_risk=abm.GFT_EVAL_RISK, reserve_share=ei.FINAL_RESERVE_SHARE,
                                  extra_threshold_mult=ei.EXTRA_THRESHOLD_MULT, n_sims=n_sims, seed=seed,
                                  b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True,
                                  ftmo_discount=True, gft_goat_guard=True, payout_cycle=True)
            t0 = time.time()
            df = bsl.run_propagated_custom_alpha(sub, market_data, excluded_map, ceiling,
                                                  ei.seq_grouped_multi(1000, 15000, 25000, 25000), ei.CONFIG_REF,
                                                  bb_threshold=bb_th, use_any_rr=True, apply_instant_risk_cap=True,
                                                  alpha_post=alpha_post, beta_post=beta_post, **common_kwargs)
            row = s18.summarize(df, f"{label}_{tag}{i+1}", ceiling, bb_th, True)
            row["n_trades"] = len(sub)
            rows.append(row)
            print(f"[{tag}{i+1} c={ceiling:.0f}$] profit_moy={row['profit_moyen']:+,.0f}$ "
                  f"solde_neg_an4={row['solde_negatif_annee4']:.2f}% annee1<0={row['annee1_neg']:.2f}% "
                  f"n={len(sub)} ({time.time()-t0:.0f}s)", flush=True)
            pd.DataFrame(rows).to_csv(f"point_d_bloc1_bloc2_{out_tag}_2026-08-22.csv", index=False)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    ceilings = [float(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [3000.0]
    out_tag = sys.argv[3] if len(sys.argv) > 3 else "screen"

    print(f"{'='*90}\nA seule (donnees corrigees, live via s18.load_common)\n{'='*90}", flush=True)
    df_a = run_stress_pgp("A", n_sims, ceilings, out_tag + "_A")

    print(f"\n{'='*90}\nB_tradable_pgp seule (n=1248, donnees corrigees ce jour)\n{'='*90}", flush=True)
    df_b = run_stress_pgp("B_tradable_pgp", n_sims, ceilings, out_tag + "_B")
