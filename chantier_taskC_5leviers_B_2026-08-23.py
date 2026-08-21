"""chantier_taskC_5leviers_B_2026-08-23.py

TACHE C2 (session du 23/08, suite) : re-test des 5 leviers du registre (V2,
S1.8, S2.35, FTMO-10%/GoatGuard, payout/forfeiture) specifiquement sur
B_tradable_pgp SEULE (n=1248, chantier_gold_silver_pop_B_tradable_pgp_2026-
08-20.csv) -- chantier_5leviers_revalidation_2026-08-23.py avait en realite
teste sur load_common() de chantier_rrtp2_sizing_2026-08-16.py, qui renvoie
n=742 = A_seule (build_population_with_trailing sur historique_lutessia_15k_
force.csv), PAS B ni un mix -- jamais teste sur B jusqu'ici pour aucun des 5
leviers.

Reutilise chantier_rrtp2_sizing_2026-08-19.py (PAS -08-16 : verifie ce jour
par citation de code que -08-16 n'applique JAMAIS le clamp Blueberry Instant
BB_INSTANT_RISK_CAP=1.5 -- ni dans effective_risk() ni ailleurs -- alors que
-08-19 l'applique (ligne 536-537, apres tout multiplicateur/size_func) ET
expose size_func/routing_field tout autant, contrairement a ce qu'affirmait
le docstring de chantier_5leviers_revalidation_2026-08-23.py ; -08-19 est un
sur-ensemble strict de -08-16, aucune perte de fonctionnalite) -- meme
FULL_KW/ABLATIONS que chantier_5leviers_revalidation_2026-08-23.py -- seul
autre changement : la population et le market_data/excluded_map, construits
comme point_d_bloc1_bloc2_2026-08-22.py::load_scenario_pgp()
(s18.build_market_data_with_indices() + labels GOLD/SILVER cross-rate +
PALLADIUM/PLATINUM en "unconstrained", seule maniere connue dans le projet
de couvrir tous les tickers de B_tradable_pgp).

Usage : python chantier_taskC_5leviers_B_2026-08-23.py <n_sims>
  (teste les 5 leviers a la suite, memes ceilings [1000,3000]$ que
  chantier_5leviers_revalidation ; S1_8/S2_35 recoivent en plus le run
  bloc1+bloc2 seul, meme convention)
"""
import importlib.util
import sys
import time

import pandas as pd

_spec = importlib.util.spec_from_file_location("rr2", "chantier_rrtp2_sizing_2026-08-19.py")
rr2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rr2)

_spec2 = importlib.util.spec_from_file_location("pd22", "point_d_bloc1_bloc2_2026-08-22.py")
pd22 = importlib.util.module_from_spec(_spec2)
_spec2.loader.exec_module(pd22)

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


def load_pop_b_full():
    """Population B_tradable_pgp (n=1248) + market_data couvrant TOUS ses
    tickers (forex/indices/metaux/cross-rate) + excluded_map correlation."""
    pop, market_data, excluded_map, _, _, _ = pd22.load_scenario_pgp()
    return pop, market_data, excluded_map


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
    print(f"{'='*90}\nLEVIER : {lever} sur B_tradable_pgp (n_sims={n_sims}, ceilings={CEILINGS})\n{'='*90}", flush=True)
    for ceiling in CEILINGS:
        row_full = run_config(pop, market_data, excluded_map, ceiling, n_sims, f"B_FULL_{lever} c={ceiling:.0f}", {})
        row_abl = run_config(pop, market_data, excluded_map, ceiling, n_sims, f"B_FULL_moins_{lever} c={ceiling:.0f}",
                              dict(ABLATIONS[lever]))
        rows.append(row_full); rows.append(row_abl)
        delta_profit = (row_full["profit_moyen"] - row_abl["profit_moyen"]) / abs(row_abl["profit_moyen"]) * 100
        print(f"  -> [B seule] apport du levier {lever} a {ceiling:.0f}$ : delta profit = {delta_profit:+.2f}% "
              f"(FULL vs FULL-moins-{lever}), delta solde_neg = {row_full['solde_negatif_annee4']-row_abl['solde_negatif_annee4']:+.2f}pts, "
              f"delta annee1<0 = {row_full['annee1_neg']-row_abl['annee1_neg']:+.2f}pts", flush=True)

    if lever in STRESS_LEVERS:
        print(f"\n{'='*90}\nSTRESS-TEST {lever} -- B_tradable_pgp bloc1+bloc2 SEULE (< {BLOC2_END.date()})\n{'='*90}", flush=True)
        for ceiling in CEILINGS:
            row_full = run_config(pop_b12, market_data, excluded_map, ceiling, n_sims, f"B_BLOC12_FULL_{lever} c={ceiling:.0f}", {})
            row_abl = run_config(pop_b12, market_data, excluded_map, ceiling, n_sims, f"B_BLOC12_moins_{lever} c={ceiling:.0f}",
                                  dict(ABLATIONS[lever]))
            rows.append(row_full); rows.append(row_abl)
            delta_profit = (row_full["profit_moyen"] - row_abl["profit_moyen"]) / abs(row_abl["profit_moyen"]) * 100
            print(f"  -> [B bloc1+2 seul] apport du levier {lever} a {ceiling:.0f}$ : delta profit = {delta_profit:+.2f}%, "
                  f"delta solde_neg = {row_full['solde_negatif_annee4']-row_abl['solde_negatif_annee4']:+.2f}pts, "
                  f"delta annee1<0 = {row_full['annee1_neg']-row_abl['annee1_neg']:+.2f}pts", flush=True)


def main():
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    levers = sys.argv[2].split(",") if len(sys.argv) > 2 else list(ABLATIONS.keys())
    for lv in levers:
        assert lv in ABLATIONS, f"levier inconnu : {lv}"

    pop, market_data, excluded_map = load_pop_b_full()
    print(f"[verif] population B_tradable_pgp : {len(pop)} trades, "
          f"{pop['date_creation'].min()} -> {pop['date_creation'].max()}", flush=True)
    pop_b12 = pop[pop["date_creation"] < BLOC2_END].reset_index(drop=True)
    print(f"[verif] sous-population B bloc1+bloc2 : {len(pop_b12)} trades", flush=True)

    rows = []
    for lever in levers:
        run_lever(lever, pop, pop_b12, market_data, excluded_map, n_sims, rows)

    pd.DataFrame(rows).to_csv(f"chantier_taskC_5leviers_B_2026-08-23_n{n_sims}.csv", index=False)


if __name__ == "__main__":
    main()
