"""
Pour chaque duo parmi les 14 paires forex (91 combinaisons), compte les jours où le
drawdown intrajournalier combiné des positions simultanément ouvertes aurait dépassé
-4% / -5% du capital (seuils prop firm typiques).

Deux hypothèses de mesure :
- "flottant" (scénario le plus strict) : pire excursion adverse intrajournalière de
  CHAQUE position ouverte ce jour-là, cumulée, cappée à -1R le jour où le SL est
  effectivement touché.
- "réalisé" : seulement les pertes closes (-1R = -0.5%) le jour même où le SL est touché.

Réutilise les bougies H1 déjà en cache (yfinance_cache/, cf. tp_sequence_analysis.py)
et les temps de résolution déjà calculés (tp_sequence_results.csv). Risque par trade =
0.5% du capital (cf. la simulation d'élargissement du SL, même hypothèse).
"""
import itertools

import pandas as pd

from tp_sequence_analysis import CSV_PATH, MIN_RR, FOREX_PATTERN, ticker_to_yahoo_symbol, fetch_h1_history

RISK_PCT_PER_TRADE = 0.5  # % du capital risqué par trade (1R)
DD_THRESHOLDS = [4.0, 5.0]


def load_forex_population(csv_path=None, sequence_results_path="tp_sequence_results.csv"):
    csv_path = csv_path or CSV_PATH
    df = pd.read_csv(csv_path)
    df["date_creation"] = pd.to_datetime(df["date_creation"])
    pop = df[(df["rr_tp1"] >= MIN_RR) & (df["statut_final"].isin(["OBJECTIF ATTEINT", "INVALIDÉE"]))].copy()
    pop = pop[pop["ticker"].apply(lambda t: bool(FOREX_PATTERN.match(t)))].copy()

    seq = pd.read_csv(sequence_results_path)
    seq["date_creation"] = pd.to_datetime(seq["date_creation"])
    for col in ("tp1_time", "tp2_time", "sl_time"):
        seq[col] = pd.to_datetime(seq[col])

    merged = pop.merge(
        seq[["ticker", "date_creation", "is_long", "tp1_time", "sl_time"]],
        on=["ticker", "date_creation"],
        how="left",
    )

    merged["resolution_time"] = merged.apply(
        lambda r: r["tp1_time"] if r["statut_final"] == "OBJECTIF ATTEINT" else r["sl_time"], axis=1
    )
    dropped = merged[merged["resolution_time"].isna()]
    if not dropped.empty:
        # Inclut les trades hors de la fenêtre H1 Yahoo disponible (~730 jours, cf.
        # tp_sequence_analysis.py) : pas d'erreur, juste pas vérifiables avec les
        # données de prix actuellement accessibles.
        print(f"Exclu (résolution/données introuvables) : {len(dropped)} trade(s) sur {len(merged)}")
        print(f"  Répartition par ticker : {dropped['ticker'].value_counts().to_dict()}")
        print(f"  Plage de dates concernée : {dropped['date_creation'].min()} -> {dropped['date_creation'].max()}")
    merged = merged[merged["resolution_time"].notna()].reset_index(drop=True)
    return merged


def build_trade_day_excursions(pop):
    """Retourne un DataFrame : une ligne par (trade, jour ouvert), avec l'excursion
    adverse ce jour-là en unités de R (0 = pas d'excursion adverse, 1 = -1R plein).

    CORRECTIF (bug détecté lors du calibrage du déclencheur de hedge, piste #8) : la
    version précédente calculait le low/high sur la JOURNÉE CALENDAIRE ENTIÈRE
    (00:00-23:59), y compris les heures où la position n'était PAS encore ouverte ou
    déjà refermée -- gonflant artificiellement l'excursion adverse rapportée (ex: un creux
    survenu 4h avant l'entrée du trade comptait comme si la position l'avait subi).
    Version corrigée : restreint le low/high à la fenêtre RÉELLE où la position était
    ouverte (bougies dont l'heure de départ est dans [date_creation, resolution_time]),
    même convention >= / <= que tp_sequence_analysis.analyze_trade (démarre à la
    première bougie PLEINE après l'entrée -- une entrée à 07:27 ignore la bougie 07:00
    qui a commencé avant l'entrée, cohérent avec le reste du projet)."""
    unique_symbols = sorted(set(ticker_to_yahoo_symbol(t) for t in pop["ticker"].unique()))
    candles_by_symbol = {}
    for symbol in unique_symbols:
        candles = fetch_h1_history(symbol, pop["date_creation"].min(), pd.Timestamp.utcnow())
        if candles is not None and not candles.empty:
            candles_by_symbol[symbol] = candles.sort_values("datetime").reset_index(drop=True)

    rows = []
    for trade_id, row in pop.iterrows():
        symbol = ticker_to_yahoo_symbol(row["ticker"])
        candles = candles_by_symbol.get(symbol)
        if candles is None:
            continue

        entry = row["prix_entree"]
        sl = row["stop_loss_init"]
        is_long = row["is_long"]
        risk_distance = abs(entry - sl)
        if risk_distance == 0:
            continue

        entry_time = row["date_creation"]
        exit_time = row["resolution_time"]
        resolution_is_loss = row["statut_final"] == "INVALIDÉE"
        end_day = exit_time.date()

        window = candles[(candles["datetime"] >= entry_time) & (candles["datetime"] <= exit_time)]
        if window.empty:
            # Entrée et sortie dans la même bougie H1 (position résolue en < 1h) :
            # utilise la dernière bougie démarrée avant l'entrée (même bougie qui
            # englobe l'entrée), même repli que "meme_bougie" ailleurs dans ce projet.
            enclosing = candles[candles["datetime"] <= entry_time]
            if enclosing.empty:
                continue
            window = enclosing.iloc[[-1]]

        window = window.copy()
        window["date"] = window["datetime"].dt.date
        daily = window.groupby("date").agg(low=("low", "min"), high=("high", "max"))

        for day, day_row in daily.iterrows():
            day_low, day_high = day_row["low"], day_row["high"]

            if is_long:
                adverse = max(0.0, entry - day_low)
            else:
                adverse = max(0.0, day_high - entry)

            excursion_r = adverse / risk_distance
            is_final_sl_day = resolution_is_loss and day == end_day
            if is_final_sl_day:
                excursion_r = min(excursion_r, 1.0)

            rows.append({
                "trade_id": trade_id,
                "ticker": row["ticker"],
                "date": day,
                "excursion_r": excursion_r,
                "is_final_sl_day": is_final_sl_day,
            })

    return pd.DataFrame(rows)


