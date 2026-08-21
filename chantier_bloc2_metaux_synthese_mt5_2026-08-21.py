"""chantier_bloc2_metaux_synthese_mt5_2026-08-21.py

Reapplique la logique de synthese par taux croise (gold_silver_yahoo_mapping_
2026-08-19.py : jambe USD x jambe FX) avec les legs MT5 deja backfilles
(au lieu des legs Yahoo) pour GOLD-GBP/EUR/AUD et SILVER-AUD/EUR -- decision
utilisateur du 21/08. Reduit le trou de couverture de 2021-04->2023-01
(21 mois) a 2021-04->2022-01 (~9 mois residuels, limite de la jambe FX MT5
elle-meme). Palladium reste sans solution avant 2023-01-19 (pas de cross a
synthetiser, ticker direct introuvable partout).

Etape A : construit les bougies (reel MT5 quand disponible >=2023-01-19,
synthetique USD x FX sinon) + VALIDE la synthese sur la fenetre de
recouvrement (2023-01-19->2026-08-20, ou reel ET synthetique existent tous
les deux) avant de faire confiance a la synthese sur la fenetre non
couverte.

Etape B/C/D : quantifie l'exposition residuelle par ticker/bloc, recalcule
r_trailing avec la meilleure donnee disponible (garde-fou hors_couverture_
historique applique explicitement sur ce qui reste non resolu), et
re-teste bloc1/bloc2 sur B_tradable."""
import re

import numpy as np
import pandas as pd
import importlib.util

_spec = importlib.util.spec_from_file_location("tpseq_local", "tp_sequence_analysis.py")
tpseq = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tpseq)

_spec_tsv = importlib.util.spec_from_file_location("tsv_local", "trailing_stop_variants.py")
tsv = importlib.util.module_from_spec(_spec_tsv)
_spec_tsv.loader.exec_module(tsv)

MT5_DIR = "data/mt5_h1_backfill"
DATE_TAG = "2026-08-21"

USD_LEG_SYMBOL = {"GOLD": "XAUUSD.pi", "SILVER": "XAGUSD.pi"}
FX_LEG = {  # (symbole MT5, "divide"/"multiply") -- meme convention que gold_silver_yahoo_mapping
    "EUR": ("EURUSD.pi", "divide"),
    "GBP": ("GBPUSD.pi", "divide"),
    "AUD": ("AUDUSD.pi", "divide"),
}
REAL_CROSS_SYMBOL = {
    ("GOLD", "GBP"): "XAUGBP.pi", ("GOLD", "EUR"): "XAUEUR.pi", ("GOLD", "AUD"): "XAUAUD.pi",
    ("SILVER", "AUD"): "XAGAUD.pi", ("SILVER", "EUR"): "XAGEUR.pi",
}
DIRECT_SYMBOL = {"GOLD - USD": "XAUUSD.pi", "SILVER - USD": "XAGUSD.pi",
                 "PALLADIUM": "XPDUSD.pi", "PLATINUM": "XPTUSD.pi"}

TICKER_RE = re.compile(r"^(GOLD|SILVER) - (USD|EUR|GBP|CHF|CAD|AUD|NZD)$")


def _load_raw(symbol):
    path = f"{MT5_DIR}/mt5_h1_backfill_{symbol}_{DATE_TAG}.csv"
    d = pd.read_csv(path, usecols=["datetime", "open", "high", "low", "close"])
    d["datetime"] = pd.to_datetime(d["datetime"])
    return d.sort_values("datetime").reset_index(drop=True)


_cache = {}


def build_synthetic(metal, ccy):
    key = (metal, ccy, "synth")
    if key in _cache:
        return _cache[key]
    usd = _load_raw(USD_LEG_SYMBOL[metal])
    fx_symbol, op = FX_LEG[ccy]
    fx = _load_raw(fx_symbol)
    merged = pd.merge(usd, fx, on="datetime", suffixes=("_usd", "_fx"), how="inner")
    for col in ["open", "high", "low", "close"]:
        merged[col] = merged[f"{col}_usd"] / merged[f"{col}_fx"] if op == "divide" else merged[f"{col}_usd"] * merged[f"{col}_fx"]
    out = merged[["datetime", "open", "high", "low", "close"]].sort_values("datetime").reset_index(drop=True)
    _cache[key] = out
    return out


