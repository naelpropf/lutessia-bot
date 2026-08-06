"""
Wrapper autour du package MetaTrader5 : connexion, positions ouvertes, exécution
d'ordre au marché, suivi de clôture.

Config via .env (voir .env.example) : compte de base MT5_LOGIN/MT5_PASSWORD/
MT5_SERVER/MT5_ACCOUNT_ID (sans suffixe, ex: FTMO), puis MT5_LOGIN_2/MT5_PASSWORD_2/
MT5_SERVER_2/MT5_ACCOUNT_ID_2 pour un 2e compte (ex: The5%ers), _3 pour un 3e (ex:
Blueberry Funded), etc. MT5_ACCOUNT_ID(_n) est un identifiant libre utilisé dans
trades_reels.csv / le routage, distinct du login MT5 lui-même.

Étendu (2026-07-30) pour la flotte copytrade à 3 comptes : `load_accounts()` charge
maintenant TOUS les comptes configurés dans .env (au lieu d'un seul), le compte de
base restant rétrocompatible sans suffixe. Un compte non encore configuré (login/
password/server manquant) est simplement absent de la liste retournée -- permet de
démarrer avec seulement le compte FTMO actif, et d'ajouter The5%ers/Blueberry Funded
plus tard en complétant juste .env, sans toucher au code. Chaque fonction continue de
prendre un objet compte explicite : la logique de connexion/ordre/positions/capital
initial est déjà par-compte (state persisté par account.account_id), donc rien
d'autre à changer ici pour gérer plusieurs comptes.
"""
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import MetaTrader5 as mt5

# Ré-exportés pour que les modules appelants (trade_logger.py) n'aient pas besoin
# d'importer MetaTrader5 directement -- app_mt5.py reste le seul point de contact
# avec le package MT5 (cf. structure existante : primitives ici, logique métier
# dans app.py/trade_logger.py).
POSITION_TYPE_BUY = mt5.POSITION_TYPE_BUY
POSITION_TYPE_SELL = mt5.POSITION_TYPE_SELL

DRAWDOWN_STATE_PATH = Path("account_risk_state.json")
# Moitié du seuil de clôture prop firm typique (10%) — cf. instructions : "5-6%".
DRAWDOWN_PAUSE_THRESHOLD_PCT = 5.0
# Avertissement précoce (pas une pause) pour anticiper avant le seuil de pause ci-dessus.
DRAWDOWN_WARNING_THRESHOLD_PCT = 3.0
# % du capital INITIAL (fixe) risqué par trade — jamais recalculé sur l'équité courante,
# cohérent avec la méthode de calcul du drawdown des prop firms (FTMO, The5%ers, Alpha
# Capital) déjà utilisée par check_drawdown() ci-dessous.
RISK_PCT_PER_TRADE = 0.5


@dataclass
class MT5Account:
    account_id: str
    login: int
    password: str
    server: str


def _load_single_account(suffix, default_account_id):
    login = os.environ.get(f"MT5_LOGIN{suffix}")
    password = os.environ.get(f"MT5_PASSWORD{suffix}")
    server = os.environ.get(f"MT5_SERVER{suffix}")
    account_id = os.environ.get(f"MT5_ACCOUNT_ID{suffix}", default_account_id)

    if not login or not password or not server:
        return None
    return MT5Account(account_id=account_id, login=int(login), password=password, server=server)


def load_accounts():
    """Charge TOUS les comptes MT5 configurés dans .env : le compte de base (sans
    suffixe, MT5_LOGIN/MT5_PASSWORD/MT5_SERVER/MT5_ACCOUNT_ID) puis MT5_LOGIN_2/...,
    MT5_LOGIN_3/... dans l'ordre, en s'arrêtant au premier numéro totalement absent.
    Retourne une liste (peut contenir 0, 1, 2 ou 3+ comptes selon ce qui est réellement
    configuré) -- un compte incomplet ou manquant est simplement omis, pas une erreur."""
    accounts = []

    base = _load_single_account("", "compte_1")
    if base is not None:
        accounts.append(base)

    i = 2
    while True:
        account = _load_single_account(f"_{i}", f"compte_{i}")
        if account is None:
            break
        accounts.append(account)
        i += 1

    return accounts


