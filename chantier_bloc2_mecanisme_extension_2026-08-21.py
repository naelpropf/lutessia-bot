"""chantier_bloc2_mecanisme_extension_2026-08-21.py

Diagnostic du mecanisme d'extension plafonnee sur bloc2 (demande utilisateur
21/08, suite du diagnostic Piste 2/ADX). Reutilise SANS reinvention :
- analyze_trade (tp_sequence_analysis.py:161) : classification tp1->tp2
  (case), y compris "hors_couverture_historique" si le trade est anterieur
  a la fenetre H1 disponible.
- simulate_trailing / find_tp2_touch (trailing_stop_variants.py:54-128) :
  simulation du trailing APRES le toucher de TP2 (horizon borne
  min(3x delai creation->tp2, 30j)).
- _stop_fn_fixed (chantier_b6_montecarlo_2026-08-19.py:678) + trailing_factor
  B ADOPTE = 0,10 (chantier_gold_silver_configs_2026-08-19.py:47).
- CONTINUATION_CONFIRMED_CASES = {"tp1_avant_tp2","meme_bougie"}
  (chantier_b6_montecarlo_2026-08-19.py:66).

Decouverte PREALABLE a toute decomposition (verifiee empiriquement avant
d'ecrire ce chantier) : le r_trailing DEJA STOCKE dans la population montre
100% des gagnants de bloc1 ET bloc2 avec r_trailing EXACTEMENT egal a
rr_tp1 (0 extension detectee sur 108 trades) contre 49,3%/14,1% sur
bloc3/bloc4 -- signature evidente de l'artefact de couverture bougies deja
trouve 3 fois cette session (ADX, EMA/MACD Piste 2) : bloc1/bloc2 sont
ENTIEREMENT anterieurs au cutoff yfinance (~730j, 2024-07-30), donc
analyze_trade() retournait "hors_couverture_historique" pour CHAQUE trade
de ces 2 blocs au moment ou r_trailing a ete calcule -- pas parce que le
marche ne repart jamais, mais parce qu'aucune bougie n'existait alors pour
le verifier. Ce chantier recalcule le VRAI mecanisme via le backfill MT5
(couverture complete 2022-01-02->2026-08-20)."""
import pandas as pd
import numpy as np
import importlib.util

_spec = importlib.util.spec_from_file_location("tsv", "trailing_stop_variants.py")
tsv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tsv)

_spec2 = importlib.util.spec_from_file_location("tpseq_local", "tp_sequence_analysis.py")
tpseq = importlib.util.module_from_spec(_spec2)
_spec2.loader.exec_module(tpseq)

CONTINUATION_CONFIRMED_CASES = {"tp1_avant_tp2", "meme_bougie"}
TRAILING_FACTOR_B = 0.10
MT5_DIR = "data/mt5_h1_backfill"
TICKER_TO_MT5_FILES = {
    "AUD/JPY": ["AUDJPY.pi"], "AUD/USD": ["AUDUSD.pi"], "CHF/JPY": ["CHFJPY.pi"],
    "EUR/CHF": ["EURCHF.pi"], "EUR/GBP": ["EURGBP.pi"], "EUR/JPY": ["EURJPY.pi"],
    "EUR/USD": ["EURUSD.pi"], "GBP/CHF": ["GBPCHF.pi"], "GBP/JPY": ["GBPJPY.pi"],
    "GBP/USD": ["GBPUSD.pi"], "NZD/USD": ["NZDUSD.pi"], "USD/CAD": ["USDCAD.pi"],
    "USD/CHF": ["USDCHF.pi"], "USD/JPY": ["USDJPY.pi"],
    "DAX40 FULL0926": ["GER30.p", "GER40.p"], "DAX40 PERF INDEX": ["GER30.p", "GER40.p"],
    "NASDAQ100 - MINI NASDAQ100 FULL0926": ["NAS100.p"], "NASDAQ100 INDEX": ["NAS100.p"],
    "S&P500 - MINI S&P500 FULL0926": ["SP500.p"],
}
BLOC_EDGES = pd.to_datetime([
    "2021-04-23 12:43:32", "2022-08-20 17:22:34.250",
    "2023-12-17 22:01:36.500", "2025-04-15 02:40:38.750", "2026-08-12 07:19:41",
])

