"""Test de sensibilite bloc2 (meme protocole que chantier_bloc1_sensibilite_
duree_2026-08-19.py) -- utilise la fenetre COMMUNE verifiee identique aux 3
scenarios (A-seule/B_no_metals/B_tradable), PAS la fenetre propre a
B_tradable seule (verification demandee explicitement) : bloc2 =
2022-08-19 18:00:53.750000 -> 2023-12-17 06:27:09.500000 (min/max de
pop_A_config0 UNION pop_B_config0 14-tickers, confirme identique pour les
3 scenarios par calcul direct)."""
import time

import pandas as pd

import importlib.util
_spec = importlib.util.spec_from_file_location("bsl", "chantier_gold_silver_B_seule_lancement_2026-08-19.py")
bsl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bsl)
abm = bsl.abm
s18 = bsl.s18
import etape_e_fleet_integration as ei
from monte_carlo_simulation import precompute_correlation_pairs

BLOC2_START = pd.Timestamp("2022-08-19 18:00:53.750000")
BLOC2_END = pd.Timestamp("2023-12-17 06:27:09.500000")
MEDIAN_DUR = pd.Timedelta("0 days 08:37:56")


def build_perturbed_bloc2(pop, scale):
    oa_all = pd.read_csv("chantier_gold_silver_pop_metaux_all_2026-08-19.csv")
    metal_set = set(oa_all["ticker"].unique())
    sub = pop[(pop["date_creation"] >= BLOC2_START) & (pop["date_creation"] < BLOC2_END)].copy()
    is_metal_bloc2 = sub["ticker"].isin(metal_set)
    new_dur = MEDIAN_DUR * scale
    sub.loc[is_metal_bloc2, "resolution_time_est"] = sub.loc[is_metal_bloc2, "date_creation"] + new_dur
    return sub


if __name__ == "__main__":
    pop = pd.read_csv("chantier_gold_silver_pop_B_config0_tradable_2026-08-19.csv")
    pop["date_creation"] = pd.to_datetime(pop["date_creation"])
    pop["resolution_time_est"] = pd.to_datetime(pop["resolution_time_est"])

    oa_all = pd.read_csv("chantier_gold_silver_pop_metaux_all_2026-08-19.csv")
    metal_set = set(oa_all["ticker"].unique())
    sub_check = pop[(pop["date_creation"] >= BLOC2_START) & (pop["date_creation"] < BLOC2_END)]
    n_metals_bloc2 = sub_check["ticker"].isin(metal_set).sum()
    print(f"[verif] n trades bloc2 total={len(sub_check)}, dont metaux tradable={n_metals_bloc2}")

    market_data = s18.build_market_data_with_indices()
    unconstrained = {"tick_size": 1.0, "tick_value": 1.0, "volume_min": 0.0001,
                      "volume_max": 1e9, "volume_step": 0.0001, "margin_per_lot": 0.0001, "price": 1.0}
    for label in abm.GOLD_SILVER_LABELS:
        market_data[label] = dict(unconstrained)
    tickers = sorted(pop["ticker"].unique())
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, abm.CORR_TH_NEW)

    ceiling = 3000.0
    bb_th = abm.BB_THRESHOLD_BY_CEILING[ceiling]
    seq = ei.seq_grouped_multi(1000, 15000, 25000, 25000)
    config = ei.CONFIG_REF
    common_kwargs = dict(emergency=ei.DEFAULT_EMERGENCY, eval_risk=abm.EVAL_RISK, fleet_risk=abm.FLEET_RISK,
                          gft_eval_risk=abm.GFT_EVAL_RISK, reserve_share=ei.FINAL_RESERVE_SHARE,
                          extra_threshold_mult=ei.EXTRA_THRESHOLD_MULT, n_sims=100, seed=13579,
                          b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True,
                          ftmo_discount=True, gft_goat_guard=True, payout_cycle=True)

    for label, scale in [("original(1.0x)", 1.0), ("0.5x", 0.5), ("1.5x", 1.5), ("2.0x", 2.0)]:
        sub = build_perturbed_bloc2(pop, scale)
        t0 = time.time()
        df = bsl.run_propagated_custom_alpha(sub, market_data, excluded_map, ceiling, seq, config,
                                              bb_threshold=bb_th, use_any_rr=True, apply_instant_risk_cap=True,
                                              alpha_post=533, beta_post=520, **common_kwargs)
        row = s18.summarize(df, f"bloc2_{label}", ceiling, bb_th, True)
        print(f"[bloc2 duree_scale={label}] profit_moy={row['profit_moyen']:+,.0f}$ "
              f"solde_neg_an4={row['solde_negatif_annee4']:.2f}% annee1<0={row['annee1_neg']:.2f}% "
              f"({time.time()-t0:.0f}s)")
