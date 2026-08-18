"""
CHANTIER instant funding -- suite GFT Instant (08/15/16), exploration
elargie. Compte isole, tresorerie infinie (meme convention que le premier
chantier), pas de cascade flotte -- viendra une fois qu'un candidat emerge.
Reference : GFT classique (+253 738$/4ans, 2935$ cash) et GFT Instant
Strategie A standard (+250 085$/4ans, 28 478$ cash, 57,4 casses/4ans),
deja etablis (chantier_instant_funding_phase2_2026-08-15.py).

SECTION A : Strategie B (bande contrarian rr_tp1 in [0.75, MIN_RR_T1))
sur GFT Instant, meme risque standard (pas d'optimisation separee du
risque, cf. chantier dual-trader). Sweep de risque dedie SEULEMENT si le
verdict de base est defavorable.

SECTION B : leviers structurels sur GFT Instant, population standard
(rr_tp1>=1.35) sauf B1 :
  B1 -- RR releve (1.75/2.0/2.25)
  B2 -- plafond de positions reduit (1 ou 2, via monkeypatch eng.MAX_POSITIONS)
  B3 -- exclusion de paires -- daily_dd_pair_ranking.csv verifie et ECARTE
        (donnee perimee pre-RR1.35, metrique JOINT-paire pas single-ticker,
        91 combos dont seulement 17 non-nuls et tous <=1% de DD -- signal
        trop faible et hors-sujet pour fonder une exclusion). SUBSTITUE
        par un ranking EV/ticker sur la population ACTUELLE (rr_tp1>=1.35,
        631 trades) -- proxy plus pertinent et a jour, signale explicitement
        comme une substitution, pas la donnee demandee telle quelle.
  B4 -- combinaison des leviers individuels les plus prometteurs
"""
import random
import sys
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from engine_multiformat import FORMATS
from corrected_scaling_mechanism import BASE_PALIER

import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("_phase2", "chantier_instant_funding_phase2_2026-08-15.py")
_phase2 = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_phase2)
run_one_account = _phase2.run_one_account

DAY_SECONDS = 86400
YEAR_SECONDS = 365.25 * DAY_SECONDS
MONTH_SECONDS = DAYS_PER_MONTH * DAY_SECONDS
SIM_YEARS = 4
MIN_RR_T1 = 1.35
CONTRARIAN_BAND_LOW = 0.75
CORR_TH = 0.80
FLEET_RISK = 1.90
GFT_INSTANT_PRICE = 488.0
GFT_PALIER = BASE_PALIER["GFT"]
GFT_INSTANT_FMT = FORMATS["GFT_InstantGOAT"]

REF_CLASSIC = dict(profit_mean=253738.0, cash_paid_mean=2935.0, n_breaks_mean=9.19)
REF_INSTANT_A = dict(profit_mean=250085.0, cash_paid_mean=28478.0, n_breaks_mean=57.36)

WEAK_TICKERS = ["EUR/GBP", "USD/CAD", "EUR/CHF"]  # cf. note methodologique B3


def build_pop_and_excluded(min_rr, exclude_tickers=None):
    pop = build_population_with_trailing("fixed", 0.15, min_rr=min_rr, verbose=False)
    if exclude_tickers:
        pop = pop[~pop["ticker"].isin(exclude_tickers)].copy()
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)
    return pop, market_data, excluded_map


def run_variant(pop, market_data, excluded_map, n_sims, risk_funded=FLEET_RISK, max_positions=None, seed=9999):
    orig_max = eng.MAX_POSITIONS
    if max_positions is not None:
        eng.MAX_POSITIONS = max_positions
    try:
        rng_boot = random.Random(seed + 1)
        results = []
        for _ in range(n_sims):
            trades, slot_arrivals = eng.build_flexible_population(pop, None, 1.0, False, random.Random(rng_boot.random()))
            block_seconds = 2 * 30 * DAY_SECONDS
            blocks = build_blocks(trades, slot_arrivals, block_seconds)
            raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot,
                                                                          SIM_YEARS * YEAR_SECONDS)
            order = list(range(len(raw_trades)))
            results.append(run_one_account(raw_trades, raw_slots, market_data, excluded_map, order,
                                            GFT_INSTANT_FMT, GFT_PALIER, GFT_EVAL_RISK_UNUSED, GFT_INSTANT_PRICE,
                                            funded_from_start=True, risk_funded=risk_funded))
        return pd.DataFrame(results)
    finally:
        eng.MAX_POSITIONS = orig_max


GFT_EVAL_RISK_UNUSED = 1.75  # jamais utilise (funded_from_start=True), garde pour signature


def summarize(df, label):
    return dict(config=label, n=len(df), profit_mean=df["net_profit"].mean(),
                profit_median=df["net_profit"].median(), cash_paid_mean=df["cash_paid"].mean(),
                cash_paid_p95=df["cash_paid"].quantile(0.95), n_breaks_mean=df["n_breaks"].mean())


def report(row):
    d_profit = row["profit_mean"] - REF_CLASSIC["profit_mean"]
    print(f"[{row['config']:38s}] profit_moy={row['profit_mean']:+,.0f}$ (vs classique {d_profit:+,.0f}$) "
          f"profit_med={row['profit_median']:+,.0f}$ cash_moy={row['cash_paid_mean']:,.0f}$ "
          f"cash_p95={row['cash_paid_p95']:,.0f}$ casses_moy={row['n_breaks_mean']:.2f}")