_cache = {}
def load_candles(ticker):
    if ticker in _cache:
        return _cache[ticker]
    files = TICKER_TO_MT5_FILES[ticker]
    dfs = []
    for f in files:
        d = pd.read_csv(f"{MT5_DIR}/mt5_h1_backfill_{f}_2026-08-21.csv", usecols=["datetime", "open", "high", "low", "close"])
        d["datetime"] = pd.to_datetime(d["datetime"])
        dfs.append(d)
    c = pd.concat(dfs, ignore_index=True).drop_duplicates(subset="datetime").sort_values("datetime").reset_index(drop=True)
    _cache[ticker] = c
    return c


def load_population_with_tp():
    pop = pd.read_csv("chantier_gold_silver_pop_B_config0_tradable_2026-08-19.csv")
    pop["date_creation"] = pd.to_datetime(pop["date_creation"])
    metal_kw = ["GOLD", "SILVER"]
    is_metal = pop["ticker"].str.contains("|".join(metal_kw), case=False, na=False)
    pop = pop[~is_metal].reset_index(drop=True)
    assert len(pop) == 571

    raw = pd.read_csv("historique_lutessia_15k_force.csv")
    raw["date_creation"] = pd.to_datetime(raw["date_creation"], errors="coerce")
    raw = raw.drop_duplicates(subset=["date_creation", "ticker"], keep="first")
    pop = pop.merge(raw[["date_creation", "ticker", "tp1_init", "tp2_init"]],
                     on=["date_creation", "ticker"], how="left")
    assert len(pop) == 571, f"n apres merge tp1/tp2 : {len(pop)}"
    assert pop["tp1_init"].notna().all() and pop["tp2_init"].notna().all()

    bloc = pd.cut(pop["date_creation"], bins=BLOC_EDGES, labels=["bloc1", "bloc2", "bloc3", "bloc4"])
    pop["bloc"] = bloc.astype(str)
    return pop


def recompute_case_and_trailing(pop, trailing_factor=TRAILING_FACTOR_B):
    cases, exit_rs, exit_reasons, peak_rs, tp1_times = [], [], [], [], []
    for _, row in pop.iterrows():
        if row["r_trailing"] <= 0:
            cases.append("perte"); exit_rs.append(row["r_trailing"]); exit_reasons.append(None); peak_rs.append(None); tp1_times.append(None)
            continue
        c = load_candles(row["ticker"])
        res = tpseq.analyze_trade(row, c)
        case = res.get("case", "pas_de_donnees")
        cases.append(case)
        tp1_times.append(res.get("tp1_time"))
        if case in CONTINUATION_CONFIRMED_CASES:
            sim = tsv.simulate_trailing(row, c, _stop_fn(trailing_factor), f"fixed_{trailing_factor}")
            if sim is not None:
                exit_rs.append(sim["exit_r"]); exit_reasons.append(sim["exit_reason"]); peak_rs.append(sim["peak_r"])
            else:
                exit_rs.append(row["rr_tp1"]); exit_reasons.append(None); peak_rs.append(None)
        else:
            exit_rs.append(row["rr_tp1"]); exit_reasons.append(None); peak_rs.append(None)
    pop = pop.copy()
    pop["case_mt5"] = cases
    pop["r_trailing_mt5"] = exit_rs
    pop["exit_reason_mt5"] = exit_reasons
    pop["peak_r_mt5"] = peak_rs
    pop["tp1_time_mt5"] = tp1_times
    return pop


def _stop_fn(param):
    def fn(extreme, entry, risk_distance, atr):
        is_long_direction = extreme >= entry
        return extreme - param * risk_distance if is_long_direction else extreme + param * risk_distance
    return fn


