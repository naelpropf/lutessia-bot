"""
Analyse de séquencement TP1/TP2/SL à partir de bougies H1 (Yahoo Finance).

Pour les trades filtrés (rr_tp1 >= MIN_RR) :
- OBJECTIF ATTEINT : le prix touche-t-il TP1 avant TP2 ? Repasse-t-il par le prix
  d'entrée (breakeven) entre les deux ?
- INVALIDÉE : le prix touche-t-il TP1 avant de finalement toucher le stop-loss ?

Un seul appel HTTP par ticker unique (tout l'historique H1 de la période), mis en
cache localement dans yfinance_cache/, puis découpé en mémoire par trade.

Note technique : yfinance échoue sur cet environnement (Python 3.7, handshake
anti-bot Yahoo cassé dans la version compatible 3.7 de la lib). L'API Yahoo Finance
chart sous-jacente (celle que yfinance appelle en interne) répond normalement en
requête directe avec un User-Agent de navigateur ; c'est elle qu'on utilise ici.
"""
import datetime as dt
import re
import time
from pathlib import Path

import pandas as pd
import requests

CSV_PATH = "historique_lutessia.csv"
MIN_RR = 2.0
CACHE_DIR = Path("yfinance_cache")

# Écart entre deux bougies H1 consécutives au-delà duquel on considère qu'il s'agit
# d'une fermeture de marché (week-end forex, jour férié) plutôt que d'un trou de
# données ponctuel — sert à détecter les gaps de week-end pour compute_weekend_gap_cost.
WEEKEND_GAP_THRESHOLD_HOURS = 20

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

# Indices : ticker Lutessia (contient souvent un contrat futures avec échéance) ->
# indice spot Yahoo utilisé comme proxy, faute de contrat futures identique sur Yahoo.
INDEX_KEYWORD_MAP = [
    ("DAX40", "^GDAXI"),
    ("NASDAQ100", "^NDX"),
    ("S&P500", "^GSPC"),
]

FOREX_PATTERN = re.compile(r"^[A-Z]{3}/[A-Z]{3}$")


def ticker_to_yahoo_symbol(ticker):
    if FOREX_PATTERN.match(ticker):
        base, quote = ticker.split("/")
        return f"{base}{quote}=X"
    upper = ticker.upper()
    for keyword, symbol in INDEX_KEYWORD_MAP:
        if keyword in upper:
            return symbol
    return None


# Yahoo Finance rejette purement et simplement (erreur, pas de troncature silencieuse)
# toute requête 1h dont le début dépasse cette limite glissante.
YFINANCE_MAX_LOOKBACK_DAYS = 729


def fetch_h1_history(symbol, start_dt, end_dt):
    CACHE_DIR.mkdir(exist_ok=True)
    cache_file = CACHE_DIR / (re.sub(r"[^A-Za-z0-9]", "_", symbol) + ".csv")

    earliest_available = dt.datetime.utcnow() - dt.timedelta(days=YFINANCE_MAX_LOOKBACK_DAYS)
    effective_start = max(start_dt, earliest_available)

    if cache_file.exists():
        df = pd.read_csv(cache_file, parse_dates=["datetime"])
        # Le cache ne suffit que s'il couvre déjà assez loin en arrière (marge de 2
        # jours) ; sinon on retélécharge avec la fenêtre maximale disponible pour le
        # COMPLÉTER (pas besoin de merge : une nouvelle requête sur la fenêtre max
        # englobe toujours l'ancien cache, qui était une sous-fenêtre plus récente).
        if not df.empty and df["datetime"].min() <= effective_start + dt.timedelta(days=2):
            print(f"  {symbol} : cache local suffisant ({len(df)} bougies, depuis {df['datetime'].min()})")
            return df
        print(f"  {symbol} : cache local trop récent (depuis {df['datetime'].min() if not df.empty else 'vide'}), "
              f"re-téléchargement sur la fenêtre max disponible...")

    period1 = int(effective_start.timestamp())
    period2 = int(end_dt.timestamp())
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        f"?period1={period1}&period2={period2}&interval=1h"
    )
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        data = r.json()
    except (requests.RequestException, ValueError) as e:
        print(f"  {symbol} : échec de récupération ({e})")
        return None

    result = data.get("chart", {}).get("result")
    if not result:
        err = data.get("chart", {}).get("error")
        print(f"  {symbol} : pas de données ({err})")
        return None

    res = result[0]
    ts = res.get("timestamp")
    quote = res.get("indicators", {}).get("quote", [{}])[0]
    if not ts or "high" not in quote:
        print(f"  {symbol} : réponse vide")
        return None

    df = pd.DataFrame({
        "datetime": [dt.datetime.utcfromtimestamp(t) for t in ts],
        "open": quote.get("open"),
        "high": quote.get("high"),
        "low": quote.get("low"),
        "close": quote.get("close"),
    }).dropna(subset=["high", "low"])

    df.to_csv(cache_file, index=False)
    print(f"  {symbol} : {len(df)} bougies récupérées et mises en cache")
    time.sleep(1)
    return df


