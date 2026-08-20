"""Pilote scraping actions Europe (session 2026-08-19), meme methode que le
pilote paires exotiques (chantier_exotiques_pilote_2026-08-19.py:1-21) --
scraping cible sur la vue categorie (pas les archives globales melangees),
filtrage post-hoc sur les tickers candidats.

N'ecrit PAS dans TARGET_FOREX_TICKERS de scraper.py (config de production
intacte) -- liste temporaire separee PILOT_KEYWORDS ci-dessous.

Difference cle vs le pilote exotiques : les tickers exacts affiches sur
CentralCharts pour les actions (nom complet vs abrege) ne sont pas connus a
l'avance (contrairement aux paires forex "USD/ZAR" etc., format fixe connu).
Matching par MOT-CLE (comme scraper.TARGET_INDEX_KEYWORDS,
scraper.py:94/101-107), pas par egalite exacte -- evite de rater des lignes
a cause d'un nom complet different de l'abreviation.

Candidats prioritaires (6, categorie Actions Europe) : LVMH, TotalEnergies,
Sanofi (France), SAP, Siemens, Allianz (Allemagne).

Cout dominant = pagination (~4176 pages x 3s = ~3h30, FIXE quel que soit le
nombre de tickers cibles, meme raisonnement que chantier_exotiques_pilote_
2026-08-19.py:16-20) -- le filtrage par mot-cle ne reduit que le cout des
requetes de fiche detail (3s/ligne retenue), pas la pagination elle-meme.
"""
import re
import time
from collections import Counter

import pandas as pd
from bs4 import BeautifulSoup

import scraper

# <<< CORRECTIF post-validation-15-pages (2026-08-19) : un simple `in` substring
# (1re version de ce script) capturait des FAUX POSITIFS -- entites cotees
# DISTINCTES de la maison mere candidate, meme nom de marque :
#   "SIEMENS ENERGY" (spin-off 2020, action separee) matche par substring
#   "SIEMENS" -- exclu explicitement, memes raisons "SIEMENS HEALTHINEERS"
#   (spin-off 2018, jamais vu dans l'echantillon 15p mais meme risque).
#   "TOTALENERGIESGABON" (filiale gabonaise cotee separement sur Euronext,
#   PAS l'action mere) matche par substring "TOTALENERGIES" -- exclue.
# Passage a un match par mot-entier (\b...\b) + liste d'exclusion explicite.
# "SANOFI INHABER" CONSERVE (Inhaberaktien = designation "actions au porteur"
# d'une cotation Xetra de la MEME entite Sanofi, pas une filiale distincte).
PILOT_KEYWORDS = [
    "LVMH", "TOTALENERGIES", "SANOFI", "SAP", "SIEMENS", "ALLIANZ",
]
PILOT_EXCLUDE_SUBSTRINGS = [
    "SIEMENS ENERGY", "SIEMENS HEALTHINEERS", "TOTALENERGIESGABON",
]

ARCHIVES_URL_ACTIONS_EUROPE = f"{scraper.BASE_URL}/fr/analyses-lutessia-opportunities/ab_1-actions-europe"

CSV_PATH = "historique_actions_europe_pilote_2026-08-19.csv"


def matches_pilot(ticker, keywords=PILOT_KEYWORDS, excludes=PILOT_EXCLUDE_SUBSTRINGS):
    upper = ticker.upper()
    if any(exc in upper for exc in excludes):
        return False
    return any(re.search(rf"\b{re.escape(kw)}\b", upper) for kw in keywords)


def scrape_pilot(max_pages=None, save_every=50, csv_path=CSV_PATH, keywords=PILOT_KEYWORDS,
                  track_all_tickers=False, start_page=1):
    """track_all_tickers=True : comptabilise TOUS les tickers rencontres (sans fetch
    de fiche detail pour les non-candidats) -- utilise pour la validation 15 pages,
    afin de detecter d'eventuels large caps frequents non prevus dans PILOT_KEYWORDS
    (meme demarche que la decouverte USD/SEK sur le pilote exotiques).

    start_page : reprise apres interruption (crash/pause volontaire) -- l'archive est
    triee ANTI-chronologique (page 1 = plus recent), donc reprendre a la page N ne
    cree jamais de chevauchement avec les lignes deja sauvegardees (page < N) : on les
    recharge simplement depuis csv_path et on ajoute les nouvelles a la suite, aucun
    risque de doublon ni de trou."""
    extracted_data = []
    if start_page > 1:
        try:
            extracted_data = pd.read_csv(csv_path).to_dict("records")
            print(f"Reprise a la page {start_page} : {len(extracted_data)} lignes deja sauvegardees rechargees.", flush=True)
        except FileNotFoundError:
            print(f"[!] start_page={start_page} mais {csv_path} introuvable -- reprise a vide.", flush=True)
    all_ticker_counts = Counter()
    start_time = time.monotonic()
    print(f"Lancement du pilote actions Europe (categorie Actions Europe, "
          f"mots-cles ciblés : {keywords})...", flush=True)

    page = start_page
    while True:
        url = ARCHIVES_URL_ACTIONS_EUROPE if page == 1 else f"{ARCHIVES_URL_ACTIONS_EUROPE}?p={page}"
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

            if track_all_tickers:
                all_ticker_counts[parsed["ticker"]] += 1

            if not matches_pilot(parsed["ticker"], keywords):
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

    if track_all_tickers:
        print("\n--- Frequence de TOUS les tickers rencontres (validation, non filtre) ---", flush=True)
        for ticker, count in all_ticker_counts.most_common(30):
            flag = "  <-- CANDIDAT" if matches_pilot(ticker) else ""
            print(f"  {ticker:40s} {count:4d}{flag}", flush=True)

    return df


if __name__ == "__main__":
    import sys
    max_pages_arg = sys.argv[1] if len(sys.argv) > 1 else ""
    max_pages = int(max_pages_arg) if max_pages_arg.strip() else None
    track_all = len(sys.argv) > 2 and sys.argv[2] == "track_all"
    start_page_arg = sys.argv[3] if len(sys.argv) > 3 else ""
    start_page = int(start_page_arg) if start_page_arg.strip() else 1
    scrape_pilot(max_pages=max_pages, track_all_tickers=track_all, start_page=start_page)
