# Contexte projet trading Lutessia — au 5 août 2026

Ce fichier sert de mémoire de reprise pour Claude (claude.ai). Il résume l'intégralité du
projet à date : stratégie verrouillée, bugs trouvés et corrigés, chiffres de référence
actuels, décisions prises, et le sujet en cours de traitement.

---

## 1. Le projet en une phrase

Bot de trading automatisé (Python, VPS) qui lit les signaux e-mail de "Lutessia"
(CentralCharts), calcule le R:R, et exécute en copytrade sur une flotte de comptes prop
firm (forex, MT5). Objectif : générer un revenu significatif avec un capital de départ
très limité (~2000€), en acceptant une stratégie agressive (casses de comptes fréquentes
assumées, rachat systématique).

---

## 2. Décisions de stratégie verrouillées

- **Filtre d'entrée** : R:R ≥ 1,5 (rr_tp1)
- **Sortie** : TP2 avec trailing stop post-TP2 à 0,2× la distance SL initiale (validé,
  gain net +10-11% vs TP2 sec)
- **Actifs** : 14 paires forex. Pas de filtre horaire (session asiatique testée et
  rejetée — coûte plus en volume que ça ne rapporte en stabilité)
- **Mode de compte** : COPYTRADE sur plusieurs comptes / plusieurs firms distinctes
  (même signal répliqué)
- **Philosophie centrale** : stratégie AGRESSIVE assumée. On ne compte PAS sur le
  scaling interne d'un compte (palier qui grossit organiquement) — on retire les
  profits régulièrement et on rachète des comptes plus gros à côté avec la réserve
  poolée. Les casses de comptes sont normales et budgétées, pas un échec.
- **Sécurité opérationnelle déjà en place** : plafond de positions simultanées par
  compte + seuil de corrélation 0,6 + règle JPY-JPY explicite (indépendante du
  coefficient calculé). Coupe-circuit news (retarde une entrée, jamais une position déjà
  ouverte). monitor.py tourne en service Windows (NSSM) sur le VPS, survit aux
  redémarrages.
- **Bot déjà testé en compte démo** — le pipeline logiciel (parsing email, calcul,
  exécution, trailing) est validé de bout en bout. Ce qui reste à tester uniquement sur
  un compte réel : slippage/spread réels, comportement broker en conditions live,
  mécaniques spécifiques de la prop firm (rollover, DD journalier réel).

---

## 3. Bugs découverts et corrigés depuis le début du projet (par ordre chronologique)

Chaque bug a été trouvé par vérification indépendante du code, pas en faisant confiance
aux chiffres rapportés — c'est la discipline centrale du projet ("ne jamais accepter un
résultat trop beau sans vérification croisée").

1. **Bug TP1/TP2** : le statut Lutessia "OBJECTIF ATTEINT" signifie TP1 atteint, pas
   TP2. La continuation jusqu'à TP2 doit être vérifiée via yfinance — ~14% des cas
   vérifiables n'atteignent pas TP2. Payoff réaliste = rr_tp2 si continuation confirmée,
   sinon rr_tp1. Ce bug était encore présent dans `backtest_analyzer.py` (script jamais
   corrigé alors que le correctif existait ailleurs) — écart mesuré : winrate 37,3%
   identique, mais R:R moyen des gagnants naïf 5,77 vs corrigé 3,89 (le 3,89 est
   lui-même une convention antérieure, voir point 8 ci-dessous pour la valeur actuelle).
2. **Biais bootstrap par permutation** : la permutation mélangeait l'identité des
   trades tout en gardant les dates, détruisant le regroupement temporel réel des
   séquences de pertes. Remplacé par un **block bootstrap** (blocs contigus de 2 mois),
   qui préserve la vraie structure de clustering. Effet : augmente le pire cas de
   trésorerie (la permutation sous-estimait le risque de queue).
3. **Réserve non poolée → poolée** : l'ancien modèle donnait à chaque compte sa propre
   cagnotte séparée. Corrigé : une seule réserve commune alimentée par 80% des gains de
   n'importe quel compte, utilisable pour racheter n'importe quel compte (reflète la
   réalité : même personne, même argent). Effet isolé : -27 577€ sur le pire cas de
   trésorerie Phase 1 (le plus gros effet des trois corrections liées au bug des 21972€).