def compute_weekend_gap_cost(entry, sl, is_long, sl_time, window):
    """Coût réel (en R, au-delà du -1R théorique) d'un gap de week-end sur le SL : si
    la bougie qui touche le SL suit un trou >= WEEKEND_GAP_THRESHOLD_HOURS dans la
    série de bougies (typiquement le marché forex fermé le week-end), regarde si
    l'OUVERTURE de cette bougie avait déjà dépassé le SL avant tout mouvement
    intra-bougie — c'est le slippage réel qu'un compte réel aurait subi (rempli au
    prix d'ouverture du gap, pas exactement au SL). Retourne (excess_r, is_gap) ;
    excess_r est None si sl_time est inconnu (pas de perte, ou donnée manquante)."""
    if sl_time is None:
        return None, False

    sorted_candles = window.sort_values("datetime").reset_index(drop=True)
    idx_matches = sorted_candles.index[sorted_candles["datetime"] == sl_time]
    if len(idx_matches) == 0 or idx_matches[0] == 0:
        return 0.0, False
    idx = idx_matches[0]

    gap_hours = (sorted_candles.loc[idx, "datetime"] - sorted_candles.loc[idx - 1, "datetime"]).total_seconds() / 3600
    if gap_hours < WEEKEND_GAP_THRESHOLD_HOURS:
        return 0.0, False

    risk_distance = abs(entry - sl)
    if risk_distance == 0:
        return 0.0, True

    gap_open = sorted_candles.loc[idx, "open"]
    if is_long:
        excess = max(0.0, (sl - gap_open) / risk_distance)
    else:
        excess = max(0.0, (gap_open - sl) / risk_distance)

    return excess, True


def analyze_trade(row, candles):
    entry = row["prix_entree"]
    sl = row["stop_loss_init"]
    tp1 = row["tp1_init"]
    tp2 = row["tp2_init"]
    is_long = tp1 > entry
    creation = row["date_creation"]

    earliest_candle = candles["datetime"].min()
    if pd.isna(earliest_candle) or creation < earliest_candle - dt.timedelta(hours=6):
        # Le trade est antérieur à la fenêtre H1 disponible (limite ~730 jours de
        # Yahoo) : l'analyser quand même donnerait un résultat trompeur (les bougies
        # disponibles ne couvrent pas le vrai début du trade), pas juste incomplet.
        return {"case": "hors_couverture_historique", "is_long": is_long}

    window = candles[candles["datetime"] >= creation].sort_values("datetime")
    if window.empty:
        return {"case": "pas_de_donnees", "is_long": is_long}

    if is_long:
        tp1_hits = window[window["high"] >= tp1]
        tp2_hits = window[window["high"] >= tp2]
        sl_hits = window[window["low"] <= sl]
    else:
        tp1_hits = window[window["low"] <= tp1]
        tp2_hits = window[window["low"] <= tp2]
        sl_hits = window[window["high"] >= sl]

    tp1_time = tp1_hits["datetime"].iloc[0] if not tp1_hits.empty else None
    tp2_time = tp2_hits["datetime"].iloc[0] if not tp2_hits.empty else None
    sl_time = sl_hits["datetime"].iloc[0] if not sl_hits.empty else None

    result = {"is_long": is_long, "tp1_time": tp1_time, "tp2_time": tp2_time, "sl_time": sl_time}

    if row["statut_final"] == "OBJECTIF ATTEINT":
        if tp1_time is None:
            result["case"] = "tp1_non_detecte"
        elif tp2_time is None:
            result["case"] = "tp2_non_atteint_dans_fenetre"
        elif tp1_time == tp2_time:
            result["case"] = "meme_bougie"
        elif tp2_time > tp1_time:
            result["case"] = "tp1_avant_tp2"
            result["delay_hours"] = (tp2_time - tp1_time).total_seconds() / 3600
            between = window[(window["datetime"] > tp1_time) & (window["datetime"] < tp2_time)]
            result["breakeven_revisit"] = bool(((between["low"] <= entry) & (between["high"] >= entry)).any())
        else:
            result["case"] = "tp2_avant_tp1"

    elif row["statut_final"] == "INVALIDÉE":
        if sl_time is None:
            result["case"] = "sl_non_detecte"
        elif tp1_time is None:
            result["case"] = "perte_directe_sans_tp1"
        elif tp1_time == sl_time:
            result["case"] = "meme_bougie"
        elif tp1_time < sl_time:
            result["case"] = "tp1_avant_sl"
            result["delay_hours"] = (sl_time - tp1_time).total_seconds() / 3600
        else:
            result["case"] = "sl_avant_tp1"

        gap_excess_r, is_gap = compute_weekend_gap_cost(entry, sl, is_long, sl_time, window)
        result["gap_excess_r"] = gap_excess_r
        result["is_weekend_gap"] = is_gap

    return result


