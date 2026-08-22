# Registre de la stratégie de trading (edge) — Lutessia

*Document vivant, pendant de `registre_parametres_projet.md` mais sur un
axe DIFFÉRENT : ce fichier couvre l'EDGE lui-même (filtres d'entrée,
logique de sortie, validité statistique du signal) — PAS l'architecture
de capital/flotte (comptes, caps de firms, risque % par trade réparti
sur la flotte, mécanique de payout), qui reste intégralement dans
`registre_parametres_projet.md`, déjà à jour et complet sur cet axe.

**Pourquoi ce fichier existe** : les documents "recherche_robustesse_edge
_lutessia", "pistes_amelioration_rendement" et "strategie_trading_recap"
(accessibles côté projet mais absents de ce repo) sont PÉRIMÉS — ils ne
reflètent ni le test Force score (fait et rejeté), ni la taille
d'échantillon actuelle (721 trades, pas 67). Créé le 2026-08-11 en
auditant directement le code/CSV/logs du repo (aucune trace mémoire
n'existait pour Force/news/session avant ce fichier).

**Comment mettre à jour** : comme `registre_parametres_projet.md`, ce
fichier-ci EST la table vivante — mettre à jour après toute session qui
teste un nouveau filtre/levier sur l'edge, pas créer un nouveau fichier
séparé. Toujours dater et citer les scripts source.

---

## 1. Échantillon actuel

**Source canonique la plus récente** : `historique_lutessia_15k_force.csv`
(scrape du 2026-08-01), 1 965 signaux bruts, plage 2022-01-27 → 2026-07-30.

**Population filtrée standard du projet** (rr_tp1≥1,25, forex uniquement,
statut terminal `OBJECTIF ATTEINT`/`INVALIDÉE`, convention utilisée
partout dans le moteur de simulation) : **721 trades** — confirme et
dépasse le "400+" déjà avancé par l'utilisateur.

| | n | Winrate | Marge d'erreur (IC95%, approx. normale) | IC95% Wilson |
|---|---|---|---|---|
| **Population actuelle (721 trades)** | 721 | 40,36% | **±3,58pt** | [36,84%, 43,98%] |
| Ancienne pop. encore utilisée par les sims flotte (646 trades) | 646 | 40,09% | ±3,78pt | — |
| Pour mémoire, à l'ancien échantillon périmé (~67 trades) | 67 | ~40% (supposé) | **±11,7pt** | — |

**⚠️ Point de vigilance découvert pendant cet audit** : les scripts de
simulation flotte utilisés tout au long du chantier capital (`trailing_
payoff_population.build_population_with_trailing` → `rr_threshold_test.
build_extended_population`) pointent encore vers l'ANCIEN fichier
`historique_lutessia_15k.csv` (646 trades filtrés, arrêté au 2026-07-27)
— PAS le fichier `_force` plus récent (721 trades, jusqu'au 2026-07-30,
disponible depuis le 2026-08-01). Écart ~75 trades / ~4 jours de
données plus récentes non exploitées. **Non corrigé ici** (changerait
potentiellement tous les chiffres de référence capital sans que ça ait
été demandé) — signalé comme point ouvert §4.

**Verdict sur la marge d'erreur** : à 721 trades, l'incertitude sur le
winrate mesuré est de ±3,6pt — bien plus étroite qu'à l'ancien
échantillon de ~67 trades (±11,7pt, 3,3× plus large). La taille actuelle
permet des comparaisons de sous-groupes (segments Force, sessions) avec
une confiance raisonnable, mais tout sous-groupe de moins de ~100 trades
(ex. segments Force extrêmes, n=7) reste à traiter avec prudence.

---

## 2. Journal des tests sur l'edge

### 2.1 Force score (score de force du signal Lutessia) — REJETÉ, DEUX variantes testées

**Mécanisme (a) — filtre d'entrée** (`force_score_analysis.py`,
2026-08-01) : seuil additionnel `score_force >= X` par-dessus le filtre
rr_tp1≥1,5 déjà en place. Testé sur `population_with_force.csv` (472
trades, rr_tp1≥1,5).
- Corrélation Force↔victoire : r=+0,026, t=0,56 (n=472) — **non
  significatif** (seuil |t|>1,96).
- Corrélation Force↔R : r=+0,072, t=1,55 — **non significatif** à 5%.
- Segments (`force_score_segments.csv`) : NON monotones — Force 7-8
  (n=95) EV +0,97R ; Force 8-9 (n=363, 77% du volume) EV +0,76R (PIRE) ;
  Force <7 et >9 (n=7 chacun) trop petits pour être fiables.
- Seuil Force≥8,0 → EV +0,796R (n=370, PIRE que le baseline +0,822R) ;
  Force≥8,5 → EV +1,199R (n=154, le seul segment avec un vrai lift, mais
  repose sur une corrélation non significative).

**Mécanisme (b) — pondérateur de taille de position**
(`force_weighting_test.py`, "Partie 5", 2026-08-01) : Force<7→0,5×
risque, Force≥8,5→1,5×risque, sinon 1×. Testé en Monte Carlo flotte
complet (n=2000, régime hybride année 1).
- Baseline (risque fixe) : profit moyen +989 672€, P(perte) 17,40%.
- Force-pondéré : profit moyen +1 335 486€, P(perte) 11,80%.
- Delta apparent : **+345 814€ (+34,94%)**.

**Verdict officiel trouvé (`session_summary_2026-08-01.md`) : "Force non
exploitable".** Le gain apparent du pondérateur (b) repose presque
entièrement sur le segment Force≥8,5 (32,6% du volume pondéré ×1,5) —
le seul segment avec un fort lift EN ÉCHANTILLON, mais dont la
corrélation sous-jacente échoue le test de significativité (t=1,55) et
dont la table de segments n'est pas monotone (7-8 bat 8-9). Traité par
le projet comme du bruit/surapprentissage, pas un signal réel.

**Condition de réouverture** : ré-testerait avec un échantillon
nettement plus grand (le segment Force≥8,5 n'a que n=154, sous-groupe
d'un total déjà limité) — pas de piste concrète identifiée, faute de
plus de données Lutessia disponibles.

### 2.2 "Force-close" 24h/weekend (clôture forcée) — REJETÉ

⚠️ À NE PAS CONFONDRE avec le Force score ci-dessus (même mot "force" en
français, mécanismes totalement différents). `point3_force_close_24h_
weekend.py` (2026-08-06) : force la clôture du trade à entrée+24h (ou
plus tôt si un gap de weekend s'ouvre avant), au prix de la bougie H1 la
plus proche. Testé sur la population rr_tp1≥1,25/trailing-0,15×SL
(n=646).

**Résultat** (`point3_force_closed_population_detail.csv`) :
- Winrate : 40,09% (baseline) → 39,63% (forcé) — quasi inchangé.
- **EV : +0,971R (baseline) → +0,808R (forcé), soit -16,8%.**
- Somme R totale : 627,4 → 522,2 (-16,8%).

**Verdict : REJETÉ.** Forcer une sortie précoce coûte significativement
en EV — laisser les gagnants courir jusqu'à leur résolution réelle
(souvent >24h) capture nettement plus de R qu'une coupe dure à 24h/
weekend.

### 2.3 Filtre horaire de session (Asie/London/US/nuit) — REJETÉ, 3 variantes concordantes

**Signal descriptif** (`session_hour_analysis.py`, 2026-07-30) : EV(TP2)
par session UTC sur la population prise (472 trades) — Asie (00-08h,
n=121) +1,24R ; London (08-13h, n=88) +1,56R ; chevauchement (13-16h,
n=37) +1,31R ; **US (16-22h, n=132) +1,69R (meilleur)** ; nuit (22-24h,
n=38) +1,10R. Fuseau horaire confirmé UTC (JS `dayjs.utc` de
CentralCharts). Cet écart descriptif a motivé le test d'un filtre
d'exclusion de la session asiatique.

3 variantes testées (référence / exclusion stricte Asie / demi-risque
Asie), sur des configs flotte différentes :

| Variante | Config | Référence | Exclusion stricte | Demi-risque |
|---|---|---|---|---|
| `session_filter_test.py` | solo, 0,5%, payoff rr_tp1 | 79 729€ | 65 284€ | 70 899€ |
| `session_filter_copytrade_test.py` | copytrade 3 comptes, 2%/compte, **payoff rr_tp2 naïf** (connu périmé ~13×, cf. §2.7) | 17,82M€ | 13,76M€ | 15,78M€ |
| `session_filter_realistic_test.py` | idem, **payoff réaliste** (fiable) | 9,39M€ | 6,93M€ | 8,16M€ |

**Verdict : REJETÉ dans les 3 variantes**, y compris la variante
réaliste (fiable). Exclure ou dé-risquer la session asiatique réduit le
profit total malgré son EV/trade plus faible — la perte de volume/
diversification l'emporte sur le gain d'EV moyen.

### 2.4 Pyramiding (+0,5R/+1R sur trades gagnants) — REJETÉ *(déjà en mémoire, consolidé ici)*

`pyramid_engine.py`, testé en flotte copytrade 3 comptes (2%/compte,
rr_tp1≥1,5, payoff réaliste+trailing 0,2×SL). Baseline sans pyramiding
~10,34M€/41,4 casses. Cas de base +0,5R/+1R : ~4,16M€ (structure A) à
~3,77M€ (structure B) — TOUTES les variantes testées (espacements
0,75R/1,5R, paliers à 3 niveaux) sous-performent nettement, casses
2-2,2× la baseline. Winrate conditionnel réel (63,9% après +0,5R) ne
compense pas : les unités ajoutées captent structurellement moins de R
(entrent plus tard) et le risque agrégé plus élevé amplifie les casses
de flotte plus vite que l'EV ne compense. Robuste (delta négatif sur
les deux moitiés chronologiques + après retrait du trade le plus
contributeur). **Condition de réouverture** : nécessiterait un filtre de
sélection différent (momentum) pour choisir QUELS trades pyramider, pas
juste "atteint +0,5R".

### 2.5 Kelly fractionnel — REJETÉ (50%) / ARBITRAGE non tranché (25%) *(déjà en mémoire, consolidé ici)*

Testé flotte copytrade 3 comptes. **Correction comptable décisive**
appliquée : seul le P&L généré compte FINANCÉ (`total_funded_pnl`,
jamais celui généré pendant une tentative de challenge, jamais réel)
doit compter dans la comparaison — sans cette correction, Kelly semblait
nettement gagnant (trompeur).

| Config | Risque moyen/trade | Profit financé net | p5 | Casses flotte |
|---|---|---|---|---|
| Baseline fixe 2% | 2,0% | 7,77M€ | 6,29M€ | 41,4 |
| Kelly 25% | 5,37% | 8,36M€ (+7,6%) | 5,52M€ | 127,7 |
| Kelly 50% | 10,74% | 7,81M€ (+0,5%, non significatif) | 4,36M€ | 168,0 |

**Kelly 50% REJETÉ** (règle de décision utilisateur : si Kelly 50% ne bat
plus significativement la baseline une fois corrigé, on retient Kelly
25% ou la baseline). **Kelly 25% reste un ARBITRAGE non tranché** (+7,6%
profit mais p5 pire et 3× plus de casses) — pas un gain net évident, pas
re-testé sous le moteur multi-format actuel depuis cette correction.

### 2.6 Sizing ajusté ATR — quasi NEUTRE *(déjà en mémoire, consolidé ici)*

Testé en même temps que Kelly (§2.5). Risque réalisé quasi inchangé
(~2,01% vs 2% cible) — effet lui-même indépendant de la correction
comptable funded/challenge, mais **jamais recalculé** avec cette
correction appliquée (contrairement à Kelly). Verdict : neutre en l'état,
pas prioritaire à re-tester sans nouvelle piste.

### 2.7 Trailing stop après TP2 (0,2× SL) — ADOPTÉ *(déjà en mémoire, consolidé ici)*

Sur les 98 trades à continuation TP1→TP2 confirmée. **0,2× distance SL
initiale = meilleure config actuelle** : +9,7% à +11,1% profit flotte vs
sortie TP2 dure, casses quasi inchangées. Robuste (tient sur les deux
moitiés chronologiques, survit au retrait des 10 meilleurs trades,
pire cas individuel borné -0,20R vs -0,50R pour 0,5×SL). Historique :
0,5×SL était le premier "gagnant" (+3,5-4%) avant qu'un bug d'ancrage de
simulation soit trouvé et corrigé (l'ancrage utilisait le prix TP2
littéral au lieu de l'extremum réel de la bougie qui a touché TP2) —
0,2× a émergé comme le vrai optimum après correction. **Caveat non
résolu** : seulement 98 trades (55,7% de la pop. rr_tp1≥1,5), l'EV
s'améliore de façon monotone jusqu'à 0,05×SL dans le sweep corrigé mais
ce plancher n'a jamais été testé en robustesse (risque de spread/
slippage réel non modélisé à cette distance serrée).

### 2.8 Seuil R:R (rr_tp1) — ADOPTÉ, en usage actif (1,25)

`rr_threshold_test.py`, sweep {1,0/1,1/1,25/1,35/1,5/1,75/2,0/2,5} sur
population à durées réelles vérifiées (bougies H1). Résultats bruts
(`rr_threshold_summary.csv`, EV en R "pris") : 1,0→0,073R (n=715) ;
1,1→0,064R (n=630) ; **1,25→0,107R (n=545)** ; 1,35→0,122R (n=489) ;
1,5→0,115R (n=416) ; 1,75→0,093R (n=314) ; 2,0→0,169R (n=230) ;
2,5→0,123R (n=112, mais pct_loss=22,65%, nettement plus risqué). **1,25
est la valeur actuellement utilisée par TOUT le moteur de simulation**
(`min_rr=1.25` partout dans les scripts flotte) — cohérent avec un bon
compromis EV/volume dans ce sweep, sans être le seul point testé.
`rr_risk_combo_test.py` a aussi testé 1,5 combiné à des schémas de
risque% (progressif/fixe) — volet risque% hors périmètre de ce registre
(capital, cf. `registre_parametres_projet.md`).

### 2.8bis 🟡 *(CANDIDAT n=300, 08/12)* Affinage de la grille RR — 1,35 domine strictement 1,25 sur les 4 axes

Le sweep §2.8 était grossier {1,0/1,1/1,25/1,35/1,5/1,75/2,0/2,5}. Affiné
autour de l'optimum : {1,05/1,10/1,15/1,20/1,25 réf/1,30/1,35/1,40/1,45},
population 721, **payoff trailing 0,15×SL actuellement en production**
(pas le payoff TP1-plat de l'ancien `rr_threshold_test.py` — écart
méthodologique explicite, `chantier1_rr_grid_2026-08-12.py`).

**Étape 1 — solo** (EV des trades PRIS après plafond 3 positions +
corrélation 0,6/JPY, marche chronologique déterministe) :

| Seuil | n pris | Winrate pris | EV pris (R) |
|---|---|---|---|
| 1,05 | 762 | 41,5% | +0,7300 |
| 1,10 | 712 | 40,2% | +0,7007 |
| 1,15 | 675 | 39,9% | +0,7007 |
| 1,20 | 636 | 39,0% | +0,7133 |
| **1,25 (réf)** | **612** | **39,9%** | **+0,7938** |
| 1,30 | 571 | 39,6% | +0,7989 |
| **1,35** | **546** | **38,8%** | **+0,8080** |
| 1,40 | 513 | 38,0% | +0,7812 |
| 1,45 | 488 | 37,3% | +0,7487 |

EV_pris culmine à 1,35, top 3 candidats retenus pour confirmation flotte :
1,35/1,30/1,40.

**Étape 2 — flotte n=300, 2 plafonds** (moteur officiel Option A/Prime,
config Run C) :

| Plafond | Seuil | n trades | Profit moyen/médian | solde_negatif_annee4 | hit_ceiling_pct | Année1<0 |
|---|---|---|---|---|---|---|
| 1000$ | **1,25 (réf)** | 721 | **5 588 381$/5 336 808$** | 1,33% | 3,33% | 32,67% |
| 1000$ | 1,30 | 669 | 5 049 693$/4 913 330$ | 0,67% | 2,00% | 33,33% |
| 1000$ | **1,35** | 631 | **5 764 076$/5 632 206$** | **0,33%** | **1,67%** | **29,33%** |
| 1000$ | 1,40 | 591 | 5 655 586$/5 396 698$ | 0,67% | 3,00% | 31,00% |
| 3000$ | **1,25 (réf)** | 721 | **5 629 882$/5 361 131$** | 0,33% | 1,67% | 32,67% |
| 3000$ | 1,30 | 669 | 5 084 237$/4 926 585$ | 0,00% | 0,33% | 33,33% |
| 3000$ | **1,35** | 631 | **5 764 865$/5 632 206$** | **0,33%** | **1,00%** | **29,33%** |
| 3000$ | 1,40 | 591 | 5 701 782$/5 463 724$ | 0,00% | 1,00% | 31,00% |

**1,35 DOMINE STRICTEMENT 1,25 sur les 4 axes aux deux plafonds** :
profit +3,1%/+2,4%, solde_neg meilleur/égal, hit_ceiling meilleur, année1<0
-3,3pt aux deux plafonds — standard "GO" du projet (dominance 3+ axes aux
2 plafonds) atteint. 1,40 domine aussi 1,25 mais plus faiblement (+1,2%/
+1,3% profit). **1,30 est nettement PIRE que la référence sur le profit
(-9,6%/-9,7%)** malgré un solo EV_pris légèrement meilleur que 1,25 — rappel
que l'EV solo ne se traduit pas linéairement en profit flotte (interaction
avec le volume de trades/le bootstrap/le scaling). **Candidat prioritaire :
1,35.**

**✅ 08/12, plus tard : n=600+cascade CONFIRMÉ** en combinaison avec le
seuil de corrélation 0,80 (`registre_parametres_projet.md` §2.62,
`chantier1_combined_confirm_n600_2026-08-12.py`) — RR1,35 seul (corr 0,60
inchangé) confirmé n=600 : 1000$ 5 710 066$/0,50%/1,83%/33,17% ; 3000$
5 717 829$/0,33%/0,83%/33,17% (domine la référence 1,25 sur les 4 axes aux
deux plafonds). Combiné avec corr0,80 : dominance encore renforcée (profit
+6,3%/+5,5% vs référence, année1<0 -5,0pt/-4,8pt, effet super-additif sur
année1<0 spécifiquement).

**✅ ADOPTÉ 08/12 (cascade complète, `registre_parametres_projet.md`
§2.62-2.63)** — RR≥1,35 est désormais la référence officielle du projet
(avec corrélation 0,80). Toute la chaîne dépendante régénérée : référence
capital Run C/F, config 1/4 dual-trader, décomposition du mécanisme de
sauvetage (mécanisme confirmé intact), Blueberry Prime A/B/C (verdict
qualitatif inchangé). Un risque structurel a été trouvé et corrigé en
route : la bande contrarian de Stratégie B (0,75-1,25, `dual_trader_2026-
08-11.py`) était bornée par un littéral dupliqué indépendant de RR T1 —
aurait créé une zone morte de trades (rr_tp1∈[1,25;1,35)) ni pris par T1
ni par T2. Corrigée : la borne haute suit désormais `MIN_RR_T1=1.35`, une
constante partagée — voir §2.63 pour le détail. Nouvelle bande Stratégie B
(0,75-1,35) revérifiée solo avant réutilisation : n=401 (vs 311), EV
+0,8005R (vs +0,7809R) — pas de dilution.

### 2.9 Filtre news (calendrier ForexFactory) — BACKTEST PARTIEL 08/11, DONNÉES INSUFFISANTES POUR TRANCHER

**08/12 : réouverture demandée puis annulée par l'utilisateur en cours de
chantier** ("le filtre news a été testé, annule la section 4") — le verdict
ci-dessous (08/11) reste inchangé, pas de nouveau test effectué.

