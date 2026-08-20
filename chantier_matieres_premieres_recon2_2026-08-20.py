"""Reconnaissance v2 (suite de chantier_matieres_premieres_recon_2026-08-20.py) :
extension du scan a plus de pages (liste seule, PAS de fetch detail -- tp1_init/
tp2_init/stop_loss_init viennent deja de la page liste, seul prix_entree requiert
un fetch detail et n'est PAS le champ a risque, cf. verification FULLxxxx faite
avant ce chantier : 157/157 FULL rows ont prix_entree rempli, 157/157 ont
tp1_init NUL). Capture TOUTES les occurrences (pas juste la 1ere) pour les 8
matieres premieres cibles, + verifie la presence du suffixe "FULL" (contrat date)
sur les tickers matches -- indicateur direct du risque de parsing, deja confirme
sur GOLD/SILVER FULLxxxx et observe aussi sur EUR/GBP FULL0926 / EUR/CHF FULL0926
(paires forex ordinaires) dans le scan v1 -- donc pas specifique aux matieres
premieres, potentiellement un phenomene periodique lie a une bascule de flux
de donnees (rollover contrat) plutot qu'a la categorie d'actif.
"""
import re
import sys
import time
from collections import Counter, defaultdict

import pandas as pd
from bs4 import BeautifulSoup

import scraper

ARCHIVES_URL_FX = f"{scraper.BASE_URL}/fr/analyses-lutessia-opportunities/ab_3-fx-indices"

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
EXCLUDE_SUBSTRINGS = ["COPPER MOUNTAIN", "ZINC OF IRELAND", "LEADER"]


def matches_any(ticker, keywords):
    upper = ticker.upper()
    if any(exc in upper for exc in EXCLUDE_SUBSTRINGS):
        return False
    return any(kw in upper for kw in keywords)


def scan_range(start_page, end_page, csv_out=None):
    all_ticker_counts = Counter()
    commodity_rows = defaultdict(list)
    total_rows = 0
    page = start_page
    while page <= end_page:
        url = ARCHIVES_URL_FX if page == 1 else f"{ARCHIVES_URL_FX}?p={page}"
        if page % 10 == 0 or page == start_page:
            print(f"[scan2] page {page}/{end_page}...", flush=True)
        response = scraper._get_with_retries(url)
        if response is None:
            print(f"[scan2] echec page {page}, on continue.", flush=True)
            page += 1
            time.sleep(scraper.CRAWL_DELAY_SECONDS)
            continue

        soup = BeautifulSoup(response.text, "lxml")
        table = scraper._get_archive_table(soup)
        rows = table.select("tr.js-link") if table else []
        if not rows:
            print(f"[scan2] plus de lignes a la page {page}, fin anticipee.", flush=True)
            break

        for row in rows:
            parsed = scraper._parse_archive_row(row)
            if parsed is None:
                continue
            total_rows += 1
            all_ticker_counts[parsed["ticker"]] += 1
            for name, kws in COMMODITY_KEYWORDS.items():
                if matches_any(parsed["ticker"], kws):
                    commodity_rows[name].append({
                        "date_creation": parsed["date_creation"],
                        "ticker": parsed["ticker"],
                        "timeframe": parsed["timeframe"],
                        "stop_loss_init": parsed["stop_loss_init"],
                        "tp1_init": parsed["tp1_init"],
                        "tp2_init": parsed["tp2_init"],
                        "statut_final": parsed["statut_final"],
                        "is_full_dated": "FULL" in parsed["ticker"].upper(),
                    })

        next_link = soup.select_one("a.pagination-nav.next")
        if not next_link:
            print(f"[scan2] derniere page atteinte ({page}).", flush=True)
            break
        page += 1
        time.sleep(scraper.CRAWL_DELAY_SECONDS)

    print(f"\n--- {total_rows} lignes scannees, pages {start_page}-{page} ---")
    rows_out = []
    for name in COMMODITY_KEYWORDS:
        matches = commodity_rows.get(name, [])
        n_full = sum(1 for m in matches if m["is_full_dated"])
        n_tp1_null = sum(1 for m in matches if m["tp1_init"] is None)
        n_full_tp1_null = sum(1 for m in matches if m["is_full_dated"] and m["tp1_init"] is None)
        print(f"\n[{name}] {len(matches)} lignes trouvees, {n_full} avec suffixe FULL (contrat date), "
              f"{n_tp1_null} avec tp1_init NUL ({n_full_tp1_null} parmi les FULL)")
        distinct_tickers = Counter(m["ticker"] for m in matches)
        for t, c in distinct_tickers.most_common():
            print(f"    ticker: {t:30s} x{c}")
        for m in matches[:5]:
            print(f"    ex: {m}")
        rows_out.extend({**m, "commodity": name} for m in matches)

    if csv_out and rows_out:
        pd.DataFrame(rows_out).to_csv(csv_out, index=False)
        print(f"\nSauvegarde : {csv_out} ({len(rows_out)} lignes)")

    print("\n--- Volume total par commodite estime sur la plage scannee ---")
    for name in COMMODITY_KEYWORDS:
        print(f"  {name:15s} {len(commodity_rows.get(name, []))}")

    return commodity_rows, all_ticker_counts, total_rows


if __name__ == "__main__":
    start_page = int(sys.argv[1]) if len(sys.argv) > 1 else 201
    end_page = int(sys.argv[2]) if len(sys.argv) > 2 else 700
    csv_out = sys.argv[3] if len(sys.argv) > 3 else "chantier_matieres_premieres_recon2_2026-08-20.csv"
    scan_range(start_page, end_page, csv_out=csv_out)