def main():
    pop = load_population_with_tp()
    pop = recompute_case_and_trailing(pop)
    pop.to_csv("chantier_bloc2_mecanisme_extension_signaux_2026-08-21.csv", index=False)

    print(f"{'='*95}\nARTEFACT CONFIRME -- comparaison r_trailing STOCKE vs RECALCULE (MT5), par bloc\n{'='*95}")
    for bl in ("bloc1", "bloc2", "bloc3", "bloc4"):
        sub = pop[(pop["bloc"] == bl) & (pop["r_trailing"] > 0)]
        old_capped = (abs(sub["r_trailing"] - sub["rr_tp1"]) < 1e-6).sum()
        new_capped = (sub["case_mt5"] != "tp1_avant_tp2") & (sub["case_mt5"] != "meme_bougie")
        new_capped_n = new_capped.sum()
        ev_old = sub["r_trailing"].mean()
        ev_new = sub["r_trailing_mt5"].mean()
        print(f"  {bl}: n_gagnants={len(sub)} | capped AVANT (stocke)={old_capped}/{len(sub)} "
              f"({old_capped/len(sub)*100:.1f}%) -> capped APRES (MT5)={new_capped_n}/{len(sub)} "
              f"({new_capped_n/len(sub)*100:.1f}%) | EV gagnants stocke={ev_old:+.3f}R recalcule={ev_new:+.3f}R")

    print(f"\n{'='*95}\nA -- taux de declenchement (i) et taux de reussite conditionnel (ii), bloc2 vs bloc3\n{'='*95}")
    for bl in ("bloc2", "bloc3"):
        sub = pop[(pop["bloc"] == bl) & (pop["r_trailing"] > 0)]
        n_tp1 = len(sub)
        declenche = sub[sub["case_mt5"].isin(["tp1_avant_tp2", "meme_bougie"])]
        non_declenche = sub[sub["case_mt5"] == "tp2_non_atteint_dans_fenetre"]
        autres = sub[~sub["case_mt5"].isin(["tp1_avant_tp2", "meme_bougie", "tp2_non_atteint_dans_fenetre"])]
        print(f"\n-- {bl} (n gagnants TP1 = {n_tp1}) --")
        print(f"  (i) declenchement : {len(declenche)}/{n_tp1} ({len(declenche)/n_tp1*100:.1f}%) atteignent tp2_init "
              f"| {len(non_declenche)}/{n_tp1} ({len(non_declenche)/n_tp1*100:.1f}%) n'atteignent jamais tp2_init "
              f"| {len(autres)} autres cas ({sorted(autres['case_mt5'].unique().tolist())})")
        if len(declenche):
            reussite_forte = (declenche["r_trailing_mt5"] >= declenche["rr_tp2"] * 0.7)
            stop_reason = (declenche["exit_reason_mt5"] == "stop").sum()
            horizon_reason = (declenche["exit_reason_mt5"] == "horizon").sum()
            print(f"  (ii) reussite conditionnelle (sur les {len(declenche)} qui declenchent) : "
                  f"r_trailing_mt5 median={declenche['r_trailing_mt5'].median():.3f}R vs rr_tp2 median={declenche['rr_tp2'].median():.3f}R | "
                  f">=70% de rr_tp2 capture : {reussite_forte.sum()}/{len(declenche)} ({reussite_forte.mean()*100:.1f}%) | "
                  f"exit_reason: stop={stop_reason} horizon={horizon_reason}")

    print(f"\n{'='*95}\nC -- sensibilite trailing_factor sur bloc2 (observation uniquement)\n{'='*95}")
    b2 = pop[(pop["bloc"] == "bloc2") & (pop["r_trailing"] > 0)]
    declenche_b2 = b2[b2["case_mt5"].isin(["tp1_avant_tp2", "meme_bougie"])]
    for tf in (0.05, 0.10, 0.15, 0.20):
        exit_rs = []
        for _, row in declenche_b2.iterrows():
            c = load_candles(row["ticker"])
            sim = tsv.simulate_trailing(row, c, _stop_fn(tf), f"fixed_{tf}")
            exit_rs.append(sim["exit_r"] if sim is not None else row["rr_tp1"])
        exit_rs = pd.Series(exit_rs)
        reussite_forte = (exit_rs >= declenche_b2["rr_tp2"].values * 0.7).mean() * 100
        print(f"  trailing_factor={tf:.2f} : EV(declenches)={exit_rs.mean():+.3f}R median={exit_rs.median():+.3f}R "
              f">=70%rr_tp2={reussite_forte:.1f}%")


if __name__ == "__main__":
    main()
