"""chantier_5leviers_revalidation_fixed_2026-08-23.py

Re-run de chantier_5leviers_revalidation_2026-08-23.py (revalidation des 5
leviers sur A_seule, n=742, qui avait servi a l'adoption formelle de §1.8 et
§2.35 cette session) -- mais sur chantier_rrtp2_sizing_2026-08-19.py au lieu
de -08-16 : verifie par citation de code que -08-16 n'applique JAMAIS le
clamp Blueberry Instant (BB_INSTANT_RISK_CAP=1.5, ligne 89/536-537 de
-08-19), alors que -08-19 l'applique ET expose size_func/routing_field tout
autant (le docstring de la version -08-16 affirmait a tort etre "le seul de
la lignee" a le faire). -08-19 est un sur-ensemble strict, aucune perte de
fonctionnalite. Boucle sur les 5 leviers a la suite (contrairement a
l'original, CLI a un seul levier) pour produire un comparatif direct
avant/apres cap dans un seul CSV.

Usage : python chantier_5leviers_revalidation_fixed_2026-08-23.py <n_sims> [levers_csv]
"""
import importlib.util
import sys
import time

import pandas as pd

_spec = importlib.util.spec_from_file_location("rr2", "chantier_rrtp2_sizing_2026-08-19.py")
rr2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rr2)

CEILINGS = [1000.0, 3000.0]
BB_THRESHOLD_BY_CEILING = {960.0: 5000.0, 1000.0: 5000.0, 3000.0: 0.0, 5000.0: 0.0}
BLOC2_END = pd.Timestamp("2023-12-17")

FULL_KW = dict(b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True,
               ftmo_discount=True, gft_goat_guard=True, payout_cycle=True,
               use_any_rr=True, size_func=None, routing_field="rr_tp1")

ABLATIONS = {
    "V2": dict(b_entry_frac=None, b_reduction=None, pre_unlock_only=False),
    "S1_8": dict(bb_threshold_override=float("inf"), use_any_rr=False),
    "FTMO_GoatGuard": dict(ftmo_discount=False, gft_goat_guard=False),
    "payout": dict(payout_cycle=False),
    "S2_35": dict(size_func=rr2.make_size_func_tail(1.6), routing_field="rr_tp2"),
}
STRESS_LEVERS = {"S1_8", "S2_35"}


def run_config(pop, market_data, excluded_map, ceiling, n_sims, label, overrides):
    kw = dict(FULL_KW)
    bb_threshold = overrides.pop("bb_threshold_override", None)
    kw.update(overrides)
    bb_th = bb_threshold if bb_threshold is not None else BB_THRESHOLD_BY_CEILING[ceiling]
    common_kwargs = dict(emergency=rr2.ei.DEFAULT_EMERGENCY, eval_risk=rr2.EVAL_RISK, fleet_risk=rr2.FLEET_RISK,
                          gft_eval_risk=rr2.GFT_EVAL_RISK, reserve_share=rr2.ei.FINAL_RESERVE_SHARE,
                          extra_threshold_mult=rr2.ei.EXTRA_THRESHOLD_MULT, n_sims=n_sims, seed=9999,
                          b_entry_frac=kw["b_entry_frac"], b_reduction=kw["b_reduction"],
                          pre_unlock_only=kw["pre_unlock_only"], ftmo_discount=kw["ftmo_discount"],
                          gft_goat_guard=kw["gft_goat_guard"], payout_cycle=kw["payout_cycle"])
    seq = rr2.ei.seq_grouped_multi(1000, 15000, 25000, 25000)
    config = rr2.ei.CONFIG_REF
    t0 = time.time()
    df = rr2.run_propagated(pop, market_data, excluded_map, ceiling, seq, config,
                             bb_threshold=bb_th, use_any_rr=kw["use_any_rr"],
                             size_func=kw["size_func"], routing_field=kw["routing_field"],
                             **common_kwargs)
    row = rr2.summarize(df, label, ceiling, bb_th, kw["use_any_rr"])
    dt = time.time() - t0
    print(f"[{label} c={ceiling:.0f}$] profit_moy={row['profit_moyen']:+,.0f}$ "
          f"solde_neg={row['solde_negatif_annee4']:.2f}% hit_ceiling={row['hit_ceiling_pct']:.2f}% "
          f"annee1<0={row['annee1_neg']:.2f}% n={n_sims} ({dt:.0f}s)", flush=True)
    return row


