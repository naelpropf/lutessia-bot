"""
Applique les mêmes métriques que backtest_analyzer.py (winrate, RR moyen des gains,
écart-type, EV) à trades_reels.csv, et compare explicitement aux chiffres du backtest
historique (historique_lutessia.csv) pour repérer une dérive entre le live et le
backtest. Log horodaté dans suivi_ev.log (voir aussi le paramètre --log).
"""
import argparse
from datetime import datetime, timezone

import pandas as pd

from backtest_analyzer import (
    MIN_RR,
    MIN_SAMPLE_SIZE,
    TERMINAL_STATUSES,
    WIN_STATUS,
    _compute_metrics,
)

HISTORIQUE_PATH = "historique_lutessia.csv"
LIVE_PATH = "trades_reels.csv"
LOG_PATH = "suivi_ev.log"


def _load_terminal_trades(csv_path):
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        return None
    if df.empty:
        return df
    return df[df["statut_final"].isin(TERMINAL_STATUSES)]


def _global_metrics(df_clean, rr_column):
    if df_clean is None or df_clean.empty:
        return None
    filtered = df_clean[df_clean[rr_column] >= MIN_RR]
    if filtered.empty:
        return None
    return _compute_metrics(filtered, rr_column)


def _fmt_metrics(m):
    if m is None:
        return "pas de données"
    ev_str = f"{m['ev']:+.3f} R" if m["ev"] is not None else "n/a"
    return f"{m['count']} trades | winrate {m['winrate'] * 100:.2f}% ({m['wins']}/{m['count']}) | EV {ev_str}"


def compare_segment(label, live_metrics, backtest_metrics):
    lines = [f"\n--- {label} ---", f"Live      : {_fmt_metrics(live_metrics)}", f"Backtest  : {_fmt_metrics(backtest_metrics)}"]

    if live_metrics is None:
        lines.append("Pas assez de trades live terminés pour comparer sur ce segment.")
        return "\n".join(lines)

    if live_metrics["count"] < MIN_SAMPLE_SIZE:
        lines.append(f"[AVERTISSEMENT STATISTIQUE] Échantillon live trop faible (< {MIN_SAMPLE_SIZE}). Écart ci-dessous à interpréter avec prudence.")

    if backtest_metrics is None:
        return "\n".join(lines)

    winrate_diff_pts = (live_metrics["winrate"] - backtest_metrics["winrate"]) * 100
    lines.append(
        f"Écart winrate : {winrate_diff_pts:+.1f} point(s) "
        f"(live {live_metrics['winrate'] * 100:.2f}% vs backtest {backtest_metrics['winrate'] * 100:.2f}%)"
    )

    if live_metrics["ev"] is not None and backtest_metrics["ev"] is not None:
        ev_diff = live_metrics["ev"] - backtest_metrics["ev"]
        lines.append(f"Écart EV : {ev_diff:+.3f} R (live {live_metrics['ev']:+.3f} R vs backtest {backtest_metrics['ev']:+.3f} R)")

    return "\n".join(lines)


def build_report():
    live_clean = _load_terminal_trades(LIVE_PATH)
    backtest_clean = _load_terminal_trades(HISTORIQUE_PATH)

    lines = [f"=== Suivi EV live vs backtest — {datetime.now(timezone.utc).isoformat(timespec='seconds')} ==="]

    if live_clean is None:
        lines.append(f"{LIVE_PATH} introuvable : aucun trade réel exécuté pour l'instant.")
        return "\n".join(lines)

    if live_clean.empty:
        lines.append(f"{LIVE_PATH} existe mais ne contient encore aucun trade terminé.")
        return "\n".join(lines)

    live_wins = len(live_clean[live_clean["statut_final"] == WIN_STATUS])
    backtest_wins = len(backtest_clean[backtest_clean["statut_final"] == WIN_STATUS]) if backtest_clean is not None else 0
    lines.append(
        f"\nWinrate global brut (tous RR confondus) : "
        f"live {live_wins}/{len(live_clean)} ({live_wins / len(live_clean) * 100:.2f}%)"
        + (f" | backtest {backtest_wins}/{len(backtest_clean)} ({backtest_wins / len(backtest_clean) * 100:.2f}%)" if backtest_clean is not None and len(backtest_clean) else "")
    )

    for rr_column, label in (("rr_tp1", "TP1"), ("rr_tp2", "TP2")):
        live_metrics = _global_metrics(live_clean, rr_column)
        backtest_metrics = _global_metrics(backtest_clean, rr_column)
        lines.append(compare_segment(f"R:R {label} (RR >= {MIN_RR})", live_metrics, backtest_metrics))

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Compare le winrate/EV live à trades_reels.csv vs le backtest historique.")
    parser.add_argument("--log", action="store_true", help=f"Ajoute aussi le rapport à {LOG_PATH}")
    args = parser.parse_args()

    report = build_report()
    print(report)

    if args.log:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(report + "\n\n")
        print(f"\n(Rapport ajouté à {LOG_PATH})")


if __name__ == "__main__":
    main()
