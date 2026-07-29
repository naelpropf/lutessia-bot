import imaplib
import email
from email.header import decode_header
import os
import re
import subprocess
import sys
import threading
import time
import requests
from dotenv import load_dotenv

import account_router
import app_mt5
import news_filter
import trade_logger

# Évite un crash sur les emojis/accents si la console Windows est en cp1252
# (codepage par défaut fréquente en français) plutôt qu'en UTF-8.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

load_dotenv()

STATUS_CHECK_INTERVAL_SECONDS = 3600  # vérifie les trades ouverts sur MT5 toutes les heures
WEEKLY_ANALYSIS_INTERVAL_SECONDS = 7 * 24 * 3600  # relance analyse_live.py une fois par semaine

# --- CONFIGURATION TELEGRAM ---
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# --- CONFIGURATION EMAIL ---
IMAP_SERVER = os.environ.get("IMAP_SERVER", "imap.gmail.com")
EMAIL_USER = os.environ["EMAIL_USER"]
EMAIL_PASS = os.environ["EMAIL_PASS"]


# --- TELEGRAM : canal de notification pur, jamais un mécanisme de communication
# entre composants. Rien dans le pipeline d'exécution ne doit dépendre de Telegram
# ni attendre son résultat. ---

def envoyer_telegram(message):
    """Envoi Telegram bloquant. Ne jamais appeler directement depuis le chemin
    d'exécution : utiliser notifier_telegram_async() à la place."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"⚠️ [Telegram] Échec d'envoi (notification perdue, sans impact sur l'exécution) : {e}")


def notifier_telegram_async(message):
    """Envoie la notification dans un thread séparé : ne bloque jamais, ne peut
    jamais retarder ni faire échouer le chemin d'exécution critique (MT5), même
    si l'API Telegram est down ou lente."""
    try:
        threading.Thread(target=envoyer_telegram, args=(message,), daemon=True).start()
    except Exception as e:
        print(f"⚠️ [Telegram] Échec de dispatch de la notification : {e}")


def extraire_champs_signal(body):
    """Extrait ticker, direction, stop_loss_init, tp1_init, tp2_init, asset_class,
    timeframe du corps de l'email d'un signal validé.

    TODO : format exact des emails Lutessia en attente (l'utilisateur le fournira).
    Retourne None tant que non implémenté — traiter_signal_valide() n'exécute alors
    aucun ordre (mais la notification Telegram part quand même normalement)."""
    return None


def traiter_signal_valide(rr_value, subject, body):
    """Point d'entrée unique quand un signal passe le filtre R:R >= 2.0.
    Déclenche deux actions indépendantes, non-bloquantes l'une envers l'autre :
      1. L'exécution réelle sur MT5 (chemin critique).
      2. La notification Telegram (informatif uniquement, en arrière-plan).
    Un échec ou un ralentissement de (2) n'affecte jamais (1), et inversement
    l'exécution ne retarde pas l'envoi de la notification puisqu'elle est
    dispatchée avant, dans son propre thread.
    """
    notifier_telegram_async(f"🚨 *Signal validé* (R:R {rr_value})\n\nSujet : {subject}")

    champs = extraire_champs_signal(body)
    if champs is None:
        print("ℹ️ Signal validé mais champs d'exécution non extraits (format d'email en attente) — pas d'ordre MT5.")
        return

    executer_signal_reel(date_creation=time.strftime("%Y-%m-%d %H:%M:%S"), **champs)


def verifier_mails():
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_USER, EMAIL_PASS)
        mail.select("inbox")

        status, messages = mail.search(None, '(UNSEEN)')
        if not messages[0]:
            mail.logout()
            return

        email_ids = messages[0].split()
        for e_id in email_ids:
            _, msg_data = mail.fetch(e_id, '(RFC822)')
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding or "utf-8", errors="ignore")

                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode(errors="ignore")
                                break
                    else:
                        body = msg.get_payload(decode=True).decode(errors="ignore")

                    match = re.search(r'R:R\s*:\s*([0-9\.]+)', body, re.IGNORECASE)
                    if match:
                        rr_value = float(match.group(1))
                        if rr_value >= 2.0:
                            traiter_signal_valide(rr_value, subject, body)

        mail.logout()
    except Exception as e:
        print(f"⚠️ Erreur lors du scan email : {e}")


