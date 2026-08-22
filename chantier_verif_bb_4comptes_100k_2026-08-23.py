"""chantier_verif_bb_4comptes_100k_2026-08-23.py

Correction structurelle (pas juste le prix) confirmee par l'utilisateur :
Blueberry limite reellement a 4 comptes MAX par personne (pivot inclus,
donc 3 comptes extra) et Instant Elite est plafonne a 100k$/compte -- le
moteur actuel modelise a tort un NOMBRE ILLIMITE de comptes extra a 50k$
chacun (BASE_PALIER["Blueberry"]=25k x EXTRA_ACCOUNT_MULT=2.0=50k,
FIRM_MAX_ACCOUNTS["Blueberry"]=None) jusqu'a un plafond de capital cumule
de 400k$ (~7 comptes extra).

Compare DIRECTEMENT (meme seed, meme population B_tradable_pgp, ceiling
1000$) :
  - BASELINE (bug actuel) : illimite, 50k$/compte, 333$/ouverture (prix
    extrapole generique, deja identifie faux).
  - CORRIGE : max 4 comptes Blueberry au total (pivot inclus, 3 extra
    max), 100k$/compte extra, prix Instant Elite 100k estime par ratio
    reel sourcee (Blueberry_2StepStandard 100k/25k=620/170=3,647x
    applique a l'ancre Instant Elite 25k=800$ -> ~2918$/ouverture).

Metriques : profit, annee1<0%, nombre d'ouvertures Instant/Classic,
total_opens (validation que le cap a 4 comptes est bien respecte).
"""
import importlib.util
import random

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

RATIO_100K = 620.0 / 170.0  # 3,647 -- ratio reel sourcee Blueberry_2StepStandard 100k/25k
CORRECTED_PRICE_INSTANT_100K = round(800.0 * RATIO_100K)  # ~2918$


def build_run_one_capped():
    """Patch minimal de s18.run_one : le SEUL changement est le calcul de
    unit_palier pour Blueberry specifiquement dans process_extra_account
    (100k au lieu de BASE_PALIER*EXTRA_ACCOUNT_MULT=50k) -- FTMO/GFT
    (les 2 autres GROWTH_FIRMS_EXTRA) restent inchanges, non concernes par
    cette correction Blueberry-specifique."""
    import inspect
    src = inspect.getsource(s18.run_one)
    src = src.replace("def run_one(", "def run_one_capped(", 1)
    marker = 'unit_palier = BASE_PALIER[gname] * ei.EXTRA_ACCOUNT_MULT'
    assert marker in src, "point d'injection unit_palier introuvable"
    src = src.replace(marker,
                       'unit_palier = 100000.0 if gname == "Blueberry" else BASE_PALIER[gname] * ei.EXTRA_ACCOUNT_MULT',
                       1)
    ns = dict(s18.run_one.__globals__)
    code = compile(src, "<run_one_capped>", "exec")
    exec(code, ns)
    return ns["run_one_capped"]


def run_batch(label, run_one_fn):
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
        res = run_one_fn(rt, rs, market_data, excluded_map, order, CEILING,
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
    print(f"[{label}] profit_moy={profit.mean():+,.0f}$ annee1_neg={(df['year1_net_split']<0).mean()*100:.2f}% "
          f"bb_instant_opens_moy={df['bb_instant_opens'].mean():.2f} bb_classic_opens_moy={df['bb_classic_opens'].mean():.2f} "
          f"total_opens_moy={df['total_opens'].mean():.2f} total_opens_max={df['total_opens'].max():.0f}", flush=True)
    return df, profit


def main():
    print(f"Prix Instant Elite 100k corrige (ratio reel 2StepStandard 100k/25k={RATIO_100K:.3f}) : "
          f"{CORRECTED_PRICE_INSTANT_100K}$", flush=True)

    print("\n--- BASELINE (bug actuel : illimite, 50k$/compte, 333$) ---", flush=True)
    df_base, profit_base = run_batch("baseline_bug", s18.run_one)

    ei.FIRM_MAX_ACCOUNTS["Blueberry"] = 4  # pivot inclus -> 3 extra max
    emf.FORMATS["Blueberry_InstantElite"]["price"][100000] = CORRECTED_PRICE_INSTANT_100K
    run_one_capped = build_run_one_capped()

    print("\n--- CORRIGE (max 4 comptes total, 100k$/extra, prix sourcee) ---", flush=True)
    df_corr, profit_corr = run_batch("corrige_4comptes_100k", run_one_capped)

    print(f"\n{'='*90}\nDELTA (corrige - baseline)\n{'='*90}")
    print(f"  delta profit_moy = {profit_corr.mean()-profit_base.mean():+,.0f}$ "
          f"({(profit_corr.mean()/profit_base.mean()-1)*100:+.2f}%)")
    a1_base = (df_base["year1_net_split"] < 0).mean() * 100
    a1_corr = (df_corr["year1_net_split"] < 0).mean() * 100
    print(f"  delta annee1<0 = {a1_corr-a1_base:+.2f}pts ({a1_base:.2f}% -> {a1_corr:.2f}%)")
    print(f"  baseline total_opens_moy={df_base['total_opens'].mean():.2f} (max={df_base['total_opens'].max():.0f}) "
          f"vs corrige total_opens_moy={df_corr['total_opens'].mean():.2f} (max={df_corr['total_opens'].max():.0f})")


if __name__ == "__main__":
    main()
