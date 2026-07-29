import imaplib
import email
from email.header import decode_header
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

import account_router
import app_mt5
import news_filter
import scraper
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

# Suivi des emails déjà traités par LE BOT — totalement indépendant du flag IMAP
# \Seen (jamais touché : fetch en BODY.PEEK[]). Un email n'est marqué "traité" que
# lorsque le pipeline complet l'a géré (extraction + dispatch à l'exécution), pas au
# simple fait de l'avoir lu. Voir verifier_mails().
PROCESSED_EMAILS_PATH = "processed_emails.json"
FAILED_EMAILS_LOG_PATH = "failed_emails.log"

# Emails en échec de parsing déjà notifiés/logués PENDANT CE RUN (en mémoire, jamais
# persisté) : évite de re-notifier Telegram et de re-logger le même email à chaque
# cycle de 60s. Volontairement pas marqué dans processed_emails.json (qui doit rester
# réservé aux emails réellement traités) — un redémarrage du bot vide ce suivi et
# relance donc automatiquement le traitement de ces emails.
_failed_this_run = set()

# --- CONFIGURATION TELEGRAM ---
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# --- CONFIGURATION EMAIL ---
IMAP_SERVER = os.environ.get("IMAP_SERVER", "imap.gmail.com")
EMAIL_USER = os.environ["EMAIL_USER"]
EMAIL_PASS = os.environ["EMAIL_PASS"]

# --- CONFIGURATION CENTRALCHARTS (fiches d'analyses EN COURS) ---
CENTRALCHARTS_EMAIL = os.environ.get("CENTRALCHARTS_EMAIL")
CENTRALCHARTS_PASSWORD = os.environ.get("CENTRALCHARTS_PASSWORD")

MIN_RR = 2.0

# Session CentralCharts authentifiée, créée à la demande et réutilisée (voir
# _get_centralcharts_session) — pas de reconnexion à chaque signal.
_centralcharts_session = None


def _get_centralcharts_session(force_relogin=False):
    """Session authentifiée CentralCharts, créée au premier besoin puis réutilisée.
    force_relogin=True si un appel précédent a échoué (session probablement expirée)."""
    global _centralcharts_session
    if _centralcharts_session is not None and not force_relogin:
        return _centralcharts_session

    if not CENTRALCHARTS_EMAIL or not CENTRALCHARTS_PASSWORD:
        print("⚠️ CENTRALCHARTS_EMAIL/CENTRALCHARTS_PASSWORD non configurés (.env) : "
              "fiches EN COURS inaccessibles.")
        return None

    _centralcharts_session = scraper.create_authenticated_session(CENTRALCHARTS_EMAIL, CENTRALCHARTS_PASSWORD)
    return _centralcharts_session

# Le lien de signal a la forme "GBP/SEK (Baissière)" / "EUR/USD (Haussière)" dans le
# corps HTML de l'email (pas dans le texte brut : c'est un vrai hyperlien).
SIGNAL_LINK_PATTERN = re.compile(r'^(.+?)\s*\((Haussière|Baissière)\)$', re.IGNORECASE)
IAID_PATTERN = re.compile(r'/iaid/\d+')


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