def executer_signal_reel(ticker, direction, stop_loss_init, tp1_init, tp2_init,
                          asset_class, timeframe, date_creation):
    """Route le signal vers un compte MT5 éligible et exécute l'ordre au marché
    (chemin critique — aucun appel Telegram bloquant ici). Log le trade dans
    trades_reels.csv avec le prix de remplissage réel (pas celui de l'email).
    Ne fait rien si aucun compte n'est éligible."""
    # Filtre news : ne s'applique qu'ici (nouvelle entrée), jamais sur une position déjà
    # ouverte (trade_logger.update_open_trades() ne l'appelle pas). Retarde sans jamais
    # annuler ; placé avant le routage pour que la sélection de compte se fasse sur un
    # état à jour (positions/corrélations) une fois la fenêtre de news passée.
    news_filter.apply_news_delay(ticker)

    accounts = app_mt5.load_accounts()
    if not accounts:
        print("⚠️ Aucun compte MT5 configuré (.env) : signal ignoré.")
        return

    account = account_router.select_account(ticker, accounts)
    if account is None:
        print(f"ℹ️ Aucun compte éligible pour {ticker} (positions max atteintes ou actif corrélé) : signal ignoré.")
        return

    if not app_mt5.connect(account):
        return
    try:
        mt5_symbol = ticker.replace("/", "")
        volume = app_mt5.calculate_position_size(account, mt5_symbol, stop_loss_init)
        if volume is None:
            print(f"⚠️ Taille de position incalculable pour {ticker} sur {account.account_id} : signal ignoré.")
            return
        success, fill_price, ticket, _ = app_mt5.place_market_order(
            mt5_symbol, direction, stop_loss_init, tp1_init, volume
        )
    finally:
        app_mt5.disconnect()

    if not success:
        notifier_telegram_async(f"❌ *Échec d'exécution* {ticker} sur {account.account_id}")
        return

    date_execution = time.strftime("%Y-%m-%d %H:%M:%S")
    risk_distance = abs(fill_price - stop_loss_init)
    rr_tp1 = abs(tp1_init - fill_price) / risk_distance if risk_distance else None
    rr_tp2 = abs(tp2_init - fill_price) / risk_distance if risk_distance else None

    trade_logger.log_trade_execution(
        date_creation, ticker, asset_class, timeframe, fill_price,
        stop_loss_init, tp1_init, tp2_init, rr_tp1, rr_tp2,
        account.account_id, date_execution, ticket,
    )
    notifier_telegram_async(f"✅ *Trade exécuté* {ticker} sur {account.account_id} @ {fill_price} (ticket {ticket})")


def verifier_drawdown_comptes():
    """Vérifie le drawdown de chaque compte MT5 et déclenche la pause + alerte Telegram
    si le seuil est franchi (cf. app_mt5.check_drawdown — jamais basé sur un compteur de
    pertes consécutives, jamais levée automatiquement). Ne touche jamais aux positions
    déjà ouvertes : bloque uniquement le routage de nouvelles entrées (account_router)."""
    for account in app_mt5.load_accounts():
        if app_mt5.is_account_paused(account.account_id):
            continue

        if not app_mt5.connect(account):
            continue
        try:
            drawdown_pct, just_paused = app_mt5.check_drawdown(account)
        finally:
            app_mt5.disconnect()

        if just_paused:
            notifier_telegram_async(
                f"🛑 *Pause automatique — {account.account_id}*\n"
                f"Drawdown : {drawdown_pct:.2f}% (seuil {app_mt5.DRAWDOWN_PAUSE_THRESHOLD_PCT}%)\n"
                f"Nouvelles entrées bloquées sur ce compte. Positions déjà ouvertes non affectées.\n"
                f"Levée manuelle uniquement : `python app_mt5.py --resume {account.account_id}`"
            )
            print(f"🛑 Compte {account.account_id} mis en pause (drawdown {drawdown_pct:.2f}%).")


if __name__ == "__main__":
    print("🚀 Bot Lutessia démarré !")
    notifier_telegram_async("🚀 *Bot Lutessia opérationnel (H24)*")

    last_status_check = 0.0
    last_weekly_analysis = 0.0

    while True:
        verifier_mails()

        try:
            verifier_drawdown_comptes()
        except Exception as e:
            print(f"⚠️ Erreur lors de la vérification du drawdown : {e}")

        now = time.time()
        if now - last_status_check >= STATUS_CHECK_INTERVAL_SECONDS:
            try:
                trade_logger.update_open_trades()
            except Exception as e:
                print(f"⚠️ Erreur lors de la mise à jour des trades ouverts : {e}")
            last_status_check = now

        if now - last_weekly_analysis >= WEEKLY_ANALYSIS_INTERVAL_SECONDS:
            try:
                subprocess.run(["python", "analyse_live.py", "--log"], check=False)
            except Exception as e:
                print(f"⚠️ Erreur lors de l'analyse live hebdomadaire : {e}")
            last_weekly_analysis = now

        time.sleep(60)
