# Résumé de session — soirée du 2026-08-05 (Lutessia bot)

Document de sauvegarde avant clear. Complète `session_summary_2026-08-05.md`
(session de l'après-midi, conservé intact) — ne le remplace pas. Cette session
a traité 4 vagues de questions successives, toutes liées à la viabilité
stratégique de la flotte prop firm : (A) 4 scénarios de calibrage du daily DD
The5%ers, (B) 4 points de vérification méthodologique + grille risque×maxpos,
(C) correction du prix de rachat réaliste (Summer Plan a une date de fin
réelle), (D) 4 points d'exploration stratégique (Régime A, actifs alternatifs,
nouvelles firms, trésorerie dormante), (E) 3 points de suivi sur FXIFY/Ment
Funding, (F) 3 points de suivi supplémentaires (bascule hybride, sourcing Ment
Funding, combiné FXIFY+Ment). Prompt utilisateur explicite à la fin : "sois
précis et complet plutôt que concis — l'objectif est de pouvoir reprendre le
travail sans rien reperdre."

---

## A. Scénarios de calibrage The5%ers (`the5ers_viability_scenarios.py`)

Moteur unique `run_5ers_fleet` paramétrable (n_accounts, palier, challenge_cost,
daily_loss_pct, low_risk, high_risk, ramp_trades, max_positions,
phase1_cap_trades, per_trade_cap_pct), 2000 runs MC / config, block bootstrap
2 mois, mêmes tirages aléatoires (`rng = random.Random(42)` par variante) pour
permettre la recombinaison exacte flotte via `growth_only_cash_{suffix}.csv`
et `three_firm_fleet_dailydd_{suffix}.csv` (colonnes `year1_net_growth` /
`final_net_growth` déjà présentes, réutilisées partout ensuite).

**Résultats flotte complète (5ers 4×100k + FTMO/Blueberry 3 comptes scaling
plafonné, prix 179$ perpétuel — PAS ENCORE CORRIGÉ à ce stade), winrate
37,29% / 32% :**

| Option | Profit final 37,29% | Casses | Cash pire cas | Profit final 32% |
|---|---|---|---|---|
| 1 — statu quo (5ers 2% ramp, 3 pos) | 5 372 936$ | 164,3 | 20 014$ | 3 215 356$ |
| 5 — 5ers maxpos=1 | 5 003 982$ (-6,9%) | 126,4 (-23,1%) | 17 150$ | 3 160 785$ |
| 2 — 5ers risque fixe 1% | 4 610 926$ (-14,2%) | 66,6 (-59,5%) | 13 570$ | 2 960 107$ |
| 4/S4 — sizing plafonné budget DD (~1%/trade) | 4 594 066$ (-14,5%) | 66,3 | 13 570$ | 2 946 552$ |
| 2 — 5ers risque fixe 0,5% | 3 935 717$ (-26,7%) | 55,8 | 12 138$ | 2 491 163$ |
| 3 — tremplin (5ers 0,5% plafonné 15 trades puis stop) | 3 274 042$ (-39,1%) | 52,9 | 10 706$ | 2 052 515$ |
| 4 — abandon pur (croissance seule) | 3 268 903$ (-39,2%) | 52,9 | 9 990$ | 2 050 036$ |

**Conclusions verrouillées** : tremplin ≈ abandon pur (résidu négligeable,
piste rejetée) ; sizing-plafonné ≈ risque fixe 1% (convergent, pas besoin de
la logique complexe de sizing) ; maxpos=1 seul est le meilleur "coup pas
cher" (-7% profit pour -23% casses) ; risque fixe 1% est le meilleur
compromis modéré (-14% profit pour -60% casses, -32% cash pire cas).

**Fichiers** : `the5ers_viability_scenarios.py` (moteur), 26 CSV
`scenario{1..6}*_{37_29pct,32pct}.csv` (2000 lignes chacun, détail par run),
`the5ers_viability_scenarios_summary.csv`, `the5ers_viability_final_synthesis_{37_29pct,32pct}.csv`
(tableau flotte reconstruit ligne à ligne).

---

## B. Vérification méthodologique + grille risque×maxpos (prix 179$ perpétuel)

