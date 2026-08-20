"""Scenario de lancement SEQUENTIEL (2026-08-20) : comparer A seule vs B
seule+metaux (Config0, sans overflow -- A n'existe pas encore dans ce
scenario) pour trancher lequel demarrer en premier. Reutilise le moteur
single-fleet OFFICIEL (chantier_S1_8_regen_population_2026-08-19.py,
s18.run_propagated/run_one) TEL QUEL, sans passer par le moteur double-
flotte (aucune raison de dupliquer -- B seule n'a besoin que d'UN fleet,
exactement le cas d'usage pour lequel s18.run_one a ete concu, deja
valide par comparaison directe cette session)."""
import importlib.util
import sys
import time

import numpy as np
import pandas as pd

_spec = importlib.util.spec_from_file_location("abm", "chantier_ab_metaux_cascade_officiel_2026-08-19.py")
abm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(abm)
s18 = abm.s18
import etape_e_fleet_integration as ei
from real_cash_risk_year1_block_bootstrap import DAYS_PER_MONTH

DAY_SECONDS = 86400
YEAR_SECONDS = 365.25 * DAY_SECONDS
MONTH_SECONDS = DAYS_PER_MONTH * DAY_SECONDS


def date_subperiods_single(pop, n_parts, lo=None, hi=None):
    """<<< CORRECTIF (2026-08-20) : lo/hi optionnels pour imposer une
    grille calendaire COMMUNE entre scenarios (A/B_no_metals/B_tradable
    ont des plages de dates differentes -- B_tradable demarre en 2021-04
    a cause des metaux, A/B_no_metals en 2022-01 -- calculer les bornes
    sur CHAQUE population independamment produit des blocs qui ne
    representent PAS le meme regime de marche, verifie : bloc2 tombait
    2022-08->2023-12 pour B_tradable contre 2023-03->2024-04 pour A/B_no_
    metals, quasi aucun recouvrement). Sans lo/hi : comportement original
    (bornes propres a `pop`), CONSERVE pour compatibilite mais NE DOIT
    PLUS etre utilise pour comparer 2 scenarios entre eux."""
    pop = pop.sort_values("date_creation").reset_index(drop=True)
    if lo is None:
        lo = pop["date_creation"].min()
    if hi is None:
        hi = pop["date_creation"].max()
    edges = pd.date_range(lo, hi, periods=n_parts + 1)
    parts = []
    for i in range(n_parts):
        sub = pop[(pop["date_creation"] >= edges[i]) & (pop["date_creation"] < edges[i + 1])].reset_index(drop=True)
        parts.append(sub)
    return parts


def run_scenario(pop, market_data, excluded_map, alpha_post, beta_post, ceilings, n_sims, label, out_tag, seed=9999):
    seq = ei.seq_grouped_multi(1000, 15000, 25000, 25000)
    config = ei.CONFIG_REF
    common_kwargs = dict(emergency=ei.DEFAULT_EMERGENCY, eval_risk=abm.EVAL_RISK, fleet_risk=abm.FLEET_RISK,
                          gft_eval_risk=abm.GFT_EVAL_RISK, reserve_share=ei.FINAL_RESERVE_SHARE,
                          extra_threshold_mult=ei.EXTRA_THRESHOLD_MULT, n_sims=n_sims, seed=seed,
                          b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True,
                          ftmo_discount=True, gft_goat_guard=True, payout_cycle=True)
    rows = []
    for ceiling in ceilings:
        bb_th = abm.BB_THRESHOLD_BY_CEILING[ceiling]
        t0 = time.time()
        df = run_propagated_custom_alpha(pop, market_data, excluded_map, ceiling, seq, config,
                                          bb_threshold=bb_th, use_any_rr=True, apply_instant_risk_cap=True,
                                          alpha_post=alpha_post, beta_post=beta_post, **common_kwargs)
        row = s18.summarize(df, label, ceiling, bb_th, True)
        rows.append(row)
        print(f"[{label} c={ceiling:.0f}$] profit_moy={row['profit_moyen']:+,.0f}$ "
              f"solde_neg_an4={row['solde_negatif_annee4']:.2f}% hit_ceiling={row['hit_ceiling_pct']:.2f}% "
              f"annee1<0={row['annee1_neg']:.2f}% ({time.time()-t0:.0f}s)")
        pd.DataFrame(rows).to_csv(f"chantier_B_seule_lancement_{out_tag}_2026-08-19.csv", index=False)
    return pd.DataFrame(rows)


