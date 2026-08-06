"""
Statistiques de sizing pour les pistes #5 (Kelly fractionnel) et #6 (ajusté ATR) du
document de reprise -- indépendantes du pyramiding (piste #4, déjà traitée et rejetée,
cf. pyramid_engine.py / memory projet), ici chaque trade reste une position UNIQUE
(pas d'ajouts), seul le RISQUE CIBLE (target_risk_pct) varie selon la méthode.

Population de référence : trailing_payoff_population.build_population_with_trailing
("fixed", 0.2) -- seuil rr_tp1 >= 1.5, payoff réaliste (rr_tp2 si continuation confirmée
sinon rr_tp1, sinon -1.0) AVEC le trailing stop post-TP2 0.2xSL déjà adopté appliqué
comme partout ailleurs (colonne "r_trailing", pas "r_realiste" brut -- le trailing reste
INCHANGÉ, cf. demande explicite de l'utilisateur). Nécessaire pour rester cohérent avec
la baseline lue dans risk_levels_trailing_02_summary.csv (même config exacte).

--- Kelly fractionnel ---
f* = (p*b - q) / b = p - q/b,  avec p = winrate, b = RR moyen des gains (en R), q = 1-p.
Calculé PAR SEGMENT (paire de devises -- pas de dimension "timeframe" distincte dans ce
dataset, tous les signaux Lutessia sont sur le même flux/timeframe), avec repli sur les
statistiques GLOBALES de la population si le segment a moins de MIN_SEGMENT_N trades
(l'estimation winrate/RR devient trop bruitée en-dessous de ce seuil pour être fiable).

Le Kelly plein appliqué brut à des multiples de R (sans coûts de transaction ni
incertitude de modèle) suggère typiquement des fractions ÉNORMES sur cette population
(20-31% plein par paire, cf. sortie du module) -- 25-50% de ça reste souvent >10%/trade,
bien au-delà de la plage 0.5-3% déjà testée dans ce projet. Aucun plafond artificiel
n'est appliqué ici (l'utilisateur a spécifié la formule et la fraction à utiliser
telles quelles) -- seul un plancher à 0 est appliqué si le Kelly plein est négatif
(pas d'edge sur ce segment -> risque cible nul, cohérent avec le principe même du
critère de Kelly : ne pas parier sans edge). Le résultat (risques par trade très
supérieurs à tout ce qui a été testé jusqu'ici, et l'impact que ça a sur les casses de
flotte) est justement une partie de ce que le backtest doit révéler.

--- Sizing ajusté ATR ---
Le sizing actuel (feasible_risk_pct) rend déjà le risque $ proportionnel au risque
NOMINAL visé (target_risk_pct% du palier), quelle que soit la distance de SL du signal
-- mais ne tient PAS compte du niveau de volatilité COURANT de la paire au moment du
trade (un ATR anormalement élevé ou faible par rapport à la normale de cette paire).
L'ajustement ATR échelonne le risque cible INVERSEMENT à ce ratio :
    ratio = ATR_de_référence(paire) / ATR_courant(au moment du trade)
    risque_ajusté = risque_de_base * ratio  (clippé à [MIN_ATR_RATIO, MAX_ATR_RATIO])
ATR_de_référence = médiane de l'ATR(14, H1) sur tout l'historique H1 en cache pour cette
paire (niveau "typique" stable, pas influencé par un pic ponctuel).
"""
import pandas as pd

import tp_sequence_analysis as tpseq
from tp2_realistic_payoff import MIN_RR_TP1
from trailing_payoff_population import build_population_with_trailing
from trailing_stop_variants import compute_atr

MIN_SEGMENT_N = 20

MIN_ATR_RATIO = 0.5
MAX_ATR_RATIO = 2.0
ATR_PERIOD = 14


def build_base_population(min_rr=MIN_RR_TP1, verbose=False):
    pop = build_population_with_trailing("fixed", 0.2, min_rr=min_rr, verbose=verbose)
    pop["yahoo_symbol"] = pop["ticker"].apply(tpseq.ticker_to_yahoo_symbol)
    return pop


def _segment_stats(sub):
    n = len(sub)
    wins = sub[sub["statut_final"] == "OBJECTIF ATTEINT"]
    winrate = len(wins) / n if n else float("nan")
    avg_win_r = wins["r_trailing"].mean() if len(wins) else float("nan")
    return n, winrate, avg_win_r


def kelly_fraction(winrate, avg_win_r):
    if avg_win_r is None or avg_win_r != avg_win_r or avg_win_r <= 0:
        return 0.0
    q = 1 - winrate
    return winrate - q / avg_win_r


