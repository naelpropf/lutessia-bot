"""
Section 1 (08/12, prompt utilisateur) : decomposition directionnelle du
mecanisme de sauvetage croise pour config 4 (A/B, reserve commune) --
n=600, deux plafonds, meme seed que la confirmation deja publiee
(§2.53 registre_parametres_projet.md) pour que les runs "separee" et
"commune" soient VRAIMENT apparies (meme tirage de marche pour T1 ET T2).

Etape 1 : passe rapide (sans journal) sur n=600, capture T1_net/T2_net/
hit_ceiling pour separee ET commune, meme run_idx -- identifie les runs
"sauvetage" (separee casse, commune sauve).
Etape 2 : pour CES runs uniquement, rejoue avec journal complet pour
determiner QUEL trader a declenche le hit_ceiling_touche sous separee
(direction du sauvetage : T2 sauve T1 ou T1 sauve T2).
Etape 3 : decomposition du profit combine -- T1_net(commune) vs
T1_net(separee) [gain de T1 du pooling], T2_net(commune) [contribution
propre de T2], et comparaison de T1_net(commune) a la reference solo
(flotte simple T1 seul, deja etablie ~5,59M$/1000$ et ~5,66M$/3000$,
structure_pistes_2026-08-11.py baseline).

N'importe pas ce script directement (convention du projet).
"""
import importlib.util
import random
import sys
import time

import pandas as pd

spec = importlib.util.spec_from_file_location("dt", "dual_trader_2026-08-11.py")
dt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dt)

import robustness_5ers_risk_challenge as eng
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from point_liquidity_rules import DAY_SECONDS
import etape_e_fleet_integration as ei

SEED = 9999
BBV = "split"


def build_draws(pop, cpop, market_data, excluded_map, seq, config, n_sims, seed=SEED):
    """Reconstruit les n_sims tirages (main + contrarian) dans le meme ordre
    RNG que run_sweep/mode confirm -- garantit l'appariement exact separee/
    commune (meme trade pour T1 ET T2 aux 2 architectures)."""
    rng_wr = random.Random(seed)
    rng_boot = random.Random(seed + 1)
    rng_wr_c = random.Random(seed + 2)
    rng_boot_c = random.Random(seed + 3)
    draws = []
    for run_idx in range(n_sims):
        wr_draw = rng_wr.betavariate(ei.ALPHA_POST, ei.BETA_POST)
        trades, slot_arrivals = eng.build_flexible_population(pop, wr_draw, 1.0, False, random.Random(rng_boot.random()))
        block_seconds = 2 * 30 * DAY_SECONDS
        blocks = build_blocks(trades, slot_arrivals, block_seconds)
        target_duration = slot_arrivals[-1]
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot, target_duration)
        order = list(range(len(raw_trades)))

        wr_draw_c = rng_wr_c.betavariate(ei.ALPHA_POST, ei.BETA_POST)
        trades_c, slots_c = eng.build_flexible_population(cpop, wr_draw_c, 1.0, False, random.Random(rng_boot_c.random()))
        blocks_c = build_blocks(trades_c, slots_c, block_seconds)
        raw_trades_c, raw_slots_c = build_full_block_bootstrap_sequence(blocks_c, block_seconds, rng_boot_c, target_duration)

        draws.append((raw_trades, raw_slots, order, raw_trades_c, raw_slots_c))
    return draws