def connect(account):
    """Connecte le terminal MT5 local au compte donné. Retourne True/False.

    Vérifie explicitement, après coup, que le compte réellement actif (account_info().login)
    correspond bien à celui demandé -- constaté empiriquement le 2026-08-06 : quand le
    terminal est déjà connecté à un autre compte (partagé entre tous les comptes de la
    flotte copytrade), mt5.initialize(login=..., server=...) peut retourner True sans
    avoir réellement basculé de compte, laissant silencieusement la session précédente
    active. Sans cette vérification, la flotte à plusieurs comptes pourrait exécuter un
    ordre en croyant être sur un compte alors qu'elle est restée sur un autre (doublon,
    mauvaise taille de position calculée sur le mauvais capital initial). Si le premier
    essai n'a pas basculé, on force un mt5.login() explicite avant d'abandonner."""
    if not mt5.initialize(login=account.login, password=account.password, server=account.server):
        print(f"[MT5] Échec de connexion au compte {account.account_id} : {mt5.last_error()}")
        return False

    info = mt5.account_info()
    if info is None or info.login != account.login:
        if not mt5.login(login=account.login, password=account.password, server=account.server):
            print(f"[MT5] Échec de bascule vers le compte {account.account_id} : {mt5.last_error()}")
            return False
        info = mt5.account_info()
        if info is None or info.login != account.login:
            actual = info.login if info else None
            print(f"[MT5] Échec de bascule vers le compte {account.account_id} : "
                  f"compte actif resté {actual} après tentative de connexion.")
            return False

    return True


def disconnect():
    mt5.shutdown()


def get_open_positions(symbol=None):
    """Positions ouvertes sur le compte actuellement connecté (toutes, ou filtrées par symbole)."""
    positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
    return list(positions) if positions is not None else []


def count_open_positions():
    return len(get_open_positions())


def _ensure_symbol_visible(symbol):
    """S'assure que le symbole est sélectionné dans le Market Watch du terminal --
    condition nécessaire pour que symbol_info_tick() retourne une cotation. Constaté
    le 07/08 sur EURCHF : symbol_info() existe (visible=False) mais symbol_info_tick()
    reste None tant que symbol_select() n'a pas été appelé une fois. N'importe quelle
    paire suivie mais jamais encore tradée sur ce compte peut retomber dans ce piège."""
    info = mt5.symbol_info(symbol)
    if info is not None and not info.visible:
        mt5.symbol_select(symbol, True)


def calculate_position_size(account, symbol, sl_price, risk_pct=RISK_PCT_PER_TRADE):
    """Taille de position (en lots) pour risquer risk_pct% du capital INITIAL fixe du
    compte (get_initial_capital — jamais l'équité courante), si le SL est touché.
    Retourne None si le calcul est impossible (symbole/cotation introuvable, capital
    initial inconnu, distance SL nulle...) — l'appelant doit alors ignorer le signal
    plutôt que d'exécuter avec une taille par défaut arbitraire."""
    initial_capital = get_initial_capital(account)
    if not initial_capital:
        print(f"[risk] Capital initial introuvable pour {account.account_id}.")
        return None

    _ensure_symbol_visible(symbol)
    tick = mt5.symbol_info_tick(symbol)
    symbol_info = mt5.symbol_info(symbol)
    if tick is None or symbol_info is None:
        print(f"[risk] Symbole introuvable pour le calcul de taille de position : {symbol}")
        return None

    # Prix indicatif pré-trade ; le fill réel (place_market_order) peut différer
    # légèrement (spread/slippage normal entre le calcul et l'exécution).
    entry_price_estimate = tick.ask if symbol_info.trade_tick_size else None
    if not entry_price_estimate or symbol_info.trade_tick_size == 0:
        return None

    sl_distance = abs(entry_price_estimate - sl_price)
    if sl_distance == 0:
        print(f"[risk] Distance SL nulle pour {symbol} : impossible de dimensionner la position.")
        return None

    risk_amount = initial_capital * (risk_pct / 100)
    loss_per_lot = (sl_distance / symbol_info.trade_tick_size) * symbol_info.trade_tick_value
    if loss_per_lot <= 0:
        return None

    volume = risk_amount / loss_per_lot

    step = symbol_info.volume_step or 0.01
    volume = round(volume / step) * step
    volume = max(symbol_info.volume_min, min(symbol_info.volume_max, volume))
    return round(volume, 2)


