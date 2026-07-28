"""
Simule l'élargissement du stop-loss (avec réduction de taille de position pour garder
le même risque de 0.5% du capital) sur les trades INVALIDÉE, et son effet sur l'EV
globale de la population filtrée (rr_tp1 >= MIN_RR, OBJECTIF ATTEINT + INVALIDÉE).

Réutilise les bougies H1 déjà en cache (yfinance_cache/, voir tp_sequence_analysis.py)
et les temps de passage TP1/TP2/SL déjà calculés (tp_sequence_results.csv).
"""
import pandas as pd

from tp_sequence_analysis import CSV_PATH, MIN_RR, ticker_to_yahoo_symbol, fetch_h1_history

WIDEN_SCENARIOS = [0, 10, 20, 30, 50]  # % d'élargissement de la distance entrée-SL

# Le MAE et le "recovery" TP1/TP2 sont bornés à cette fenêtre après le SL initial : au-delà,
# tout mouvement de prix relève de la dérive de marché normale, sans rapport avec le trade
# (signaux tradés en 1H/Journalier — un retour des mois plus tard n'est pas un "recovery" réaliste).
MAE_WINDOW_DAYS = 30


def analyze_loss_for_widening(row, candles):
    """MAE (en % de la distance entrée-SL) borné à [sl_time, tp1_time] si TP1 est
    retouché dans la fenêtre, sinon [sl_time, sl_time + MAE_WINDOW_DAYS]. Retourne aussi
    les temps de passage TP1/TP2 (bornés à la même fenêtre) pour la simulation de sauvetage.
    """
    entry = row["prix_entree"]
    sl = row["stop_loss_init"]
    tp1 = row["tp1_init"]
    tp2 = row["tp2_init"]
    sl_time = row["sl_time"]
    is_long = row["is_long"]

    cutoff = sl_time + pd.Timedelta(days=MAE_WINDOW_DAYS)
    full_window = candles[(candles["datetime"] >= sl_time) & (candles["datetime"] <= cutoff)].sort_values("datetime")
    if full_window.empty:
        return None, None, None

    if is_long:
        tp1_hits = full_window[full_window["high"] >= tp1]
        tp2_hits = full_window[full_window["high"] >= tp2]
    else:
        tp1_hits = full_window[full_window["low"] <= tp1]
        tp2_hits = full_window[full_window["low"] <= tp2]

    tp1_time = tp1_hits["datetime"].iloc[0] if not tp1_hits.empty else None
    tp2_time = tp2_hits["datetime"].iloc[0] if not tp2_hits.empty else None

    mae_end = tp1_time if tp1_time is not None else cutoff
    mae_window = full_window[full_window["datetime"] <= mae_end]

    risk_distance = abs(entry - sl)
    if risk_distance == 0 or mae_window.empty:
        return None, tp1_time, tp2_time

    if is_long:
        excursion = sl - mae_window["low"].min()
    else:
        excursion = mae_window["high"].max() - sl

    mae_pct = max(0.0, excursion / risk_distance * 100)
    return mae_pct, tp1_time, tp2_time


def load_population():
    df = pd.read_csv(CSV_PATH)
    df["date_creation"] = pd.to_datetime(df["date_creation"])
    pop = df[(df["rr_tp1"] >= MIN_RR) & (df["statut_final"].isin(["OBJECTIF ATTEINT", "INVALIDÉE"]))].copy()

    seq = pd.read_csv("tp_sequence_results.csv")
    seq["date_creation"] = pd.to_datetime(seq["date_creation"])
    for col in ("tp1_time", "tp2_time", "sl_time"):
        seq[col] = pd.to_datetime(seq[col])

    merged = pop.merge(
        seq[["ticker", "date_creation", "is_long", "tp1_time", "tp2_time", "sl_time"]],
        on=["ticker", "date_creation"],
        how="left",
    )
    return merged


def compute_mae_for_losses(pop):
    lost = pop[pop["statut_final"] == "INVALIDÉE"].copy()
    lost["yahoo_symbol"] = lost["ticker"].apply(ticker_to_yahoo_symbol)

    mae_values, tp1_times, tp2_times = [], [], []
    candles_cache = {}
    for _, row in lost.iterrows():
        symbol = row["yahoo_symbol"]
        if symbol is None or pd.isna(row["sl_time"]):
            mae_values.append(None)
            tp1_times.append(None)
            tp2_times.append(None)
            continue
        if symbol not in candles_cache:
            candles_cache[symbol] = fetch_h1_history(symbol, row["date_creation"], pd.Timestamp.utcnow())
        candles = candles_cache[symbol]
        if candles is None:
            mae_values.append(None)
            tp1_times.append(None)
            tp2_times.append(None)
            continue
        mae_pct, tp1_time, tp2_time = analyze_loss_for_widening(row, candles)
        mae_values.append(mae_pct)
        tp1_times.append(tp1_time)
        tp2_times.append(tp2_time)

    lost["mae_pct"] = mae_values
    # Écrase tp1_time/tp2_time (non bornés, issus de tp_sequence_results.csv) par les
    # versions bornées à MAE_WINDOW_DAYS après le SL, seules valables pour ce scénario.
    lost["tp1_time"] = tp1_times
    lost["tp2_time"] = tp2_times
    return lost


