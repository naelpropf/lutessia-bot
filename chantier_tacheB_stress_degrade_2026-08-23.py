"""chantier_tacheB_stress_degrade_2026-08-23.py

TACHE B (session du 23/08) : stress-test de l'architecture de flotte
B_tradable_pgp (population qui a servi a refermer §6.5, n=1248, r_trailing
corrige) a winrate/EV degrades, sur le moteur cascade officiel COMPLET
(bsl.run_propagated_custom_alpha / s18.run_one, point_d_bloc1_bloc2_2026-
08-22.py::load_scenario_pgp -- meme population/prior/market_data que la
confirmation n=600 de §6.5), 4 plafonds (960/1000/3000/5000$), n=600+.

3 scenarios degrades + reference (edge mesuree telle quelle) :
  1. winrate fixe au P10 du block-bootstrap (calcule ici, meme methode que
     chantier_tacheA_significativite_ev_2026-08-23.py::block_bootstrap_ci,
     appliquee a l'indicateur binaire win/loss au lieu du r_trailing) --
     remplace le tirage Beta(625,625) habituel par une valeur FIXE
     pessimiste pour CHAQUE simulation (stress, pas un scenario probable).
  2. EV reduite de -30%/-50% en ne touchant QUE la magnitude des trades
     GAGNANTS (les pertes restent a -1R, deja le plancher structurel du
     risque defini) -- isole l'effet magnitude de l'effet frequence,
     applique APRES le tirage winrate normal (Beta(625,625) inchange).
  3. rejeu de bloc2 SEUL (2022-08-20->2023-12-17, winrate 43,12%/EV+1,35R,
     le bloc le plus faible) comme population source du block-bootstrap
     pour TOUTE la duree de la trajectoire (duree cible forcee a la meme
     duree que le baseline complet, sinon le block-bootstrap ne
     tournerait que ~1,3 an au lieu de ~4 ans -- pas comparable).

Reutilise TEL QUEL real_cash_risk_year1_block_bootstrap.build_blocks +
reference_metrics_final.build_full_block_bootstrap_sequence (block
bootstrap calendaire 2 mois, PAS de permutation) -- deja le moteur standard
de tout run_propagated_custom_alpha de ce projet.
"""
import importlib.util
import random
import sys
import time

import numpy as np
import pandas as pd

_spec = importlib.util.spec_from_file_location("pdb", "point_d_bloc1_bloc2_2026-08-22.py")
pdb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pdb)
bsl = pdb.bsl
s18 = bsl.s18
abm = bsl.abm
ei = bsl.ei

from real_cash_risk_year1_block_bootstrap import build_blocks
from reference_metrics_final import build_full_block_bootstrap_sequence

DAY_SECONDS = 86400
BLOCK_SECONDS = 2 * 30 * DAY_SECONDS
BLOC2_START, BLOC2_END = pd.Timestamp("2022-08-20"), pd.Timestamp("2023-12-17")
CEILINGS = [960.0, 1000.0, 3000.0, 5000.0]


def block_bootstrap_ci_stat(dates, values, stat_fn, n_boot=5000, seed=20260823, alpha=0.10):
    order = np.argsort(dates.values)
    d = dates.values[order]
    v = np.asarray(values)[order]
    t0 = d[0]
    block_idx = ((d - t0) / np.timedelta64(1, "D") // 60).astype(int)
    blocks = [v[block_idx == b] for b in np.unique(block_idx)]
    blocks = [b for b in blocks if len(b) > 0]
    n_blocks = len(blocks)
    rng = np.random.default_rng(seed)
    boot_stats = np.empty(n_boot)
    for i in range(n_boot):
        chosen = rng.integers(0, n_blocks, size=n_blocks)
        sample = np.concatenate([blocks[c] for c in chosen])
        boot_stats[i] = stat_fn(sample)
    return np.percentile(boot_stats, 100 * alpha)  # P10 par defaut (alpha=0.10)


def compute_p10_winrate(pop):
    is_win = (pop["statut_final"] == "OBJECTIF ATTEINT").astype(float)
    p10 = block_bootstrap_ci_stat(pop["date_creation"], is_win.to_numpy(), lambda x: x.mean())
    print(f"[verif] winrate observe = {is_win.mean()*100:.2f}%, P10 block-bootstrap = {p10*100:.2f}%", flush=True)
    return p10


def run_propagated_degraded(pop, market_data, excluded_map, ceiling, seq_grouped, format_by_firm, emergency,
                             eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult, n_sims, seed,
                             alpha_post, beta_post, winrate_override=None, ev_scale=None,
                             target_duration_override=None, **kw):
    rng_wr = random.Random(seed)
    rng_boot = random.Random(seed + 1)
    rows = []
    for _ in range(n_sims):
        wr_draw = winrate_override if winrate_override is not None else rng_wr.betavariate(alpha_post, beta_post)
        trades, slot_arrivals = s18.build_flexible_population_with_rr(pop, wr_draw, 1.0, False, random.Random(rng_boot.random()))
        if ev_scale is not None:
            for t in trades:
                if t["outcome_r"] > 0:
                    t["outcome_r"] = t["outcome_r"] * ev_scale
        blocks = build_blocks(trades, slot_arrivals, BLOCK_SECONDS)
        target_duration = target_duration_override if target_duration_override is not None else slot_arrivals[-1]
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, BLOCK_SECONDS, rng_boot, target_duration)
        order = list(range(len(raw_trades)))
        res = s18.run_one(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, seq_grouped, format_by_firm,
                           emergency, eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult, **kw)
        rows.append(res)
    return pd.DataFrame(rows)


