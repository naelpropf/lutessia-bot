import requests

BOT_TOKEN = "
8874281357 : AAFVy2x5KgLhkc-3AKT8aVdwVgqoMH8aMbw"
CHAT_ID = "-5301699978"

def envoyer_test():
    message = "🚀 System Test OK !\nLe Bot Telegram est parfaitement connecté."
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message
    }
    
    response = requests.post(url, data=payload)
    if response.status_code == 200:
        print("✅ Message envoyé avec succès !")
    else:
        print(f"❌ Erreur : {response.text}")

envoyer_test()
EOF
