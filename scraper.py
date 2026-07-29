import re
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.centralcharts.com"
ARCHIVES_URL = f"{BASE_URL}/fr/analyses-lutessia-opportunities"
LOGIN_URL = f"{BASE_URL}/fr/connexion"
CRAWL_DELAY_SECONDS = 3  # aligné sur le Crawl-delay du robots.txt de centralcharts.com

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def create_authenticated_session(login, password):
    """Session requests connectée à CentralCharts (nécessaire pour lire les fiches
    d'analyses EN COURS/non résolues, contrairement aux archives déjà résolues qui
    restent publiques). Formulaire vérifié sur /fr/connexion : champs login/password/
    redirect, pas de token CSRF, juste le cookie de session PHPSESSID posé au GET
    initial. Retourne la Session (à réutiliser pour tous les appels suivants) ou None
    si la connexion échoue."""
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        session.get(LOGIN_URL, timeout=15)
        response = session.post(
            LOGIN_URL,
            data={"login": login, "password": password, "redirect": "", "submit": "Connexion"},
            timeout=15,
        )
    except requests.RequestException as e:
        print(f"Erreur lors de la connexion à CentralCharts : {e}")
        return None

    # Après une connexion réussie, le site redirige hors de /fr/connexion. Si le
    # formulaire de login est encore présent dans la réponse, la connexion a échoué
    # (identifiants refusés).
    if "connexion" in response.url and 'name="password"' in response.text:
        print("Échec de connexion à CentralCharts : identifiants refusés.")
        return None

    return session


def _get_with_retries(url, retries=3, backoff=5):
    """GET avec quelques tentatives : un hoquet réseau ponctuel ne doit pas faire
    échouer un scraping de plusieurs heures. Retourne None si toutes échouent."""
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
        except requests.RequestException as e:
            print(f"Erreur réseau ({url}), tentative {attempt}/{retries} : {e}", flush=True)
        else:
            if response.status_code == 200:
                return response
            print(f"Erreur HTTP {response.status_code} ({url}), tentative {attempt}/{retries}", flush=True)
        if attempt < retries:
            time.sleep(backoff)
    return None


def _safe_save_csv(df, csv_path, retries=3, retry_delay=2):
    """Écrit le CSV avec quelques tentatives : sur Windows, OneDrive ou l'antivirus
    peut verrouiller brièvement un fichier en cours de synchro/scan (PermissionError)."""
    for attempt in range(1, retries + 1):
        try:
            df.to_csv(csv_path, index=False)
            return True
        except PermissionError as e:
            print(f"Écriture CSV échouée (tentative {attempt}/{retries}) : {e}", flush=True)
            if attempt < retries:
                time.sleep(retry_delay)
    print(f"Abandon de la sauvegarde CSV pour ce checkpoint ({csv_path}).", flush=True)
    return False

TARGET_FOREX_TICKERS = {
    # Forex majeures
    "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "USD/CAD", "AUD/USD", "NZD/USD",
    # Forex croisées majeures
    "EUR/GBP", "EUR/JPY", "EUR/CHF", "GBP/JPY", "GBP/CHF", "AUD/JPY", "CHF/JPY",
    # Métaux
    "XAU/USD", "XAG/USD",
}
# Noms réels observés sur CentralCharts (vérifiés via autocomplete) :
# US30 -> DJ30, NAS100 -> NASDAQ100, SP500 -> S&P500 (pas "SP500" sans esperluette,
# qui ratait les tickers réels), UK100/FTSE -> FTSE100, GER40/DAX -> DAX40 (bare
# "DAX" matchait aussi les indices sectoriels DAXSEC.* à tort).
TARGET_INDEX_KEYWORDS = ["DAX40", "DJ30", "NASDAQ100", "S&P500", "FTSE100"]

# BTC/ETH en USD spot uniquement, ex. ticker Lutessia "BITCOIN - BTC/USD". Comparé en
# suffixe (pas simple "in") pour ne pas capter "BTC/USDT" ("BTC/USD" en est un préfixe).
TARGET_CRYPTO_SUFFIXES = ["BTC/USD", "ETH/USD"]


def _is_target_asset(ticker):
    if ticker in TARGET_FOREX_TICKERS:
        return True
    upper = ticker.upper()
    if any(keyword in upper for keyword in TARGET_INDEX_KEYWORDS):
        return True
    return any(upper.endswith(suffix) for suffix in TARGET_CRYPTO_SUFFIXES)


CSV_COLUMNS = [
    "date_creation",
    "ticker",
    "asset_class",
    "timeframe",
    "prix_entree",
    "stop_loss_init",
    "tp1_init",
    "tp2_init",
    "rr_tp1",
    "rr_tp2",
    "statut_final",
]


