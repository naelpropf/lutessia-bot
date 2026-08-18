"""
Etape AA (08/10 nuit, suite 11) : sur la reference officielle actuelle
(REF+V2 + cap Blueberry corrige + FTMO-10%/GFT Goat Guard), compare le
profit total a 4 ans entre les runs qui finissent annee1<0 et ceux qui
finissent annee1>0 -- verifie si l'ecart historique (~30%+, mesure avant
la refonte multi-phase et avant la correction Blueberry) tient toujours.

Reutilise directement etape_q_v2_plus_ftmo_gft_2026-08-10.py (nom de
fichier avec tirets, charge via importlib) -- meme code, meme seed, pas
de nouveau tirage aleatoire, juste une lecture differente du meme
DataFrame de sortie (le script officiel ne sauvegarde que le resume
agrege, pas le split par groupe).

N'importe pas ce script directement (convention du projet).
"""
import importlib.util
import sys
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
from point_liquidity_rules import CORR_TH
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs
import etape_e_fleet_integration as ei

spec = importlib.util.spec_from_file_location("etape_q_mod", "etape_q_v2_plus_ftmo_gft_2026-08-10.py")
etape_q_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(etape_q_mod)

if __name__ == "__main__":
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    ceilings_arg = [float(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [1000.0, 3000.0]

    t_start = time.time()
    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)
    seq = ei.seq_grouped_multi(1000, 15000, 25000, 25000)
    config = ei.CONFIG_REF
    EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK = 1.25, 1.90, 1.75

    print(f"[verif] FIRM_MAX_ACCOUNTS Blueberry = {ei.FIRM_MAX_ACCOUNTS['Blueberry']}, "
          f"FIRM_CAPITAL_CAP Blueberry = {ei.FIRM_CAPITAL_CAP['Blueberry']:,.0f}$")

    rows = []
    for ceiling in ceilings_arg:
        t0 = time.time()
        df = etape_q_mod.run_propagated(pop, market_data, excluded_map, ceiling, seq, config, ei.DEFAULT_EMERGENCY,
                                         EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE,
                                         ei.EXTRA_THRESHOLD_MULT, n_sims=n_sims, seed=9999,
                                         b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True,
                                         ftmo_discount=True, gft_goat_guard=True)
        net = df["final_net_split"] - df["is_paid_cum"]
        year1_neg = df["year1_net_split"] < 0

        profit_all = net.mean()
        profit_neg = net[year1_neg].mean()
        profit_pos = net[~year1_neg].mean()
        n_neg = year1_neg.sum()
        n_pos = (~year1_neg).sum()
        gap_abs = profit_pos - profit_neg
        gap_pct_of_mean = gap_abs / profit_all * 100
        gap_pct_relative = gap_abs / profit_neg * 100 if profit_neg != 0 else float("nan")

        row = dict(ceiling=ceiling, n=len(df), n_annee1_neg=n_neg, n_annee1_pos=n_pos,
                   pct_annee1_neg=year1_neg.mean() * 100,
                   profit_moyen_tous=profit_all,
                   profit_moyen_annee1_neg=profit_neg,
                   profit_moyen_annee1_pos=profit_pos,
                   ecart_abs=gap_abs,
                   ecart_pct_du_profit_moyen=gap_pct_of_mean,
                   ecart_pct_relatif_au_groupe_neg=gap_pct_relative)
        rows.append(row)
        print(f"[plafond={ceiling:.0f}$] n_annee1_neg={n_neg} ({row['pct_annee1_neg']:.1f}%) "
              f"n_annee1_pos={n_pos} | profit_moy_TOUS={profit_all:+,.0f}$ | "
              f"profit_moy_annee1_NEG={profit_neg:+,.0f}$ | profit_moy_annee1_POS={profit_pos:+,.0f}$ | "
              f"ecart={gap_abs:+,.0f}$ ({gap_pct_of_mean:.1f}% du profit moyen, "
              f"{gap_pct_relative:.1f}% relatif au groupe neg) "
              f"({time.time()-t0:.0f}s)")
        pd.DataFrame(rows).to_csv(f"etape_aa_annee1_profit_gap_n{n_sims}.csv", index=False)

    print(f"\nTermine en {time.time()-t_start:.0f}s.")
