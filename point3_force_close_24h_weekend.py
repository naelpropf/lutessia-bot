"""
Point 3 (07/08) : fermeture forcee avant 24h (ou avant le week-end si plus tot),
sur la population RR>=1,25/trailing 0,15xSL (config gagnante identifiee au
point 1). Pour chaque trade dont la resolution reelle (resolution_time_est)
depasse le delai de fermeture forcee, on recalcule le R obtenu a la fermeture
forcee a partir du prix de la bougie H1 la plus proche (sans depasser) le
moment de fermeture -- close price de cette bougie comme prix de sortie.

Regle de deadline : min(entree + 24h, prochain trou >= WEEKEND_GAP_THRESHOLD_HOURS
dans la serie de bougies du ticker APRES l'entree si ce trou commence avant
entree+24h -- c'est la fermeture de marche du week-end, meme detection que
tp_sequence_analysis.compute_weekend_gap_cost).
"""
import datetime as dt

import numpy as np
import pandas as pd

import tp_sequence_analysis as tpseq
from trailing_payoff_population import build_population_with_trailing

FORCE_CLOSE_HOURS = 24


def find_forced_exit_price(row, candles):
    entry_time = row["date_creation"]
    deadline = entry_time + dt.timedelta(hours=FORCE_CLOSE_HOURS)

    window = candles[candles["datetime"] >= entry_time].sort_values("datetime").reset_index(drop=True)
    if window.empty:
        return None, None

    # detecte un trou de week-end (>= WEEKEND_GAP_THRESHOLD_HOURS) commencant avant le
    # deadline 24h -- si trouve, la fermeture forcee arrive AU DEBUT du trou (dernier
    # prix disponible avant fermeture du marche), pas apres
    for i in range(1, len(window)):
        prev_t = window.loc[i - 1, "datetime"]
        cur_t = window.loc[i, "datetime"]
        gap_h = (cur_t - prev_t).total_seconds() / 3600
        if gap_h >= tpseq.WEEKEND_GAP_THRESHOLD_HOURS and prev_t < deadline:
            return window.loc[i - 1, "close"], prev_t
        if cur_t >= deadline:
            break

    before_deadline = window[window["datetime"] <= deadline]
    if before_deadline.empty:
        return None, None
    return before_deadline.iloc[-1]["close"], before_deadline.iloc[-1]["datetime"]


def build_force_closed_population(pop, force_close_hours=FORCE_CLOSE_HOURS):
    global FORCE_CLOSE_HOURS
    FORCE_CLOSE_HOURS = force_close_hours

    pop = pop.copy()
    pop["hold_h"] = (pop["resolution_time_est"] - pop["date_creation"]).dt.total_seconds() / 3600
    to_force = pop[pop["hold_h"] > force_close_hours].copy()
    print(f"Trades necessitant une fermeture forcee (hold > {force_close_hours}h) : {len(to_force)}/{len(pop)} "
          f"({len(to_force)/len(pop)*100:.1f}%)")

    unique_symbols = sorted(to_force["yahoo_symbol"].dropna().unique())
    candles_by_symbol = {}
    for symbol in unique_symbols:
        candles = tpseq.fetch_h1_history(symbol, to_force["date_creation"].min().to_pydatetime(),
                                          pd.Timestamp.utcnow().tz_localize(None).to_pydatetime())
        if candles is not None and not candles.empty:
            candles_by_symbol[symbol] = candles

    new_outcome_r = pop["outcome_r_base"].copy() if "outcome_r_base" in pop else np.where(
        pop["statut_final"] == "OBJECTIF ATTEINT", pop["r_trailing"], -1.0)
    new_outcome_r = pd.Series(new_outcome_r, index=pop.index)

    n_forced_applied = 0
    n_unresolved = 0
    for idx, row in to_force.iterrows():
        candles = candles_by_symbol.get(row["yahoo_symbol"])
        if candles is None:
            n_unresolved += 1
            continue
        exit_price, exit_time = find_forced_exit_price(row, candles)
        if exit_price is None:
            n_unresolved += 1
            continue
        entry = row["prix_entree"]
        sl = row["stop_loss_init"]
        is_long = row["tp1_init"] > entry
        sl_distance = abs(entry - sl)
        if sl_distance == 0:
            n_unresolved += 1
            continue
        r = (exit_price - entry) / sl_distance if is_long else (entry - exit_price) / sl_distance
        new_outcome_r.loc[idx] = r
        n_forced_applied += 1

    print(f"Fermeture forcee appliquee avec succes : {n_forced_applied}/{len(to_force)} "
          f"({n_unresolved} non resolus par manque de bougies -- outcome original conserve)")

    pop["outcome_r_forced"] = new_outcome_r
    return pop


def main():
    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    pop["yahoo_symbol"] = pop["ticker"].apply(tpseq.ticker_to_yahoo_symbol)
    baseline_r = np.where(pop["statut_final"] == "OBJECTIF ATTEINT", pop["r_trailing"], -1.0)

    pop_forced = build_force_closed_population(pop)
    forced_r = pop_forced["outcome_r_forced"].to_numpy()

    n = len(pop)
    winrate_baseline = (baseline_r > 0).mean() * 100
    winrate_forced = (forced_r > 0).mean() * 100
    print(f"\n--- Comparaison population complete (n={n}) ---")
    print(f"Winrate : baseline {winrate_baseline:.2f}% -> force-close24h {winrate_forced:.2f}%")
    print(f"EV moyen : baseline {baseline_r.mean():+.4f}R -> force-close24h {forced_r.mean():+.4f}R "
          f"({(forced_r.mean()/baseline_r.mean()-1)*100:+.1f}%)")
    print(f"R:R moyen gagnants : baseline {baseline_r[baseline_r>0].mean():.3f} -> "
          f"force-close24h {forced_r[forced_r>0].mean():.3f}")
    print(f"Total R : baseline {baseline_r.sum():.1f} -> force-close24h {forced_r.sum():.1f} "
          f"({(forced_r.sum()/baseline_r.sum()-1)*100:+.1f}%)")

    pop_forced.to_csv("point3_force_closed_population_detail.csv", index=False)


if __name__ == "__main__":
    main()
