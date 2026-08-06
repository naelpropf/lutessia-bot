"""
Moteur de simulation bougie par bougie (H1) du pyramiding : STOP CONSOLIDÉ UNIQUE pour
tout le paquet (unité initiale + ajouts) -- pas de stop indépendant par unité, décision
explicite de l'utilisateur. Étend AVANT TP2 le même principe de marche par bougie déjà
utilisé après TP2 (trailing_stop_variants.simulate_trailing), et se connecte à cette
règle déjà adoptée une fois TP2 atteint sur un trade à continuation confirmée, sans
jamais redescendre sous le stop pyramidé acquis (ratchet, jamais de recul).

Règle du stop consolidé (AVANT TP2) : à chaque palier d'ajout franchi (+0.5R, +1R, ...),
le stop de la position ENTIÈRE remonte à
    prix_entree_du_dernier_ajout - ATR_MULT * ATR_H1_courant   (LONG, symétrique en SHORT)
jamais en-dessous du stop déjà acquis. Une fois TP2 touché (continuation confirmée), le
stop bascule sur la règle déjà adoptée ailleurs dans ce projet (extremum favorable -
POST_TP2_TRAIL_MULT x distance SL initiale, cf. trailing_payoff_population.WINNING_CONFIGS
["trailing_distance_fixe_0.2x" -> ("fixed", 0.2)]).

Convention de déclenchement par bougie (même ordre conservateur que
trailing_stop_variants.simulate_trailing) : le stop COURANT est vérifié EN PREMIER --
il protège la bougie AVANT d'être remonté / avant tout autre événement (ajout, TP1, TP2)
sur cette même bougie.

Distinction cruciale gagnant/perdant sur les trades SANS continuation confirmée à TP2 :
- OBJECTIF ATTEINT (gagnant), continuation non confirmée -> sortie terminale à TP1 dès
  que touché (cohérent avec r_realiste = rr_tp1 pour ce cas).
- INVALIDÉE (perdant) -> AUCUNE sortie automatique à TP1 même si le prix le touche en
  chemin (le statut final confirme que le trade a continué au-delà, jusqu'au SL --
  cf. les cas "tp1_avant_sl" déjà présents dans tp_sequence_analysis.analyze_trade) : on
  continue simplement à marcher bougie par bougie (stop + ajouts) jusqu'à ce que le stop
  consolidé (qui ne peut être qu'AU-DESSUS ou égal au SL d'origine pour un LONG, jamais
  en-dessous) soit touché -- ce qui arrive nécessairement au plus tard au moment où le
  SL d'origine aurait été touché.

Restriction : seuls les trades `resolution_verifiee` (bougies H1 disponibles, TP1/SL
détectés par rr_threshold_test.build_extended_population) sont walkés bougie par bougie.
Les autres gardent leur comportement actuel (1 seule unité, R = r_realiste) -- même
logique prudente que le reste du projet sur les trades hors couverture historique.
"""
import pandas as pd

from trailing_stop_variants import compute_atr, HORIZON_MULTIPLIER, MAX_HORIZON_ABS

ATR_PERIOD = 14
ATR_MULT = 2.0
POST_TP2_TRAIL_MULT = 0.2  # règle déjà adoptée (trailing_distance_fixe_0.2x)


def _prep_candles(candles):
    if "atr" not in candles.columns:
        candles = compute_atr(candles, period=ATR_PERIOD)
    return candles.sort_values("datetime").reset_index(drop=True)


