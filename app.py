import imaplib
import email
from email.header import decode_header
import hashlib
import json
import msvcrt
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
import slippage_logger
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

# Abaissé à 1.25 le 07/08 (était 1.5, qui remplaçait déjà 2.0) -- confirmé par Monte
# Carlo flotte complète (contexte_projet_lutessia_2026-08-07-v3.md, section 1) :
# malgré une EV brute par trade plus faible (+0.97R vs +0.91R), la fréquence de
# trades plus élevée (646 vs 472 sur l'échantillon) compense largement via l'effet de
# compounding -- +43.5% de profit final, P(an1<0) 4x meilleure. La rampe de risque
# 2.0%->2.5% évaluée dans la même session n'est PAS appliquée ici (RISK_PCT_PER_TRADE
# dans app_mt5.py reste fixe à 0.5%, changement structurel à part).
MIN_RR = 1.25

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


def _find_signal_links(html_body):
    """Cherche dans le corps HTML de l'email TOUS les liens "TICKER
    (Haussière|Baissière)" — un même email "Opportunities FX/Indices" peut contenir
    plusieurs signaux (ex: 2 tickers dans un même envoi groupé), pas un seul.
    Retourne une liste de (ticker, direction, detail_url), dans l'ordre d'apparition
    dans le HTML, dédupliquée par detail_url. Liste vide si aucun lien de ce type
    n'est trouvé (email non pertinent, ex: newsletter)."""
    if not html_body:
        return []

    soup = BeautifulSoup(html_body, "lxml")
    seen_urls = set()
    results = []
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
        if detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        results.append((ticker, direction, detail_url))

    return results


def extraire_champs_signal(html_body):
    """Extrait ticker/direction/URL depuis TOUS les liens de signal de l'email
    (corps HTML, pas texte brut — un email peut en contenir plusieurs, cf.
    _find_signal_links), valide chaque ticker contre la liste des paires suivies,
    visite sa fiche détail pour les prix réels, et calcule rr_tp1/rr_tp2 avec la
    même formule que scraper.py.

    Retourne une liste de (detail_url, outcome, champs) — un triplet par signal
    trouvé dans l'email, traité indépendamment des autres (l'échec de l'un ne
    bloque pas les autres) :
      - (url, "ok", dict)                    : prêt pour executer_signal_reel (rr_tp1 >= MIN_RR).
      - (url, "hors_perimetre", {"ticker"})  : ticker parsé avec succès mais pas dans
                                  notre liste d'actifs suivis — signal légitimement
                                  ignoré, PAS une erreur de parsing.
      - (url, "rr_insuffisant", {"ticker", "rr_tp1"}) : ticker suivi mais rr_tp1 < MIN_RR.
      - (url, "fiche_inaccessible", {"ticker"}) : lien trouvé et ticker suivi, mais
                                  la fiche détail n'a pas pu être récupérée (souvent
                                  une analyse encore "EN COURS", pas encore publique).
    champs contient toujours au moins le ticker pour les cas non-"ok" (sauf
    "echec_parsing", où aucun ticker n'a pu être identifié) -- utilisé par
    verifier_mails() pour notifier la raison exacte d'un signal non pris.
    Si aucun lien de signal n'est trouvé dans l'email (newsletter, etc.), retourne
    une liste à un seul élément [(None, "echec_parsing", None)].
    """
    links = _find_signal_links(html_body)
    if not links:
        return [(None, "echec_parsing", None)]

    resultats = []
    for ticker, direction, detail_url in links:
        if ticker not in scraper.TARGET_FOREX_TICKERS:
            resultats.append((detail_url, "hors_perimetre", {"ticker": ticker}))
            continue

        session = _get_centralcharts_session()
        details = scraper.fetch_signal_detail(detail_url, session=session)
        if details is None and session is not None:
            # La session a peut-être expiré : une tentative de reconnexion avant
            # d'abandonner. Court délai pour ne pas enchaîner deux requêtes quasi
            # simultanées vers CentralCharts (cf. incident 403/429 Cloudflare du
            # 29/07, confirmé causé par des requêtes concurrentes, pas la fréquence
            # seule — voir aussi le verrou mono-instance dans verifier_mails()).
            time.sleep(3)
            session = _get_centralcharts_session(force_relogin=True)
            details = scraper.fetch_signal_detail(detail_url, session=session)
        if details is None:
            resultats.append((detail_url, "fiche_inaccessible", {"ticker": ticker}))
            continue

        risk_distance = abs(details["prix_entree"] - details["stop_loss_init"])
        if risk_distance == 0:
            resultats.append((detail_url, "fiche_inaccessible", {"ticker": ticker}))
            continue

        rr_tp1 = abs(details["tp1_init"] - details["prix_entree"]) / risk_distance
        if rr_tp1 < MIN_RR:
            resultats.append((detail_url, "rr_insuffisant", {"ticker": ticker, "rr_tp1": rr_tp1}))
            continue

        resultats.append((detail_url, "ok", {
            "ticker": ticker,
            "direction": direction,
            "stop_loss_init": details["stop_loss_init"],
            "tp1_init": details["tp1_init"],
            "tp2_init": details["tp2_init"],
            "asset_class": "FX/Indices",
            "timeframe": details["timeframe"],
            # Score "Force" (0-10, cf. scraper.py) : capturé pour usage futur uniquement,
            # accumulé à partir de maintenant (aucune donnée rétroactive) -- peut être
            # None si le widget est absent sur cette fiche, jamais bloquant pour
            # l'exécution.
            "score_force": details.get("score_force"),
            # Prix de la fiche au moment du parsing -- référence pour la mesure de
            # slippage (cf. slippage_logger.log_slippage), distinct du prix de
            # remplissage réel obtenu plus tard dans executer_signal_reel().
            "signal_price": details["prix_entree"],
        }))

    return resultats