`news_filter.py` : mécanisme de PRODUCTION — sur un signal d'entrée, si
un événement High-impact ForexFactory (NFP/CPI/décisions banque
centrale) pour une devise de la paire tombe dans les ±2 minutes,
**retarde** l'exécution jusqu'à la fin de la fenêtre — n'annule jamais
le signal. Source prod : flux JSON `ff_calendar_thisweek.json`
("cette semaine" uniquement, PAS d'historique).

**08/11 : premier backtest tenté** (`edge_news_filter_test_2026-08-11.py`).
Source historique trouvée après recherche bornée (15-20min) : dataset
HuggingFace `Ehsanrs2/Forex_Factory_Calendar` (licence MIT, même source
ForexFactory, mêmes catégories d'impact) — **couverture 2007-01-01 →
2025-04-04 seulement**, la population de référence va jusqu'au
2026-07-30 (261/721 trades hors couverture, exclus explicitement, pas
supposés "sans news").

Sur les 460 trades couverts par le calendrier : seulement **4 trades**
tombent dans la fenêtre ±2min d'un événement High Impact sur une devise
de la paire (winrate 75%, EV +2,16R, mais IC95% [30%,95%] — n bien trop
petit pour conclure). **Constat clé : la fenêtre de 2 minutes est
intrinsèquement si étroite qu'elle ne peut statistiquement affecter
qu'une poignée de trades sur tout l'historique** — pas un problème de
données, un problème d'échelle du mécanisme lui-même.

**Point 3 (simulation du délai d'exécution) NON CALCULABLE** : le projet
n'a que des bougies H1 en cache (yfinance) — bien trop grossières pour
résoudre un mouvement de prix sur 2 minutes (le bruit intra-heure
domine). Nécessiterait des données M1/tick (seule la mesure ponctuelle
de slippage Dukascopy §2.11 en a, pas une archive complète).

**Verdict : NI adopté NI rejeté — sous-alimenté pour trancher, mais le
mécanisme lui-même est structurellement à faible enjeu** (trop peu de
trades concernés pour que son effet, quel qu'il soit, pèse sur l'EV
global). Pas prioritaire à re-creuser sauf données M1/tick disponibles.
Fichiers : `ff_calendar_historical_2007_2025.csv` (dataset brut),
`edge_news_filter_summary.csv`/`edge_news_filter_population_detail.csv`
(résultats).

### 2.10 Walk-forward / robustesse de l'edge — VALIDATION (pas un levier), edge confirmé réel

Pas un test de filtre — établit que l'edge lui-même est réel, pas du
surapprentissage. Sur la population actuelle (472 trades, payoff
`r_trailing`) :

**`walk_forward_ev_robustness.py`** (2026-08-01) : split 60/40 → train
EV +0,574R (n=283) vs test EV +1,407R (n=189). Retrait des 3 meilleurs
trades du test : EV reste +1,213R (77% de l'écart train/test survit) ;
retrait des 5 meilleurs : +1,110R (64% survit). Split 50/50 : même
schéma (train +0,399R vs test +1,415R, 77-85% de l'écart survit).
**Conclusion du script : "edge plus homogène"** — la surperformance du
test n'est pas due à quelques trades chanceux.

**`walk_forward_gap_investigation.py`** (2026-08-04), creuse le POURQUOI
du grand écart train/test :
- Composition (paires, RR, Force, timeframe) similaire train/test — pas
  un artefact de sélection.
- Tendance chronologique CROISSANTE confirmée sur fenêtres glissantes de
  50 trades : ~-0,2R à 0R en 2022, jusqu'à +1,3-2,6R en 2025-2026.
- **Test de permutation (10 000 tirages)** : écart observé +0,834R au
  99,85e percentile de la distribution nulle, **p=0,0027** — statistique-
  ment significatif, peu probable que ce soit juste le hasard du split.
- Volatilité de marché (ATR14/prix) plus FAIBLE en période test (ratio
  0,807× train) — écarte l'hypothèse "période test juste plus volatile".
- Biais de rescraping explicitement marqué "non vérifiable" par le
  script (le rescraping Force a enrichi les lignes existantes, pas ajouté
  de nouveaux trades — aucun marqueur de provenance par ligne).

**Robustesse au stress winrate/RR** (`robustness_5ers_risk_challenge.py`/
`robustness_part2_3_run.py`, 2026-08-06) : sweep du risque sur les bornes
IC95% du winrate (32,9%-41,7%) + stress RR -10%/-20% — **la stratégie
reste profitable et P(année1<0) reste borné sur toute la plage
stressée**, confirme que l'edge ne dépend pas de la précision exacte des
estimations ponctuelles. Re-testé avec slippage Dukascopy réel (§2.11) —
profit toujours positif à tous les niveaux de risque.

### 2.11 Slippage réaliste (Dukascopy) — ADOPTÉ *(déjà en mémoire, consolidé ici)*

yfinance/MT5 historique jugé insuffisant pour mesurer le slippage réel.
Mesuré via Dukascopy : slippage moyen -0,91 pip. **EV : +0,907R →
+0,850R** une fois le slippage réaliste appliqué — adopté comme
correction permanente du calcul d'EV.

### 2.12 "OBJECTIF ATTEINT" = TP1, pas TP2 — correction méthodologique *(déjà en mémoire, consolidé ici)*

Correction transversale au projet : utiliser `rr_tp2` comme payoff
garanti surestimait les résultats jusqu'à ~13× dans un test. Convention
retenue partout depuis : `r_realiste` = `rr_tp2` SI continuation TP1→TP2
confirmée (98 trades), sinon `rr_tp1`. Base de tous les calculs d'EV
cités dans ce registre.

### 2.13 Filtre ADX en entrée — FRAGILE, NON ADOPTÉ (08/11)

`edge_adx_atr_filters_2026-08-11.py` : ADX(14) Wilder (EWM alpha=1/14,
pas de lib externe) calculé sur bougies H1 au moment de l'entrée.
**Contrainte de couverture** : yfinance H1 ne couvre que ~729 jours
glissants → seulement 375/721 trades (52%) ont un ADX calculable
(fenêtre 2024-08-01→2026-07-30). Comparaison faite **contre un baseline
restreint au même sous-ensemble couvert** (pas la population totale) —
sinon confond l'effet du filtre avec le biais temporel déjà identifié
en §2.10 (edge structurellement meilleur en période récente).

| Seuil | n (exclus) | Winrate [IC95%] | EV | Δ EV vs baseline |
|---|---|---|---|---|
| Baseline couvert | 375 | 41,87% [37,0-46,9] | +1,631R | — |
| ADX≥20 | 240 (135) | 42,92% [36,8-49,2] | +1,752R | +7,4% |
| ADX≥25 | 151 (224) | 44,37% [36,7-52,3] | +1,711R | +4,9% |
| ADX≥30 | 90 (285) | 41,11% [31,5-51,4] | +1,591R | -2,5% |

**Sous-période (split chronologique 50/50 du sous-ensemble couvert)** :
ADX≥20 : période 1 +2,126R (vs baseline1 +1,930R, +0,196) → période 2
+1,378R (vs baseline2 +1,334R, +0,044) — lift qui **s'effondre** en
période récente. ADX≥25/30 : lift positif en période 1 mais **devient
négatif** en période 2 (ADX≥25 : +0,270 → -0,106 ; ADX≥30 : +0,115 →
-0,197). **Verdict : REJETÉ tel quel** — ne survit pas au test de
sous-période (règle du projet : un filtre qui gagne en échantillon
complet mais s'inverse en sous-période est fragile, pas adopté).

### 2.14 Filtre ATR en entrée (régime de volatilité) — NEUTRE, NON ADOPTÉ (08/11)

Même script, même contrainte de couverture (52%). Ratio ATR(14)/médiane
historique du ticker (convention déjà utilisée par `sizing_stats.py`
pour le sizing ATR §2.6, réutilisée ici comme filtre d'entrée).

| Config | n (exclus) | EV | Δ EV vs baseline |
|---|---|---|---|
| ATR∈[0,5;2,0] (exclut extrêmes) | 359 (16) | +1,598R | -2,0% |
| ATR∈[0,7;1,5] (régime modéré) | 295 (80) | +1,533R | -6,0% |
| ATR≥0,7 (exclut faible vol) | 341 (34) | +1,605R | -1,6% |
| ATR≤1,5 (exclut forte vol) | 329 (46) | +1,571R | -3,7% |

**Verdict : NEUTRE À LÉGÈREMENT NÉGATIF, REJETÉ** — aucune config
n'améliore l'EV, toutes légèrement pires que le baseline couvert, et le
sens ne tient pas non plus entre sous-périodes (pas de signal
directionnel cohérent). Distinct du sizing ATR déjà testé (§2.6, quasi
neutre) — ici testé comme filtre d'entrée, conclusion similaire (aucun
edge).

### 2.15 Combinaison ADX+ATR — lift modeste mais mieux réparti (08/11, PARTIEL)

`ADX≥20 + ATR∈[0,5;2,0]` (n=228, exclus=147) : EV +1,730R (+6,0% vs
baseline +1,631R) — proche du gain d'ADX seul, l'ATR n'ajoute ni
n'enlève grand-chose en combinaison. **Fait notable** : contrairement à
ADX seul (lift qui s'effondre en sous-période 2), la combinaison reste
positive dans les DEUX moitiés chronologiques (période 1 : +1,956R vs
baseline1 +1,930R, +0,026 ; période 2 : +1,504R vs baseline2 +1,334R,
+0,170) — plus robuste qu'ADX seul, mais n=114/moitié reste petit (IC
large, pas testé formellement). **Verdict initial : PAS ADOPTÉ, à confirmer**
— seul filtre des tests 08/11 dont le signe ne s'inverse pas en
sous-période, mais l'échantillon par moitié est trop petit pour un
verdict définitif. Combinaisons avec le Test 1 (news) impossibles pour
l'instant (n=4 trades "près news", §2.9) — **Test 4 seulement
partiellement fait** (2+3, pas 1+2/1+3/1+2+3).

**🆕 IC bootstrap calculé (08/11, suite)** : rééchantillonnage avec
remise (5000 itérations, baseline n=375 vs combo n=228) sur le delta EV
observé (+0,0985R) : **IC95% = [-0,4867R, +0,6591R]** — inclut
largement zéro. **P(delta>0) sur les tirages = 61,8%**, à peine
au-dessus du hasard. **Verdict précisé : le lift n'est PAS
statistiquement significatif à cette taille d'échantillon** — l'IC
quantifie explicitement l'incertitude plutôt que de la laisser
qualitative. Toujours PAS REJETÉ (P(delta>0)=61,8% reste orienté dans
le bon sens) mais loin d'être confirmé.

**Source H1 alternative identifiée mais PAS exploitée** : Dukascopy
(`dukascopy_ticks.py`, déjà intégré au projet pour la mesure de
slippage §2.11) fournit des ticks historiques par heure explicite, SANS
la limite ~729j de yfinance (cache existant remonte déjà à 2022-09).
Mais le cache actuel est **sparse** (37 fichiers pour AUDJPY, des
heures ponctuelles autour de trades spécifiques, pas une série
continue) — construire des bougies H1 continues sur 4,5 ans × 14
tickers pour recalculer ADX/ATR nécessiterait des centaines/milliers de
requêtes horaires supplémentaires, un chantier distinct et non
négligeable, pas fait dans cette session faute d'un go explicite.

### 2.16 Coupe-circuit réactif — RÉOUVERT sur preuve concrète, REJETÉ À NOUVEAU avec évidence renforcée (08/11)

**Rejet précédent** (`registre_parametres_projet.md` §2.7, 08/09-08/10) :
24 configs (seuils sur le R moyen glissant), verdict "signal de mauvaise
passe récente = bruit statistique pur, pas un vrai signal de dégradation
de l'edge". **Condition de réouverture explicite posée à l'époque** :
"seulement si un signal MOINS bruité est proposé" — pas un simple
resweep de seuils.

**Élément déclencheur de la réouverture** : `registre_parametres_projet
.md` §2.37 a identifié une VRAIE fenêtre historique creuse (2022-11-01→
2023-01-20), vérifiée directement sur les 721 trades réels (winrate
17,5%/EV -0,466R vs 40,4%/+0,890R global) — pas une supposition, une
preuve concrète. Conforme au principe de fraîcheur du projet : rouvrir
sur preuve nouvelle, pas sur intuition.

**Point 1 — détectabilité de la dégradation** (`edge_circuit_breaker_v2
_2026-08-11.py`, seuil = moyenne historique − 2σ théorique du winrate/EV
glissant) :

| N | Seuil winrate (2σ) | 1ère détection dans la fenêtre |
|---|---|---|
| 10 | 9,3% | trade #36/40 (quasi la fin — N=10 trop insensible au seuil 2σ) |
| 15 | 15,0% | trade #7/40 (~18% dans la fenêtre) |
| 20 | 18,4% | trade #9-11/40 (~25% dans la fenêtre) |

N=15/20 détectent relativement tôt (moins d'un tiers de la fenêtre
écoulé) ; N=10 est trop bruité à 2σ pour détecter avant que l'essentiel
des dégâts soit fait.

**Point 2 — coupe-circuit calibré sur run202 (le run catastrophique
"5 firms" identifié en §2.37)** : pause fleet-wide (tous comptes, même
convention que §2.7) si winrate glissant sur N trades < X, reprise après
M trades (délai fixe). Grille N∈{15,20}, X∈{15-25%}, M∈{10,20} testée
sur le tirage EXACT de run202 (rejeu RNG reproduit à l'identique).

**Résultat spectaculaire mais à lire avec précaution** : les 8
configurations testées transforment TOUTES le run202 de -72 010$ à
**entre +1 121 316$ et +3 543 195$**. ⚠️ Mais le nombre de casses
AUGMENTE dans tous les cas (112-132 vs 92 baseline, "casses évitées"
négatif) — ce n'est PAS que le coupe-circuit empêche des casses
individuelles, c'est qu'il évite le **blocage définitif de la flotte**
(hit_ceiling → comptes gelés pour le reste des 4 ans, mécanisme identifié
en §2.37) : la flotte redémarre normalement et continue à trader
activement (donc accumule PLUS de casses au total sur 4 ans qu'une
flotte figée qui arrête d'en produire). Le vrai signal de succès est le
profit final, pas le compte de casses. Sur les épisodes de pause : 2-6
vrais positifs (chevauchant la vraie fenêtre creuse) contre 4-8 faux
positifs (déclenchés hors fenêtre, sur du bruit) selon la config —
**les faux positifs dominent déjà numériquement sur ce seul run**.

**Point 3 — retest sur l'ensemble n=300, deux plafonds** (pas seulement
la fenêtre creuse) — 2 configs retenues (N=20/X=18%/M=10, la meilleure
sur run202 ; N=15/X=15%/M=10, plus agressive) :

| Config | Profit moyen (1000$/3000$) | solde_negatif_annee4 | Année1<0 |
|---|---|---|---|
| Run C (référence, sans coupe-circuit) | 5 588 381$ / 5 629 882$ | 1,33% / 0,33% | 32,67% / 32,67% |
| N=20/X=18%/M=10 | 5 268 855$ / 5 318 877$ (**-5,7%/-5,5%**) | 1,33% / 0,00% | **32,67% / 32,67% (identique)** |
| N=15/X=15%/M=10 | 4 990 003$ / 5 123 519$ (**-10,7%/-9,0%**) | 3,00% / 0,33% (pire) | 35,33% / 34,67% (**pire**) |

**Confirme exactement le mécanisme d'échec déjà identifié en §2.7** : à
l'échelle de 300 runs, les faux positifs (qui dominent numériquement,
point 2) coûtent 5,5-10,7% de profit systématiquement, sans AUCUNE
amélioration mesurable de solde_negatif_annee4/année1<0 pour la
meilleure config (identique à la référence), et une dégradation nette
pour la config plus agressive. Le gain spectaculaire sur run202 est réel
mais concerne un run sur ~300 (voire ~1200, cf. §2.36/§2.37) — noyé dans
le coût systématique payé sur tous les autres.

**Verdict (point 4) : REJET RECONFIRMÉ, avec une preuve nettement plus
solide que la première fois.** La réouverture était légitime (preuve
concrète, pas supposition) et le coupe-circuit calibré sur cette preuve
fonctionne remarquablement bien sur le cas précis qui l'a motivé — mais
ce succès ne se généralise pas : impossible de cibler UNIQUEMENT les
vraies périodes creuses sans payer un coût systématique sur toutes les
fausses alertes, qui restent majoritaires. Le mécanisme d'échec de 08/09
("bruit statistique domine un pool à edge positif haute variance") tient
toujours, même avec un signal beaucoup moins bruité qu'un simple R
moyen glissant arbitraire. **Nouvelle condition de réouverture** :
nécessiterait un signal capable de distinguer une vraie dégradation
structurelle d'une simple série perdante AVANT qu'elle ne se
matérialise pleinement (ex. un indicateur externe au P&L lui-même,
pas dérivé de la même série de trades qu'il est censé protéger) — pas
identifié à ce jour.

**🆕 Suite immédiate 08/11 : correction méthodologique demandée AVANT
tout test de piste précurseur.** Le §2.16 ci-dessus a cherché un signal
en se concentrant sur nov22-jan23 (la fenêtre qui explique run202) —
methode biaisée en soi (chercher un signal pour une conclusion déjà
connue). §2.17 corrige : recense D'ABORD toutes les fenêtres de
sous-performance de l'échantillon, PUIS teste chaque piste contre
l'ensemble, pas contre le seul cas connu.

### 2.17 Piste 7 — Recensement complet des fenêtres de sous-performance (PRÉALABLE, 08/11)

Winrate/EV glissants (N=15/20/30) sur les 721 trades EN ENTIER, seuil
2σ théorique (`sqrt(p(1-p)/N)` pour le winrate, `std_R/sqrt(N)` pour
l'EV). Fenêtres contiguës regroupées (gap≤3 index) :

| Épisode | Dates | Durée | Winrate | EV | Sévérité |
|---|---|---|---|---|---|
| A | 2022-01-27 → 2022-03-08 | ~40j | ~19-21% | -0,45 à -0,50R | Modérée |
| B | 2022-06-09 → 2022-09-09 | ~90j | ~32% | -0,12R | Légère |
| **C-large** | 2022-09-05 → 2023-05-05 | ~8 mois | 20-25% | -0,26 à -0,41R | **Sévère (large)** |
| **C-core** | 2022-11-01 → 2023-01-20 | ~2,5 mois | **17,5%** | **-0,47 à -0,56R** | **LA PLUS SÉVÈRE** (= celle qui explique run202, §2.36-2.37) |
| D | 2023-07-11 → 2023-11-13 | ~4 mois | ~24-31% | -0,16 à -0,32R | Légère-modérée |
| E | 2023-12-20 → 2024-02-26 | ~2 mois | ~18-23% | -0,35 à -0,52R | Modérée |

**Conclusion méthodologique majeure : nov22-jan23 N'EST PAS un cas
isolé** — c'est le sous-épisode le plus sévère d'un phénomène RÉCURRENT
(6 épisodes distincts en 4,5 ans, un tous les 6-12 mois environ). Change
la nature du problème : pas un accident statistique rare à ignorer, un
phénomène à comprendre s'il est modélisable — mais aucun des épisodes
autres que C n'atteint la même sévérité, et leur écart temporel n'est
pas régulier (pas un cycle strict). Utilisé comme grille de test pour
toutes les pistes ci-dessous — **un signal qui ne matche QUE C(-core)
et pas A/B/D/E est un match probablement fortuit, pas adopté**.

### 2.18 Piste 1 — Régime macro (VIX/MOVE) — NÉGATIF, pas de signal généralisable (08/11)

VIX et MOVE récupérés directement (API Yahoo Finance en accès direct,
`yfinance` cassé dans cet environnement au moment du test — contournement
`requests` brut, `vix_daily_2022_2026.csv`/`move_daily_2022_2026.csv`).

| Épisode | VIX moyen (σ vs global) | MOVE moyen (σ vs global) |
|---|---|---|
| A | +1,53σ | -0,26σ |
| B | +1,06σ | +1,06σ |
| C-large | +0,64σ | +1,16σ |
| **C-core (le plus sévère)** | **+0,54σ (modeste)** | +0,88σ |
| D | **-0,59σ (BAS)** | +0,57σ |
| E | **-1,05σ (BAS)** | +0,29σ |

**Rejeté : pas de relation cohérente.** L'épisode le plus sévère (C-core)
n'a qu'une élévation VIX modeste, et deux épisodes clairement dégradés
(D, E) ont un VIX **en dessous** de la moyenne — l'inverse de
l'hypothèse "VIX élevé = edge dégradé". MOVE légèrement plus cohérent
(toujours positif) mais faible et non discriminant (+0,3 à +1,2σ,
jamais un vrai pic).

### 2.19 Piste 2 — Régime de corrélation inter-paires (glissant, PAS filtre) — NÉGATIF (08/11)

Corrélation glissante 20j moyenne inter-paires sur les 14 tickers
(closes daily via API Yahoo directe, `rolling_corr_20d.csv`).

| Épisode | Corrélation moyenne (σ vs global) |
|---|---|
| A | +1,89σ (élevée) |
| B | +0,27σ |
| C-large | -0,35σ |
| **C-core (le plus sévère)** | **-0,85σ (BASSE)** |
| D | -0,00σ |
| E | -0,55σ |

**Rejeté, et dans le sens INVERSE de l'hypothèse "risk-off généralisé"** :
l'épisode le plus sévère a la corrélation la PLUS BASSE de tous les
épisodes testés (-0,85σ), pas la plus haute. Distinct de Piste H
(§2.12 ancien registre, routage par paire déjà rejeté) — ici confirmé
que même le régime de corrélation générale n'est pas le mécanisme.

### 2.20 Piste 3 — Volatilité réalisée en régime (glissante, PAS filtre trade-par-trade) — MIXTE, NON GÉNÉRALISABLE (08/11)

Moyenne des |rendements| journaliers sur les 14 paires, glissante 20j.

| Épisode | Vol réalisée moyenne (σ vs global) |
|---|---|
| A | -0,59σ (basse) |
| B | +0,98σ |
| C-large | +1,27σ |
| **C-core (le plus sévère)** | **+1,58σ (la plus haute)** |
| D | -0,42σ (basse) |
| E | -0,53σ (basse) |

**Le seul des 3 signaux "régime" à montrer une gradation cohérente SUR
LE GROUPE B/C** (plus l'épisode est sévère, plus la vol est élevée) —
mais A/D/E (3 épisodes sur 6, dont 2 modérément sévères) montrent
l'INVERSE (vol en dessous de la moyenne). **Verdict : pas généralisable,
fonctionne sur la moitié des cas seulement (pile ou face)** — ne
satisfait pas la barre "spécifique aux vraies fenêtres creuses, pas
déclenché ailleurs" posée par Piste 7. Pas retenu pour un test de
coupe-circuit.

### 2.21 Piste 4 — Saisonnalité récurrente (Nov-Jan) — NÉGATIF, cas isolé confirmé (08/11)

Comparaison directe des 4 cycles Nov-Janv disponibles dans l'échantillon :

| Cycle | n | Winrate | EV |
|---|---|---|---|
| **Nov2022-Jan2023** | 49 | **14,3%** | **-0,564R** |
| Nov2023-Jan2024 | 33 | 48,5% | +0,357R |
| Nov2024-Jan2025 | 39 | 38,5% | +1,476R |
| Nov2025-Jan2026 | 53 | 47,2% | +1,422R |

**Rejeté sans ambiguïté : AUCUNE récurrence saisonnière.** Les 3 autres
cycles Nov-Janv de l'échantillon sont normaux à très bons (tous EV
positifs, souvent au-dessus de la moyenne globale +0,890R). Nov22-Jan23
est un cas isolé au sens calendaire strict — confirme (sur un axe
différent de Piste 7) que ce n'est pas un phénomène cyclique. Note
secondaire, hors sujet direct : février (toutes années confondues)
ressort comme le mois le plus faible de l'année (winrate 20,8%, EV
+0,10R, quasi-breakeven) — pas assez creusé pour un verdict, à noter
si un signal calendaire est reproposé un jour.

### 2.22 Piste 5 — Densité d'actualités à fort impact — NÉGATIF (08/11)

Réutilise `ff_calendar_historical_2007_2025.csv` (Test 1, §2.9).
Densité hebdomadaire moyenne globale : 18,82 événements High Impact/
semaine (tickers/devises confondus).

| Épisode | Densité (événements/semaine) | vs moyenne globale |
|---|---|---|
| A | 12,42 | -34% |
| B | 13,32 | -29% |
| C-large | 15,50 | -18% |
| **C-core (le plus sévère)** | **14,70** | **-22%** |
| D | 18,76 | ~identique |
| E | 14,31 | -24% |

**Rejeté, et dans le sens inverse encore une fois** : TOUS les épisodes
de sous-performance ont une densité de news **inférieure ou égale** à
la moyenne globale — jamais supérieure. Si un lien existe, il serait
inverse (moins de news = edge plus faible), mais l'écart n'est pas
assez marqué ni monotone avec la sévérité pour être un signal exploitable.

### 2.23 Piste 6 — Variance de R glissante (distincte du winrate) — NÉGATIF, pas de précurseur (08/11)

Écart-type glissant du R réalisé (pas juste le winrate), seuil 1,5σ vs
la moyenne globale de cet écart-type, sur la fenêtre C-core.

| N | 1ère déviation détectée |
|---|---|
| 10 | trade #36/40 (aussi tardif que le winrate à N=10, §2.16 point 1) |
| 15 | **ne dévie jamais >1,5σ dans la fenêtre** |
| 20 | **ne dévie jamais >1,5σ dans la fenêtre** |

**Rejeté : pas de signal précurseur, moins sensible que le winrate
lui-même.** Explication cohérente : la fenêtre creuse est caractérisée
par une PROPORTION de pertes anormalement élevée (winrate 17,5%), pas
par une DISPERSION anormale des résultats — les pertes restent des -1R
typiques, l'amplitude ne bouge pas, seule la fréquence directionnelle
change. La variance de R n'est structurellement pas le bon axe pour
détecter ce type de dégradation.

### 2.24 Piste 8 — Autocorrélation / clustering du signe des résultats — NÉGATIF, faible (08/11)

Sur la séquence chronologique complète (n=721, winrate 40,36%) :
- **Autocorrélation** (lags 1-10) : un seul lag significatif à p<0,05
  (lag=4, r=+0,074, p=0,049) sur 10 tests — attendu ~0,5 faux positif
  par hasard avec 10 comparaisons à α=0,05, **pas robuste**.
- **Test de runs (Wald-Wolfowitz)** : 323 runs observés vs 348,1
  attendus sous i.i.d., z=-1,943, **p=0,052** — tout juste NON
  significatif au seuil conventionnel 5%. Sens : légèrement moins de
  runs qu'attendu (tendance faible au clustering), mais pas assez pour
  rejeter l'hypothèse i.i.d.
- **Plus longue série de pertes consécutives** : 14, vs 11,52 attendu
  sous i.i.d. (Monte Carlo 5000 tirages) — **P(max≥14 sous i.i.d.) =
  18,2%**, pas un événement rare/extrême.

**Verdict : pas de clustering significatif au-delà du bruit d'un
processus i.i.d.** — cohérent avec le diagnostic déjà posé en 08/09
("bruit statistique pur sur un pool à edge positif haute variance").
Aucune base pour un coupe-circuit déclenché sur un compteur de pertes
consécutives.

### 2.24bis Piste 9 — Régime directionnel DXY (retournement de tendance dominante) — REJETÉ, décisivement (08/11)

Hypothèse distincte des pistes 1-8 (aucune ne testait un changement de
RÉGIME DIRECTIONNEL, seulement des niveaux) : le dollar a connu un
retournement de tendance majeur documenté fin 2022 (pic DXY 28/09/2022,
cassure confirmée début nov22) coïncidant avec C-core — hypothèse qu'une
stratégie orientée cassure/retournement performe mal spécifiquement
pendant un renversement de tendance dominante établie.

**Données** : DXY réel récupéré directement (ticker `DX-Y.NYB`, API
Yahoo en accès direct, `dxy_daily_2021_2026.csv`, 2021-06→2026-08 pour
disposer du recul MA100 dès janvier 2022). Indicateur : pente de la
MA50 sur 20 jours (`ma50_slope20`), retournement CONFIRMÉ si la
nouvelle direction tient ≥15 jours de trading (filtre anti-bruit).

**16 retournements confirmés sur la période** (~1 tous les 3,5 mois) —
dont le retournement du 2022-11-25 (USD haussier→baissier), qui
correspond bien à la cassure de tendance documentée par l'utilisateur et
tombe EN PLEIN dans C-core.

**Test de spécificité (EV mesurée directement sur ±30j autour de CHAQUE
retournement, pas juste C-core)** :

| Retournement | EV (±30j) | Négatif ? |
|---|---|---|
| 2022-03-04 | +0,216R | non |
| **2022-11-25 (= C-core)** | **-0,578R** | **oui** |
| 2023-04-04 | +0,032R | non |
| 2023-06-13 | +0,699R | non |
| 2023-07-25 | +0,055R | non |
| 2023-09-05 (proche D) | -0,152R | oui (léger) |
| 2023-11-30 | +0,499R | non |
| 2024-02-22 | +0,248R | non |
| 2024-07-11 → 2026-06-23 (8 retournements) | +0,626R à **+3,471R** | non, souvent très positif |

**Seuls 2/16 retournements (12,5%) coïncident avec un EV négatif** — et
un seul avec la sévérité de C-core. **EV moyen autour des 16
retournements : +0,835R, quasi identique à l'EV global (+0,890R)** —
aucune différence mesurable. Les 8 retournements les plus récents
(2024-2026) sont TOUS suivis d'EV positif, plusieurs fortement (jusqu'à
+3,47R) — un retournement de tendance dominante n'a, dans l'immense
majorité des cas, AUCUN effet négatif sur l'edge.

**Vérification inverse (point 4)** : la période Juin-Sept 2022 (épisode
B) s'est déroulée pendant une tendance DXY stable (aucun retournement
entre le 2022-03-04 et le 2022-11-25, ~9 mois sans cassure) — pourtant
l'edge y était légèrement dégradé (EV -0,12R). Une tendance stable ne
garantit pas non plus une bonne performance.

**Verdict : REJETÉ, décisivement — pas "plutôt cohérent", un vrai rejet
statistique.** Le signal ne coïncide qu'avec C-core (et très
marginalement avec D) sur 6 épisodes recensés et 16 retournements
testés — exactement le pattern de faux positif ponctuel que Piste 7
était censée prévenir. Aucun test de coupe-circuit engagé (rejet trop
net pour justifier l'effort). Fichiers : `dxy_daily_2021_2026.csv`,
`dxy_with_trend.csv`.

### 2.25 Bilan pistes 1-9 (08/11) — AUCUNE piste précurseur généralisable trouvée

Sur 9 pistes testées avec la même rigueur (dont Piste 7, le recensement
préalable qui a évité de valider un signal sur le seul cas déjà connu) :
**AUCUNE ne satisfait le critère "coïncide avec les vraies fenêtres
creuses ET pas ailleurs"**. VIX/MOVE, corrélation inter-paires et
densité news vont même dans le sens INVERSE de leur hypothèse
respective sur l'épisode le plus sévère. Volatilité réalisée est le
signal le moins mauvais mais ne fonctionne que sur la moitié des
épisodes. Le retournement de tendance DXY (Piste 9, l'hypothèse la plus
spécifique testée) ne coïncide qu'avec 2/16 fenêtres de retournement
(12,5%) et l'EV moyen autour de tous les retournements est quasi
identique à l'EV global — rejet net, pas un cas limite. Saisonnalité
confirme que nov22-jan23 est un cas isolé, pas récurrent.
Autocorrélation/clustering ne dépasse pas le bruit i.i.d. **Aucun test
de coupe-circuit supplémentaire justifié** — le rejet du coupe-circuit
réactif (§2.16) reste la conclusion opérationnelle, et cette session de
recherche de signal précurseur ferme la piste plus largement (pas
seulement le winrate contemporain déjà testé) : rien dans les données
actuelles ne permet de détecter une vraie dégradation structurelle
avant qu'elle ne se matérialise pleinement dans le P&L lui-même.

### 2.26 Piste 10 — Détection DXY EN TEMPS RÉEL pendant l'épisode (vs coupe-circuit winrate glissant) — REJETÉ (08/11)

Cadrage volontairement DIFFÉRENT de la Piste 9 (§2.24bis, prédiction AVANT
l'épisode, déjà rejetée) : pas de prédiction, une DÉTECTION EN COURS,
comparée en vitesse au coupe-circuit winrate glissant déjà testé et
rejeté (§2.16 `registre_parametres_projet.md`). Question précise : un
signal EXTERNE (DXY, indépendant de nos propres résultats) peut-il
détecter une dégradation plus vite qu'un signal INTERNE (winrate glissant
sur nos trades) ? Script : `edge_dxy_realtime_detection_2026-08-11.py`,
résultats bruts `edge_dxy_realtime_detection_results.csv`. Durée
d'exécution : ~10s (population 721 trades reconstruite depuis le cache
`yfinance_cache/` local, aucun appel réseau).

**Méthodologie** : réutilise `dxy_with_trend.csv` (déjà produit pour la
Piste 9, colonne `trend_dir` = signe brut de la pente MA50/20j — PAS de
confirmation intégrée dans ce fichier). Un retournement est **confirmé,
donc utilisable comme déclencheur causal réel**, quand le nouveau signe
tient 15 jours de trading consécutifs sans revenir en arrière (même
convention que §2.24bis) — le signal se déclenche le jour même où la
confirmation est atteinte, aucune information future n'est utilisée.
16 changements de signe bruts détectés sur 2022-2026, **aucun rejeté par
le filtre de confirmation** (tous ont tenu 15j) → 16 retournements
confirmés, mêmes dates qu'en §2.24bis (cohérence croisée vérifiée).

**Grille de test : les 6 épisodes recensés en Piste 7** (§2.17), pas
seulement C-core — délai de détection mesuré en jours calendaires depuis
le DÉBUT réel de chaque épisode, DXY vs winrate glissant N=15/20 (seuil
= moyenne historique − 2σ théorique, formule et méthode identiques à
§2.16 point 1, étendue ici aux 6 épisodes au lieu du seul C-core) :

| Épisode | Durée | DXY (confirmé 15j) | DXY (flip brut, borne inf. best-case) | Winrate N=15 | Winrate N=20 |
|---|---|---|---|---|---|
| A | 40j | AUCUN signal dans la fenêtre | — | +39j (98% fenêtre) | NON DÉTECTÉ |
| B | 92j | AUCUN (le plus proche : -77j, hors fenêtre) | — | NON DÉTECTÉ | NON DÉTECTÉ |
| C-large | 242j | +101j (42%) | +81j (33%) | +77j (32%) | +88j (36%) |
| **C-core** | **80j** | **+44j (55%)** | **+24j (30%)** | **+20j (25%)** | **+31j (39%)** |
| D | 125j | -6j (avant le début) | -28j | NON DÉTECTÉ | NON DÉTECTÉ |
| E | 68j | 0j (jour du début) | -20j | +63j (93%) | NON DÉTECTÉ |

**Résultat central (point 3, C-core = le seul épisode correspondant à
l'hypothèse d'un VRAI retournement dollar majeur, cf. réserve
d'échantillon ci-dessous) : le signal DXY est PLUS LENT que le
coupe-circuit winrate déjà rejeté, pas plus rapide.** Version réaliste
(confirmation 15j, la seule vraiment utilisable comme déclencheur en
conditions réelles) : détection à 55% de la fenêtre (+44j), contre 25%
(N=15) et 39% (N=20) pour le winrate glissant. Même la version la plus
optimiste possible — signal brut non confirmé, borne inférieure
irréaliste puisqu'inutilisable tel quel (aucune protection contre un
retour en arrière) — n'est qu'à égalité avec N=20 (30% vs 39%) et reste
plus lente que N=15 (30% vs 25%). **La prémisse du point 3 de la
consigne ("un signal externe pourrait réagir avant que nos pertes ne
s'accumulent assez pour bouger une moyenne glissante interne") est
directement infirmée sur le seul cas où elle pouvait s'appliquer.**
Sur D et E le signal DXY précède ou coïncide avec le début — mais ni D
ni E ne sont des épisodes de retournement dollar majeur au sens de
l'hypothèse (sévérité "légère-modérée", cf. Piste 7), la coïncidence de
timing y est probablement fortuite (16 retournements bruts sur 4,5 ans,
densité élevée).

**Point 4 — faux positifs, contre la grille des 6 épisodes (pas contre
la seule sévérité EV comme dans l'ancienne Piste 9)** : 8/16 retournements
confirmés (50%) ne coïncident avec AUCUN des 6 épisodes, même avec une
marge généreuse de ±30j. Plus parlant : **les 8 retournements les plus
récents (2024-07-31 → 2026-07-14, plus de la moitié de l'échantillon,
~2 ans consécutifs) sont TOUS des faux positifs** — aucun épisode de
sous-performance n'a été recensé sur toute cette période (Piste 7 couvre
les 721 trades en entier, pas seulement 2022-2024). Utilisé comme
déclencheur en conditions réelles sur la période la plus récente et la
plus étoffée du dataset, le signal se serait déclenché 8 fois pour rien.

**Réserve d'échantillon (demandée explicitement, signalée qu'elle que
soit la direction du résultat)** : au sens strict de l'hypothèse
(retournement de la tendance dollar PLURIANNUELLE dominante, pas une
simple pente locale MA50/20j), un seul des 16 retournements confirmés
correspond à un événement documenté comme majeur par une source externe
(pic DXY historique 28/09/2022, fin de la hausse la plus forte depuis
l'ère Volcker) — celui du 25/11/2022, qui est précisément C-core. Ce
mécanisme spécifique n'a donc qu'UNE seule observation dans les données
disponibles. **Ceci ne fragilise PAS le rejet** (contrairement à ce
qu'aurait fait un résultat positif sur ce même n=1) : la conclusion n'est
pas "le signal ne fonctionne jamais" de façon générale, mais "sur le seul
cas où il pouvait s'appliquer, il n'apporte aucun gain de vitesse
mesurable par rapport à un signal déjà rejeté" — une conclusion qui ne
nécessite pas plusieurs répétitions pour être valide, à la différence
d'une adoption qui en aurait exigé.

**Verdict : REJETÉ, point 5 non engagé.** Le signal n'est ni net ni
rapide sur C-core (condition explicite posée avant de justifier un
backtest coupe-circuit sur run202/n=300) — au contraire, il est plus
lent que l'alternative déjà écartée. Même conclusion opérationnelle que
Piste 9 et que le rejet du coupe-circuit réactif (§2.16
`registre_parametres_projet.md`) : aucun signal externe ou interne testé
à ce jour ne devance la matérialisation de la dégradation dans le P&L
lui-même. Fichiers sur disque : `edge_dxy_realtime_detection_2026-08-11
.py` (suivi par git) et `edge_dxy_realtime_detection_results.csv`
(non suivi, `*.csv` gitignoré projet entier sauf `correlation_matrix
.csv` — même convention que les ~100 autres CSV `etape_*` du dépôt).

### 2.27 Piste 11 — Amplification d'exposition sur bonne série confirmée — REJETÉ (08/11)

Distincte de la recherche de signal précurseur négatif (§2.16-2.26,
fermée, 10 pistes rejetées) : ici on ne cherche pas à détecter une
mauvaise période pour couper, mais une BONNE période confirmée pour
amplifier l'exposition pendant qu'elle dure. Hypothèse testée (prompt
utilisateur 08/11) : même avec un signal aussi imparfait que celui déjà
rejeté pour couper, l'asymétrie du coût d'erreur pourrait être favorable
à l'amplification (se tromper en amplifiant sur du bruit coûte peu, se
tromper en coupant sur du bruit coûte du vrai profit perdu).

**Étape 1 — recensement des fenêtres de surperformance** (721 trades,
même grille que Piste 7 §2.17, seuil moyenne+2σ, N=15/20/30,
`edge_amplification_episodes_2026-08-11.py`). Deux résultats mesurés
avant même de construire le mécanisme :
- **Le critère EV seul est inutilisable côté positif** — R n'est pas
  borné à la hausse (le trailing stop peut produire des gains très
  larges) mais borné à -1R à la baisse, donc un seuil EV crée un
  "sillage" artificiel : une seule grosse levée de trailing gonfle la
  fenêtre glissante EV pour les N trades suivants même s'ils sont
  eux-mêmes perdants. Pas symétrique au cas négatif de Piste 7 (le plancher
  -1R borne la queue côté casse). Bascule sur winrate seul — qui a
  l'avantage supplémentaire d'être exactement le signal déjà utilisé par
  le coupe-circuit rejeté (`compute_pause_mask`,
  `edge_circuit_breaker_v2_2026-08-11.py`), donc comparaison directe à
  l'Étape 4.
- **Diagnostic de persistance (nouveau, ajouté en cours de route)** :
  corrélation entre le winrate glissant précédent un trade et l'issue de
  ce trade est quasi nulle (+0,03 à +0,11 selon N=15/20/30) — très
  faible comparé aux 6 épisodes froids substantiels et récurrents de
  Piste 7. Sous le seuil winrate seul (2σ), 10/6/4 épisodes trouvés selon
  N, mais courts (quelques jours à quelques semaines, jamais plusieurs
  mois) — contre les 6 épisodes de Piste 7 (semaines à mois). Signal
  d'alerte fort mesuré AVANT de construire le mécanisme, mais la mesure a
  été poursuivie jusqu'au bout conformément à la consigne (mesurer, pas
  supposer).

**Étape 2b — mécanisme et 3 variantes** (`edge_amplification_fleet_2026-
08-11.py`, base = référence officielle par plafond, décision #16
`registre_parametres_projet.md` §1.8/§2.35bis — Run C à 1000$, Run F à
3000$). Détection : fenêtre glissante N=20, seuil winrate>62,3% (formule
2σ, mirroir exact de la meilleure config testée côté coupe-circuit,
20/0,18/20), sortie 20 trades après l'entrée (délai fixe, même
convention que le coupe-circuit). 3 variantes testées séparément, jamais
combinées :
1. **unlock** — seuil de réserve pour le déclenchement de groupe/palier
   divisé par 2 pendant un épisode boost (déblocage accéléré).
2. **sizing** — risque multiplié par 1,3 pendant un épisode boost.
3. **reopen** — coût de réouverture/rachat après casse réduit de 15%
   pendant un épisode boost (même mécanique que le discount FTMO déjà
   codé, appliqué ici à toutes les firms pendant un boost).

**Étape 3 — n=300, deux plafonds, faux positifs mesurés explicitement**
(overlap calendaire avec les fenêtres de surperformance de l'Étape 1,
même méthode que le point 2 du coupe-circuit) :

| Plafond | Config | Profit moyen | Δ vs référence | solde_negatif_annee4 | hit_ceiling_pct | Année1<0 |
|---|---|---|---|---|---|---|
| 1000$ | référence (Run C) | 5 588 381$ | — | 1,33% | 3,33% | 32,67% |
| 1000$ | unlock | 5 606 460$ | +0,32% | 1,67% (pire) | 3,33% | 33,00% (pire) |
| 1000$ | sizing | 5 374 527$ | **-3,83%** | 1,67% (pire) | 3,33% | 34,00% (pire) |
| 1000$ | reopen | 5 588 964$ | +0,01% (nul) | 1,33% | 3,33% | 32,67% |
| 3000$ | référence (Run F) | 5 658 217$ | — | 0,67% | 1,67% | 29,00% |
| 3000$ | unlock | 5 675 445$ | +0,30% | 0,67% | 3,00% (pire) | 29,00% |
| 3000$ | sizing | 5 495 444$ | **-2,88%** | 0,67% | 2,33% (pire) | 28,67% |
| 3000$ | reopen | 5 659 019$ | +0,01% (nul) | 0,67% | 1,67% | 29,00% |

**Taux de faux positifs mesuré (n=300, deux plafonds confondus — la
détection est identique pour les 3 variantes)** : 1 261 épisodes
déclenchés au total, 522 vrais positifs (chevauchent une fenêtre de
surperformance connue de l'Étape 1), **739 faux positifs — 58,6%**, plus
d'un épisode sur deux. Cohérent avec le diagnostic de persistance quasi
nulle de l'Étape 1.

**Étape 4 — verdict, comparaison explicite au coupe-circuit** (§2.16
`registre_parametres_projet.md`, config gagnante N=20/X=18%/M=10 :
-5,5%/-5,7% de profit pour un année1<0 identique à la référence, REJETÉ) :
aucune des 3 variantes d'amplification ne produit de gain net. `sizing`
perd -2,9 à -3,8% de profit ET dégrade les 3 axes de risque aux deux
plafonds — pire que le coupe-circuit sur le rapport coût/bénéfice, pas
meilleur. `reopen` est économiquement nul (effet <0,01%, le rachat après
casse coûte déjà trop peu pour qu'une remise de 15% se voie). `unlock`
est le seul cas où l'hypothèse d'asymétrie tient PARTIELLEMENT sur
l'ordre de grandeur du coût (+0,3% de profit contre -5,5% pour le
coupe-circuit) — mais ce n'est pas un gain net non plus : hit_ceiling se
dégrade à 3000$ (+1,33pt) et solde_negatif_annee4 à 1000$ (+0,34pt), pour
un gain de profit dans le bruit. **Conclusion demandée explicitement par
le prompt utilisateur en cas de ratio non nettement meilleur : le
problème n'est pas l'asymétrie du coût d'erreur, c'est la fiabilité
intrinsèque du signal** (persistance quasi nulle, 58,6% de faux
positifs) — la piste est fermée avec la MÊME conclusion opérationnelle
que le coupe-circuit réactif et que Piste 9/10 (DXY) : aucun signal
testé à ce jour, ni pour couper ni pour amplifier, ne devance ou n'exploite
utilement la matérialisation du edge dans le P&L lui-même. **REJETÉ,
n=600 non engagé** (aucune configuration positive à confirmer). Fichiers :
`edge_amplification_episodes_2026-08-11.py`,
`edge_amplification_fleet_2026-08-11.py` (suivis par git),
`edge_amplification_episodes_2026-08-11.csv`,
`edge_amplification_fleet_n300.csv` (non suivis, convention gitignore
standard du projet).

### 2.28 Plafond de 3 positions simultanées — REJETÉ (cap=4 ET swap), Section 4 non engagée (08/15)

**Contexte** : chantier demandé explicitement pour vérifier si le plafond de
3 positions ouvertes par compte (`MAX_POSITIONS`, `scaling_simulation.py`)
bloque des signaux à haut RR de façon significative, sous la base actuelle
du projet (RR≥1,35, corrélation 0,80, éval=1,25%, §1.8
`registre_parametres_projet.md`). Fichier : `chantier_position_cap_2026-
08-15.py` (suivi par git).

**⚠️ Correction méthodologique reçue de l'utilisateur en cours de chantier** :
la doc historique de `missed_signals_replay.py` ("un signal bloqué sur un
compte peut être pris par un autre") est **fausse pour les comptes d'une
même firm** (FTMO a 2 comptes day-0, The5%ers en a 4, `N_ACCOUNTS_DAY0`
`etape_e_fleet_integration.py:120`) : en copytrade, ces clones reçoivent le
même flux de signaux, au même risque%, avec les mêmes règles de DD, ouverts
au même instant — rien dans le moteur n'introduit de divergence entre eux
(aucun RNG par-compte), donc ils bloquent/cassent en **lockstep parfait**.
La redondance "un autre compte peut prendre le relais" n'existe qu'**ENTRE
FIRMS DIFFÉRENTES** (règles de DD et âges différents), pas entre clones
d'une même firm. Le remplay 1-compte de la Section 1 (ci-dessous) est donc une borne
haute plus généreuse que ce que le texte d'origine suggérait — mais peu
importe pour le verdict final : les chiffres $ qui tranchent (Section
2/3) viennent du moteur de flotte complet, où chaque compte (y compris les
clones FTMO/Fivers) suit son propre `open_positions` correctement, sans
cette approximation.

**Section 1 — ampleur (replay chronologique 1-compte, population réelle
RR≥1,35, n=631)** :

| | n | % population | R_trailing moyen | Winrate | RR (rr_tp1) moyen |
|---|---|---|---|---|---|
| Pris | 582 | 92,2% | +0,819 | 38,7% | 1,97 |
| Bloqué (cap) | 5 | **0,8%** | **-0,500** | **20,0%** | 1,95 |
| Bloqué (corrélation) | 44 | 7,0% | +2,029 | 52,3% | 2,15 |

Volume marginal (5 cas sur 631) et — résultat contre-intuitif — les
signaux historiquement bloqués par le cap auraient en moyenne PERDU de
l'argent (-0,500R, winrate 20%), malgré un RR planifié correct. RR max
observé chez les bloqués-cap = 2,81 (jamais de RR "exceptionnel type 5" —
`rr_tp1` est de toute façon plafonné à 3,0 par construction du payoff
trailing, `pop['rr_tp1'].max()`=3,0 vérifié). n=5 trop petit pour un
verdict en soi — juste un signal d'alerte cohérent avec le verdict final
ci-dessous.

**Sections 2/3 — moteur de flotte complet, n=300, seed=9999, référence
RunC/RunF rr135/corr080 (§1.8) comme baseline `REF_cap3`** :

| Config | Plafond | Profit moyen | Δ vs REF | solde_neg_an4 | hit_ceiling | Année1<0 |
|---|---|---|---|---|---|---|
| REF (cap=3) | 1000$ | 5 915 946$ | — | 0,33% | 2,00% | 28,00% |
| **Section 2 — cap=4** | 1000$ | 5 928 809$ | **+0,22%** | 0,67% (pire) | 2,00% | 28,00% |
| Section 3 — swap X=1,5 | 1000$ | 5 890 726$ | -0,43% | 0,33% | 1,67% (mieux) | 27,67% (mieux) |
| Section 3 — swap X=2,0 | 1000$ | 5 899 331$ | -0,28% | 0,33% | 1,67% (mieux) | 27,67% (mieux) |
| Section 3 — swap X=3,0 | 1000$ | 5 915 946$ | 0,00% (0 éviction) | 0,33% | 2,00% | 28,00% |
| REF (cap=3) | 3000$ | 5 919 687$ | — | 0,33% | 1,00% | 28,00% |
| Section 2 — cap=4 | 3000$ | 5 948 372$ | **+0,48%** | 0,33% | 1,00% | 28,00% |
| Section 3 — swap X=1,5 | 3000$ | 5 892 831$ | -0,45% | 0,33% | 1,00% | 27,67% (mieux) |
| Section 3 — swap X=2,0 | 3000$ | 5 901 436$ | -0,31% | 0,33% | 1,00% | 27,67% (mieux) |
| Section 3 — swap X=3,0 | 3000$ | 5 919 687$ | 0,00% (0 éviction) | 0,33% | 1,00% | 28,00% |

X=3,0 est un no-op structurel confirmé (ratio max possible entre deux
`rr_tp1` de la population = 3,0/1,35 = 2,22, donc `rr_tp1_nouveau >=
3,0 x rr_tp1_le_plus_faible` n'est jamais atteignable — 0 éviction
mesurée aux deux plafonds, cohérent). X=1,5/2,0 déclenchent en moyenne
~20-22 évictions par run sur un total de plusieurs milliers de trades
fleet-wide sur 4 ans — volume dérisoire, cohérent avec Section 1.

**Limite de modélisation explicite (Section 3, swap)** : le moteur
(`engine_multiformat.process_trade_mf`) applique le PnL d'un trade
intégralement à SON OUVERTURE (résolution instantanée, aucun prix
intra-position suivi). "Couper" une position ne peut donc être modélisé
qu'en libérant son slot d'occupation SANS toucher au PnL déjà appliqué
(qui reste son issue réelle finale) — ce qui SURESTIME probablement le
vrai gain d'un swap réel (une vraie coupe anticipée change le R réel,
généralement vers un résultat moins extrême que l'issue finale). Signalé
explicitement plutôt que supposé neutre.

**Verdict : REJETÉ dans les deux variantes testées.** Cap=4 apporte un
gain de profit dans le bruit (+0,2%/+0,5%, effet de cet ordre jamais
confirmé à n=600 dans ce projet) tout en dégradant légèrement
solde_negatif_annee4 à 1000$ (0,33%→0,67%, ×2 mais reste marginal en
absolu à n=300). Le swap (X=1,5/2,0) est carrément CONTRE-PRODUCTIF sur
le profit (-0,3% à -0,5%) malgré une légère amélioration de hit_ceiling/
année1<0 — cohérent avec Section 1 (les signaux historiquement bloqués
par le cap ont un R_trailing négatif en moyenne, donc les capturer coûte
plus qu'il ne rapporte), ET ce, avec une limite de modélisation qui
SURESTIME déjà l'effet réel. **N=600 non engagé** — aucune configuration
positive à confirmer, exactement le cas visé par la consigne du prompt
("si le volume est marginal, le dire explicitement, pas la peine de
complexifier").

**Section 4 (4e position temporaire + retour à 3) : NON ENGAGÉE**, gating
explicite du prompt ("seulement si Section 3 déçoit") — Section 3 n'a pas
juste déçu, elle est allée dans le sens négatif sur l'axe qui compte le
plus (profit), avec une méthodologie déjà optimiste. Rien dans ces
résultats ne suggère qu'une variante plus complexe (4e slot temporaire)
inverserait le verdict — le goulot d'étranglement mesuré (0,8% de la
population, EV négatif sur ces cas précis) est trop petit pour qu'aucune
règle de gestion de plafond ne produise un gain mesurable. **Chantier
fermé.**

Fichiers : `chantier_position_cap_2026-08-15.py` (suivi par git),
`chantier_position_cap_section1_detail_2026-08-15.csv`,
`chantier_position_cap_n300_2026-08-15.csv`,
`chantier_position_cap_run_2026-08-15.log` (non suivis, convention
gitignore standard du projet).

**Vérification complémentaire demandée le 08/15 (même jour) : le 14/08 est-il
un jour normal ou un outlier, méthodologie Section 1 fiable ?** Script
`verif_clustering_14aout_2026-08-15.py` (suivi par git) :
- **Q1** — sur la population complète min_rr=1,25 (721 trades) : **29,6% des
  jours actifs (153/517) ont 2+ signaux le même jour calendaire**, 8,1% en
  ont 3+. Le 14/08 (2 signaux) est un jour **NORMAL**, pas un outlier.
- **Q2** — audit du code de Section 1 : compare des timestamps complets
  (`date_creation`/`resolution_time_est`), PAS des jours calendaires — aucun
  bug de granularité trouvé. Point de vigilance réel mais mineur : le
  fallback à la durée médiane (~7h41, pour les ~49% de trades non vérifiés
  par bougies H1) sous-estime probablement la queue longue de la
  distribution réelle (moyenne 29,3h vs médiane 7,7h, p95=140,7h≈5,9j sur
  les 325 trades vérifiés) — source plausible de sous-comptage résiduel,
  concentrée sur les positions les plus longues, mais pas une erreur de
  méthode.
- **Q3** — taux de blocage cap, population 631 (RR≥1,35) : temps réel
  (Section 1) = 0,79% (5/631) vs méthode naïve jour-calendaire (borne
  haute grossière, ignore les heures) = 1,11% (7/631) — **écart de
  seulement 1,4x**, pas d'ordre de grandeur.
- **Verdict : ni anomalie statistique, ni sous-comptage structurel.**
  "Même jour" (fréquent, 29,6%) et "chevauchement réel de position" (rare,
  <1%) sont deux choses différentes — la durée médiane de détention
  (~7h41) est courte devant l'écart typique entre signaux, donc un jour à
  2 signaux ne sature quasiment jamais le plafond de 3. Le verdict REJETÉ
  du chantier ci-dessus tient, avec une nuance mineure notée (queue longue
  de durée, biais résiduel non quantifié précisément mais probablement
  petit vu que même la borne haute naïve reste basse).

### 2.29 CHANTIER 2 (08/15) — Stabilité temporelle du winrate + distribution bayésienne, population actuelle (RR≥1,35, 631 trades)

Fichier : `chantier2_section2_stability_bayes_2026-08-15.py` (suivi par
git). Refait sur la base actuelle (les analyses antérieures de ce type
tournaient sur RR≥1,25/721 ou RR≥1,5/472).

**Population** : n=631, wins=249, losses=382, winrate observé=39,46%, RR
(rr_tp1) moyen=1,985.

**Stabilité temporelle** — winrate par semestre : 2022-S1 41,5% →
2022-S2 28,2% → 2023-S1 34,5% → 2023-S2 38,3% → 2024-S1 46,4% → 2024-S2
43,2% → 2025-S1 42,0% → 2025-S2 39,3% → 2026-S1 40,0% (n=75) → 2026-S2
50,0% (n=10 seulement, à ignorer). **Aucune dérive temporelle
statistiquement significative** : test le plus puissant disponible
(corrélation point-bisériale trade-par-trade, pas de perte d'info par
binning) r=+0,057, p=0,150 > 0,05. Une régression sur les moyennes
semestrielles suggère une légère tendance HAUSSIÈRE (pente
+0,0116/semestre) mais reste elle-même non significative (p=0,079) — pas
un signal à traiter, cohérent avec un winrate stable dans le temps.

**Distribution bayésienne** (prior Jeffreys Beta(0,5;0,5), non-informatif
standard — PAS le posterior Beta(172,66;305,36) de
`winrate_bayesian_posterior_weighted.py`, qui vient d'un contexte
différent et sans rapport, ancienne population 472 trades + scénario "15
pertes consécutives" spécifique ; sensibilité vérifiée avec un prior
uniforme Beta(1,1), résultat quasi identique — le choix de prior importe
peu à n=631) :
- Posterior Beta(249,5 ; 382,5) → **P10=36,99% | P50=39,47% | P90=41,98%**
- P(winrate>35%)=99,0% | P(winrate>38%)=77,6% | P(winrate>40%)=39,2% |
  P(winrate>42%)=9,8%
- EV correspondant à chaque seuil (RR=1,985) : +0,045R (35%) / +0,135R
  (38%) / +0,194R (40%) / +0,254R (42%)

**Seuil de rentabilité (EV=0)** : winrate_seuil = 1/(RR+1) = **33,50%**.
**P(winrate réel < seuil, donc EV réel < 0) = 0,09%** sous le posterior
Jeffreys — marge du winrate observé au-dessus du seuil : **+5,97pt**
(39,46% observé vs 33,50% seuil). **Verdict : edge statistiquement très
solide, risque de faux edge quasi nul (<0,1%) sur cette population.**

### 2.30 CHANTIER 2 (08/15) — Frottements réels décomposés, population actuelle (RR≥1,35, 631 trades)

Fichiers : `chantier2_section1_slippage_631_2026-08-15.py`,
`chantier2_section1_frictions_bdef_2026-08-15.py` (suivis par git),
`slippage_proxy_dukascopy_detail_631_2026-08-15.csv` (non suivi,
convention gitignore).

**a) Slippage réel (Dukascopy)** — 469/472 trades déjà mesurés (ancienne
base RR≥1,5) + 159/162 trades supplémentaires mesurés spécifiquement pour
ce chantier (nouveaux appels tick Dukascopy, 3 sans tick trouvé malgré
retries réseau) → **628/631 trades couverts (99,5%)**. Slippage moyen
**-0,939 pips** (médiane -0,700 pips), quasi identique à l'ancien test
(-0,910 pips sur RR≥1,5/469 trades) — se généralise bien à la population
élargie, pas d'anomalie. Par classe d'actif : /JPY -1,111 | /USD -0,426 |
/GBP -0,814 | /CHF -1,224 | /CAD -1,639 pips. Reconstruction déterministe
par trade (pas un tirage dans la distribution empirique comme
`slippage_adjusted_population.py` — ici le slippage RÉEL mesuré de
CHAQUE trade est appliqué à CE trade, plus précis) : **EV +0,8934R
(sans frottement) → +0,8490R (avec slippage) = -0,0444R (-5,0%)**, très
proche de l'ancien chiffre cité (-6,3%) — l'écart s'explique par un
mélange population plus large (RR≥1,35) + méthode déterministe vs tirage
empirique, dans le même ordre de grandeur.

**d) Swap/rollover** — hypothèse haute -2 à -3 pips/nuit, pondérée par le
vrai nombre de franchissements de l'heure de rollover (22h UTC,
convention retail standard) entre `date_creation` et
`resolution_time_est` de chaque trade (pas une durée moyenne globale
appliquée uniformément) : 40,3% des trades franchissent au moins 1
rollover. Coût moyen dilué sur la population entière : **-0,053R/trade**
(hypothèse -2 pips/nuit) à **-0,079R/trade** (hypothèse -3 pips/nuit).

**e) Erreurs de parsing/exécution manquée** — modélisé comme un
prélèvement PROPORTIONNEL sur l'EV (trades manqués = échantillon
aléatoire, pas de biais supposé sur lesquels) : coût = miss_rate × EV,
donc **dépend explicitement de quelle EV sert de référence** (⚠️
autocorrection en cours d'assemblage : le calcul initial de ce
paragraphe utilisait par erreur l'EV simple +0,153R comme base pour LES
DEUX combinaisons finales ci-dessous, alors que la combinaison "EV
plancher réaliste" doit utiliser l'EV réaliste +0,8934R comme base —
corrigé dans les totaux ci-dessous, l'écart final reste minime mais
autant citer le bon chiffre) : à 3% (hypothèse haute retenue), coût
= 0,03×0,8934=**-0,0268R** (base réaliste) ou 0,03×0,1042=**-0,0031R**
(base P10 bayésien, RR moyen simple) selon la combinaison utilisée
ci-dessous.

**f) Gap de week-end** — revérifié sur la population actuelle (193/382
pertes couvertes par les bougies H1, même limite ~730j que d'habitude) :
**4/193 pertes couvertes (2,1%)** touchées par un gap ≥20h, coût excess
moyen sur ces cas +0,434R (au-delà du -1R théorique). Dilué sur
l'ensemble des pertes couvertes : **+0,009R/perte** ; dilué sur la
population totale (n=631, gains inclus) : **-0,00275R/trade** (frottement
mineur, cohérent avec la faible fréquence de gaps significatifs sur ces
14 paires majeures/mineures).

**b) Spread** — la mesure de slippage Dukascopy (point a) compare déjà
`prix_entree` au prix réellement tradable (ask pour un achat, bid pour
une vente) : le coût du côté spread payé à l'entrée est donc **déjà
inclus** dans le slippage mesuré, ce n'est pas un frottement additif
séparé (coût = 0 dans la combinaison ci-dessous). Vérification de
symétrie/widening +20-30% non poussée plus loin — la note méthodologique
ci-dessus rend le point largement sans objet (il n'y a pas de second
frottement distinct à isoler).