def _parse_price(text):
    if not text:
        return None
    cleaned = text.replace("\xa0", " ").strip()
    cleaned = re.sub(r"[^0-9,.\s-]", "", cleaned)
    cleaned = cleaned.replace(" ", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _compute_rr(prix_entree, stop_loss_init, target):
    if prix_entree is None or stop_loss_init is None or target is None:
        return None
    risque = abs(prix_entree - stop_loss_init)
    if risque == 0:
        return None
    return abs(target - prix_entree) / risque


def _get_archive_table(soup):
    return soup.select_one("table.tabAnalysis")


QUOTE_PRICE_PATTERN = re.compile(r"(?:est de|cote)\s*([\d][\d\s.,]*\d)")


def _fetch_entry_price(detail_url):
    """Récupère la cotation affichée sur la fiche individuelle d'un signal (prix d'entrée).

    Le widget de cotation (.hp-cot-val) n'est peuplé que côté JS après chargement et vaut
    toujours "-" dans le HTML brut ; on récupère donc le prix depuis la phrase générée
    côté serveur dans le bloc "Cotations" : "La cotation de X est de Y" / "Le cours de X est
    de Y" pour les indices, "X/Y cote Z" pour le forex.
    """
    time.sleep(CRAWL_DELAY_SECONDS)
    try:
        response = requests.get(detail_url, headers=HEADERS, timeout=15)
    except requests.RequestException as e:
        print(f"Erreur lors de la requête détail ({detail_url}) : {e}")
        return None

    if response.status_code != 200:
        print(f"Erreur HTTP sur la fiche détail ({detail_url}) : {response.status_code}")
        return None

    detail_soup = BeautifulSoup(response.text, "lxml")
    cotations_div = detail_soup.select_one("div.bloc-section-cotations")
    if not cotations_div:
        return None

    match = QUOTE_PRICE_PATTERN.search(cotations_div.get_text(" ", strip=True))
    return _parse_price(match.group(1)) if match else None


TIMEFRAME_PATTERN = re.compile(r"Unité de temps\s*:\s*(\S+)")


def fetch_signal_detail(detail_url, session=None):
    """Récupère prix d'entrée, seuil d'invalidation (SL) et objectifs (TP1/TP2)
    directement depuis la fiche individuelle d'un signal — utilisé par app.py pour
    les signaux reçus par email en direct, qui n'ont pas de ligne de liste associée
    (contrairement au scraping d'archives, où stop_loss_init/tp1_init/tp2_init
    viennent de la page liste). Pas de délai crawl-delay ici : requête ponctuelle
    déclenchée par un signal réel, pas du scraping en masse.

    session : requests.Session déjà authentifiée (create_authenticated_session),
    nécessaire pour les analyses encore EN COURS (non publiques sans connexion) ;
    None utilise une requête anonyme (suffisant pour les archives déjà résolues).

    Retourne un dict {prix_entree, stop_loss_init, tp1_init, tp2_init, timeframe} ou
    None si la fiche n'est pas accessible (redirection — typique d'une analyse encore
    "EN COURS" sans session authentifiée) ou si les valeurs attendues sont absentes.
    """
    requester = session if session is not None else requests
    try:
        response = requester.get(detail_url, headers=HEADERS, timeout=15)
    except requests.RequestException as e:
        print(f"Erreur lors de la requête détail ({detail_url}) : {e}")
        return None

    if response.status_code != 200 or response.history:
        print(f"Fiche détail inaccessible ({detail_url}) : redirection ou erreur HTTP {response.status_code}.")
        return None

    detail_soup = BeautifulSoup(response.text, "lxml")

    cotations_div = detail_soup.select_one("div.bloc-section-cotations")
    prix_entree = None
    if cotations_div:
        match = QUOTE_PRICE_PATTERN.search(cotations_div.get_text(" ", strip=True))
        prix_entree = _parse_price(match.group(1)) if match else None

    opinion_span = detail_soup.select_one("div.sy-opinion span.valToHide")
    stop_loss_init = _parse_price(opinion_span.get_text()) if opinion_span else None

    tp_divs = detail_soup.select("div.sy-tp")
    tp1_init = tp2_init = None
    if len(tp_divs) >= 1:
        val = tp_divs[0].select_one("span.valToHide")
        tp1_init = _parse_price(val.get_text()) if val else None
    if len(tp_divs) >= 2:
        val = tp_divs[1].select_one("span.valToHide")
        tp2_init = _parse_price(val.get_text()) if val else None

    timeframe = None
    tf_match = TIMEFRAME_PATTERN.search(detail_soup.get_text(" ", strip=True))
    if tf_match:
        timeframe = tf_match.group(1)

    if prix_entree is None or stop_loss_init is None or tp1_init is None:
        return None

    return {
        "prix_entree": prix_entree,
        "stop_loss_init": stop_loss_init,
        "tp1_init": tp1_init,
        "tp2_init": tp2_init,
        "timeframe": timeframe or "1H",
    }


def _parse_archive_row(row):
    ticker_cell = row.select_one("td:nth-of-type(2)")
    if ticker_cell is None:
        return None

    ticker_link = ticker_cell.select_one("b")
    ticker = ticker_link.text.strip() if ticker_link else ticker_cell.text.strip()

    asset_tag = ticker_cell.select_one(".abonnement_tag")
    asset_class = asset_tag.text.strip() if asset_tag else ""

    date_span = ticker_cell.select_one(".set-elapsed-time")
    date_creation = date_span["data-date"] if date_span and date_span.has_attr("data-date") else ""

    status_span = row.select_one('[class*="ia-status"]')
    statut_final = status_span.text.strip() if status_span else ""

    timeframe_cell = row.select_one("td:nth-of-type(4)")
    timeframe = timeframe_cell.text.strip() if timeframe_cell else ""

    opinion_cell = row.select_one("td:nth-of-type(5)")
    stop_loss_init = _parse_price(opinion_cell.text) if opinion_cell else None

    objectifs_cell = row.select_one("td:nth-of-type(6)")
    tp1_init = tp2_init = None
    if objectifs_cell:
        matches = re.findall(r"[\d][\d\s ]*[.,]\d+(?=\s*\()", objectifs_cell.get_text(" "))
        prices = [p for p in (_parse_price(m) for m in matches) if p is not None]
        if len(prices) >= 1:
            tp1_init = prices[0]
        if len(prices) >= 2:
            tp2_init = prices[1]

    detail_path = row.get("data-url")
    detail_url = f"{BASE_URL}{detail_path}" if detail_path else None

    return {
        "date_creation": date_creation,
        "ticker": ticker,
        "asset_class": asset_class,
        "timeframe": timeframe,
        "stop_loss_init": stop_loss_init,
        "tp1_init": tp1_init,
        "tp2_init": tp2_init,
        "statut_final": statut_final,
        "detail_url": detail_url,
    }


def scrape_lutessia_archives(max_pages=None, save_every=50, csv_path="historique_lutessia.csv"):
    extracted_data = []
    start_time = time.monotonic()
    print("Lancement du scraper des archives...", flush=True)

    page = 1
    while True:
        url = ARCHIVES_URL if page == 1 else f"{ARCHIVES_URL}?p={page}"
        elapsed_min = (time.monotonic() - start_time) / 60
        print(
            f"Récupération de la page {page}"
            + (f"/{max_pages}" if max_pages else "")
            + f"... ({len(extracted_data)} lignes retenues, {elapsed_min:.1f} min écoulées)",
            flush=True,
        )

        response = _get_with_retries(url)
        if response is None:
            print(f"Échec définitif sur la page {page}, on passe à la suivante.", flush=True)
            if max_pages is not None and page >= max_pages:
                break
            page += 1
            time.sleep(CRAWL_DELAY_SECONDS)
            continue

        soup = BeautifulSoup(response.text, "lxml")
        table = _get_archive_table(soup)
        rows = table.select("tr.js-link") if table else []

        if not rows:
            print("Aucune ligne trouvée, fin de la pagination.", flush=True)
            break

        for row in rows:
            parsed = _parse_archive_row(row)
            if parsed is None:
                continue

            if not _is_target_asset(parsed["ticker"]):
                continue

            prix_entree = _fetch_entry_price(parsed["detail_url"]) if parsed["detail_url"] else None
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
                "rr_tp1": _compute_rr(prix_entree, stop_loss_init, parsed["tp1_init"]),
                "rr_tp2": _compute_rr(prix_entree, stop_loss_init, parsed["tp2_init"]),
                "statut_final": parsed["statut_final"],
            })

        if save_every and page % save_every == 0:
            if _safe_save_csv(pd.DataFrame(extracted_data, columns=CSV_COLUMNS), csv_path):
                print(f"Sauvegarde intermédiaire à la page {page} ({len(extracted_data)} lignes).", flush=True)

        if max_pages is not None and page >= max_pages:
            print(f"Limite de {max_pages} page(s) atteinte.", flush=True)
            break

        next_link = soup.select_one("a.pagination-nav.next")
        if not next_link:
            print("Dernière page atteinte.", flush=True)
            break

        page += 1
        time.sleep(CRAWL_DELAY_SECONDS)

    df = pd.DataFrame(extracted_data, columns=CSV_COLUMNS)
    _safe_save_csv(df, csv_path)
    elapsed_min = (time.monotonic() - start_time) / 60
    print(f"Extraction terminée. {len(df)} lignes enregistrées. ({elapsed_min:.1f} min écoulées)", flush=True)


if __name__ == "__main__":
    scrape_lutessia_archives()