def traiter_signal_valide(champs, subject, email_sent_at=None):
    """Point d'entrée unique pour un signal validé (ticker suivi, rr_tp1 >= MIN_RR).
    Déclenche deux actions indépendantes, non-bloquantes l'une envers l'autre :
      1. L'exécution réelle sur MT5 (chemin critique).
      2. La notification Telegram (informatif uniquement, en arrière-plan).
    Un échec ou un ralentissement de (2) n'affecte jamais (1), et inversement
    l'exécution ne retarde pas l'envoi de la notification puisqu'elle est
    dispatchée avant, dans son propre thread.
    email_sent_at : datetime du header Date de l'email (latence email->exécution,
    cf. slippage_logger) -- None si absent/non parsable, la mesure de latence
    sera alors simplement omise pour ce trade.
    """
    notifier_telegram_async(
        f"🚨 *Signal validé* {champs['ticker']} ({champs['direction']})\n\nSujet : {subject}"
    )
    executer_signal_reel(date_creation=time.strftime("%Y-%m-%d %H:%M:%S"),
                          email_sent_at=email_sent_at, **champs)


def _reason_text(outcome, champs):
    """Raison lisible d'un signal NON pris, pour la notification Telegram (cf.
    verifier_mails) -- pas juste un code interne, pour permettre une vérification
    rapide sans aller lire les logs."""
    ticker = (champs or {}).get("ticker", "?")
    if outcome == "hors_perimetre":
        return f"{ticker} — paire non suivie"
    if outcome == "rr_insuffisant":
        rr_tp1 = (champs or {}).get("rr_tp1")
        rr_txt = f"{rr_tp1:.2f}" if rr_tp1 is not None else "?"
        return f"{ticker} — R:R trop bas ({rr_txt} < {MIN_RR})"
    if outcome == "fiche_inaccessible":
        return f"{ticker} — fiche d'analyse inaccessible (page indisponible ou pas encore publiée)"
    if outcome == "echec_parsing":
        return "email reçu mais aucun signal reconnu dedans (format inattendu)"
    return f"{ticker} — {outcome}"


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
                # Skip rapide : ne s'applique que si TOUS les signaux de cet email
                # ont déjà atteint un état terminal lors d'un run précédent (voir la
                # clé message_id posée en fin de boucle ci-dessous). Tant que ce
                # n'est pas le cas, on reparse pour retenter individuellement les
                # signaux encore en échec (fiche_inaccessible / echec_parsing).
                if message_id in processed:
                    continue

                subject, encoding = decode_header(msg["Subject"])[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding or "utf-8", errors="ignore")

                # Header Date de l'email Lutessia -- référence pour la latence
                # email->exécution (cf. slippage_logger.log_slippage). None si absent
                # ou malformé : la mesure de latence sera simplement omise.
                try:
                    email_sent_at = email.utils.parsedate_to_datetime(msg["Date"])
                except (TypeError, ValueError):
                    email_sent_at = None

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
                    resultats = extraire_champs_signal(body_html)
                except Exception as e:
                    resultats = [(None, "echec_parsing", None)]
                    print(f"⚠️ Exception lors du parsing du signal {message_id} : {e}")

                # Un email peut contenir plusieurs signaux (plusieurs liens /iaid/) :
                # chacun a sa propre clé de suivi (message_id::detail_url), pour ne
                # jamais ré-exécuter un signal déjà "ok" au run précédent juste parce
                # qu'un AUTRE signal du même email a échoué et doit être retenté.
                all_terminal = True
                for detail_url, outcome, champs in resultats:
                    sub_key = message_id if detail_url is None else f"{message_id}::{detail_url}"
                    if sub_key in processed or sub_key in _failed_this_run:
                        continue

                    if outcome == "ok":
                        try:
                            traiter_signal_valide(champs, subject, email_sent_at=email_sent_at)
                            _mark_email_processed(sub_key, "traite")
                        except Exception as e:
                            # Échec pendant l'exécution elle-même (pas le parsing) : même
                            # traitement que les échecs de parsing, retenté au redémarrage.
                            _failed_this_run.add(sub_key)
                            _log_failed_email(sub_key, subject, body_plain or body_html)
                            all_terminal = False
                            print(f"⚠️ Exception lors du traitement du signal {sub_key} : {e}")

                    elif outcome in ("hors_perimetre", "rr_insuffisant"):
                        # Parsé avec succès, mais légitimement hors scope — pas une erreur,
                        # ne sera jamais retraité (le résultat ne changera pas dans le temps).
                        _mark_email_processed(sub_key, outcome)
                        print(f"ℹ️ Signal {sub_key} ignoré ({outcome}) — {subject}")
                        notifier_telegram_async(f"🚫 *Trade non pris* — {_reason_text(outcome, champs)}")

                    else:
                        # "echec_parsing" ou "fiche_inaccessible" : notifié/logué une seule
                        # fois par run (voir _failed_this_run), pas de re-log toutes les
                        # 60s. Pas marqué dans processed_emails.json (persistant) : un
                        # redémarrage du bot relance automatiquement le traitement.
                        _failed_this_run.add(sub_key)
                        _log_failed_email(sub_key, subject, body_plain or body_html)
                        all_terminal = False
                        print(
                            f"⚠️ Signal {sub_key} non traité ({outcome}) — NON marqué comme "
                            f"traité, contenu loggé dans {FAILED_EMAILS_LOG_PATH} "
                            f"(une seule fois ce run ; relance au redémarrage du bot)."
                        )
                        notifier_telegram_async(f"🚫 *Trade non pris* — {_reason_text(outcome, champs)}")

                if all_terminal:
                    # Tous les signaux de cet email ont atteint un état terminal (ok /
                    # hors_perimetre / rr_insuffisant) : l'email entier peut être
                    # sauté rapidement dès le prochain run (voir le skip en haut de
                    # boucle), sans reparser son contenu à chaque cycle de 60s.
                    _mark_email_processed(message_id, "traite_complet")

        mail.logout()
    except Exception as e:
        print(f"⚠️ Erreur lors du scan email : {e}")