**c) Latence d'exécution** (délai email→bot, proxy 10s = milieu de la
fourchette 5-15s demandée, mesuré par décalage de tick Dukascopy sur
607/631 trades, mêmes heures que (a) donc déjà en cache) : mouvement
moyen sur 10s = **-0,0217 pips** (médiane 0,0000), **pas de biais
directionnel détectable** (test t : p=0,447 — le bruit domine largement
le signal à cette échelle de temps, cohérent avec un marché liquide sur
ces 14 paires). Coût pessimiste (ne compte QUE le mouvement défavorable,
hypothèse conservatrice demandée) : **-0,00838R/trade** en moyenne.

**Section 1 point 3 — EV plancher final**, combinaison additive de tous
les frottements (hypothèse pessimiste sur chacun) :

| Frottement | Coût (R) |
|---|---|
| a) Slippage réel (mesuré) | -0,0444 |
| b) Spread (déjà inclus dans a) | 0 |
| c) Latence exécution (pessimiste) | -0,0084 |
| d) Swap/rollover (-3 pips/nuit, pessimiste) | -0,0792 |
| e) Erreurs parsing (3%, pessimiste) | -0,0268 (base réaliste) |
| f) Gap week-end (dilué population) | -0,0028 |
| **TOTAL** | **-0,1615** |