def main(csv_path=None, results_path="tp_sequence_results.csv"):
    csv_path = csv_path or CSV_PATH
    df = pd.read_csv(csv_path)
    df["date_creation"] = pd.to_datetime(df["date_creation"])
    sub = df[(df["rr_tp1"] >= MIN_RR) & (df["statut_final"].isin(["OBJECTIF ATTEINT", "INVALIDÉE"]))].copy()
    print(f"Source : {csv_path}")
    print(f"Trades filtrés (rr_tp1 >= {MIN_RR}, OBJECTIF ATTEINT + INVALIDÉE) : {len(sub)}")
    print(f"Période couverte par l'échantillon : {sub['date_creation'].min()} -> {sub['date_creation'].max()}")

    sub["yahoo_symbol"] = sub["ticker"].apply(ticker_to_yahoo_symbol)
    unmapped = sorted(sub[sub["yahoo_symbol"].isna()]["ticker"].unique())
    if unmapped:
        print(f"\nTickers non mappés vers Yahoo Finance (exclus) : {unmapped}")

    mapped = sub[sub["yahoo_symbol"].notna()].copy()
    unique_symbols = sorted(mapped["yahoo_symbol"].unique())
    print(f"\nTéléchargement/complément de l'historique H1 pour {len(unique_symbols)} ticker(s) unique(s)...")

    start_dt = mapped["date_creation"].min() - dt.timedelta(days=1)
    end_dt = dt.datetime.utcnow()

    candles_by_symbol = {}
    unavailable_symbols = []
    for symbol in unique_symbols:
        candles = fetch_h1_history(symbol, start_dt, end_dt)
        if candles is None or candles.empty:
            unavailable_symbols.append(symbol)
        else:
            candles_by_symbol[symbol] = candles

    if unavailable_symbols:
        affected = sorted(mapped[mapped["yahoo_symbol"].isin(unavailable_symbols)]["ticker"].unique())
        print(f"\nSymboles Yahoo sans données (exclus) : {unavailable_symbols} -> tickers concernés : {affected}")

    analyzable = mapped[mapped["yahoo_symbol"].isin(candles_by_symbol.keys())].copy()
    print(f"\nTrades avec un historique de prix pour leur ticker : {len(analyzable)} / {len(sub)}")

    results = []
    for _, row in analyzable.iterrows():
        candles = candles_by_symbol[row["yahoo_symbol"]]
        res = analyze_trade(row, candles)
        res["ticker"] = row["ticker"]
        res["date_creation"] = row["date_creation"]
        res["statut_final"] = row["statut_final"]
        results.append(res)

    res_df = pd.DataFrame(results)
    res_df.to_csv(results_path, index=False)

    # Trades dont la date de création précède la fenêtre H1 disponible chez Yahoo
    # (~730 jours en arrière) : on ne peut pas les vérifier, on les signale plutôt
    # que de les analyser avec des bougies qui ne couvrent pas leur vraie période
    # (ce qui donnerait un résultat trompeur) ou de planter.
    hors_couverture = res_df[res_df["case"] == "hors_couverture_historique"]
    if not hors_couverture.empty:
        earliest_covered = min(c["datetime"].min() for c in candles_by_symbol.values())
        print(f"\n⚠️ {len(hors_couverture)} trade(s) antérieurs à la fenêtre H1 disponible "
              f"(couverture à partir de ~{earliest_covered}) : NON vérifiables, exclus de "
              f"l'analyse ci-dessous (pas comptés comme erreurs, juste hors de portée).")
        print(f"   Répartition par ticker : {hors_couverture['ticker'].value_counts().to_dict()}")
        print(f"   Plage de dates concernée : {hors_couverture['date_creation'].min()} -> {hors_couverture['date_creation'].max()}")

    analysable_res = res_df[res_df["case"] != "hors_couverture_historique"]

    print("\n" + "=" * 70)
    print("RÉSULTATS — OBJECTIF ATTEINT")
    print("=" * 70)
    won = analysable_res[analysable_res["statut_final"] == "OBJECTIF ATTEINT"]
    total_won = len(won)
    print(f"Total analysable (dans la fenêtre historique) : {total_won}")
    print(won["case"].value_counts().to_string())

    tp1_before_tp2 = won[won["case"] == "tp1_avant_tp2"]
    if total_won > 0:
        pct_tp1_before_tp2 = len(tp1_before_tp2) / total_won * 100
        print(f"\n% trades où TP1 touché avant TP2 (bougies distinctes) : {pct_tp1_before_tp2:.1f}% ({len(tp1_before_tp2)}/{total_won})")
    if not tp1_before_tp2.empty:
        print(f"Délai moyen TP1 -> TP2 : {tp1_before_tp2['delay_hours'].mean():.1f} h (médiane {tp1_before_tp2['delay_hours'].median():.1f} h)")
        pct_breakeven = tp1_before_tp2["breakeven_revisit"].mean() * 100
        print(f"% de ces trades où le prix repasse par le breakeven avant TP2 : {pct_breakeven:.1f}% ({tp1_before_tp2['breakeven_revisit'].sum()}/{len(tp1_before_tp2)})")

    print("\n" + "=" * 70)
    print("RÉSULTATS — INVALIDÉE")
    print("=" * 70)
    lost = analysable_res[analysable_res["statut_final"] == "INVALIDÉE"]
    total_lost = len(lost)
    print(f"Total analysable (dans la fenêtre historique) : {total_lost}")
    print(lost["case"].value_counts().to_string())

    tp1_before_sl = lost[lost["case"] == "tp1_avant_sl"]
    if total_lost > 0:
        pct_tp1_before_sl = len(tp1_before_sl) / total_lost * 100
        print(f"\n% trades INVALIDÉE ayant touché TP1 avant de finalement perdre : {pct_tp1_before_sl:.1f}% ({len(tp1_before_sl)}/{total_lost})")
    if not tp1_before_sl.empty:
        print(f"Délai moyen TP1 -> SL : {tp1_before_sl['delay_hours'].mean():.1f} h (médiane {tp1_before_sl['delay_hours'].median():.1f} h)")

    print("\n--- Coût du risque de gap week-end (trades INVALIDÉE) ---")
    lost_with_sl = lost[lost["gap_excess_r"].notna()]
    gap_trades = lost_with_sl[lost_with_sl["is_weekend_gap"] == True]
    print(f"Trades perdants avec un SL identifié : {len(lost_with_sl)}")
    print(f"Dont touchés par un gap de week-end au moment du SL : {len(gap_trades)} "
          f"({len(gap_trades) / len(lost_with_sl) * 100:.1f}%)" if len(lost_with_sl) else "")
    if not gap_trades.empty:
        print(f"Coût excédentaire moyen sur les trades concernés par un gap : {gap_trades['gap_excess_r'].mean():+.3f} R "
              f"(médiane {gap_trades['gap_excess_r'].median():+.3f} R, max {gap_trades['gap_excess_r'].max():+.3f} R)")
        print(f"Coût excédentaire moyen sur TOUS les trades perdants (gap ou non) : "
              f"{lost_with_sl['gap_excess_r'].mean():+.3f} R")
        print("Détail des trades avec gap :")
        print(gap_trades[["ticker", "date_creation", "sl_time", "gap_excess_r"]].to_string(index=False))
    else:
        print("Aucun trade perdant touché par un gap de week-end sur cet échantillon.")

    print(f"\nRésultats détaillés enregistrés dans {results_path}")


if __name__ == "__main__":
    main()
