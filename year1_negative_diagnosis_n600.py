"""
Reconfirmation a n=600 de year1_negative_diagnosis.py (initialement a
n=300), suite a la confirmation que l'ecart 29,3% (n=300) vs 27,5% (n=600,
REF deja valide) etait du bruit d'echantillonnage, pas un bug. Meme seed
que le REF@1000$ deja valide (777) pour comparabilite directe.

Fichier separe plutot que d'editer year1_negative_diagnosis.py -- convention
adoptee cette session : un rapport/script deja transmis reste fige, tout
complement va dans un nouveau fichier date.
"""
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
from point_liquidity_rules import CORR_TH
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs

import etape_e_fleet_integration as ei
from engine_multiformat import FORMATS, phase as mk_phase, format_def
from year1_negative_diagnosis import make_flat_ablation, FIRMS

N_SIMS = 600
CEILING = 1000.0
EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK = 1.25, 1.75, 1.75
SEED = 777  # meme seed que le REF@1000$ n=600 deja valide (etape_e_final_comparison.py)

if __name__ == "__main__":
    t_start = time.time()
    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)
    seq = ei.seq_grouped_multi(1000, 15000, 25000, 25000)

    ablation_keys = {}
    for firm in FIRMS:
        fmt_key = ei.CONFIG_REF[firm]
        ablation_key = fmt_key + "__FLAT8_ABLATION_N600"
        FORMATS[ablation_key] = make_flat_ablation(fmt_key)
        ablation_keys[firm] = ablation_key
        if firm == "Fivers":
            ei.FIVERS_PALIER[ablation_key] = ei.FIVERS_PALIER[fmt_key]

    rows = []

    t0 = time.time()
    df = ei.run_propagated(pop, market_data, excluded_map, CEILING, seq, ei.CONFIG_REF, ei.DEFAULT_EMERGENCY,
                            EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE, ei.EXTRA_THRESHOLD_MULT,
                            n_sims=N_SIMS, seed=SEED)
    net = df["final_net_split"] - df["is_paid_cum"]
    rows.append(dict(variant="BASELINE (tout reel)", annee1_neg=(df["year1_net_split"] < 0).mean() * 100,
                      ruine=(net < 0).mean() * 100, profit=net.mean()))
    print(f"[BASELINE] annee1<0={rows[-1]['annee1_neg']:.2f}% ruine={rows[-1]['ruine']:.2f}% "
          f"profit={rows[-1]['profit']:+,.0f}$ ({time.time()-t0:.0f}s)")
    pd.DataFrame(rows).to_csv("year1_negative_diagnosis_n600_results.csv", index=False)

    all_flat_config = {firm: ablation_keys[firm] for firm in FIRMS}
    t0 = time.time()
    df = ei.run_propagated(pop, market_data, excluded_map, CEILING, seq, all_flat_config, ei.DEFAULT_EMERGENCY,
                            EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE, ei.EXTRA_THRESHOLD_MULT,
                            n_sims=N_SIMS, seed=SEED)
    net = df["final_net_split"] - df["is_paid_cum"]
    rows.append(dict(variant="TOUT-FLAT (aucune firm reelle)", annee1_neg=(df["year1_net_split"] < 0).mean() * 100,
                      ruine=(net < 0).mean() * 100, profit=net.mean()))
    print(f"[TOUT-FLAT] annee1<0={rows[-1]['annee1_neg']:.2f}% ruine={rows[-1]['ruine']:.2f}% "
          f"profit={rows[-1]['profit']:+,.0f}$ ({time.time()-t0:.0f}s)")
    pd.DataFrame(rows).to_csv("year1_negative_diagnosis_n600_results.csv", index=False)

    for firm in FIRMS:
        config = dict(ei.CONFIG_REF)
        config[firm] = ablation_keys[firm]
        t0 = time.time()
        df = ei.run_propagated(pop, market_data, excluded_map, CEILING, seq, config, ei.DEFAULT_EMERGENCY,
                                EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE, ei.EXTRA_THRESHOLD_MULT,
                                n_sims=N_SIMS, seed=SEED)
        net = df["final_net_split"] - df["is_paid_cum"]
        rows.append(dict(variant=f"{firm} seule en flat-8% (4 autres reelles)",
                          annee1_neg=(df["year1_net_split"] < 0).mean() * 100,
                          ruine=(net < 0).mean() * 100, profit=net.mean()))
        print(f"[{firm} flat seule] annee1<0={rows[-1]['annee1_neg']:.2f}% ruine={rows[-1]['ruine']:.2f}% "
              f"profit={rows[-1]['profit']:+,.0f}$ ({time.time()-t0:.0f}s)")
        pd.DataFrame(rows).to_csv("year1_negative_diagnosis_n600_results.csv", index=False)

    print(f"\nTermine en {time.time()-t_start:.0f}s.")