**EV plancher (base réaliste, EV brute +0,8934R avec payoff trailing/TP2)
= +0,7319R** — largement positif même sous l'hypothèse pessimiste
cumulée de TOUS les frottements simultanément.

**Combiné avec le P10 bayésien du winrate (Section 2, 36,99%) et l'EV
SIMPLE (RR moyen 1,985, pas le payoff réaliste — cohérence avec la
formule EV=0 de la Section 2)** : EV brute à ce P10 = +0,1042R → total
frottements recalculé à cette base (e recalculé = 0,03×0,1042=-0,0031R,
total=-0,1378R) → **EV PLANCHER FINAL = -0,0336R**.

**🔴 Verdict : le plancher ABSOLU (P10 winrate pessimiste ET tous les
frottements au pire cas simultanément, ET formule EV simple sans le
bonus du payoff réaliste trailing/TP2) devient marginalement NÉGATIF.**
À lire avec 3 nuances explicites, pas comme une alerte au même titre
qu'un signal cassé :
1. C'est un cumul de PLUSIEURS scénarios pessimistes indépendants à la
   fois (P10 winrate ET pire cas sur chaque frottement) — la probabilité
   que TOUS se matérialisent simultanément est bien plus faible que
   10% seul. C'est un stress-test du plancher, pas un scénario probable.
2. La formule utilise le RR simple (1,985), pas le payoff RÉALISTE
   (trailing/continuation TP2) qui donne l'EV brute réelle du projet
   (+0,8934R) — sous cette base réaliste (plus fidèle à ce qui est
   effectivement tradé), le plancher reste **largement positif
   (+0,7319R)**, cf. tableau ci-dessus.
3. Le winrate observé actuel (39,46%) reste à +5,97pt au-dessus du
   seuil de rentabilité EV simple (33,50%, Section 2) — le scénario P10
   (36,99%) est déjà lui-même conservateur, pas la médiane.
**Conclusion opérationnelle : pas de signal d'alarme sur l'edge lui-même
(la marge réaliste reste large), mais le point mérite d'être gardé en
tête si plusieurs frottements pessimistes se cumulaient EN MÊME TEMPS
qu'une mauvaise série de winrate — ce n'est capturé nulle part ailleurs
dans le projet avant ce chantier.**

### 2.31 CHANTIER 2 (08/15) — Couverture ADX/ATR sur population actuelle + coût d'extension Dukascopy — extension REFUSÉE (raisonnée), verdict ADX/ATR mis à jour

**Couverture actuelle** (RR≥1,35, 631 trades) : **328/631 (52,0%)** —
quasiment identique à l'ancienne mesure (52,0% sur 375/721, RR≥1,25) : le
changement de seuil RR n'a pas changé la couverture, cohérent (la
contrainte est la fenêtre H1 Yahoo ~730j, indépendante du seuil RR).
Fenêtre couverte : 2024-08-01 → 2026-07-30 ; fenêtre non couverte :
2022-01-31 → 2024-08-01 (**913 jours**).

**Estimation coût/temps de l'extension Dukascopy (demandée avant tout
lancement)** : construire des bougies H1 continues sur les 913 jours non
couverts × 14 tickers nécessite un appel par heure de marché actif
(≈120h/168h en forex) : 913j × 24h × (120/168) ≈ **15 650 heures actives
× 14 tickers ≈ 219 000 requêtes**. Au délai minimal imposé par le code
(0,3s anti-429, `dukascopy_ticks.REQUEST_DELAY_SECONDS`) plus latence
réseau réaliste (0,3-1,0s tout compris avec les 429 déjà observés sur ce
projet) : **18 à 61 heures d'exécution continue, mono-thread** (le
parallélisme agressif est risqué — Dukascopy limite déjà le débit sans
`Retry-After`, cf. docstring `dukascopy_ticks.py`).

**Décision : extension REFUSÉE, chantier lourd disproportionné au signal
recherché.** Même APRÈS mise à jour sur la population actuelle (ci-dessous),
le signal ADX/ATR reste dans la même zone d'incertitude qu'en 08/11 (IC
bootstrap traversant largement zéro) — passer 1 à 2,5 jours de scraping
continu pour renforcer un lead déjà marginal n'est pas un usage
raisonnable du temps, conformément au gating explicite du prompt ("si
raisonnable, étendre"). Le point reste ouvert pour reconsidération future
si un nouveau lead structurel rendait ADX/ATR prioritaire.

**Verdict ADX/ATR mis à jour SANS extension** (population RR≥1,35,
corrélation 0,80, couverture 52% inchangée, n=328 couverts) :

| Config | n | Winrate | EV (R) | Δ vs baseline | Sous-période 1 | Sous-période 2 |
|---|---|---|---|---|---|---|
| Baseline (couvert, sans filtre) | 328 | 41,2% | 1,636 | — | 1,864 | 1,409 |
| ADX≥20 | 207 | 42,5% | 1,806 | +10,4% | 2,099 | 1,516 |
| ADX≥25 | 126 | 43,7% | 1,792 | +9,6% | 2,165 | 1,419 |
| ADX≥30 | 77 | 39,0% | 1,572 | -3,9% | 1,846 | 1,305 |
| ATR[0,5-2,0] | 313 | 40,6% | 1,590 | -2,8% | 1,779 | 1,402 |
| **COMBO ADX≥20+ATR[0,5-2,0]** | 196 | 42,3% | 1,769 | **+8,1%** | 2,064 | 1,474 |

**Changement notable vs 08/11** : sous l'ANCIENNE base (RR≥1,25), ADX
seul s'effondrait en sous-période 2 (signe qui s'inversait) — sous la
NOUVELLE base (RR≥1,35, corr 0,80), **ADX≥20 seul ET le combo restent
positifs dans les DEUX sous-périodes** (ADX≥20 : 2,099→1,516 ;
combo : 2,064→1,474 ; baseline : 1,864→1,409 — tous en baisse en
période 2, cohérent avec la baisse globale du winrate en 2025-2026, mais
le FILTRE reste au-dessus du baseline dans les deux). IC bootstrap
(5000 itérations) sur le delta EV du combo : **+0,133R observé, IC95%=
[-0,496, +0,778], P(delta>0)=65,2%** (vs 61,8% en 08/11 — légère
amélioration mais **toujours pas significatif**, l'IC traverse
largement zéro).

**Verdict final : PAS ADOPTÉ, toujours pas rejeté non plus — statut
inchangé malgré la mise à jour.** Le signe ne s'inverse plus en
sous-période (amélioration qualitative réelle par rapport à 08/11), mais
la significativité statistique reste insuffisante (n=196 pour le combo,
IC large). Extension de couverture refusée pour la raison de coût
ci-dessus — ce point restera dans cet état tant qu'aucun signal
structurel supplémentaire ne justifie le coût de l'extension complète.

### 2.32 Échange par corrélation — classement de paires + mécanisme d'échange ciblé sur les blocages corrélation (08/16)

**Contexte** : suite directe de §2.28 (plafond de 3 positions, REJETÉ) —
mais cible ici le blocage par la règle de **corrélation** (44 trades, 7,0%
de la population, R_trailing moyen +2,029 — bien plus significatif en
volume ET en qualité que les 5 trades bloqués par le cap, EV -0,500,
déjà fermé). Fichiers : `chantier_correlation_swap_2026-08-16.py`,
`chantier_correlation_swap_h1rank_check_2026-08-16.py`,
`chantier_correlation_swap_n600_confirm_2026-08-16.py` (tous suivis par
git), CSV associés (non suivis, convention gitignore).

**Section 0 — robustesse du chiffre +2,029R** : distribution complète des
44 R_trailing bloqués-corrélation = 23 valeurs positives (+1,45 à +10,27)
+ 21 valeurs exactement à -1,00 (pas de traîne d'outliers positifs
au-delà de +10,27). Médiane +1,508R. Retrait du top 3 : moyenne
+1,555R (delta -0,47R). Retrait du top 5 : moyenne +1,284R (delta
-0,74R). Bootstrap IC95% (5000 itérations) : **[+1,05R, +3,02R],
P(moyenne>0)=100,0%**. **Verdict : signal robuste, ne dépend pas de
quelques outliers** — reste largement positif même après retrait des 5
meilleurs cas.

**Section 1 — classement de paires** (EV/winrate/rendement total par
ticker, population complète 631 trades) :

| Quartile | Paires | EV (R) |
|---|---|---|
| 1 (meilleur) | AUD/USD (n=57), AUD/JPY (n=57), GBP/CHF (n=30), EUR/JPY (n=42) | +1,22 à +1,42 |
| 2 | GBP/JPY (n=49), USD/JPY (n=43), CHF/JPY (n=46) | +0,99 à +1,15 |
| 3 | GBP/USD (n=40), EUR/USD (n=38), NZD/USD (n=60) | +0,62 à +0,93 |
| 4 (pire) | USD/CHF (n=41), EUR/CHF (n=36), USD/CAD (n=49), EUR/GBP (n=43) | +0,06 à +0,62 |

Aucune paire sous n=20 sur la population complète (fiabilité correcte).

**🔴 Alerte data-mining confirmée (piège déjà rencontré sur ce projet —
score Force, ADX/ATR)** : validation split temporel (classement calculé
sur H1 seul [n=315, 2022-01-31→2024-08-22], testé sur H2 [n=316,
2024-08-30→2026-07-30]) — **l'ordre ne se maintient PAS hors
échantillon**. EV pondéré en H2 du quartile 1-selon-H1 = +1,635R contre
**+1,793R pour le quartile 4-selon-H1** (ordre inversé). Corrélation de
rang (Spearman) entre classement H1 et classement population complète =
**0,446** (faible). Sur H1 seul, 6/14 paires ont n<20 (1, GBP/CHF, n<15)
— échantillon par moitié trop petit pour un classement stable par
paire à ce niveau de granularité (14 tickers seulement).

