"""
Etape C CORRIGEE (08/09 soir) : re-run de etape_c_solo_comparison.py (08/08)
sous la config de risque et les paliers REELS du moteur de production
actuel, pour nourrir un ratio EV/$ par firm/format -- prealable au chantier
fongibilite des slots (la fonction de priorite inter-firm est le vrai
inconnu identifie dans le scoping du 08/09, cf. registre section 2.6bis /
memoire project_slot_fungibility_scoping_2026-08-09).

===========================================================================
CORRECTIONS APPLIQUEES (verifiees par lecture de code, pas supposees) :
===========================================================================
1. RISQUE -- l'original utilisait EVAL_RISK=2,25%/FUNDED_RISK=2,75%
   uniformement pour toutes les firms (etape_c_solo_comparison.py:31-32).
   Le script de PRODUCTION qui a genere la reference n=600 confirmee
   (4 827 736$/4 892 588$, cascade GO -- etape_e_final_lock_bbreset_
   2026-08-09.py:368) utilise EVAL_RISK=1,25%/FLEET_RISK=1,90%/
   GFT_EVAL_RISK=1,75% (differencie par firm, PAS uniforme -- l'original
   appliquait le meme risque eval a GFT qu'aux autres). Corrige ici avec le
   meme risque eval differencie par firm que la production.
2. PALIER -- DEFAULT_PALIER_BY_FIRM de l'original testait FTMO et GFT a
   100 000$ (etape_c_solo_comparison.py:38-39). Le vrai palier de
   production (BASE_PALIER, corrected_scaling_mechanism.py:56, confirme
   empiriquement lors du bootstrap parallele du 08/09) est 50 000$ pour les
   deux. Corrige. Blueberry (25 000$) et FundedNext (200 000$) etaient deja
   corrects, verifie contre BASE_PALIER/FUNDEDNEXT_PALIER -- inchanges.
3. PALIER FIVERS HYPERGROWTH -- ecart supplementaire trouve en verifiant
   "les autres" comme demande : DEFAULT_PALIER_BY_FIRM["The5%ers"]=100 000$
   n'est PAS dans la grille de prix de Fivers_HyperGrowth (price={10000,
   20000,40000}), donc l'original RETOMBAIT sur le plus petit palier connu
   (10 000$, palier_and_cost() ligne 55) au lieu du vrai palier de
   production (FIVERS_PALIER["Fivers_HyperGrowth"]=40 000$,
   etape_e_fleet_integration.py:127). Corrige via un override explicite
   (meme mecanisme que le PALIER_OVERRIDE deja utilise pour FundedNext
   Stellar Instant dans l'original). Fivers_HighStakes (100 000$) etait
   deja correct (seul prix connu de ce format, resolu correctement par
   l'original) -- inchange.

===========================================================================
RATIO EV/$ -- formule et definition exacte
===========================================================================
Pour chaque compte simule sur l'horizon complet (~4 ans, meme population et
meme bootstrap-par-blocs que l'original) :
  cost_to_fund          = cout cumule paye JUSQU'AU premier financement
                           (echecs eval inclus), deja mesure dans l'original.
  profit_apres_financement = total_funded_pnl (gain net finance cumule sur
                           TOUT l'horizon, y compris apres une eventuelle
                           casse+relance post-financement) MOINS les frais
                           payes APRES le premier financement (relances
                           post-casse) -- pour ne pas compter deux fois le
                           cout d'entree deja capture dans cost_to_fund.
Puis, par format (moyenne sur les sims OU le compte a ete finance) :
  EV/$ = P(finance) x moyenne(profit_apres_financement | finance)
              / moyenne(cost_to_fund | finance)
P(finance) pondere le ratio par le risque de ne jamais etre finance du tout
(sinon un format qui finance rarement mais tres profitablement une fois
finance semblerait artificiellement bon).

N'importe pas ce script directement (convention du projet).
"""
import random
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs
from real_cash_risk_year1_block_bootstrap import build_blocks
from reference_metrics_final import build_full_block_bootstrap_sequence

from engine_multiformat import FORMATS, make_acc_mf, process_trade_mf
import etape_e_fleet_integration as ei

