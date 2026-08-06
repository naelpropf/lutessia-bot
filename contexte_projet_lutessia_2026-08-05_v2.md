# Contexte projet trading Lutessia — mise à jour du 5 août 2026 (soir)

Ce fichier remplace `contexte_projet_lutessia_2026-08-05.md` comme mémoire de reprise.
Il reprend tout ce qui était déjà validé, ajoute les 4 points explorés dans la session
du soir (Régime A vs flotte, or/indices, FXIFY/Ment Funding, trésorerie dormante),
et surtout **acte une correction de trajectoire importante** (section 0) qu'il faut
lire en premier avant toute décision de structure de comptes.

---

## 0. ⚠️ CORRECTION DE TRAJECTOIRE — À LIRE EN PREMIER

Dans la session du 5 août (soir), l'exploration de nouvelles firms (FXIFY, Ment
Funding) et de structures à comptes multiples a produit des chiffres de pire cas de
trésorerie personnelle de **82 000$ à 99 000$** — soit 30 à 35 fois le seuil que le
projet avait lui-même fixé comme acceptable au départ (~3 000€, voir section 2).
Personne ne s'est arrêté pour comparer ces chiffres au repère de départ avant qu'ils
soient signalés comme absurdes.

**Décision actée : ces structures (comptes fixes multiples, FXIFY, Ment Funding) ne
sont PAS écartées sur le fond — leur intérêt économique est réel et confirmé
(+22,9% à +78,9% de profit selon la structure). Mais elles sont repoussées à une
phase ULTÉRIEURE du projet, déclenchée par un seuil de réserve largement
confortable (à définir précisément, de l'ordre de 5 à 10x le pire cas de trésorerie
initial, PAS un seuil de type "20-50k$" évoqué en cours de session), pas prises
comme structure de départ.**

