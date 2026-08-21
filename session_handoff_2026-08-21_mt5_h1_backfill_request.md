# Handoff — 21/08/2026 — Demande de backfill H1 via MT5 (VPS)

Suite de `session_handoff_2026-08-20_soir.md` (crowding H2/bloc4 confirmé +
sweep MAX_POSITIONS le 20/08 au soir, cf. commit `bbc0304` juste poussé) et
de la session du 21/08 (test midterm forex + démarrage Piste 2 confluence
multi-horizons, bloqué sur données manquantes — objet de ce fichier).

## 0. Contexte du projet (pour une session qui découvre le repo)

Simulation Monte Carlo multi-comptes prop firm copytrading. Stratégie B =
trades scrapés depuis les signaux Lutessia (technique, calculée en H1
uniquement). Population de production actuelle : `chantier_gold_silver_pop_
B_tradable_pgp_2026-08-20.csv` (n=1248 = 571 forex/indices + 480 gold/
silver + 102 palladium + 95 platinum). Le filtre ADX-fx-only (déjà actif,
séquentiel B->A 3000$, trailing 0,10x) s'applique aux 571 forex/indices
uniquement, jamais aux métaux.

## 1. État committé/poussé à l'instant de ce handoff

Tout le travail de la session du 20/08 soir (script + résultats crowding/
MAX_POSITIONS) vient d'être commité et poussé : commit `bbc0304` sur `main`.
**Rien n'est en attente côté local avant ce backfill** — le repo distant
(`origin` = https://github.com/naelpropf/lutessia-bot) est à jour avec le
local au moment de l'écriture de ce fichier. Après le backfill MT5, pull ce
commit avant de continuer.

Note conforme aux conventions du projet : la plupart des CSV générés (`*.
csv`) sont dans `.gitignore` sauf whitelist explicite (`correlation_matrix.
csv`, `chantier_gold_silver_pop_B_tradable_pgp_2026-08-20.csv`) — ne pas
s'étonner que les CSV de résultats (ex: `chantier_maxpos_crowding_sweep_
pgp_mp{3,4,5}_2026-08-20.csv`) ne soient pas dans git ; les scripts qui les
régénèrent le sont.

## 2. Ce qui bloque — Piste 2 (confluence multi-horizons EMA/MACD)

Chantier exploratoire (screening n=300-like, PAS un résultat à adopter) :
tester si un filtre de confluence multi-horizons (pente EMA courte/longue +
signe MACD(12,26,9) à ces mêmes 2 horizons, horizons calibrés à 8 et 40
bougies H1 sur la distribution de durée de vie des trades B, médiane=8,63h/
p90=41,26h) change les stats de bloc2 (fenêtre calendaire 2022-08-20 ->
2023-12-17, régime "chop" déjà diagnostiqué -- signature MACD/AROON/
SuperTrend fouettés).

**Blocage** : `tp_sequence_analysis.fetch_h1_history` (source Yahoo
Finance) est plafonné à ~730 jours d'historique intraday -- le cache local
démarre au 2024-07-30 pour tous les tickers forex/indices. Vérifié
précisément par croisement avec les 4 bornes calendaires (`date_subperiods`,
ancrage A/B commun) :

| Bloc | Fenêtre | n (fx+idx, B_tradable) | Couverture H1 actuelle |
|---|---|---|---|
| bloc1 | 2021-04-23 -> 2022-08-20 | 70 | 0% |
| **bloc2** | **2022-08-20 -> 2023-12-17** | **160** | **0%** |
| bloc3 | 2023-12-17 -> 2025-04-15 | 149 | 55,7% (83/149) |
| bloc4 | 2025-04-15 -> 2026-08-12 | 192 | 100% |

bloc2 (la cible du diagnostic) est entièrement hors de la fenêtre Yahoo --
aucun calcul EMA/MACD possible dessus avec l'infra actuelle. Décision prise
avec l'utilisateur (21/08) : backfill via MT5 sur le VPS plutôt que
d'abandonner ou de changer de cible.

## 3. Demande précise — données H1 à récupérer via MT5

**Symboles** (18 lignes -- ticker Lutessia -> équivalent Yahoo déjà utilisé
dans le projet pour référence, à mapper vers le symbole MT5 équivalent du
broker utilisé) :

| Ticker Lutessia (population) | Symbole Yahoo (référence, NON MT5) |
|---|---|
| AUD/JPY | AUDJPY=X |
| AUD/USD | AUDUSD=X |
| CHF/JPY | CHFJPY=X |
| EUR/CHF | EURCHF=X |
| EUR/GBP | EURGBP=X |
| EUR/JPY | EURJPY=X |
| EUR/USD | EURUSD=X |
| GBP/CHF | GBPCHF=X |
| GBP/JPY | GBPJPY=X |
| GBP/USD | GBPUSD=X |
| NZD/USD | NZDUSD=X |
| USD/CAD | USDCAD=X |
| USD/CHF | USDCHF=X |
| USD/JPY | USDJPY=X |
| DAX40 FULL0926 | ^GDAXI |
| DAX40 PERF INDEX | ^GDAXI |
| NASDAQ100 - MINI NASDAQ100 FULL0926 | ^NDX |
| NASDAQ100 INDEX | ^NDX |
| S&P500 - MINI S&P500 FULL0926 | ^GSPC |

(les 2 labels DAX40 partagent le même sous-jacent, idem les 2 labels
NASDAQ100 -- un seul symbole MT5 à récupérer pour chaque paire de labels.)

**Timeframe** : H1.

**Plage de dates** : **2022-01-15 -> 2023-12-10** (couvre les 230 trades
bloc1+bloc2 réels de la population, du 2022-01-27 au 2023-12-06, avec
marge de ~10j avant/après pour le warm-up des indicateurs -- l'horizon
long calibré ne fait que 40 bougies H1, donc la marge est large).

**Format de sortie attendu** (même schéma que `tp_sequence_analysis.
fetch_h1_history`, pour réintégration directe sans adaptation de code) :
CSV par ticker/symbole, colonnes exactes `datetime,open,high,low,close`
(pas de volume nécessaire), `datetime` en heure identique à la convention
déjà utilisée dans le projet pour les bougies H1 existantes (vérifier
cohérence avec un fichier déjà en cache, ex. `EURUSD=X` dans le cache
yfinance local, avant de considérer le backfill terminé -- décalage
horaire silencieux = bug d'alignement classique de ce projet, cf. mémoire
`feedback_index_alignment_bug_pattern`).

**Convention de nommage suggérée** (pour éviter tout conflit avec le cache
yfinance existant) : `mt5_h1_backfill_{SYMBOLE}_2026-08-21.csv` un fichier
par symbole MT5 (14 forex + ^GDAXI/^GSPC/^NDX-équivalents = 17 fichiers),
à la racine du repo, committés (ce sont des données de référence longue
durée, pas un résultat de run -- à ajouter explicitement au whitelist
`.gitignore` si besoin, comme `correlation_matrix.csv`).

## 4. Après le backfill

Une fois pull/repush fait : réintégrer ces CSV dans une fonction de
chargement (mapper ticker Lutessia -> fichier backfill au lieu de
`tpseq.fetch_h1_history` pour les dates < 2024-07-30, garder Yahoo pour le
reste), recalculer la couverture bloc1/bloc2 (devrait passer à ~100%), puis
reprendre Piste 2 à l'Étape 2 (calcul EMA/MACD 2 horizons) telle que
spécifiée dans la conversation du 21/08 (horizons EMA = période directe
8/40 bougies H1, pas de convention Lutessia externe à matcher ; MACD(12,26,9)
calculé sur fenêtre glissante des `horizon` dernières bougies avant entrée,
interprétation à confirmer avec l'utilisateur si besoin). Référence bloc2 à
battre : recalculée fraîchement sur les 571 forex/indices (PAS n=1248,
métaux exclus), métrique `r_trailing` (déjà corrigé du trailing stop) --
PAS les chiffres 42,12%/+0,0135R/p=0,0025 cités initialement (introuvables
dans repo/mémoire, invalidés par l'utilisateur au profit d'un recalcul
propre).