def executer_signal_reel(ticker, direction, stop_loss_init, tp1_init, tp2_init,
                          asset_class, timeframe, date_creation, score_force=None,
                          signal_price=None, email_sent_at=None):
    """COPYTRADE : tente le MÊME signal INDÉPENDAMMENT sur CHAQUE compte MT5 éligible
    (flotte de 3 comptes/3 firms distinctes, cf. account_router.eligible_accounts) --
    si un compte rejette (plafond de positions atteint ou actif corrélé déjà ouvert sur
    CE compte), les autres comptes éligibles prennent quand même le trade. Chemin
    critique — aucun appel Telegram bloquant dans la boucle d'exécution elle-même.
    Log chaque exécution séparément dans trades_reels.csv avec le prix de remplissage
    réel (pas celui de l'email). Ne fait rien si aucun compte n'est éligible."""
    # Filtre news : ne s'applique qu'ici (nouvelle entrée), jamais sur une position déjà
    # ouverte (trade_logger.update_open_trades() ne l'appelle pas). Retarde sans jamais
    # annuler ; placé avant le routage pour que l'éligibilité se calcule sur un état à
    # jour (positions/corrélations) une fois la fenêtre de news passée. Un seul délai
    # partagé pour les 3 comptes (même signal, même fenêtre de news).
    news_filter.apply_news_delay(ticker)

    accounts = app_mt5.load_accounts()
    if not accounts:
        print("⚠️ Aucun compte MT5 configuré (.env) : signal ignoré.")
        return

    eligible = account_router.eligible_accounts(ticker, accounts)
    if not eligible:
        # Corrigé le 06/08 : ce cas ne notifiait jamais Telegram (contrairement à tous
        # les autres rejets -- hors_perimetre, rr_insuffisant, échec d'exécution...),
        # cause confirmée d'un signal AUD/USD silencieusement ignoré (corrélé 0.85 à
        # une position NZD/USD déjà ouverte, seuil 0.6) sans aucune trace côté utilisateur.
        print(f"ℹ️ Aucun compte éligible pour {ticker} (positions max atteintes ou actif corrélé "
              f"sur tous les comptes configurés) : signal ignoré.")
        notifier_telegram_async(
            f"🚫 *Trade non pris* — {ticker} : aucun compte éligible "
            f"(position corrélée déjà ouverte ou plafond de positions atteint)"
        )
        return

    mt5_symbol = ticker.replace("/", "")
    for account in eligible:
        if not app_mt5.connect(account):
            continue
        try:
            # Taille de position calculée INDÉPENDAMMENT pour ce compte, sur SON propre
            # capital initial (cf. app_mt5.get_initial_capital, persisté par
            # account.account_id) -- jamais un capital partagé entre comptes.
            volume = app_mt5.calculate_position_size(account, mt5_symbol, stop_loss_init)
            if volume is None:
                print(f"⚠️ Taille de position incalculable pour {ticker} sur {account.account_id} : compte ignoré.")
                continue
            # TP envoyé au broker = tp2_init, pas tp1_init (corrigé le 31/07 — cause
            # racine du trade NZD/USD ticket 81685339 sorti prématurément à TP1 :
            # cf. audit du même soir). La stratégie voulue vise TP2 comme sortie
            # normale ; TP1 n'est utilisé nulle part comme cible d'exécution, sauf
            # dans rr_tp1 (le filtre d'entrée sur extraire_champs_signal).
            success, fill_price, ticket, _ = app_mt5.place_market_order(
                mt5_symbol, direction, stop_loss_init, tp2_init, volume
            )
        finally:
            app_mt5.disconnect()

        if not success:
            notifier_telegram_async(f"❌ *Échec d'exécution* {ticker} sur {account.account_id}")
            continue

        date_execution = time.strftime("%Y-%m-%d %H:%M:%S")
        risk_distance = abs(fill_price - stop_loss_init)
        rr_tp1 = abs(tp1_init - fill_price) / risk_distance if risk_distance else None
        rr_tp2 = abs(tp2_init - fill_price) / risk_distance if risk_distance else None

        trade_logger.log_trade_execution(
            date_creation, ticker, asset_class, timeframe, fill_price,
            stop_loss_init, tp1_init, tp2_init, rr_tp1, rr_tp2,
            account.account_id, date_execution, ticket, score_force,
        )

        # Mesure de slippage (pure observation, aucun impact sur l'exécution) : prix
        # signal (fiche Lutessia) vs fill réel, latence email->exécution, session
        # horaire. Ne doit jamais interrompre le pipeline critique si elle échoue.
        if signal_price is not None:
            try:
                slippage_logger.log_slippage(
                    ticker, direction, account.account_id, ticket,
                    signal_price, fill_price, email_sent_at=email_sent_at,
                )
            except Exception as e:
                print(f"⚠️ Erreur lors du log de slippage (n'affecte pas le trade) : {e}")

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


