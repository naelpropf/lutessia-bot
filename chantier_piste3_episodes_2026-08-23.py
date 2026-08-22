"""chantier_piste3_episodes_2026-08-23.py

Piste 3, ETAPE 2 : verification directe sur les 3 chocs. Utilise le proxy
retenu a l'etape 1 -- ATR H1 fenetre 40 barres (le plus stable sur TOUS les
tickers sans exception, cf. chantier_piste3_volgate_2026-08-23.py) --
et les fichiers piste3_h1vol_<ticker>_2026-08-23.csv deja calcules.

Pour chaque fenetre choc, sur les trades PERDANTS de B_tradable_pgp (et
A_seule) tombant dans la fenetre :
- l'ATR(40) du ticker concerne franchit-il son P90 historique (rang
  percentile sur la distribution COMPLETE du ticker) AVANT/AU MOMENT du
  trade perdant (pas apres coup) ?
- delai (en heures) entre le franchissement effectif du P90 et l'entree du
  trade perdant -- mesure si un gate reactif aurait protege CE trade
  precis ou seulement les suivants.
- niveau ATR(40) percentile dans les 2-3 semaines PRECEDANT le choc (calme
  avant la tempete ou deja eleve ?).
"""
import re

import numpy as np
import pandas as pd

WINDOWS = {
    "SVB": (pd.Timestamp("2023-03-08"), pd.Timestamp("2023-03-24")),
    "israel_hamas": (pd.Timestamp("2023-10-07"), pd.Timestamp("2023-11-15")),
    "carry_unwind": (pd.Timestamp("2024-08-01"), pd.Timestamp("2024-08-16")),
}
PRE_WINDOW_DAYS = 21


def load_vol_csv(ticker):
    fname = f"piste3_h1vol_{re.sub(r'[^A-Za-z0-9]', '_', ticker)}_2026-08-23.csv"
    try:
        df = pd.read_csv(fname, usecols=["datetime", "atr_40"])
    except FileNotFoundError:
        return None
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.dropna(subset=["atr_40"]).reset_index(drop=True)
    df["pct_rank"] = df["atr_40"].rank(pct=True) * 100
    p90_value = df["atr_40"].quantile(0.90)
    return df, p90_value


def analyze_trade(df, p90_value, trade_time, window_start):
    """Retourne (au_dessus_p90_au_moment, premier_franchissement_dans_fenetre,
    delai_heures_vs_trade, pct_rank_pre_choc_moyen)."""
    before = df[df["datetime"] <= trade_time]
    if before.empty:
        return None
    at_trade = before.iloc[-1]
    above_at_trade = at_trade["atr_40"] >= p90_value

    in_window_before_trade = df[(df["datetime"] >= window_start) & (df["datetime"] <= trade_time)]
    crossing = in_window_before_trade[in_window_before_trade["atr_40"] >= p90_value]
    first_cross_time = crossing["datetime"].min() if not crossing.empty else None
    delay_hours = None
    if first_cross_time is not None:
        delay_hours = (trade_time - first_cross_time).total_seconds() / 3600.0
    would_have_protected = first_cross_time is not None and first_cross_time <= trade_time

    pre_window = df[(df["datetime"] >= window_start - pd.Timedelta(days=PRE_WINDOW_DAYS)) &
                     (df["datetime"] < window_start)]
    pre_pct_mean = pre_window["pct_rank"].mean() if not pre_window.empty else None

    return dict(above_at_trade=bool(above_at_trade), would_have_protected=bool(would_have_protected),
                delay_hours=delay_hours, pre_window_pct_mean=pre_pct_mean,
                pct_rank_at_trade=float(at_trade["pct_rank"]))


def main():
    pop_b = pd.read_csv("chantier_gold_silver_pop_B_tradable_pgp_2026-08-20.csv")
    pop_b["date_creation"] = pd.to_datetime(pop_b["date_creation"])
    pop_a_files_tried = "chantier_gold_silver_B_seule_lancement_2026-08-19.py"
    import importlib.util
    spec = importlib.util.spec_from_file_location("bsl", pop_a_files_tried)
    bsl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bsl)
    pop_a, _, _, _, _, _ = bsl.load_scenario("A")
    pop_a["date_creation"] = pd.to_datetime(pop_a["date_creation"])

    rows = []
    for wname, (start, end) in WINDOWS.items():
        for pop_label, pop in (("B_tradable_pgp", pop_b), ("A_seule", pop_a)):
            losers = pop[(pop["date_creation"] >= start) & (pop["date_creation"] < end) & (pop["r_trailing"] < 0)]
            print(f"\n{'='*90}\n{wname} / {pop_label} : {len(losers)} trades perdants dans la fenetre\n{'='*90}", flush=True)
            vol_cache = {}
            for _, trade in losers.iterrows():
                ticker = trade["ticker"]
                if ticker not in vol_cache:
                    vol_cache[ticker] = load_vol_csv(ticker)
                loaded = vol_cache[ticker]
                if loaded is None:
                    print(f"  {ticker} @ {trade['date_creation']} : PAS DE DONNEES VOL", flush=True)
                    continue
                df, p90 = loaded
                res = analyze_trade(df, p90, trade["date_creation"], start)
                if res is None:
                    print(f"  {ticker} @ {trade['date_creation']} : pas de bougie H1 disponible avant ce trade", flush=True)
                    continue
                print(f"  {ticker} @ {trade['date_creation']} (r_trailing={trade['r_trailing']:.2f}) : "
                      f"pct_rank_at_trade={res['pct_rank_at_trade']:.1f} au_dessus_P90={res['above_at_trade']} "
                      f"aurait_protege={res['would_have_protected']} delai_h={res['delay_hours']} "
                      f"pre_choc_pct_moy={res['pre_window_pct_mean']:.1f}" if res['pre_window_pct_mean'] is not None else "N/A",
                      flush=True)
                row = dict(window=wname, population=pop_label, ticker=ticker, date_creation=trade["date_creation"],
                           r_trailing=trade["r_trailing"], **res)
                rows.append(row)

    out = pd.DataFrame(rows)
    out.to_csv("chantier_piste3_episodes_detail_2026-08-23.csv", index=False)

    print(f"\n{'='*90}\nSYNTHESE\n{'='*90}")
    for (wname, pop_label), grp in out.groupby(["window", "population"]):
        n = len(grp)
        n_protected = grp["would_have_protected"].sum()
        pre_mean = grp["pre_window_pct_mean"].mean()
        print(f"{wname}/{pop_label} : {n} pertes analysees, {n_protected}/{n} auraient ete au-dessus P90 "
              f"AVANT ou AU trade ({n_protected/n*100:.0f}% des pertes 'protegeables' en theorie), "
              f"contexte pre-choc moyen = P{pre_mean:.0f}")


if __name__ == "__main__":
    main()
