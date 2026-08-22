"""chantier_verif_prix_bb_extra_2026-08-23.py

Verification directe (pas deduction) : le prix des comptes Blueberry extra
a 50k$ (BASE_PALIER["Blueberry"]=25k x EXTRA_ACCOUNT_MULT=2.0) retombe sur
une extrapolation lineaire generique (FEE_RATIO, engine_multiformat.py
price_for()) faute d'entree {50000: ...} dans FORMATS["Blueberry_
InstantElite"]/["Blueberry_Prime2Step"]["price"] -- 333$ actuellement pour
Instant ET Classic, alors qu'on a une vraie table sourcee (tradingpilot.com,
confidence_notes Blueberry_2StepStandard) : 25K=170$/50K=315$/100K=620$/
200K=1240$ -- ratio 50k/25k=1,853 (progression sous-lineaire, pas le ratio
generique). Applique a l'ancre reelle Instant Elite 25k=800$ :
50k corrige ~= 800*1,853 ~= 1482$ (vs 333$ actuel, x4,45).

Compare DIRECTEMENT (meme seed, meme population, seul le prix change) :
annee1<0%, timing d'ouverture de flotte (full_structure_month), nombre
d'ouvertures Instant/Classic, profit -- baseline (prix actuel, bug) vs
corrige (prix estime par ratio sourcee).
"""
import importlib.util
import random

import numpy as np
import pandas as pd

_spec = importlib.util.spec_from_file_location("pdb", "point_d_bloc1_bloc2_2026-08-22.py")
pdb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pdb)
s18, abm, ei = pdb.s18, pdb.abm, pdb.ei

import engine_multiformat as emf

from real_cash_risk_year1_block_bootstrap import build_blocks
from reference_metrics_final import build_full_block_bootstrap_sequence

DAY_SECONDS = 86400
BLOCK_SECONDS = 2 * 30 * DAY_SECONDS
CEILING = 1000.0
N_SIMS = 50
SEED = 2468

RATIO_50K = 315.0 / 170.0  # 1,853 -- ratio reel sourcee Blueberry_2StepStandard 50k/25k
CORRECTED_PRICE_INSTANT_50K = round(800.0 * RATIO_50K)   # ~1482$
CORRECTED_PRICE_CLASSIC_50K = round(165.0 * RATIO_50K)   # ~306$ (proche de l'extrapolation actuelle)


def run_batch(label):
    common_kwargs = dict(emergency=ei.DEFAULT_EMERGENCY, eval_risk=abm.EVAL_RISK, fleet_risk=abm.FLEET_RISK,
                          gft_eval_risk=abm.GFT_EVAL_RISK, reserve_share=ei.FINAL_RESERVE_SHARE,
                          extra_threshold_mult=ei.EXTRA_THRESHOLD_MULT,
                          b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True,
                          ftmo_discount=True, gft_goat_guard=True, payout_cycle=True)
    pop, market_data, excluded_map, alpha_post, beta_post, _ = pdb.load_scenario_pgp()
    rng_wr = random.Random(SEED)
    rng_boot = random.Random(SEED + 1)
    rows = []
    for _ in range(N_SIMS):
        wr = rng_wr.betavariate(alpha_post, beta_post)
        trades, slots = s18.build_flexible_population_with_rr(pop, wr, 1.0, False, random.Random(rng_boot.random()))
        blocks = build_blocks(trades, slots, BLOCK_SECONDS)
        target = slots[-1]
        rt, rs = build_full_block_bootstrap_sequence(blocks, BLOCK_SECONDS, rng_boot, target)
        order = list(range(len(rt)))
        res = s18.run_one(rt, rs, market_data, excluded_map, order, CEILING,
                           ei.seq_grouped_multi(1000, 15000, 25000, 25000), ei.CONFIG_REF,
                           ei.DEFAULT_EMERGENCY, abm.EVAL_RISK, abm.FLEET_RISK, abm.GFT_EVAL_RISK,
                           ei.FINAL_RESERVE_SHARE, ei.EXTRA_THRESHOLD_MULT,
                           b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True,
                           ftmo_discount=True, gft_goat_guard=True, payout_cycle=True,
                           bb_threshold=abm.BB_THRESHOLD_BY_CEILING[CEILING], use_any_rr=True,
                           apply_instant_risk_cap=True)
        rows.append(res)
    df = pd.DataFrame(rows)
    profit = df["final_net_split"] - df["is_paid_cum"]
    print(f"[{label}] profit_moy={profit.mean():+,.0f}$ annee1_neg={ (df['year1_net_split']<0).mean()*100:.2f}% "
          f"bb_instant_opens_moy={df['bb_instant_opens'].mean():.2f} bb_classic_opens_moy={df['bb_classic_opens'].mean():.2f} "
          f"total_opens_moy={df['total_opens'].mean():.2f}", flush=True)
    return df, profit


def main():
    print(f"Prix corrige estime (ratio reel sourcee 2StepStandard 50k/25k={RATIO_50K:.3f}) : "
          f"Instant 50k = {CORRECTED_PRICE_INSTANT_50K}$ (vs 333$ actuel, x{CORRECTED_PRICE_INSTANT_50K/333:.2f}), "
          f"Classic 50k = {CORRECTED_PRICE_CLASSIC_50K}$ (vs 333$ actuel)", flush=True)

    print("\n--- BASELINE (prix actuel, bug) ---", flush=True)
    df_base, profit_base = run_batch("baseline_bug")

    # patch les prix directement dans FORMATS -- meme process, aucune copie de module
    emf.FORMATS["Blueberry_InstantElite"]["price"][50000] = CORRECTED_PRICE_INSTANT_50K
    emf.FORMATS["Blueberry_Prime2Step"]["price"][50000] = CORRECTED_PRICE_CLASSIC_50K

    print("\n--- CORRIGE (prix sourcee estime) ---", flush=True)
    df_corr, profit_corr = run_batch("corrige")

    print(f"\n{'='*90}\nDELTA (corrige - baseline)\n{'='*90}")
    print(f"  delta profit_moy = {profit_corr.mean()-profit_base.mean():+,.0f}$ "
          f"({(profit_corr.mean()/profit_base.mean()-1)*100:+.2f}%)")
    a1_base = (df_base["year1_net_split"] < 0).mean() * 100
    a1_corr = (df_corr["year1_net_split"] < 0).mean() * 100
    print(f"  delta annee1<0 = {a1_corr-a1_base:+.2f}pts ({a1_base:.2f}% -> {a1_corr:.2f}%)")
    print(f"  delta bb_instant_opens_moy = {df_corr['bb_instant_opens'].mean()-df_base['bb_instant_opens'].mean():+.2f}")
    print(f"  delta total_opens_moy = {df_corr['total_opens'].mean()-df_base['total_opens'].mean():+.2f}")


if __name__ == "__main__":
    main()