### Point 1 — Rachat perpétuel à 179$ : confirmé comme hypothèse du code, mais
impact quasi nul sur les chiffres (cutoff testé 12/18/24 MOIS, prix post-cutoff
495$ — CE PRIX ET CE CUTOFF SONT DEVENUS OBSOLÈTES, voir section C ci-dessous).
Raison de l'impact nul : à cutoff 12-24 mois, la quasi-totalité des comptes
sont déjà financés avant le cutoff, donc les rachats sont payés depuis la
réserve (jamais depuis la poche) → cash pire cas quasi inchangé. **Ce
raisonnement s'est avéré FAUX une fois le vrai cutoff (26 jours) testé — voir
section C, le cash pire cas triple en réalité.**

### Point 2 — The5%ers isolé, année 1 vs horizon complet (prix 179$ perpétuel,
OBSOLÈTE — refait en section C avec prix réaliste) : part de l'année 1 dans le
profit total = 22,6-22,9%, LÉGÈREMENT SOUS la part proportionnelle au temps
attendue (25,3% sur un horizon de 3,96 ans) → l'année 1 n'a pas d'avantage
caché, c'est une phase de friction cash nette (casses coûtent cher avant que
la réserve existe). **Ce ratio proportionnel reste valable qualitativement
même après correction du prix (voir section C), seuls les $ absolus
changent.**

### Point 3 — Plein risque puis arrêt programmé (freeze 6/12 mois) : REJETÉ,
dominé sur les 3 métriques par "risque fixe 1% permanent" (moins de profit,
autant/plus de casses, cash pire cas égal ou pire). Fichiers :
`scenario3bis_fullrisk_freeze{6,12}m_{suffix}.csv`.

