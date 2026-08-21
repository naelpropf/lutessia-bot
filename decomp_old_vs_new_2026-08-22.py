"""decomp_old_vs_new_2026-08-22.py

Point D volet B (demande utilisateur) : decompose le saut de profit_moy
bloc1/bloc2 en (i) effet EV-par-trade direct et (ii) effet indirect
survie/compounding, en rejouant les populations OLD (pre-toute-correction
du 22/08) dans EXACTEMENT le meme moteur/seed que les populations NEW deja
mesurees -- comparaison directe, pas d'estimation."""
import importlib.util
import time

import pandas as pd

_spec = importlib.util.spec_from_file_location("bsl", "chantier_gold_silver_B_seule_lancement_2026-08-19.py")
bsl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bsl)
s18 = bsl.s18
abm = bsl.abm
ei = bsl.ei

from monte_carlo_simulation import precompute_correlation_pairs


def load_old_A():
    pop = pd.read_csv("chantier_gold_silver_pop_A_config0_2026-08-19.csv")
    pop["date_creation"] = pd.to_datetime(pop["date_creation"])
    pop["resolution_time_est"] = pd.to_datetime(pop["resolution_time_est"])
    market_data = s18.build_market_data_with_indices()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, abm.CORR_TH_NEW)
    return pop, market_data, excluded_map, abm.ALPHA_POST, abm.BETA_POST, "A_OLD_pre_fix"


def load_old_B():
    unconstrained = {"tick_size": 1.0, "tick_value": 1.0, "volume_min": 0.0001,
                      "volume_max": 1e9, "volume_step": 0.0001, "margin_per_lot": 0.0001, "price": 1.0}
    pop = pd.read_csv("chantier_gold_silver_pop_B_tradable_pgp_OLD_PRE_FIX_2026-08-22.csv")
    pop["date_creation"] = pd.to_datetime(pop["date_creation"])
    pop["resolution_time_est"] = pd.to_datetime(pop["resolution_time_est"])
    market_data = s18.build_market_data_with_indices()
    for label in list(abm.GOLD_SILVER_LABELS) + ["PALLADIUM", "PLATINUM"]:
        market_data[label] = dict(unconstrained)
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, abm.CORR_TH_NEW)
    return pop, market_data, excluded_map, 625, 625, "B_OLD_pre_fix"


def common_calendar_bounds_old():
    pop_A, _, _, _, _, _ = load_old_A()
    pop_B, _, _, _, _, _ = load_old_B()
    return min(pop_A["date_creation"].min(), pop_B["date_creation"].min()), \
        max(pop_A["date_creation"].max(), pop_B["date_creation"].max())


def run_old(scenario, n_sims, ceiling, seed=13579):
    pop, market_data, excluded_map, alpha_post, beta_post, label = (load_old_A() if scenario == "A" else load_old_B())
    lo, hi = common_calendar_bounds_old()
    parts = bsl.date_subperiods_single(pop, 4, lo=lo, hi=hi)
    rows = []
    for i, sub in enumerate(parts[:2]):  # bloc1, bloc2 seulement
        if len(sub) < 10:
            print(f"[bloc{i+1}] trop petit (n={len(sub)}) -- ignore")
            continue
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
        row = s18.summarize(df, f"{label}_bloc{i+1}", ceiling, bb_th, True)
        row["n_trades"] = len(sub)
        row["EV_r_trailing"] = sub["r_trailing"].mean()
        rows.append(row)
        print(f"[bloc{i+1} c={ceiling:.0f}$] profit_moy={row['profit_moyen']:+,.0f}$ "
              f"solde_neg_an4={row['solde_negatif_annee4']:.2f}% n={len(sub)} EV={row['EV_r_trailing']:+.4f}R "
              f"({time.time()-t0:.0f}s)", flush=True)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    print("=== A OLD (pre-fix) ===", flush=True)
    df_a_old = run_old("A", 100, 3000.0)
    df_a_old.to_csv("decomp_A_old_2026-08-22.csv", index=False)
    print("\n=== B OLD (pre-fix) ===", flush=True)
    df_b_old = run_old("B", 100, 3000.0)
    df_b_old.to_csv("decomp_B_old_2026-08-22.csv", index=False)
