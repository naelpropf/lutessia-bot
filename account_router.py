"""
Sélectionne, parmi les comptes MT5 disponibles, celui qui doit prendre un nouveau
signal : exclut les comptes en pause drawdown (cf. app_mt5.check_drawdown), ceux
ayant déjà >= 2 positions ouvertes, et ceux ayant une position ouverte sur un actif
corrélé (|r| > CORRELATION_THRESHOLD) à l'actif du signal, puis choisit celui avec
le moins de positions ouvertes (0 en priorité). Retourne None si aucun compte n'est
éligible : le signal est alors ignoré.
"""
import pandas as pd

import app_mt5

MAX_POSITIONS_PER_ACCOUNT = 2
CORRELATION_THRESHOLD = 0.5
CORRELATION_MATRIX_PATH = "correlation_matrix.csv"


def load_correlation_matrix():
    return pd.read_csv(CORRELATION_MATRIX_PATH, index_col=0)


def _correlated_tickers(ticker, corr_matrix):
    if ticker not in corr_matrix.columns:
        return set()
    row = corr_matrix[ticker].drop(labels=[ticker], errors="ignore")
    return set(row[row.abs() > CORRELATION_THRESHOLD].index)


def select_account(ticker, accounts, corr_matrix=None):
    """ticker : actif du signal entrant (ex: 'EUR/USD'). accounts : liste de MT5Account.
    Retourne le compte choisi (MT5Account) ou None si aucun n'est éligible."""
    if corr_matrix is None:
        corr_matrix = load_correlation_matrix()

    correlated = _correlated_tickers(ticker, corr_matrix)

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
            correlated_no_slash = {c.replace("/", "") for c in correlated}
            if open_symbols & correlated_no_slash:
                continue

            eligible.append((account, n_positions))
        finally:
            app_mt5.disconnect()

    if not eligible:
        return None

    eligible.sort(key=lambda x: x[1])
    return eligible[0][0]
