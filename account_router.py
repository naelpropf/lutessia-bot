"""
Détermine, parmi les comptes MT5 disponibles, lesquels sont ÉLIGIBLES pour un nouveau
signal : exclut les comptes en pause drawdown (cf. app_mt5.check_drawdown), ceux ayant
déjà >= MAX_POSITIONS_PER_ACCOUNT positions ouvertes, et ceux ayant une position ouverte
sur un actif corrélé (|r| > CORRELATION_THRESHOLD, OU règle JPY-JPY explicite -- deux
paires JPY toujours exclues entre elles indépendamment du coefficient calculé) à l'actif
du signal.

Structure COPYTRADE (2026-07-30) : le même signal est tenté INDÉPENDAMMENT sur CHAQUE
compte éligible (3 comptes/3 firms distinctes), pas routé vers un seul -- cf.
eligible_accounts(), utilisée par app.py.executer_signal_reel(). select_account() est
conservé pour compatibilité (retourne le compte le moins chargé parmi les éligibles, ou
None) mais n'est plus utilisé par le pipeline principal.

CORRECTIF (audit du 2026-07-30) : ce module utilisait ses propres constantes
(plafond 2, seuil 0.5, pas de règle JPY) restées désynchronisées des paramètres
validés par tout le backtest (plafond 3, seuil 0.6 + JPY-JPY, cf.
scaling_simulation.py) -- jamais mis à jour après leur verrouillage. Corrigé en
réimportant directement MAX_POSITIONS/CORR_THRESHOLD/correlated depuis
scaling_simulation.py (source unique de vérité) plutôt que de dupliquer des
constantes locales, pour que ce fichier ne puisse plus diverger silencieusement des
simulations de référence à l'avenir.

SÉQUENCE DE LANCEMENT VERROUILLÉE (session du 06-07/08/2026, cf.
contexte_projet_lutessia_2026-08-07-v3.md section 2) : Blueberry Funded (palier
réduit 25k$) SEULE au jour 0 -- pas FTMO, dont le format inclut nativement 2
comptes et double donc l'exposition day0 sans bénéfice de vitesse mesurable. Le
reste de la flotte (FTMO, The5%ers, Goat Funded Trader, FundedNext si activée) est
ouvert TOUS ENSEMBLE dès le premier financement Blueberry -- déclencheur
ÉVÉNEMENTIEL uniquement (jamais un délai calendaire fixe ni un seuil de réserve,
les deux étant dominés par l'événementiel dans les tests). L'ouverture des comptes
(achat du challenge, ajout des identifiants MT5 dans .env) reste une action MANUELLE
de l'opérateur -- ce module ne l'automatise pas, seul le ROUTAGE des signaux vers
les comptes déjà connectés est géré ici. Cette note documente l'ordre attendu pour
guider l'opérateur, pas un comportement du code.

⚠️ Le plafond de risque personnel (règle hybride "avance jusqu'à un plafond, puis
attente", cf. contexte v3 section 0.2-0.3) est une politique de gestion de la
réserve/trésorerie personnelle, PAS une fonctionnalité du bot -- aucun module de ce
projet ne suit ni n'automatise l'état de la réserve poolée ou les rachats de
challenge ; c'est un processus manuel externe au code. Les chiffres de profit
utilisés dans les simulations de référence restent BRUTS (split prop firm et
fiscalité non encore intégrés, cf. contexte v3 section 0.1).
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


def eligible_accounts(ticker, accounts, corr_matrix=None):
    """ticker : actif du signal entrant (ex: 'EUR/USD'). accounts : liste de MT5Account.
    Retourne la liste de TOUS les comptes éligibles (triée par nombre de positions
    ouvertes croissant), chacun évalué INDÉPENDAMMENT sur SES PROPRES positions --
    utilisée par le mode copytrade (app.py) pour tenter le signal sur chaque compte
    éligible, pas un seul. Liste vide si aucun compte n'est éligible."""
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

            # Plafond overridable par compte (cf. MT5Account.max_positions, None =
            # utiliser le défaut global MAX_POSITIONS_PER_ACCOUNT) -- ajouté le 15/08
            # pour compte_blueberry : ce compte sert à collecter un maximum de données
            # d'exécution, plafond relevé très haut via MT5_MAX_POSITIONS{suffix}
            # dans .env pour ne quasiment plus jamais bloquer un signal.
            account_max_positions = (
                account.max_positions if account.max_positions is not None
                else MAX_POSITIONS_PER_ACCOUNT
            )
            if n_positions >= account_max_positions:
                continue

            # Les symboles MT5 (ex: "EURUSD", ou "EURUSD.pi" chez un broker qui suffixe
            # -- cf. MT5Account.symbol_suffix) n'ont pas le "/" du ticker Lutessia : on
            # retire le suffixe PROPRE à ce compte pour comparer sur la forme brute
            # commune aux deux univers. Corrigé le 10/08 : avant ce fix, la comparaison
            # échouait systématiquement sur tout compte à suffixe (ex: BlueBerry),
            # rendant l'exclusion par corrélation totalement inopérante sur ces comptes.
            open_symbols = {account.strip_symbol_suffix(p.symbol) for p in positions}
            correlated_no_slash = {c.replace("/", "") for c in excluded_tickers}
            if open_symbols & correlated_no_slash:
                continue

            eligible.append((account, n_positions))
        finally:
            app_mt5.disconnect()

    eligible.sort(key=lambda x: x[1])
    return [account for account, _ in eligible]


def select_account(ticker, accounts, corr_matrix=None):
    """Conservé pour compatibilité (retourne le compte le moins chargé parmi les
    éligibles, ou None) -- le pipeline principal (app.py, copytrade) utilise désormais
    eligible_accounts() pour tenter le signal sur TOUS les comptes éligibles."""
    elig = eligible_accounts(ticker, accounts, corr_matrix)
    return elig[0] if elig else None