def main():
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    t_start = time.time()
    all_rows = []

    # reference deja connues (rappel, pas recalculees)
    all_rows.append(dict(config="REF_classique_GFT_2Step", n=n_sims, **REF_CLASSIC, cash_paid_p95=float("nan")))
    all_rows.append(dict(config="A_standard_deja_connu", n=n_sims, **REF_INSTANT_A, cash_paid_p95=34184.0))

    print("=" * 70)
    print("SECTION A -- Strategie B (bande contrarian) sur GFT Instant")
    print("=" * 70)
    pop_contrarian, market_data, excluded_map = build_pop_and_excluded(CONTRARIAN_BAND_LOW)
    pop_contrarian = pop_contrarian[(pop_contrarian["rr_tp1"] >= CONTRARIAN_BAND_LOW) &
                                     (pop_contrarian["rr_tp1"] < MIN_RR_T1)].reset_index(drop=True)
    print(f"[verif] population contrarian (0.75<=rr_tp1<{MIN_RR_T1}) : {len(pop_contrarian)} trades")
    df_a = run_variant(pop_contrarian, market_data, excluded_map, n_sims)
    row_a = summarize(df_a, "A_StrategieB_risque_standard")
    all_rows.append(row_a)
    report(row_a)

    if row_a["profit_mean"] <= REF_CLASSIC["profit_mean"]:
        print("\n  Verdict de base defavorable -> sweep de risque dedie Strategie B sur GFT Instant :")
        for risk in (0.75, 1.00, 1.25, 1.50, 1.90):
            df_sweep = run_variant(pop_contrarian, market_data, excluded_map, n_sims, risk_funded=risk)
            row = summarize(df_sweep, f"A_StrategieB_risque_{risk:.2f}")
            all_rows.append(row)
            report(row)

    print("\n" + "=" * 70)
    print("SECTION B1 -- RR releve specifiquement pour GFT Instant")
    print("=" * 70)
    for min_rr in (1.75, 2.00, 2.25):
        pop_rr, market_data, excluded_map = build_pop_and_excluded(min_rr)
        print(f"[verif] population RR>={min_rr} : {len(pop_rr)} trades")
        df_rr = run_variant(pop_rr, market_data, excluded_map, n_sims)
        row = summarize(df_rr, f"B1_RR_{min_rr:.2f}")
        all_rows.append(row)
        report(row)

    print("\n" + "=" * 70)
    print("SECTION B2 -- plafond de positions reduit pour GFT Instant")
    print("=" * 70)
    pop_std, market_data, excluded_map = build_pop_and_excluded(MIN_RR_T1)
    for max_pos in (1, 2):
        df_cap = run_variant(pop_std, market_data, excluded_map, n_sims, max_positions=max_pos)
        row = summarize(df_cap, f"B2_cap_{max_pos}")
        all_rows.append(row)
        report(row)

    print("\n" + "=" * 70)
    print("SECTION B3 -- exclusion de paires (substitution methodologique, voir docstring)")
    print("=" * 70)
    g = pop_std.groupby("ticker")["r_trailing"].mean().sort_values()
    print("Classement EV/ticker (population actuelle, remplace daily_dd_pair_ranking.csv "
          "perime/hors-sujet -- voir note methodologique) :")
    print(g.to_string())
    for excl in (["EUR/GBP"], ["EUR/GBP", "USD/CAD"], ["EUR/GBP", "USD/CAD", "EUR/CHF"]):
        pop_excl, market_data, excluded_map = build_pop_and_excluded(MIN_RR_T1, exclude_tickers=excl)
        df_excl = run_variant(pop_excl, market_data, excluded_map, n_sims)
        row = summarize(df_excl, f"B3_exclu_{'+'.join(t.replace('/','') for t in excl)}")
        all_rows.append(row)
        report(row)

    print("\n" + "=" * 70)
    print("SECTION B4 -- combinaison des 2 MEILLEURS leviers individuels (toutes categories)")
    print("=" * 70)
    b_rows = [r for r in all_rows if r["config"].startswith(("B1_", "B2_", "B3_"))]
    top2 = sorted(b_rows, key=lambda r: -r["profit_mean"])[:2]
    print("2 meilleurs leviers individuels (toutes categories confondues, pas 1 par categorie) :")
    for r in top2:
        print(f"  {r['config']:30s} profit_moy={r['profit_mean']:+,.0f}$")

    def parse_lever(cfg):
        if cfg.startswith("B1_RR_"):
            return dict(min_rr=float(cfg.split("_")[-1]))
        if cfg.startswith("B2_cap_"):
            return dict(max_positions=int(cfg.split("_")[-1]))
        if cfg.startswith("B3_exclu_"):
            tag = cfg.split("_", 2)[-1]
            return dict(exclude=[t[:3] + "/" + t[3:] for t in tag.split("+")])
        raise ValueError(cfg)

    combo_kwargs = {}
    for r in top2:
        combo_kwargs.update(parse_lever(r["config"]))
    min_rr = combo_kwargs.get("min_rr", MIN_RR_T1)
    max_positions = combo_kwargs.get("max_positions")
    exclude = combo_kwargs.get("exclude")

    pop_combo, market_data, excluded_map = build_pop_and_excluded(min_rr, exclude_tickers=exclude)
    df_combo = run_variant(pop_combo, market_data, excluded_map, n_sims, max_positions=max_positions)
    label = "B4_" + "+".join(r["config"] for r in top2)
    row_combo = summarize(df_combo, label[:60])
    all_rows.append(row_combo)
    report(row_combo)

    pd.DataFrame(all_rows).to_csv(f"chantier_gft_instant_exploration_n{n_sims}.csv", index=False)
    print(f"\nTermine en {time.time()-t_start:.0f}s.")


if __name__ == "__main__":
    main()