def simulate_pyramid_trade(row, candles, add_levels, add_fractions):
    """Retourne la liste des unités réellement ouvertes pour CE trade :
    [{"level_r": 0.0, "entry_price": ..., "fraction": 1.0, "exit_r": ...}, ...]
    Le exit_r de chaque unité est calculé par rapport à SA PROPRE entrée (pas l'entrée
    d'origine) -- une unité ajoutée à +0.5R qui sort au niveau +1R gagne +0.5R, pas +1R.

    Fallback (trade non `resolution_verifiee`, candles indisponibles, ou distance de
    risque nulle) : une seule unité, fraction 1.0, exit_r = row["r_realiste"] --
    comportement strictement identique à l'absence de pyramiding."""
    fallback = [{"level_r": 0.0, "entry_price": row["prix_entree"], "fraction": 1.0,
                 "exit_r": row["r_realiste"]}]

    if not bool(row.get("resolution_verifiee", False)) or candles is None or candles.empty:
        return fallback

    entry = row["prix_entree"]
    sl = row["stop_loss_init"]
    tp1 = row["tp1_init"]
    tp2 = row["tp2_init"]
    risk_distance = abs(entry - sl)
    if risk_distance <= 0:
        return fallback

    is_long = tp1 > entry
    sign = 1 if is_long else -1
    is_winner = row["statut_final"] == "OBJECTIF ATTEINT"
    continuation_allowed = row.get("payoff_bucket") == "continuation_confirmee"

    candles = _prep_candles(candles)
    creation = row["date_creation"]
    # Pas de troncature amont arbitraire : la marche s'arrête d'elle-même (stop touché,
    # sortie TP1, ou horizon post-TP2 borné plus bas) -- même principe que
    # trailing_stop_variants, qui part de la même fenêtre complète.
    window = candles[candles["datetime"] >= creation].reset_index(drop=True)
    if window.empty:
        return fallback

    add_price_levels = [entry + sign * lvl * risk_distance for lvl in add_levels]

    units = [{"level_r": 0.0, "entry_price": entry, "fraction": 1.0}]
    next_add_idx = 0
    stop = sl
    # Le stop consolidé n'est vérifiable dès le départ QUE sur les trades PERDANTS
    # (INVALIDÉE) -- c'est littéralement ainsi que la perte se matérialise (cohérent avec
    # r_realiste = -1.0 en l'absence de tout ajout). Sur un trade GAGNANT, le stop ne
    # devient actif qu'APRÈS le premier événement qui le fait bouger (1er ajout, ou passage
    # en phase post-TP2) : avant ça, l'unité initiale seule doit se comporter EXACTEMENT
    # comme la convention déjà adoptée dans tout le reste du projet (r_realiste, qui ne
    # vérifie jamais si le SL d'origine a été transitoirement effleuré avant TP1 sur un
    # trade OBJECTIF ATTEINT -- le statut final de Lutessia fait foi). Sans ce garde-fou,
    # une simple mèche H1 sur le SL d'origine, même sur un trade gagnant confirmé,
    # déclencherait une sortie que le reste du projet ignore -- écart détecté par
    # comparaison directe avec trailing_payoff_population.r_trailing
    # (cf. scratch_pyramid_vs_trailing_parity.py).
    stop_active = not is_winner
    phase = "pre_tp2"
    extreme = None  # extremum favorable, utilisé seulement en phase post-TP2
    horizon_limit = None  # borne temporelle post-TP2, cf. trailing_stop_variants
    exit_price = None

    def ratchet(candidate):
        nonlocal stop, stop_active
        stop = max(stop, candidate) if is_long else min(stop, candidate)
        stop_active = True

    last_close = None
    for _, candle in window.iterrows():
        # borne d'horizon post-TP2 (même règle que trailing_stop_variants.simulate_trailing :
        # min(3x délai création->TP2, 30 jours)) -- évite de mesurer une dérive de prix sans
        # rapport avec une position réellement tenue ouverte (cf. trailing_stop_vigilance_check.py).
        if phase == "post_tp2" and horizon_limit is not None and candle["datetime"] > horizon_limit:
            exit_price = last_close
            break

        # 1. le stop consolidé courant est vérifié EN PREMIER (convention conservatrice),
        #    mais seulement s'il a déjà été activé par un ajout ou le passage post-TP2.
        if stop_active and ((candle["low"] <= stop) if is_long else (candle["high"] >= stop)):
            exit_price = stop
            break

        if phase == "pre_tp2":
            # 2. paliers d'ajout non encore déclenchés, dans l'ordre croissant.
            stop_hit_on_add = False
            while next_add_idx < len(add_price_levels):
                lvl_price = add_price_levels[next_add_idx]
                triggered = (candle["high"] >= lvl_price) if is_long else (candle["low"] <= lvl_price)
                if not triggered:
                    break
                atr_now = candle["atr"] if candle["atr"] and candle["atr"] > 0 else risk_distance * 0.1
                ratchet(lvl_price - sign * ATR_MULT * atr_now)
                units.append({
                    "level_r": add_levels[next_add_idx], "entry_price": lvl_price,
                    "fraction": add_fractions[next_add_idx],
                })
                next_add_idx += 1
                # le stop vient de remonter : revérifier que CETTE bougie ne le franchit
                # pas déjà (même convention conservatrice qu'à l'étape 1).
                if (candle["low"] <= stop) if is_long else (candle["high"] >= stop):
                    exit_price = stop
                    stop_hit_on_add = True
                    break
            if stop_hit_on_add:
                break

            if is_winner:
                if continuation_allowed:
                    # 3. continuation confirmée + TP2 touché -> bascule en phase post-TP2,
                    #    reprend la règle déjà adoptée (extremum - 0.2xSL).
                    tp2_touched = (candle["high"] >= tp2) if is_long else (candle["low"] <= tp2)
                    if tp2_touched:
                        phase = "post_tp2"
                        extreme = max(tp2, candle["high"]) if is_long else min(tp2, candle["low"])
                        ratchet(extreme - sign * POST_TP2_TRAIL_MULT * risk_distance)
                        delay_to_tp2 = candle["datetime"] - creation
                        horizon_limit = candle["datetime"] + min(HORIZON_MULTIPLIER * delay_to_tp2, MAX_HORIZON_ABS)
                        last_close = candle["close"]
                        continue
                else:
                    # 4. pas de continuation confirmée -> sortie terminale à TP1.
                    tp1_touched = (candle["high"] >= tp1) if is_long else (candle["low"] <= tp1)
                    if tp1_touched:
                        exit_price = tp1
                        break
            # perdant (INVALIDÉE) : aucune sortie automatique à TP1 même si touché en
            # chemin -- on continue simplement à marcher (stop + ajouts) bougie par
            # bougie jusqu'au stop consolidé.

        else:  # phase == "post_tp2" : reprend la règle déjà adoptée (extremum - 0.2xSL)
            new_extreme = candle["high"] if is_long else candle["low"]
            if (new_extreme > extreme) if is_long else (new_extreme < extreme):
                extreme = new_extreme
                ratchet(extreme - sign * POST_TP2_TRAIL_MULT * risk_distance)

        last_close = candle["close"]

    if exit_price is None:
        # horizon des données épuisé sans déclenchement (ou horizon post-TP2 atteint sans
        # sortie détectée dans la boucle) -> dernière clôture connue -- jamais le sommet,
        # même convention que trailing_stop_variants (évite l'erreur du MFE non borné).
        exit_price = last_close if last_close is not None else window["close"].iloc[-1]

    result = []
    for u in units:
        exit_r = (exit_price - u["entry_price"]) / risk_distance if is_long \
            else (u["entry_price"] - exit_price) / risk_distance
        result.append({**u, "exit_r": exit_r})
    return result
