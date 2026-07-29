"""
Wrapper autour du package MetaTrader5 : connexion, positions ouvertes, exécution
d'ordre au marché, suivi de clôture.

Config via .env (voir .env.example) : MT5_LOGIN, MT5_PASSWORD, MT5_SERVER,
MT5_ACCOUNT_ID (identifiant libre utilisé dans trades_reels.csv / le routage,
distinct du login MT5 lui-même).

Structuré pour n'accueillir qu'un seul compte aujourd'hui, mais chaque fonction
prend un objet compte explicite : ajouter des comptes plus tard (ex: MT5_LOGIN_2,
MT5_PASSWORD_2, MT5_SERVER_2, MT5_ACCOUNT_ID_2...) ne demandera que d'étendre
`load_accounts()`, pas de changer la logique de connexion/ordre/positions.
"""
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import MetaTrader5 as mt5

DRAWDOWN_STATE_PATH = Path("account_risk_state.json")
# Moitié du seuil de clôture prop firm typique (10%) — cf. instructions : "5-6%".
DRAWDOWN_PAUSE_THRESHOLD_PCT = 5.0
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


def load_accounts():
    """Charge les comptes MT5 depuis .env. Un seul compte pour l'instant
    (MT5_LOGIN/MT5_PASSWORD/MT5_SERVER/MT5_ACCOUNT_ID) ; prêt à étendre vers une
    liste numérotée (MT5_LOGIN_2, ...) quand un deuxième compte sera ajouté.
    """
    login = os.environ.get("MT5_LOGIN")
    password = os.environ.get("MT5_PASSWORD")
    server = os.environ.get("MT5_SERVER")
    account_id = os.environ.get("MT5_ACCOUNT_ID", "compte_1")

    if not login or not password or not server:
        return []

    return [MT5Account(account_id=account_id, login=int(login), password=password, server=server)]


def connect(account):
    """Connecte le terminal MT5 local au compte donné. Retourne True/False."""
    if not mt5.initialize(login=account.login, password=account.password, server=account.server):
        print(f"[MT5] Échec de connexion au compte {account.account_id} : {mt5.last_error()}")
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


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Utilitaires de gestion des comptes MT5.")
    parser.add_argument("--resume", metavar="ACCOUNT_ID", help="Lève manuellement la pause drawdown d'un compte.")
    args = parser.parse_args()

    if args.resume:
        resume_account(args.resume)
    else:
        parser.print_help()
