"""chantier_coldstart_svb_isrhamas_2026-08-23.py

QUESTION 1 (session du 23/08) : un compte NEUF (capital 5000$, Blueberry
Instant Elite, sizing B_tradable_pgp sequentiel courant -- config identique
a point_d_bloc1_bloc2_2026-08-22.py::load_scenario_pgp) qui demarre ses
15-20 premiers trades DIRECTEMENT dans une fenetre choc (SVB ou Israel-
Hamas) plutot qu'a un point aleatoire de la trajectoire -- quel est l'impact
sur le risque de ruine annee1 ?

Methode : reutilise TEL QUEL le moteur officiel (run_propagated_custom_alpha,
block bootstrap 2 mois, s18.run_one) -- seul changement : le TOUT PREMIER
segment de la trajectoire synthetique de chaque simulation MC est force a
etre exactement les trades reels tombant dans la fenetre choc (au lieu d'un
bloc de 2 mois tire au hasard comme pour tous les segments suivants et comme
pour TOUS les segments du run baseline). Le reste de la trajectoire (a partir
du 2e segment) suit le bootstrap par blocs standard, identique au baseline --
seul le point de depart change, pas le mecanisme.

Chaque iteration MC redessine deja un tirage winrate (wr_draw ~ Beta(625,625))
qui reassigne aleatoirement une partie des labels gagnant/perdant sur TOUTE la
population (mecanisme standard du moteur, pas specifique a ce chantier) -- les
trades de la fenetre choc gardent donc leur ticker/date/taille de risque reels,
mais pas necessairement leur issue win/loss historique exacte a chaque tirage.
C'est deja comme ca que fonctionne tout MC de ce projet ; pas une deviation.
"""
import importlib.util
import random
import sys
import time

import pandas as pd

_spec = importlib.util.spec_from_file_location("pdb", "point_d_bloc1_bloc2_2026-08-22.py")
pdb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pdb)
bsl = pdb.bsl
s18 = pdb.s18
abm = pdb.abm
ei = pdb.ei

from real_cash_risk_year1_block_bootstrap import build_blocks
from reference_metrics_final import build_full_block_bootstrap_sequence

DAY_SECONDS = 86400
BLOCK_SECONDS = 2 * 30 * DAY_SECONDS

WINDOWS = {
    "SVB": (pd.Timestamp("2023-03-08"), pd.Timestamp("2023-03-24")),
    "israel_hamas": (pd.Timestamp("2023-10-07"), pd.Timestamp("2023-11-15")),
}


def run_propagated_coldstart(pop, market_data, excluded_map, ceiling, seq_grouped, format_by_firm, emergency,
                              eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult, n_sims, seed,
                              alpha_post, beta_post, forced_window=None, **kw):
    rng_wr = random.Random(seed)
    rng_boot = random.Random(seed + 1)
    sub_sorted = pop.sort_values("date_creation").reset_index(drop=True)

    forced_mask = None
    if forced_window is not None:
        start_ts, end_ts = forced_window
        forced_mask = (sub_sorted["date_creation"] >= start_ts) & (sub_sorted["date_creation"] < end_ts)
        n_forced = int(forced_mask.sum())
        assert n_forced > 0, f"fenetre forcee vide : {forced_window}"

    rows = []
    for _ in range(n_sims):
        wr_draw = rng_wr.betavariate(alpha_post, beta_post)
        trades, slot_arrivals = s18.build_flexible_population_with_rr(pop, wr_draw, 1.0, False, random.Random(rng_boot.random()))
        blocks = build_blocks(trades, slot_arrivals, BLOCK_SECONDS)
        target_duration = slot_arrivals[-1]

        if forced_window is None:
            raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, BLOCK_SECONDS, rng_boot, target_duration)
        else:
            idxs = [i for i, keep in enumerate(forced_mask.to_numpy()) if keep]
            base_slot = min(slot_arrivals[i] for i in idxs)
            raw_trades, raw_slots = [], []
            for i in idxs:
                raw_trades.append(trades[i])
                raw_slots.append(slot_arrivals[i] - base_slot)
            cursor = BLOCK_SECONDS
            while cursor < target_duration:
                block = blocks[rng_boot.randrange(len(blocks))]
                for trade, offset in block:
                    raw_trades.append(trade)
                    raw_slots.append(cursor + offset)
                cursor += BLOCK_SECONDS

        order = list(range(len(raw_trades)))
        res = s18.run_one(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, seq_grouped, format_by_firm,
                           emergency, eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult, **kw)
        rows.append(res)
    return pd.DataFrame(rows)


