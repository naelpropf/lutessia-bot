"""chantier_tacheB_sequence_2026-08-23.py

TACHE B, VOLET 2 (suite directe de chantier_tacheB_stress_degrade_2026-08-23.py) :
le stress-test winrate/EV degrade a montre que le risque de casse ne bouge
presque pas (cf. memoire projet_tacheB_stress_degrade_2026-08-23.md), parce que
ce risque est pilote par une SEQUENCE de pertes consecutives touchant le
drawdown journalier, pas par la magnitude des gains. Ce chantier teste
DIRECTEMENT une degradation de la sequence elle-meme, focalisee sur l'annee 1
(tresorerie la plus fine) :

  1. pire_decile_Nmo : force les N premiers mois (N=6 ou 12) de chaque
     simulation a piocher EXCLUSIVEMENT dans le decile le plus faible (10%)
     des blocs de 2 mois HISTORIQUES REELS (classes par EV realisee =
     outcome_r moyen, PAS le winrate/EV du tirage winrate-override par-sim,
     qui varie a chaque run et ne represente pas "les pires periodes reelles").
     Apres la duree forcee, retour au tirage bootstrap normal (pool complet).
  2. winrate_P5 / winrate_P1 : meme mecanisme que winrate_P10 (deja teste),
     mais aux percentiles P5/P1 du block-bootstrap CI (memes fonctions que
     chantier_tacheA_significativite_ev_2026-08-23.py::block_bootstrap_ci,
     alpha=0.05/0.01 au lieu de 0.10).
  3. clustering_Nmo : blocs de bootstrap plus longs (N=4 ou 6 mois au lieu de
     2) -- teste si une plus forte autocorrelation temporelle des mauvaises
     periodes fait bouger le risque annee 1, sans toucher winrate/EV globale.

Alignement calendaire des blocs (justifie l'identification "worst_block_indices"
UNE SEULE FOIS, reutilisee pour toutes les simulations pire_decile) : le decoupage
en blocs de s18.build_flexible_population_with_rr(pop, wr, ...) est base sur
slot_arrivals = offset temporel depuis pop trie par date_creation -- CE
DECOUPAGE NE DEPEND PAS du tirage winrate (seul outcome_r est flippe par
build_flexible_population, jamais slot_arrivals/l'ordre). Donc l'indice de
bloc i correspond TOUJOURS a la meme fenetre calendaire reelle, quel que soit
le tirage winrate-per-sim -- verifie par lecture directe de
robustness_5ers_risk_challenge.py::build_flexible_population (slot_arrivals
calcule une seule fois depuis sub["date_creation"], hors du bloc if
target_winrate is not None qui ne touche qu'outcome_r).

Meme moteur cascade complet (s18.run_one via point_d_bloc1_bloc2_2026-08-
22.py::load_scenario_pgp), memes 4 plafonds, meme risque REF (1,25%/1,90%,
pas touche par le sweep en cours ailleurs).
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
CEILINGS = [960.0, 1000.0, 3000.0, 5000.0]
REF_CSV = "chantier_tacheB_stress_degrade_2026-08-23.csv"  # REF deja calcule, pas relance
OUT_CSV = "chantier_tacheB_sequence_2026-08-23.csv"


def load_resume_state(path, n_sims):
    """Reprise apres kill/relance : ne garde que les configs deja terminees
    AU MEME n_sims demande (evite de confondre un run n=6 de validation avec
    un run n=600 de verdict) -- les autres sont recalculees."""
    try:
        df = pd.read_csv(path)
    except FileNotFoundError:
        return set(), []
    done_rows = df[df["n"] == n_sims]
    done_keys = set(zip(done_rows["scenario"], done_rows["ceiling"]))
    return done_keys, done_rows.to_dict("records")


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
    return np.percentile(boot_stats, 100 * alpha)


def compute_winrate_percentile(pop, alpha):
    is_win = (pop["statut_final"] == "OBJECTIF ATTEINT").astype(float)
    p = block_bootstrap_ci_stat(pop["date_creation"], is_win.to_numpy(), lambda x: x.mean(), alpha=alpha)
    print(f"[verif] winrate observe = {is_win.mean()*100:.2f}%, P{int(alpha*100)} block-bootstrap = {p*100:.2f}%", flush=True)
    return p


def compute_worst_decile_blocks(pop, block_seconds):
    """Blocs REELS (outcome_r non flippe, target_winrate=None) classes par EV
    (outcome_r moyen) croissant -- worst decile = 10% des blocs NON-VIDES les
    plus faibles. Retourne (blocks_reference_partition_length_check, worst_indices,
    details)."""
    true_trades, true_slots = s18.build_flexible_population_with_rr(pop, None, 1.0, False, random.Random(0))
    true_blocks = build_blocks(true_trades, true_slots, block_seconds)
    stats = []
    for i, blk in enumerate(true_blocks):
        if len(blk) == 0:
            continue
        outcomes = [t["outcome_r"] for t, off in blk]
        ev = sum(outcomes) / len(outcomes)
        wr = sum(1 for o in outcomes if o > 0) / len(outcomes)
        stats.append((i, ev, wr, len(outcomes)))
    stats.sort(key=lambda x: x[1])
    n_worst = max(1, round(0.10 * len(stats)))
    worst = stats[:n_worst]
    print(f"[verif] {len(true_blocks)} blocs au total ({len(stats)} non-vides), "
          f"decile le plus faible = {n_worst} blocs :", flush=True)
    for i, ev, wr, n in worst:
        print(f"    bloc #{i} : n={n} trades, winrate={wr*100:.1f}%, EV={ev:+.3f}R", flush=True)
    return len(true_blocks), [i for i, ev, wr, n in worst]


def build_forced_worst_decile_sequence(blocks, block_seconds, rng, worst_indices, forced_duration, target_duration):
    synthetic_trades, synthetic_slots = [], []
    cursor = 0.0
    while cursor < target_duration:
        if cursor < forced_duration:
            block = blocks[worst_indices[rng.randrange(len(worst_indices))]]
        else:
            block = blocks[rng.randrange(len(blocks))]
        for trade, offset in block:
            synthetic_trades.append(trade)
            synthetic_slots.append(cursor + offset)
        cursor += block_seconds
    return synthetic_trades, synthetic_slots


def run_propagated_sequence(pop, market_data, excluded_map, ceiling, seq_grouped, format_by_firm, emergency,
                             eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult, n_sims, seed,
                             alpha_post, beta_post, block_seconds=BLOCK_SECONDS,
                             winrate_override=None, forced_worst_indices=None, forced_duration=None, **kw):
    rng_wr = random.Random(seed)
    rng_boot = random.Random(seed + 1)
    rows = []
    for _ in range(n_sims):
        wr_draw = winrate_override if winrate_override is not None else rng_wr.betavariate(alpha_post, beta_post)
        trades, slot_arrivals = s18.build_flexible_population_with_rr(pop, wr_draw, 1.0, False, random.Random(rng_boot.random()))
        blocks = build_blocks(trades, slot_arrivals, block_seconds)
        target_duration = slot_arrivals[-1]
        if forced_worst_indices is not None:
            raw_trades, raw_slots = build_forced_worst_decile_sequence(
                blocks, block_seconds, rng_boot, forced_worst_indices, forced_duration, target_duration)
        else:
            raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot, target_duration)
        order = list(range(len(raw_trades)))
        res = s18.run_one(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, seq_grouped, format_by_firm,
                           emergency, eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult, **kw)
        rows.append(res)
    return pd.DataFrame(rows)


def run_scenario(pop, market_data, excluded_map, alpha_post, beta_post, ceiling, n_sims, seed, label,
                  block_seconds=BLOCK_SECONDS, winrate_override=None,
                  forced_worst_indices=None, forced_duration=None):
    common_kwargs = dict(emergency=ei.DEFAULT_EMERGENCY, eval_risk=abm.EVAL_RISK, fleet_risk=abm.FLEET_RISK,
                          gft_eval_risk=abm.GFT_EVAL_RISK, reserve_share=ei.FINAL_RESERVE_SHARE,
                          extra_threshold_mult=ei.EXTRA_THRESHOLD_MULT, n_sims=n_sims, seed=seed,
                          b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True,
                          ftmo_discount=True, gft_goat_guard=True, payout_cycle=True)
    bb_th = abm.BB_THRESHOLD_BY_CEILING[ceiling]
    t0 = time.time()
    df = run_propagated_sequence(pop, market_data, excluded_map, ceiling,
                                  ei.seq_grouped_multi(1000, 15000, 25000, 25000), ei.CONFIG_REF,
                                  bb_threshold=bb_th, use_any_rr=True, apply_instant_risk_cap=True,
                                  alpha_post=alpha_post, beta_post=beta_post,
                                  block_seconds=block_seconds, winrate_override=winrate_override,
                                  forced_worst_indices=forced_worst_indices, forced_duration=forced_duration,
                                  **common_kwargs)
    row = s18.summarize(df, label, ceiling, bb_th, True)
    row["profit_median_year1"] = df["year1_net_split"].median()
    dt = time.time() - t0
    print(f"[{label} c={ceiling:.0f}$] profit_moy={row['profit_moyen']:+,.0f}$ profit_med_an1={row['profit_median_year1']:+,.0f}$ "
          f"solde_neg_an4={row['solde_negatif_annee4']:.2f}% annee1<0={row['annee1_neg']:.2f}% n={n_sims} ({dt:.0f}s)", flush=True)
    return row


def main():
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 271828
    ceilings = [float(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else CEILINGS

    pop, market_data, excluded_map, alpha_post, beta_post, label = pdb.load_scenario_pgp()
    print(f"Population : {label}, n={len(pop)}, prior Beta({alpha_post},{beta_post})", flush=True)

    n_blocks_total, worst_idx = compute_worst_decile_blocks(pop, BLOCK_SECONDS)
    p5 = compute_winrate_percentile(pop, 0.05)
    p1 = compute_winrate_percentile(pop, 0.01)

    SCENARIOS = [
        ("pire_decile_6mo", dict(forced_worst_indices=worst_idx, forced_duration=6 * 30 * DAY_SECONDS)),
        ("pire_decile_8mo", dict(forced_worst_indices=worst_idx, forced_duration=8 * 30 * DAY_SECONDS)),
        ("pire_decile_9mo", dict(forced_worst_indices=worst_idx, forced_duration=9 * 30 * DAY_SECONDS)),
        ("pire_decile_10mo", dict(forced_worst_indices=worst_idx, forced_duration=10 * 30 * DAY_SECONDS)),
        ("pire_decile_12mo", dict(forced_worst_indices=worst_idx, forced_duration=12 * 30 * DAY_SECONDS)),
        ("winrate_P5", dict(winrate_override=p5)),
        ("winrate_P1", dict(winrate_override=p1)),
        ("clustering_4mo", dict(block_seconds=4 * 30 * DAY_SECONDS)),
        ("clustering_6mo", dict(block_seconds=6 * 30 * DAY_SECONDS)),
    ]

    done_keys, all_rows = load_resume_state(OUT_CSV, n_sims)
    if done_keys:
        print(f"[resume] {len(done_keys)} config(s) deja terminee(s) a n={n_sims}, sautee(s) : "
              f"{sorted(done_keys)}", flush=True)

    for sname, sconf in SCENARIOS:
        print(f"\n{'='*95}\nSCENARIO : {sname}\n{'='*95}", flush=True)
        for ceiling in ceilings:
            if (sname, ceiling) in done_keys:
                print(f"  [resume] {sname} c={ceiling:.0f}$ deja fait, skip.", flush=True)
                continue
            row = run_scenario(pop, market_data, excluded_map, alpha_post, beta_post, ceiling, n_sims, seed,
                                f"{sname} c={ceiling:.0f}",
                                block_seconds=sconf.get("block_seconds", BLOCK_SECONDS),
                                winrate_override=sconf.get("winrate_override"),
                                forced_worst_indices=sconf.get("forced_worst_indices"),
                                forced_duration=sconf.get("forced_duration"))
            row["scenario"] = sname
            all_rows.append(row)
            pd.DataFrame(all_rows).to_csv(OUT_CSV, index=False)

    print(f"\n{'='*95}\nSYNTHESE -- annee1<0%/solde_neg_an4%/profit_med_an1 par scenario x plafond\n{'='*95}")
    dfres = pd.DataFrame(all_rows)
    ref = pd.read_csv(REF_CSV)
    ref = ref[ref["scenario"] == "REF"].set_index("ceiling")
    for sname, _ in SCENARIOS:
        sub = dfres[dfres["scenario"] == sname].set_index("ceiling")
        for ceiling in ceilings:
            if ceiling not in sub.index:
                continue
            r = sub.loc[ceiling]
            rr = ref.loc[ceiling]
            print(f"  {sname:16s} c={ceiling:.0f}$ : annee1<0={r['annee1_neg']:.2f}% (REF {rr['annee1_neg']:.2f}%) "
                  f"solde_neg_an4={r['solde_negatif_annee4']:.2f}% (REF {rr['solde_negatif_annee4']:.2f}%) "
                  f"profit_med_an1={r['profit_median_year1']:+,.0f}$")


if __name__ == "__main__":
    main()
