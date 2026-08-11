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

### 2.9 Filtre news (calendrier ForexFactory) — BACKTEST PARTIEL 08/11, DONNÉES INSUFFISANTES POUR TRANCHER

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
