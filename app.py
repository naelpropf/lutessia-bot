import imaplib
import email
from email.header import decode_header
import re
import time
import requests

# --- CONFIGURATION TELEGRAM ---
BOT_TOKEN = "8874281357:AAFVy2x5KgLhkc-3"
CHAT_ID = "-5301699978"

# --- CONFIGURATION EMAIL ---
IMAP_SERVER = "imap.gmail.com"
EMAIL_USER = "lutessia.propfirm@gmail.com"
EMAIL_PASS = "agjl ciie hzkr puya"

def envoyer_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"❌ Erreur envoi Telegram : {e}")

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
                            alerte = f"🚨 *Signal validé* (R:R {rr_value})\n\nSujet : {subject}"
                            envoyer_telegram(alerte)
                            
        mail.logout()
    except Exception as e:
        print(f"⚠️ Erreur lors du scan email : {e}")

if __name__ == "__main__":
    print("🚀 Bot Lutessia démarré !")
    envoyer_telegram("🚀 *Bot Lutessia opérationnel (H24)*")
    while True:
        verifier_mails()
        time.sleep(60)