def run_config(pop, market_data, excluded_map, alpha_post, beta_post, ceiling, n_sims, seed, forced_window, label):
    common_kwargs = dict(emergency=ei.DEFAULT_EMERGENCY, eval_risk=abm.EVAL_RISK, fleet_risk=abm.FLEET_RISK,
                          gft_eval_risk=abm.GFT_EVAL_RISK, reserve_share=ei.FINAL_RESERVE_SHARE,
                          extra_threshold_mult=ei.EXTRA_THRESHOLD_MULT, n_sims=n_sims, seed=seed,
                          b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True,
                          ftmo_discount=True, gft_goat_guard=True, payout_cycle=True)
    bb_th = abm.BB_THRESHOLD_BY_CEILING[ceiling]
    t0 = time.time()
    df = run_propagated_coldstart(pop, market_data, excluded_map, ceiling,
                                   ei.seq_grouped_multi(1000, 15000, 25000, 25000), ei.CONFIG_REF,
                                   bb_threshold=bb_th, use_any_rr=True, apply_instant_risk_cap=True,
                                   alpha_post=alpha_post, beta_post=beta_post, forced_window=forced_window,
                                   **common_kwargs)
    row = s18.summarize(df, label, ceiling, bb_th, True)
    dt = time.time() - t0
    print(f"[{label}] profit_moy={row['profit_moyen']:+,.0f}$ solde_neg_an4={row['solde_negatif_annee4']:.2f}% "
          f"annee1<0={row['annee1_neg']:.2f}% hit_ceiling={row['hit_ceiling_pct']:.2f}% n_sims={n_sims} ({dt:.0f}s)", flush=True)
    return row, df


def main():
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    ceiling = float(sys.argv[2]) if len(sys.argv) > 2 else 5000.0
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 24680

    pop, market_data, excluded_map, alpha_post, beta_post, label = pdb.load_scenario_pgp()
    print(f"Population : {label}, n={len(pop)}, prior Beta({alpha_post},{beta_post}), ceiling={ceiling:.0f}$, n_sims={n_sims}")
    for wname, (s, e) in WINDOWS.items():
        n_w = int(((pop["date_creation"] >= s) & (pop["date_creation"] < e)).sum())
        print(f"  fenetre {wname} [{s.date()}->{e.date()}] : {n_w} trades reels dans B_tradable_pgp")

    print("\n" + "=" * 90)
    print("BASELINE (point de depart aleatoire, methode standard deja utilisee partout dans le projet)")
    print("=" * 90)
    row_base, df_base = run_config(pop, market_data, excluded_map, alpha_post, beta_post, ceiling, n_sims, seed,
                                    None, "baseline")

    results = {"baseline": (row_base, df_base)}
    for wname, window in WINDOWS.items():
        print("\n" + "=" * 90)
        print(f"COLD START force sur fenetre {wname}")
        print("=" * 90)
        row_w, df_w = run_config(pop, market_data, excluded_map, alpha_post, beta_post, ceiling, n_sims, seed,
                                  window, f"coldstart_{wname}")
        results[wname] = (row_w, df_w)

    print("\n" + "=" * 90)
    print("SYNTHESE -- annee1<0 (risque de ruine annee 1), meme seed/n_sims/ceiling pour comparabilite directe")
    print("=" * 90)
    base_a1 = row_base["annee1_neg"]
    print(f"  baseline (aleatoire)     : annee1<0 = {base_a1:.2f}%  (n_sims={n_sims})")
    import numpy as np
    from scipy import stats as sps
    for wname in WINDOWS:
        row_w = results[wname][0]
        delta = row_w["annee1_neg"] - base_a1
        p1, p2 = base_a1 / 100, row_w["annee1_neg"] / 100
        se = np.sqrt(p1 * (1 - p1) / n_sims + p2 * (1 - p2) / n_sims)
        z = (p2 - p1) / se if se > 0 else float("nan")
        print(f"  coldstart {wname:15s} : annee1<0 = {row_w['annee1_neg']:.2f}%  delta={delta:+.2f}pts  z(approx)={z:+.2f}")
        print(f"      profit_moy delta = {row_w['profit_moyen']-row_base['profit_moyen']:+,.0f}$  "
              f"solde_neg_an4 delta = {row_w['solde_negatif_annee4']-row_base['solde_negatif_annee4']:+.2f}pts")

    print("\n" + "=" * 90)
    print("METRIQUE CONTINUE (plus sensible que le binaire annee1<0 a ce n) : year1_net_split ($)")
    print("=" * 90)
    y1_base = df_base["year1_net_split"]
    print(f"  baseline    : mean={y1_base.mean():+,.0f}$ p5={y1_base.quantile(.05):+,.0f}$ "
          f"p10={y1_base.quantile(.10):+,.0f}$ p25={y1_base.quantile(.25):+,.0f}$ median={y1_base.median():+,.0f}$ "
          f"n(<0)={int((y1_base < 0).sum())}/{n_sims}")
    for wname in WINDOWS:
        y1_w = results[wname][1]["year1_net_split"]
        print(f"  {wname:12s}: mean={y1_w.mean():+,.0f}$ p5={y1_w.quantile(.05):+,.0f}$ "
              f"p10={y1_w.quantile(.10):+,.0f}$ p25={y1_w.quantile(.25):+,.0f}$ median={y1_w.median():+,.0f}$ "
              f"n(<0)={int((y1_w < 0).sum())}/{n_sims}")
        u, p_mw = sps.mannwhitneyu(y1_base, y1_w, alternative="two-sided")
        print(f"      Mann-Whitney U vs baseline : p={p_mw:.4f}")

    pd.DataFrame([results[k][0] for k in results]).to_csv("chantier_coldstart_svb_isrhamas_2026-08-23.csv", index=False)
    for k in results:
        results[k][1].to_csv(f"chantier_coldstart_svb_isrhamas_raw_{k}_2026-08-23.csv", index=False)


if __name__ == "__main__":
    main()
