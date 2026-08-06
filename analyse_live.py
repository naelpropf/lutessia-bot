"""
Compare le winrate/EV réel (trades_reels.csv) à la référence backtest, pour repérer
une dérive entre le live et le backtest. Log horodaté dans suivi_ev.log (voir aussi
le paramètre --log).

CORRECTIF (2026-07-31, cf. dossier de vérification indépendante) : le comparatif
"TP2" utilisait auparavant rr_tp2 THÉORIQUE moyenné sur TOUS les trades "OBJECTIF
ATTEINT" (= TP1 atteint, cf. mémoire projet), sans jamais vérifier si le prix avait
réellement continué jusqu'à TP2 -- surestimait l'EV backtest d'environ 85% (naïf
+1.52R vs réaliste +0.82R sur les 472 trades de référence). MIN_RR était aussi resté
à 2.0 (obsolète, le seuil verrouillé et réellement utilisé en live est 1.5) --
corrigé directement dans backtest_analyzer.py, dont ce module hérite la constante.

CORRECTIF 2 (même jour, suite) : passage de tp2_realistic_payoff_detail.csv
(colonne r_realiste, sans trailing) à trailing_realistic_payoff_detail.csv (colonne
r_trailing) -- cohérent avec la stratégie de sortie RÉELLEMENT verrouillée
(trailing_payoff_population.py, 0.2x la distance SL post-TP2, EV +0.907R au lieu de
+0.822R). Déjà filtré au seuil rr_tp1>=1.5 lors de sa génération, donc PAS refiltré
une 2e fois ici (refiltrer une colonne de RÉSULTAT sur un seuil de RR exclurait à
tort tous les trades perdants, dont r_trailing=-1).

Côté LIVE, rr_tp2 (déjà présent dans trades_reels.csv) reste utilisé tel quel SANS
changement : contrairement au backtest historique (où le statut Lutessia "OBJECTIF
ATTEINT" ne garantit que TP1, pas la continuation), un trade live gagnant ferme
RÉELLEMENT à tp2_init -- c'est le TP dur envoyé au broker par
app.executer_signal_reel() (place_market_order(..., tp2_init, ...), corrigé le
31/07 après le trade NZD/USD ticket 81685339). rr_tp2 y est donc déjà le R
RÉELLEMENT atteint pour un trade clos gagnant, pas un objectif théorique non vérifié
-- aucun changement nécessaire côté live pour ce correctif. Note : le trailing post-TP2
n'est pas encore câblé dans la boucle live (trade_logger.manage_trailing_stops existe
mais n'est pas encore appelé depuis app.py), donc rr_tp2 live et r_trailing backtest
ne sont pas encore rigoureusement la même stratégie -- écart à garder en tête tant que
le trailing live n'est pas branché.

trailing_realistic_payoff_detail.csv est un instantané STATIQUE (régénéré en relançant
`python trailing_payoff_population.py`, JAMAIS recalculé à la volée par ce script) --
volontairement pas de nouvel appel réseau H1 (Yahoo Finance) depuis la boucle live
hebdomadaire de app.py, pour ne jamais faire dépendre la fiabilité/latence du bot
d'une requête externe. À régénérer manuellement de temps en temps si l'historique de
référence s'étoffe significativement (pas nécessairement à chaque semaine).

ÉCART CONNU AVEC LA CONFIG VERROUILLÉE PAR SIMULATION (session du 06-07/08/2026,
cf. contexte_projet_lutessia_2026-08-07-v3.md section 5.7) : les simulations de
cette session ont verrouillé RR>=1,25 (pas 1,5) et un trailing post-TP2 à 0,15x la
distance SL (pas 0,2x) comme configuration dominante -- MIN_RR ici et dans app.py/
backtest_analyzer.py, ainsi que le trailing câblé dans trade_logger.py, n'ont PAS
été mis à jour vers ces valeurs. Décision explicite à prendre avant de répercuter
ce changement dans le code de trading réel (impact direct sur l'argent réel,
contrairement aux scripts de simulation).

RAPPEL : tout chiffre de profit produit par ce projet (backtest, simulations Monte
Carlo, comparatif live) reste BRUT -- split prop firm et fiscalité non intégrés à
ce jour, cf. contexte v3 section 0.1. Ne pas interpréter l'EV ou le profit affichés
ici comme un revenu net.
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

REALISTIC_BACKTEST_PATH = "trailing_realistic_payoff_detail.csv"
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


def _global_metrics(df_clean, rr_column, min_rr=MIN_RR):
    """min_rr=None : ne refiltre pas la colonne (cas de r_realiste, déjà filtré au
    seuil d'entrée verrouillé lors de la génération de tp2_realistic_payoff_detail.csv
    -- refiltrer une colonne de RÉSULTAT sur un seuil de RR exclurait à tort tous les
    trades perdants, dont r_realiste vaut -1)."""
    if df_clean is None or df_clean.empty:
        return None
    filtered = df_clean[df_clean[rr_column] >= min_rr] if min_rr is not None else df_clean
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
    backtest_realistic = _load_terminal_trades(REALISTIC_BACKTEST_PATH)

    lines = [f"=== Suivi EV live vs backtest — {datetime.now(timezone.utc).isoformat(timespec='seconds')} ==="]

    if live_clean is None:
        lines.append(f"{LIVE_PATH} introuvable : aucun trade réel exécuté pour l'instant.")
        return "\n".join(lines)

    if live_clean.empty:
        lines.append(f"{LIVE_PATH} existe mais ne contient encore aucun trade terminé.")
        return "\n".join(lines)

    if backtest_realistic is None:
        lines.append(f"[AVERTISSEMENT] {REALISTIC_BACKTEST_PATH} introuvable -- relancer "
                      f"`python trailing_payoff_population.py` pour régénérer la référence backtest. "
                      f"Comparaison backtest indisponible pour ce run.")

    live_wins = len(live_clean[live_clean["statut_final"] == WIN_STATUS])
    bt_wins = len(backtest_realistic[backtest_realistic["statut_final"] == WIN_STATUS]) if backtest_realistic is not None and not backtest_realistic.empty else 0
    lines.append(
        f"\nWinrate global brut (tous RR confondus) : "
        f"live {live_wins}/{len(live_clean)} ({live_wins / len(live_clean) * 100:.2f}%)"
        + (f" | backtest {bt_wins}/{len(backtest_realistic)} ({bt_wins / len(backtest_realistic) * 100:.2f}%)"
           if backtest_realistic is not None and len(backtest_realistic) else "")
    )

    # TP1 : qualité d'entrée (rr_tp1 = ce que Lutessia annonce à l'ouverture du signal,
    # pas de bug ici -- OBJECTIF ATTEINT garantit littéralement TP1 atteint).
    live_metrics = _global_metrics(live_clean, "rr_tp1")
    backtest_metrics = _global_metrics(backtest_realistic, "rr_tp1") if backtest_realistic is not None else None
    lines.append(compare_segment(f"R:R TP1 (RR >= {MIN_RR}, qualité d'entrée)", live_metrics, backtest_metrics))

    # TP2 réaliste + trailing 0.2xSL : stratégie de sortie verrouillée (cf. correctif en tête de fichier).
    live_metrics = _global_metrics(live_clean, "rr_tp2")
    backtest_metrics = (
        _global_metrics(backtest_realistic, "r_trailing", min_rr=None) if backtest_realistic is not None else None
    )
    lines.append(compare_segment("R:R TP2 réaliste + trailing (stratégie de sortie)", live_metrics, backtest_metrics))

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