def run_scenario(pop, market_data, excluded_map, alpha_post, beta_post, ceiling, n_sims, seed, label,
                  winrate_override=None, ev_scale=None, target_duration_override=None):
    common_kwargs = dict(emergency=ei.DEFAULT_EMERGENCY, eval_risk=abm.EVAL_RISK, fleet_risk=abm.FLEET_RISK,
                          gft_eval_risk=abm.GFT_EVAL_RISK, reserve_share=ei.FINAL_RESERVE_SHARE,
                          extra_threshold_mult=ei.EXTRA_THRESHOLD_MULT, n_sims=n_sims, seed=seed,
                          b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True,
                          ftmo_discount=True, gft_goat_guard=True, payout_cycle=True)
    bb_th = abm.BB_THRESHOLD_BY_CEILING[ceiling]
    t0 = time.time()
    df = run_propagated_degraded(pop, market_data, excluded_map, ceiling,
                                  ei.seq_grouped_multi(1000, 15000, 25000, 25000), ei.CONFIG_REF,
                                  bb_threshold=bb_th, use_any_rr=True, apply_instant_risk_cap=True,
                                  alpha_post=alpha_post, beta_post=beta_post,
                                  winrate_override=winrate_override, ev_scale=ev_scale,
                                  target_duration_override=target_duration_override,
                                  **common_kwargs)
    row = s18.summarize(df, label, ceiling, bb_th, True)
    dt = time.time() - t0
    print(f"[{label} c={ceiling:.0f}$] profit_moy={row['profit_moyen']:+,.0f}$ profit_med={row['profit_median']:+,.0f}$ "
          f"solde_neg_an4={row['solde_negatif_annee4']:.2f}% annee1<0={row['annee1_neg']:.2f}% n={n_sims} ({dt:.0f}s)", flush=True)
    return row, df


def main():
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 31415

    pop, market_data, excluded_map, alpha_post, beta_post, label = pdb.load_scenario_pgp()
    print(f"Population : {label}, n={len(pop)}, prior Beta({alpha_post},{beta_post})", flush=True)
    full_duration = (pop["date_creation"].max() - pop["date_creation"].min()).total_seconds()
    print(f"Duree pleine population (reference pour toutes les trajectoires) : {full_duration/DAY_SECONDS:.0f} jours", flush=True)

    p10_winrate = compute_p10_winrate(pop)

    bloc2_pop = pop[(pop["date_creation"] >= BLOC2_START) & (pop["date_creation"] < BLOC2_END)].reset_index(drop=True)
    wr_bloc2 = (bloc2_pop["statut_final"] == "OBJECTIF ATTEINT").mean()
    ev_bloc2 = bloc2_pop["r_trailing"].mean()
    print(f"[verif] bloc2 seul : n={len(bloc2_pop)}, winrate={wr_bloc2*100:.2f}%, EV={ev_bloc2:+.4f}R", flush=True)

    SCENARIOS = [
        ("REF", dict()),
        ("winrate_P10", dict(winrate_override=p10_winrate)),
        ("EV_-30pct", dict(ev_scale=0.70)),
        ("EV_-50pct", dict(ev_scale=0.50)),
        ("bloc2_replay", dict(pop_override=bloc2_pop, target_duration_override=full_duration)),
    ]

    all_rows = []
    for sname, sconf in SCENARIOS:
        print(f"\n{'='*95}\nSCENARIO : {sname}\n{'='*95}", flush=True)
        use_pop = sconf.get("pop_override", pop)
        for ceiling in CEILINGS:
            row, df = run_scenario(use_pop, market_data, excluded_map, alpha_post, beta_post, ceiling, n_sims, seed,
                                    f"{sname} c={ceiling:.0f}",
                                    winrate_override=sconf.get("winrate_override"),
                                    ev_scale=sconf.get("ev_scale"),
                                    target_duration_override=sconf.get("target_duration_override"))
            row["scenario"] = sname
            all_rows.append(row)
            pd.DataFrame(all_rows).to_csv("chantier_tacheB_stress_degrade_2026-08-23.csv", index=False)

    print(f"\n{'='*95}\nSYNTHESE -- solde_negatif%/annee1<0%/profit par scenario x plafond\n{'='*95}")
    dfres = pd.DataFrame(all_rows)
    ref = dfres[dfres["scenario"] == "REF"].set_index("ceiling")
    for sname, _ in SCENARIOS:
        sub = dfres[dfres["scenario"] == sname].set_index("ceiling")
        for ceiling in CEILINGS:
            r = sub.loc[ceiling]
            rr = ref.loc[ceiling]
            print(f"  {sname:14s} c={ceiling:.0f}$ : profit_moy={r['profit_moyen']:+,.0f}$ "
                  f"(vs REF {rr['profit_moyen']:+,.0f}$, {(r['profit_moyen']/rr['profit_moyen']-1)*100:+.1f}%) "
                  f"solde_neg={r['solde_negatif_annee4']:.2f}% (REF {rr['solde_negatif_annee4']:.2f}%) "
                  f"annee1<0={r['annee1_neg']:.2f}% (REF {rr['annee1_neg']:.2f}%)")


if __name__ == "__main__":
    main()