def validate_synthesis():
    print(f"{'='*95}\nETAPE A -- validation synthese MT5 sur fenetre de recouvrement (reel vs synthetique)\n{'='*95}")
    for (metal, ccy), real_symbol in REAL_CROSS_SYMBOL.items():
        real = _load_raw(real_symbol)
        synth = build_synthetic(metal, ccy)
        m = pd.merge(real, synth, on="datetime", suffixes=("_real", "_synth"))
        if m.empty:
            print(f"  {metal}-{ccy}: AUCUN recouvrement horodate -- validation impossible")
            continue
        pct_diff = (m["close_synth"] - m["close_real"]) / m["close_real"] * 100
        print(f"  {metal}-{ccy} ({real_symbol}) : n_recouvrement={len(m)} "
              f"ecart_moyen={pct_diff.mean():+.3f}% ecart_abs_moyen={pct_diff.abs().mean():.3f}% "
              f"ecart_median={pct_diff.median():+.3f}% max_abs={pct_diff.abs().max():.3f}%")


def build_combined_candles(ticker):
    """Bougies combinees pour un ticker metal : reel MT5 (>=2023-01-19 pour les
    5 crosses) UNION synthetique (USD x FX, dispo des que les 2 legs existent,
    >=2022-01-02) -- reel prioritaire sur le recouvrement."""
    if ticker in DIRECT_SYMBOL:
        return _load_raw(DIRECT_SYMBOL[ticker])
    m = TICKER_RE.match(ticker)
    if not m:
        return None
    metal, ccy = m.groups()
    if ccy == "USD":
        return _load_raw(USD_LEG_SYMBOL[metal])
    if (metal, ccy) not in REAL_CROSS_SYMBOL:
        return None  # CHF/CAD/NZD non backfilles MT5, hors perimetre de cette demande
    real = _load_raw(REAL_CROSS_SYMBOL[(metal, ccy)])
    synth = build_synthetic(metal, ccy)
    synth_only = synth[synth["datetime"] < real["datetime"].min()]
    combined = pd.concat([synth_only, real], ignore_index=True).sort_values("datetime").reset_index(drop=True)
    return combined


BLOC_EDGES = pd.to_datetime([
    "2021-04-23 12:43:32", "2022-08-20 17:22:34.250",
    "2023-12-17 22:01:36.500", "2025-04-15 02:40:38.750", "2026-08-12 07:19:41",
])
TRAILING_FACTOR_METAUX = 0.10


def load_metal_population():
    pop = pd.read_csv("chantier_gold_silver_pop_B_tradable_pgp_2026-08-20.csv")
    pop["date_creation"] = pd.to_datetime(pop["date_creation"])
    metal_kw = ["GOLD", "SILVER", "PALLADIUM", "PLATINUM"]
    is_metal = pop["ticker"].str.contains("|".join(metal_kw), case=False, na=False)
    pop = pop[is_metal].reset_index(drop=True)

    gs_raw = pd.read_csv("historique_or_argent_pilote_2026-08-19.csv")
    gs_raw["date_creation"] = pd.to_datetime(gs_raw["date_creation"])
    pdpt_raw = pd.read_csv("historique_gaz_palladium_platine_pilote_2026-08-20.csv")
    pdpt_raw["date_creation"] = pd.to_datetime(pdpt_raw["date_creation"])
    raw = pd.concat([gs_raw[["date_creation", "ticker", "tp1_init", "tp2_init"]],
                      pdpt_raw[["date_creation", "ticker", "tp1_init", "tp2_init"]]], ignore_index=True)
    raw = raw.drop_duplicates(subset=["date_creation", "ticker"], keep="first")
    pop = pop.merge(raw, on=["date_creation", "ticker"], how="left")
    n_missing = pop["tp1_init"].isna().sum()
    if n_missing:
        print(f"[avertissement] {n_missing}/{len(pop)} trades metaux sans tp1_init/tp2_init apres merge")

    bloc = pd.cut(pop["date_creation"], bins=BLOC_EDGES, labels=["bloc1", "bloc2", "bloc3", "bloc4"])
    pop["bloc"] = bloc.astype(str)
    return pop


