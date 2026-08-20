"""Reconnaissance technique (PAS de scraping massif) sur 8 matieres premieres
potentielles chez Lutessia/CentralCharts : copper, aluminium, natural gas,
lead, nickel, zinc, palladium, platinum.

Meme methode que chantier_or_argent_pilote_2026-08-19.py (categorie
ab_3-fx-indices, qui a deja revele GOLD/SILVER par ce biais) : scan de N
pages avec track_all_tickers pour reperer le nommage exact, puis
echantillon cible (50-100 lignes/matiere) avec fetch de la fiche detail
pour tester le taux d'echec de parsing tp1_init/tp2_init (le vrai bug
FULLxxxx trouve ce script : ce n'est PAS prix_entree qui manque sur les
157 lignes GOLD/SILVER FULLxxxx, mais tp1_init/rr_tp1 -- 157/157 null,
prix_entree 0/157 null -- cf. verification faite avant ce chantier).

N'ecrit PAS dans scraper.py (reconnaissance seule).
"""
import re
import sys
import time
from collections import Counter

import pandas as pd
from bs4 import BeautifulSoup

import scraper

ARCHIVES_URL_FX = f"{scraper.BASE_URL}/fr/analyses-lutessia-opportunities/ab_3-fx-indices"

# Mots-cles par matiere premiere -- nommage CentralCharts inconnu a priori,
# on liste les variantes plausibles (comme GOLD/SILVER ont revele "GOLD - USD").
COMMODITY_KEYWORDS = {
    "copper": ["COPPER", "CUIVRE"],
    "aluminium": ["ALUMINIUM", "ALUMINUM"],
    "natural_gas": ["NATURAL GAS", "NATGAS", "GAZ NATUREL", "NAT GAS"],
    "lead": ["LEAD", "PLOMB"],
    "nickel": ["NICKEL"],
    "zinc": ["ZINC"],
    "palladium": ["PALLADIUM"],
    "platinum": ["PLATINUM", "PLATINE"],
}

# Faux positifs plausibles a exclure par prudence (actions/entites homonymes),
# meme demarche que PILOT_EXCLUDE_SUBSTRINGS pour GOLD/SILVER.
EXCLUDE_SUBSTRINGS = [
    "COPPER MOUNTAIN", "ZINC OF IRELAND",  # mines/actions
]


def matches_any(ticker, keywords):
    upper = ticker.upper()
    if any(exc in upper for exc in EXCLUDE_SUBSTRINGS):
        return False
    return any(kw in upper for kw in keywords)


def scan_ticker_frequency(max_pages, start_page=1):
    """Scan sec (pas de fetch detail) : juste la liste des tickers rencontres
    et leur frequence, categorie ab_3-fx-indices."""
    all_ticker_counts = Counter()
    ticker_sample_row = {}
    total_rows = 0
    page = start_page
    while page < start_page + max_pages:
        url = ARCHIVES_URL_FX if page == 1 else f"{ARCHIVES_URL_FX}?p={page}"
        print(f"[scan] page {page}...", flush=True)
        response = scraper._get_with_retries(url)
        if response is None:
            print(f"[scan] echec page {page}, on continue.", flush=True)
            page += 1
            time.sleep(scraper.CRAWL_DELAY_SECONDS)
            continue

        soup = BeautifulSoup(response.text, "lxml")
        table = scraper._get_archive_table(soup)
        rows = table.select("tr.js-link") if table else []
        if not rows:
            print("[scan] plus de lignes, fin.", flush=True)
            break

        for row in rows:
            parsed = scraper._parse_archive_row(row)
            if parsed is None:
                continue
            total_rows += 1
            all_ticker_counts[parsed["ticker"]] += 1
            if parsed["ticker"] not in ticker_sample_row:
                ticker_sample_row[parsed["ticker"]] = parsed

        next_link = soup.select_one("a.pagination-nav.next")
        if not next_link:
            print("[scan] derniere page atteinte.", flush=True)
            break
        page += 1
        time.sleep(scraper.CRAWL_DELAY_SECONDS)

    return all_ticker_counts, ticker_sample_row, total_rows


def sample_commodity(keywords, target_n, max_pages, csv_out=None):
    """Echantillon cible : parcourt les pages ab_3-fx-indices, ne fetch le detail
    QUE pour les lignes matchant les mots-cles, s'arrete a target_n lignes ou
    max_pages pages (le premier atteint)."""
    extracted = []
    page = 1
    while len(extracted) < target_n and page <= max_pages:
        url = ARCHIVES_URL_FX if page == 1 else f"{ARCHIVES_URL_FX}?p={page}"
        print(f"[sample] page {page} ({len(extracted)}/{target_n} trouves)...", flush=True)
        response = scraper._get_with_retries(url)
        if response is None:
            page += 1
            time.sleep(scraper.CRAWL_DELAY_SECONDS)
            continue

        soup = BeautifulSoup(response.text, "lxml")
        table = scraper._get_archive_table(soup)
        rows = table.select("tr.js-link") if table else []
        if not rows:
            break

        for row in rows:
            parsed = scraper._parse_archive_row(row)
            if parsed is None:
                continue
            if not matches_any(parsed["ticker"], keywords):
                continue

            prix_entree = scraper._fetch_entry_price(parsed["detail_url"]) if parsed["detail_url"] else None
            extracted.append({
                "date_creation": parsed["date_creation"],
                "ticker": parsed["ticker"],
                "asset_class": parsed["asset_class"],
                "timeframe": parsed["timeframe"],
                "prix_entree": prix_entree,
                "stop_loss_init": parsed["stop_loss_init"],
                "tp1_init": parsed["tp1_init"],
                "tp2_init": parsed["tp2_init"],
                "statut_final": parsed["statut_final"],
            })
            if len(extracted) >= target_n:
                break

        next_link = soup.select_one("a.pagination-nav.next")
        if not next_link:
            break
        page += 1
        time.sleep(scraper.CRAWL_DELAY_SECONDS)

    df = pd.DataFrame(extracted)
    if csv_out and len(df):
        df.to_csv(csv_out, index=False)
    return df


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "scan"
    if mode == "scan":
        max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else 100
        counts, samples, total_rows = scan_ticker_frequency(max_pages)
        print(f"\n--- {total_rows} lignes scannees sur {max_pages} pages, {len(counts)} tickers distincts ---")
        for name, kws in COMMODITY_KEYWORDS.items():
            hits = [(t, c) for t, c in counts.items() if matches_any(t, kws)]
            if hits:
                print(f"\n[{name}] MATCH :")
                for t, c in sorted(hits, key=lambda x: -x[1]):
                    print(f"  {t:30s} {c:4d}  ex: {samples[t]}")
            else:
                print(f"\n[{name}] aucun match sur {kws}")
        print("\n--- Top 40 tickers tous confondus (verif visuelle) ---")
        for t, c in counts.most_common(40):
            print(f"  {t:30s} {c:4d}")