### Point 4 — Grille risque×maxpos (5 niveaux de risque flat × 3 maxpos = 15
combos × 2 winrates, prix 179$ perpétuel — corrigée en section C) :
**constat clé, toujours valable** : maxpos=2 et maxpos=3 sont quasi
identiques partout (l'exclusion par corrélation limite déjà les positions
réellement simultanées) → le vrai levier est maxpos=1 vs maxpos≥2. Et une
fois le risque déjà réduit (≤1%), maxpos=1 n'apporte presque plus rien
(effet **sous-additif** : les deux leviers agissent sur le même mécanisme
d'exposition au DD journalier). Fichiers : `the5ers_risk_maxpos_grid.py`,
`grid_5ers_only_summary.csv`, `grid_flotte_summary.csv`, 30 CSV
`grid_5ers_risk{X}_maxpos{Y}_{suffix}.csv`.

⚠️ **Bug rencontré et corrigé** : le premier run de cette grille a produit un
`grid_flotte_summary.csv` corrompu (cash pire cas artificiellement bas sur
TOUTES les lignes, pas seulement celles affectées par un problème de fichiers
obsolètes). Cause exacte non identifiée avec certitude (possible
désynchronisation stdout/lecture pendant l'exécution background). **Corrigé
en reconstruisant le résumé directement depuis les 30 CSV bruts vérifiés
(2000 lignes chacun)** — leçon retenue : après un run background, toujours
vérifier `wc -l` sur les fichiers avant de faire confiance au résumé écrit
par le script. **Ce même bug s'est reproduit à l'identique sur le premier run
de la grille section C (3 derniers combos restés à 10 lignes, résidus d'un
smoke test) — reconstruction manuelle nécessaire à chaque fois.**

---

## C. Correction du prix de rachat réaliste (le vrai sujet critique)

**Déclencheur** : l'offre Summer Plan (179$) se termine **fin août 2026**,
soit **26 jours** à partir du 2026-08-05 (date de cette session) — PAS 12-24
mois comme testé en section B. Prix normal 100K 2-Step **545$**, sourcé
directement via l'annonce officielle The5ers sur X/Twitter
(@the5erstrading, 16 janvier 2025 : *"Starting January 16, 2025, the prices
for our 100K and 60K High Stakes accounts will be updated to $545 and $329,
respectively"*), recoupé par propfirmmatch.com (545$ normal / 490,50$ avec
code -10%, cohérent : 545×0,9=490,5). **Remplace définitivement le 495$
utilisé en section B (moins bien sourcé, données déc. 2024, avant la hausse
de janvier 2025) et le cutoff 12-24 mois (trop optimiste).**

**Moteur unifié créé** : `the5ers_pricing_engine.py` — `run_5ers_fleet`
paramétrable avec bascule de prix : 179$ tant que `now < cutoff_seconds`
(défaut 26 jours), puis `post_summer_cost` (545$) ensuite. Les 4 comptes
INITIAUX restent toujours à 179$ (seuls les RACHATS après casse basculent).

### Point 2 corrigé — The5%ers isolé année 1, prix réaliste (26j→545$)

Script `the5ers_year1_realistic_pricing.py`, sensibilité testée à 21/26/35
jours (quasi aucun effet du choix précis dans cette fourchette — le run le
pire arrive dans les 21 premiers jours de toute façon).

| N | Winrate | Profit an1 | **Cash pire cas an1 (ANCIEN 179$ perpétuel)** | **Cash pire cas an1 (NOUVEAU, cutoff 26j)** | Casses an1 |
|---|---|---|---|---|---|
| 4 | 37,29% | 471 414$ | 10 024$ | **29 056$ (+190%)** | 25,9 |
| 4 | 32% | 251 988$ | 11 456$ | **33 416$ (+192%)** | 30,9 |
| 3 | 37,29% | 353 560$ | 7 518$ | **21 792$ (+190%)** | 19,5 |
| 3 | 32% | 188 991$ | 8 592$ | **25 062$ (+192%)** | 23,2 |

**Découverte clé** : `year1_cash` et `final_cash` sont **strictement
identiques** dans TOUS les runs (vérifié : moyenne, écart-type, max tous
égaux) — le risque de cash pire cas est réalisé ENTIÈREMENT dans la fenêtre
avant le premier financement, jamais après (`ever_funded` est un flag
GLOBAL partagé entre les 4 comptes, dès qu'UN compte finance, tous les futurs
rachats partout sont payés par la réserve). **Ce mécanisme se retrouve
identique dans TOUS les scénarios ultérieurs (grille, hybride) — c'est la clé
de compréhension de tout le reste de la session.**

Profit final quasi inchangé (~-2%) car le delta de prix (179→545, soit 366$)
est minuscule face à l'économie de trading d'un compte 100k. Fichiers :
`the5ers_N{3,4}_realpricing_cutoff{21,26,35}d_{suffix}.csv`,
`the5ers_isolated_year1_realistic_pricing.csv`.

### Point 4 corrigé — Grille risque×maxpos, prix réaliste

Script `the5ers_risk_maxpos_grid_realistic_pricing.py`. **Bug identique à la
section B rencontré et corrigé** (3 derniers combos = résidus smoke test 10
lignes) — reconstruit manuellement depuis les CSV bruts vérifiés (2000
lignes). Fichiers corrects : `gridrp_5ers_only_summary.csv`,
`gridrp_flotte_summary.csv`, 30 CSV `gridrp_5ers_risk{X}_maxpos{Y}_{suffix}.csv`
(risque 179 fixe = risque en %, ex `risk2_0`, `risk0_5`).

**Résultat définitif** (remplace section B pour toute référence future) :
profit final quasi inchangé (0 à -1%) mais **cash pire cas flotte +23% à
+99%** selon la config (plus le risque/casses sont élevés, plus l'effet est
marqué) :

| Config (flotte) | Profit final (ancien→nouveau) | Cash pire cas (ancien→nouveau) |
|---|---|---|
| risk=2%, maxpos=3 | 5 416 147$ → 5 375 041$ | 20 730$ → **41 226$ (+99%)** |
| risk=1%, maxpos=3 | 4 610 926$ → 4 605 918$ | 13 570$ → **19 426$ (+43%)** |
| risk=0,5%, maxpos=3 | 3 935 717$ → 3 934 674$ | 12 138$ → **15 066$ (+24%)** |

**Le levier de réduction du risque est donc encore plus important qu'estimé
en section B**, puisque le cash pire cas était sous-estimé partout avant
cette correction.

**Ces chiffres (`gridrp_*`, `the5ers_N{3,4}_realpricing_cutoff26d_*`) sont
la référence définitive pour tout usage futur du modèle 5ers seul — ne plus
utiliser les CSV `grid_*`/`scenario*` de la section B ni
`the5ers_100k_N{3,4}_*_dailydd.csv` (prix 179$ perpétuel, tous obsolètes
pour le cash pire cas, profit final toujours ~correct à 1-2% près).**

---

## D. Exploration stratégique (4 points)

### D1 — Écart Régime A (7,7M$) vs flotte 3-firms (5,37M$)

**Cause confirmée par lecture de code** (`three_firm_fleet_dailydd.py`,
`run_growth_segment`) : PAS une restriction de copytrade. `FIRM_CAP=400000`
pour FTMO et Blueberry. Les 2 comptes FTMO plafonnent à 200k chacun
(200k+200k=400k=plafond exact). Le compte Blueberry (SEUL) plafonne aussi à
200k car même sans partager avec un autre compte, sauter à 500k (500000 >
400000) dépasse déjà le plafond à lui seul — **le palier 500k est
structurellement inaccessible chez une firm dont le plafond combiné (400k)
est inférieur au palier lui-même**, indépendamment du nombre de comptes.
Régime A ne modélisait aucun plafond de ce type (hypothèse optimiste
obsolète).

**Test de l'hypothèse "comptes fixes multiples au lieu du scaling
plafonné"** : `growth_fixed_multi_account_test.py`, 16 comptes fixes 50k
(8+8 pour combler les 2×400k de plafond FTMO+Blueberry), jamais scalés,
casse+rachat au même palier (coût 333$, source `CHALLENGE_COST[50000]`
existant dans `scaling_simulation.py`), même ramp risque 0,5%→2%/12 trades,
daily 5%/trailing 10% (règles growth inchangées).

| | Profit final 37,29% | Cash pire cas | Casses |
|---|---|---|---|
| Growth actuel (3 comptes scaling plafonné) | 3 268 903$ | 9 990$ | 52,9 |
| **Growth fixe 16×50k (800k combiné)** | **4 489 777$ (+37,4%)** | 53 280$ | 290,1 |

Combiné à la flotte totale (5ers prix réaliste + ce growth restructuré) :

| | Profit final 37,29% | Cash pire cas | Casses |
|---|---|---|---|
| Baseline (5ers réaliste + growth actuel) | 5 332 216$ | 39 046$ | 164,3 |
| **Growth restructuré en 16×50k fixe** | **6 553 090$ (+22,9%)** | 82 336$ (+111%) | 401,6 (+144%) |

**Hypothèse utilisateur confirmée et chiffrée** : +18-23% de profit total,
mais cash pire cas et casses plus que doublent — vrai arbitrage, pas un gain
gratuit. Fichiers : `growth_fixed_multi_account_test.py`,
`growth_fixed_N16_{suffix}.csv`, `growth_fixed_multi_account_summary.csv`.

### D2 — Or/indices/exotiques dans les données Lutessia

Vérifié dans `historique_lutessia_15k.csv` (1773 signaux, 2022-2026, colonne
`asset_class` unique = "FX/Indices") et `scraper.py` (qui recherche
ACTIVEMENT XAU/USD, XAG/USD, BTC/USD, ETH/USD, FTSE100 en plus du reste,
lignes 82-98 de `scraper.py` : `TARGET_FOREX_TICKERS` inclut XAU/USD et
XAG/USD, `TARGET_INDEX_KEYWORDS` inclut FTSE100).

- **Or/argent/crypto/FTSE100 : ZÉRO signal en 4 ans de scraping** — pas un
  trou du scraper (il les cherche), Lutessia n'en publie simplement jamais.
- **Indices couverts** : DAX40, NASDAQ100, S&P500, MINI DJ30 (6 tickers).
  Après filtre standard (rr_tp1≥1,5, statut terminal) : **n=82 trades**,
  winrate **37,8%** (vs 37,3% forex), RR moyen gagnants 2,08 (vs 2,06 forex)
  — remarquablement proche mais **échantillon petit** : IC95% approximatif
  ±10,5 pts (plage réaliste 27-48%).
- **Taille nécessaire pour fiabilité comparable au forex** (marge ±5 pts) :
  ~360 trades exploitables, soit 4,4x le volume actuel. Au rythme actuel
  (~20/an), **~14 ans pour y arriver sur ces 6 tickers seuls** —
  impraticable sans élargir la couverture d'indices suivie. **Verdict :
  piste prometteuse mais NON tranchable aujourd'hui.**
- Détail par ticker (n / winrate%) : DAX40 FULL0926 21/33,3 ; DAX40 PERF
  INDEX 17/41,2 ; NASDAQ100-MINI 18/33,3 ; NASDAQ100 INDEX 13/46,2 ;
  S&P500-MINI 13/38,5. MINI DJ30 FULL0625 : 0 trade dans le sous-échantillon
  filtré (probablement pas encore résolu, contrat récent).

Aucun script créé pour ce point (analyse ad hoc en une-shot Python, pas
sauvegardée en fichier réutilisable — à refaire si besoin, requête simple :
filtrer `historique_lutessia_15k.csv` sur `~ticker.match(r'^[A-Z]{3}/[A-Z]{3}$')`).

### D3/D4 — voir sections E et F (FXIFY, Ment Funding, trésorerie dormante)

**Trésorerie dormante (D4)** : dans le statu quo (flotte 3 firms, prix 179$
perpétuel — chiffre pas encore recorrigé avec le prix réaliste), le rythme
"mature" (années 2-4) est **1 425 722$/an à 37,29%** et **863 596$/an à 32%**
— supérieur au rythme année 1 (respectivement 1 151 418$/an et 658 276$/an).
Ce profit n'est structurellement JAMAIS redéployé dans le modèle (N comptes
fixé au départ, jamais augmenté) — options identifiées : (1) restructuration
comptes fixes (D1, +22,9%), (2) nouvelles firms (FXIFY/Ment Funding, voir E),
(3) accélérer le rachat au-delà des casses — jugé non pertinent car les
comptes existants sont déjà rachetés immédiatement à chaque casse dans le
modèle actuel.

---

## E. FXIFY et Ment Funding — première passe

### FXIFY — retenu et chiffré

Programme "2-Phase 2-Step" (Two Phase Standard) : **daily loss 4%, max
drawdown 10% trailing** (confirmé sur plusieurs sources indépendantes après
plusieurs tentatives infructueuses sur le site officiel, JS-heavy/bloqué en
fetch direct). Copytrading entre comptes propres confirmé OFFICIELLEMENT
(tweet @fxifycom, 2024). Détention week-end autorisée (sauf programme
"Instant Funding", non utilisé ici). MT5 confirmé.

**Grille de prix complète, sourcée sur plusieurs pages produit
propfirmmatch.com/thetrustedprop.com** (programme 2-Phase 2-Steps) :

| Palier | 5k | 10k | 15k | 25k | 50k | 100k | 200k | 400k |
|---|---|---|---|---|---|---|---|---|
| Prix | 59$ | 75$ | 99$ | 175$ | 379$ | 475$ | 999$ | 2 950$ |

**Plafond de capital combiné : 805 000$ CONFIRMÉ à la source officielle**
(page FAQ FXIFY "what-the-max-allocation", citation exacte : *"Traders who
wish to trade multiple accounts at one time are able to purchase one active
account of each size: 1 x $5,000, 1 x $10,000, 1 x $15,000, 1 x $25,000, 1 x
$50,000, 1 x $100,000, 1 x $200,000, and $400,000"*) — **UN SEUL compte de
CHAQUE taille distincte, PAS plusieurs comptes de même taille** (différent du
modèle 5ers/FTMO/Blueberry où le plafond est "peu importe comment on
l'atteint"). Le "795 000$" évoqué initialement dans une passe de recherche
antérieure était une ERREUR D'ADDITION d'un résumé automatique — la somme
réelle des 8 paliers officiels est bien 805 000$, confirmée deux fois à la
source. **Aucun écart à résoudre, le chiffre 805 000$ est définitif.**

**Simulation** (`fxify_fleet_test.py`) : 8 comptes de tailles distinctes
figées (jamais scalées, casse→rachat au même palier), daily 4%/trailing 10%,
ramp 0,5%→2%/12 trades, maxpos=3 (règle projet standard).

| Winrate | Profit final FXIFY seul | Cash pire cas | Casses |
|---|---|---|---|
| 37,29% | 4 207 188$ | 59 929$ | 179,2 |
| 32% | 2 485 945$ | 65 890$ | 217,5 |

Combiné à la flotte (5ers réaliste + growth actuel + FXIFY, en LANCEMENT
IMMÉDIAT, PAS via bascule — voir section F pour la version bascule qui
domine cette approche) :

| | Profit final 37,29% | Cash pire cas | Casses |
|---|---|---|---|
| Baseline | 5 332 216$ | 39 046$ | 164,3 |
| **+FXIFY** | **9 539 404$ (+78,9%)** | 98 975$ (+153,5%) | 343,6 |

Fichiers : `fxify_fleet_test.py`, `fxify_fleet_{suffix}.csv`,
`fxify_fleet_summary.csv`.

### Ment Funding — première passe, incertitudes identifiées

- Homepage indique "Multi-accounts, permanent ban" — **clarifié** : concerne
  le gaming de leaderboard/compétitions avec identités dupliquées, PAS les
  comptes multiples légitimes (EA/copy trading entre comptes propres
  explicitement autorisés selon plusieurs sources).
- Weekend : fermeture forcée 15h45 EST vendredi, **soft breach seulement**
  (pas de résiliation), **add-on +10% ponctuel** (pas récurrent) pour tenir
  le week-end — confirmé viable, pas bloquant.
- DD 6% (type conflictuel selon les sources — voir section F pour la
  clarification partielle).

---

## F. Suivi final — hybride, sourcing Ment Funding précis, combiné

### F1 — Bascule hybride par seuil de réserve (RÉSULTAT LE PLUS IMPORTANT DE
LA SESSION)

Script `hybrid_reserve_switch_test.py` : flotte démarre en structure actuelle
(5ers réaliste 4 comptes + growth scaling plafonné 3 comptes, réserve
COMMUNE partagée dès le départ entre les deux segments — changement de design
par rapport à avant où chaque segment avait sa réserve propre), PUIS bascule
vers structure étendue (growth restructuré 16×50k fixe + FXIFY 8 comptes,
805k$ combiné) dès que la réserve commune franchit un seuil. Au moment de la
bascule, les 3 anciens comptes growth sont GELÉS (plus de nouveaux trades,
mais gardent leur profit déjà acquis) et les 24 nouveaux comptes sont ouverts
d'un coup, payés depuis la réserve accumulée.

| Seuil | Profit final 37,29% | Cash pire cas | Casses | Bascule médiane |
|---|---|---|---|---|
| 20 000$ | 10 307 322$ | **39 046$** | 554,4 | 71j |
| 50 000$ | 10 232 553$ | **39 046$** | 550,1 | 85j |
| 100 000$ | 10 144 554$ | **39 046$** | 544,7 | 95j |
| *(32% : 20k/50k/100k)* | 5 904 838$/5 850 467$/5 765 460$ | **43 406$** (les 3) | 676/671/661 | 91j/98j/126j |

**Découverte majeure** : le cash pire cas est **strictement identique** au
baseline actuel SANS AUCUNE expansion (39 046$/43 406$, exactement les mêmes
valeurs que la section D1 "Baseline"), quel que soit le seuil choisi entre
20k et 100k. Explication (cohérente avec la découverte du point B/C sur
`ever_funded` global) : le pire cas de cash est entièrement déterminé par la
fenêtre AVANT le premier financement, qui est strictement identique dans les
3 scénarios (même structure de départ) ; une fois n'importe quel seuil
atteint (toujours après financement, bascule médiane 71-127 jours, **0% de
runs "jamais basculés"**), l'expansion est payée depuis la réserve, jamais
depuis la poche personnelle. **Le choix du seuil est quasi indifférent**
(écart de profit <2% entre 20k et 100k) — recommandation : **50 000$** comme
marge de sécurité pragmatique, coût quasi nul. Ce résultat DÉPASSE même le
lancement immédiat de FXIFY (10,1-10,3M$ vs 9,5M$) grâce à la réserve
commune unifiée, plus efficace que deux réserves séparées.

Fichiers : `hybrid_reserve_switch_test.py`,
`hybrid_switch_{20000,50000,100000}_{suffix}.csv` (2000 lignes chacun, avec
colonne `switch_time_days` par run), `hybrid_reserve_switch_summary.csv`.

**⚠️ POINT OUVERT NON TRAITÉ** : ce moteur hybride n'intègre PAS encore Ment
Funding (voir F3 ci-dessous — le scénario combiné FXIFY+Ment testé en
lancement immédiat fait exploser le cash pire cas à 320-462k$ à cause de
Ment Funding spécifiquement ; intégrer Ment Funding dans CE mécanisme de
bascule par réserve éliminerait très probablement l'essentiel de ce risque,
comme cela a fonctionné pour FXIFY seul — **calcul demandé par l'utilisateur
mais pas encore fait**).

### F2 — Ment Funding, sourcing précis (officiel + agrégateurs de qualité)

- **Grille de prix complète** (1-step evaluation, source
  thepropfirmguide.com, cohérente sur toute la table) :

| Palier | 25k | 50k | 100k | 200k | 400k | 1M | 2M |
|---|---|---|---|---|---|---|---|
| Prix | 250$ | 450$ | 750$ | 1 500$ | 3 000$ | 8 600$ | **17 200$** |

  (Pas de palier 5M confirmé dans cette table malgré mention ailleurs.)

- **Le palier 2M$ NÉCESSITE une évaluation** (1-step, cible 10% de profit,
  "no verification step" au-delà — confirmé, PAS d'accès instantané sans
  évaluation contrairement à l'espoir initial).
- **Plafond de capital combiné : TOUJOURS NON TROUVÉ explicitement** malgré
  recherche approfondie sur le site officiel et plusieurs agrégateurs
  (`mentfunding.com/mentfunding-fx/`, `/commissions-and-products/`,
  agrégateurs tiers) — seule règle identifiée reste anti-abus de
  "leaderboard gaming", pas une limite de capital total. **Reste une zone
  d'incertitude non résolue** — recommandation faite à l'utilisateur :
  contacter le support Ment Funding directement (comme il l'a fait pour le
  plafond 500k$ confirmé de The5%ers).
- **Add-on week-end +10% ponctuel** confirmé comme option de checkout
  générale sur les évaluations forex (pas limité à un palier spécifique).
- **Conflit non résolu sur le type de max drawdown** : la homepage
  mentfunding.com (via un fetch) dit "6% Static", deux autres sources
  (thepropfirmguide.com, un extrait de recherche tradingfinder) disent "6%
  trailing". **Tranché par défaut vers TRAILING dans la simulation** (2
  sources contre 1, et cohérent avec le modèle BREAK_DD_PCT existant), mais
  **non confirmé avec certitude — à vérifier avant tout engagement réel.**
- **Daily loss** : 5% pour les paliers standards, mais **2,5% spécifiquement
  pour le palier 2M$** selon une source distincte (règle plus stricte au
  palier le plus haut) — utilisé dans la simulation par prudence.

### F3 — Simulation Ment Funding (borne basse, 1 seul compte 2M$)

**Hypothèse volontairement conservatrice** : faute de plafond combiné
confirmé, modélisé comme UN SEUL compte 2M$ (le produit le plus haut vendu
sans ambiguïté) plutôt que de supposer un multiple non confirmé — **c'est une
borne BASSE**, le potentiel réel pourrait être largement supérieur si
plusieurs comptes de ce type sont confirmés autorisés.

Script `growth_fixed_fleet_test.py` (nom trompeur, historique de dev — c'est
en réalité le test Ment Funding 1×2M, pas un test "growth fixed" générique).
Règles : palier 2 000 000$, coût 17 200$/reset, daily 2,5%, max DD 6%
trailing, ramp 0,5%→2%/12 trades, maxpos=3.

| Winrate | Profit final | Cash pire cas | Casses |
|---|---|---|---|
| 37,29% | 3 973 453$ | **223 600$** | 16,4 |
| 32% | 1 761 541$ | **412 800$** | 21,3 |

**Cash pire cas énorme** (ordre de grandeur au-dessus de tout ce qui a été
testé jusqu'ici) — mécanisme : un seul gros compte, coût de rachat élevé
(17 200$) à payer potentiellement plusieurs fois avant le premier
financement, sans dilution sur plusieurs petits comptes. Fichiers :
`growth_fixed_fleet_test.py`, `ment_fleet_{suffix}.csv`,
`ment_fleet_summary.csv`.

### F4 — Scénario combiné FXIFY + Ment Funding (lancement immédiat, PAS via
bascule hybride)

| | Profit final 37,29% | Cash pire cas |
|---|---|---|
| Baseline | 5 332 216$ | 39 046$ |
| +FXIFY seul | 9 539 404$ | 98 975$ |
| **+FXIFY +Ment (1×2M, borne basse)** | **13 512 857$** | **319 703$** |

À 32% : baseline 3 166 253$/43 406$ ; +FXIFY 5 652 199$/109 296$ ; +les deux
7 413 740$/**461 882$**.

**Le profit explose mais le cash pire cas aussi** — entièrement porté par
Ment Funding (223-413k$ à lui seul, cf. F3). **Incohérent avec la logique du
point F1** : le bon réflexe serait d'intégrer Ment Funding dans le mécanisme
de bascule par seuil de réserve plutôt que de le lancer en "big bang" dès le
départ — **calcul explicitement identifié comme prochaine étape mais PAS
ENCORE FAIT**.

---

## G. Points ouverts / non résolus — à reprendre en priorité

1. **Intégrer Ment Funding au moteur hybride** (`hybrid_reserve_switch_test.py`)
   au lieu du lancement immédiat testé en F4 — devrait éliminer l'essentiel
   du cash pire cas de 320-462k$ tout en gardant le gain de profit énorme
   (13,5M$ à 37,29%). C'est la suite logique la plus évidente de la session.
2. **Plafond de capital combiné Ment Funding non confirmé** — à vérifier
   directement auprès du support (comme fait pour The5%ers). Bloque toute
   estimation au-delà de la borne basse "1 compte 2M$".
3. **Type de max drawdown Ment Funding (statique vs trailing) non tranché
   avec certitude** — 2 sources contre 1 en faveur de trailing, utilisé par
   défaut, mais à confirmer.
4. **Couverture indices Lutessia (n=82) trop faible pour trancher** — besoin
   de ~360 trades (4,4x le volume actuel) pour une fiabilité comparable au
   forex ; au rythme actuel (~20/an), ~14 ans sur les 6 tickers actuels.
   Piste or/crypto définitivement écartée (zéro signal en 4 ans malgré
   recherche active du scraper).
5. **D4 (trésorerie dormante) calculé sur l'ancien prix 179$ perpétuel**,
   jamais recalculé avec le prix réaliste (section C) ni avec les structures
   étendues (D1/E/F) — les vrais rythmes de trésorerie mature sont
   probablement très différents une fois FXIFY/growth-fixe intégrés.
6. **Pas de décision finale prise** sur : (a) quelle option de la frontière
   profit/casses (statu quo / maxpos=1 / risque 1% / risque 0,5%) adopter
   pour The5%ers seul ; (b) seuil de réserve précis pour la bascule hybride
   (50k$ recommandé mais pas figé) ; (c) si Ment Funding est retenu malgré
   l'incertitude sur son plafond ; (d) structure finale de la flotte
   (garder FTMO/Blueberry scaling classique, ou tout basculer vers
   comptes fixes + FXIFY + éventuellement Ment Funding).

## H. Notes techniques pour reprise du travail

- **Convention de nommage des CSV par run** : `{scenario}_{winrate_suffix}.csv`
  où `winrate_suffix` ∈ {`37_29pct`, `32pct`}. Toujours 2000 lignes (+ header)
  pour un run complet — **vérifier `wc -l` avant de faire confiance à un
  résumé**, deux bugs de résumé corrompu rencontrés cette session (section B
  et C), tous deux dus à des résidus de smoke test (10-20 lignes) non
  écrasés par le vrai run background au moment de la lecture.
- **Recombinaison exacte entre segments** : possible UNIQUEMENT si les deux
  scripts utilisent `rng = random.Random(42)` et appellent
  `build_full_block_bootstrap_sequence` exactement une fois par itération,
  dans le même ordre — alors les lignes d'index i dans deux CSV différents
  correspondent au même tirage de trades et peuvent être additionnées
  directement (profit, cash, casses). Vérifié empiriquement plusieurs fois
  (ex. casses 5ers implicites = 111,438 recoupe exactement la référence
  connue 111,4).
- **`ever_funded` est un flag GLOBAL partagé** dans tous les moteurs de ce
  projet (pas par compte) : dès qu'UN SEUL compte d'un segment/de la flotte
  finance, tous les rachats futurs partout dans ce segment sont payés par la
  réserve, plus jamais par la poche. C'est le mécanisme clé qui explique (a)
  pourquoi `year1_cash == final_cash` systématiquement, (b) pourquoi le
  cash pire cas ne dépend quasi pas du seuil de bascule hybride.
  **Dans le moteur hybride (F1), ce flag a été rendu commun à TOUTE la
  flotte (5ers+growth ensemble), pas juste par segment — changement de
  design par rapport aux scripts précédents.**
- **Scripts obsolètes de cette session, ne plus utiliser pour de nouveaux
  chiffres** : tout CSV `scenario1..6*` (section A, prix 179$ perpétuel),
  `grid_5ers_*`/`grid_flotte_summary.csv` (section B, idem) — préférer
  systématiquement les équivalents `gridrp_*` et `the5ers_N{3,4}_realpricing_*`
  (section C, prix réaliste 545$/cutoff 26j) pour toute référence au modèle
  5ers seul désormais.