DAY_SECONDS = 86400
BLOCK_MONTHS = 2
EVAL_RISK = 1.25          # etait 2,25 -- aligne sur ei.EVAL_RISK de production (etape_e_final_lock_bbreset:368)
FUNDED_RISK = 1.90         # etait 2,75 -- aligne sur ei.FLEET_RISK de production
GFT_EVAL_RISK = 1.75       # NOUVEAU -- l'original n'avait pas de risque eval differencie pour GFT
N_SIMS = 300
SEED = 42

# Palier de reference par format : prix connu si disponible, sinon taille
# typique deja utilisee ailleurs dans le projet pour cette firm.
# FTMO/GFT corriges 100000->50000 (BASE_PALIER reel de production).
DEFAULT_PALIER_BY_FIRM = {"FTMO": 50000, "The5%ers": 100000, "Blueberry": 25000,
                          "GFT": 50000, "FundedNext": 200000}

# Overrides : formats dont le palier reel/pertinent differe du defaut de la
# firm (ex. FundedNext Stellar Instant plafonne a 20k$, pas 200k$).
# Fivers_HyperGrowth AJOUTE (40000, palier reel de production
# FIVERS_PALIER -- l'original retombait sur 10000 par defaut de grille).
PALIER_OVERRIDE = {"FundedNext_StellarInstant": 20000, "Fivers_HyperGrowth": 40000}

CONFIG_REF_FORMATS = set(ei.CONFIG_REF.values())


def palier_and_cost(fmt_key):
    fmt = FORMATS[fmt_key]
    known_prices = {p: c for p, c in fmt["price"].items() if c is not None}
    if fmt_key in PALIER_OVERRIDE:
        palier = PALIER_OVERRIDE[fmt_key]
        return palier, known_prices.get(palier)
    if not known_prices:
        return DEFAULT_PALIER_BY_FIRM[fmt["firm"]], None  # cout inconnu
    preferred = DEFAULT_PALIER_BY_FIRM[fmt["firm"]]
    palier = preferred if preferred in known_prices else sorted(known_prices.keys())[0]
    return palier, known_prices[palier]


def eval_risk_for(firm):
    return GFT_EVAL_RISK if firm == "GFT" else EVAL_RISK


def run_format_solo(fmt_key, palier, cost, blocks, block_seconds, target_duration, market_data, excluded_map,
                     n_sims, seed):
    fmt = FORMATS[fmt_key]
    cost_val = cost if cost is not None else 0.0
    eval_r = eval_risk_for(fmt["firm"])
    rng_boot = random.Random(seed)
    results = []
    for sim in range(n_sims):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot, target_duration)

        acc = make_acc_mf(fmt, palier, cost=cost_val, active=True)
        state = {"reserve": 10_000_000.0, "total_breaks": 0, "ever_funded": False, "real_cash_paid": 0.0}
        first_funded_time = 0.0 if not fmt["phases"] else None
        if not fmt["phases"]:
            state["ever_funded"] = True
        cost_at_funding = cost_val if not fmt["phases"] else None
        post_fund_breaks = 0
        was_ever_funded_flag = not fmt["phases"]

        for trade, now in zip(raw_trades, raw_slots):
            was_funded_before = acc["phase"] == "funded"
            breaks_before = state["total_breaks"]
            just_funded = process_trade_mf(acc, trade, now, fmt, state, eval_r if not was_funded_before else FUNDED_RISK,
                                            market_data, excluded_map, cost_override=cost_val)
            if just_funded and first_funded_time is None:
                first_funded_time = now
                cost_at_funding = acc["total_fees_paid"]
            if was_ever_funded_flag and was_funded_before and state["total_breaks"] > breaks_before:
                post_fund_breaks += 1
            if just_funded:
                was_ever_funded_flag = True

        funded = first_funded_time is not None
        profit_after_funding = None
        if funded:
            fees_after_funding = acc["total_fees_paid"] - cost_at_funding
            profit_after_funding = acc["total_funded_pnl"] - fees_after_funding

        results.append(dict(sim=sim, funded=funded,
                             days_to_fund=(first_funded_time / DAY_SECONDS) if funded else None,
                             cost_to_fund=cost_at_funding if fmt["phases"] else cost_val,
                             breaks_total=state["total_breaks"], post_fund_breaks=post_fund_breaks,
                             profit_after_funding=profit_after_funding))
    return pd.DataFrame(results)