def place_market_order(symbol, direction, sl, tp, volume, comment="lutessia-bot"):
    """Passe un ordre au marché avec SL/TP. direction: 'buy' ou 'sell'.
    Retourne (success: bool, fill_price: float | None, ticket: int | None, raw_result)."""
    _ensure_symbol_visible(symbol)
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        print(f"[MT5] Symbole introuvable ou pas de cotation : {symbol}")
        return False, None, None, None

    order_type = mt5.ORDER_TYPE_BUY if direction == "buy" else mt5.ORDER_TYPE_SELL
    price = tick.ask if direction == "buy" else tick.bid

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result is None:
        print(f"[MT5] order_send() a retourné None : {mt5.last_error()}")
        return False, None, None, None

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"[MT5] Échec d'exécution ({result.retcode}) : {result.comment}")
        return False, None, None, result

    return True, result.price, result.order, result


def get_open_position_raw(ticket):
    """Position brute (objet MT5 complet : price_current, sl, tp, type, symbol...),
    contrairement à get_position_status() qui ne retourne qu'un statut résumé. Utilisé
    par le trailing stop post-TP2 (trade_logger.manage_trailing_stops), qui a besoin
    du prix courant et du SL actuellement en place sur le broker pour décider s'il
    faut resserrer. Retourne None si la position n'est plus ouverte."""
    positions = mt5.positions_get(ticket=ticket)
    return positions[0] if positions else None


def modify_position_sltp(ticket, symbol, sl, tp):
    """Modifie le SL et/ou le TP d'une position déjà ouverte (TRADE_ACTION_SLTP,
    par opposition à TRADE_ACTION_DEAL qui ouvre/ferme une position). Utilisé par le
    trailing stop pour resserrer le SL au fil du prix. tp=0.0 désactive le TP fixe
    (nécessaire une fois le trailing armé : sinon le TP fixe fermerait la position
    à ce niveau avant que le trailing n'ait la moindre chance d'agir).
    Retourne True/False."""
    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": ticket,
        "symbol": symbol,
        "sl": sl,
        "tp": tp,
    }
    result = mt5.order_send(request)
    if result is None:
        print(f"[MT5] modify_position_sltp() order_send() a retourné None pour le ticket {ticket} : {mt5.last_error()}")
        return False
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"[MT5] Échec de modification SL/TP ({result.retcode}) pour le ticket {ticket} : {result.comment}")
        return False
    return True


def get_position_status(ticket):
    """Statut d'une position par ticket : 'ouverte', 'objectif_atteint', 'invalidee'
    ou 'introuvable', avec le prix de clôture réel si close (via l'historique des deals)."""
    positions = mt5.positions_get(ticket=ticket)
    if positions:
        return "ouverte", None

    deals = mt5.history_deals_get(position=ticket)
    if not deals:
        return "introuvable", None

    closing_deals = [d for d in deals if d.entry == mt5.DEAL_ENTRY_OUT]
    if not closing_deals:
        return "introuvable", None

    close_deal = closing_deals[-1]
    close_price = close_deal.price
    statut = "OBJECTIF ATTEINT" if close_deal.profit >= 0 else "INVALIDÉE"
    return statut, close_price


# --- Pause opérationnelle par compte, basée sur le drawdown réel (jamais sur un
# compteur de pertes consécutives — une série de 4-5 pertes est statistiquement
# normale même avec un edge sain). La pause bloque les NOUVELLES entrées sur le
# compte concerné (cf. account_router.select_account) mais ne touche jamais aux
# positions déjà ouvertes. Levée uniquement manuelle (resume_account), jamais
# automatique même si l'équité remonte au-dessus du seuil. ---

