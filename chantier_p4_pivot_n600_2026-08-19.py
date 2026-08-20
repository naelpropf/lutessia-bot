"""
Point 4 (session 18/08->19/08) -- confirmation n=600 du pivot Instant a
taille reduite (5k$/10k$) vs REF (pivot InstantElite25k) ET vs REF-sans-
pivot-Instant (Prime25k, pivot classique pre-18/08 -- pas de pivot Instant
du tout).

Reutilise integralement chantier_pivot_instant_taille_reduite_2026-08-18.py
(4 configs deja codees : Prime25k/InstantElite25k/InstantElite10k/
InstantElite5k, risque 1,5% Instant deja integre) via importlib, SEUL
ajout : garde-fou population forex-only (meme raison que Points 2/3 --
build_population_with_trailing() inclut desormais les indices
automatiquement depuis le correctif rr_threshold_test.py:43-61 du 08/18,
applique APRES l'execution originale n=300 de ce script a 00:27 -- verifie
par timestamp fichier, cf. ls -la : script pivot modifie 2026-08-18 00:27,
patch rr_threshold_test.py modifie 2026-08-18 04:13, donc le n=300
original n'etait PAS contamine, mais un re-run aujourd'hui le serait sans
ce garde-fou -- eng.load_market_data() ne couvre pas les indices, meme
KeyError que Points 2/3).

N'importe pas ce script directement (convention du projet).
"""
import importlib.util
import sys
import time

import pandas as pd

PIVOT_SCRIPT = "chantier_pivot_instant_taille_reduite_2026-08-18.py"

spec = importlib.util.spec_from_file_location("pivot_p4", PIVOT_SCRIPT)
piv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(piv)

INDEX_KEYWORDS = ["DAX40", "S&P500", "NASDAQ100", "DJ30"]


def load_common_forex_only():
    pop, market_data, excluded_map = piv.load_common()
    is_index = pop["ticker"].str.contains("|".join(INDEX_KEYWORDS), case=False, na=False)
    n_before = len(pop)
    pop = pop[~is_index].reset_index(drop=True)
    if len(pop) != n_before:
        tickers = sorted(pop["ticker"].unique())
        excluded_map = piv.precompute_correlation_pairs(
            tickers, pd.read_csv("correlation_matrix.csv", index_col=0), piv.CORR_TH_NEW)
    return pop, market_data, excluded_map


if __name__ == "__main__":
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    ceilings_arg = [float(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [3000.0, 5000.0]

    t_start = time.time()
    pop, market_data, excluded_map = load_common_forex_only()
    print(f"[verif] population REF (forex-only) : {len(pop)} trades")
    seq = piv.ei.seq_grouped_multi(1000, 15000, 25000, 25000)
    config = piv.ei.CONFIG_REF

    common_kwargs = dict(emergency=piv.ei.DEFAULT_EMERGENCY, eval_risk=piv.EVAL_RISK, fleet_risk=piv.FLEET_RISK,
                          gft_eval_risk=piv.GFT_EVAL_RISK, reserve_share=piv.ei.FINAL_RESERVE_SHARE,
                          extra_threshold_mult=piv.ei.EXTRA_THRESHOLD_MULT, n_sims=n_sims, seed=9999,
                          b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True,
                          ftmo_discount=True, gft_goat_guard=True, payout_cycle=True)

    BB_THRESHOLD_BY_CEILING = {960.0: 5000.0, 1000.0: 5000.0, 3000.0: 0.0, 5000.0: 0.0}

    PIVOT_TESTS = [
        ("Prime25k", "Blueberry_Prime2Step", 25000.0, 165.0),
        ("InstantElite25k", "Blueberry_InstantElite", 25000.0, 800.0),
        ("InstantElite10k", "Blueberry_InstantElite", 10000.0, 400.0),
        ("InstantElite5k", "Blueberry_InstantElite", 5000.0, 200.0),
    ]

    rows = []
    for ceiling in ceilings_arg:
        bb_th = BB_THRESHOLD_BY_CEILING[ceiling]
        for label, fmt_key, palier, cout in PIVOT_TESTS:
            t0 = time.time()
            df = piv.run_propagated(pop, market_data, excluded_map, ceiling, seq, config,
                                     bb_threshold=bb_th, use_any_rr=True, apply_instant_risk_cap=True,
                                     pivot_fmt_key=fmt_key, pivot_palier=palier, **common_kwargs)
            row = piv.summarize(df, label, ceiling, bb_th, True, cout)
            rows.append(row)
            print(f"[{label:16s} cout={cout:.0f}$ plafond={ceiling:.0f}$] profit_moy={row['profit_moyen']:+,.0f}$ "
                  f"solde_neg={row['solde_negatif_annee4']:.2f}% hit_ceiling={row['hit_ceiling_pct']:.2f}% "
                  f"annee1<0={row['annee1_neg']:.2f}% ({time.time()-t0:.0f}s)")
            pd.DataFrame(rows).to_csv(f"chantier_p4_pivot_n{n_sims}_2026-08-19.csv", index=False)

    print(f"\nTermine en {time.time()-t_start:.0f}s.")