def run_propagated_custom_alpha(pop, market_data, excluded_map, ceiling, seq_grouped, format_by_firm, emergency,
                                 eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult, n_sims, seed,
                                 alpha_post, beta_post, **kw):
    """Identique a s18.run_propagated, SEUL changement : alpha_post/beta_post
    parametrables au lieu de ei.ALPHA_POST/BETA_POST fige (necessaire pour
    utiliser la derivation propre a la population B, cf. registre S9.6)."""
    import random
    rng_wr = random.Random(seed)
    rng_boot = random.Random(seed + 1)
    rows = []
    for _ in range(n_sims):
        wr_draw = rng_wr.betavariate(alpha_post, beta_post)
        trades, slot_arrivals = s18.build_flexible_population_with_rr(pop, wr_draw, 1.0, False, random.Random(rng_boot.random()))
        block_seconds = 2 * 30 * DAY_SECONDS
        from real_cash_risk_year1_block_bootstrap import build_blocks
        from reference_metrics_final import build_full_block_bootstrap_sequence
        blocks = build_blocks(trades, slot_arrivals, block_seconds)
        target_duration = slot_arrivals[-1]
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot, target_duration)
        order = list(range(len(raw_trades)))
        res = s18.run_one(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, seq_grouped, format_by_firm,
                           emergency, eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult, **kw)
        rows.append(res)
    return pd.DataFrame(rows)


def load_scenario(mode):
    """Retourne (pop, market_data, excluded_map, alpha_post, beta_post, label)
    pour un des 4 scenarios de lancement sequentiel."""
    from monte_carlo_simulation import precompute_correlation_pairs
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    if mode == "A":
        pop, market_data, excluded_map = s18.load_common()
        return pop, market_data, excluded_map, abm.ALPHA_POST, abm.BETA_POST, "A_seule_ref"

    unconstrained = {"tick_size": 1.0, "tick_value": 1.0, "volume_min": 0.0001,
                      "volume_max": 1e9, "volume_step": 0.0001, "margin_per_lot": 0.0001, "price": 1.0}

    if mode == "B_no_metals":
        # <<< Population B SANS metaux (571 trades, rr_tp1<1,35+tout_indices)
        # ALPHA_POST_B/BETA_POST_B=276/297 DEJA derive (registre_parametres_
        # projet.md S9.6, n=571 wins=275/losses=296, winrate 48,16%) -- non
        # recalcule ici, reutilise tel quel (population identique).
        pop_full = pd.read_csv("chantier_gold_silver_pop_B_config0_2026-08-19.csv")
        pop_full["date_creation"] = pd.to_datetime(pop_full["date_creation"])
        pop_full["resolution_time_est"] = pd.to_datetime(pop_full["resolution_time_est"])
        oa_all = pd.read_csv("chantier_gold_silver_pop_metaux_all_2026-08-19.csv")
        metal_set = set(oa_all["ticker"].unique())
        pop = pop_full[~pop_full["ticker"].isin(metal_set)].reset_index(drop=True)
        market_data = s18.build_market_data_with_indices()
        tickers = sorted(pop["ticker"].unique())
        excluded_map = precompute_correlation_pairs(tickers, corr_matrix, abm.CORR_TH_NEW)
        return pop, market_data, excluded_map, 276, 297, "B_seule_sans_metaux"

    if mode == "B_full":
        pop = abm.build_pop_B()
        market_data = s18.build_market_data_with_indices()
        for label in abm.GOLD_SILVER_LABELS:
            market_data[label] = dict(unconstrained)
        tickers = sorted(pop["ticker"].unique())
        excluded_map = precompute_correlation_pairs(tickers, corr_matrix, abm.CORR_TH_NEW)
        return pop, market_data, excluded_map, abm.ALPHA_POST_B_METAUX, abm.BETA_POST_B_METAUX, "B_seule_Config0_full14"

    if mode == "B_tradable":
        pop = pd.read_csv("chantier_gold_silver_pop_B_config0_tradable_2026-08-19.csv")
        pop["date_creation"] = pd.to_datetime(pop["date_creation"])
        pop["resolution_time_est"] = pd.to_datetime(pop["resolution_time_est"])
        market_data = s18.build_market_data_with_indices()
        for label in abm.GOLD_SILVER_LABELS:
            market_data[label] = dict(unconstrained)
        tickers = sorted(pop["ticker"].unique())
        excluded_map = precompute_correlation_pairs(tickers, corr_matrix, abm.CORR_TH_NEW)
        return pop, market_data, excluded_map, 533, 520, "B_seule_Config0_tradable7"

    raise ValueError(mode)