def run_lever(lever, pop, pop_b12, market_data, excluded_map, n_sims, rows):
    print(f"{'='*90}\nLEVIER : {lever} sur A_seule REFIXED cap Blueberry (n_sims={n_sims}, ceilings={CEILINGS})\n{'='*90}", flush=True)
    for ceiling in CEILINGS:
        row_full = run_config(pop, market_data, excluded_map, ceiling, n_sims, f"FIXED_FULL_{lever} c={ceiling:.0f}", {})
        row_abl = run_config(pop, market_data, excluded_map, ceiling, n_sims, f"FIXED_FULL_moins_{lever} c={ceiling:.0f}",
                              dict(ABLATIONS[lever]))
        rows.append(row_full); rows.append(row_abl)
        delta_profit = (row_full["profit_moyen"] - row_abl["profit_moyen"]) / abs(row_abl["profit_moyen"]) * 100
        print(f"  -> apport du levier {lever} a {ceiling:.0f}$ (cap actif) : delta profit = {delta_profit:+.2f}% "
              f"delta solde_neg = {row_full['solde_negatif_annee4']-row_abl['solde_negatif_annee4']:+.2f}pts, "
              f"delta annee1<0 = {row_full['annee1_neg']-row_abl['annee1_neg']:+.2f}pts", flush=True)

    if lever in STRESS_LEVERS:
        print(f"\n{'='*90}\nSTRESS-TEST {lever} REFIXED -- bloc1+bloc2 SEUL (< {BLOC2_END.date()})\n{'='*90}", flush=True)
        for ceiling in CEILINGS:
            row_full = run_config(pop_b12, market_data, excluded_map, ceiling, n_sims, f"FIXED_BLOC12_FULL_{lever} c={ceiling:.0f}", {})
            row_abl = run_config(pop_b12, market_data, excluded_map, ceiling, n_sims, f"FIXED_BLOC12_moins_{lever} c={ceiling:.0f}",
                                  dict(ABLATIONS[lever]))
            rows.append(row_full); rows.append(row_abl)
            delta_profit = (row_full["profit_moyen"] - row_abl["profit_moyen"]) / abs(row_abl["profit_moyen"]) * 100
            print(f"  -> [bloc1+2 seul, cap actif] apport du levier {lever} a {ceiling:.0f}$ : delta profit = {delta_profit:+.2f}%, "
                  f"delta solde_neg = {row_full['solde_negatif_annee4']-row_abl['solde_negatif_annee4']:+.2f}pts, "
                  f"delta annee1<0 = {row_full['annee1_neg']-row_abl['annee1_neg']:+.2f}pts", flush=True)


def main():
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    levers = sys.argv[2].split(",") if len(sys.argv) > 2 else list(ABLATIONS.keys())
    for lv in levers:
        assert lv in ABLATIONS, f"levier inconnu : {lv}"

    pop, market_data, excluded_map = rr2.load_common()
    unconstrained = {"tick_size": 1.0, "tick_value": 1.0, "volume_min": 0.0001,
                      "volume_max": 1e9, "volume_step": 0.0001, "margin_per_lot": 0.0001, "price": 1.0}
    for label in ["DAX40 FULL0926", "DAX40 PERF INDEX",
                  "NASDAQ100 - MINI NASDAQ100 FULL0926", "NASDAQ100 INDEX",
                  "S&P500 - MINI S&P500 FULL0926"]:
        market_data[label] = dict(unconstrained)
    print(f"[verif] population A_seule (RR>={rr2.MIN_RR_NEW}, corrigee) : {len(pop)} trades, "
          f"{pop['date_creation'].min()} -> {pop['date_creation'].max()}", flush=True)
    pop_b12 = pop[pop["date_creation"] < BLOC2_END].reset_index(drop=True)
    print(f"[verif] sous-population bloc1+bloc2 : {len(pop_b12)} trades", flush=True)

    rows = []
    for lever in levers:
        run_lever(lever, pop, pop_b12, market_data, excluded_map, n_sims, rows)

    pd.DataFrame(rows).to_csv(f"chantier_5leviers_revalidation_fixed_2026-08-23_n{n_sims}.csv", index=False)


if __name__ == "__main__":
    main()
