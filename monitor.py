"""
Bot de surveillance système, indépendant du pipeline principal (app.py) : vérifie
périodiquement (toutes les CHECK_INTERVAL_SECONDS) :
  1. Connexion MT5 active.
  2. Connexion IMAP Gmail active (alerte après IMAP_FAILURE_THRESHOLD échecs consécutifs).
  3. Fraîcheur du dernier email reçu (alerte de contrôle après NO_EMAIL_ALERT_DAYS jours).
  4. Drawdown de chaque compte MT5 (avertissement précoce à DRAWDOWN_WARNING_THRESHOLD_PCT,
     avant le seuil de pause automatique déjà géré par app_mt5.check_drawdown()).

Chaque vérification est isolée (try/except) : un échec sur un point n'empêche jamais
la vérification des autres, et le bot ne doit jamais s'arrêter. Résultat de chaque
vérification loggé dans monitor.log.
"""
import email
import imaplib
import os
import sys
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests
from dotenv import load_dotenv

import app_mt5

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

load_dotenv()

CHECK_INTERVAL_SECONDS = 20 * 60  # 20 min (fourchette 15-30 min demandée)
IMAP_FAILURE_THRESHOLD = 3
NO_EMAIL_ALERT_DAYS = 10
MONITOR_LOG_PATH = "monitor.log"

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
IMAP_SERVER = os.environ.get("IMAP_SERVER", "imap.gmail.com")
EMAIL_USER = os.environ["EMAIL_USER"]
EMAIL_PASS = os.environ["EMAIL_PASS"]

# État en mémoire du process (pas besoin de persistance disque : monitor.py tourne en
# continu comme app.py — un redémarrage repart juste à zéro sur ces compteurs).
_imap_consecutive_failures = 0
_no_email_alert_sent = False


def _log(message):
    line = f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} | {message}"
    print(line)
    with open(MONITOR_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _alert_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        _log(f"⚠️ Échec d'envoi Telegram : {e}")


def check_mt5():
    """1. Connexion MT5 active, par compte configuré."""
    try:
        accounts = app_mt5.load_accounts()
        if not accounts:
            _log("MT5 | ÉCHEC | aucun compte configuré dans .env")
            _alert_telegram("🔴 *MT5 déconnecté* : aucun compte configuré dans .env")
            return

        for account in accounts:
            if app_mt5.connect(account):
                app_mt5.disconnect()
                _log(f"MT5 | OK | {account.account_id}")
            else:
                _log(f"MT5 | ÉCHEC | {account.account_id}")
                _alert_telegram(f"🔴 *MT5 déconnecté* sur {account.account_id}")
    except Exception as e:
        _log(f"MT5 | ERREUR | {e}")
        _alert_telegram(f"🔴 *MT5 déconnecté* (erreur inattendue : {e})")


def check_imap():
    """2. Connexion IMAP Gmail active — alerte après IMAP_FAILURE_THRESHOLD échecs consécutifs."""
    global _imap_consecutive_failures
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_USER, EMAIL_PASS)
        mail.logout()
        if _imap_consecutive_failures > 0:
            _log(f"IMAP | OK (rétabli après {_imap_consecutive_failures} échec(s))")
        else:
            _log("IMAP | OK")
        _imap_consecutive_failures = 0
    except Exception as e:
        _imap_consecutive_failures += 1
        _log(f"IMAP | ÉCHEC ({_imap_consecutive_failures}/{IMAP_FAILURE_THRESHOLD}) | {e}")
        if _imap_consecutive_failures >= IMAP_FAILURE_THRESHOLD:
            _alert_telegram(
                f"🔴 *Connexion email en échec* ({_imap_consecutive_failures} échecs consécutifs)\n{e}"
            )


def check_last_email():
    """3. Fraîcheur du dernier email reçu — alerte de contrôle (pas une urgence) après
    NO_EMAIL_ALERT_DAYS jours sans aucun email dans la boîte."""
    global _no_email_alert_sent
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_USER, EMAIL_PASS)
        mail.select("inbox", readonly=True)
        status, messages = mail.search(None, "ALL")
        ids = messages[0].split()
        if not ids:
            mail.logout()
            _log("DERNIER EMAIL | AUCUN | boîte vide")
            return

        _, msg_data = mail.fetch(ids[-1], "(RFC822.HEADER)")
        mail.logout()

        msg = email.message_from_bytes(msg_data[0][1])
        last_email_dt = parsedate_to_datetime(msg.get("Date"))
        if last_email_dt.tzinfo is None:
            last_email_dt = last_email_dt.replace(tzinfo=timezone.utc)

        days_since = (datetime.now(timezone.utc) - last_email_dt).total_seconds() / 86400
        _log(f"DERNIER EMAIL | il y a {days_since:.1f} jour(s) | {last_email_dt.isoformat()}")

        if days_since >= NO_EMAIL_ALERT_DAYS:
            if not _no_email_alert_sent:
                _alert_telegram(
                    f"ℹ️ *Vérification recommandée* : aucun email reçu depuis {days_since:.1f} jours "
                    f"(seuil {NO_EMAIL_ALERT_DAYS}j, ~1.5 signal/semaine attendu) — pas forcément un "
                    f"problème, mais vérifie que tout fonctionne bien."
                )
                _no_email_alert_sent = True
        else:
            _no_email_alert_sent = False
    except Exception as e:
        _log(f"DERNIER EMAIL | ERREUR | {e}")


def check_drawdown_warnings():
    """4. Drawdown de chaque compte — avertissement précoce avant le seuil de pause."""
    try:
        for account in app_mt5.load_accounts():
            if not app_mt5.connect(account):
                _log(f"DRAWDOWN | ÉCHEC connexion | {account.account_id}")
                continue
            try:
                drawdown_pct, should_warn = app_mt5.check_drawdown_warning(account)
            finally:
                app_mt5.disconnect()

            if drawdown_pct is None:
                _log(f"DRAWDOWN | ÉCHEC lecture | {account.account_id}")
                continue

            paused = app_mt5.is_account_paused(account.account_id)
            _log(f"DRAWDOWN | {drawdown_pct:.2f}% | {account.account_id} | paused={paused}")

            if should_warn:
                _alert_telegram(
                    f"🟠 *Avertissement précoce — {account.account_id}*\n"
                    f"Drawdown : {drawdown_pct:.2f}% "
                    f"(seuil d'avertissement {app_mt5.DRAWDOWN_WARNING_THRESHOLD_PCT}%, "
                    f"pause automatique à {app_mt5.DRAWDOWN_PAUSE_THRESHOLD_PCT}%)\n"
                    f"Pas encore de pause, juste un signal pour anticiper."
                )
    except Exception as e:
        _log(f"DRAWDOWN | ERREUR | {e}")


CHECKS = (check_mt5, check_imap, check_last_email, check_drawdown_warnings)


def main():
    _log("🚀 monitor.py démarré")
    while True:
        for check in CHECKS:
            try:
                check()
            except Exception as e:
                # Filet de sécurité en plus du try/except propre à chaque fonction :
                # une vérification ne doit jamais empêcher les autres de tourner.
                _log(f"ERREUR NON GÉRÉE dans {check.__name__} : {e}")
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