def common_calendar_bounds():
    """Bornes calendaires COMMUNES aux 3 scenarios de lancement (A,
    B_no_metals, B_tradable) -- IDENTIQUES a l'ancrage deja utilise par le
    stress-test double-flotte original (chantier_ab_metaux_cascade_
    officiel_2026-08-19.py:date_subperiods, min/max de pop_A_config0 ET
    pop_B_config0 14-tickers) pour que les chiffres A-seule DEJA mesures
    cette session restent directement comparables sans reexecution."""
    pop_A = pd.read_csv("chantier_gold_silver_pop_A_config0_2026-08-19.csv")
    pop_B = pd.read_csv("chantier_gold_silver_pop_B_config0_2026-08-19.csv")
    pop_A["date_creation"] = pd.to_datetime(pop_A["date_creation"])
    pop_B["date_creation"] = pd.to_datetime(pop_B["date_creation"])
    return min(pop_A["date_creation"].min(), pop_B["date_creation"].min()), \
        max(pop_A["date_creation"].max(), pop_B["date_creation"].max())


def run_stress(mode, n_sims, ceilings, out_tag, seed=13579, common_window=True):
    pop, market_data, excluded_map, alpha_post, beta_post, label = load_scenario(mode)
    lo, hi = common_calendar_bounds() if common_window else (None, None)
    rows = []
    for n_parts, tag in ((2, "H"), (4, "bloc")):
        parts = date_subperiods_single(pop, n_parts, lo=lo, hi=hi)
        for i, sub in enumerate(parts):
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
                df = run_propagated_custom_alpha(sub, market_data, excluded_map, ceiling,
                                                  ei.seq_grouped_multi(1000, 15000, 25000, 25000), ei.CONFIG_REF,
                                                  bb_threshold=bb_th, use_any_rr=True, apply_instant_risk_cap=True,
                                                  alpha_post=alpha_post, beta_post=beta_post, **common_kwargs)
                row = s18.summarize(df, f"{label}_{tag}{i+1}", ceiling, bb_th, True)
                row["n_trades"] = len(sub)
                rows.append(row)
                print(f"[{tag}{i+1} c={ceiling:.0f}$] profit_moy={row['profit_moyen']:+,.0f}$ "
                      f"solde_neg_an4={row['solde_negatif_annee4']:.2f}% annee1<0={row['annee1_neg']:.2f}% "
                      f"({time.time()-t0:.0f}s)")
                pd.DataFrame(rows).to_csv(f"chantier_B_seule_lancement_stress_{out_tag}_2026-08-19.csv", index=False)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    run_mode = sys.argv[1]  # "sweep" ou "stress"
    scenario = sys.argv[2]  # "A", "B_no_metals", "B_full", "B_tradable"
    n_sims = int(sys.argv[3]) if len(sys.argv) > 3 else 600
    ceilings = [float(x) for x in sys.argv[4].split(",")] if len(sys.argv) > 4 else [3000.0, 5000.0]
    out_tag = sys.argv[5] if len(sys.argv) > 5 else scenario

    if run_mode == "sweep":
        pop, market_data, excluded_map, alpha_post, beta_post, label = load_scenario(scenario)
        run_scenario(pop, market_data, excluded_map, alpha_post, beta_post, ceilings, n_sims, label, out_tag)
    elif run_mode == "stress":
        run_stress(scenario, n_sims, ceilings, out_tag)
