"""
Construit la population de trades avec slippage réel intégré (données Dukascopy,
469/472 trades mesurés, slippage_proxy_dukascopy_detail.csv), selon 2 méthodes :
  A. Slippage moyen PAR CLASSE de paire (JPY/USD/GBP/CHF/CAD) -- déterministe.
  B. Tirage dans la DISTRIBUTION EMPIRIQUE complète (469 valeurs mesurées,
     rééchantillonnées avec remise) -- capte la dispersion réelle, y compris les cas
     favorables (P95 +1.90 pip). MÉTHODE PRIMAIRE utilisée pour les Monte Carlo
     (plus réaliste que la moyenne seule, comme demandé).

Mécanique (par trade) :
  - Prix d'entrée AJUSTÉ = prix_entree ± slippage (buy: - slippage, sell: + slippage
    -- convention du slippage mesuré : négatif = défavorable, cf.
    slippage_proxy_dukascopy.py). Les 3 trades non mesurés (delta réseau) reçoivent
    aussi un tirage empirique (méthode B) / la moyenne de leur classe (méthode A).
  - Distance SL AJUSTÉE = |prix_entree_ajusté - stop_loss_init| (le niveau de stop
    lui-même ne bouge pas, seul le prix d'entrée réellement obtenu change -- donc la
    distance de risque effective change, et la taille de position nécessaire pour
    respecter le risque cible en % en dépend directement).
  - Le niveau de sortie (TP1/TP2/trailing/-SL) est RECONSTRUIT en prix absolu à
    partir du R original (r_trailing x distance_sl_originale + prix_entree) --
    hypothèse : le niveau de sortie réel ne change pas avec le slippage d'entrée
    (le trailing/TP/SL sont des niveaux de marché fixes, pas relatifs à l'entrée) --
    seule la distance parcourue DEPUIS l'entrée réelle change.
  - R ajusté = (niveau_sortie - prix_entree_ajusté) / distance_sl_ajustée (buy),
    signe inversé pour sell.
"""
import numpy as np
import pandas as pd

POP_PATH = "population_with_force.csv"
SLIPPAGE_DETAIL_PATH = "slippage_proxy_dukascopy_detail.csv"
SEED = 777

CLASS_MEAN_SLIPPAGE_PIPS = {
    "/JPY": -1.05, "/USD": -0.46, "/GBP": -0.85, "/CHF": -1.37, "/CAD": -1.23,
}


def _pip_size(ticker):
    return 0.01 if ticker.endswith("/JPY") else 0.0001


def _asset_class(ticker):
    for cls in CLASS_MEAN_SLIPPAGE_PIPS:
        if ticker.endswith(cls):
            return cls
    return "/USD"  # repli, ne devrait pas arriver sur les 14 tickers suivis


def build_adjusted_population(method="empirical"):
    """method: 'empirical' (tirage dans la distribution mesurée, méthode B -- primaire)
    ou 'class_mean' (moyenne par classe, méthode A)."""
    pop = pd.read_csv(POP_PATH)
    pop["date_creation"] = pd.to_datetime(pop["date_creation"])
    slip = pd.read_csv(SLIPPAGE_DETAIL_PATH)
    empirical_pips = slip["slippage_pips"].to_numpy()

    rng = np.random.default_rng(SEED)

    direction = np.where(pop["tp1_init"] > pop["prix_entree"], "buy", "sell")
    pip_sizes = pop["ticker"].apply(_pip_size).to_numpy()

    if method == "empirical":
        slippage_pips = rng.choice(empirical_pips, size=len(pop), replace=True)
    elif method == "class_mean":
        slippage_pips = pop["ticker"].apply(lambda t: CLASS_MEAN_SLIPPAGE_PIPS[_asset_class(t)]).to_numpy()
    else:
        raise ValueError(method)

    slippage_price = slippage_pips * pip_sizes

    prix_entree = pop["prix_entree"].to_numpy()
    stop_loss_init = pop["stop_loss_init"].to_numpy()
    original_sl_distance = np.abs(prix_entree - stop_loss_init)
    r_trailing = pop["r_trailing"].to_numpy()

    is_buy = direction == "buy"
    actual_entry = np.where(is_buy, prix_entree - slippage_price, prix_entree + slippage_price)
    adjusted_sl_distance = np.abs(actual_entry - stop_loss_init)

    # Niveau de sortie reconstruit (fixe, indépendant du slippage d'entrée)
    exit_price = np.where(is_buy,
                           prix_entree + r_trailing * original_sl_distance,
                           prix_entree - r_trailing * original_sl_distance)

    new_movement = np.where(is_buy, exit_price - actual_entry, actual_entry - exit_price)
    # Garde-fou : distance SL ajustée ne doit jamais s'effondrer à ~0 (slippage extrême
    # rarissime sur cette distribution -- cas non observé mais protégé numériquement)
    adjusted_sl_distance_safe = np.maximum(adjusted_sl_distance, original_sl_distance * 0.05)
    r_slippage = new_movement / adjusted_sl_distance_safe

    result = pop.copy()
    result["slippage_pips_applied"] = slippage_pips
    result["actual_entry"] = actual_entry
    result["original_sl_distance"] = original_sl_distance
    result["adjusted_sl_distance"] = adjusted_sl_distance_safe
    result["r_slippage"] = r_slippage
    result["direction"] = direction
    return result


if __name__ == "__main__":
    for method in ["empirical", "class_mean"]:
        adj = build_adjusted_population(method)
        print(f"\n--- Méthode: {method} ---")
        print(f"EV sans slippage (r_trailing)  : {adj['r_trailing'].mean():+.4f}R")
        print(f"EV avec slippage (r_slippage)   : {adj['r_slippage'].mean():+.4f}R")
        print(f"Delta EV : {adj['r_slippage'].mean() - adj['r_trailing'].mean():+.4f}R")
        adj.to_csv(f"slippage_adjusted_population_{method}.csv", index=False)