def main(n_sims, ceiling):
    pop, market_data, excluded_map, seq, config = dt._common_setup()
    cpop = dt._contrarian_population()
    draws = build_draws(pop, cpop, market_data, excluded_map, seq, config, n_sims)

    kw_common = dict(bb_variant=BBV, spec_variant="rr_band", ceiling_combined=ceiling)
    rows = []
    t0 = time.time()
    for run_idx, (raw_trades, raw_slots, order, raw_trades_c, raw_slots_c) in enumerate(draws):
        res_sep = dt.run_dual(raw_trades, raw_slots, market_data, excluded_map, order, seq, config,
                               ei.DEFAULT_EMERGENCY, dt.EVAL_RISK, dt.FLEET_RISK, dt.GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                               ei.EXTRA_THRESHOLD_MULT, reserve_pooled=False,
                               contrarian_trades=raw_trades_c, contrarian_slots=raw_slots_c, **kw_common)
        res_pool = dt.run_dual(raw_trades, raw_slots, market_data, excluded_map, order, seq, config,
                                ei.DEFAULT_EMERGENCY, dt.EVAL_RISK, dt.FLEET_RISK, dt.GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                                ei.EXTRA_THRESHOLD_MULT, reserve_pooled=True,
                                contrarian_trades=raw_trades_c, contrarian_slots=raw_slots_c, **kw_common)
        # T{1,2}_net brut (avant IS) -- CORRECTION (trouvee en verifiant contre
        # le total publie) : il faut soustraire is_paid_cum par trader pour un
        # T1/T2 net APRES IMPOT comparable au profit combine deja publie
        # (§2.53, qui est net d'impot). Sans ca, T1_net+T2_net gonfle le
        # profit reel d'environ le montant d'IS paye (~25-30% a ces niveaux
        # de profit) -- ecart trouve en recoupant avec §2.53, pas suppose.
        rows.append(dict(run_idx=run_idx,
                          sep_hc=res_sep["combined_hit_ceiling"], pool_hc=res_pool["combined_hit_ceiling"],
                          sep_T1=res_sep["T1_net"] - res_sep["T1_is_paid"],
                          sep_T2=res_sep["T2_net"] - res_sep["T2_is_paid"],
                          pool_T1=res_pool["T1_net"] - res_pool["T1_is_paid"],
                          pool_T2=res_pool["T2_net"] - res_pool["T2_is_paid"]))
        if (run_idx + 1) % 100 == 0:
            print(f"  ... {run_idx+1}/{n_sims} ({time.time()-t0:.0f}s)")

    df = pd.DataFrame(rows)
    df.to_csv(f"dual_trader_config4_decomposition_pass1_ceiling{int(ceiling)}_n{n_sims}.csv", index=False)

    rescue_T1 = df[df["sep_hc"] & ~df["pool_hc"]]  # sauvetage : separee casse, commune sauve
    reverse = df[~df["sep_hc"] & df["pool_hc"]]  # sens inverse : commune casse, separee non
    print(f"\n[ceiling={ceiling:.0f}$] n={n_sims}")
    print(f"  Runs 'sauvetage' (separee hit_ceiling, commune non) : {len(rescue_T1)}/{n_sims} ({len(rescue_T1)/n_sims*100:.2f}%)")
    print(f"  Runs sens inverse (commune hit_ceiling, separee non) : {len(reverse)}/{n_sims} ({len(reverse)/n_sims*100:.2f}%)")

    # Etape 2 : direction du sauvetage (rejoue les runs 'sauvetage' avec journal)
    rescue_runs = rescue_T1["run_idx"].tolist()
    direction_counts = {"T1": 0, "T2": 0, "aucun_event(?)": 0}
    for run_idx in rescue_runs:
        raw_trades, raw_slots, order, raw_trades_c, raw_slots_c = draws[run_idx]
        res_sep_logged = dt.run_dual(raw_trades, raw_slots, market_data, excluded_map, order, seq, config,
                                      ei.DEFAULT_EMERGENCY, dt.EVAL_RISK, dt.FLEET_RISK, dt.GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                                      ei.EXTRA_THRESHOLD_MULT, reserve_pooled=False, log_events=True,
                                      contrarian_trades=raw_trades_c, contrarian_slots=raw_slots_c, **kw_common)
        events = res_sep_logged["event_log"]
        hc_events = [e for e in events if e["type_evenement"] == "hit_ceiling_touche"]
        if hc_events:
            direction_counts[hc_events[0]["trader"]] += 1
        else:
            direction_counts["aucun_event(?)"] += 1

    print(f"\n  Direction du sauvetage (parmi les {len(rescue_runs)} runs 'sauvetage') :")
    for k, v in direction_counts.items():
        pct = (v / len(rescue_runs) * 100) if rescue_runs else 0
        print(f"    {k} declenche hit_ceiling sous reserves separees (donc sauve par le pooling) : {v} ({pct:.1f}%)")

    # Etape 3 : decomposition du profit combine
    # MAJ 08/12 (cascade RR1.35+corr0.80, registre_parametres_projet.md
    # §2.62) : reference solo T1 mise a jour avec les VRAIS chiffres n=600
    # deja regeneres sous la nouvelle base (etape_aq_run_c/etape_ar_run_f,
    # meme config/moteur que T1 -- Run C a 1000$ [pas de BB7j], Run F a
    # 3000$ [BB7j actif, coherent avec BB_7J_CEILING_THRESHOLD=3000.0 de ce
    # fichier]) -- remplace l'ancienne reference n=300 structure_pistes
    # (§2.44, RR1.25+corr0.6, desormais perimee).
    solo_ref = {1000.0: 5836643.0, 3000.0: 5900859.0}.get(ceiling)
    mean_sep_T1, mean_sep_T2 = df["sep_T1"].mean(), df["sep_T2"].mean()
    mean_pool_T1, mean_pool_T2 = df["pool_T1"].mean(), df["pool_T2"].mean()
    print(f"\n  Decomposition profit moyen (n={n_sims}) :")
    print(f"    T1_net separee = {mean_sep_T1:+,.0f}$   T1_net commune = {mean_pool_T1:+,.0f}$   "
          f"delta pooling pour T1 = {mean_pool_T1-mean_sep_T1:+,.0f}$")
    print(f"    T2_net separee = {mean_sep_T2:+,.0f}$   T2_net commune = {mean_pool_T2:+,.0f}$   "
          f"delta pooling pour T2 = {mean_pool_T2-mean_sep_T2:+,.0f}$")
    if solo_ref is not None:
        print(f"    Reference T1 solo (flotte simple, sans T2 du tout) = {solo_ref:+,.0f}$")
        print(f"    T1_net commune vs solo = {mean_pool_T1-solo_ref:+,.0f}$ ({(mean_pool_T1/solo_ref-1)*100:+.2f}%)")
        print(f"    T1_net separee vs solo = {mean_sep_T1-solo_ref:+,.0f}$ ({(mean_sep_T1/solo_ref-1)*100:+.2f}%)")

    return df, direction_counts


if __name__ == "__main__":
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    ceiling = float(sys.argv[2]) if len(sys.argv) > 2 else 3000.0
    t_start = time.time()
    import rr_threshold_test as rrt
    print(f"[verif] HIST_PATH = {rrt.HIST_PATH}, FIRM_MAX_ACCOUNTS Blueberry = {ei.FIRM_MAX_ACCOUNTS['Blueberry']}")
    main(n_sims, ceiling)
    print(f"\nTermine en {time.time()-t_start:.0f}s.")
