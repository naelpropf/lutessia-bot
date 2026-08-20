"""Test de sensibilite (point 3, verification bloc1) : les 131 trades
metaux de bloc1 ont 0% de couverture duree reelle (100% fallback median,
tp_sequence_analysis.py -- median calculee GLOBALEMENT sur tout le pool,
pas par periode, or_argent_population_2026-08-19.py:81 "median_duration =
(verified['resolution_time']-verified['date_creation']).median()"
applique uniformement via .fillna() ligne 82). Objectif : verifier si
l'ecart bloc1 B_tradable(29%) vs A-seule(92%) tient sous une hypothese de
duree differente pour ces 131 trades, ou est un artefact du choix de
duree fixe."""
import importlib.util
import time

import pandas as pd

_spec = importlib.util.spec_from_file_location("bsl", "chantier_gold_silver_B_seule_lancement_2026-08-19.py")
bsl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bsl)
abm = bsl.abm
s18 = bsl.s18
import etape_e_fleet_integration as ei
from monte_carlo_simulation import precompute_correlation_pairs

TRADABLE = ["GOLD - USD", "GOLD - GBP", "GOLD - EUR", "GOLD - AUD", "SILVER - AUD", "SILVER - EUR", "SILVER - USD"]
BLOC1_START = pd.Timestamp("2021-04-23 12:43:32")
BLOC1_END = pd.Timestamp("2022-08-20 17:22:34.250000")
MEDIAN_DUR = pd.Timedelta("0 days 08:37:56")


def build_perturbed_bloc1(pop, scale):
    """Retourne bloc1 seul, avec hold_seconds des metaux bloc1 scale par `scale`x
    autour de la duree mediane (les non-metaux/forex de bloc1 restent inchanges --
    leur duree vient d'un pipeline different, tp_sequence_analysis.py, deja
    verifie H1 a un taux different, hors scope de ce test)."""
    oa_all = pd.read_csv("chantier_gold_silver_pop_metaux_all_2026-08-19.csv")
    metal_set = set(oa_all["ticker"].unique())
    sub = pop[(pop["date_creation"] >= BLOC1_START) & (pop["date_creation"] < BLOC1_END)].copy()
    is_metal_bloc1 = sub["ticker"].isin(metal_set)
    new_dur = MEDIAN_DUR * scale
    sub.loc[is_metal_bloc1, "resolution_time_est"] = sub.loc[is_metal_bloc1, "date_creation"] + new_dur
    return sub


if __name__ == "__main__":
    pop = pd.read_csv("chantier_gold_silver_pop_B_config0_tradable_2026-08-19.csv")
    pop["date_creation"] = pd.to_datetime(pop["date_creation"])
    pop["resolution_time_est"] = pd.to_datetime(pop["resolution_time_est"])

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
        sub = build_perturbed_bloc1(pop, scale)
        t0 = time.time()
        df = bsl.run_propagated_custom_alpha(sub, market_data, excluded_map, ceiling, seq, config,
                                              bb_threshold=bb_th, use_any_rr=True, apply_instant_risk_cap=True,
                                              alpha_post=533, beta_post=520, **common_kwargs)
        row = s18.summarize(df, f"bloc1_{label}", ceiling, bb_th, True)
        print(f"[bloc1 duree_scale={label}] profit_moy={row['profit_moyen']:+,.0f}$ "
              f"solde_neg_an4={row['solde_negatif_annee4']:.2f}% annee1<0={row['annee1_neg']:.2f}% "
              f"({time.time()-t0:.0f}s)")