def _stop_fn(param):
    def fn(extreme, entry, risk_distance, atr):
        is_long_direction = extreme >= entry
        return extreme - param * risk_distance if is_long_direction else extreme + param * risk_distance
    return fn


def recompute_metals(pop):
    cases, r_trailing_new = [], []
    _candle_cache = {}
    for _, row in pop.iterrows():
        ticker = row["ticker"]
        if row["r_trailing"] <= 0:
            cases.append("perte")
            r_trailing_new.append(row["r_trailing"])
            continue
        if ticker not in _candle_cache:
            _candle_cache[ticker] = build_combined_candles(ticker)
        candles = _candle_cache[ticker]
        if candles is None:
            cases.append("pas_de_mapping")
            r_trailing_new.append(row["rr_tp1"])
            continue
        res = tpseq.analyze_trade(row, candles)
        case = res.get("case", "pas_de_donnees")
        cases.append(case)
        if case in {"tp1_avant_tp2", "meme_bougie"}:
            sim = tsv.simulate_trailing(row, candles, _stop_fn(TRAILING_FACTOR_METAUX), "fixed_0.10")
            r_trailing_new.append(sim["exit_r"] if sim is not None else row["rr_tp1"])
        else:
            r_trailing_new.append(row["rr_tp1"])
    pop = pop.copy()
    pop["case_mt5"] = cases
    pop["r_trailing_mt5"] = r_trailing_new
    return pop


def main():
    validate_synthesis()

    pop = load_metal_population()
    pop = recompute_metals(pop)
    pop.to_csv("chantier_bloc2_metaux_recalc_2026-08-21.csv", index=False)

    UNRESOLVED = {"hors_couverture_historique", "resolution_incertaine_horizon_insuffisant", "pas_de_mapping", "pas_de_donnees"}

    print(f"\n{'='*95}\nETAPE B -- exposition residuelle par ticker, bloc1/bloc2\n{'='*95}")
    for bl in ("bloc1", "bloc2"):
        sub = pop[pop["bloc"] == bl]
        wins = sub[sub["r_trailing"] > 0]
        print(f"\n-- {bl} --")
        for t in sorted(wins["ticker"].unique()):
            w = wins[wins["ticker"] == t]
            unresolved = w["case_mt5"].isin(UNRESOLVED).sum()
            resolved = len(w) - unresolved
            print(f"  {t:12s} n_gagnants={len(w):3d}  resolus={resolved:3d} ({resolved/len(w)*100:5.1f}%)  "
                  f"non_resolus={unresolved:3d} ({unresolved/len(w)*100:5.1f}%)")

    print(f"\n{'='*95}\nETAPE B (bonus) -- verif gap Platinum vs bloc3\n{'='*95}")
    b3_pt = pop[(pop["bloc"] == "bloc3") & (pop["ticker"] == "PLATINUM") & (pop["r_trailing"] > 0)]
    unresolved_pt_b3 = b3_pt["case_mt5"].isin(UNRESOLVED).sum()
    print(f"  bloc3 PLATINUM gagnants={len(b3_pt)} non_resolus_par_le_gap={unresolved_pt_b3}")

    print(f"\n{'='*95}\nRESUME GLOBAL -- ancien EV stocke vs nouveau (meilleure donnee dispo), par bloc\n{'='*95}")
    for bl in ("bloc1", "bloc2", "bloc3", "bloc4"):
        sub = pop[pop["bloc"] == bl]
        n = len(sub)
        ev_old = sub["r_trailing"].mean()
        ev_new = sub["r_trailing_mt5"].mean()
        wr = (sub["r_trailing"] > 0).mean() * 100
        print(f"  {bl}: n={n} winrate={wr:.2f}% EV_ancien={ev_old:+.4f}R EV_nouveau={ev_new:+.4f}R delta={ev_new-ev_old:+.4f}R")


if __name__ == "__main__":
    main()
