"""chantier_cluster_cap_impact_v2_2026-08-23.py

Correction de chantier_cluster_cap_impact_2026-08-23.py (INVALIDE, bug
confirme : le cap de cluster s'appliquait meme a une position SEULE dans un
cluster vide, contaminant le signal avec un effet "cap 1,5% solo" sans
rapport avec la co-occurrence -- FLEET_RISK=1,90% > CLUSTER_CAP=1,5% donc
meme un trade isole se faisait raboter).

Perimetre definitif (indices US confirme deja protege a 100% par
l'exclusion existante, |corr| 0,95-1,00 > seuil 0,80 -- pas reteste) :
  - metaux : XAUUSD+XAGUSD SEULS (GOLD-USD + SILVER-USD, 11 co-occurrences
    confirmees) -- PAS les 5 croisements EUR/GBP/AUD qui ont leur propre
    budget separe chez Blueberry.
  - fx_majors : les 7 paires majors (EUR/USD, GBP/USD, USD/JPY, USD/CHF,
    USD/CAD, AUD/USD, NZD/USD), 24 co-occurrences confirmees.

Mecanisme corrige (verifie explicitement au point 3 ci-dessous) : le budget
de cluster ne s'applique QUE si une AUTRE position du meme cluster est DEJA
ouverte au moment ou la nouvelle tente de s'ouvrir -- une position seule
dans un cluster vide n'est JAMAIS touchee, garde son risque individuel
normal (1,25/1,90% selon phase, deja plafonne a 1,5% si Instant par
BB_INSTANT_RISK_CAP, mecanisme INCHANGE). Si une 2e position du cluster
s'ouvre pendant que la 1re est encore ouverte : risque combine (1re+2e)
plafonne a CLUSTER_CAP=1,5% total -- budget residuel = max(0, 1,5% -
risque deja engage), 0 si la 1re occupe deja >=1,5% a elle seule.
"""
import importlib.util
import inspect
import random
import sys
import time

import numpy as np
import pandas as pd

_spec = importlib.util.spec_from_file_location("pdb", "point_d_bloc1_bloc2_2026-08-22.py")
pdb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pdb)
bsl = pdb.bsl
s18 = pdb.s18
abm = pdb.abm
ei = pdb.ei

import engine_multiformat as emf

from real_cash_risk_year1_block_bootstrap import build_blocks
from reference_metrics_final import build_full_block_bootstrap_sequence

DAY_SECONDS = 86400
BLOCK_SECONDS = 2 * 30 * DAY_SECONDS
CLUSTER_CAP = 1.5  # %, risque COMBINE max par cluster (pas par position)

