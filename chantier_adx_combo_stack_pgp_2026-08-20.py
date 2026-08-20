"""Rafraichit le factoriel §7 (REF/SEQ_SEUL/ADX_SEUL/COMBO) sur la
population B_tradable FINALE avec palladium/platine (n=1248, Beta(625,625)
-- chantier_ab_metaux_tradable_pgp_2026-08-20.py, integration verifiee
independamment ce chantier -- pull VPS + re-execution, n/wins/losses
recontroles sur le CSV, assertions du wrapper repassees).

Meme logique EXACTE que chantier_adx_combo_stack_2026-08-20.py (facteur
2x2 : {jour0, sequentiel 3000$} x {aucun filtre, ADX>32,27 fx-only}) --
reutilise run_config() tel quel (aucune reecriture de la mecanique de
simulation). SEUL changement : source de population/prior, et le
metal_set utilise pour separer forex/indices vs "jamais filtre par
ADX" -- DOIT desormais inclure PALLADIUM et PLATINUM en plus des 7
tickers GOLD/SILVER tradables (sinon ces 2 nouveaux tickers seraient a
tort traites comme du forex/indices et exposes au filtre ADX, ce qui
contredirait le principe "ADX-fx-only, metaux jamais concernes" deja
etabli et confirme causalement sur GOLD/SILVER)."""
import importlib.util
import sys
import time

import numpy as np
import pandas as pd

_spec_stack = importlib.util.spec_from_file_location("stack", "chantier_adx_combo_stack_2026-08-20.py")
stack = importlib.util.module_from_spec(_spec_stack)
_spec_stack.loader.exec_module(stack)

_spec_adxfx = importlib.util.spec_from_file_location("adxfx", "chantier_adx_fx_only_B_tradable_2026-08-20.py")
adxfx = importlib.util.module_from_spec(_spec_adxfx)
_spec_adxfx.loader.exec_module(adxfx)

abm = stack.abm
run_config = stack.run_config
SEQUENTIAL_THRESHOLD = stack.SEQUENTIAL_THRESHOLD  # 3000.0, inchange

POP_PGP_PATH = "chantier_gold_silver_pop_B_tradable_pgp_2026-08-20.csv"
ALPHA_REF, BETA_REF = 625, 625  # Beta(625,625), verifie independamment ce chantier
EXPECTED_N = 1248


def load_pop_B_pgp():
    pop = pd.read_csv(POP_PGP_PATH)
    pop["date_creation"] = pd.to_datetime(pop["date_creation"])
    pop["resolution_time_est"] = pd.to_datetime(pop["resolution_time_est"])
    return pop


# <<< CORRECTIF (2026-08-20) : meme classe de bug que celui deja trouve/
# corrige pour GOLD/SILVER (chantier_ab_metaux_cascade_officiel_2026-08-19.
# py:756-766, market_data n'a pas de specs broker pour les labels metaux ->
# feasible_risk_pct() KeyError). PALLADIUM/PLATINUM n'etaient PAS dans
# GOLD_SILVER_LABELS (liste figee aux 14 tickers or/argent), donc jamais
# couverts -- rate au 1er smoke test (KeyError('PALLADIUM') dans
# feasible_risk_pct, apres avoir deja corrige le meme probleme sur
# correlation_matrix.csv). Wrapper la fonction plutot que modifier le
# fichier officiel (convention du projet, cf. session_handoff_2026-08-20_
# pgp_priors.md point 4).
_orig_build_market_data_and_excluded_map = abm.build_market_data_and_excluded_map


def _build_market_data_and_excluded_map_pgp(pop_A, pop_B):
    market_data, excluded_map = _orig_build_market_data_and_excluded_map(pop_A, pop_B)
    unconstrained = {"tick_size": 1.0, "tick_value": 1.0, "volume_min": 0.0001,
                      "volume_max": 1e9, "volume_step": 0.0001, "margin_per_lot": 0.0001, "price": 1.0}
    for label in ("PALLADIUM", "PLATINUM"):
        market_data[label] = dict(unconstrained)
    return market_data, excluded_map


abm.build_market_data_and_excluded_map = _build_market_data_and_excluded_map_pgp


def build_metal_set_pgp():
    """7 tickers GOLD/SILVER tradables (chantier_gold_silver_pop_metaux_all_
    2026-08-19.csv, deja utilise partout ailleurs) + PALLADIUM/PLATINUM
    (tickers uniques, pas de variante devise -- verifie lors du scraping/EV
    du 20/08). Ces 2 nouveaux tickers ne doivent JAMAIS etre exposes au
    filtre ADX, au meme titre que GOLD/SILVER."""
    oa_all = pd.read_csv(adxfx.POP_METAUX_ALL_CSV)
    metal_set = set(oa_all["ticker"].unique())
    metal_set |= {"PALLADIUM", "PLATINUM"}
    return metal_set