def compute_metrics(winrate, avg_rr_wins):
    if avg_rr_wins is None:
        return None
    return winrate * avg_rr_wins - (1 - winrate)


def main():
    pop = load_population()
    total = len(pop)
    wins = pop[pop["statut_final"] == "OBJECTIF ATTEINT"]
    n_wins_baseline = len(wins)
    print(f"Population : {total} trades ({n_wins_baseline} OBJECTIF ATTEINT, {total - n_wins_baseline} INVALIDÉE)")

    lost = compute_mae_for_losses(pop)
    no_mae = lost[lost["mae_pct"].isna()]
    if not no_mae.empty:
        print(f"\nMAE non calculable pour {len(no_mae)} trade(s) (données manquantes) : "
              f"{sorted(no_mae['ticker'].unique())}")
    lost_valid = lost[lost["mae_pct"].notna()]

    print("\nDistribution du MAE (% de la distance entrée-SL originale) sur les trades INVALIDÉE :")
    print(lost_valid["mae_pct"].describe().to_string())
    lost_valid.to_csv("sl_widening_mae_detail.csv", index=False)

    rows = []
    for widen_pct in WIDEN_SCENARIOS:
        widen_frac = widen_pct / 100

        saved = lost_valid[lost_valid["mae_pct"] < widen_pct]
        saved_tp1 = saved[saved["tp1_time"].notna()]
        saved_tp2 = saved[saved["tp2_time"].notna()]

        n_wins_tp1 = n_wins_baseline + len(saved_tp1)
        n_wins_tp2 = n_wins_baseline + len(saved_tp2)
        winrate_tp1 = n_wins_tp1 / total
        winrate_tp2 = n_wins_tp2 / total

        new_rr_tp1 = pop["rr_tp1"] / (1 + widen_frac)
        new_rr_tp2 = pop["rr_tp2"] / (1 + widen_frac)

        # RR moyen des gains : trades déjà gagnants (statut d'origine) + trades sauvés pour ce scénario.
        win_mask_tp1 = (pop["statut_final"] == "OBJECTIF ATTEINT") | pop.index.isin(saved_tp1.index)
        win_mask_tp2 = (pop["statut_final"] == "OBJECTIF ATTEINT") | pop.index.isin(saved_tp2.index)
        avg_rr_wins_tp1 = new_rr_tp1[win_mask_tp1].mean() if win_mask_tp1.any() else None
        avg_rr_wins_tp2 = new_rr_tp2[win_mask_tp2].mean() if win_mask_tp2.any() else None

        ev_tp1 = compute_metrics(winrate_tp1, avg_rr_wins_tp1)
        ev_tp2 = compute_metrics(winrate_tp2, avg_rr_wins_tp2)

        rows.append({
            "elargissement_sl": f"+{widen_pct}%" if widen_pct else "actuel (0%)",
            "trades_sauves": len(saved),
            "winrate_tp1": winrate_tp1,
            "rr_moyen_gains_tp1": avg_rr_wins_tp1,
            "ev_tp1": ev_tp1,
            "winrate_tp2": winrate_tp2,
            "rr_moyen_gains_tp2": avg_rr_wins_tp2,
            "ev_tp2": ev_tp2,
        })

    comparison = pd.DataFrame(rows)
    comparison.to_csv("sl_widening_comparison.csv", index=False)

    print("\n" + "=" * 100)
    print("COMPARATIF ÉLARGISSEMENT DU SL")
    print("=" * 100)
    for r in rows:
        print(f"\n{r['elargissement_sl']} — {r['trades_sauves']} trade(s) sauvé(s) par rapport au SL actuel")
        print(f"  Scénario TP1 : winrate {r['winrate_tp1']*100:.2f}% | RR moyen gains {r['rr_moyen_gains_tp1']:.2f} | EV {r['ev_tp1']:+.3f} R")
        print(f"  Scénario TP2 : winrate {r['winrate_tp2']*100:.2f}% | RR moyen gains {r['rr_moyen_gains_tp2']:.2f} | EV {r['ev_tp2']:+.3f} R")

    print("\nDétails enregistrés dans sl_widening_comparison.csv et sl_widening_mae_detail.csv")


if __name__ == "__main__":
    main()