**Section 2 — mécanisme d'échange** (moteur de flotte complet, copie de
`chantier_position_cap_2026-08-15.py`, convention "copie figée, points
`<<< CHANTIER` marqués") : au moment où un signal est bloqué par la
règle de corrélation avec EXACTEMENT une position ouverte conflictuelle
(cas à conflits multiples simultanés : non traité, trop rare), teste
l'écart de quartile entre la paire bloquée et la paire occupante ; si
favorable selon la variante, ferme la position occupante pour admettre
le signal bloqué. Même limite de modélisation que §2.28 (PnL de la
position coupée déjà appliqué à son ouverture, non recalculé — borne
HAUTE de l'effet réel). n=300, seed=9999, référence RunC/F rr135/corr080
(§1.8 `registre_parametres_projet.md`) :

| Variante | Plafond | Profit moyen | Δ vs REF | hit_ceiling | Année1<0 | Évictions moy. |
|---|---|---|---|---|---|---|
| extreme (Q1 exact vs Q4 exact) | 1000$/3000$ | 5 915 946$/5 919 687$ | **0,00%** (0 éviction) | inchangé | inchangé | 0,00 |
| gap2 (écart≥2) | 1000$/3000$ | 5 889 341$/5 893 082$ | -0,45% | inchangé | 27,67% (léger mieux) | 38,76 |
| **any (tout écart favorable)** | 1000$ | **6 389 435$** | **+8,00%** | 2,00%→**0,67%** | 28,00%→27,00% | 292,98 |
| **any** | 3000$ | **6 389 392$** | **+8,00%** | 1,00%→**0,33%** | 28,00%→27,00% | 292,99 |

"extreme" est un **no-op structurel confirmé** (0 éviction sur 300 runs —
exiger Q1/Q4 exact ET exactement 1 conflit ne se produit jamais dans le
moteur bootstrappé). "gap2" est dans le bruit. "any" **domine sur les 4
axes simultanément** aux deux plafonds (solde_neg inchangé à 0,33%,
les 3 autres axes meilleurs).

**Test de sensibilité au classement** (`chantier_correlation_swap_
h1rank_check_2026-08-16.py`, n=300) : rejoue "any" avec le classement
**H1 seul** (délibérément dégradé/instable, cf. alerte Section 1) au lieu
du classement in-sample complet, pour isoler si le gain vient de la
PRÉCISION du classement ou du mécanisme de fond (Section 0, déjà validé
robuste) :

| Classement utilisé | Plafond | Profit moyen | Δ vs REF | hit_ceiling |
|---|---|---|---|---|
| Complet (in-sample) | 1000$ | 6 389 435$ | +8,00% | 0,67% (mieux) |
| H1 seul (dégradé) | 1000$ | 6 285 931$ | **+6,26%** | 2,00% (= REF, pas d'amélioration) |
| Complet (in-sample) | 3000$ | 6 389 392$ | +8,00% | 0,33% (mieux) |
| H1 seul (dégradé) | 3000$ | 6 286 646$ | **+6,20%** | 1,33% (légèrement pire que REF) |

**Interprétation** : le gain de PROFIT persiste largement (+6,2-6,3% sur
les +8,0%, soit ~78% de l'effet) même avec un classement de paires
délibérément instable — ce n'est donc PAS un artefact de data-mining pur
comme le score Force ou ADX/ATR (qui s'effondraient sous ce type de
test). L'essentiel de la valeur vient bien du mécanisme validé en
Section 0 (admettre des signaux bloqués-corrélation, structurellement
très bons, en échange d'une position quelconque). En revanche,
l'amélioration du RISQUE (hit_ceiling) NE PERSISTE PAS avec un
classement dégradé (revient au niveau REF ou légèrement pire) — cette
partie de l'effet dépend bien de la précision du classement, qui elle
n'est pas confirmée stable hors échantillon.

**Confirmation n=600** (`chantier_correlation_swap_n600_confirm_
2026-08-16.py`, classement complet, cascade check 4 axes complet,
848s≈14min) :

| Config | Plafond | Profit moyen | solde_negatif_annee4 | hit_ceiling | Année1<0 |
|---|---|---|---|---|---|
| REF | 1000$ | 5 836 643$ | 0,50% | 1,50% | 30,50% |
| **any** | 1000$ | **6 317 804$ (+8,24%)** | **0,17% (mieux)** | **0,67% (mieux)** | **29,17% (mieux)** |
| REF | 3000$ | 5 847 908$ | 0,33% | 0,67% | 30,50% |
| **any** | 3000$ | **6 318 027$ (+8,05%)** | **0,17% (mieux)** | **0,33% (mieux)** | **29,17% (mieux)** |

**🔴 Verdict : DOMINANCE STRICTE confirmée n=600 sur les 4 axes
simultanément, aux deux plafonds** — sous le standard du projet pour un
"GO" (cf. BBx2 §2.18), c'est un free lunch, pas un arbitrage. C'est
l'effet confirmé le plus large mesuré à ce jour sur ce projet en
proportion (+8,0-8,2% profit, devant la bascule Blueberry +5,2%,
`registre_parametres_projet.md` §7.1), avec une réserve documentée et
quantifiée (pas juste signalée) : ~22% de l'effet profit et la totalité
de l'effet risque dépendent de la précision du classement de paires, qui
n'a pas passé le test de stabilité hors échantillon en Section 1. **PAS
ENCORE ADOPTÉ dans la référence officielle §1.8** — comme pour la
bascule Blueberry (§7 `registre_parametres_projet.md`), nécessiterait une
régénération complète de la cascade avant tout chiffre définitif
(décision utilisateur en attente). Recommandation : candidat le plus
solide actuellement en attente d'adoption, mais présenter le chiffre
comme "+6 à +8% profit selon la fiabilité du classement" plutôt que
"+8%" sec, pour rester honnête sur la part non confirmée hors
échantillon.

### 2.33 Classement de paires — fiabilisation (ÉCHEC) + critère alternatif RR (nouveau meilleur candidat) (08/16)

Suite directe de §2.32 (échange ciblé blocages-corrélation) : deux
objectifs — fiabiliser le classement de paires pour retrouver le
bénéfice risque perdu avec un classement dégradé, et tester un critère
alternatif ne reposant pas sur un historique par paire. Fichiers :
`chantier_pair_ranking_shrinkage_kfold_2026-08-16.py`,
`chantier_correlation_swap_section4_rr_2026-08-16.py`,
`chantier_correlation_swap_section4_n600_confirm_2026-08-16.py` (tous
suivis par git).

**Section 3 — fiabilisation du classement : ÉCHEC, documenté clairement
(pas de conclusion forcée, conformément à la consigne du prompt).**
Estimateur à rétrécissement empirique bayésien (EV de chaque paire
ramenée vers la moyenne globale +0,8934R, poids=n/(n+k), k=20/30) +
validation k-fold temporelle (4 blocs chronologiques de ~157-158
trades, ~11 trades/paire/bloc en moyenne, remplace le split unique
H1/H2 de §2.32) :

| Méthode | Fold0 | Fold1 | Fold2 | Fold3 | Spearman moyen |
|---|---|---|---|---|---|
| Brut | +0,648 | -0,191 | -0,231 | -0,288 | -0,015 |
| Shrinkage k=20 | +0,670 | -0,200 | -0,187 | -0,262 | +0,005 |
| Shrinkage k=30 | +0,670 | -0,209 | -0,187 | -0,218 | +0,014 |

Le shrinkage ne récupère quasiment rien (Spearman moyen reste ~0, bien
en dessous du seuil 0,6 fixé par le prompt, et même en dessous du
0,446 obtenu avec le split unique H1/H2 de §2.32 — un seul fold sur 4
montre une vraie stabilité). **Verdict : le classement par paire n'est
PAS structurellement récupérable à cet effectif** (631 trades / 14
paires ≈ 45 trades/paire en moyenne, ~11/paire par fold — le shrinkage
neutralise le bruit des faibles effectifs mais ne peut pas créer un
signal de qualité de paire qui n'est pas mesurable à cette taille
d'échantillon). Piste classement-de-paires fermée pour l'instant, pas
de nouvelle tentative sans un effectif par paire significativement plus
grand.

**Section 4 — critère alternatif : comparer le RR PLANIFIÉ du trade
(`rr_tp1`, connu au moment du signal) au lieu du rang historique de la
paire.** Mécanisme "any-RR" : au blocage-corrélation avec exactement une
position ouverte conflictuelle, admet le signal bloqué si son RR
planifié est strictement supérieur à celui de la position occupante
(suivi via un tracker `_open_meta_rr` séparé, `acc['open_positions']`
inchangé pour ne rien casser dans `process_trade_mf`). "any-RR-hybrid"
ajoute le quartile de paire (brut, §2.32) comme départage en cas
d'égalité exacte de RR — **testé strictement identique à any-RR à
n=300 aux deux plafonds** (égalités exactes de RR planifié quasi
inexistantes, valeurs continues) : le départage hérité de la Section 3
(cassée) ne pèse donc de facto pas sur le résultat.

n=300 (screening), même référence RunC/F rr135/corr080 :

| Config | Plafond | Profit moyen | Δ vs REF | solde_neg | hit_ceiling | Année1<0 |
|---|---|---|---|---|---|---|
| REF | 1000$ | 5 915 946$ | — | 0,33% | 2,00% | 28,00% |
| **any-RR / any-RR-hybrid** | 1000$ | **6 473 770$** | **+9,43%** | 0,33% | **0,33%** | **25,67%** |
| REF | 3000$ | 5 919 687$ | — | 0,33% | 1,00% | 28,00% |
| **any-RR / any-RR-hybrid** | 3000$ | **6 494 857$** | **+9,71%** | **0,00%** | 0,33% | **25,67%** |

**any-RR dominait déjà "any" (classement de paires, §2.32) sur les 4
axes aux deux plafonds à n=300** — règle du prompt respectée,
confirmation n=600 engagée.

**Confirmation n=600** (848s→840s, cascade check 4 axes complet) :

| Config | Plafond | Profit moyen | solde_negatif_annee4 | hit_ceiling | Année1<0 |
|---|---|---|---|---|---|
| REF | 1000$ | 5 836 643$ | 0,50% | 1,50% | 30,50% |
| **any-RR** | 1000$ | **6 399 549$ (+9,65%)** | **0,17% (mieux)** | **0,50% (mieux)** | **28,17% (mieux)** |
| REF | 3000$ | 5 847 908$ | 0,33% | 0,67% | 30,50% |
| **any-RR** | 3000$ | **6 410 360$ (+9,62%)** | **0,00% (mieux)** | **0,17% (mieux)** | **28,17% (mieux)** |

**🔴 Verdict : DOMINANCE STRICTE confirmée n=600 sur les 4 axes, aux
deux plafonds — meilleur candidat du projet à ce jour, devant "any"
(§2.32, +8,0-8,2%) ET sans sa réserve principale.** any-RR dépasse any
sur CHAQUE axe aux deux plafonds (ex. année1<0 28,17% vs 29,17%,
solde_neg identique ou meilleur, hit_ceiling meilleur), tout en
s'appuyant uniquement sur une information connue au moment du trade
(RR planifié du signal) — **aucune dépendance à un historique de paire
non stable**, contrairement à any qui restait exposé à l'échec de
validation de la Section 3 ci-dessus. Ce n'est donc plus un "+6 à +8%
selon la fiabilité du classement" mais un **+9,6-9,7% confirmé sans
réserve de ce type**. Réserve résiduelle identique à §2.32 (limite de
modélisation : PnL de la position coupée non recalculé, borne HAUTE de
l'effet réel — commune à tout mécanisme de coupe anticipée dans ce
projet, cf. §2.28). **PAS ENCORE ADOPTÉ dans la référence officielle
§1.8** — décision utilisateur d'adoption toujours en attente (même
convention que la bascule Blueberry, nécessite régénération complète de
la cascade), mais **any-RR devrait remplacer any comme candidat proposé
si adoption il y a**.

### 2.34 Sizing modulé par le RR planifié — REJETÉ (08/16)

**Principe testé** : any-RR a prouvé que le RR planifié du signal
(information connue au moment du trade) est exploitable pour le
ROUTAGE (quel signal admettre en cas de blocage-corrélation). Ce
chantier teste s'il peut aussi informer la TAILLE de position — plus le
RR planifié est élevé, plus le risque% est (marginalement) augmenté.

**3 fonctions de scaling testées** (`chantier_rr_sizing_2026-08-16.py`,
suivi par git), toutes bornées à un multiplicateur max **×1,30** (borne
prudente, bas de la fourchette ×1,3-1,5) :
- **(a) linéaire** : ×1,00 à RR=1,35 → ×1,30 à RR=3,0 (plafond de
  construction du payoff trailing).
- **(b) palier** (3 tranches à la main) : RR<1,75→×1,00 ;
  1,75≤RR<2,50→×1,15 ; RR≥2,50→×1,30.
- **(c) quantile** (quartiles de la population actuelle, évite un seuil
  choisi à la main) : Q1(<1,587)→×1,00 ; Q2(<1,889)→×1,10 ;
  Q3(<2,318)→×1,20 ; Q4→×1,30.

**Contrainte dure vérifiée AVANT tout lancement** : risque max par
trade = base_risk×1,30 = 1,90%×1,30=2,47% (funded) ou
1,75%×1,30=2,275% (éval GFT), vs DD journalier le plus strict de la
flotte actuellement utilisée (**4,0%**, Blueberry_Prime2Step/
GFT_2Step_GOAT/FundedNext_StellarLite, `engine_multiformat.FORMATS`) —
marge ≥1,53pt (≥38% relatif), y compris cumulé avec le DD-distance-
sizing V2 déjà en place (qui ne fait que RÉDUIRE le risque, jamais
l'augmenter — aucun risque de compounding vers le haut). Marge
confirmée suffisante, gating respecté avant le run.

**Résultat n=300 (screening), any-RR + bascule Blueberry actifs, 4
plafonds, comparé au COMBINÉ n=600 déjà confirmé (§1.8
`registre_parametres_projet.md`)** :

| Plafond | Variant | Profit | Δ vs COMBINÉ | solde_neg | hit_ceiling | Année1<0 |
|---|---|---|---|---|---|---|
| 960$/1000$ | COMBINÉ (réf., n=600) | 6 752 310$ | — | 0,17% | 0,50-0,67% | 24,33% |
| 960$/1000$ | linear | 6 384-6 440k$ | -4,6 à -5,5% | **1,3-2,7% (pire)** | **3,0-5,7% (pire)** | **26,7% (pire)** |
| 960$/1000$ | palier | 6 241-6 294k$ | -6,8 à -7,6% | **2,0-3,3% (pire)** | **3,3-6,3% (pire)** | **28,3% (pire)** |
| 960$/1000$ | quantile | 6 445-6 516k$ | -3,5 à -4,6% | **1,7-3,3% (pire)** | **3,3-6,0% (pire)** | **27,0-27,3% (pire)** |
| 3000$/5000$ | COMBINÉ (réf., n=600) | 7 080 725$ | — | 0,00% | 0,00% | 13,83% |
| 3000$/5000$ | linear | 6 907 876$ | -2,44% | 0,00% (=) | 0,00% (=) | 12,67% (mieux) |
| 3000$/5000$ | palier | 6 815 255$ | -3,75% | 0,00% (=) | 0,00% (=) | 13,33% (mieux) |
| 3000$/5000$ | quantile | 7 039 869$ | -0,57% | 0,00% (=) | 0,00% (=) | 13,67% (≈) |

**Verdict : REJETÉ, aucune variante ne domine ni n'égale le COMBINÉ sur
les 4 axes à aucun plafond — gating n=600 du prompt non déclenché (pas
de lancement de confirmation).** À 960$/1000$ : les 3 variantes sont
PIRES sur les 4 axes simultanément (profit -3,5 à -7,6%, solde_neg et
hit_ceiling nettement dégradés, année1<0 pire) — un résultat sans
ambiguïté. À 3000$/5000$ : profit toujours pire (-0,6 à -3,75%),
année1<0 légèrement meilleur, solde_neg/hit_ceiling inchangés — pas une
dominance, un arbitrage négatif net.

**Mécanisme identifié (pas juste constaté)** : le RR planifié n'est PAS
corrélé à l'EV réalisée dans cette population — corrélation de Pearson
rr_tp1/r_trailing = **0,006** (quasi nulle), et corrélation rr_tp1/
winrate = **-0,108** (légèrement NÉGATIVE, RR élevé → winrate plus
faible, cohérent avec un objectif de prix plus loin à atteindre). EV
moyen par tranche de RR NON monotone : [1,35-1,75]→+1,042R,
[1,75-2,50]→+0,723R, [2,50-3,0]→+0,953R — pas d'ordre croissant. Le
succès d'any-RR (§2.33) vient du MÉCANISME DE SÉLECTION au moment d'un
conflit (admettre un signal plutôt qu'un autre, tous deux déjà filtrés
RR≥1,35), pas d'un pouvoir prédictif intrinsèque du RR sur l'EV — sizer
dessus ajoute donc de la variance (risque plus grand sur des trades pas
spécialement meilleurs) sans edge compensatoire, cohérent avec la
dégradation mesurée. **Chantier fermé, ne pas retester le RR comme
signal de sizing sans une nouvelle piste structurelle (ex. un score
composite RR+ADX/ATR, ou une transformation non-linéaire justifiée par
un mécanisme économique, pas juste "RR élevé = plus confiant").**

### 2.35 Sizing/routage basé sur rr_tp2 (queue haute) — CONFIRMÉ n=600, statut différencié par plafond (08/16)

**Correction de méthode vs §2.34** : le test précédent caractérisait
`rr_tp1` (plafonné structurellement à 3,0), pas `rr_tp2` — pas la bonne
variable pour tester un effet de queue. Ce chantier corrige le tir.

**Étape 0 — anti-lookahead (bloquant, vérifié avant tout calcul)** :
`tp2_init` est extrait de la page du signal Lutessia **au même moment**
que `prix_entree`/`stop_loss_init`/`tp1_init` (`scraper.py:240-268`,
fonction `fetch_signal_detail`, même parsing `_parse_price`) — PAS
déterminé après coup via la confirmation de continuation H1
(`payoff_bucket`, qui ne détermine que le RÉSULTAT réalisé utilisé,
`r_trailing` vs `r_realiste`, une question séparée). **Aucun
lookahead — piste valide.**

**Étape 1 — rr_tp2 recalculé depuis les niveaux de prix bruts**
(`(tp2_init-prix_entree).abs()/(prix_entree-stop_loss_init).abs()`) :
écart max vs colonne existante = 3,6e-15 (bruit flottant, confirmé
identique). **rr_tp2 n'est PAS plafonné comme rr_tp1** : distribution
1,74 à 30,4 (médiane 5,08, P75=6,78, P90=8,82) — n avec rr_tp2≥3/4/5/6 =
570/435/325/217 (échantillons larges, contrairement à rr_tp1).

**Étape 2 — caractérisation EV par tranche** : tranches non-
chevauchantes montrent une tendance monotone croissante
((1,35-3]→+0,50R … (8,100]→+1,69R) — la tranche **rr_tp2>8 (n=96)** est
la seule dont l'IC95% bootstrap (5000 itérations) **exclut l'EV
globale** (+0,89R) : IC=[+0,91,+2,55]. Stress-test de stabilité (split
H1/H2 + 4 blocs k-fold, gratuit avant d'engager le calcul coûteux) :
**direction constante dans TOUTES les sous-périodes** (H1 : queue à
+0,31R vs baseline H1 +0,11R ; H2 : queue à +3,25R vs baseline H2
+1,68R ; les 4 blocs k-fold montrent tous EV(queue)>EV(bloc)) — contraste
net avec le classement de paires (§2.32/2.33) dont la direction
s'inversait en H2. Corrélation Pearson rr_tp2/r_trailing=0,123 (faible
mais non nulle, très supérieure au 0,006 de rr_tp1 §2.34). Seuil
retenu : **rr_tp2>8**.

**Contrainte dure (marge ≥30% sous DD journalier strict 4,0%, côté
funded 1,90%)** — vérifiée pour chaque multiplicateur avant lancement,
affichée explicitement au runtime (`chantier_rrtp2_sizing_2026-08-
16.py`) : ×1,2/×1,3 conformes (43,0%/38,3%) ; ×1,5/×1,6/×1,75/×1,9 **NE
respectent PAS la marge ≥30%** (28,8%/24,0%/16,9%/9,8%) — testés quand
même sur demande explicite utilisateur, marge affichée à chaque run,
pas cachée. Aucun ne dépasse le DD journalier lui-même (contrairement à
×3,0 en §2.34, qui aurait été un dépassement direct).

**Deux variantes testées** : **A** = routage any-RR inchangé (rr_tp1),
sizing seul module par rr_tp2>8. **B** = routage ET sizing tous deux
sur rr_tp2>8 (remplace rr_tp1 comme critère de routage flotte, la
population d'entrée RR≥1,35 reste inchangée). n=300 screening (1000$/
3000$, 6 multiplicateurs pour A ; 3 pour B) puis n=600 confirmation du
meilleur candidat (B ×1,6, gagnant net aux deux variantes) sur les 4
plafonds :

| Plafond | Profit (B×1,6, n=600) | Δ vs COMBINÉ | solde_neg | hit_ceiling | Année1<0 |
|---|---|---|---|---|---|
| 960$ | 7 811 075$ | **+15,68%** | 0,17% (=) | **1,67% (vs 0,67%, pire)** | 24,50% (≈) |
| 1000$ | 7 812 088$ | **+15,70%** | 0,17% (=) | **1,00% (vs 0,50%, pire)** | 24,50% (≈) |
| 3000$ | 8 206 650$ | **+15,90%** | 0,00% (=) | 0,00% (=) | **13,17% (mieux)** |
| 5000$ | 8 206 650$ | **+15,90%** | 0,00% (=) | 0,00% (=) | **13,17% (mieux)** |

**🔴 Correction n=300→n=600** : le gain apparent sur année1<0 à
960$/1000$ observé en screening (22-24%) NE SE CONFIRME PAS à n=600
(24,50%, essentiellement identique au COMBINÉ 24,33%) — même leçon de
bruit d'échantillonnage déjà rencontrée deux fois dans ce chantier
(plancher Run E, calibration seuil Blueberry).

**Verdict différencié, PAS un statut unique** :
- **3000$/5000$ : DOMINANCE STRICTE confirmée n=600** — +15,9% de
  profit par-dessus le COMBINÉ déjà lui-même très supérieur à la
  référence pure, tous les autres axes égaux ou meilleurs. **Candidat
  prêt sans réserve à ces plafonds.**
- **960$/1000$ : un arbitrage, PAS une dominance** — +15,7% de profit
  contre un hit_ceiling qui DOUBLE (0,5-0,67%→1,0-1,67%) et un
  année1<0 inchangé (pas de compensation). Décision selon tolérance au
  risque personnelle, pas un candidat automatique à ces plafonds.

**PAS ENCORE ADOPTÉ dans la référence officielle §1.8** — décision
utilisateur en attente, même convention que les leviers précédents.
Fichier : `chantier_rrtp2_sizing_2026-08-16.py` (suivi par git).

**✅ Vérification finale post-adoption-proposée (08/16,
`chantier_rrtp2_stability_verification_2026-08-16.py`, suivi par git)**
— 3 points demandés avant adoption définitive, tous confirmés :
1. **Anti-lookahead** : `scraper.py:239-246` (`tp_divs =
   detail_soup.select("div.sy-tp")`, `tp1_init`/`tp2_init` =
   `tp_divs[0]`/`tp_divs[1]`) — tp2 extrait du même bloc DOM, même
   fonction (`fetch_signal_detail`), même instant que `prix_entree`/
   `stop_loss_init`/`tp1_init`. Aucune dérivation du prix atteint après
   coup.
2. **Stabilité temporelle chiffrée** : Pearson(rr_tp2, r_trailing) par
   fold — H1=+0,047, H2=+0,225, bloc0=+0,045, bloc1=+0,064,
   bloc2=+0,220, bloc3=+0,219 (moyenne 4 blocs=+0,137). EV(queue>8) >
   EV(reste) dans **6/6 sous-périodes indépendantes** (2 moitiés + 4
   blocs), y compris bloc0 où l'environnement global est négatif
   (-0,096R) mais où la queue reste relativement meilleure (+0,032R vs
   -0,120R). **STABLE**, contraste net avec le classement de paires
   (§1), dont la direction s'inversait en H2.
3. **Table complète** (n=631 couverts intégralement, tranches non-
   chevauchantes) : croissance monotone (1,73-3]→+0,50R … (8-30,4]→
   +1,69R — **seule la tranche >8 (n=96) sort de l'IC95% de l'EV
   globale**, confirmant la coupure exacte déjà retenue.

**Verdict : les 3 points confirment — §2.35 adopté sans réserve**,
dominance stricte à 3000$/5000$ et arbitrage documenté à 960$/1000$
inchangés par rapport à la proposition initiale.

**✅ Dernière vérification (08/16) : chevauchement de population et
mécanisme du rebond de winrate** — deux derniers points avant adoption
définitive, tous deux propres :
1. **Chevauchement** : tail rr_tp2>8 (n=96) vs bloqués-corrélation
   (Section 0, mécanisme réellement adopté par any-RR) = **10,4%**
   (proche du taux de base 7,0%) — axe très majoritairement
   indépendant. Vs quartile 1 de paires (classement REJETÉ pour
   instabilité, §1/§3, non adopté) = 35,4% — dans la zone signalée,
   mais sans conséquence puisque le mécanisme source n'est pas dans la
   cascade officielle.
2. **Rebond de winrate (35,3%→44,8%)** : aucun confondant trouvé
   (composition paires diversifiée, asset_class/timeframe/score_force
   identiques entre tranches, rebond présent aussi bien en JPY
   qu'en non-JPY). Mécanisme identifié : cible TP2 réellement plus
   lointaine (corrélation rr_tp2/distance_TP2%=+0,45), PAS un stop-loss
   artificiellement resserré (distance_SL% quasi non corrélée au
   winrate, -0,06). Effet large-spectre, pas un artefact de
   construction du ratio.

**Aucune part de gain à requalifier comme redondante — §2.35 reste
confirmé adopté sans réserve.**

**✅ ADOPTÉ formellement (décision utilisateur, 2026-08-23)** — re-testé
sur données r_trailing corrigées (fix `df261dc`, backfill complet bloc1/
bloc2), avec la même mésaventure de cap Blueberry que §1.8
(`registre_parametres_projet.md` §1.8) : un premier passage
(`chantier_5leviers_revalidation_2026-08-23.py`, n=600) tournait sur un
moteur (`chantier_rrtp2_sizing_2026-08-16.py`) antérieur au correctif du
cap Blueberry Instant 1,5%/trade (08/17-18) et jamais repatché — cap
absent, apport de §2.35 gonflé artificiellement à +25,9%/+26,2%
(population complète) et +37,0%/+37,3% (bloc1+2 seul).

**Chiffres retenus après correction du cap** (`chantier_5leviers_
revalidation_fixed_2026-08-23.py`, **n=300 screening — pas encore
reconfirmé à n=600**, cap actif) :
- Population complète : **+21,8% / +21,9%** (1000$/3000$) — toujours net
  positif et substantiel, juste plus modeste que le premier passage.
- Bloc1+2 seul (n=280) : **+29,97% / +30,09%** — reste FORT (contrairement
  à §1.8, dont l'effet sur ce même sous-échantillon s'effondre à quasi
  neutre). Cohérent avec le mécanisme : §2.35 cible directement la queue
  rr_tp2>8, indépendamment du cap Blueberry (qui concerne le risque par
  trade sur le format Instant, pas le sizing rr_tp2 lui-même) — l'essentiel
  de sa robustesse sur bloc1+2 vient de la correction r_trailing, pas
  d'un artefact du cap manquant.

**Direction d'adoption inchangée** (toujours dominance stricte à 3000$/
5000$, arbitrage à 960$/1000$, cf. table ci-dessus) — seule l'AMPLEUR
était surestimée par le bug de cap, corrigée ici. **Reconfirmation à
n=600 (niveau verdict) avec le cap actif reste à faire** avant de citer
ces chiffres au même niveau de confiance que le reste de cette section.

Logs : `log_5leviers_A_refixed_n300_2026-08-23.txt`, scripts
`chantier_5leviers_revalidation_2026-08-23.py` (buggé, cap absent) et
`chantier_5leviers_revalidation_fixed_2026-08-23.py` (corrigé).

### 2.36 Sizing continu/paliers étendus sur rr_tp2 — REJETÉ, portée précise (08/17)

Suite à §2.35 (seuil simple rr_tp2≥8→×1,6, adopté) : test de 3 candidats de
sizing gradué sur une plage plus large de la distribution, add-on isolé sur
la référence de travail (§1.8+§2.35), n=300, 4 plafonds. Fichiers :
`chantier_A_rr_sizing_diagnostic_2026-08-17.py` (diagnostic),
`chantier_A_rr_sizing_2026-08-17.py` (screening, suivi par git).

**Diagnostic (Étape 0)** : déciles rr_tp2 non monotones sur l'ensemble de
la plage (Spearman global +0,024, quasi nul) — signal fiable concentré
dans les 3 derniers déciles (rr_tp2 >~6,46 : EV +1,198R/+1,350R/+1,973R,
croissant) ; déciles 1-7 sans tendance (+0,266R à +0,945R).

**3 candidats testés, tous plafonnés à ×1,6** (marge 24,0%, déjà acceptée
en §2.35, aucune nouvelle violation) :

| Plafond | REF (§2.35) | A1 palier 2 niv. (1,3-1,6 sur [6,5;8[/[8;+inf[) | A2 rampe continue (1,0→1,6 sur [6;15]) | A3 paliers 10 déciles (1,0→1,6) |
|---|---|---|---|---|
| 960$/1000$ | 7 909 560$/7 911 585$ | -6,19%/-5,68% | -6,28%/-5,99% | -24,82%/-23,55% |
| 3000$/5000$ | 8 334 629$ | -3,63% | -6,31% | -20,28% |

Autres axes (solde_neg/hit_ceiling/année1<0) égaux ou pires pour les 3
candidats, aucune compensation. **Verdict : REJETÉS, aucun ne bat REF à
aucun plafond.** Même A1 (ciblant précisément le "pré-tail" prometteur au
diagnostic brut par décile) perd -3,6 à -6,2% — la promesse apparente du
diagnostic par décile ne s'est pas traduite en gain simulé, confirmant que
le seuil simple >8 capture correctement le seul segment stable. Stress-test
H1/H2+k-fold non lancé (aucun candidat n'a passé le screening).

**🔴 Portée EXACTE du rejet, à ne pas généraliser** (vérifié par citation
de code, `chantier_A_rr_sizing_2026-08-17.py`) : les 3 candidats
n'appliquent JAMAIS de multiplicateur <1,0× — `make_size_func_step2`
(:109-115, `return 1.0` sous le seuil bas) ; `make_size_func_ramp`
(:119-126, `1.0 + (max_mult-1.0)*frac` avec frac∈[0,1], plancher exact
1,0) ; `make_size_func_decile_full` (:130-132,
`mults = np.linspace(1.0, max_mult, 10)`, le décile le plus bas reçoit
exactement 1,0×). **Ce qui est rejeté = la famille "boost gradué ≥1,0×
étendu ou lissé sur plus de la distribution". PAS TESTÉ = sizing
asymétrique avec réduction (<1,0×) sur les segments faibles** — chantier
distinct en cours (Section A-bis, downsizing temporel/conditionnel).

### 2.37 GFT Instant en comptes extra parallèles — REJETÉ, portée précise (08/17)

Add-on isolé sur la référence de travail (§1.8+§2.35) : comptes GFT
"extra" (croissance, `process_extra_account`) basculés du format classique
vers `GFT_InstantGOAT` au lieu du classique, n=300, 4 plafonds. Fichier :
`chantier_B_gft_instant_parallel_2026-08-17.py` (suivi par git).

| Plafond | REF | B (GFT Instant parallèle) | Δ profit |
|---|---|---|---|
| 960$ | 7 909 560$ | 7 674 995$ | -2,97% |
| 1000$ | 7 911 585$ | 7 676 320$ | -2,98% |
| 3000$/5000$ | 8 334 629$ | 8 097 701$ | -2,84% |

solde_neg/hit_ceiling inchangés ; année1<0 légèrement amélioré (+0,6 à
+1,0pt, insuffisant). Mécanisme confirmé : `gft_breaks_moy` triple
(42-44→118-124/4ans), porté à 91-92% par `gft_instant_breaks_moy`
(108-113) — DD 6% trailing structurellement trop serré, confirmé en
contexte flotte réelle (cohérent avec §6.2/§6.3, compte isolé).

**🔴 Portée EXACTE du rejet, à ne pas généraliser** : la stratégie
appliquée aux comptes Instant est la stratégie CLASSIQUE rejouée à
l'identique (même population RR≥1,35, même routage any-RR/rr_tp2, même
risque de base) sur un format dont le DD (6% trailing) est structurellement
différent du format classique (10% statique). **Ce qui est rejeté =
"stratégie classique inchangée sur comptes Instant". PAS TESTÉ = une
stratégie spécifiquement adaptée à la contrainte 6% trailing** — chantier
distinct en cours (Section B, diagnostic du mode de casse + candidats
adaptés).

### 2.38 Recherche de variable de segmentation alternative à RR — AUCUNE variable exploitable trouvée (08/17)

Suite à §2.36 (aucun segment RR négatif même à granularité fine) : recherche
d'une variable DIFFÉRENTE de RR pour du sizing/segmentation EV.

**Étape 0 — inventaire** : `score_force` EXCLU (déjà testé exactement comme
base de sizing, §2.1 mécanisme b, "Force non exploitable"). ATR ratio EXCLU
(§2.6 "quasi neutre", déjà testé comme sizing, malgré moteur ancien jamais
recalculé). Retenues (jamais testées comme base de sizing EV, seulement
comme filtre ou confondant) : ADX(14) à l'entrée (couverture ~52%), session
horaire UTC (couverture 100%), asset_class (100%), distance_SL% (100%).
distance_TP2% écartée explicitement (corrélée +0,45 à rr_tp2, trop proche
de "RR sous une autre forme").

**Étape 2-3 — EV par segment + garde-fou out-of-sample**
(`chantier_segmentation_variables_2026-08-17.py`) :
- Session horaire (3 blocs et 6 tranches) : aucun segment sous l'IC95%.
- **asset_class : inutilisable — une seule catégorie dans toute la
  population** ("FX/Indices", aucune variance).
- ADX(14) : quintiles non-monotones (1,34R à 2,29R), Pearson=+0,037 quasi
  nul, aucun signal (confirme §2.13/§2.31).
- **distance_SL% ((entrée-SL)/entrée×100) : seul candidat à passer le
  garde-fou.** Segment >0,235% (quintiles 4-5, n=252, 40% de la
  population) SOUS la moyenne locale dans **6/6 sous-périodes** (H1/H2 +
  4 blocs k-fold) — aussi stable que le tail rr_tp2 déjà adopté. Quasi
  indépendant de rr_tp2 (Pearson=-0,15, chevauchement 16/252 avec le
  segment déjà boosté).

**Étape 4 — chiffrage flotte** (`chantier_segmentation_fleet_test_2026-08-17.py`,
n=300, 4 plafonds, downsizing ×0,5/×0,8 sur le segment distance_SL%>0,235,
boost rr_tp2≥8→×1,6 maintenu) : **REJETÉ à tous les plafonds** — coût de
profit -2,7% à -3,7%, non compensé par les gains modestes sur les axes de
risque (réels à 960$/1000$, marginaux à 3000$/5000$ où REF est déjà proche
de l'optimum).

**Conclusion : aucune variable actuellement capturée dans le pipeline ne
porte un signal de segmentation EV exploitable pour du sizing**, même
quand elle est statistiquement stable out-of-sample (distance_SL%
prouve que "stable" ≠ "économiquement exploitable" — le segment reste EV
positive, sans surreprésentation dans les pertes, §2.38bis). Capturer une
nouvelle donnée à la source serait nécessaire pour rouvrir cette
direction. Fermé.

### 2.38bis Downsizing temporel/conditionnel (Section A-bis) — hypothèse causale RÉFUTÉE, rien construit (08/17)

Piste distincte : downsizing TEMPORAIRE (fenêtre année1/seuil réserve,
analogue V2) sur le(s) segment(s) faible(s) en EV, plutôt que permanent.
Rationnel à vérifier avant construction : les segments faibles
contribuent-ils de façon disproportionnée aux PERTES (fréquence+magnitude),
pas juste à un profit moyen plus bas ?

**Résultat (même diagnostic que §2.36)** : perte moyenne=perte
max=-1,000R pour TOUS les déciles (sortie en stop plein, aucune variation
de magnitude possible par construction). Ratio contribution-aux-pertes/
poids-population entre 0,85 et 1,14 pour tous les déciles — **aucune
surreprésentation notable** (seuil 1,2 jamais atteint).

**L'hypothèse ne tient pas empiriquement — mécanisme NON construit**,
conformément à la consigne explicite ("si aucune surreprésentation, dis-le
avant de perdre du temps à construire"). Fermé, sauf nouvelle piste de
justification causale.

### 2.39 Doublon même paire (2 signaux simultanés) — FERMÉ, statu quo optimal (08/17)

Contexte : observation terrain (2 positions GBP/JPY simultanées, signal 2
validé pendant signal 1 actif). Étape 0 vérifiée par citation de code AVANT
toute construction de candidat, comme demandé (`chantier_positioncap_
blocking_diagnostic_2026-08-17.py`, suivi par git) :

- **Frictions (spread/commission)** : `pnl = trade["outcome_r"] *
  risk_amount` (`engine_multiformat.py:331`) est purement proportionnel à
  la taille — **aucun terme de spread/commission en $ dans le moteur**
  (`feasible_risk_pct`, `scaling_simulation.py:121-147`, ne gère que
  l'arrondi de lot/marge).
- **Risque d'échec de parsing/exécution** : identifié (`app.py` logge des
  échecs réels en production via `failed_emails.log`) mais **non modélisé
  dans le moteur de simulation** — angle mort réel mais UNIFORME sur toute
  la population, pas spécifique au cas doublon.
- **Blocage plafond spécifique au doublon même paire** : taux global de
  blocage plafond = 1,91% (n=300, pile actuelle) ; part causée par un
  doublon même ticker = 10% des blocages, soit **0,19% de tous les trades
  offerts**.

**Verdict : ARRÊT à l'Étape 0** — les 3 composantes sont nulles/
proportionnelles, non modélisées mais uniformes, ou négligeables (0,19%).
Statu quo (2 trades séparés) = optimal théorique. Aucun candidat construit.

**Condition de réouverture explicite** : si le risque d'échec de parsing/
exécution est un jour quantifié et s'avère non négligeable — actuellement
un angle mort connu mais non chiffré, pas un risque écarté par la mesure.

### 2.40 Plafond de positions (3→6) × risque par trade réduit — REJETÉ, effet INVERSE de l'hypothèse (08/17)

Hypothèse testée : répartir le même risque agrégé pire-cas sur plus de
positions plus petites réduirait la variance (hit_ceiling/solde_neg/
année1<0) sans changer l'EV. n=300, 4 plafonds, risque agrégé pire-cas
maintenu ~constant (3,75-3,76%), `chantier_sectionB_poscap_risk_
2026-08-17.py` (suivi par git) :

| Config | Δ profit (tous plafonds) | Δ année1<0 |
|---|---|---|
| V1 (4 positions × 0,94%) | -17,7% à -18,0% | pire (+1,0 à +1,3pt) |
| V2 (5 positions × 0,75%) | -32,7% à -33,1% | pire (+3,3pt) |
| V3 (6 positions × 0,625%) | -44,2% à -44,9% | pire (+3,7 à +5,7pt) |

solde_neg/hit_ceiling s'améliorent marginalement (REF déjà proche de 0%,
peu de marge pour un gain visible).

**Raison** : réduire le risque par trade ralentit la progression vers
l'objectif de challenge (% fixe du palier), retardant le financement de la
flotte — effet déjà identifié comme dominant dans ce projet (vitesse de
financement), qui écrase tout bénéfice de diversification attendu.
Composition des slots au-delà de l'ancien plafond 3 mesurée séparément :
24,4% doublons même paire, 75,6% paires nouvelles.

**Verdict : REJETÉ sans ambiguïté, les 3 variantes, tous plafonds. Fermé.**

**Condition de réouverture** : aucune identifiée à ce jour — effet inverse
net et monotone (V1<V2<V3 en dégradation), pas un cas limite ou une
question de calibration.

### 2.41 Piste A (BBx2, 2 comptes Blueberry) — statut différencié par plafond, réouverture d'un ancien rejet (08/17)

Ancienne piste (pré-08/12, ancien §2.15, sous une pile de paramètres
antérieure au rebuild RR≥1,35/corr0,80 et à §1.8+§2.35) : confirmée à
3000$, rejetée à 1000$ à l'époque. Re-testée à l'identique (2e compte day0
SANS scaling de risque) sous la pile actuelle, n=300 (4 plafonds) puis
stress-test H1/H2+4 blocs k-fold puis n=600+cascade (aucune inversion sur
les 3 tests). Fichiers : `chantier_pisteAB_bbx2_bbgft_2026-08-17.py`
(screening), `chantier_stresstest_pisteAB_2026-08-17.py` (stress-test),
`chantier_n600_pisteAB_2026-08-17.py` (confirmation, tous suivis par git).

| Plafond | Statut |
|---|---|
| **5000$** | **Dominance stricte confirmée n=600.** Profit 8 487 070$ vs REF 8 206 650$ (**+3,42%**), solde_neg=0%(=), hit_ceiling=0%(=), année1<0 10,00% vs 13,17% (**-3,17pt**). |
| 3000$ | PAS dominant en screening n=300 (hit_ceiling 0%→12,67%) — verdict CHANGÉ vs l'ancienne mesure pré-08/12, qui ne voyait pas cet effet. Jamais envoyé en confirmation n=600 à ce plafond. |
| 960$/1000$ | Rejeté (hit_ceiling explose, comme à l'ancienne mesure). |

**✅ 5000$ : GO technique** — PAS ENCORE intégré à la référence officielle
§1.8, décision d'adoption séparée en attente (même convention que les
leviers précédents).

**Condition de réouverture pour 3000$** : lancer la confirmation n=600 à ce
plafond précis si 3000$ redevient le plafond personnel pertinent (le
screening n=300 seul n'est pas suffisant pour trancher, cf. §2.35 où
l'écart n=300→n=600 s'est déjà avéré significatif).

### 2.42 Piste B (BB+GFT jour0, bootstrap parallèle) — statut différencié par plafond, réouverture d'un ancien rejet (08/17)

Ancienne piste (pré-08/12, ancien §2.6/§2.41 sous la numérotation
antérieure, pile de paramètres antérieure au rebuild RR≥1,35/corr0,80 et à
§1.8+§2.35) : arbitrage à 3000$, rejetée à 1000$ à l'époque. Re-testée à
l'identique sous la pile actuelle, même protocole que §2.41 (n=300 → 
stress-test H1/H2+4 blocs k-fold → n=600+cascade, aucune inversion).
Fichiers : identiques à §2.41.

| Plafond | Statut |
|---|---|
| **5000$** | **Dominance stricte confirmée n=600.** Profit 8 324 100$ vs REF 8 206 650$ (**+1,43%**), solde_neg=0%(=), hit_ceiling=0%(=), année1<0 10,17% vs 13,17% (**-3,00pt**). |
| 3000$ | **Arbitrage chiffré, PAS de verdict tranché.** +113 934$ de profit (+1,39%) contre hit_ceiling 0%→3,50% (+21 runs/600) et année1<0 13,17%→10,17% (-18 runs/600, amélioré malgré le coût hit_ceiling). |
| 960$/1000$ | Rejeté. |

**✅ 5000$ : GO technique** — PAS ENCORE intégré à la référence officielle
§1.8, décision d'adoption séparée en attente.

**🟡 3000$ : en attente de décision utilisateur explicite** sur l'arbitrage
(+113 934$ vs +21 runs/600 touchant le plafond) — à mettre à jour dans ce
registre une fois la décision prise, pas un rejet ni une adoption par
défaut.

### 2.43 Re-tests de Piste C (fonds d'urgence) et Piste D (contrarian) sous la pile actuelle (08/17)

Suite directe de §2.41/§2.42 — même exercice de réouverture appliqué à 2
autres anciennes pistes pré-08/12, sous la pile actuelle (RR≥1,35/corr0,80,
risque éval 1,25%/funded 1,90%, §1.8+§2.35 actifs).

**Piste C (fonds d'urgence 10%/7j/N2)** — ancien §2.39 (numérotation
antérieure) : rejetée à 1000$, candidat n=300 seul à 3000$ (jamais
confirmé n=600) à l'époque. Re-testée à l'identique, n=300, 4 plafonds
(`chantier_pisteC_fonds_urgence_2026-08-17.py`, suivi par git) :

| Plafond | Δ profit | Δ hit_ceiling |
|---|---|---|
| 960$/1000$ | -0,22% | ÷2 (1,33%→0,67% à 1000$) |
| 3000$/5000$ | -0,28% | 0%(=, REF déjà optimal — rien à gagner, contrairement à l'ancienne mesure) |

**Verdict : trop faible pour prioriser, PAS un rejet définitif.** N=600
jamais lancé. Disponible sur demande séparée si l'utilisateur le souhaite.

**Piste D (contrarian RR 0,75-1,25)** — ancien §2.47 (numérotation
antérieure) : marchait aux deux plafonds testés à l'époque (+1,80%/+2,09%
profit), marquée "candidat prioritaire n=600+cascade", jamais reprise
depuis. Reconstruite par portage sous la pile actuelle, population
contrarian vérifiée identique (n=311 trades, 0,75≤rr_tp1<1,25),
`chantier_pisteD_contrarian_2026-08-17.py` (suivi par git) :

| Plafond | Δ profit | Δ année1<0 |
|---|---|---|
| 960$/1000$ | **-15,9% à -16,4% (effondrement)** — inversion complète vs ancien +1,80% sous l'ancienne pile | -5,0pt (seul axe positif) |
| 3000$/5000$ | +0,43% (dominance légère, magnitude réduite vs ancien +2,09%) | -0,67pt |

**Verdict : rejeté net à 960$/1000$ ; candidat faible mais pas prioritaire
à 3000$/5000$.** N=600 jamais lancé. Disponible sur demande séparée.

**🔴 Note de méthode à consigner explicitement** : ces deux pistes avaient
été testées et jugées sous une pile de paramètres antérieure (avant le
rebuild RR≥1,35/corr0,80 du 08/12, avant §1.8+§2.35). Le re-test illustre
directement le principe #1 du projet — **un rejet (ou une confirmation)
n'est valable que sous la config exacte dans laquelle il a été prononcé,
jamais à généraliser sans re-test.** Cohérent avec l'inversion déjà
observée en §2.41 (BBx2@3000$) et le déplacement de verdict en §2.42
(Piste C).

### 2.44 Piste B (BB+GFT jour0) — ouverture GFT différée (T>0 au lieu de jour0), résultat PRÉLIMINAIRE 2-4 mois (08/17)

Suite de §2.42 — question posée : le mécanisme BB+GFT jour0 est-il
structurellement lié à T=0, ou peut-il être simulé comme une ouverture
GFT différée à un instant T ultérieur (négociation en cours pour faire
passer le plafond personnel de 3000$ à 5000$) ?

**Étape 0 — lecture de code, pas de simulation** : NON structurellement
lié à T=0. `acc["active"]` est un booléen activable à n'importe quel
instant via `handle_cost_hybrid()` (respecte le plafond), pas un flag figé
à l'initialisation. Précédent trouvé : `etape_r_piste_a_delayed_start_
2026-08-10.py` implémentait déjà un trigger différé (jours de survie ou
seuil de réserve) sous l'ANCIENNE pile (pré-08/12) — jamais porté sous la
pile actuelle, jamais testé avec un délai en mois.

**Portage sous la pile actuelle** (`chantier_pisteB_delayed_start_
2026-08-17.py`, suivi par git) : GFT reste un compte normal (inactif)
jusqu'à T=X mois puis s'ouvre via `handle_cost_hybrid` (comme
`open_group()`, PAS un coût jour0 inconditionnel) ; no-op si le trigger
normal de croissance (réserve≥25000$) a déjà ouvert GFT avant T. n=300,
plafonds 3000$/5000$ (bb_threshold=0, régime déjà adopté à ces plafonds) :

| Config | Profit moyen | Δ vs REF | Hit_ceiling@3000$ | Hit_ceiling@5000$ | Année1<0 |
|---|---|---|---|---|---|
| REF (sans GFT parallèle) | 8 334 629$ | — | 0,00% | 0,00% | 11,67% |
| Jour0 (baseline §2.42) | 8 455 883$/8 459 335$ | **+1,45%/+1,50%** | 2,67% | 0,00% | 9,00% (-2,67pt) |
| Délai 2 mois | 8 363 019$ (identique aux 2 plafonds) | +0,34% | 0,00%(=) | 0,00%(=) | 10,67% (-1,00pt) |
| Délai 4 mois | 8 340 794$ (identique aux 2 plafonds) | +0,07% (quasi nul) | 0,00%(=) | 0,00%(=) | 11,00% (-0,67pt) |

**Constat** : le bénéfice de BB+GFT n'est pas linéaire dans le temps — il
est concentré dans les tout premiers jours/semaines (mécanisme = tête de
pont de trésorerie AVANT le déblocage de la flotte). À 2 mois, il ne reste
plus que ~23% du gain de profit du jour0 ; à 4 mois, ~5% seulement
(quasiment retombé à zéro). Le coût en hit_ceiling à 3000$ (2,67% pour
jour0) disparaît en revanche complètement dès 2 mois de délai.

**Statut : PRÉLIMINAIRE, n=300 screening seul (pas de stress-test H1/H2+
k-fold, pas de n=600), granularité mensuelle jugée trop grossière pour la
vraie fenêtre de décision utilisateur (négociation financeur 1-3
semaines, pas 2-4 mois) — chantier complémentaire à granularité semaine
en cours (résultat à consigner séparément une fois obtenu). Ce résultat
2-4 mois reste correct et exploitable tel quel (ne PAS le re-mesurer),
juste insuffisant seul pour trancher la décision réelle.**

**Condition de réouverture / suite** : granularité fine 1-4 semaines
(même méthode, même fichier, paramètre `gft_delay_days`) — voir §2.44bis
ci-dessous (résultat obtenu le même jour).

### 2.44bis Piste B (BB+GFT jour0) — ouverture différée, granularité SEMAINE (fenêtre de décision réelle) (08/17)

Suite immédiate de §2.44 : la fenêtre de décision réelle utilisateur est
de 1 à 3 semaines (négociation en cours avec le financeur pour passer le
plafond personnel de 3000$ à 5000$), pas 2-4 mois — la granularité
mensuelle était trop grossière pour informer cette décision. Même
mécanisme, même fichier (`chantier_pisteB_delayed_start_2026-08-17.py`,
paramètre `gft_delay_days` au lieu de `gft_delay_months`, précision
exacte en jours), n=300, plafonds 3000$/5000$ :

| Config | Profit moyen | Δ vs REF (8 334 629$) | Hit_ceiling@3000$ | Hit_ceiling@5000$ | Année1<0 |
|---|---|---|---|---|---|
| Jour0 (rappel §2.42/§2.44) | 8 455 883$/8 459 335$ | +1,45%/+1,50% | 2,67% | 0,00% | 9,00% (-2,67pt) |
| **Délai 1 semaine** | 8 432 150$/8 432 080$ | **+1,17%** | **0,33%** | 0,00%(=) | 9,33% (-2,34pt) |
| **Délai 2 semaines** | 8 407 338$/8 407 268$ | **+0,87%** | 0,33% | 0,00%(=) | 9,33% (-2,34pt) |
| **Délai 3 semaines** | 8 393 273$/8 393 259$ | **+0,70%** | 0,33% | 0,00%(=) | 10,00% (-1,67pt) |
| **Délai 4 semaines** | 8 390 855$ (identique aux 2 plafonds) | **+0,67%** | 0,00%(=) | 0,00%(=) | 10,00% (-1,67pt) |
| *(rappel §2.44)* Délai 2 mois | 8 363 019$ | +0,34% | 0,00%(=) | 0,00%(=) | 10,67% (-1,00pt) |
| *(rappel §2.44)* Délai 4 mois | 8 340 794$ | +0,07% | 0,00%(=) | 0,00%(=) | 11,00% (-0,67pt) |

**Constat révisé — la décroissance est BEAUCOUP moins abrupte à l'échelle
des semaines que ne le suggérait le point à 2 mois seul** : à 1 semaine,
~78% du gain jour0 est conservé (+1,17% sur +1,45-1,50%) ; à 4 semaines
(~1 mois), encore ~45% (+0,67%). La chute à ~23% n'intervient qu'entre 1
et 2 mois — hors de la fenêtre de négociation réelle. **Le coût en
hit_ceiling@3000$ (2,67% pour jour0), lui, s'effondre presque
immédiatement** : 0,33% dès 1 semaine de délai (÷8), 0,00% dès 4 semaines
— l'essentiel du risque de plafond du jour0 disparaît bien plus vite que
le profit.

**Verdict opérationnel** : dans la fenêtre réelle de négociation (1-3
semaines), "lancer maintenant sans BB+GFT et ajouter GFT dès que la
négociation aboutit" retient la MAJORITÉ du gain jour0 (70-78% à
1-2 semaines) tout en évitant l'essentiel du risque hit_ceiling@3000$ —
un compromis nettement plus favorable que ce que suggérait le point à 2
mois pris isolément. Si la négociation traîne au-delà de 4-6 semaines,
l'intérêt continue de s'éroder mais reste positif (+0,67% encore à 4
semaines).

**Statut : PRÉLIMINAIRE, n=300 screening seul** (pas de stress-test
H1/H2+k-fold, pas de n=600) — suffisant pour une décision de calendrier
immédiate, mais à confirmer en n=600+stress-test avant adoption formelle
si ce chemin (lancement différé) est retenu comme la stratégie réelle.

**Condition de réouverture** : n=600+stress-test H1/H2+k-fold sur le(s)
délai(s) retenu(s) (probablement 1-2 semaines vu la fenêtre réelle) avant
toute décision définitive ; affiner à J+3/J+5/J+10 si la négociation
aboutit plus vite que prévu et qu'une granularité encore plus fine devient
utile.

### 2.45 Risque Instant mal appliqué — 2e erreur de prémisse dans §1.8, CORRIGÉ n=600 (08/17-18)

**Découverte** : Blueberry Instant Elite/Lite ne bénéficient PAS de
l'exemption Prime sur le risque par trade — ils sont soumis à un cap réel
de **1,5%/trade, calculé sur la taille INITIALE du compte (fixe, ne bouge
jamais même si le solde grossit)**. Seul Prime en est exempté. 2e erreur
de prémisse découverte dans le chantier §1.8, après le bug de cadence
Blueberry 7j du 08/16 (`registre_parametres_projet.md` §1.8, correction
Run F).

**Vérification par citation de code (moteur backant §1.8)** : `format_def()`
(`engine_multiformat.py:46-55`) n'a **aucun champ risque-par-trade** — seuls
`dd_daily_pct`/`dd_max_pct`/`dd_max_mode`/`lock_after_pct` existent. Le
risque réellement appliqué à un compte Blueberry Instant funded est le
risque flotte global, identique à Prime (`chantier_cascade_combined_
bb_switch_any_rr_2026-08-16.py:55,451` : `FLEET_RISK=1,90` ;
`base_r = fleet_risk if acc["phase"] == "funded" else base_risk`, aucune
branche Instant). Le moteur autorisait donc 1,90% (potentiellement ×0,5 si
DD-distance V2 actif, jamais un cap absolu) au lieu du vrai plafond 1,5%.

**Calcul déjà correct sur la taille initiale** (vérifié séparément,
question explicite de l'utilisateur) : `risk_amount = eff_risk/100 *
acc["palier"]` (`engine_multiformat.py:330`) — `acc["palier"]` ne grossit
JAMAIS dans ce moteur (recherche exhaustive de toute assignation
`acc["palier"] = ...`, seule occurrence trouvée = remise à `base_palier`
sur réouverture, jamais une augmentation). Le clamp `r=min(r,1,5%)` capture
donc automatiquement "1,5% de la taille initiale figée" par construction,
sans logique supplémentaire nécessaire.

**Correctif** : clamp `r=min(r,BB_INSTANT_RISK_CAP=1,5)` appliqué aux
trades Blueberry Instant, APRÈS tout autre multiplicateur (DD-distance V2
inclus), intégré en dur (pas un flag optionnel) dans
`chantier_S1_8_officiel_n600_risque_corrige_2026-08-17.py` (copie figée de
`chantier_cascade_combined_bb_switch_any_rr_2026-08-16.py`, script backant
la référence officielle). 99,9-100,0% des trades Instant sont affectés à
tous les plafonds (~2,58-2,83M trades échantillonnés n=600) — le DD-distance
V2 ne fait quasiment jamais retomber le risque sous 1,5% de lui-même.

**Stress-test H1/H2+4 blocs k-fold** (`chantier_S1_8_stresstest_risque_
instant_2026-08-17.py`, n=100, 2 régimes de plafond représentatifs
960$/3000$, avant tout n=600, même protocole que §2.35/§2.41-42) : 10/12
sous-périodes confirment la dominance (profit MIEUX, direction constante).
Les 2 exceptions (toutes deux "bloc1", aux deux régimes) sont un artefact
de bruit sur une base REF quasi nulle (347$/965$ contre des millions dans
les autres sous-périodes, delta absolu de seulement -606$/-5522$) — année1<0
s'améliore malgré tout dans ce même bloc (-9 à -16pt) — pas une inversion
économique réelle du mécanisme sous-jacent.

**✅ Confirmation n=600+cascade, chiffres avant/après correction, 4 plafonds** :

| Plafond | REF | COMBINÉ non corrigé (ancien, était dans le registre) | COMBINÉ corrigé (nouveau, adopté) | Écart |
|---|---|---|---|---|
| 960$/1000$ | 5 835 876$/5 836 643$ | 6 752 310$ (+15,7%) | **6 417 256$ (+9,95-9,96%)** | **-335 054$ (-4,96%)** |
| 3000$/5000$ | 5 900 859$/5 848 265$ | 7 080 725$ (+20,0-21,1%) | **6 693 474$ (+13,44-14,45%)** | **-387 251$ (-5,47%)** |

Autres axes après correction : solde_neg/hit_ceiling **inchangés** à tous
les plafonds. Année1<0 légèrement **mieux** à 960$/1000$ (24,00% vs
24,33% avant correction) mais légèrement **dégradé** à 3000$/5000$
(15,67% vs 13,83% avant correction, +1,84pt) — reste très inférieur à REF
(28,83-30,50%), la dominance globale n'est pas remise en cause.

**Verdict : dominance stricte sur les 4 axes, aux 4 plafonds — CONFIRMÉE
n=600 après correction.** Environ 33-37% du gain de profit annoncé par
l'ancien tableau non corrigé s'évapore (le gain réel retenu est ~63-69% du
gain brut original selon le plafond) — cohérent entre n=300 (screening,
mêmes proportions) et n=600 (confirmation). **Ce tableau remplace
définitivement les $ précédemment affichés pour §1.8 dans
`registre_parametres_projet.md` §1.8** — décision d'adoption officielle
de §1.8 dans son ensemble toujours séparée et en attente (statut inchangé
par cette correction).

**Condition de réouverture** : aucune à ce stade — correction validée
n=300→n=600 avec stress-test, cohérente aux deux échelles. Rouvrir
seulement si une 3e composante du produit Instant s'avère mal modélisée
(ex. le plancher de trailing qui ne se réinitialise jamais après un
retrait, signalé non modélisé dans `engine_multiformat.py:148` mais jamais
creusé).

### 2.45bis Pivot Instant à taille réduite (5k$/10k$) — mitige le coût du jour0 aux plafonds serrés, N'AMÉLIORE PAS le plafond réel 3000$ (08/18)

Suite directe de §2.45 : le pivot (1er compte Blueberry, jour0) ouvre à
25k$ dans le moteur actuel (coût réel 800$ en Instant Elite avec
bb_seuil=0 adopté à 3000$/5000$) — écart significatif avec un budget
utilisateur initialement prévu autour du prix Prime (165$). Question :
un pivot Instant Elite à taille RÉDUITE (5k$/10k$, coût 200$/400$)
capture-t-il encore l'avantage structurel d'Instant (financé dès jour0) à
moindre coût d'entrée, et cela suffit-il à faire basculer le verdict
"Blueberry-adaptatif" REJETÉ en 08/09 (`registre_parametres_projet.md`
ligne 681, rejet motivé par "trade au risque flotte dès jour 0, pas de
phase protectrice" — sous l'ANCIENNE pile pré-08/12 et SANS le correctif
de risque 1,5% ; les deux conditions du rejet ont changé depuis) ?

4 configs statiques pour le pivot (format+palier FIXES toute sa vie, y
compris après casse — pas de bascule dynamique sur le pivot spécifiquement,
seulement sur les comptes extra/croissance qui gardent le mécanisme S1.8
standard), risque 1,5%/trade déjà intégré dès le départ, n=300, 4 plafonds
(`chantier_pivot_instant_taille_reduite_2026-08-18.py`, suivi par git) :

| Config | Coût réel | Profit@960-1000$ | Profit@3000-5000$ | Hit_ceiling@960-1000$ | Année1<0@960-1000$ |
|---|---|---|---|---|---|
| Prime25k | 165$ | 6 489 695$ | 6 534 951$/6 510 591$ | 0,33% | 21,67% |
| InstantElite5k | 200$ | 6 490 660$ (≈0%) | 6 491 257$/6 512 070$ (≈0%) | 0,67% | 19,67% |
| InstantElite10k | 400$ | 6 590 213$ (+1,55%) | 6 589 757$/6 610 414$ (+0,84%/+1,53%) | 1,33% | 17,33% |
| InstantElite25k | 800$ | 6 688 902$ (+3,07%) | **6 791 917$ (+3,93%/+4,32%)** | **3,33%** | 14,67%/14,00% |

**À 3000$/5000$ (plafond réel) : InstantElite25k reste strictement
optimal** — meilleur profit, solde_neg/hit_ceiling à 0,00%=, aucun coût de
risque supplémentaire (le régime bb_seuil=0 le rend déjà sûr à ce
plafond). Les variantes réduites n'apportent RIEN à ce plafond — elles ne
sacrifient que du profit sans gain de sécurité, puisqu'il n'y a rien à
mitiger.

**Le levier taille-réduite n'est utile qu'aux plafonds serrés
(960$/1000$)** — là où InstantElite25k jour0 dégrade solde_neg (0,33%→
2,00%, non montré au-dessus) et hit_ceiling (0,33%→3,33%), les versions
5k/10k atténuent fortement ce coût (hit_ceiling 0,67%/1,33% au lieu de
3,33%) tout en gardant une partie du gain de profit — mais **ne renversent
PAS franchement le rejet "Blueberry-adaptatif" de 08/09** : même mitigé,
le risque reste non-nul vs Prime, cohérent avec le choix actuel §1.8 de
garder bb_seuil=5000$ (rester classique) à ces plafonds plutôt qu'une
taille intermédiaire.

**Verdict : pas un levier de performance à 3000$/5000$ (déjà optimal en
25k$), mais un filet de sécurité budgétaire valide** si la trésorerie
disponible au lancement est plus proche de 200-400$ que de 800$ —
InstantElite5k coûte à peine plus que Prime (200$ vs 165$) pour un profit
quasi identique et un année1<0 légèrement meilleur. Décision purement
liée à la trésorerie réelle disponible cette semaine, pas à un arbitrage
de performance.

**Condition de réouverture** : si le plafond personnel réel change
significativement vers le bas (redevient pertinent aux plafonds serrés
960$/1000$ où le levier a un effet réel) ; n=600 pas lancé, candidat pas
assez fort à 3000$/5000$ pour le justifier.

### 2.46 Filtre forex-only — bug de population CORRIGÉ, impact sur A et B chiffré (08/18)

**Découverte** (partie du chantier "amélioration Stratégie B") :
`build_extended_population()` (`rr_threshold_test.py:47`, fonction
utilisée par TOUTE construction de population du projet, A comme B)
appliquait un filtre **forex-only codé en dur** (`FOREX_PATTERN.match
(ticker)`), totalement indépendant de tout critère RR ou du whitelist
scraper (`scraper.py:82-98`, qui lui inclut bien 5 indices via
`TARGET_INDEX_KEYWORDS`). Vérifié par citation de code et git log
(aucun commit n'a jamais documenté ce filtre comme un choix
méthodologique) : **321 trades indices scrapés avec succès (DAX40/
S&P500/NASDAQ100/DJ30, `historique_lutessia_15k_force.csv`) étaient
silencieusement éliminés avant toute simulation du projet.** DJ30 (53
lignes) s'est avéré structurellement inutilisable en plus (rr_tp1=NaN
sur toutes ses lignes, bug de parsing distinct, non corrigé ici).

**Correctif appliqué** : `rr_threshold_test.py:43-61` — remplace le
filtre `FOREX_PATTERN` par un critère de mappabilité réelle
(`ticker_to_yahoo_symbol(t) is not None`, couvre forex ET les 3 indices
gérés par `INDEX_KEYWORD_MAP`). DJ30 reste exclu naturellement (échoue
déjà le filtre rr_tp1 en amont). Propage automatiquement à toute
construction de population future (plus besoin de re-derniver
manuellement).

**Impact mesuré (même méthodologie EV/trailing que le reste du
projet)** :

| Population | n avant | n après | Δ volume | Winrate | EV |
|---|---|---|---|---|---|
| A (RR≥1,35, référence) | 631 | **742** | **+17,6%** | 39,5%→39,9% (+0,4pt) | +0,893R→+0,900R (+0,7% relatif) |
| B (1,00≤RR<1,35) | 401 | **460** | **+14,7%** | 49,6%→49,6% (≈0) | +0,801R→+0,781R (-2,4% relatif) |

**Qualité d'edge quasi inchangée, volume réellement augmenté** — les 111
trades indices ajoutés à A ont une EV propre (+0,934R) très proche du
forex (+0,893R), d'où la dilution de l'effet sur winrate/EV à l'échelle
de 631-742 trades. Stress-test H1/H2+4 blocs sur A élargi
(`chantier_reference_A_indices_2026-08-18.py`) : **aucune inversion de
direction imputable aux indices** — la seule sous-période limite (bloc0,
EV globale -0,009R quasi nulle) est un régime de marché difficile
préexistant dans le forex seul (-0,082R), et les indices y sont même
stabilisateurs (+0,402R). Comportement typique d'une vraie
diversification, pas le profil d'échec du classement de paires
(§2.32/§2.33, inversion H2).

**Limite non résolue** : le diagnostic "bloqué par corrélation" sur B
(§2.44bis/récent, n=16, Δ=+0,668R) n'est PAS recalculable avec les
indices — `correlation_matrix.csv` ne couvre que les 14 paires FX,
aucune donnée de corrélation indices↔indices ou indices↔forex. Tâche
séparée si utile.

**Voir aussi `registre_parametres_projet.md` §1.8bis** pour l'impact
détaillé sur la référence officielle A (volume/EV/stress-test complet) —
ce §2.46 se concentre sur B et le correctif lui-même.

**Condition de réouverture / suite** : Tâche de faisabilité d'exécution
live (le setup MT5/broker actuel peut-il réellement trader ces indices ?)
et construction de la matrice de corrélation indices en cours au moment
de la rédaction — statut à mettre à jour une fois ces deux points tranchés.

**✅ Suite (même jour)** : faisabilité live tranchée NON (§2.47), matrice
de corrélation construite (19×19, `extend_correlation_matrix_indices_
2026-08-18.py`) — voir §2.47 pour le routage optimal des indices vers B.

### 2.47 Routage indices vers B — "tout indices→B" bat le routage naturel par RR, effet régime-dépendant (08/18)

Suite de §2.46. Deux prérequis tranchés avant simulation flotte :

**Faisabilité d'exécution live : NON.** Deux blocages distincts dans
`app.py`, vérifiés par citation de code (pas supposé) : (1) whitelist à
l'entrée du parsing live (`app.py:225`, `if ticker not in scraper.
TARGET_FOREX_TICKERS`) — tout signal indice serait classé
`"hors_perimetre"` avant même d'atteindre MT5 ; (2) `mt5_symbol = ticker.
replace("/", "")` (`app.py:479`) produirait un symbole broker invalide
pour un ticker indice (aucun mapping ticker→symbole broker n'existe côté
live, contrairement à `ticker_to_yahoo_symbol` côté backtesting). Il
faudrait étendre le whitelist ET construire un vrai mapping vérifié
contre le Market Watch réel du broker (noms variables selon courtier :
GER40/DE40, US500/SPX500, USTEC/NAS100...) — non fait, chantier
purement décisionnel sur le moteur de simulation.

**Matrice de corrélation étendue** (`extend_correlation_matrix_indices_
2026-08-18.py`, backup de l'ancienne conservé) : 14×14→19×19 (14 FX + 5
labels indices). Vérification : 2 labels du même sous-jacent (ex. "DAX40
FULL0926"/"DAX40 PERF INDEX") donnent 1,0000 exactement (même série de
prix assignée). Indices↔forex faible partout (max +0,161) — jamais
bloqués par une position forex. **NASDAQ100↔S&P500 = +0,954** (>seuil
0,80, any-RR s'applique réellement). DAX40↔NASDAQ100/S&P500 ≈ 0,000
(probable artefact des heures H1 qui se chevauchent peu Europe/US,
signalé pas creusé).

**Comparaison flotte réelle (B en isolation, protocole §2.55, stack
actuel complet S1.8+S2.35+correctif risque Instant+matrice étendue),
n=300, 4 plafonds — 2 populations candidates :**
- "routage naturel" : B forex (401) + indices RR<1,35 seulement (59) = 460
- "tout_indices" : B forex (401) + TOUS les indices, indépendamment du RR (170) = 571

| Plafond | naturel (profit/solde_neg/hit_ceiling/année1<0) | tout_indices | Δ profit | Δ année1<0 |
|---|---|---|---|---|
| 960$ | 1 557 560$/10,67%/5,00%/72,67% | 2 277 650$/5,00%/4,00%/57,67% | **+46,2%** | **-15,00pt** |
| 1000$ | 1 569 324$/10,00%/3,00%/72,67% | 2 293 468$/4,67%/3,00%/57,67% | **+46,1%** | **-15,00pt** |
| 3000$/5000$ | 1 765 023$/8,00%/0,00%/56,33% | 2 521 095$/3,00%/0,00%/41,67% | **+42,8%** | **-14,66pt** |

**Dominance nette et cohérente sur les 4 axes, à tous les plafonds.**
Feasibilité d'exécution (marge/lot) NON modélisée pour les indices dans
ce test (aucune spec broker réelle recherchée, contrainte désactivée —
distinct de la faisabilité d'EXÉCUTION déjà tranchée NON ci-dessus, cf.
`chantier_strategie_b_isolation_indices_2026-08-18.py` docstring) —
l'économie du trade (R réalisé) vient des données historiques réelles,
inchangée par cette simplification.

**Stress-test H1/H2+4 blocs (n=100, `chantier_strategie_b_isolation_
stresstest_2026-08-18.py`) — effet RÉGIME-DÉPENDANT, pas uniforme** :

| Sous-période | Δ profit tout_indices vs naturel | Année1<0 (nat/tout) | Direction |
|---|---|---|---|
| H1 | -760,9% | 100%/100% | INVERSION |
| H2 | +38,8% | 14%/6% | OK |
| bloc0 | -94,6% | 100%/99% | INVERSION |
| bloc1 | -46,8% | 100%/100% | INVERSION |
| bloc2 | +79,4% | 20%/17% | OK |
| bloc3 | +80,3% | 13%/6% | OK |

**Pas du bruit — motif net et cohérent** : la 1ère moitié chronologique
(H1/bloc0/bloc1) est un régime où B s'effondre totalement quel que soit
le scénario (année1<0=100% des deux côtés) ; dans ce régime, plus de
volume (tout_indices) aggrave marginalement une perte déjà totale
(mécanisme cohérent : plus de tentatives de challenge = plus de frais
engagés quand l'edge ne compense pas assez vite, déjà vu ailleurs dans
ce projet). La 2e moitié (H2/bloc2/bloc3) est un régime où B fonctionne,
et là plus de volume aide nettement (+38-80%).

**Verdict : direction claire en faveur de "tout indices→B"** — le
routage par RR (approprié pour A) n'est pas le bon critère pour B, qui
est frequency-starved avant tout (cohérent avec §2.55). Le gain agrégé
vient entièrement des périodes où B est déjà viable ; dans les périodes
où B échoue de toute façon, l'effet est délétère mais de faible ampleur
absolue (dizaines de milliers $ sur un échec déjà total). **PAS un
signal d'alarme sur le sens global, mais une nuance réelle à garder.**

**Statut : n=300 + stress-test fait, PAS de n=600.** Bug de méthode
trouvé et corrigé en cours de route : double-comptage des indices RR<1,35
dans la population "naturel" (`build_population_with_trailing` inclut
désormais les indices automatiquement depuis le correctif §2.46, il
fallait explicitement les retirer avant de les rajouter manuellement) —
n=519/630 avant correction, n=460/571 après, corrigé dans les 2 scripts
avant tout résultat rapporté.

**Condition de réouverture** : n=600+cascade si adoption sérieusement
envisagée ; faisabilité d'exécution live (whitelist+mapping broker) à
construire séparément si ce candidat devient prioritaire — actuellement
un exercice décisionnel sur le moteur de simulation uniquement, pas
déployable.

## 3. Hors périmètre (fleet-architecture, pas l'edge)

Scripts trouvés pendant cet audit mais volontairement EXCLUS de ce
registre (relèvent de `registre_parametres_projet.md` ou en sont trop
proches) :
- `missed_signals_replay.py` — quantifie les signaux bloqués par le cap
  de position/la règle de corrélation (routage, pas edge).
- `signal_stability_cluster_diagnosis.py` — vérifie si les casses
  groupées viennent du copytrade synchrone (architecture flotte, pas
  edge).
- Volet risque% de `rr_risk_combo_test.py` (le volet seuil R:R est
  couvert en §2.8 ci-dessus).

---

## 4. Points ouverts (à ne pas re-tester sans nouvelle piste, mais pas fermés)

1. ✅ *(backtesté 08/11, §2.9)* Filtre news — mécanisme trop étroit (±2min)
   pour affecter statistiquement plus de 4 trades sur 460 couverts.
   Verdict : sous-alimenté, pas prioritaire. Point 3 (simulation du
   délai) reste impossible sans données M1/tick.
2. ✅ *(RÉSOLU/APPLIQUÉ 08/11)* Fichier historique stale — corrigé dans
   `rr_threshold_test.py:37`, `historique_lutessia_15k_force.csv` (721
   trades) est maintenant le défaut. Impact mesuré : -3,2 à -3,5%
   profit, année1<0 +4,3 à +4,7pt. Voir `registre_parametres_projet.md`
   §2.29/§4#14.
3. **Kelly 25%** reste un arbitrage non tranché (§2.5), jamais re-testé
   sous le moteur multi-format actuel.
4. **ATR sizing** jamais recalculé avec la correction funded/challenge
   (contrairement à Kelly, §2.6).
5. **Plancher du trailing stop** (<0,2×SL) jamais testé en robustesse
   malgré une amélioration monotone observée jusqu'à 0,05×SL (§2.7) —
   risque de spread/slippage réel non modélisé à cette distance.
6. 🟡 *(nouveau 08/11)* Combo ADX≥20+ATR[0,5-2,0] (§2.15) — seul filtre
   testé dont le lift ne s'inverse pas en sous-période, mais n=114/moitié
   trop petit pour un verdict définitif. Pas adopté, pas rejeté — à
   reconfirmer si l'échantillon grandit ou avec un test statistique
   formel (pas juste visuel) sur la stabilité du lift.
7. 🔴 *(nouveau 08/11)* Test 4 (combinaisons) incomplet — seul 2+3
   (ADX+ATR) fait. 1+2/1+3/1+2+3 (impliquant le filtre news) bloqués par
   le manque de données sur le filtre news (§2.9, n=4 seulement dans la
   fenêtre couverte) — pas une vraie combinaison possible tant que ce
   point ne progresse pas.
8. 🔴 *(nouveau 08/11)* Couverture ADX/ATR limitée à 52% de la
   population (375/721, contrainte yfinance ~729j) — tous les verdicts
   §2.13-2.15 reposent sur ce sous-ensemble récent uniquement, pas sur
   les 721 trades. Une source de bougies plus profonde (Dukascopy,
   déjà utilisée pour le slippage §2.11) permettrait de retester sur
   la population complète si jugé utile.
9. 🟡 *(RÉOUVERT 08/19-20, §6.4)* Plafond de positions simultanées (§2.28) —
   verdict "Fermé" du 08/15 valable pour A SEULE uniquement (0,8% de la
   population bloquée par le cap à l'époque). Sous Config2-AB (population
   B+métaux, fréquence 171,6% de A), le cap est bien plus contraignant
   (6,4% bloqué, EV du segment bloqué SUPÉRIEURE à la moyenne prise) —
   cap=4/5 testés n=600, gains de profit significatifs (+8,4%/+10,8%
   cumulés) à risque quasi neutre. PAS ADOPTÉ (jamais testé sur la
   population de lancement réelle B_tradable ni stress-testé), voir §7#1.
10. ✅ *(RÉSOLU/SUPERSEDÉ 08/16)* Échange par corrélation, variante "any"
    (§2.32, classement de paires) — CONFIRMÉ n=600 (+8,0-8,2% profit,
    4 axes) mais **remplacé par "any-RR" (§2.33, critère RR planifié du
    trade)**, CONFIRMÉ n=600 **+9,6-9,7% profit, dominance stricte 4 axes,
    supérieur à any sur CHAQUE axe, sans la réserve classement-de-paires**
    (§2.33 a aussi tenté de fiabiliser le classement par shrinkage —
    ÉCHEC documenté, Spearman moyen k-fold ~0, piste fermée).
    **✅ RÉSOLU/INTÉGRÉ 08/16** — cascade groupée avec la bascule
    Blueberry Instant régénérée dans le même moteur/seed
    (`registre_parametres_projet.md` §1.8, proposition 08/16) :
    dominance stricte 4 axes aux 4 plafonds testés (960$/1000$/3000$/
    5000$), effet légèrement SUPER-ADDITIF vs la somme des deux effets
    isolés (+0,4 à +0,9pt selon le plafond, pas de cannibalisation).
    En marge de cette intégration, découverte d'une dérive méthodologique
    préexistante (cadence Blueberry 14j appliquée par erreur au lieu du
    7j officiel à 3000$ dans les moteurs hérités depuis
    `chantier_position_cap_2026-08-15.py`, donc aussi dans §2.28/§2.32/
    §2.33 ci-dessus) — corrigée dans le moteur de la cascade groupée et
    vérifiée (REF@3000$ corrigé = 5 900 859$, correspond exactement à la
    référence officielle 08/12). Les $ absolus cités à 3000$/5000$ dans
    §2.28/§2.32/§2.33 sont donc sous-estimés d'environ 0,9%, mais les
    verdicts relatifs (comparaisons A/B internes cohérentes) restent
    valides. PAS ENCORE ADOPTÉ dans la référence officielle §1.8 —
    décision utilisateur finale en attente (proposition prête,
    tableau complet et décomposition disponibles).
11. 🟡 *(ouvert 08/17)* Suites directes des rejets §2.36/§2.37, portée
    précisément délimitée (pas des re-tests de la même famille) :
    - **Downsizing temporel/conditionnel sur segment(s) RR faible(s)**
      (analogue V2, fenêtre année1/seuil réserve) — distinct du boost
      gradué ≥1,0× rejeté en §2.36. Étape 0 (surreprésentation
      pertes/casses par segment) à faire avant toute construction.
    - **Sizing asymétrique multi-niveaux permanent** (boost ×1,6 maintenu
      + downsizing ×0,5/×0,8 sur segment(s) faibles) — distinct des 3
      candidats "plancher 1,0×" rejetés en §2.36.
    - **GFT Instant, stratégie adaptée à la contrainte 6% trailing**
      (risque réduit ciblé/filtre RR resserré/exclusion paires
      dangereuses, informé par un diagnostic du mode de casse) — distinct
      de la stratégie classique rejouée à l'identique rejetée en §2.37.
12. ✅ *(RÉSOLU/ADOPTÉ 08/19, §5.9)* Trailing 0,10×SL sur B (au lieu de
    0,15× hérité de A) — dominance stricte n=600, 4 axes, 4 plafonds.
13. 🟡 *(ouvert 08/19, §5)* Diagnostic corrélation sur B (n=31, §5.2) —
    signal statistiquement solide (IC95% bootstrap positif, shrinkage
    résistant), mais AUCUN mécanisme actionnable trouvé qui capture une
    part significative du gisement (+0,99R) — any-RR simple ≈nul, marge
    RR minimale pas mûre (§5.7), priorité ciblée NASDAQ100/S&P500 jamais
    testée en Monte Carlo. Piste ouverte, à reprendre avec une idée de
    mécanisme différente.
14. ✅ *(RÉSOLU/SUPERSEDÉ 08/19-20, §6.2)* Risque par trade recalibré pour B —
    le moteur A+B PARALLÈLE manquant a été construit
    (`chantier_ab_metaux_cascade_officiel_2026-08-19.py`, 2 flottes à 5
    firms, réserve séparée/plafond combiné, validé contre S1.8). N'a pas
    directement recalculé le risque par trade de B isolément, mais rend
    la question largement caduque : la décision de lancement (§6.5) est
    passée à B seule (Config0 tradable) puis A par seuil de trésorerie,
    pas A+B simultané avec risque à recalibrer séparément.
15. 🟡 *(ouvert 08/19, §5.4)* Géométrie de trade B (stop large -32%/TP1
    proche +18% vs A en médiane, §5.4) jamais exploitée par un mécanisme
    concret — seulement diagnostiquée par la caractérisation structurelle.
    Piste réellement spécifique à B (pas transposée de A), jamais testée.

---

## 5. Session 2026-08-19 — maturation complète de Stratégie B

Objectif : faire grandir B (571 trades, forex[1,00;1,35)+tout-indices) au
niveau de A pour permettre un lancement à 2 comptes en parallèle. Détails
complets et scripts : `session_handoff_2026-08-19.md`. Population de
référence tout au long : B=571 (tout-indices→B déjà adopté), A=742/853
selon reconstruction (RR≥1,35, indices inclus).

### 5.1 Trailing post-TP2 — 0,10×SL ADOPTÉ, dominance stricte n=600

Sweep 0,10/0,15/0,20/0,25×SL sur B (117 trades à continuation confirmée,
bug corrigé en route : filtre `rr_tp1>=1.0` trop strict excluait 13
trades à RR=1,00 pile par artefact flottant). **0,10× domine en EV
statique de façon monotone sur toute la plage** (+0,89% vs 0,15× actuel).
Slippage-robuste (delta constant +0,0398R jusqu'à 5 pips testés,
décalage parallèle mathématique — voir limite methodo ci-dessous).
Décomposé forex seul (n=86) / indices seul (n=31) : les deux confirment
indépendamment 0,10×>0,15×, pas un artefact de composition.

**Monte Carlo fleet, n=300 puis n=600, 4 plafonds** (`chantier_b6_
montecarlo_2026-08-19.py`) :

| Plafond | Δ profit | solde_neg | hit_ceiling | année1<0 |
|---|---|---|---|---|
| 960$ | **+2,65%** | 6,17%→5,67% | 4,17%→4,00% | 56,33%→55,83% |
| 1000$ | **+2,60%** | 5,50%→5,00% | 2,83%=2,83% | 56,33%→55,83% |
| 3000$/5000$ | **+2,20%** | 4,00%→3,50% | 0,00%=0,00% | 42,17%→42,00% |

**Dominance stricte confirmée n=600, 4 axes, 4 plafonds, sans exception.**
**Verdict : ADOPTABLE.** Réserve méthodologique non résolue : le modèle
de slippage testé est un décalage UNIFORME par trade, ne capture pas un
risque de gap/slippage catastrophique ponctuel plus fréquent en
exécution réelle sur un trail serré — signalé, pas quantifiable avec les
données disponibles.

### 5.2 Diagnostic corrélation sur B — signal solide (n=31), mécanisme actionnable non trouvé

Repris de la session 08/18 (n=16, Δ=+0,668R, jugé fragile). Avec la
population B élargie (571, matrice 19×19 déjà construite, réutilisée
sans recalcul) : **n=31**, EV bloqués=+1,7099R vs EV admis=+0,7238R,
**Δ=+0,9861R**. Bootstrap IC95% (5000 itérations) = [+0,81 ; +2,68]R,
P(moyenne>0)=100%. Retrait top 3/5 outliers : reste positif (+1,10R/
+0,84R). **Shrinkage bayésien** (formule §3.16-08/16, k=10/20/30/50) :
reste positif même à k=50 (+1,15R shrinké, delta +0,43R vs admis).
Stress-test H1/H2+4blocs : 4/6 cohérent (2 inversions H1/bloc1, régime
difficile déjà connu).

**Fiche d'identité complète des 31 trades** (`chantier_b5_1_fiche_
identite_2026-08-19.py`) : tous à conflit SIMPLE (aucun conflit multiple,
catégorie "C" vide). Catégorie A (RR bloqué>occupant, théoriquement
capturable par any-RR) = 16/31 (54,1% du delta), catégorie B (RR
bloqué≤occupant) = 15/31 (45,9%). **Dominé à ~26% par le seul couple
NASDAQ100-MINI/S&P500-MINI** (corrélation 0,954) — bloqué 8/31 fois
(surreprésenté ~4,3× son poids réel dans B), occupant 8/31 fois
(surreprésenté ~4,1×). Session Asie surreprésentée (45,2% des blocages
vs 34,0% de base). 13/31 cas où l'occupant a perdu, dont 5/31 (16,1%)
où le bloqué aurait aussi gagné (cas de valeur perdue le plus net).

**Trace dynamique du mécanisme any-RR déjà en production** : 15 swaps
réels au total sur toute la population (pas 3 comme le comptage net
+3 trades le suggérait) — **8/15 à gain NET NUL** (occupant évincé aussi
perdant, -1,00R vs -1,00R), **2/15 à gain NÉGATIF** (occupant évincé
aurait gagné), seuls **5/15 à gain net positif**, pour un total de
+3,930R sur toute la population. Explique pourquoi any-RR capture si
peu (+0,01R mesuré séparément) malgré un signal statistique fort en
amont : le RR planifié est un proxy bruité du résultat réalisé.

**2 mécanismes proposés, non testés en Monte Carlo** :
1. Marge RR minimale sur le swap — voir §5.7, jugé PAS MÛR.
2. Priorité ciblée NASDAQ100-MINI>S&P500-MINI (EV propre +0,967R vs
   +0,628R dans B, n=34/36) — **jamais testé en Monte Carlo, fragile**
   (comparaison à 2 échantillons modestes, non stress-testée).

**Verdict : signal exploitable statistiquement, AUCUN mécanisme
actionnable ne capture une part significative du gisement à ce jour.**
Piste ouverte (§4#13).

### 5.3 Leviers transposés de A — Force, JPY-JPY, rr_tp2

**Score Force sur indices de B** (`chantier_b4_a_force_indices_2026-08-19.py`) :
déjà testé et rejeté sur forex (§2.1, r=+0,026/+0,072, non significatif).
Reconfirmé sur B forex actuel (r=-0,086/-0,025, non significatif). Sur
indices B seuls (n=170) : r=+0,081 (victoire)/+0,125 (R), **toujours non
significatif** (p=0,291/0,104). Stress-test 6 sous-périodes : aucune
significative (p entre 0,053 et 0,786). **REJETÉ, pas de signal
spécifique aux indices.**

**Règle JPY-JPY** (`is_jpy()`, `scaling_simulation.py:78-79`, utilisée
dans `monte_carlo_simulation.py:83`) : re-testée sur B (`chantier_b4_b_
jpy_rule_2026-08-19.py`). Diagnostic historique direct (10 duos JPY-JPY,
même méthode que §2.60/08/12) : max DD flottant combiné = **1,32%** sur B
forex (même ordre que le 1,53% déjà confirmé sur A en 08/12), identique
sur B complet (indices jamais JPY par construction, `is_jpy()` retourne
False pour les 5 labels indices — vérifié par citation directe).
Corrélation JPY↔indices max = 0,156 (loin du seuil 0,80, pas de risque de
sous-exclusion cachée). **CONFIRMÉ : la règle tient sur B, aucune
adaptation nécessaire pour les indices.**

**Mécanisme rr_tp2** (`chantier_b4_c_rrtp2_diagnostic_2026-08-19.py`) :
rejeté en sizing/routage sur B en session précédente (échec stress-test
H1). Corrélation rr_tp2↔distance_TP2% recalculée fraîchement : A=+0,266,
B=+0,201 (ratio 0,76, comparable, pas d'effondrement structurel — note :
ce +0,266 sur A ne retrouve pas le +0,45 historique cité en §2.35/08-16,
population/définition probablement différente à l'époque, non
réconcilié). Sweep de seuils sur B : delta EV positif et substantiel à
TOUS les seuils testés (+0,66R à +1,30R), pas un signal plat. **Mais le
stress-test échoue systématiquement dans les mêmes sous-périodes
(H1/bloc0/bloc1) quel que soit le seuil essayé (>7,5 comme >8,0)**,
toujours avec un échantillon fin (n=13-26) dans ces sous-périodes
précisément. **Verdict : ni rejet structurel confirmé ni seuil mal
calibré — probablement un problème de volume de données dans les
périodes difficiles, pas une preuve d'inversion réelle du mécanisme. Pas
fermé, à rouvrir avec plus de données.**

### 5.4 Caractérisation structurelle complète A vs B

8 axes comparés (`chantier_b4_e_caracterisation_2026-08-19.py`), A=853,
B=571, indices inclus des deux côtés. Résumé des divergences notables :

- **Composition actifs** : B légèrement plus indices (29,8% vs 26,0%) ;
  recomposition au sein du forex (CHF/JPY 5,4%→3,3%, GBP/JPY 5,7%→4,2%,
  EUR/GBP 5,0%→6,5%).
- **rr_tp1** : B beaucoup plus concentré près de son plancher (skew
  +2,29 vs +0,57 sur A) — B n'est pas homogène dans sa propre bande.
- **Distances SL/TP1/TP2%** : **divergence structurelle majeure** — B a
  des stops PLUS LARGES (+18% en médiane) et un TP1 PLUS PROCHE (-32%
  en médiane) que A. Pas juste "A avec un seuil RR plus bas" — une
  géométrie de trade différente.
- **Score Force** : distributions statistiquement indiscernables (KS
  p=0,104).
- **Durée de vie** : médiane proche (~8h) mais traîne beaucoup plus
  lourde sur B (skew 13,3 vs 6,6 sur A_fx).
- **Session horaire, ADX à l'entrée** : pas de divergence notable.

**3 hypothèses formulées, testées en §5.6** (segmentation interne rr_tp1,
sizing distance_SL%, timeout traîne longue).

### 5.5 Risque par trade recalibré pour B — DIFFÉRÉ, moteur A+B manquant

Nécessite une comparaison n=600 "scénario 2 comptes A+B en parallèle" qui
suppose un moteur à 2 flux de signaux indépendants + réserve de cash
partagée — **n'existe pas dans le code actuel** (les scripts B actuels
substituent B à A dans la même flotte, ils ne font pas tourner les deux
ensemble). Décision utilisateur : différer après les autres points de ce
chantier. **Jamais construit, jamais testé.** Chantier d'ingénierie
séparé si repris.

### 5.6 Segmentation EV 4 variables + 3 hypothèses structurelles (Chantier E)

**Segmentation initiale** (`chantier_b_ev3_segmentation_2026-08-19.py`) :
session horaire = bruit, asset_class = 1 seule catégorie (non
discriminant, vérifié sur le CSV source), distance_SL% signalé en coupe
simple mais **non stable en stress-test sur B** (4/6 et 3/6 inversions
selon quintile — contraste avec A où cette variable était le seul
candidat stable), **ADX(14)>32,27 = signal net, stress-testé 6/6 SANS
EXCEPTION** (couverture 48%, n=274/571).

**3 hypothèses de la caractérisation structurelle testées** (`chantier_
b5_6_hypotheses_e_2026-08-19.py`) :
1. Segmentation interne rr_tp1 (§5.4) : quintiles non monotones (forme en
   U), seuil rr_tp1≤1,25 le plus stable trouvé (5/6, voir §5.8).
2. Sizing par distance_SL% : **REJETÉ** — et la prémisse structurelle
   elle-même invalidée : `risk_amount = risk_pct% × palier`
   (`engine_multiformat.py:329-330`) déjà normalisé indépendamment de
   distance_SL%, l'hypothèse "stop plus large = risque $ plus élevé" ne
   s'applique pas au moteur actuel.
3. Timeout sur la traîne longue de durée : **REJETÉ nettement**.
   Pearson(durée,R)=+0,018 (p=0,665, aucune corrélation). La traîne
   longue (>P90) a en fait une EV PLUS HAUTE, effet inverse à
   l'hypothèse dû à un artefact de confusion temporelle (aucun trade à
   traîne longue dans les sous-périodes difficiles H0/bloc1). **Ne pas
   poursuivre un mécanisme de timeout sur B.**

**Décomposition forex/indices** (`chantier_b5_5_decomposition_2026-08-19.py`) :
trailing 0,10× et ADX>32,27 confirmés indépendamment sur B-forex ET
B-indices — aucun des deux signaux n'est un artefact de composition
(ADX même plus marqué côté indices : EV 0,406R vs 2,048R, n=22/58).

### 5.7 K-fold marge RR minimale sur swap corrélation — PAS MÛR

Sweep de marge (1,00 à 1,50×) sur les 15 événements de swap réels de B :
marge=1,20 double quasi le gain net statique (+3,93R→+6,42R, filtre le
pire swap négatif, garde 13/15 événements). **Stress-test H1/H2+4blocs :
2/6 sous-périodes NÉGATIVES (H1, bloc0), 4/6 positives** — motif cohérent
avec le régime difficile déjà connu ailleurs, mais **seulement 2 à 8
événements par sous-période, non tranchable statistiquement**. **Verdict :
amélioration statique réelle, PAS MÛR pour Monte Carlo faute de volume.**
Exclu du Monte Carlo fleet §5.9.

### 5.8 K-fold segmentation rr_tp1≤1,25 — MÛR, sizing ×0,7 retenu

Détail 6 sous-périodes (n=51-182 chacune, échantillons solides) :
**5/6 cohérent** (1 seule inversion, bloc3). Seuils voisins testés :
1,20→3/6 (delta=-0,032R), **1,25→5/6 (delta=-0,087R)**, 1,30→3/6
(delta=+0,014R, signe même inversé) — **1,25 est un pic isolé de
stabilité**, pas un point sur une pente monotone (réserve légitime sur
la sensibilité au seuil exact, signal probablement réel mais pas
définitivement prouvé indépendant du choix de coupure).

**Mécanisme retenu : sizing réduit ×0,7 (PAS exclusion)** — le segment
reste positif (+0,78R en coupe complète), l'exclure coûterait 63% du
volume de B (déjà frequency-starved). **Verdict : MÛR pour Monte Carlo.**

### 5.9 Monte Carlo fleet des leviers B mûrs — 1 seul adopté, découverte méthodologique majeure

n=300 puis n=600, 4 plafonds, isolation stricte (`chantier_b6_
montecarlo_2026-08-19.py`, copie figée du moteur `chantier_strategie_b_
isolation_indices_2026-08-18.py`, size_func modifié pour recevoir le
trade entier au lieu de rr_tp2 seul) :

| Levier | Δ profit (3 plafonds) | Verdict fleet |
|---|---|---|
| **Trailing 0,10×** | +2,04% à +2,65% | ✅ **DOMINANCE STRICTE n=600** (§5.1) |
| Filtre ADX>32,27 | **-5,07% à -7,34%** | ❌ **REJETÉ** (exclut 9,6% du volume, coûte plus en fréquence perdue que ça n'économise en qualité) |
| Sizing rr_tp1≤1,25 ×0,7 | **-14,59% à -16,05%** | ❌ **REJETÉ** (coût profit sévère) |
| Marge RR minimale | — | Non testé (pas mûr, §5.7) |

**Découverte méthodologique la plus importante de la session** : ADX et
rr_tp1-sizing sont TOUS DEUX des signaux statistiques propres et
stress-testés (6/6 et 5/6 respectivement) qui **échouent au niveau
flotte** — confirme qu'un signal statistique confirmé n'implique PAS une
confirmation fleet sur une population frequency-starved comme B (réduire
le volume, même sur un segment statistiquement plus faible, coûte plus
en fréquence perdue que le gain de qualité). **Aucune cascade testée**
(un seul levier validé sur 4, il en faut ≥2 selon la règle du prompt).

**Bilan final Stratégie B (toute la session)** : trailing 0,10× ADOPTABLE,
tout le reste rejeté au niveau fleet ou non mûr. B reste un chantier
ouvert avant un lancement A+B en parallèle (risque recalibré §5.5
bloquant, mécanisme corrélation §5.2 non trouvé).

---

## 6. Session 2026-08-19 soir/2026-08-20 — gisement métaux confirmé, moteur cascade A/B corrigé, lancement séquentiel B→A tranché

### 6.1 Gisement or/argent — EV confirmée, deux périmètres à ne pas confondre

Pipeline durée+trailing complet construit pour la première fois pour l'or/argent
(`or_argent_population_2026-08-19.py`, `gold_silver_yahoo_mapping_2026-08-19.py`).

| Périmètre | n | EV poolée | Usage |
|---|---|---|---|
| Pool complet (14 tickers GOLD/SILVER × 7 devises) | 934 | **+1,066R** | Population B Config0/Config2 complète |
| Sous-ensemble tradable Blueberry 5k$ (7 tickers : XAUUSD/GBP/EUR/AUD, XAGAUD/EUR/USD) | 480 | **+1,164R** | Population de lancement réelle (B_tradable) |
| ⚠️ **Ancienne mesure — NE JAMAIS RÉUTILISER** | — | +0,342R | Approximation sans trailing, obsolète, périmètre non documenté |

Le sous-ensemble tradable a une EV **légèrement supérieure** au pool complet (les 7
tickers non listés sur Blueberry — CHF/CAD/NZD — ont l'EV la plus faible, +0,962R) :
restreindre aux tickers exécutables ne coûte aucune qualité, seulement ~48,6% de
volume (934→480 trades métaux, 1505→1051 trades B total).

Couverture durée réelle (bougies H1) : 323/934 (34,6%) globalement, mais **0% avant
la fenêtre Yahoo de 730j** (~2024-07/08) — donc 100% fallback médiane sur toute
sous-période antérieure à cette date (bloc1/bloc2 du stress-test notamment). Testé
en robustesse (scale ×0,5-2,0 sur la durée fallback) : conclusions qualitatives
inchangées, mais écarts quantitatifs précis (ex. bloc1 29% vs 92%) sensibles à
cette hypothèse — ne jamais citer au point de pourcentage près sur ces
sous-périodes.

### 6.2 Moteur cascade double-flotte A/B officiel construit et validé

`chantier_ab_metaux_cascade_officiel_2026-08-19.py` — premier moteur combinant DEUX
flottes complètes à 5 firms (pas le moteur réduit 2-comptes utilisé jusqu'ici),
résout le point ouvert §4#14 (moteur A+B parallèle manquant). Base :
`dual_trader_2026-08-11.py` (architecture double-flotte, réserve séparée/plafond
personnel combiné) + mécaniques S1.8 à jour portées depuis
`chantier_S1_8_regen_population_2026-08-19.py` (bascule Blueberry Instant/Classic
dynamique, cap risque Instant 1,5%, any-RR).

**3 bugs trouvés et corrigés pendant la construction** (validation par comparaison
directe au module S1.8 authentique sur séquence de trades identique — résultats
identiques au $ près une fois corrigés) :
1. **`ALPHA_POST`/`BETA_POST` de A réutilisé pour B** — chaque tirage MC forçait le
   winrate de B vers ~40% (calibré sur A) au lieu de son vrai ~50,6%. Dérivation
   propre à la population B+métaux+routage : **Beta(762, 745)**, n=1505, winrate
   50,56% (`registre_parametres_projet.md` §9.6 documente le bug général et la
   dérivation 276/297 pour le périmètre B SANS métaux, n=571 — **périmètre
   DIFFÉRENT**, ne pas confondre). Pour la population B_tradable (1051 trades,
   métaux tradable Blueberry only) : **Beta(533, 520)**, winrate 50,62%.
2. **Ancrage calendaire commun appliqué même en mode A-seule** — décalait A de
   284,5 jours dans un préfixe de blocs vides (B démarre 2021-04, A 2022-01/02),
   gonflant `année1<0`. Corrigé : l'ancrage commun ne s'applique que si B
   participe réellement à la simulation.
3. **Ordonnancement des mécanismes de croissance** — portés depuis
   `dual_trader_2026-08-11.py` qui les exécutait avant le trade de l'événement, pas
   après comme S1.8 officiel. Corrigé pour matcher exactement l'ordre S1.8.

**Résultats sweep n=600, 4 plafonds, corrigés (A-seule vs Config2-AB pool complet
métaux)** :

| Plafond | A-seule profit | Config2-AB profit | A-seule solde_nég | Config2-AB solde_nég | corr(A,B) |
|---|---|---|---|---|---|
| 960$ | 6,82M$ | 18,98M$ | 0,83% | 4,67% | 0,60 |
| 1000$ | 6,83M$ | 19,77M$ | 0,50% | 3,33% | 0,63 |
| 3000$ | 7,09M$ | 21,65M$ | 0,50% | 1,33% | 0,65 |
| 5000$ | 7,12M$ | 22,00M$ | 0,17% | 0,17% | 0,68 |

`hit_ceiling` enfin discriminant (45%→3% selon plafond, jamais collé à 100% comme
dans le moteur réduit). Point de vigilance corrélation A/B confirmé réel (0,60-0,68,
positive, croît avec le plafond) mais l'inversion de signe observée en bloc1 dans
un run intermédiaire buggé (-0,36) **ne se reproduit pas** une fois les 3 bugs
corrigés — corrélation reste positive dans toutes les sous-périodes stress-testées
(0,11 à 0,58 selon régime).

### 6.3 ADX>32,27 et rr_tp1≤1,25-sizing — rejet reconfirmé, mécanismes causaux identifiés

Suite directe de §5.9 (rejet mesuré à fréquence B contrainte, 76,7% de A). Retesté
sous Config2 (fréquence B métaux+routage = 171,6% de A) : **rejet confirmé, la
contrainte de fréquence n'était pas la seule cause**. Mécanismes causaux distincts
identifiés par investigation (citations de code, session du 19/08 soir) :

- **ADX** : le segment exclu (adx>32,27) est statistiquement plus faible en
  moyenne/winrate MAIS **sur-représenté dans la queue de distribution** (×1,65 au
  top 5% par R alors qu'il ne pèse que 9,7% de la population) — couper ce segment
  ampute une part disproportionnée des gains extrêmes qui portent 44,8% du profit
  total en Monte Carlo.
- **rr_tp1-sizing** : le downsize ×0,7 touche 42,2% de la population mais
  n'affecte QUE le payoff, pas l'occupation de slot — `engine_multiformat.py:324`
  teste le plafond de positions AVANT tout calcul de risque, donc un trade
  downsizé occupe un slot pendant tout son `hold_seconds` exactement comme un
  trade plein, sans jamais libérer de capacité pour un meilleur trade. Contraste
  avec l'exclusion (ADX), qui retire le trade AVANT génération d'événement et
  libère réellement de la capacité.

**Leçon méthodologique généralisée (à appliquer à tout futur levier de sizing)** :
sous un cap de positions serré (`MAX_POSITIONS`), un sizing-réduit (garde le trade,
réduit juste le risque) sur un segment LARGE de la population peut coûter plus en
capacité perdue qu'il ne rapporte en qualité — même avec un écart d'EV brut propre
et statistiquement significatif. Un levier de sizing doit être jugé sur sa PORTÉE
(% de population touchée) autant que sur son écart d'EV, et comparé explicitement à
la variante "exclusion pure" du même segment (qui libère de la capacité, contrairement
au sizing).

### 6.4 MAX_POSITIONS — cap réouvert pour B, sweep effectué sur Config2-AB uniquement

Contredit partiellement le point §4#9 ("Fermé" 08/15, testé sur A seule) : **le
cap est nettement plus contraignant pour B Config2** que pour A. Replay 1-compte
chronologique (même méthode que §2.28) :

| Population | % bloqué par le cap | EV segment bloqué vs EV moyenne prise |
|---|---|---|
| A seule (post-fix, 742 trades) | 2,6% | +1,82R vs +0,80R (positif, cohérent avec le rejet §2.28) |
| B Config2 (1505 trades) | **6,4%** | **+1,83R vs +0,82R** (segment bloqué MEILLEUR que la moyenne prise) |

Sweep MAX_POSITIONS∈{3,4,5} sur Config2-AB (n=600, 3000$/5000$, moteur cascade
officiel corrigé) :

| Cap | Profit@3000$ | Profit@5000$ | cap_bloqué (B) |
|---|---|---|---|
| 3 (référence) | 21,65M$ | 22,00M$ | 6,4% |
| 4 | 23,46M$ (+8,4%) | 23,80M$ (+8,2%) | 1,0% |
| 5 | 24,03M$ (+2,4% vs 4) | 24,34M$ (+2,4% vs 4) | 0,1% |

Rendements décroissants nets (gain 3→4 » gain 4→5), cohérent avec `cap_bloqué` qui
s'approche de 0%. **PAS ADOPTÉ** — testé uniquement sur Config2-AB (pool métaux
complet), jamais sur B_tradable seule (population de lancement réelle) ni
confirmé en stress-test. Point ouvert, voir §7.

### 6.5 Lancement séquentiel B→A — décision actée

**Décision** : lancer **B_tradable seule en premier** (Config0, 1051 trades — 571
forex/indices rr_tp1<1,35 + 480 métaux tradable Blueberry), PAS A. Confirmé sur
tous les axes de risque, y compris en régime catastrophique (bloc1 : B_tradable
29-40% solde_négatif selon hypothèse de durée vs A-seule 92%, bloc2 : 32-38% vs
60-61%) — pas juste sur le profit moyen.

**A s'ouvre ensuite via seuil de trésorerie de B**, mécanisme construit sur mesure
(`try_sequential_activation`, `chantier_ab_metaux_cascade_officiel_2026-08-19.py`)
— PAS une réutilisation de `try_gft_delayed_trigger` (déclencheur temporel,
`chantier_pisteB_delayed_start_2026-08-17.py:413-417`), adapté du mécanisme de
seuil de réserve `pending_group_trigger` déjà utilisé pour débloquer les groupes
de firms. Capital de A décaissé au déclenchement réel (`handle_cost_hybrid`), PAS
pré-engagé à t=0 — vérifié par citation de code.

Sweep de seuils {2000$, 3000$, 5000$, 8000$, 12000$}, n=600, 3000$/5000$ : **tous
quasi équivalents** (17,74M$-18,03M$, <2% d'écart sur toute la plage), **seuil
3000$ légèrement en tête** (année1<0 le plus bas). L'essentiel du gain vient
d'ouvrir A à UN MOMENT OU UN AUTRE (vs B_tradable seule pour toujours, 10,23M$),
pas du réglage fin du seuil.

**Comparaison directe Config2-jour0 vs Séquentiel-3000$** (même population 7
tickers, mêmes fenêtres bloc1/bloc2 vérifiées identiques au calcul près) :
hypothèse de départ ("jour0 protège mieux en régime dégradé") **NON CONFIRMÉE** —
écarts de ~2pp dans les deux sens selon la sous-période (bloc1 : jour0 37% vs
séquentiel 39% ; bloc2 : jour0 52% vs **séquentiel 50%**, séquentiel légèrement
meilleur). **Le seuil 3000$ préserve à la fois l'économie de trésorerie ET la
protection de régime** — pas un compromis entre les deux.

**Recommandation opérationnelle** : ouvrir B_tradable (Config0, 7 tickers) en
premier ; ouvrir A quand la trésorerie de B atteint ~3000$ ; router les métaux
B→A dès l'ouverture de A (overflow actif, décision utilisateur).

### 6.6 Leçon méthodologique — fenêtres de sous-période non alignées entre scénarios

Bug trouvé en cours de session (pas dans le moteur, dans les scripts d'ANALYSE) :
`date_subperiods_single()` (moteur single-fleet, scénarios de lancement solo)
calculait les bornes de bloc1-4/H1-H2 à partir des dates propres à CHAQUE
population testée, au lieu d'une grille calendaire commune. Résultat : comparer
"bloc2 de B_tradable" à "bloc2 d'A-seule" comparait deux **régimes de marché
différents** (fenêtres décalées de ~7 mois), pas la même période. Corrigé
(`common_calendar_bounds()`, ancrage sur `pop_A_config0 ∪ pop_B_config0`
14-tickers, identique à `date_subperiods()` du moteur double-flotte déjà correct).
**Vigilance pour tout futur script single-fleet comparant plusieurs scénarios par
sous-période : toujours vérifier/imposer une grille calendaire commune, ne jamais
laisser chaque scénario calculer ses propres bornes indépendamment.**

### 6.7 Pas de coupure indices sur la fenêtre midterm US 2026 (mi-août → 3 novembre) — décision actée (08/23)

**Annule/remplace** une "coupure indices pendant la fenêtre midterm" évoquée
en session du 21/08 mais **jamais formalisée dans ce registre** (aucune
trace trouvée par recherche systématique — confirmé avant d'écrire cette
entrée).

**Contexte** : un test interne antérieur (session 21/08, script jamais
commité au repo) avait mesuré un écart EV significatif défavorable sur une
fenêtre forex "midterm US 2022" (18/08→08/11/2022, p=0,0105, mécanisme
apparent "gains plafonnés"). Ce test datait d'AVANT la correction du bug
r_trailing (commit `df261dc`, 21/08 soir) et portait sur une fenêtre
entièrement contenue dans bloc1/bloc2 — la portion 100% exposée au bug
(plafonnement artificiel du gain trailing pour tout trade antérieur à la
limite yfinance de 730j). Le mécanisme trouvé à l'époque est la signature
exacte du bug. Rejoué le 23/08 sur données corrigées
(`chantier_midterm2022_retest_2026-08-23.py`) :

- **Forex** (n=21) vs reste de bloc2 (n=91) : EV midterm=+2,13R vs
  +1,05R, delta=+1,08R, **Welch p=0,24 / Mann-Whitney p=0,31** —
  indiscernable du régime bloc2, pas de signal défavorable.
- **Indices** (n=6) vs reste de bloc2 (n=42) : EV midterm=+5,33R vs
  +1,03R, delta=+4,30R, **Mann-Whitney p=0,054** (limite, non
  significatif uniquement du fait de n=6) — direction favorable, pas
  défavorable.
- **Or/argent** (n=25) vs reste de bloc2 (n=79) : EV midterm=+3,93R vs
  +2,26R, delta=+1,66R, **p=0,31-0,50** — non significatif, direction
  favorable.
- Vs baseline global (plutôt que reste de bloc2 seul), même verdict sur
  les trois classes d'actifs : le résultat original (p=0,0105,
  défavorable) a disparu ET s'est inversé de signe post-correction.

**DÉCISION ACTÉE** : pas de coupure indices pour la fenêtre midterm US
2026 (mi-août → 3 novembre 2026). Indices tradables sur toute la fenêtre,
au même titre que forex et métaux.

**Rationale consignée explicitement** : la littérature externe (chop
pré-midterm) reste un risque qualitatif valide en soi, mais le seul test
chiffré sur données propres du projet ne le soutient pas — la direction
disponible (non significative, n=6 sur indices) pointe vers une EV
favorable, pas défavorable. Décision prise en connaissance de cette
incertitude statistique (n=6 est petit), jugée acceptable au vu de la
marge d'EV mesurée (+4,30R indicatif).

**Limite structurelle rappelée** : un seul cycle midterm US couvert par
les données du projet (2018 hors couverture historique du signal
Lutessia) — même ce résultat propre reste un indice qualitatif sur n=1
cycle électoral, pas une règle statistiquement validée au sens
fréquentiste standard (impossible de construire une distribution
d'échantillonnage inter-cycles avec un seul cycle observé).

**CONDITION DE RÉOUVERTURE EXPLICITE** — cette décision doit être
reconsidérée si :
  (a) le monitoring live (une fois les comptes lancés) montre une
      sous-performance des trades indices spécifiquement sur la fenêtre
      27/08→03/11/2026, par rapport aux bandes p10/p50/p90 Monte Carlo
      établies (méthode du 18-19/08) ;
  (b) un choc macro externe majeur et inattendu (hors whipsaw Fed déjà
      anticipé, Jackson Hole/FOMC) survient sur la fenêtre ;
  (c) un futur re-test avec plus de puissance statistique (cycles
      midterm supplémentaires accumulés dans le temps) infirme le
      signal directionnel favorable observé ici.

Scripts/logs : `chantier_midterm2022_retest_2026-08-23.py`,
`chantier_midterm2022_retest_log_2026-08-23.txt`,
`chantier_midterm2022_retest_detail_2026-08-23.csv`. Mémoire projet :
`project_midterm2022_retest_artifact_confirmed_2026-08-23.md`.

---

### 6.8 Risque de casse du pivot sous choc carry-unwind (08/24) — ce n'est PAS "les chocs sont sans danger", c'est "la composition du panier de départ compte plus que l'événement macro"

**⚠️ Titre correct à préserver, contre une lecture erronée facile** : le
résultat brut mesuré (choc forcé = risque de casse du pivot RÉDUIT, pas
augmenté, n=600, z jusqu'à -5,82, cf.
[[project_pivot_carryunwind_risk_2026-08-23]]) **ne veut PAS dire** "les
chocs macro ne sont pas dangereux pour le pivot" — une citation future de
ce type serait une lecture fausse.

**Mécanisme réel** : le 1er bloc de 2 mois typique tiré au hasard dans B
est souvent dominé par le cluster métaux fortement corrélés (or/argent/
platine/palladium, corr 0,52-0,94, §2.35 — cf.
[[project_s235_ab_divergence_mechanism_2026-08-23]]) — un vrai risque de
CONCENTRATION. Le choc carry-unwind (mix équilibré 53% métaux/47% forex,
proche de la composition moyenne de B) est accidentellement PLUS
diversifié qu'un démarrage aléatoire moyen. Le choc dégrade bien l'EV
brute (-1,65R/-1,79R sur A/B, confirmé le même jour,
[[project_omicron_detail_et_carry_unwind_2026-08-23]]) — mais ce risque de
dégradation d'EV est structurellement MOINS dangereux pour la solvabilité
du pivot que le risque de concentration d'un panier de métaux corrélés qui
perdent tous ensemble.

**Implication pour le calendrier réel (Jackson Hole 28/08, FOMC 15-16/09)** :
le facteur de risque n'est pas temporel ("y a-t-il un choc macro ce
jour-là") mais COMPOSITIONNEL ("quelle est la diversification des tickers
que Lutessia signale effectivement cette semaine-là"). Une semaine de choc
macro à composition équilibrée est moins dangereuse pour le pivot qu'une
semaine calme à composition concentrée métaux. La vigilance à avoir n'est
donc pas une question de date, mais de composition mesurable en temps réel
des tout premiers trades d'un compte qui vient d'ouvrir.

**Piste structurelle ouverte par cette lecture** (notée ici, PAS testée,
distincte des Piste 2/3 déjà closes — cf.
[[project_piste2_confluence_retest_rejected_2026-08-22]] et
[[project_diagnostic_chop_bloc2_diffus_2026-08-23]]) : plafonner
l'exposition corrélée dans les tout premiers trades d'un compte qui vient
d'ouvrir (ex. ne pas laisser 2-3 métaux du même cluster représenter la
totalité du portefeuille initial). Moins fragile que Piste 2/3 car elle ne
cherche pas à prédire un événement macro à l'avance — elle contrôle une
composition mesurable en temps réel. Pas urgent, mais à garder en tête si
le sujet du risque de lancement revient.

Voir [[project_pivot_carryunwind_risk_2026-08-23]] pour le détail chiffré
complet (8 configs, n=600).

---

## 7. Points ouverts pour la prochaine session (19-20/08)

1. 🔴 *(ouvert)* MAX_POSITIONS∈{4,5} testé UNIQUEMENT sur Config2-AB (§6.4) —
   jamais sur B_tradable seule (la population de lancement réellement décidée,
   §6.5). Le mécanisme causal (cap_bloqué élevé + EV du segment bloqué positive)
   devrait transposer, mais non vérifié. À faire avant d'adopter un cap>3 pour de
   bon.
2. 🟡 *(ouvert)* Reconnaissance copper/autres matières premières Blueberry — risque
   de parsing sur des noms de contrats futures datés (pattern jamais vérifié pour
   ces instruments, contrairement à GOLD/SILVER dont le mapping est validé §6.1).
   À vérifier avant tout scraping/pipeline sur d'autres matières premières.
3. ✅ *(clos par cette session, contrairement à une première formulation)*
   `ALPHA_POST_B`/`BETA_POST_B` POUR LA POPULATION B_TRADABLE SPÉCIFIQUEMENT —
   déjà dérivé et vérifié séparément (Beta(533,520), §6.2 point 1), pas juste
   hérité du périmètre sans métaux (276/297) ni du pool complet (762/745). Les 3
   dérivations sont distinctes et documentées, aucune confusion résiduelle connue.
4. 🟡 *(ouvert)* Stress-test MAX_POSITIONS∈{4,5} — non fait (dépend du point 1).
5. 🟡 *(ouvert)* Cascade combinant plusieurs leviers adoptés cette session-ci et
   les précédentes (trailing 0,10× B + Config2/lancement séquentiel + éventuel
   MAX_POSITIONS>3) — jamais testée ensemble, seulement isolément.
