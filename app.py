import imaplib
import email
from email.header import decode_header
import re
import time
import requests

# --- CONFIGURATION TELEGRAM ---
BOT_TOKEN = "8874281357:AAFVy2x5KgLhkc-3AKT8aVdwVgqoMH8aMbw"
CHAT_ID = "-5301699978"

# --- CONFIGURATION EMAIL (À remplir si ce n'est pas déjà fait) ---
IMAP_SERVER = "imap.gmail.com"
EMAIL_USER = "lutessia.propfirm@gmail.com"        # Ton adresse Gmail
EMAIL_PASS = "agjl ciie hzkr puya"      # Mot de passe d'application Gmail

def envoyer_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"❌ Erreur envoi Telegram : {e}")

def verifier_mails():
    try:
        # Connexion à la boîte mail
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_USER, EMAIL_PASS)
        mail.select("inbox")

        # Recherche des mails non lus
        status, messages = mail.search(None, 'UNSEEN')
        email_ids = messages[0].split()

        for e_id in email_ids:
            _, msg_data = mail.fetch(e_id, '(RFC822)')
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8")
                    
                    # On vérifie si le mail vient de Lutessia / contient une alerte
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode()
                    else:
                        body = msg.get_payload(decode=True).decode()

                    # Extraction du R:R (ex: cherche un format du type "R:R 1:2.5" ou "RR: 2.1")
                    match = re.search(r'(?:R:R|RR|Ratio)\s*[:=]?\s*1\s*:\s*([\d\.]+)', body, re.IGNORECASE)
                    if match:
                        rr_value = float(match.group(1))
                        if rr_value >= 2.0:  # Si R:R supérieur ou égal à 1:2
                            alerte = f"🚨 *NOUVELLE ALERTE LUTESSIA*\n\n📊 **Ratio R:R** : 1:{rr_value}\n📩 **Sujet** : {subject}"
                            envoyer_telegram(alerte)

        mail.logout()
    except Exception as e:
        print(f"⚠️ Erreur lors du scan email : {e}")

# --- BOUCLE DE SCAN H24 ---
print("🚀 Bot Lutessia démarré !")
envoyer_telegram("🚀 *Bot Lutessia opérationnel !* Analyse automatique des R:R >= 1:2 activée.")

while True:
    verifier_mails()
    time.sleep(60)  # Attend 60 secondes avant de re-scanner
