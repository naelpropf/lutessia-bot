"""
Garde-fou À FAIRE AVANT de simuler des variantes de trailing stop post-TP2 : sur les
98 trades à continuation TP1->TP2 CONFIRMÉE (tp2_realistic_payoff.py), calcule via les
bougies H1 déjà en cache l'excursion favorable maximale (MFE) APRÈS le passage de TP2,
en R additionnels au-delà de rr_tp2 -- pour savoir si un trailing stop post-TP2 vaut la
peine d'être simulé en détail (3 variantes) ou si l'effet serait marginal sur l'EV
globale (peu de trades concernés / peu de R additionnels).

Méthode : même fenêtre de bougies H1 que tp_sequence_analysis.analyze_trade (déjà en
cache pour ces trades, puisqu'ils ont justement été classés "continuation confirmée"
grâce à ces mêmes bougies). Pour chaque trade, on repère tp2_time (premier instant où
le prix atteint tp2_init), puis on prend l'extremum favorable (plus haut si LONG, plus
bas si SHORT) sur TOUTES les bougies disponibles à partir de tp2_time (inclus), jusqu'à
la fin de la fenêtre H1 en cache -- PAS jusqu'à un stop-loss ou une invalidation, juste
le MFE brut, pour quantifier le potentiel maximal avant de choisir une règle de sortie.
"""
import pandas as pd

import tp_sequence_analysis as tpseq
from tp2_realistic_payoff import build_realistic_payoff_population

MIN_RR_TP1 = 1.5
SIGNIFICANT_ADDITIONAL_R = 1.0  # seuil arbitraire mais explicite : +1R additionnel ou plus


MAX_HORIZON_ABS = pd.Timedelta(days=30)
HORIZON_MULTIPLIER = 3  # proxy : on laisse courir jusqu'à 3x le délai déjà mis pour atteindre TP2


def compute_mfe_after_tp2(row, candles):
    """MFE brut (première passe, SANS borne) puis MFE BORNÉ à un horizon réaliste --
    la 1ère passe (sans plafond) s'est révélée mesurer la dérive du prix jusqu'à
    AUJOURD'HUI (des mois/années après le trade, sans rapport avec une position
    réellement tenue ouverte) : 100% des 98 trades touchaient la fin de la fenêtre H1
    en cache, avec un R additionnel moyen de +34R et un max de +143R, ce qui n'a de
    sens que si on suppose que la position reste ouverte indéfiniment.

    Horizon borné retenu (proxy explicite, pas une vraie règle de trailing -- celle-ci
    sera testée séparément dans les 3 variantes) : min(3x le délai mis pour atteindre
    TP2 depuis la création du trade, 30 jours). Le facteur x3 et le plafond de 30 jours
    sont des choix arbitraires mais assumés, pour donner un ordre de grandeur réaliste
    avant de construire les règles de trailing proprement dites."""
    entry = row["prix_entree"]
    sl = row["stop_loss_init"]
    tp1 = row["tp1_init"]
    tp2 = row["tp2_init"]
    is_long = tp1 > entry
    creation = row["date_creation"]
    risk_distance = abs(entry - sl)

    window = candles[candles["datetime"] >= creation].sort_values("datetime")
    if window.empty:
        return None

    if is_long:
        tp2_hits = window[window["high"] >= tp2]
    else:
        tp2_hits = window[window["low"] <= tp2]

    if tp2_hits.empty:
        return None  # ne devrait pas arriver pour ce sous-ensemble (continuation confirmée)

    tp2_time = tp2_hits["datetime"].iloc[0]
    delay_to_tp2 = tp2_time - creation
    horizon_limit = tp2_time + min(HORIZON_MULTIPLIER * delay_to_tp2, MAX_HORIZON_ABS)

    after_raw = window[window["datetime"] >= tp2_time]
    after = after_raw[after_raw["datetime"] <= horizon_limit]
    if after.empty:
        after = after_raw.iloc[[0]]

    if is_long:
        extreme_price_raw = after_raw["high"].max()
        extreme_r_raw = (extreme_price_raw - entry) / risk_distance
        extreme_price = after["high"].max()
        extreme_r = (extreme_price - entry) / risk_distance
    else:
        extreme_price_raw = after_raw["low"].min()
        extreme_r_raw = (entry - extreme_price_raw) / risk_distance
        extreme_price = after["low"].min()
        extreme_r = (entry - extreme_price) / risk_distance

    last_candle_time = after["datetime"].iloc[-1]
    return {
        "tp2_time": tp2_time,
        "delay_to_tp2_hours": delay_to_tp2.total_seconds() / 3600,
        "horizon_limit": horizon_limit,
        "extreme_price": extreme_price,
        "extreme_r": extreme_r,
        "extreme_r_non_borne": extreme_r_raw,
        "n_candles_after_tp2": len(after),
        "last_candle_time": last_candle_time,
        "window_end": candles["datetime"].max(),
        "fenetre_tronquee": (last_candle_time >= candles["datetime"].max() - pd.Timedelta(hours=2)) and
                            (horizon_limit >= candles["datetime"].max()),
    }


