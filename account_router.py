"""
Sélectionne, parmi les comptes MT5 disponibles, celui qui doit prendre un nouveau
signal : exclut les comptes en pause drawdown (cf. app_mt5.check_drawdown), ceux
ayant déjà >= MAX_POSITIONS_PER_ACCOUNT positions ouvertes, et ceux ayant une position
ouverte sur un actif corrélé (|r| > CORRELATION_THRESHOLD, OU règle JPY-JPY explicite --
deux paires JPY toujours exclues entre elles indépendamment du coefficient calculé) à
l'actif du signal, puis choisit celui avec le moins de positions ouvertes (0 en
priorité). Retourne None si aucun compte n'est éligible : le signal est alors ignoré.

CORRECTIF (audit du 2026-07-30) : ce module utilisait ses propres constantes
(plafond 2, seuil 0.5, pas de règle JPY) restées désynchronisées des paramètres
validés par tout le backtest (plafond 3, seuil 0.6 + JPY-JPY, cf.
scaling_simulation.py) -- jamais mis à jour après leur verrouillage. Corrigé en
réimportant directement MAX_POSITIONS/CORR_THRESHOLD/correlated depuis
scaling_simulation.py (source unique de vérité) plutôt que de dupliquer des
constantes locales, pour que ce fichier ne puisse plus diverger silencieusement des
simulations de référence à l'avenir.
"""
import pandas as pd

import app_mt5
from scaling_simulation import CORR_THRESHOLD, MAX_POSITIONS, correlated

MAX_POSITIONS_PER_ACCOUNT = MAX_POSITIONS  # 3, cf. scaling_simulation.py
CORRELATION_THRESHOLD = CORR_THRESHOLD  # 0.6, cf. scaling_simulation.py
CORRELATION_MATRIX_PATH = "correlation_matrix.csv"


def load_correlation_matrix():
    return pd.read_csv(CORRELATION_MATRIX_PATH, index_col=0)


def _correlated_tickers(ticker, corr_matrix):
    """Tickers exclus pour ce signal : corrélation > CORRELATION_THRESHOLD OU règle
    JPY-JPY explicite -- réutilise scaling_simulation.correlated telle quelle (même
    fonction que celle validée par tout le backtest), pour garantir que le routage live
    se comporte EXACTEMENT comme les simulations de référence."""
    if ticker not in corr_matrix.columns:
        return set()
    others = [t for t in corr_matrix.columns if t != ticker]
    return {t for t in others if correlated(ticker, t, corr_matrix)}


def select_account(ticker, accounts, corr_matrix=None):
    """ticker : actif du signal entrant (ex: 'EUR/USD'). accounts : liste de MT5Account.
    Retourne le compte choisi (MT5Account) ou None si aucun n'est éligible."""
    if corr_matrix is None:
        corr_matrix = load_correlation_matrix()

    excluded_tickers = _correlated_tickers(ticker, corr_matrix)

    eligible = []
    for account in accounts:
        if app_mt5.is_account_paused(account.account_id):
            continue

        if not app_mt5.connect(account):
            continue
        try:
            positions = app_mt5.get_open_positions()
            n_positions = len(positions)

            if n_positions >= MAX_POSITIONS_PER_ACCOUNT:
                continue

            open_symbols = {p.symbol for p in positions}
            # Les symboles MT5 (ex: "EURUSD") n'ont pas le "/" du ticker Lutessia :
            # on compare sur la forme sans séparateur pour matcher les deux univers.
            correlated_no_slash = {c.replace("/", "") for c in excluded_tickers}
            if open_symbols & correlated_no_slash:
                continue

            eligible.append((account, n_positions))
        finally:
            app_mt5.disconnect()

    if not eligible:
        return None

    eligible.sort(key=lambda x: x[1])
    return eligible[0][0]
