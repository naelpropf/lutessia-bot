"""Pilote scraping paires forex exotiques (session 2026-08-19).

N'écrit PAS dans TARGET_FOREX_TICKERS de scraper.py (config de production
intacte) -- liste temporaire séparée PILOT_TICKERS ci-dessous.

Découverte clé de cette session : la page d'archives Lutessia globale
(scraper.ARCHIVES_URL) mélange TOUTES les classes d'actifs (actions, crypto,
FX/indices) et nécessite ~15-20k pages pour l'historique complet -- c'est
pourquoi le scraper de production a mis autant de temps à tourner à l'origine.
Il existe une vue filtrée par catégorie sur le site
(/fr/analyses-lutessia-opportunities/ab_3-fx-indices) qui ne contient QUE les
lignes FX/Indices : ~1595 pages au 19/08/2026 pour tout l'historique
disponible (jusqu'à avril 2021, donc un léger surplus vs la fenêtre
2022-2026 de la population actuelle -- pas corrigé ici, à filtrer par date si
besoin en aval plutôt que risquer de tronquer la fenêtre en pariant sur un
numéro de page approximatif). Le coût de la pagination (poste dominant :
~80 min pour 1595 pages à 3s/page) est FIXE quel que soit le nombre de
tickers ciblés -- ne restreindre qu'à quelques paires ne réduit donc que le
coût des requêtes de fiche détail (3s par ligne retenue), pas le coût de la
pagination elle-même.
"""
import time

import pandas as pd
from bs4 import BeautifulSoup

import scraper

PILOT_TICKERS = {
    "USD/ZAR", "USD/NOK", "USD/MXN", "USD/SEK",
    "EUR/ZAR", "GBP/ZAR", "USD/HUF", "USD/CNH",
}

ARCHIVES_URL_FX = f"{scraper.BASE_URL}/fr/analyses-lutessia-opportunities/ab_3-fx-indices"

CSV_PATH = "historique_exotiques_pilote_2026-08-19.csv"


def scrape_pilot(max_pages=None, save_every=50, csv_path=CSV_PATH):
    extracted_data = []
    start_time = time.monotonic()
    print(f"Lancement du pilote exotiques (catégorie FX/Indices, {len(PILOT_TICKERS)} paires ciblées)...", flush=True)

    page = 1
    while True:
        url = ARCHIVES_URL_FX if page == 1 else f"{ARCHIVES_URL_FX}?p={page}"
        elapsed_min = (time.monotonic() - start_time) / 60
        print(
            f"Récupération de la page {page}"
            + (f"/{max_pages}" if max_pages else "")
            + f"... ({len(extracted_data)} lignes retenues, {elapsed_min:.1f} min écoulées)",
            flush=True,
        )

        response = scraper._get_with_retries(url)
        if response is None:
            print(f"Échec définitif sur la page {page}, on passe à la suivante.", flush=True)
            if max_pages is not None and page >= max_pages:
                break
            page += 1
            time.sleep(scraper.CRAWL_DELAY_SECONDS)
            continue

        soup = BeautifulSoup(response.text, "lxml")
        table = scraper._get_archive_table(soup)
        rows = table.select("tr.js-link") if table else []

        if not rows:
            print("Aucune ligne trouvée, fin de la pagination.", flush=True)
            break

        for row in rows:
            parsed = scraper._parse_archive_row(row)
            if parsed is None:
                continue

            if parsed["ticker"] not in PILOT_TICKERS:
                continue

            prix_entree = scraper._fetch_entry_price(parsed["detail_url"]) if parsed["detail_url"] else None
            stop_loss_init = parsed["stop_loss_init"]

            extracted_data.append({
                "date_creation": parsed["date_creation"],
                "ticker": parsed["ticker"],
                "asset_class": parsed["asset_class"],
                "timeframe": parsed["timeframe"],
                "prix_entree": prix_entree,
                "stop_loss_init": stop_loss_init,
                "tp1_init": parsed["tp1_init"],
                "tp2_init": parsed["tp2_init"],
                "rr_tp1": scraper._compute_rr(prix_entree, stop_loss_init, parsed["tp1_init"]),
                "rr_tp2": scraper._compute_rr(prix_entree, stop_loss_init, parsed["tp2_init"]),
                "statut_final": parsed["statut_final"],
                "score_force": parsed["score_force"],
            })

        if save_every and page % save_every == 0:
            if scraper._safe_save_csv(pd.DataFrame(extracted_data, columns=scraper.CSV_COLUMNS), csv_path):
                print(f"Sauvegarde intermédiaire à la page {page} ({len(extracted_data)} lignes).", flush=True)

        if max_pages is not None and page >= max_pages:
            print(f"Limite de {max_pages} page(s) atteinte.", flush=True)
            break

        next_link = soup.select_one("a.pagination-nav.next")
        if not next_link:
            print("Dernière page atteinte.", flush=True)
            break

        page += 1
        time.sleep(scraper.CRAWL_DELAY_SECONDS)

    df = pd.DataFrame(extracted_data, columns=scraper.CSV_COLUMNS)
    scraper._safe_save_csv(df, csv_path)
    elapsed_min = (time.monotonic() - start_time) / 60
    print(f"Extraction terminée. {len(df)} lignes enregistrées. ({elapsed_min:.1f} min écoulées)", flush=True)


if __name__ == "__main__":
    import sys
    max_pages = int(sys.argv[1]) if len(sys.argv) > 1 else None
    scrape_pilot(max_pages=max_pages)
