"""chantier_piste3_crossmarket_2026-08-23.py

Piste 3, verification ciblee (demandee suite au constat carry-unwind 8%
protegeable) : un gate CROSS-MARCHE base sur la vol JPY (USD/JPY + croix
JPY tradees) aurait-il mieux protege les pertes carry-unwind que la vol du
ticker tradé lui-meme ? Meme proxy retenu (ATR H1, fenetre 40 barres).
"""
import re

import numpy as np
import pandas as pd

WINDOWS = {
    "SVB": (pd.Timestamp("2023-03-08"), pd.Timestamp("2023-03-24")),
    "israel_hamas": (pd.Timestamp("2023-10-07"), pd.Timestamp("2023-11-15")),
    "carry_unwind": (pd.Timestamp("2024-08-01"), pd.Timestamp("2024-08-16")),
}
JPY_CROSSES = ["USD/JPY", "AUD/JPY", "CHF/JPY", "EUR/JPY", "GBP/JPY"]


def load_vol_csv(ticker):
    fname = f"piste3_h1vol_{re.sub(r'[^A-Za-z0-9]', '_', ticker)}_2026-08-23.csv"
    try:
        df = pd.read_csv(fname, usecols=["datetime", "atr_40"])
    except FileNotFoundError:
        return None
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.dropna(subset=["atr_40"]).reset_index(drop=True)
    p90_value = df["atr_40"].quantile(0.90)
    return df, p90_value


def build_jpy_signal():
    """Signal cross-marche : au-dessus P90 des que N'IMPORTE LAQUELLE des
    croix JPY tradees est au-dessus de son propre P90 (union, pas moyenne --
    detecte le stress JPY le plus tot possible, coherent avec l'esprit
    "signal d'alerte precoce")."""
    signals = []
    for t in JPY_CROSSES:
        loaded = load_vol_csv(t)
        if loaded is None:
            print(f"  [JPY signal] {t} : pas de donnees", flush=True)
            continue
        df, p90 = loaded
        s = df[["datetime"]].copy()
        s["above_p90"] = df["atr_40"] >= p90
        s["ticker"] = t
        signals.append(s)
        print(f"  [JPY signal] {t} : P90={p90:.6f}, {s['above_p90'].sum()} bougies au-dessus", flush=True)
    combined = pd.concat(signals).sort_values("datetime")
    # union par timestamp : au-dessus si AU MOINS une croix JPY est au-dessus
    union = combined.groupby("datetime")["above_p90"].any().reset_index()
    union = union.sort_values("datetime").reset_index(drop=True)
    return union


def first_cross_time(union_df, window_start, trade_time):
    sub = union_df[(union_df["datetime"] >= window_start) & (union_df["datetime"] <= trade_time)]
    crossing = sub[sub["above_p90"]]
    return crossing["datetime"].min() if not crossing.empty else None


def analyze_window(wname, window_start, window_end, union_jpy, pop, pop_label):
    losers = pop[(pop["date_creation"] >= window_start) & (pop["date_creation"] < window_end) & (pop["r_trailing"] < 0)]
    n = len(losers)
    protected = 0
    delays = []
    print(f"\n{'='*90}\n{wname} / {pop_label} : {n} pertes -- signal cross-marche JPY\n{'='*90}", flush=True)
    for _, trade in losers.iterrows():
        fc = first_cross_time(union_jpy, window_start, trade["date_creation"])
        would_protect = fc is not None
        if would_protect:
            protected += 1
            delay_h = (trade["date_creation"] - fc).total_seconds() / 3600.0
            delays.append(delay_h)
        print(f"  {trade['ticker']} @ {trade['date_creation']} : jpy_signal_avant={would_protect} "
              f"delai_h={delays[-1] if would_protect else None}", flush=True)
    pct = protected / n * 100 if n else float("nan")
    print(f"  -> {protected}/{n} ({pct:.0f}%) proteges par le signal cross-marche JPY", flush=True)
    return dict(window=wname, population=pop_label, n=n, protected=protected, pct=pct,
                delay_mean=np.mean(delays) if delays else None, delay_median=np.median(delays) if delays else None)


def main():
    print("Construction du signal cross-marche JPY (union des croix)...", flush=True)
    union_jpy = build_jpy_signal()

    pop_b = pd.read_csv("chantier_gold_silver_pop_B_tradable_pgp_2026-08-20.csv")
    pop_b["date_creation"] = pd.to_datetime(pop_b["date_creation"])
    import importlib.util
    spec = importlib.util.spec_from_file_location("bsl", "chantier_gold_silver_B_seule_lancement_2026-08-19.py")
    bsl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bsl)
    pop_a, _, _, _, _, _ = bsl.load_scenario("A")
    pop_a["date_creation"] = pd.to_datetime(pop_a["date_creation"])

    rows = []
    for wname, (start, end) in WINDOWS.items():
        for pop_label, pop in (("B_tradable_pgp", pop_b), ("A_seule", pop_a)):
            rows.append(analyze_window(wname, start, end, union_jpy, pop, pop_label))

    out = pd.DataFrame(rows)
    out.to_csv("chantier_piste3_crossmarket_2026-08-23.csv", index=False)
    print(f"\n{'='*90}\nSYNTHESE COMPARATIVE (ticker-propre vs cross-marche JPY)\n{'='*90}")
    print(out.to_string())


if __name__ == "__main__":
    main()
