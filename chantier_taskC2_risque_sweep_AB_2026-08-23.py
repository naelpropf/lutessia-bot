"""chantier_taskC2_risque_sweep_AB_2026-08-23.py

TACHE C2 (session du 23/08) : re-optimisation du risque par trade (eval et
funded, meme valeur pour les deux dans chaque point de grille -- convention
registre §2.23 "risque eval 1,25%/funded 1,90%") pour A_seule et
B_tradable_pgp SEPAREMENT, sur donnees a jour (r_trailing corrige, 5 leviers
adoptes actifs -- FULL_KW ci-dessous, y compris S2.35/size_func) et sur le
moteur chantier_rrtp2_sizing_2026-08-19.py (PAS -08-16, cf. chantier_
5leviers_revalidation_fixed_2026-08-23.py -- -08-19 applique le clamp
Blueberry Instant BB_INSTANT_RISK_CAP=1.5, verifie ligne 534-538 : ne
s'applique QUE si gname=="Blueberry" ET format in BB_INSTANT_FORMAT_KEYS
(Instant Elite/Lite) -- Prime et toutes les autres firms restent au risque
de grille choisi, non plafonnees).

Grille testee (meme valeur eval+funded a chaque point, GFT_EVAL_RISK laisse
fixe a 1,75 -- non demande dans la consigne) : 0.75/1.00/1.25/1.50/1.75/
1.90/2.25 (%). Le clamp Blueberry Instant a 1,5% s'applique automatiquement
et seulement aux comptes Instant Elite/Lite quelle que soit la valeur de
grille -- donc au-dela de 1,5% le "risque configure" et le "risque reellement
applique aux comptes Instant" divergent, ce qui permet de chiffrer le
manque a gagner Blueberry Instant vs un format Prime non plafonne.

Usage : python chantier_taskC2_risque_sweep_AB_2026-08-23.py <n_sims> <A|B|AB>
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
BB_THRESHOLD_BY_CEILING = {1000.0: 5000.0, 3000.0: 0.0}
RISK_GRID = [0.75, 1.00, 1.25, 1.50, 1.75, 1.90, 2.25]
GFT_EVAL_RISK_FIXED = 1.75

# Reference "5 leviers adoptes" (FULL) -- identique a FULL_KW de chantier_
# 5leviers_revalidation_fixed_2026-08-23.py / chantier_taskC_5leviers_B_
# 2026-08-23.py, avec S2.35 (size_func tail x1.6, routing rr_tp2) inclus
# puisque desormais formellement adopte.
FULL_KW = dict(b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True,
               ftmo_discount=True, gft_goat_guard=True, payout_cycle=True,
               use_any_rr=True, size_func=rr2.make_size_func_tail(1.6), routing_field="rr_tp2")


def load_pop_a():
    pop, market_data, excluded_map = rr2.load_common()
    unconstrained = {"tick_size": 1.0, "tick_value": 1.0, "volume_min": 0.0001,
                      "volume_max": 1e9, "volume_step": 0.0001, "margin_per_lot": 0.0001, "price": 1.0}
    for label in ["DAX40 FULL0926", "DAX40 PERF INDEX",
                  "NASDAQ100 - MINI NASDAQ100 FULL0926", "NASDAQ100 INDEX",
                  "S&P500 - MINI S&P500 FULL0926"]:
        market_data[label] = dict(unconstrained)
    return pop, market_data, excluded_map


def load_pop_b():
    pop, market_data, excluded_map, _, _, _ = pd22.load_scenario_pgp()
    return pop, market_data, excluded_map


def run_point(pop, market_data, excluded_map, ceiling, n_sims, label, eval_risk, fleet_risk=None):
    if fleet_risk is None:
        fleet_risk = eval_risk
    bb_th = BB_THRESHOLD_BY_CEILING[ceiling]
    common_kwargs = dict(emergency=rr2.ei.DEFAULT_EMERGENCY, eval_risk=eval_risk, fleet_risk=fleet_risk,
                          gft_eval_risk=GFT_EVAL_RISK_FIXED, reserve_share=rr2.ei.FINAL_RESERVE_SHARE,
                          extra_threshold_mult=rr2.ei.EXTRA_THRESHOLD_MULT, n_sims=n_sims, seed=9999,
                          b_entry_frac=FULL_KW["b_entry_frac"], b_reduction=FULL_KW["b_reduction"],
                          pre_unlock_only=FULL_KW["pre_unlock_only"], ftmo_discount=FULL_KW["ftmo_discount"],
                          gft_goat_guard=FULL_KW["gft_goat_guard"], payout_cycle=FULL_KW["payout_cycle"])
    seq = rr2.ei.seq_grouped_multi(1000, 15000, 25000, 25000)
    config = rr2.ei.CONFIG_REF
    t0 = time.time()
    df = rr2.run_propagated(pop, market_data, excluded_map, ceiling, seq, config,
                             bb_threshold=bb_th, use_any_rr=FULL_KW["use_any_rr"],
                             size_func=FULL_KW["size_func"], routing_field=FULL_KW["routing_field"],
                             **common_kwargs)
    row = rr2.summarize(df, label, ceiling, bb_th, FULL_KW["use_any_rr"])
    row["eval_risk_pct"] = eval_risk
    row["fleet_risk_pct"] = fleet_risk
    dt = time.time() - t0
    print(f"[{label} eval={eval_risk:.2f}%/funded={fleet_risk:.2f}% c={ceiling:.0f}$] profit_moy={row['profit_moyen']:+,.0f}$ "
          f"profit_median={row.get('profit_median', float('nan')):+,.0f}$ "
          f"solde_neg={row['solde_negatif_annee4']:.2f}% annee1<0={row['annee1_neg']:.2f}% "
          f"n={n_sims} ({dt:.0f}s)", flush=True)
    return row


def sweep(pop_label, pop, market_data, excluded_map, n_sims, rows, risk_grid=RISK_GRID):
    print(f"{'='*90}\nSWEEP RISQUE {pop_label} (n_sims={n_sims}, grille={risk_grid}, ceilings={CEILINGS})\n{'='*90}", flush=True)
    for ceiling in CEILINGS:
        for risk_val in risk_grid:
            row = run_point(pop, market_data, excluded_map, ceiling, n_sims,
                             f"{pop_label}_risk{risk_val:.2f}", risk_val)
            row["population"] = pop_label
            rows.append(row)


def ref_point(pop_label, pop, market_data, excluded_map, n_sims, rows):
    """Reference officielle actuelle (registre §2.23) : eval=1.25%/funded=1.90%,
    IDENTIQUE pour A et B jusqu'ici. Aucun point de la grille uniforme ne
    reproduit cette asymetrie -- run dedie pour servir de vraie baseline de
    comparaison ("gain % vs reference actuelle")."""
    print(f"{'='*90}\nREFERENCE ASYMETRIQUE {pop_label} eval=1.25%/funded=1.90% (n_sims={n_sims})\n{'='*90}", flush=True)
    for ceiling in CEILINGS:
        row = run_point(pop, market_data, excluded_map, ceiling, n_sims,
                         f"{pop_label}_REF_1.25_1.90", 1.25, 1.90)
        row["population"] = pop_label
        rows.append(row)


def main():
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    which = sys.argv[2] if len(sys.argv) > 2 else "AB"
    mode = sys.argv[3] if len(sys.argv) > 3 else "grid"  # grid | ref | escalate
    rows = []

    pops = []
    if "A" in which:
        pop_a, md_a, ex_a = load_pop_a()
        print(f"[verif] population A_seule : {len(pop_a)} trades", flush=True)
        pops.append(("A_seule", pop_a, md_a, ex_a, [1.75, 1.90, 2.25]))
    if "B" in which:
        pop_b, md_b, ex_b = load_pop_b()
        print(f"[verif] population B_tradable_pgp : {len(pop_b)} trades", flush=True)
        pops.append(("B_tradable_pgp", pop_b, md_b, ex_b, [1.50, 1.75, 1.90]))

    for label, pop, md, ex, escalate_grid in pops:
        if mode == "ref":
            ref_point(label, pop, md, ex, n_sims, rows)
        elif mode == "escalate":
            sweep(label, pop, md, ex, n_sims, rows, risk_grid=escalate_grid)
            ref_point(label, pop, md, ex, n_sims, rows)
        else:
            sweep(label, pop, md, ex, n_sims, rows)

    pd.DataFrame(rows).to_csv(f"chantier_taskC2_risque_sweep_AB_2026-08-23_{which}_{mode}_n{n_sims}.csv", index=False)


if __name__ == "__main__":
    main()
