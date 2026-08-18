"""
Diagnostic demande : isoler la cause de la hausse de P(annee1<0) sous REF
(5,50%/4,00% ancien moteur flat-8% -> 27,5%/26,5% nouveau moteur multi-
phase). Deux hypotheses :
  (a) effet reel des vraies cibles par phase (ex. FTMO/Blueberry P1=10%
      reel vs 8% suppose avant), qui compound la difficulte (echouer en
      P2 renvoie repayer TOUT le challenge, P1 inclus -- jamais possible
      dans l'ancien moteur 1-phase)
  (b) un bug d'integration (transition de phase, comptage de jours min,
      reset de compteur)

Point (b) : audite par citation de code dans le rapport (engine_multiformat.
process_trade_mf, etape_e_fleet_integration.py) -- rien trouve d'anormal
dans la logique de transition/reset/comptage de jours.

Point (a) : teste ici empiriquement par ABLATION -- pour chaque firm, on
remplace SEULEMENT sa structure de phases/cible par l'ancienne cible flat
(8%, 1 phase, 4 jours min), EN GARDANT son vrai DD (journalier/max/mode)
inchange, pendant que les 4 autres firms restent sur leur vrai format REF.
Isole PUREMENT l'effet cible/nombre-de-phases, sans melanger avec l'effet
DD (deja traite separement par le re-balayage de risque).
"""
import copy
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
from point_liquidity_rules import CORR_TH
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs

import etape_e_fleet_integration as ei
from engine_multiformat import FORMATS, phase as mk_phase, format_def

N_SIMS = 300
CEILING = 1000.0
EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK = 1.25, 1.75, 1.75

FIRMS = ["FTMO", "Fivers", "Blueberry", "GFT", "FundedNext"]


def make_flat_ablation(fmt_key):
    """Remplace la structure de phases du format REF de cette firm par
    l'ancienne cible flat (8%, 1 phase, 4 jours min), en conservant le DD
    (journalier/max/mode) de la phase 1 reelle."""
    real = FORMATS[fmt_key]
    p1 = real["phases"][0] if real["phases"] else real["funded"]
    flat_phase = mk_phase(8.0, 4, p1["dd_daily_pct"], p1["dd_max_pct"], p1["dd_max_mode"])
    return format_def(real["firm"], real["format_name"] + " (ablation flat-8%)",
                       phases=[flat_phase], funded=flat_phase, price=real["price"],
                       copytrade_cap=real["copytrade_cap"], copytrade_confirmed=real["copytrade_confirmed"],
                       max_accounts=real["max_accounts"], confidence_notes="ablation diagnostique, pas un format reel")


if __name__ == "__main__":
    t_start = time.time()
    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)
    seq = ei.seq_grouped_multi(1000, 15000, 25000, 25000)

    # Monkeypatch temporaire du registre FORMATS pour les cles d'ablation --
    # n'ecrit jamais dans engine_multiformat.py, juste dans le dict en
    # memoire au sein de ce process.
    ablation_keys = {}
    for firm in FIRMS:
        fmt_key = ei.CONFIG_REF[firm]
        ablation_key = fmt_key + "__FLAT8_ABLATION"
        FORMATS[ablation_key] = make_flat_ablation(fmt_key)
        ablation_keys[firm] = ablation_key
        if firm == "Fivers":
            ei.FIVERS_PALIER[ablation_key] = ei.FIVERS_PALIER[fmt_key]

    rows = []

    # Baseline : REF tel quel (deja connu, reconfirme ici au meme n pour comparaison directe)
    t0 = time.time()
    df = ei.run_propagated(pop, market_data, excluded_map, CEILING, seq, ei.CONFIG_REF, ei.DEFAULT_EMERGENCY,
                            EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE, ei.EXTRA_THRESHOLD_MULT,
                            n_sims=N_SIMS, seed=555)
    net = df["final_net_split"] - df["is_paid_cum"]
    rows.append(dict(variant="BASELINE (tout reel)", annee1_neg=(df["year1_net_split"] < 0).mean() * 100,
                      ruine=(net < 0).mean() * 100, profit=net.mean()))
    print(f"[BASELINE] annee1<0={rows[-1]['annee1_neg']:.2f}% ruine={rows[-1]['ruine']:.2f}% "
          f"profit={rows[-1]['profit']:+,.0f}$ ({time.time()-t0:.0f}s)")

    # Tout-flat : toutes les firms sur l'ancienne cible flat (reproduit
    # l'esprit de l'ancien moteur, sauf DD deja differencie par firm)
    all_flat_config = {firm: ablation_keys[firm] for firm in FIRMS}
    t0 = time.time()
    df = ei.run_propagated(pop, market_data, excluded_map, CEILING, seq, all_flat_config, ei.DEFAULT_EMERGENCY,
                            EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE, ei.EXTRA_THRESHOLD_MULT,
                            n_sims=N_SIMS, seed=555)
    net = df["final_net_split"] - df["is_paid_cum"]
    rows.append(dict(variant="TOUT-FLAT (aucune firm reelle)", annee1_neg=(df["year1_net_split"] < 0).mean() * 100,
                      ruine=(net < 0).mean() * 100, profit=net.mean()))
    print(f"[TOUT-FLAT] annee1<0={rows[-1]['annee1_neg']:.2f}% ruine={rows[-1]['ruine']:.2f}% "
          f"profit={rows[-1]['profit']:+,.0f}$ ({time.time()-t0:.0f}s)")

    # Ablation par firm : une seule firm repasse en flat-8%, les 4 autres reelles
    for firm in FIRMS:
        config = dict(ei.CONFIG_REF)
        config[firm] = ablation_keys[firm]
        t0 = time.time()
        df = ei.run_propagated(pop, market_data, excluded_map, CEILING, seq, config, ei.DEFAULT_EMERGENCY,
                                EVAL_RISK, FLEET_RISK, GFT_EVAL_RISK, ei.FINAL_RESERVE_SHARE, ei.EXTRA_THRESHOLD_MULT,
                                n_sims=N_SIMS, seed=555)
        net = df["final_net_split"] - df["is_paid_cum"]
        rows.append(dict(variant=f"{firm} seule en flat-8% (4 autres reelles)",
                          annee1_neg=(df["year1_net_split"] < 0).mean() * 100,
                          ruine=(net < 0).mean() * 100, profit=net.mean()))
        print(f"[{firm} flat seule] annee1<0={rows[-1]['annee1_neg']:.2f}% ruine={rows[-1]['ruine']:.2f}% "
              f"profit={rows[-1]['profit']:+,.0f}$ ({time.time()-t0:.0f}s)")
        pd.DataFrame(rows).to_csv("year1_negative_diagnosis_results.csv", index=False)

    pd.DataFrame(rows).to_csv("year1_negative_diagnosis_results.csv", index=False)
    print(f"\nTermine en {time.time()-t_start:.0f}s.")