def make_baseline_and_lever_pgp():
    pop_ref = load_pop_B_pgp()
    assert len(pop_ref) == EXPECTED_N, f"Taille de population inattendue : {len(pop_ref)} (attendu {EXPECTED_N})"

    alpha_ref, beta_ref, wins_ref, losses_ref = adxfx.derive_beta_prior(pop_ref)
    print(f"[REF] population n={len(pop_ref)} wins={wins_ref} losses={losses_ref} "
          f"-> Beta({alpha_ref},{beta_ref}) winrate={wins_ref/len(pop_ref)*100:.2f}%")
    assert (alpha_ref, beta_ref) == (ALPHA_REF, BETA_REF), \
        f"derivation REF ne matche pas la reference documentee ({ALPHA_REF},{BETA_REF})"

    metal_set_pgp = build_metal_set_pgp()
    n_metal_rows = pop_ref["ticker"].isin(metal_set_pgp).sum()
    print(f"[verif] {n_metal_rows}/{len(pop_ref)} trades identifies comme metaux "
          f"(jamais ADX-filtres) -- {len(pop_ref)-n_metal_rows} forex/indices (filtrables)")

    pop_adx = adxfx.build_adx_filtered_fx_only(pop_ref, metal_set_pgp)
    alpha_adx, beta_adx, wins_adx, losses_adx = adxfx.derive_beta_prior(pop_adx)
    print(f"[ADX-fx-only] population n={len(pop_adx)} wins={wins_adx} losses={losses_adx} "
          f"-> Beta({alpha_adx},{beta_adx}) winrate={wins_adx/len(pop_adx)*100:.2f}%")

    pop_adx.to_csv("chantier_pop_B_tradable_pgp_adx_fx_only_2026-08-20.csv", index=False)
    return (pop_ref, alpha_ref, beta_ref), (pop_adx, alpha_adx, beta_adx)


def main():
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    ceilings = [float(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [3000.0, 5000.0]
    out_tag = sys.argv[3] if len(sys.argv) > 3 else f"n{n_sims}"

    (pop_ref, a_ref, b_ref), (pop_adx, a_adx, b_adx) = make_baseline_and_lever_pgp()

    configs = [
        ("REF", pop_ref, a_ref, b_ref, None),
        ("SEQ_SEUL", pop_ref, a_ref, b_ref, SEQUENTIAL_THRESHOLD),
        ("ADX_SEUL", pop_adx, a_adx, b_adx, None),
        ("COMBO", pop_adx, a_adx, b_adx, SEQUENTIAL_THRESHOLD),
    ]

    all_rows = []
    for name, pop_v, a_v, b_v, seq_th in configs:
        print(f"\n{'='*78}\n{name} (sequential_threshold={seq_th}, n={n_sims})\n{'='*78}", flush=True)
        df = run_config(pop_v, a_v, b_v, seq_th, n_sims, ceilings)
        df["config"] = name
        all_rows.append(df)
        print(f"[{name}] termine.", flush=True)

    out = pd.concat(all_rows, ignore_index=True)
    out_path = f"chantier_adx_combo_stack_pgp_{out_tag}_2026-08-20.csv"
    out.to_csv(out_path, index=False)
    print(f"\nSauvegarde : {out_path}", flush=True)

    print(f"\n{'='*78}\nDECOMPOSITION ADDITIVE (delta vs REF, profit_moyen)\n{'='*78}", flush=True)
    piv = {name: out[out["config"] == name].set_index(["scope", "ceiling"])["profit_moyen"] for name, *_ in configs}
    for scope in out["scope"].unique():
        for ceiling in ceilings:
            key = (scope, ceiling)
            if key not in piv["REF"].index:
                continue
            ref = piv["REF"][key]
            seq = piv["SEQ_SEUL"][key]
            adx = piv["ADX_SEUL"][key]
            combo = piv["COMBO"][key]
            d_seq = seq - ref
            d_adx = adx - ref
            d_combo = combo - ref
            d_additive = d_seq + d_adx
            interaction = d_combo - d_additive
            pct_interaction = interaction / abs(d_additive) * 100 if d_additive != 0 else float("nan")
            flag = " <<< bloc2" if scope == "bloc2" else ""
            print(f"[{scope} c={ceiling:.0f}$] REF={ref:+,.0f}$ | d_SEQ={d_seq:+,.0f}$ d_ADX={d_adx:+,.0f}$ "
                  f"| additif_attendu={d_additive:+,.0f}$ | COMBO_reel={d_combo:+,.0f}$ "
                  f"| interaction={interaction:+,.0f}$ ({pct_interaction:+.1f}% de l'additif){flag}", flush=True)


if __name__ == "__main__":
    main()
