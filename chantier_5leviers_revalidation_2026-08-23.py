"""chantier_5leviers_revalidation_2026-08-23.py

Re-validation des 5 leviers du registre (V2, S1.8, S2.35, FTMO-10%/GFT Goat
Guard, payout/forfeiture) sur donnees r_trailing CORRIGEES (post-fix commit
df261dc, backfill MT5/Dukascopy/TradingView complet bloc1/bloc2).

Reutilise TEL QUEL le moteur de chantier_rrtp2_sizing_2026-08-16.py (copie
figee de la lignee cascade officielle -- FIRMS, engine_multiformat, block
bootstrap real_cash_risk_year1_block_bootstrap.build_blocks +
reference_metrics_final.build_full_block_bootstrap_sequence, meme
common_kwargs que chantier_S1_8_regen_population_2026-08-19.py) -- ce script
est le seul de la lignee a exposer `size_func`/`routing_field` (necessaire
pour S2.35) EN PLUS de b_entry_frac/b_reduction (V2), bb_threshold/use_any_rr
(S1.8), ftmo_discount/gft_goat_guard (FTMO-10%/GoatGuard), payout_cycle
(payout/forfeiture) -- un seul moteur pour ablater les 5 leviers un par un,
depuis le MEME point de depart ("FULL" = pile officielle actuelle = COMBINE
S1.8+V2+FTMO-10%+GoatGuard+payout, sans S2.35, exactement la reference
"COMBINE" du registre S2.35).

Population : load_common() de chantier_rrtp2_sizing_2026-08-16.py appelle
build_population_with_trailing("fixed", 0.15, min_rr=1.35) -- CE SCRIPT ETANT
LANCE AUJOURD'HUI, cet appel passe par tp_sequence_analysis.fetch_h1_history
DEJA CORRIGE (MT5 backfill) -> population automatiquement corrigee, memes
filtres/parametres que la population originale (RR>=1.35, trailing 0.15x A).

Chaque levier : FULL (n=600) vs FULL-moins-ce-levier (n=600), memes ceilings
que la validation originale la plus contraignante ([1000,3000] -- sous-
ensemble commun a V2/FTMO-GoatGuard/payout ; S1.8/S2.35 avaient aussi 960/
5000 a l'origine, non retestes ici par contrainte de temps, note explicite).

Pour S1.8 et S2.35 (vigilance maximale demandee) : run supplementaire sur le
sous-ensemble bloc1+bloc2 SEUL (date_creation < 2023-12-17, la portion
100% exposee au bug) en plus du run sur la population complete.

Usage : python chantier_5leviers_revalidation_2026-08-23.py <lever> <n_sims>
  <lever> in {V2, S1_8, FTMO_GoatGuard, payout, S2_35}
"""
import importlib.util
import sys
import time

import pandas as pd

_spec = importlib.util.spec_from_file_location("rr2", "chantier_rrtp2_sizing_2026-08-16.py")
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


def main():
    lever = sys.argv[1] if len(sys.argv) > 1 else "V2"
    n_sims = int(sys.argv[2]) if len(sys.argv) > 2 else 600
    assert lever in ABLATIONS, f"levier inconnu : {lever}"

    print(f"{'='*90}\nLEVIER : {lever}  (n_sims={n_sims}, ceilings={CEILINGS})\n{'='*90}", flush=True)
    pop, market_data, excluded_map = rr2.load_common()
    # <<< meme correctif que chantier_S1_8_regen_population_2026-08-19.py::
    # build_market_data_with_indices() (population elargie post fix forex-only
    # inclut des labels index absents de forex_market_data.json) -- necessaire
    # ici car chantier_rrtp2_sizing_2026-08-16.py::load_common() date d'avant
    # ce fix et n'applique pas ce patch.
    unconstrained = {"tick_size": 1.0, "tick_value": 1.0, "volume_min": 0.0001,
                      "volume_max": 1e9, "volume_step": 0.0001, "margin_per_lot": 0.0001, "price": 1.0}
    for label in ["DAX40 FULL0926", "DAX40 PERF INDEX",
                  "NASDAQ100 - MINI NASDAQ100 FULL0926", "NASDAQ100 INDEX",
                  "S&P500 - MINI S&P500 FULL0926"]:
        market_data[label] = dict(unconstrained)
    print(f"[verif] population (RR>={rr2.MIN_RR_NEW}, corrigee aujourd'hui) : {len(pop)} trades, "
          f"{pop['date_creation'].min()} -> {pop['date_creation'].max()}", flush=True)

    rows = []
    for ceiling in CEILINGS:
        row_full = run_config(pop, market_data, excluded_map, ceiling, n_sims, f"FULL c={ceiling:.0f}", {})
        row_abl = run_config(pop, market_data, excluded_map, ceiling, n_sims, f"FULL_moins_{lever} c={ceiling:.0f}",
                              dict(ABLATIONS[lever]))
        rows.append(row_full); rows.append(row_abl)
        delta_profit = (row_full["profit_moyen"] - row_abl["profit_moyen"]) / abs(row_abl["profit_moyen"]) * 100
        print(f"  -> apport du levier {lever} a {ceiling:.0f}$ : delta profit = {delta_profit:+.2f}% "
              f"(FULL vs FULL-moins-{lever}), delta solde_neg = {row_full['solde_negatif_annee4']-row_abl['solde_negatif_annee4']:+.2f}pts, "
              f"delta annee1<0 = {row_full['annee1_neg']-row_abl['annee1_neg']:+.2f}pts", flush=True)

    if lever in STRESS_LEVERS:
        print(f"\n{'='*90}\nSTRESS-TEST {lever} -- sous-population bloc1+bloc2 SEULE (100% exposee au bug, < {BLOC2_END.date()})\n{'='*90}", flush=True)
        pop_b12 = pop[pop["date_creation"] < BLOC2_END].reset_index(drop=True)
        print(f"[verif] sous-population bloc1+bloc2 : {len(pop_b12)} trades", flush=True)
        for ceiling in CEILINGS:
            row_full = run_config(pop_b12, market_data, excluded_map, ceiling, n_sims, f"BLOC12_FULL c={ceiling:.0f}", {})
            row_abl = run_config(pop_b12, market_data, excluded_map, ceiling, n_sims, f"BLOC12_moins_{lever} c={ceiling:.0f}",
                                  dict(ABLATIONS[lever]))
            rows.append(row_full); rows.append(row_abl)
            delta_profit = (row_full["profit_moyen"] - row_abl["profit_moyen"]) / abs(row_abl["profit_moyen"]) * 100
            print(f"  -> [bloc1+2 seul] apport du levier {lever} a {ceiling:.0f}$ : delta profit = {delta_profit:+.2f}%, "
                  f"delta solde_neg = {row_full['solde_negatif_annee4']-row_abl['solde_negatif_annee4']:+.2f}pts, "
                  f"delta annee1<0 = {row_full['annee1_neg']-row_abl['annee1_neg']:+.2f}pts", flush=True)

    pd.DataFrame(rows).to_csv(f"chantier_5leviers_revalidation_{lever}_2026-08-23.csv", index=False)


if __name__ == "__main__":
    main()