def analyze_pairs(trade_days, tickers):
    results = []
    for a, b in itertools.combinations(sorted(tickers), 2):
        days_a = set(trade_days.loc[trade_days["ticker"] == a, "date"])
        days_b = set(trade_days.loc[trade_days["ticker"] == b, "date"])
        overlap_days = days_a & days_b
        if not overlap_days:
            results.append({
                "duo": f"{a} / {b}", "jours_chevauchement": 0,
                "jours_flottant_ge4": 0, "jours_flottant_ge5": 0, "max_dd_flottant_pct": 0.0,
                "jours_realise_ge4": 0, "jours_realise_ge5": 0, "max_dd_realise_pct": 0.0,
            })
            continue

        subset = trade_days[trade_days["ticker"].isin([a, b]) & trade_days["date"].isin(overlap_days)]

        floating_by_day = subset.groupby("date")["excursion_r"].apply(lambda s: s.sum() * RISK_PCT_PER_TRADE)
        realized_by_day = (
            subset[subset["is_final_sl_day"]]
            .groupby("date")["is_final_sl_day"]
            .count() * RISK_PCT_PER_TRADE
        )
        realized_by_day = realized_by_day.reindex(floating_by_day.index, fill_value=0.0)

        results.append({
            "duo": f"{a} / {b}",
            "jours_chevauchement": len(overlap_days),
            "jours_flottant_ge4": int((floating_by_day >= 4.0).sum()),
            "jours_flottant_ge5": int((floating_by_day >= 5.0).sum()),
            "max_dd_flottant_pct": float(floating_by_day.max()),
            "jours_realise_ge4": int((realized_by_day >= 4.0).sum()),
            "jours_realise_ge5": int((realized_by_day >= 5.0).sum()),
            "max_dd_realise_pct": float(realized_by_day.max()),
        })

    return pd.DataFrame(results)


def main(csv_path=None, sequence_results_path="tp_sequence_results.csv",
         trade_days_path="daily_dd_trade_days.csv", ranking_path="daily_dd_pair_ranking.csv"):
    pop = load_forex_population(csv_path=csv_path, sequence_results_path=sequence_results_path)
    print(f"Population forex analysée : {len(pop)} trades sur {pop['ticker'].nunique()} paires")

    trade_days = build_trade_day_excursions(pop)
    trade_days.to_csv(trade_days_path, index=False)
    print(f"Jours-trade calculés : {len(trade_days)}")

    tickers = sorted(pop["ticker"].unique())
    results = analyze_pairs(trade_days, tickers)
    results = results.sort_values(
        ["jours_flottant_ge4", "jours_flottant_ge5", "max_dd_flottant_pct"]
    ).reset_index(drop=True)
    results.to_csv(ranking_path, index=False)

    print("\n" + "=" * 100)
    print("CLASSEMENT DES 91 DUOS — SCÉNARIO ÉQUITÉ FLOTTANTE (le plus strict/prudent)")
    print("=" * 100)
    print(f"{'Duo':<22}{'Jours chev.':>12}{'Jours>=4%':>11}{'Jours>=5%':>11}{'Max DD %':>11}")
    for _, r in results.iterrows():
        print(f"{r['duo']:<22}{r['jours_chevauchement']:>12}{r['jours_flottant_ge4']:>11}{r['jours_flottant_ge5']:>11}{r['max_dd_flottant_pct']:>10.2f}%")

    print("\n" + "=" * 100)
    print("Résumé — scénario RÉALISÉ (pertes closes uniquement)")
    print("=" * 100)
    total_ge4_realise = (results["jours_realise_ge4"] > 0).sum()
    total_ge5_realise = (results["jours_realise_ge5"] > 0).sum()
    print(f"Duos avec au moins 1 jour >= -4% (réalisé) : {total_ge4_realise}/91")
    print(f"Duos avec au moins 1 jour >= -5% (réalisé) : {total_ge5_realise}/91")
    print(f"Max DD réalisé observé (tous duos confondus) : {results['max_dd_realise_pct'].max():.2f}%")

    total_ge4_flot = (results["jours_flottant_ge4"] > 0).sum()
    total_ge5_flot = (results["jours_flottant_ge5"] > 0).sum()
    print(f"\nDuos avec au moins 1 jour >= -4% (flottant) : {total_ge4_flot}/91")
    print(f"Duos avec au moins 1 jour >= -5% (flottant) : {total_ge5_flot}/91")
    print(f"Max DD flottant observé (tous duos confondus) : {results['max_dd_flottant_pct'].max():.2f}%")

    print(f"\nDétails enregistrés dans {ranking_path} et {trade_days_path}")


if __name__ == "__main__":
    main()