LOCK_FILE_PATH = "app.lock"


def _acquire_single_instance_lock():
    """Empêche deux instances de app.py de tourner en même temps sur cette machine.
    Cause confirmée le 29/07 : plusieurs process app.py lancés en parallèle pendant
    les tests d'infra (service NSSM + tâche planifiée + lancement manuel) ont
    déclenché la protection anti-bot Cloudflare de CentralCharts (403/429, "Just a
    moment...") en tapant la même fiche en concurrence — pas un problème de session
    expirée ni de blocage IP permanent. Verrou OS (msvcrt.locking), pas juste un
    fichier marqueur : relâché automatiquement par Windows si le process meurt/crash,
    donc pas de risque de lock orphelin qui bloquerait un redémarrage légitime.
    Quitte le process avec un message clair si une instance tourne déjà."""
    lock_handle = open(LOCK_FILE_PATH, "w")
    try:
        msvcrt.locking(lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        print(
            "🛑 Une autre instance de app.py tourne déjà sur cette machine "
            f"(verrou {LOCK_FILE_PATH} détenu) — arrêt pour éviter le double "
            "traitement des signaux et le rate-limiting CentralCharts."
        )
        sys.exit(1)
    return lock_handle  # gardé en vie tout le run : le verrou tient tant que ce handle est ouvert


def _run_trailing_check_if_due(now, last_trailing_check, next_trailing_delay):
    """Exécute trade_logger.manage_trailing_stops() si next_trailing_delay s'est
    écoulé depuis last_trailing_check, puis recalcule le délai avant le prochain
    passage via trade_logger.get_next_poll_delay_seconds() -- polling ADAPTATIF :
    NORMAL_POLL_INTERVAL_SECONDS (1h) tant qu'aucun trade ouvert n'approche de
    tp2_init, FAST_POLL_INTERVAL_SECONDS (2 min) dès qu'un trade entre dans les
    derniers 20% du chemin ou l'a déjà dépassé (cf. trade_logger.py, seuils validés
    empiriquement le 31/07 sur 228 trades réels : 0% de trades manqués par le
    polling normal, 96.2% des déclenchements rapides mènent bien à tp2_init).

    Isolée de la boucle principale (plutôt que du code inline dans le while True)
    pour rester testable en mock sans faire tourner app.py en entier -- cf.
    tests/test_trailing_stop.py. Retourne (nouveau last_trailing_check, nouveau
    next_trailing_delay), à réinjecter dans l'itération suivante de la boucle."""
    if now - last_trailing_check < next_trailing_delay:
        return last_trailing_check, next_trailing_delay

    try:
        trade_logger.manage_trailing_stops()
    except Exception as e:
        print(f"⚠️ Erreur lors de la gestion du trailing stop : {e}")

    try:
        next_trailing_delay = trade_logger.get_next_poll_delay_seconds()
    except Exception as e:
        print(f"⚠️ Erreur lors du calcul du délai de polling adaptatif : {e}")
        next_trailing_delay = trade_logger.NORMAL_POLL_INTERVAL_SECONDS

    return now, next_trailing_delay


if __name__ == "__main__":
    _acquire_single_instance_lock()
    print("🚀 Bot Lutessia démarré !")
    notifier_telegram_async("🚀 *Bot Lutessia opérationnel (H24)*")

    last_status_check = 0.0
    last_weekly_analysis = 0.0
    last_trailing_check = 0.0
    next_trailing_delay = 0.0  # force un premier passage dès la première itération

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

        last_trailing_check, next_trailing_delay = _run_trailing_check_if_due(
            now, last_trailing_check, next_trailing_delay
        )

        if now - last_weekly_analysis >= WEEKLY_ANALYSIS_INTERVAL_SECONDS:
            try:
                subprocess.run(["python", "analyse_live.py", "--log"], check=False)
            except Exception as e:
                print(f"⚠️ Erreur lors de l'analyse live hebdomadaire : {e}")
            last_weekly_analysis = now

        time.sleep(60)