**Principe qui doit gouverner toute décision de structure de comptes à partir de
maintenant** : tant que la trésorerie en jeu est personnelle (avant qu'un compte de
la flotte ait été financé une première fois), la priorité absolue est de minimiser
le pire cas de cash, pas de maximiser le profit théorique. Une fois l'argent en jeu
devenu celui déjà généré par le projet (mécanisme d'immunité, voir section 3, bug
#4), on peut recommencer à évaluer des structures plus agressives.

**Le plan de lancement réel reste celui de la section 2 : budget 1000-2000€, 3
comptes/firms à taille standard (50k FTMO/Blueberry, ou 4×100k Summer Plan
The5%ers), pire cas de trésorerie visé ~3 000€.**

---

## 1. Le projet en une phrase

Bot de trading automatisé (Python, VPS) qui lit les signaux e-mail de "Lutessia"
(CentralCharts), calcule le R:R, et exécute en copytrade sur une flotte de comptes
prop firm (forex, MT5). Objectif : générer un revenu significatif avec un capital de
départ très limité (~2000€), en acceptant une stratégie agressive (casses de comptes
fréquentes assumées, rachat systématique) — **mais une stratégie agressive sur le
trading, pas sur l'engagement de trésorerie personnelle** (voir section 0).

---

## 2. Décisions de stratégie verrouillées (trading)

- **Filtre d'entrée** : R:R ≥ 1,5 (rr_tp1)
- **Sortie** : TP2 avec trailing stop post-TP2 à 0,2× la distance SL initiale
  (gain net +10-11% vs TP2 sec)
- **Actifs** : 14 paires forex uniquement. Pas d'or, indices limités et non
  exploitables à ce jour (voir section 4, point 2), pas de filtre horaire (testé,
  rejeté)
- **Mode de compte** : COPYTRADE sur plusieurs comptes / plusieurs firms distinctes
- **Risque par trade** : 2% (Régime A confirmé comme dominant B et C — meilleur
  profit ET meilleure P(perte), au prix d'un pire cas de trésorerie plus élevé que
  B/C mais qui reste dans une fourchette gérable ~10-11k$ sur ce régime précis, à ne
  pas confondre avec les scénarios FXIFY/comptes fixes qui explosent ce chiffre)
- **Structure de départ** : 3 comptes/firms distinctes (FTMO Swing, The5%ers, Blueberry
  Funded), scaling classique 50k→200k→500k, réserve poolée à 80% des gains,
  bascule immédiate à 2% dès le premier financement (plus de seuil à 5000€, voir
  bug #7 ci-dessous)

**Sécurité opérationnelle déjà en place** : plafond de positions simultanées par
compte, seuil de corrélation 0,6 + règle JPY-JPY explicite, pause automatique si DD
≥5-6%, coupe-circuit news (retarde une entrée, jamais une position déjà ouverte),
monitor.py en service Windows (NSSM) sur le VPS, contrainte de faisabilité marge
1:30/plafond 100 lots intégrée au sizing.

**Bot déjà testé en compte démo** — pipeline logiciel validé de bout en bout. Reste à
tester sur compte réel : slippage/spread réels, comportement broker live, mécaniques
spécifiques prop firm (rollover, DD journalier réel).

---

## 3. Bugs découverts et corrigés (chronologique, résumé)

1. **Bug TP1/TP2** : "OBJECTIF ATTEINT" = TP1, pas TP2. Continuation à vérifier via
   yfinance (~14% des cas ne continuent pas jusqu'à TP2).
2. **Biais bootstrap par permutation** → remplacé par block bootstrap (blocs
   contigus de 2 mois), préserve le vrai clustering des séquences de pertes.
3. **Réserve non poolée → poolée** (une seule réserve commune, alimentée par 80%
   des gains de n'importe quel compte).
4. **Mécanisme d'immunité** : dès qu'au moins un compte de la flotte a été financé
   une première fois, plus aucun rachat futur ne tape dans le budget personnel.
5. **Bug des 999€ initiaux non comptés** dans `real_cash_paid`.
   → Effet cumulé de 2+3+4+5 : pire cas de trésorerie Phase 1 passé de 21 972€
   (ancienne méthodo) à **2 997€** (valeur définitive, retenue en section 0).
6. **BUG MAJEUR — comptabilité challenge vs financé** : `monte_carlo_simulation.
   run_one` comptait tout le P&L comme profit réel, y compris pendant les phases de
   challenge non financées. Explique 106% de l'écart entre les anciens chiffres
   (2,63M€-13,39M€, **définitivement obsolètes**) et les chiffres corrigés.
7. **Seuil de bascule à 5000€ obsolète** : sous le modèle poolé+immunité, le pire cas
   de trésorerie est identique (2997€) quel que soit le seuil choisi. Décision mise
   à jour : bascule immédiate au premier financement, plus de seuil de réserve.
8. **BUG MAJEUR — absence de daily drawdown** : aucune simulation ne modélisait la
   limite de perte JOURNALIÈRE des prop firms. Seuils réels : The5%ers 3%, FTMO 5%,
   Blueberry 5% (tous avec 10% de perte max trailing). Sur la trajectoire réelle,
   ajouter la limite journalière fait passer les casses de 17 à 29 (+70,6%).
9. **Prix de rachat perpétuel à 179$ (Summer Plan The5%ers)** : les moteurs
   supposaient un rachat à 179$ sur tout l'horizon (~3,96 ans), alors que l'offre
   expire (~26 jours après le premier achat dans le modèle testé, prix réel
   post-promo sourcé à ~495-545$). Effet sur le profit : quasi nul (-0,3% à -1%).
   Effet sur le **cash pire cas : sous-estimé de +23% à +99%** selon le régime de
   risque testé (plus le risque/les casses sont élevés, plus l'effet est marqué).
   **Chiffres corrigés (2%/maxpos=3, 37,29%) : cash pire cas flotte = 41 226$ sur
   CE scénario précis (comptes fixes + growth restructurés) — ne pas confondre avec
   le pire cas de 2997€/10-11k$ du plan de lancement classique en section 2, qui
   reste la référence pour le lancement réel.**

**Winrate de référence** : 37,29% (472 trades, IC95% [32,9%,41,7%]). Stress-test
bayésien P10 = 32% (scénario défavorable réaliste à utiliser dans toute simulation,
pas 28% qui était une erreur fréquentiste).

**R:R moyen des gagnants actuel (convention r_trailing)** : 4,115 (référence) / 4,164
(32%).

**Slippage réel mesuré** (469 trades, données tick Dukascopy) : moyenne -0,91 pip.
Impact EV : +0,907R (sans) → +0,850R (avec), soit -6,3%. N'affecte quasiment pas le
pire cas de trésorerie Phase 1 (2997€ stable).

---

## 4. Pistes explorées le 5 août (soir) — statut et chiffres

### Point 1 — Écart Régime A (7,7M$) vs flotte réelle plafonnée (5,33M$)

Cause confirmée par lecture de code : le plafond de capital combiné par firm (400k)
est inférieur au palier de scaling max (500k), donc les comptes plafonnent avant
d'atteindre leur taille théorique — **pas** une restriction de copytrade (le
copytrade entre comptes propres, même chez des firms différentes, n'a aucune
restriction connue chez FTMO/FundedNext/The5%ers/Funding Pips/FXIFY — seule la copie
de signaux d'un tiers externe est interdite).

Test : remplacer le scaling plafonné par 16 comptes fixes de 50k (jamais scalés,
casse+rachat au même palier) :

| | Profit final | Cash pire cas | Casses |
|---|---|---|---|
| Actuel (scaling plafonné) | 5 332 216$ | 39 046$ | 164,3 |
| Comptes fixes 16×50k | 6 553 090$ (+22,9%) | 82 336$ (+111%) | 401,6 (+144%) |

**Statut : gain confirmé mais réservé à une phase ultérieure du projet (voir section
0) — le pire cas de trésorerie associé est hors de l'échelle du budget de départ.**

### Point 2 — Or / indices / paires exotiques chez Lutessia

Vérifié sur 1773 signaux scrapés (2022-2026) : **Lutessia ne publie jamais** de
signal sur l'or, l'argent, la crypto, ou le FTSE100 (pas un bug du scraper, qui les
cherche activement). Indices couverts : DAX40, NASDAQ100, S&P500, MINI DJ30 — 82
trades exploitables, winrate 37,8% (proche du forex) mais échantillon trop petit (IC95%
±10,5 pts). Il faudrait ~360 trades (~14 ans au rythme actuel) pour une fiabilité
comparable au forex.

**Statut : piste fermée à court/moyen terme, à réévaluer si Lutessia élargit sa
couverture.**

### Point 3 — Firms à capital direct élevé (FXIFY, Ment Funding)

| Critère | Ment Funding | FXIFY |
|---|---|---|
| Taille accessible directement | Jusqu'à 2M$ (à confirmer si évaluation requise ou non — **non tranché**, voir action à suivre) | 400k$ (2-Phase 2-Step, évaluation classique) |
| Plafond capital combiné | Pas de plafond explicite trouvé | 795k$ (un compte de CHAQUE palier : 5k+10k+15k+25k+50k+100k+200k+400k — écart 10k$ non résolu avec la somme réelle des paliers, ~805k$) |
| Daily DD / Max DD | 5% / 6% statique | 4% / 10% trailing |
| Copytrade entre comptes propres | ✅ Autorisé | ✅ Confirmé officiellement |
| Détention week-end | Fermeture forcée vendredi 15h45 EST, sauf add-on +10% ponctuel à l'achat — **sans l'add-on, c'est un "soft breach" (avertissement, pas résiliation)**, donc moins bloquant qu'estimé initialement | ✅ Autorisée sans restriction |
| Prix (2-Phase 2-Step) | Dès 200$, grille complète non sourcée | 5k=59$, 10k=75$, 15k=99$, 25k=175$, 50k=379$, 100k=475$, 200k=999$, 400k=2950$ (total 6211$ pour 795-805k$ de capital) |

Chiffrage FXIFY ajouté à la flotte (8 comptes fixes 5k→400k) :

| | Profit final | Cash pire cas | Casses |
|---|---|---|---|
| Baseline (sans FXIFY), 37,29% | 5 332 216$ | 39 046$ | 164,3 |
| + FXIFY, 37,29% | 9 539 404$ (+78,9%) | 98 975$ (+153,5%) | 343,6 |

**Statut : gain le plus puissant identifié à ce jour, mais même remarque que le
point 1 — réservé à une phase ultérieure, pas une structure de départ.** Ment
Funding reste à trancher (évaluation ou accès direct réel ? grille de prix ? plafond
combiné réel ?) avant de pouvoir le chiffrer.

### Point 4 — Trésorerie dormante en phase mature

Une fois la flotte mature (réserve constituée, immunité acquise), le rythme de
profit accélère mais rien ne l'absorbe dans le modèle actuel :

| Winrate | Rythme année 1 | Rythme mature (années 2-4) |
|---|---|---|
| 37,29% | 1 151 418$/an | 1 425 722$/an (+24%) |
| 32% | 658 276$/an | 863 596$/an (+31%) |

Ordre de grandeur de trésorerie mature non redéployée : **860k$ à 1,4M$/an**, avec
deux leviers déjà chiffrés pour l'employer (points 1 et 3 ci-dessus) — **mais
uniquement une fois que cette trésorerie est bien celle générée par le projet,
pas celle du budget de départ.**

---

## 5. Prop firms — statut définitif pour la structure de DÉPART (pas les extensions)

| Firm | Statut | Notes |
|---|---|---|
| FTMO | Retenu | Compte Swing obligatoire, pas de clause anti-signaux tiers |
| The5%ers | Retenu | 4×100k Summer Plan (~179$/compte, offre expire ~fin août 2026) préférable aux 3×50k classiques : ~2,7x plus de profit pour 28% moins cher. Daily DD 3% réel — coûte -10,9% à -14,6% de profit et +34-38% de casses par rapport à un DD hypothétique à 5%, sur ce segment isolé |
| Blueberry Funded | Retenu | Broker régulé ASIC, copytrade autorisé, DD statique, pas de consistency rule sur le flagship. **Compte 5k$ (~25-35$) recommandé comme compte de test/validation Phase 1** (le moins cher des 3 firms à ce niveau) |
| Alpha Capital | Écarté | Clause "signal following" jamais levée |
| FXIFY, Ment Funding | **Extensions futures, pas la structure de départ** | Voir section 4, point 3 |

**Optimisation The5%ers seule (daily DD 3%) — frontière de compromis déjà établie :**

| Option | Profit final | Casses | Cash pire cas |
|---|---|---|---|
| Statu quo (2%, maxpos 3) | 5 372 936$ (flotte) | 164,3 | 20 014$ |
| maxpos=1 (2%, 1 position) | 5 003 982$ (-6,9%) | 126,4 (-23,1%) | 17 150$ (-14,3%) |
| Risque fixe 1% | 4 610 926$ (-14,2%) | 66,6 (-59,5%) | 13 570$ (-32,2%) |
| Tremplin / abandon pur | ~3,27M$ (-39%) | ~53 | ~10-10,7k$ | **Dominés, rejetés** |

⚠️ Ces chiffres n'intègrent pas encore la correction du prix de rachat post-Summer
Plan (point de bug #9 ci-dessus) sur la version maxpos=1 spécifiquement — seule la
version maxpos=3 a été recalculée à ce stade. **Action en attente** : demander les
15 combinaisons (risque × maxpos) avec le prix de rachat corrigé.

---

## 6. Trésorerie — chiffres de référence pour le LANCEMENT (à utiliser comme repère)

- Coût de départ garanti : 999€ (ou moins avec Summer Plan The5%ers, ~720€ pour la
  part The5%ers)
- Cas normal (jusqu'au 90e percentile) : 999€, aucun apport supplémentaire
- Cas défavorable (95%) : ~1998€
- **Pire cas retenu comme repère du projet (99%, valeur définitive post-correction) :
  2 997€**
- Recommandation : budget de départ 1000€, capacité d'appoint mobilisable en cas de
  coup dur plutôt que tout immobiliser à l'avance

**Tout chiffre de pire cas au-delà de ~10-15k$ doit être traité comme appartenant à
une phase ultérieure du projet (post-immunité, post-réserve confortable), jamais
comme un repère pour la décision de lancement.**

---

## 7. Actions en attente / points ouverts

1. **Lancer la Phase 1 réelle** (0,5% de risque, 10-15 trades) dès que la structure
   de départ (section 2 et 5) est confirmée opérationnelle sur le VPS — c'est la
   priorité, ne pas la reporter davantage pour continuer à explorer des extensions.
2. Recalculer les 15 combinaisons risque×maxpos sur The5%ers avec le prix de rachat
   corrigé (179$→495-545$ post-Summer Plan), notamment la version maxpos=1.
3. Trancher Ment Funding : évaluation réelle ou accès direct au capital ? Grille de
   prix complète ? Plafond de capital combiné réel ?
4. Résoudre l'écart 795k$ (FAQ FXIFY) vs 805k$ (somme des 8 paliers utilisés dans la
   simulation) directement à la source officielle.
5. Score "Force" Lutessia : toujours pas capturé dans le pipeline live, à ajouter
   dans scraper.py/app.py pour capture future (pas de scraping rétroactif possible).
6. Frais de swap/rollover et risque de gap week-end : toujours pas intégrés au
   modèle de coût.
7. Vérifier/confirmer l'achat effectif des comptes FTMO Swing + The5%ers (Summer
   Plan, avant expiration ~fin août) + Blueberry Funded (dont le compte 5k$ de test).
8. Définir précisément le seuil de réserve qui déclenchera le passage à la phase
   "extensions" (comptes fixes multiples, FXIFY) — de l'ordre de 5-10x le pire cas
   initial de 2997€, à faire chiffrer par Claude Code plutôt que deviner un chiffre
   rond.

---

## 8. Fichiers de référence sur le repo (état au 5 août 2026, soir)

**À jour / à utiliser** :
- `regime_abc_comparison_dailydd.py`, `the5ers_summer_100k_N_accounts_dailydd.py`,
  `three_firm_fleet_dailydd.py` et CSV associés
- `the5ers_viability_scenarios.py` et `the5ers_viability_final_synthesis_*.csv`
- Les nouveaux moteurs de la session du soir (comptes fixes 16×50k, FXIFY 8 comptes,
  prix de rachat corrigé) — noms de fichiers non communiqués précisément dans les
  synthèses reçues, à clarifier avec Claude Code au prochain contact

**Obsolètes / buggés, à ne plus utiliser comme référence** :
- Toute version sans le suffixe `_dailydd`
- Tout chiffre citant 21 972€ ou 1998€ comme pire cas de trésorerie (obsolète,
  remplacé par 2 997€)
- Tout chiffre citant 2,63M€-13,39M€ comme profit de référence (bug comptabilité
  challenge/financé)
- Tout chiffre FXIFY/comptes fixes utilisé comme repère de décision pour le
  LANCEMENT du projet plutôt que comme piste d'extension future (voir section 0)