4. **Mécanisme d'immunité** : dès qu'AU MOINS un des comptes de la flotte a été financé
   une première fois, plus aucun rachat futur ne tape dans le budget personnel — absorbé
   par la capacité de gain déjà démontrée. Effet isolé : -17 621€ sur le pire cas.
   Résultat cumulé de ces 3 corrections (bootstrap+pooling+immunité) : pire cas de
   trésorerie Phase 1 passé de 21 972€ (ancienne méthodo) à 2 997€ (voir aussi bug #5).
5. **Bug des 999€ initiaux non comptés** : l'achat initial des 3 premiers challenges
   (999€ combinés) n'était pas inclus dans `real_cash_paid` dans une version
   intermédiaire des scripts. Une fois corrigé : pire cas de trésorerie Phase 1 = 2 997€
   (valeur définitive, remplace tout chiffre antérieur à 2 997€ comme 1 998€).
6. **BUG MAJEUR — comptabilité challenge vs financé** : `monte_carlo_simulation.run_one`
   comptait TOUT le P&L de trading comme profit réel, y compris pendant les phases de
   challenge (avant financement) — argent qui n'existe pourtant pas réellement tant que
   le compte n'est pas financé. Ce bug avait déjà été corrigé ailleurs dans le projet
   (`sizing_fleet_test.py`) mais jamais propagé au script produisant les chiffres de
   référence historiques. Impact : ce bug SEUL explique 106% de l'écart entre les
   anciens chiffres de référence (2,63M€ à 13,39M€ sur l'horizon complet) et les
   chiffres corrigés — soit une SURESTIMATION de 30 à 40% du profit selon le niveau de
   risque. Corrigé partout, tous les fichiers dérivés régénérés. **Les anciens chiffres
   2,63M€-13,39M€ sont définitivement obsolètes.**
7. **Découverte structurelle liée (seuil de bascule à 5000€ obsolète)** : sous l'ancien
   modèle (réserve non poolée, sans immunité), retarder la bascule de 0,5% vers 2% de
   risque jusqu'à 5000€ de réserve avait un vrai rôle protecteur. Sous le modèle corrigé
   (poolée + immunité), ce n'est plus vrai : le pire cas de trésorerie est **strictement
   identique (2997€) quel que soit le seuil choisi** (testé de "immédiat" à 10 000€,
   vérifié run-par-run sur 2000 simulations, 0 divergence). Le risque de trésorerie est
   entièrement déterminé par la phase pré-financement, invariante au seuil. **Décision
   verrouillée mise à jour : bascule immédiate au premier financement d'un compte de la
   flotte, plus de seuil de réserve à 5000€.** Gain : +23% de profit année 1 par rapport
   à l'ancien seuil à 5000€, pour la même exposition de trésorerie.
8. **BUG MAJEUR (découvert le 5 août) — absence de daily drawdown dans les
   simulations** : grep confirmé sur tout le repo — AUCUN script de simulation ne
   modélisait la limite de perte JOURNALIÈRE des prop firms (différente du DD max
   trailing à 10%, qui lui était bien modélisé via `BREAK_DD_PCT=10.0`). Seuils réels
   confirmés par firm : **The5%ers 3% journalier**, **FTMO 5% journalier**, **Blueberry
   Funded 5% journalier** (tous avec 10% de perte max). Sur la trajectoire réelle
   (100k/2%), ajouter la limite journalière fait passer les casses de 17 à 29 (+70,6%).
   3 moteurs corrigés et relancés : `regime_abc_comparison_dailydd.py`,
   `the5ers_summer_100k_N_accounts_dailydd.py`, `three_firm_fleet_dailydd.py`.

---

## 4. Chiffres de référence ACTUELS (post-correction daily DD, les plus à jour)

⚠️ Toute mention antérieure de ces chiffres sans le suffixe "_dailydd" ou sans
précision de date doit être considérée comme obsolète.

### Régimes de risque comparés (structure historique 3 comptes, croissance 50k→200k→500k)
Trois régimes testés : **A** = 2% de risque dès le trade 1 ; **B** = hybride amélioré
(0,5% pendant challenge, bascule immédiate à 2% au premier financement, SANS seuil de
réserve) ; **C** = ancien hybride (0,5%, bascule à 2% seulement à 5000€ de réserve) —
**C est strictement dominé par B, à abandonner**.

Daily DD FTMO/Blueberry = 5% (impact de la correction quasi nul ici, -0,7 à -1,5%
seulement, le seuil 5% étant déjà proche de ce qu'impliquait le DD trailing 10%).

| | Winrate 37,29% | Winrate 32% (stress-test bayésien, P10) |
|---|---|---|
| A — profit an1 moy | +1 556 782$ | +837 128$ |
| A — profit horizon complet (~3,96 ans) | +7 737 939$ | +4 603 339$ |
| A — P(perte) an1 | 4,65% | 16,00% |
| A — cash pire cas | 9 990$ | 10 989$ |
| B — profit horizon complet | +7 432 036$ | +4 374 031$ |
| C — profit horizon complet | +7 068 040$ | +4 087 235$ |

Casses (horizon complet), winrate 37,29% : A=48,11 / B=44,94 / C=40,96 (avant correction
daily dd — à mettre à jour légèrement mais l'ordre de grandeur reste indicatif).

**Winrate de référence** : mesuré sur 472 trades historiques = **37,29%** (IC95%
[32,9%,41,7%]). Mise à jour bayésienne après un stress-test "15 trades réels tous
perdants" → winrate postérieur médian 36,1%, P10 = 32% (c'est CE chiffre à 32% qui sert
de scénario défavorable réaliste dans toutes les simulations, PAS 28% qui était un calcul
fréquentiste naïf erroné ignorant le poids de l'échantillon historique).

**R:R moyen des gagnants actuel (convention r_trailing, avec le trailing stop 0,2×SL)** :
4,115 (référence) / 4,164 (32%) / 4,226 (28%, obsolète) — stable, pas de corrélation
winrate↔ampleur des gains détectée.

**Slippage réel mesuré** (469 trades, données tick Dukascopy) : moyenne -0,91 pip,
médiane -0,70 pip, écart-type 2,85 pips. Impact sur l'EV : +0,907R (sans) → +0,850R
(avec), soit -6,3%. Impact sur le profit net : -6,9% à -13,3% selon le régime de risque.
N'affecte quasiment pas le pire cas de trésorerie Phase 1 (2997€ stable). SL serrés (Q1)
2x plus touchés par le slippage relatif que SL larges (Q4) : 10,24% vs 4,57% d'impact.

**Décision A vs B (2% direct vs hybride amélioré)** : l'utilisateur a tranché en faveur
de **A (2% direct)**. Raisonnement : A domine sur profit ET sur P(perte) à tous les
niveaux (P(perte) 2 à 4x plus faible que B/C), au prix d'un pire cas de trésorerie plus
élevé (~10-11k$ vs ~3-5k$ pour B). Vérification faite : même dans les runs qui touchent
ce pire cas de trésorerie, l'année finit positive dans 80-90% des cas (pas de lien fort
entre "beaucoup de cash sorti" et "année ratée" — sauf exceptions rares et non
systématiques). L'utilisateur accepte ce risque de queue (probabilité ≤0,1-3,75% selon
le seuil) car il juge sa capacité de mobilisation de cash de secours suffisante.

---

## 5. Structure de flotte / prop firms — décisions et points ouverts

### Firms retenues (historique, avant l'offre Summer Plan)
- **FTMO** : retenu, compte Swing obligatoire (détention week-end), pas de clause
  anti-signaux tiers trouvée
- **The5%ers** : retenu, programme scaling jusqu'à 4M€ théorique
- **Blueberry Funded** : retenu (remplace Alpha Capital, écarté pour clause
  "signal following" jamais levée), adossé à un broker régulé ASIC

### Plafonds de capital combiné pour la copie inter-comptes (CONFIRMÉS, sources
officielles/support direct)
- **The5%ers** : 500 000$ cumulés, tous programmes confondus, **mais le plafond ne
  s'applique QU'AU CAPITAL FINANCÉ, pas au capital en évaluation/challenge** (confirmé
  par le support The5%ers, agent "Zoe", par écrit). Donc on peut lancer N comptes en
  challenge simultanément sans restriction, la limite ne joue qu'une fois financés.
  Le Summer Plan (voir ci-dessous) est classé "Instant Funding" (pas "Bootcamp" — la
  copie entre 2 comptes Bootcamp est interdite, mais Instant Funding/High Stakes n'ont
  pas cette restriction).
- **FTMO** : ~400 000$ combiné (source tierce, pas encore confirmée par le support
  directement)
- **Blueberry Funded** : ~400 000$ combiné (source tierce, pas encore confirmée)

### L'offre "Summer Plan" The5%ers (juillet-août 2026, durée limitée non précisée)
Comptes 100k$ à prix cassé : 1-Step 249$, 2-Step 10/5 149$, 2-Step 8/5 **179$ (variante
retenue, cohérente avec la méthodologie Phase 1 du projet)**. Jusqu'à 6 comptes
possibles selon la page marketing, mais **la page officielle précise aussi "up to 2
accounts at once" par type d'évaluation — AMBIGUÏTÉ NON RÉSOLUE, à clarifier avec le
support avant achat** (est-ce que ça limite à 2 comptes actifs au total, ou 2 par lot
d'achat ?). Levier 1:100 (pas 1:30 comme utilisé dans les calculs de contrainte de
faisabilité antérieurs — à revérifier). **Règle de consistency à 50% s'active sur le
2-Step UNE FOIS FINANCÉ** (pas pendant l'évaluation) — point de vigilance réel pour la
stratégie du projet, qui produit des trades ponctuels à très fort R:R (10-13R observés).

### Structure de flotte retenue (décision en cours de finalisation)
- **The5%ers** : 4 comptes de 100k$ (Summer Plan 2-Step 8/5), **taille FIXE, jamais
  upgradés** — pas de scaling interne dessus (cohérent avec la philosophie du projet).
  Total 400k$, confortablement sous le plafond de copie à 500k$ même avec de la
  croissance ailleurs. Coût d'entrée total ~716$ (4×179$).
- **FTMO** : comptes qui reçoivent la croissance (rachat de comptes plus gros via la
  réserve poolée, palier 200k atteignable, palier 500k théoriquement impossible seul
  car dépasse le plafond combiné de 400k$)
- **Blueberry Funded** : idem, reçoit une partie de la croissance
- **Répartition testée pour la "croissance"** : 2 comptes FTMO + 1 compte Blueberry.
  **Découverte importante** : le palier 500k devient INATTEIGNABLE dans cette
  architecture (un seul compte à 500k dépasse à lui seul le plafond de 400k de
  n'importe quelle firm) — seul le palier 200k reste accessible. ~850 tentatives
  d'upgrade bloquées par run dans les simulations. Ceci fait perdre une part
  significative du profit par rapport à l'ancien modèle sans plafond (delta négatif
  net malgré l'ajout de comptes The5%ers).

### Chiffres de la flotte à 3 firms (POST-correction daily DD, les plus à jour)
Daily DD appliqué : The5%ers 3%, FTMO/Blueberry 5%.

| | Winrate 37,29% | Winrate 32% |
|---|---|---|
| Profit an1 moyen | +1 151 418$ | +658 276$ |
| Profit horizon complet moyen | +5 372 936$ | +3 215 356$ |
| P(perte) an1 | 2,70% | 11,25% |
| Cash pire cas | 20 014$ | 21 446$ |
| Casses moy. (horizon) | 164,3 | 200,0 |

Le segment The5%ers (daily DD 3%, le plus strict) tire l'ensemble vers le bas : sur
The5%ers seul, la correction daily DD fait chuter le profit final de 10 à 15%, et
augmenter les casses de ~65%, et le pire cas de trésorerie de 40-45%.

**Croisement cash sorti × résultat net (flotte 3 firms, post-correction)** : le pire
cas absolu de trésorerie (20-21k$) ne finit PAS systématiquement en négatif — 6/7 runs
(37,29%) et 8/10 runs (32%) qui dépassent 15 000$ de cash sorti finissent quand même
positifs. Mais un run à 19 298$ finit à -87 743$ (pas un accident de casses extrêmes,
juste dans la moyenne) — donc pas une garantie absolue. Fréquence de dépasser 10 000$ :
2,45-3,75% des runs (environ 1 run sur 25-27, pas un cas exceptionnel).

---

## 6. SUJET EN COURS — non résolu, réponse attendue de Claude Code

**Problème posé** : le nouveau pire cas de trésorerie de la flotte 3 firms (20-21k$,
post-correction daily DD) dépasse le repère de ~10k$ que l'utilisateur jugeait
acceptable. Le daily DD strict de The5%ers (3%, contre 5% pour FTMO/Blueberry) est
identifié comme la cause principale de cette dégradation. Question ouverte : The5%ers
reste-t-il un bon choix dans la flotte, sous quelle forme, ou faut-il l'écarter ?

**Éléments déjà avancés par l'utilisateur à considérer** :
- Il existe un vrai avantage économique brut à prendre 4 comptes 100k Summer Plan
  (~650-720$) plutôt que 3 comptes 50k classiques (~1000-1500$), surtout en tout début
  de projet.
- Possibilité de faire tourner The5%ers à risque réduit au démarrage (moins de casses
  potentiellement) puis de passer à 2% ailleurs / abandonner The5%ers ensuite.
- Idée d'utiliser The5%ers comme "tremplin" (collecte de données Phase 1 à bas coût)
  plutôt que comme pilier permanent de la flotte à 2% de risque.

**6 scénarios ont été demandés à Claude Code pour trancher** (prompt déjà envoyé,
réponse en attente au moment de la rédaction de ce fichier) :
1. Sensibilité au seuil — recalculer The5%ers avec un daily DD hypothétique à 5% (au
   lieu de 3% réel) pour isoler l'effet du seuil seul
2. Risque réduit sur The5%ers uniquement (1% et 0,5% au lieu de 2%), daily DD réel 3%
3. The5%ers comme tremplin Phase 1 uniquement (risque réduit puis abandon/mise en
   veille, croissance principale exclusivement sur FTMO+Blueberry à 2%)
4. Sizing contraint par le DD journalier (viser que l'exposition cumulée théorique sur
   plusieurs positions reste sous 3%, plutôt que 2% par trade sans contrainte croisée)
5. Réduction du plafond de positions simultanées sur The5%ers (1 au lieu de 2-3)
6. Comparaison brute du coût d'entrée 4×100k Summer Plan vs 3×50k classique, à
   risque/casses identiques, pour objectiver l'avantage économique indépendamment du
   problème daily DD

**Action attendue de l'utilisateur** : coller ici la réponse de Claude Code à ces 6
scénarios une fois reçue, pour que Claude (claude.ai) l'analyse et aide à trancher sur
la configuration finale de The5%ers dans la flotte (l'écarter, le garder à risque
réduit permanent, ou le garder en tremplin temporaire).

---

## 7. Autres points encore ouverts (non urgents, pour mémoire)

- Confirmer avec FTMO et Blueberry Funded leur plafond de copie exact (actuellement
  seulement des sources tierces, ~400k$ chacun, pas de confirmation écrite directe
  comme obtenue pour The5%ers)
- Clarifier avec le support The5%ers l'ambiguïté "up to 2 accounts at once" du Summer
  Plan avant d'acheter les 4 comptes prévus
- Explorer des firms alternatives à plus haut plafond de capital combiné pour le
  segment croissance (FundedNext, Ment Funding mentionnés comme pistes, non vérifiées
  — sources tierces uniquement, chiffres à confirmer avant toute décision)
- Lancer la Phase 1 réelle (10-15 trades) dès que la structure de flotte est finalisée
- Vérifier si les scripts de simulation utilisent bien le levier 1:100 (Summer Plan) et
  non 1:30 dans le calcul de la contrainte de faisabilité de marge
- Score "Force" Lutessia : toujours pas capturé dans le pipeline live, à ajouter dans
  scraper.py/app.py pour capture future
- Frais de swap/rollover : toujours pas intégrés au modèle de coût
- Risque de gap le week-end : toujours pas quantifié

---

## 8. Fichiers de référence sur le repo (état au 5 août 2026)

**À jour / à utiliser** :
- `regime_abc_comparison_dailydd.py` et CSV associés
- `the5ers_summer_100k_N_accounts_dailydd.py` et CSV associés
- `three_firm_fleet_dailydd.py` et CSV associés
- `session_summary_2026-08-01.md` et `session_summary_2026-08-05.md` (sur le repo)

**Obsolètes / buggés, à ne plus utiliser comme référence** :
- `risk_levels_trailing_02_summary.csv`, `risk_levels_trailing_summary.csv`,
  `risk_levels_realistic_summary.csv` (versions pré-correction comptabilité
  challenge/financé)
- `copytrade_vs_fleet_*_summary.csv` (idem)
- Toute version de `monte_carlo_simulation.py` / `copytrade_simulation_test.py` /
  `year1_breakdown_trailing_02.py` antérieure aux corrections listées en section 3
- Tout chiffre citant 21 972€ comme pire cas de trésorerie (obsolète, remplacé par
  2 997€ puis par les chiffres post-daily-DD de la section 4)
- Tout chiffre citant 2,63M€ à 13,39M€ comme profit de référence horizon complet
  (surestimation de 30-40%, bug comptabilité challenge/financé)
- Les versions de `regime_abc_comparison.py` / `the5ers_summer_100k_N_accounts.py` /
  `three_firm_fleet_test.py` SANS le suffixe `_dailydd` (ne modélisent pas la limite
  journalière)