def _load_processed_emails():
    if os.path.exists(PROCESSED_EMAILS_PATH):
        with open(PROCESSED_EMAILS_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _mark_email_processed(message_id, outcome):
    processed = _load_processed_emails()
    processed[message_id] = {"traite_le": time.strftime("%Y-%m-%d %H:%M:%S"), "resultat": outcome}
    with open(PROCESSED_EMAILS_PATH, "w", encoding="utf-8") as f:
        json.dump(processed, f, indent=2, ensure_ascii=False)


def _log_failed_email(message_id, subject, body):
    """Log le contenu brut d'un email dont le parsing a échoué, pour retraitement
    manuel — jamais perdu silencieusement."""
    with open(FAILED_EMAILS_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(
            f"\n{'=' * 80}\n"
            f"{time.strftime('%Y-%m-%d %H:%M:%S')} | Message-ID: {message_id}\n"
            f"Sujet: {subject}\n"
            f"{'-' * 80}\n"
            f"{body}\n"
            f"{'=' * 80}\n"
        )


def _get_message_id(msg, e_id):
    message_id = msg.get("Message-ID")
    if message_id:
        return message_id
    # Filet de sécurité si l'email n'a pas d'en-tête Message-ID (rare) : hash du
    # contenu brut, stable pour un même message.
    return "sha256:" + hashlib.sha256(msg.as_bytes()).hexdigest()


def _find_signal_link(html_body):
    """Cherche dans le corps HTML de l'email le lien "TICKER (Haussière|Baissière)"
    et retourne (ticker, direction, detail_url), ou None si aucun lien de ce type
    n'est trouvé (email non pertinent, ex: newsletter)."""
    if not html_body:
        return None

    soup = BeautifulSoup(html_body, "lxml")
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        match = SIGNAL_LINK_PATTERN.match(text)
        if not match:
            continue
        if not IAID_PATTERN.search(a["href"]):
            continue

        ticker = match.group(1).strip()
        direction_texte = match.group(2)
        direction = "buy" if direction_texte.lower() == "haussière" else "sell"
        href = a["href"]
        detail_url = href if href.startswith("http") else f"{scraper.BASE_URL}{href}"
        return ticker, direction, detail_url

    return None


def extraire_champs_signal(html_body):
    """Extrait ticker/direction/URL depuis le lien de l'email (corps HTML, pas texte
    brut), valide le ticker contre la liste des paires suivies, visite la fiche
    détail pour les prix réels, et calcule rr_tp1/rr_tp2 avec la même formule que
    scraper.py.

    Retourne (outcome, champs) :
      - ("ok", dict)            : prêt pour executer_signal_reel (rr_tp1 >= MIN_RR).
      - ("hors_perimetre", None): ticker parsé avec succès mais pas dans notre liste
                                  d'actifs suivis — signal légitimement ignoré, PAS
                                  une erreur de parsing.
      - ("rr_insuffisant", None): ticker suivi mais rr_tp1 < MIN_RR.
      - ("echec_parsing", None) : aucun lien de signal trouvé dans l'email.
      - ("fiche_inaccessible", None) : lien trouvé et ticker suivi, mais la fiche
                                  détail n'a pas pu être récupérée (souvent une
                                  analyse encore "EN COURS", pas encore publique).
    """
    found = _find_signal_link(html_body)
    if found is None:
        return "echec_parsing", None

    ticker, direction, detail_url = found

    if ticker not in scraper.TARGET_FOREX_TICKERS:
        return "hors_perimetre", None

    session = _get_centralcharts_session()
    details = scraper.fetch_signal_detail(detail_url, session=session)
    if details is None and session is not None:
        # La session a peut-être expiré : une tentative de reconnexion avant
        # d'abandonner (pas de délai/backoff ici, chemin critique temps réel).
        session = _get_centralcharts_session(force_relogin=True)
        details = scraper.fetch_signal_detail(detail_url, session=session)
    if details is None:
        return "fiche_inaccessible", None

    risk_distance = abs(details["prix_entree"] - details["stop_loss_init"])
    if risk_distance == 0:
        return "fiche_inaccessible", None

    rr_tp1 = abs(details["tp1_init"] - details["prix_entree"]) / risk_distance
    if rr_tp1 < MIN_RR:
        return "rr_insuffisant", None

    return "ok", {
        "ticker": ticker,
        "direction": direction,
        "stop_loss_init": details["stop_loss_init"],
        "tp1_init": details["tp1_init"],
        "tp2_init": details["tp2_init"],
        "asset_class": "FX/Indices",
        "timeframe": details["timeframe"],
    }


def traiter_signal_valide(champs, subject):
    """Point d'entrée unique pour un signal validé (ticker suivi, rr_tp1 >= MIN_RR).
    Déclenche deux actions indépendantes, non-bloquantes l'une envers l'autre :
      1. L'exécution réelle sur MT5 (chemin critique).
      2. La notification Telegram (informatif uniquement, en arrière-plan).
    Un échec ou un ralentissement de (2) n'affecte jamais (1), et inversement
    l'exécution ne retarde pas l'envoi de la notification puisqu'elle est
    dispatchée avant, dans son propre thread.
    """
    notifier_telegram_async(
        f"🚨 *Signal validé* {champs['ticker']} ({champs['direction']})\n\nSujet : {subject}"
    )
    executer_signal_reel(date_creation=time.strftime("%Y-%m-%d %H:%M:%S"), **champs)


def verifier_mails():
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_USER, EMAIL_PASS)
        mail.select("inbox")

        # ALL et non UNSEEN : le \Seen flag n'est plus notre mécanisme de suivi (voir
        # BODY.PEEK[] ci-dessous) — le filtrage "déjà traité" se fait via
        # processed_emails.json, sur Message-ID, pas sur le statut lu/non-lu IMAP.
        status, messages = mail.search(None, "ALL")
        if not messages[0]:
            mail.logout()
            return

        processed = _load_processed_emails()
        email_ids = messages[0].split()
        for e_id in email_ids:
            # BODY.PEEK[] (et non RFC822/BODY[]) : ne marque JAMAIS le message comme lu
            # côté serveur, quel que soit le résultat du traitement ci-dessous. Le flag
            # \Seen reste entièrement sous le contrôle de l'utilisateur (client mail).
            _, msg_data = mail.fetch(e_id, "(BODY.PEEK[])")
            for response_part in msg_data:
                if not isinstance(response_part, tuple):
                    continue

                msg = email.message_from_bytes(response_part[1])
                message_id = _get_message_id(msg, e_id)
                if message_id in processed or message_id in _failed_this_run:
                    continue

                subject, encoding = decode_header(msg["Subject"])[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding or "utf-8", errors="ignore")

                # Le lien de signal est un vrai hyperlien HTML : le texte brut seul ne
                # donne pas le href, il faut la partie text/html du message.
                body_plain = ""
                body_html = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        if content_type == "text/plain" and not body_plain:
                            body_plain = part.get_payload(decode=True).decode(errors="ignore")
                        elif content_type == "text/html" and not body_html:
                            body_html = part.get_payload(decode=True).decode(errors="ignore")
                else:
                    payload = msg.get_payload(decode=True).decode(errors="ignore")
                    if msg.get_content_type() == "text/html":
                        body_html = payload
                    else:
                        body_plain = payload

                try:
                    outcome, champs = extraire_champs_signal(body_html)
                except Exception as e:
                    outcome, champs = "echec_parsing", None
                    print(f"⚠️ Exception lors du parsing du signal {message_id} : {e}")

                if outcome == "ok":
                    try:
                        traiter_signal_valide(champs, subject)
                        _mark_email_processed(message_id, "traite")
                    except Exception as e:
                        # Échec pendant l'exécution elle-même (pas le parsing) : même
                        # traitement que les échecs de parsing, retenté au redémarrage.
                        _failed_this_run.add(message_id)
                        _log_failed_email(message_id, subject, body_plain or body_html)
                        print(f"⚠️ Exception lors du traitement du signal {message_id} : {e}")

                elif outcome in ("hors_perimetre", "rr_insuffisant"):
                    # Parsé avec succès, mais légitimement hors scope — pas une erreur,
                    # ne sera jamais retraité (le résultat ne changera pas dans le temps).
                    _mark_email_processed(message_id, outcome)
                    print(f"ℹ️ Signal {message_id} ignoré ({outcome}) — {subject}")

                else:
                    # "echec_parsing" ou "fiche_inaccessible" : notifié/logué une seule
                    # fois par run (voir _failed_this_run), pas de re-log toutes les
                    # 60s. Pas marqué dans processed_emails.json (persistant) : un
                    # redémarrage du bot relance automatiquement le traitement.
                    _failed_this_run.add(message_id)
                    _log_failed_email(message_id, subject, body_plain or body_html)
                    print(
                        f"⚠️ Signal {message_id} non traité ({outcome}) — NON marqué comme "
                        f"traité, contenu loggé dans {FAILED_EMAILS_LOG_PATH} "
                        f"(une seule fois ce run ; relance au redémarrage du bot)."
                    )

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