def compute_kelly_risk_by_ticker(pop, kelly_multiplier):
    """Retourne {ticker: target_risk_pct} -- Kelly fractionnel (kelly_multiplier x Kelly
    plein), par segment paire, avec repli sur les stats globales si le segment est trop
    petit (< MIN_SEGMENT_N). Pas de plafond artificiel (cf. docstring module) : seul un
    plancher à 0 si le Kelly plein du segment est négatif (pas d'edge -> pas de risque)."""
    n_global, winrate_global, avg_win_r_global = _segment_stats(pop)
    kelly_global = kelly_fraction(winrate_global, avg_win_r_global)

    risk_by_ticker = {}
    stats_rows = []
    for ticker, sub in pop.groupby("ticker"):
        n, winrate, avg_win_r = _segment_stats(sub)
        used_fallback = n < MIN_SEGMENT_N
        if used_fallback:
            winrate_used, avg_win_r_used, kelly_full = winrate_global, avg_win_r_global, kelly_global
        else:
            winrate_used, avg_win_r_used = winrate, avg_win_r
            kelly_full = kelly_fraction(winrate, avg_win_r)

        risk_pct = max(0.0, kelly_multiplier * kelly_full * 100)
        risk_by_ticker[ticker] = risk_pct
        stats_rows.append({
            "ticker": ticker, "n": n, "winrate_pct": winrate * 100 if winrate == winrate else float("nan"),
            "avg_win_r": avg_win_r, "used_fallback": used_fallback,
            "kelly_full_pct": kelly_full * 100, "kelly_fractional_risk_pct": risk_pct,
        })

    stats_df = pd.DataFrame(stats_rows).sort_values("ticker").reset_index(drop=True)
    return risk_by_ticker, stats_df


def _load_candles_with_atr(pop):
    candles_by_symbol = {}
    unique_symbols = sorted(pop["yahoo_symbol"].dropna().unique())
    for symbol in unique_symbols:
        candles = tpseq.fetch_h1_history(symbol, pop["date_creation"].min().to_pydatetime(),
                                          pd.Timestamp.utcnow().tz_localize(None).to_pydatetime())
        if candles is not None and not candles.empty:
            candles_by_symbol[symbol] = compute_atr(candles, period=ATR_PERIOD).sort_values("datetime").reset_index(drop=True)
    return candles_by_symbol


def compute_atr_ratio_by_trade(pop):
    """Retourne un dict {(ticker, date_creation): ratio_atr} -- ratio ATR_référence(paire)
    / ATR_courant(au moment du trade), clippé à [MIN_ATR_RATIO, MAX_ATR_RATIO]. Repli à
    1.0 (pas d'ajustement) si les bougies H1 sont indisponibles pour ce trade (même
    logique prudente qu'ailleurs dans ce projet sur les trades hors couverture)."""
    candles_by_symbol = _load_candles_with_atr(pop)

    reference_atr = {}
    for symbol, candles in candles_by_symbol.items():
        reference_atr[symbol] = candles["atr"].median()

    ratio_map = {}
    stats_rows = []
    for _, row in pop.iterrows():
        symbol = row["yahoo_symbol"]
        candles = candles_by_symbol.get(symbol)
        ratio = 1.0
        current_atr = None
        if candles is not None:
            prior = candles[candles["datetime"] <= row["date_creation"]]
            if not prior.empty:
                current_atr = prior["atr"].iloc[-1]
                if current_atr and current_atr > 0 and reference_atr.get(symbol, 0) > 0:
                    raw_ratio = reference_atr[symbol] / current_atr
                    ratio = max(MIN_ATR_RATIO, min(MAX_ATR_RATIO, raw_ratio))
        ratio_map[(row["ticker"], row["date_creation"])] = ratio
        stats_rows.append({"ticker": row["ticker"], "date_creation": row["date_creation"],
                            "current_atr": current_atr, "reference_atr": reference_atr.get(symbol),
                            "atr_ratio_clipped": ratio})

    stats_df = pd.DataFrame(stats_rows)
    return ratio_map, stats_df


if __name__ == "__main__":
    pop = build_base_population(verbose=True)

    print("\n" + "=" * 100)
    print(f"KELLY FRACTIONNEL PAR PAIRE (seuil segment N>={MIN_SEGMENT_N}, sinon repli global)")
    print("=" * 100)
    for mult, label in [(0.25, "25%"), (0.5, "50%")]:
        _, stats_df = compute_kelly_risk_by_ticker(pop, mult)
        print(f"\n--- Kelly {label} ---")
        print(stats_df.to_string(index=False))

    print("\n" + "=" * 100)
    print("RATIO ATR (référence médiane / courant), échantillon")
    print("=" * 100)
    _, atr_df = compute_atr_ratio_by_trade(pop)
    print(atr_df.groupby("ticker")["atr_ratio_clipped"].describe().to_string())