FX_MAJORS = {"EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "USD/CAD", "AUD/USD", "NZD/USD"}
METAUX_XAUUSD_XAGUSD = {"GOLD - USD", "SILVER - USD"}

CLUSTER_SETS = {"metaux_xauusd_xagusd": METAUX_XAUUSD_XAGUSD, "fx_majors": FX_MAJORS}


def cluster_of(ticker):
    for cname, cset in CLUSTER_SETS.items():
        if ticker in cset:
            return cname
    return None


def build_process_trade_mf_cluster(active_clusters):
    src = inspect.getsource(emf.process_trade_mf)
    src = src.replace("def process_trade_mf(", "def process_trade_mf_cluster(", 1)
    marker = 'eff_risk, _ = eng.feasible_risk_pct('
    assert marker in src, "point d'injection introuvable dans process_trade_mf"
    # <<< FIX v2 : le cap ne s'applique QUE si _open[_cl] est deja NON-VIDE
    # (une autre position du cluster deja ouverte) -- une position seule ne
    # rentre JAMAIS dans le bloc if, garde risk_pct intact, seulement
    # enregistree dans le tracker pour la PROCHAINE position eventuelle.
    inject = (
        '    _cl = CLUSTER_OF.get(trade["ticker"])\n'
        '    if _cl is not None and _cl in ACTIVE_CLUSTERS:\n'
        '        _open = acc.setdefault("_cluster_risk_open", {})\n'
        '        _open[_cl] = [(c, rp) for (c, rp) in _open.get(_cl, []) if c > now]\n'
        '        if _open[_cl]:\n'
        '            _committed = sum(rp for c, rp in _open[_cl])\n'
        '            _remaining = max(0.0, CLUSTER_CAP - _committed)\n'
        '            if risk_pct > _remaining:\n'
        '                risk_pct = _remaining\n'
        '            if risk_pct <= 0:\n'
        '                return False\n'
        '        _open[_cl].append((close_time, risk_pct))\n'
        '    ' + marker
    )
    src = src.replace('    ' + marker, inject, 1)
    ns = dict(emf.process_trade_mf.__globals__)
    ns["CLUSTER_OF"] = {t: cluster_of(t) for cset in CLUSTER_SETS.values() for t in cset}
    ns["CLUSTER_CAP"] = CLUSTER_CAP
    ns["ACTIVE_CLUSTERS"] = active_clusters
    code = compile(src, "<process_trade_mf_cluster_v2>", "exec")
    exec(code, ns)
    return ns["process_trade_mf_cluster"], ns


def build_process_trade_corr_swap_rr_cluster(process_trade_mf_cluster_fn):
    src = inspect.getsource(s18.process_trade_corr_swap_rr)
    src = src.replace("def process_trade_corr_swap_rr(", "def process_trade_corr_swap_rr_cluster(", 1)
    ns = dict(s18.process_trade_corr_swap_rr.__globals__)
    ns["process_trade_mf"] = process_trade_mf_cluster_fn
    code = compile(src, "<process_trade_corr_swap_rr_cluster_v2>", "exec")
    exec(code, ns)
    return ns["process_trade_corr_swap_rr_cluster"]


def build_run_one_cluster(active_clusters):
    process_trade_mf_cluster_fn, _ = build_process_trade_mf_cluster(active_clusters)
    process_trade_corr_swap_rr_cluster_fn = build_process_trade_corr_swap_rr_cluster(process_trade_mf_cluster_fn)

    src = inspect.getsource(s18.run_one)
    src = src.replace("def run_one(", "def run_one_cluster(", 1)
    code = compile(src, "<run_one_cluster_v2>", "exec")
    ns = dict(s18.run_one.__globals__)
    ns["process_trade_mf"] = process_trade_mf_cluster_fn
    ns["process_trade_corr_swap_rr"] = process_trade_corr_swap_rr_cluster_fn
    exec(code, ns)
    return ns["run_one_cluster"]


def verify_solo_not_touched():
    """Point 3 explicite : verifie par test direct qu'une position SEULE
    (pas d'autre position du meme cluster ouverte) traverse process_trade_mf_
    cluster avec un risk_pct STRICTEMENT INCHANGE, y compris quand risk_pct
    depasse deja CLUSTER_CAP=1,5% (ex: 1,90% funded) -- c'etait exactement
    le bug v1."""
    fn, ns = build_process_trade_mf_cluster({"fx_majors"})
    acc = {"active": True, "open_positions": [], "cumulative_since_reset": 0.0, "peak_since_reset": 0.0,
           "trading_days_since_reset": set(), "trades_taken": 0, "daily_pnl": {}, "phase": "funded",
           "phase_index": 0, "palier": 25000.0, "cost": 800.0, "_reset_used": False,
           "total_funded_pnl": 0.0, "total_fees_paid": 0.0}
    fmt = {"phases": [], "funded": {"dd_daily_pct": None, "dd_max_pct": None, "dd_max_mode": "static", "target_pct": None, "min_days": None}}
    trade = {"ticker": "EUR/USD", "outcome_r": -1.0, "sl_distance": 0.001, "hold_seconds": 3600}
    market_data = {"EUR/USD": {"tick_size": 0.00001, "tick_value": 1.0, "volume_min": 0.01,
                                "volume_max": 100.0, "volume_step": 0.01, "margin_per_lot": 1000.0, "price": 1.1}}
    excluded_map = {"EUR/USD": set()}
    state = {"reserve": 0.0, "total_breaks": 0}
    risk_pct_in = 1.90  # > CLUSTER_CAP=1.5, cas exact du bug v1
    fn(acc, trade, 0.0, fmt, state, risk_pct_in, market_data, excluded_map)
    committed_after = acc["_cluster_risk_open"]["fx_majors"][0][1]
    ok = abs(committed_after - risk_pct_in) < 1e-9
    print(f"[VERIF point 3] position SEULE, risk_pct entree={risk_pct_in}% (>CLUSTER_CAP={CLUSTER_CAP}%) -> "
          f"risk_pct enregistre apres passage={committed_after}% -- "
          f"{'OK, JAMAIS touche' if ok else 'BUG : le cap solo agit encore !'}", flush=True)
    assert ok, "Le bug v1 (cap applique a une position solo) n'est PAS corrige -- arret."


def run_propagated(pop, market_data, excluded_map, ceiling, seq_grouped, format_by_firm, emergency,
                    eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult, n_sims, seed,
                    alpha_post, beta_post, run_one_fn, **kw):
    rng_wr = random.Random(seed)
    rng_boot = random.Random(seed + 1)
    rows = []
    for _ in range(n_sims):
        wr_draw = rng_wr.betavariate(alpha_post, beta_post)
        trades, slot_arrivals = s18.build_flexible_population_with_rr(pop, wr_draw, 1.0, False, random.Random(rng_boot.random()))
        blocks = build_blocks(trades, slot_arrivals, BLOCK_SECONDS)
        target_duration = slot_arrivals[-1]
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, BLOCK_SECONDS, rng_boot, target_duration)
        order = list(range(len(raw_trades)))
        res = run_one_fn(raw_trades, raw_slots, market_data, excluded_map, order, ceiling, seq_grouped, format_by_firm,
                          emergency, eval_risk, fleet_risk, gft_eval_risk, reserve_share, extra_threshold_mult, **kw)
        rows.append(res)
    return pd.DataFrame(rows)


