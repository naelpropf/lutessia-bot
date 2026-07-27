import time
from bs4 import BeautifulSoup
import pandas as pd
import requests

TARGET_URL = "https://fr.centralcharts.com"

def scrape_lutessia_archives():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    extracted_data = []
    print("Lancement du scraper des archives...")

    try:
        response = requests.get(TARGET_URL, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            lignes_tableau = soup.find_all("tr")
            for ligne in lignes_tableau:
                colonnes = ligne.find_all("td")
                if len(colonnes) >= 8:
                    extracted_data.append({
                        "date_creation": colonnes[0].text.strip(),
                        "ticker": colonnes[1].text.strip(),
                        "asset_class": colonnes[2].text.strip(),
                        "timeframe": colonnes[3].text.strip(),
                        "prix_entree": colonnes[4].text.strip(),
                        "stop_loss_init": colonnes[5].text.strip(),
                        "tp1_init": colonnes[6].text.strip(),
                        "rr_theorique": 2.0,
                        "statut_final": colonnes[7].text.strip()
                    })
            
            time.sleep(3)
        else:
            print(f"Erreur HTTP : {response.status_code}")

    except Exception as e:
        print(f"Erreur lors de la requête : {e}")

    df = pd.DataFrame(
        extracted_data,
        columns=[
            "date_creation",
            "ticker",
            "asset_class",
            "timeframe",
            "prix_entree",
            "stop_loss_init",
            "tp1_init",
            "rr_theorique",
            "statut_final",
        ],
    )
    
    df.to_csv("historique_lutessia.csv", index=False)
    print("Extraction terminée. Données enregistrées.")

if __name__ == "__main__":
    scrape_lutessia_archives()