def main():
    pop, _ = build_realistic_payoff_population(min_rr=MIN_RR_TP1, verbose=False)
    confirmed = pop[pop["payoff_bucket"] == "continuation_confirmee"].copy()
    print(f"Trades à continuation TP1->TP2 confirmée : {len(confirmed)}")

    confirmed["yahoo_symbol"] = confirmed["ticker"].apply(tpseq.ticker_to_yahoo_symbol)
    unique_symbols = sorted(confirmed["yahoo_symbol"].unique())

    candles_by_symbol = {}
    for symbol in unique_symbols:
        candles = tpseq.fetch_h1_history(symbol, confirmed["date_creation"].min().to_pydatetime(),
                                          pd.Timestamp.utcnow().tz_localize(None).to_pydatetime())
        if candles is not None and not candles.empty:
            candles_by_symbol[symbol] = candles

    results = []
    for _, row in confirmed.iterrows():
        candles = candles_by_symbol.get(row["yahoo_symbol"])
        if candles is None:
            results.append(None)
            continue
        results.append(compute_mfe_after_tp2(row, candles))

    res_df = pd.DataFrame(results)
    confirmed = confirmed.reset_index(drop=True)
    detail = pd.concat([confirmed[["ticker", "date_creation", "rr_tp2", "statut_final"]], res_df], axis=1)
    detail["additional_r"] = detail["extreme_r"] - detail["rr_tp2"]

    valid = detail[detail["extreme_r"].notna()].copy()
    print(f"Trades exploitables pour le MFE post-TP2 : {len(valid)}/{len(confirmed)}")

    n_significant = (valid["additional_r"] >= SIGNIFICANT_ADDITIONAL_R).sum()
    n_any_extra = (valid["additional_r"] > 0.05).sum()  # tolérance bruit de bougie

    print("\n" + "=" * 100)
    print(f"MFE APRÈS TP2 (R additionnels au-delà de rr_tp2), sur {len(valid)} trades")
    print("=" * 100)
    print(f"R additionnel moyen   : {valid['additional_r'].mean():+.3f} R")
    print(f"R additionnel médian  : {valid['additional_r'].median():+.3f} R")
    print(f"R additionnel max     : {valid['additional_r'].max():+.3f} R")
    print(f"Trades avec un extra > 0.05R (bruit exclu)     : {n_any_extra}/{len(valid)} ({n_any_extra/len(valid)*100:.1f}%)")
    print(f"Trades avec un extra SIGNIFICATIF (>= +{SIGNIFICANT_ADDITIONAL_R}R) : {n_significant}/{len(valid)} ({n_significant/len(valid)*100:.1f}%)")

    n_troncature = valid["fenetre_tronquee"].sum()
    print(f"\nTrades dont la fenêtre H1 s'arrête juste après tp2_time (MFE probablement SOUS-ESTIMÉ, "
          f"prix encore en mouvement à la fin des données) : {n_troncature}/{len(valid)} ({n_troncature/len(valid)*100:.1f}%)")

    print("\nDistribution complète des R additionnels :")
    print(valid["additional_r"].describe())

    # Impact potentiel sur l'EV globale (population brute 472 trades) si on captait
    # PARFAITEMENT le MFE (borne haute irréaliste -- un vrai trailing capte toujours
    # moins que le sommet exact) : juste pour cadrer l'ordre de grandeur de l'enjeu.
    total_pop_n = 472  # taille connue de la population totale (seuil 1.5, forex, terminaux)
    ev_gain_upper_bound = valid["additional_r"].sum() / total_pop_n
    print(f"\n[CADRAGE] Si on captait PARFAITEMENT ce MFE (borne haute irréaliste, un trailing réel "
          f"capte toujours moins) : gain d'EV sur la population totale ({total_pop_n} trades) = "
          f"{ev_gain_upper_bound:+.4f} R -- à comparer à l'EV réaliste actuelle de +0.822 R.")

    detail.to_csv("trailing_stop_vigilance_detail.csv", index=False)
    print("\nDétail enregistré dans trailing_stop_vigilance_detail.csv")
    return detail


if __name__ == "__main__":
    main()