def run_config(pop, market_data, excluded_map, alpha_post, beta_post, ceiling, n_sims, seed, run_one_fn, label):
    common_kwargs = dict(emergency=ei.DEFAULT_EMERGENCY, eval_risk=abm.EVAL_RISK, fleet_risk=abm.FLEET_RISK,
                          gft_eval_risk=abm.GFT_EVAL_RISK, reserve_share=ei.FINAL_RESERVE_SHARE,
                          extra_threshold_mult=ei.EXTRA_THRESHOLD_MULT, n_sims=n_sims, seed=seed,
                          b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True,
                          ftmo_discount=True, gft_goat_guard=True, payout_cycle=True)
    bb_th = abm.BB_THRESHOLD_BY_CEILING[ceiling]
    t0 = time.time()
    df = run_propagated(pop, market_data, excluded_map, ceiling,
                         ei.seq_grouped_multi(1000, 15000, 25000, 25000), ei.CONFIG_REF,
                         bb_threshold=bb_th, use_any_rr=True, apply_instant_risk_cap=True,
                         alpha_post=alpha_post, beta_post=beta_post, run_one_fn=run_one_fn,
                         **common_kwargs)
    row = s18.summarize(df, label, ceiling, bb_th, True)
    dt = time.time() - t0
    print(f"[{label} c={ceiling:.0f}$] profit_moy={row['profit_moyen']:+,.0f}$ "
          f"solde_neg_an4={row['solde_negatif_annee4']:.2f}% annee1<0={row['annee1_neg']:.2f}% n={n_sims} ({dt:.0f}s)", flush=True)
    return row


def main():
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 987654321

    verify_solo_not_touched()

    pop_b, market_data_b, excluded_map_b, alpha_post_b, beta_post_b, _ = pdb.load_scenario_pgp()
    pop_a, market_data_a, excluded_map_a, alpha_post_a, beta_post_a, _ = bsl.load_scenario("A")

    run_one_plain = s18.run_one

    CONFIGS = [
        ("B_tradable_pgp", pop_b, market_data_b, excluded_map_b, alpha_post_b, beta_post_b,
         [("metaux_xauusd_xagusd", {"metaux_xauusd_xagusd"}), ("fx_majors", {"fx_majors"}),
          ("les_deux", {"metaux_xauusd_xagusd", "fx_majors"})]),
        ("A", pop_a, market_data_a, excluded_map_a, alpha_post_a, beta_post_a,
         [("fx_majors", {"fx_majors"})]),
    ]

    all_rows = []
    for pop_name, pop, market_data, excluded_map, alpha_post, beta_post, variants in CONFIGS:
        for ceiling in [3000.0, 5000.0]:
            print(f"\n{'='*95}\n{pop_name} c={ceiling:.0f}$\n{'='*95}", flush=True)
            row_ref = run_config(pop, market_data, excluded_map, alpha_post, beta_post, ceiling, n_sims, seed,
                                  run_one_plain, f"{pop_name}_REF c={ceiling:.0f}")
            row_ref["variant"] = "REF"
            row_ref["pop"] = pop_name
            all_rows.append(row_ref)

            for cname, cset in variants:
                run_one_fn = build_run_one_cluster(cset)
                row = run_config(pop, market_data, excluded_map, alpha_post, beta_post, ceiling, n_sims, seed,
                                  run_one_fn, f"{pop_name}_cap_{cname} c={ceiling:.0f}")
                delta_profit = (row["profit_moyen"] - row_ref["profit_moyen"]) / abs(row_ref["profit_moyen"]) * 100
                print(f"  -> impact cap {cname:22s} : delta profit={delta_profit:+.2f}%, "
                      f"delta solde_neg={row['solde_negatif_annee4']-row_ref['solde_negatif_annee4']:+.2f}pts, "
                      f"delta annee1<0={row['annee1_neg']-row_ref['annee1_neg']:+.2f}pts", flush=True)
                row["variant"] = cname
                row["pop"] = pop_name
                all_rows.append(row)
                pd.DataFrame(all_rows).to_csv("chantier_cluster_cap_impact_v2_2026-08-23.csv", index=False)

    print(f"\n{'='*95}\nSYNTHESE\n{'='*95}")
    print(pd.DataFrame(all_rows)[["pop", "ceiling", "variant", "profit_moyen", "solde_negatif_annee4", "annee1_neg"]].to_string(index=False))


if __name__ == "__main__":
    main()