def _load_risk_state():
    if DRAWDOWN_STATE_PATH.exists():
        with open(DRAWDOWN_STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_risk_state(state):
    with open(DRAWDOWN_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def is_account_paused(account_id):
    return _load_risk_state().get(account_id, {}).get("paused", False)


def get_initial_capital(account):
    """Capital initial du compte, figé à la toute première observation puis persisté
    — jamais recalculé sur l'équité courante. Source unique utilisée à la fois par
    check_drawdown() (méthode FTMO/The5%ers/Alpha Capital : drawdown % du capital
    initial fixe) et calculate_position_size() (risque % du même capital fixe),
    pour garantir que les deux ne divergent jamais sur "quel est le capital de
    référence" du compte."""
    state = _load_risk_state()
    account_state = state.get(account.account_id)
    if account_state is not None:
        return account_state["initial_capital"]

    info = mt5.account_info()
    if info is None:
        return None

    state[account.account_id] = {
        "initial_capital": info.balance,
        "peak_equity": info.balance,
        "paused": False,
        "paused_at": None,
        "paused_reason": None,
    }
    _save_risk_state(state)
    return info.balance


def resume_account(account_id):
    """Lève manuellement la pause d'un compte, après vérification humaine — jamais
    appelé automatiquement par le bot. Usage : `python app_mt5.py --resume compte_1`."""
    state = _load_risk_state()
    if account_id not in state:
        print(f"[risk] Compte {account_id} inconnu dans {DRAWDOWN_STATE_PATH} : rien à lever.")
        return False
    state[account_id]["paused"] = False
    state[account_id]["paused_at"] = None
    state[account_id]["paused_reason"] = None
    _save_risk_state(state)
    print(f"[risk] Pause levée manuellement pour {account_id}.")
    return True


def check_drawdown(account):
    """Met à jour le peak equity et le statut de pause du compte, à partir de son
    équité actuelle (positions ouvertes incluses — équité flottante, pas le solde).
    drawdown_pct = (peak_equity - equity_actuelle) / capital_initial * 100.
    capital_initial est capturé une seule fois (première observation pour ce compte)
    et persisté ; peak_equity est le plus haut jamais observé depuis.

    Retourne (drawdown_pct, just_paused). Ne déclenche aucune alerte ici : ce module
    reste un client MT5 pur, sans dépendance à Telegram — c'est à l'appelant (app.py)
    de notifier si just_paused est True."""
    info = mt5.account_info()
    if info is None:
        return None, False

    initial_capital = get_initial_capital(account)
    if not initial_capital:
        return None, False

    state = _load_risk_state()
    account_state = state[account.account_id]

    if info.equity > account_state["peak_equity"]:
        account_state["peak_equity"] = info.equity

    drawdown_pct = (account_state["peak_equity"] - info.equity) / initial_capital * 100

    just_paused = False
    if drawdown_pct >= DRAWDOWN_PAUSE_THRESHOLD_PCT and not account_state["paused"]:
        account_state["paused"] = True
        account_state["paused_at"] = datetime.now(timezone.utc).isoformat()
        account_state["paused_reason"] = f"Drawdown {drawdown_pct:.2f}% >= seuil {DRAWDOWN_PAUSE_THRESHOLD_PCT}%"
        just_paused = True

    _save_risk_state(state)
    return drawdown_pct, just_paused


def check_drawdown_warning(account):
    """Avertissement précoce (jamais une pause) dès que le drawdown dépasse
    DRAWDOWN_WARNING_THRESHOLD_PCT (3%), pour anticiper avant le seuil de pause
    DRAWDOWN_PAUSE_THRESHOLD_PCT (5%). Contrairement à la pause, se réarme tout seul
    si le drawdown repasse sous le seuil — pas de levée manuelle nécessaire, c'est un
    signal informatif appelé depuis monitor.py, pas un contrôle de risque dur (déjà
    couvert par check_drawdown()/is_account_paused()).
    Retourne (drawdown_pct, should_warn)."""
    info = mt5.account_info()
    if info is None:
        return None, False

    initial_capital = get_initial_capital(account)
    if not initial_capital:
        return None, False

    state = _load_risk_state()
    account_state = state[account.account_id]

    if info.equity > account_state["peak_equity"]:
        account_state["peak_equity"] = info.equity

    drawdown_pct = (account_state["peak_equity"] - info.equity) / initial_capital * 100

    already_warned = account_state.get("early_warning_sent", False)
    should_warn = False
    if drawdown_pct >= DRAWDOWN_WARNING_THRESHOLD_PCT and not already_warned:
        account_state["early_warning_sent"] = True
        should_warn = True
    elif drawdown_pct < DRAWDOWN_WARNING_THRESHOLD_PCT and already_warned:
        account_state["early_warning_sent"] = False

    _save_risk_state(state)
    return drawdown_pct, should_warn


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Utilitaires de gestion des comptes MT5.")
    parser.add_argument("--resume", metavar="ACCOUNT_ID", help="Lève manuellement la pause drawdown d'un compte.")
    args = parser.parse_args()

    if args.resume:
        resume_account(args.resume)
    else:
        parser.print_help()