def main():
    t0 = time.time()
    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, eng.CORR_THRESHOLD)

    base_trades, base_slots = eng.build_flexible_population(pop, None, 1.0, False, random.Random(123))
    block_seconds = BLOCK_MONTHS * 30 * DAY_SECONDS
    blocks = build_blocks(base_trades, base_slots, block_seconds)
    target_duration = base_slots[-1]

    print(f"Population : {len(base_trades)} trades, horizon simule {target_duration/DAY_SECONDS:.0f}j, n={N_SIMS}/format.\n")

    rows = []
    for fmt_key, fmt in FORMATS.items():
        palier, cost = palier_and_cost(fmt_key)
        df = run_format_solo(fmt_key, palier, cost, blocks, block_seconds, target_duration, market_data, excluded_map,
                              n_sims=N_SIMS, seed=SEED)

        n_phases = len(fmt["phases"])
        dd_mode = fmt["phases"][0]["dd_max_mode"] if fmt["phases"] else fmt["funded"]["dd_max_mode"]
        pass_rate = df["funded"].mean() * 100
        p_funded = df["funded"].mean()
        mean_days = df.loc[df["funded"], "days_to_fund"].mean() if df["funded"].any() else float("nan")
        mean_cost = df.loc[df["funded"], "cost_to_fund"].mean() if df["funded"].any() else float("nan")
        mean_breaks = df["breaks_total"].mean()
        mean_post_breaks = df.loc[df["funded"], "post_fund_breaks"].mean() if df["funded"].any() else float("nan")
        mean_profit_after = df.loc[df["funded"], "profit_after_funding"].mean() if df["funded"].any() else float("nan")
        ev_per_dollar = (p_funded * mean_profit_after / mean_cost
                          if (df["funded"].any() and mean_cost and mean_cost > 0) else float("nan"))

        rows.append(dict(firm=fmt["firm"], format=fmt_key, n_phases=n_phases, dd_mode=dd_mode,
                          palier=palier, cost_connu=cost is not None,
                          pass_rate_pct=pass_rate, mean_days_to_fund=mean_days,
                          mean_cost_to_fund=mean_cost, mean_breaks_pre_fund=mean_breaks,
                          mean_breaks_post_fund=mean_post_breaks,
                          mean_profit_after_funding=mean_profit_after, ev_per_dollar=ev_per_dollar,
                          is_config_ref=fmt_key in CONFIG_REF_FORMATS,
                          copytrade_confirmed=fmt["copytrade_confirmed"]))
        print(f"[{fmt['firm']:10s}] {fmt_key:28s} palier={palier:>7,} phases={n_phases} dd={dd_mode:14s} "
              f"passage={pass_rate:5.1f}% delai={mean_days:6.1f}j cout_moy={mean_cost if mean_cost==mean_cost else float('nan'):>8.0f}$ "
              f"casse_post={mean_post_breaks:5.2f} EV/$={ev_per_dollar:7.2f} ({time.time()-t0:.0f}s ecoules)")

    out = pd.DataFrame(rows)
    out.to_csv("etape_c_solo_comparison_corrige_results.csv", index=False)
    print(f"\nTermine en {time.time()-t0:.0f}s. Resultats -> etape_c_solo_comparison_corrige_results.csv")

    print("\n=== Classement des 5 firms selon leur format REF actuel (EV/$) ===")
    ref_rows = out[out["is_config_ref"]].sort_values("ev_per_dollar", ascending=False)
    for _, r in ref_rows.iterrows():
        print(f"  {r['firm']:10s} {r['format']:26s} EV/$={r['ev_per_dollar']:7.2f} "
              f"passage={r['pass_rate_pct']:5.1f}% delai={r['mean_days_to_fund']:6.1f}j cout={r['mean_cost_to_fund']:>7.0f}$")


if __name__ == "__main__":
    main()
