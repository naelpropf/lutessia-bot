# Capacité de marché et compounding réaliste — Stratégie B (session 2026-08-23)

## 0. Résumé exécutif

Le calcul non contraint établi par le projet (EV +2,28R, risque 1,50%/trade,
~16-20 trades/mois, capital composé en continu) donne un rendement mensuel
théorique de **+83%/mois**, soit un facteur **×1400/an (+142 700%/an)** si on
ignore toute limite de marché — mathématiquement absurde sur la durée.

Cette session a testé si un plafond de liquidité **mesuré** (position max en
% de l'ADV de l'instrument, retenue institutionnelle usuelle 1-5%) suffit à
ramener ce calcul dans un régime réaliste. **Réponse : non, pas à lui seul.**
Le plafond de liquidité commence à mordre sur les instruments les moins
liquides (crosses FX secondaires, palladium/platine) dès **~18-25 M$** de
capital, mais il ne devient dominant sur **l'ensemble** du portefeuille
(y compris EUR/USD, USD/JPY, or) qu'entre **~2,5 Md$ et ~12 Md$** selon
l'instrument et le seuil retenu (1/3/5% ADV) — des paliers de capital
totalement hors du champ de ce qu'un compte personnel réel atteindra jamais.
Résultat : même avec le plafond le plus strict testé (1% ADV), le capital
médian simulé dépasse déjà **~200 M$ en 12 mois** et **~15 Md$ en 48 mois**
(n=600, détail §3). **Le plafond de liquidité mesuré n'est PAS le mécanisme
qui rend le calcul non contraint réaliste** — il ne fait que retarder
l'absurdité de quelques ordres de grandeur, pas la supprimer. La vraie
contrainte qui rendrait ce calcul crédible se trouve ailleurs (capacité du
broker/liquidity provider, dégradation de l'edge à mesure que la taille
augmente, ou simplement l'impossibilité que ce régime de rendement persiste
4 ans sans qu'aucune de ces frictions non modélisées n'intervienne) — **hors
du périmètre mesurable par cette session**, voir §5.

Aucune conclusion ci-dessous ne dépasse ce que les simulations confirment
(n=300 exploration, n=600 confirmation, méthodologie standard du projet).
Chaque donnée de marché est sourcée avec un niveau de confiance explicite —
plusieurs figures (crosses FX, palladium, E-mini S&P) sont **non sourcées**
ou de confiance basse malgré deux passes de recherche dédiées, et sont
signalées comme telles plutôt que présentées comme mesurées.

---

## 1. Capacité de marché par instrument (recherche sourcée)

Population effectivement tradée par B_tradable_pgp (n=1248, confirmée par
lecture directe de `chantier_gold_silver_pop_B_tradable_pgp_2026-08-20.csv`) :
27 tickers — 14 paires forex (majors + crosses JPY/CHF/GBP), 4 variantes
devise de l'or, 3 de l'argent, palladium, platine, et 3 indices (DAX40,
NASDAQ100, S&P500, chacun en 2 variantes CFD/mini-future).

**Note de périmètre** : le gaz naturel mentionné dans la demande n'est PAS
dans la population officielle actuelle. Un pilote de scraping l'a exploré
(`chantier_gaz_palladium_platine_pilote_2026-08-20.py`, palladium/platine
retenus, gaz naturel non repris dans B_tradable_pgp pour une raison non
retracée dans cette session) — absent du tableau ci-dessous en conséquence.

### 1.1 ADV (Average Daily Volume / turnover), en notional USD/jour

| Instrument | ADV (USD/j) | Source | Confiance |
|---|---|---|---|
| EUR/USD | ~1 700 Md$ | BIS Triennial Survey 2022, part reconstruite (22,7% × 7 500 Md$ turnover OTC total global) via CompareForexBrokers/Yahoo Finance citant BIS | **Moyenne** — part non relue sur table BIS primaire (2 tentatives de fetch direct échouées : PDF illisible, portail JS non statique) |
| USD/JPY | ~1 010 Md$ | idem (13,5% × 7 500 Md$) | **Moyenne** — une 1ère recherche avait trouvé 439 Md$ étiqueté "BIS global" mais incohérent avec ce calcul (périmètre spot vs total ambigu) ; figure retenue = chaîne de calcul la plus traçable |
| GBP/USD | ~713 Md$ | idem (9,5% × 7 500 Md$) | **Moyenne** — 1ère recherche avait trouvé 432 Md$ = Londres seule (BoE), remplacée |
| USD/CAD | ~413 Md$ | idem (5,5% × 7 500 Md$) | **Moyenne** |
| AUD/USD | ~383 Md$ | idem (5,1% × 7 500 Md$) | **Moyenne** |
| USD/CHF | ~293 Md$ | idem (3,9% × 7 500 Md$) | **Moyenne** |
| NZD/USD | ~40 Md$ (proxy) | Non trouvé en table BIS (2 tentatives) — NZD = 14e devise la plus tradée (mention qualitative RBNZ), proxy prudent retenu | **Très basse / NON SOURCÉE** |
| EUR/JPY, GBP/JPY, AUD/JPY, CHF/JPY, EUR/CHF, EUR/GBP, GBP/CHF (crosses) | 15-60 Md$ (proxies) | Aucune source primaire ou secondaire fiable trouvée (2 tentatives, y compris fetch direct du PDF BIS) | **Très basse / NON SOURCÉE** — ordres de grandeur qualitatifs seulement |
| Or (XAU, toutes devises) | ~430 Md$ | LBMA Precious Metals Market Report Q4 2024 : clearing ~20M oz/j (mars 2024) × multiplicateur usage 10x (clearing→turnover réel) × ~2 150$/oz | **Moyenne** — clearing LBMA fiable, multiplicateur 10x = convention sectorielle non mesurée directement |
| Argent (XAG, toutes devises) | ~73 Md$ | idem, LBMA clearing ~292M oz/j × 10 × ~25$/oz | **Moyenne**, même caveat |
| Platine | ~3,5 Md$ (proxy) | 1 point de donnée : volume NYMEX 61 000 contrats (jour "normal") + 115 000 contrats (record, juin 2025), 50 oz/contrat, ~1 000$/oz → ~3,05 Md$/j sur le jour non-record | **Basse** — 2 points ponctuels, pas une vraie ADV mesurée |
| Palladium | ~3,5 Md$ (proxy) | Aucune donnée numérique trouvée (2 sessions de recherche) — proxy = même ordre de grandeur que le platine | **Très basse / NON SOURCÉE** |
| DAX40 (Eurex) | ~26,5 Md$ | Eurex, chiffres pleine année 2024 (EUR 24,58 Md/j, converti ~USD) | **Haute** — source exchange directe |
| NASDAQ100 (E-mini) | ~239 Md$ | Page produit Schwab citant données CME | **Moyenne** — source secondaire (broker), pas la page CME elle-même (échecs de fetch répétés, `ECONNRESET` systématique) |
| S&P500 (E-mini) | ~500 Md$ (estimation) | Aucune ADV directe trouvée pour le contrat E-mini seul (seulement CME agrégé toutes classes, ou Micro E-mini) — estimation combinée 1,5-2M contrats/j × 50$ × ~6 000 pts | **Basse** — ordre de grandeur seulement |

### 1.2 Plafond de position en % de l'ADV — littérature institutionnelle

- Fourchette usuelle citée dans la littérature/outils d'exécution algo :
  **1-10% de l'ADV**, avec **10% comme défaut "MaxParticipation"** fréquent
  dans les plateformes d'algo-trading (confiance moyenne — guidance
  practitioner/plateforme, pas un seuil réglementaire ou académique unique).
- Fondement théorique : la **loi d'impact en racine carrée**
  (`I(Q) ≈ Y·σ·√(Q/V)`, Almgren-Chriss et généralisations empiriques
  confirmées cross-asset) — un cadre de coût continu, PAS une règle "X% =
  sûr" dérivée rigoureusement du modèle lui-même. Le "1-5%" ou "10%" est un
  choix de politique de desk calibré par-dessus, pas une sortie du modèle.
  Confiance **moyenne-haute** sur l'existence/forme du modèle, **basse**
  sur tout seuil précis présenté comme "la" limite.
- **Réserve critique, institutionnel vs CFD retail** : toutes les données
  ci-dessus (BIS, LBMA, CME/Eurex) mesurent un volume interbancaire OTC ou
  un volume échangé sur un carnet d'ordres d'exchange. Un broker CFD
  retail/pro (échelle Blueberry Markets) n'exécute PAS directement contre ce
  volume visible : il internalise/warehouse la position sur son propre
  livre, ou nette le flux client et ne hedge que l'exposition nette via un
  prime broker/pool de liquidity providers (recherche : la couverture
  passe typiquement par ~10-12 LPs ou un prime broker qui pool les
  positions). **La vraie contrainte de capacité d'un compte CFD n'est donc
  probablement PAS "position vs ADV globale" mais "position vs capacité
  propre du broker/LP" — donnée non publique, non trouvée dans cette
  recherche (confiance : aucune/non sourcée, signalé explicitement plutôt
  que deviné).** Utiliser l'ADV globale comme proxy de plafond est donc
  **conservateur dans le mauvais sens pour la thèse du projet** : cela
  SURESTIME probablement la capacité réellement disponible avant friction
  côté broker — mais c'est la seule mesure publiquement sourçable, donc
  retenue comme borne, avec cette réserve explicite. Levier retail plafonné
  réglementairement à 1:30 sur les majors FX (zone UE/ESMA-style) — friction
  de marge, pas de volume, mais pertinente au même titre.

### 1.3 Lacunes de données non comblées (2 passes de recherche)

NZD/USD, les 7 crosses JPY/EUR/GBP/CHF, palladium, et l'ADV spécifique du
contrat E-mini S&P500 seul n'ont **aucune source primaire fiable** trouvée
dans cette session — les pages de volume CME (`*.volume.html`) et le PDF
BIS primaire (`rpfx22_fx.pdf`) ont systématiquement échoué au fetch
(`ECONNRESET` / PDF illisible / portail JS non statique). Ces figures sont
retenues comme proxies d'ordre de grandeur pour permettre le calcul, PAS
comme mesures — voir §4 pour l'impact de cette incertitude sur la
conclusion.

---

## 2. Modèle de compounding plafonné — méthodologie

Moteur dédié `chantier_liquidity_capacity_2026-08-23.py` (nouveau, pas une
réutilisation du moteur flotte multi-firm — hors sujet ici : capital
personnel réel post-stratégie, pas un compte prop à faire passer une
évaluation).

- **Population/prior** : exactement ceux de la stratégie B officielle
  (`B_tradable_pgp` corrigée, n=1248, prior Beta(625,625) sur le winrate —
  identiques à `point_d_bloc1_bloc2_2026-08-22.load_scenario_pgp`).
- **Distribution EV/winrate réaliste (pas une EV plate)** : bootstrap par
  blocs de 2 mois (`build_blocks`/`build_full_block_bootstrap_sequence`,
  mécanisme standard du projet), winrate tiré du prior Beta à chaque
  simulation — reproduit la vraie variabilité temporelle des blocs déjà
  validée dans le projet.
- **Stop réel par trade** : `stop_pct = |prix_entrée - stop_loss_init| /
  prix_entrée`, calculé sur les colonnes RÉELLES de la population
  (`prix_entree`, `stop_loss_init`) — PAS les specs `market_data` du moteur
  flotte, qui sont volontairement "unconstrained" (price=1.0, tick_value=1.0)
  pour l'or/argent/palladium/platine/indices dans ce moteur (vérifié en
  lisant `build_market_data_with_indices` : la contrainte de capacité y est
  explicitement désactivée par construction) — inutilisables pour cette
  question.
- **Conversion risque → notional** : approximation économique standard
  (position value vs ADV, cohérente avec la littérature d'exécution) :
  `notional = risque_$ / stop_pct` (P&L ~ linéaire en notional × variation
  de prix). Le plafond de liquidité compare ce notional à
  `liquidity_cap_pct × ADV_USD[marché]` — pas une reconstruction lot par
  lot des specs de contrat CFD (non documentées publiquement par instrument).
  **Limite explicite** : approximation économique, pas une simulation
  d'exécution tick par tick.
- **Risque appliqué par trade** = le plus restrictif entre 1,50% du solde
  courant (capital réel, pas de plafond Blueberry artificiel) et le plafond
  de liquidité.
- **Compounding** : solde mis à jour à CHAQUE trade (continu) — c'est ce
  mécanisme qui produit la composition mensuelle décrite par le calcul non
  contraint (~16-20 trades/mois). Rapporté par snapshot de fin de mois.
- **Durées** : 12 et 48 mois. **n** : 300 exploration, 600 confirmation
  (méthodologie standard du projet). Seeds fixes pour reproductibilité.
- **Regroupement multi-devises** : les variantes GOLD-AUD/EUR/GBP/USD et
  SILVER-AUD/EUR/USD partagent la même ADV (même marché sous-jacent), idem
  pour les 2 variantes DAX40/NASDAQ100.

Fichiers : `chantier_liquidity_capacity_2026-08-23.py` (moteur),
`chantier_liquidity_capacity_log_2026-08-23_n300.txt` /
`_n600.txt` (logs bruts), `chantier_liquidity_capacity_2026-08-23_thresholds.csv`
(seuils déterministes par instrument, §4).

---

## 3. Résultats — trajectoire de croissance plafonnée (n=600 confirmé)

Capital de départ 200 000€ (traité comme ≈200 000$ dans le moteur, la
distinction EUR/USD est du bruit face aux ordres de grandeur en jeu ici).

| Scénario | Durée | p10 | p50 (médiane) | Moyenne | p90 | % trades plafonnés (moy.) |
|---|---|---|---|---|---|---|
| **(a) Non plafonné** (référence absurde) | 12 mois | 68,2 M$ | 322,0 M$ | 703,7 M$ | 1 584,2 M$ | 0% |
| Plafond 1% ADV | 12 mois | 57,9 M$ | 201,7 M$ | 252,5 M$ | 540,0 M$ | 11,01% |
| Plafond 3% ADV | 12 mois | 67,3 M$ | 257,7 M$ | 373,1 M$ | 861,9 M$ | 5,97% |
| Plafond 5% ADV | 12 mois | 67,6 M$ | 282,4 M$ | 433,8 M$ | 1 015,4 M$ | 4,15% |
| **(a) Non plafonné** | 48 mois | 5,0×10¹⁶ $ | 1,08×10¹⁸ $ | 4,01×10¹⁹ $ | 4,33×10¹⁹ $ | 0% |
| Plafond 1% ADV | 48 mois | 11,6 Md$ | 14,9 Md$ | 15,0 Md$ | 18,3 Md$ | 70,85% |
| Plafond 3% ADV | 48 mois | 32,5 Md$ | 42,3 Md$ | 42,3 Md$ | 52,5 Md$ | 67,09% |
| Plafond 5% ADV | 48 mois | 52,4 Md$ | 68,6 Md$ | 68,5 Md$ | 85,5 Md$ | 65,38% |

n=600 confirmé (cohérent avec l'exploration n=300, écart p50 <5% sur tous
les scénarios). Logs bruts : `chantier_liquidity_capacity_log_2026-08-23_n600.txt`.

Le régime non plafonné à 48 mois (10¹⁶-10¹⁹$) est un artefact arithmétique
de la composition sans frein sur 4 ans (confirme, en la rendant encore plus
visible, l'absurdité du calcul de départ) — il n'a aucune valeur
prédictive, il sert uniquement de référence "sans aucune limite" demandée
en (a). Le plafond de liquidité RAMÈNE cette valeur dans une plage
"seulement" de 10-85 milliards de dollars sur 4 ans — une réduction de
~15 ordres de grandeur par rapport au non-plafonné, mais qui reste
elle-même totalement hors du champ d'un compte personnel réel.

### Constat central

Même au plafond le PLUS strict testé (1% de l'ADV, borne basse de la
fourchette institutionnelle usuelle 1-5%), le capital médian simulé reste
dans les **centaines de millions d'euros en 12 mois** et les **dizaines de
milliards en 48 mois** — voir chiffres exacts ci-dessus. Le plafond de
liquidité RALENTIT la croissance (11-12% des trades plafonnés en moyenne à
12 mois avec le seuil 1%, ~70% à 48 mois une fois que le capital a
suffisamment grossi) mais ne l'empêche pas de rester exponentielle et
absurde sur toute la durée testée.

### (b) Comparaison au régime additif prop-firm (~740-800%/an)

Figure fournie par l'utilisateur comme repère de comparaison (régime
additif façon cascade multi-firm, PAS revérifiée dans cette session — pas
un résultat de simulation produit ici). Le régime de compounding sur
capital personnel, même plafonné au taux de liquidité le plus strict,
dépasse ce régime additif de plusieurs ordres de grandeur dès les premiers
mois (57,9 M$ p10 à 12 mois pour le cap 1% vs un régime additif qui, parti
de 200k€, donnerait ~1,6-1,8M€ en un an à 740-800%/an) — **le plafond de
liquidité mesuré ne ramène PAS le compounding personnel dans l'ordre de
grandeur du régime additif prop-firm**, contrairement à l'hypothèse
implicite de la question posée en début de session.

### (c) Comparaison aux fonds quantitatifs réels

Medallion (Renaissance) : ~39%/an net historique (fonds interne, effet de
levier et frais de structure non comparables à un compte personnel, figure
largement citée dans la presse financière/littérature sur les hedge funds,
non re-sourcée dans cette session). Grands fonds quant actuels : 10-36%/an
selon les années et les stratégies (figure de repère fournie par
l'utilisateur, non revérifiée ici). **Même le scénario le plus contraint
simulé ici (plafond 1% ADV) dépasse ces régimes de plusieurs ordres de
grandeur sur 12 mois** — confirmant que la limite qui rendrait ce calcul
réaliste n'est PAS le plafond de liquidité de marché mesurable.

### 3.1 Taux mensuel composé effectif implicite (dérivé des trajectoires médianes)

Le taux mensuel n'est PAS constant : il s'effondre à mesure que le plafond
de liquidité mord davantage, calculé directement à partir de la trajectoire
médiane mois-par-mois du run n=600 (`chantier_liquidity_capacity_2026-08-23_trajectories.json`),
pas une nouvelle estimation :

| Période | Plafond 1% ADV | Plafond 3% ADV | Plafond 5% ADV | Non plafonné (réf.) |
|---|---|---|---|---|
| Mois 1-6 | ~83%/mois | ~83%/mois | ~83%/mois | ~83%/mois |
| Mois 7-12 | ~73%/mois | ~80%/mois | ~83%/mois | ~87%/mois |
| Année 2 | ~28%/mois (~1 770%/an) | ~34%/mois | ~38%/mois | ~84%/mois |
| Année 3 | ~8,0%/mois (~152%/an) | ~9,3%/mois | ~10,0%/mois | ~85%/mois |
| Année 4 | **~4,2%/mois (~64%/an)** | ~4,5%/mois (~70%/an) | ~4,6%/mois (~72%/an) | ~83%/mois |

Le taux ne se stabilise à une valeur durable dans aucun des scénarios testés
sur la fenêtre de 48 mois — il reste en chute (marches d'escalier au rythme
où chaque instrument sature, pas une courbe lisse) et n'a pas convergé à la
fin de la fenêtre testée. Même en fin de période (année 4, plafond le plus
strict), le taux annualisé implicite (~64%/an) reste **au-dessus** du haut
de la fourchette des grands fonds quant réels (10-36%/an, §3(c)) et
**en-dessous** du régime additif prop-firm cité (~740-800%/an, §3(b)) — il
n'a pas encore atteint un régime "réaliste" comparable aux fonds réels dans
la fenêtre simulée ; à quel mois précis cela se produirait n'a pas été
mesuré (nécessiterait de prolonger la simulation au-delà de 48 mois).

---

## 4. À partir de quel palier de capital le plafond devient-il dominant ?

Pas un seuil unique — une **cascade**, calculée déterministiquement (stop
médian réel par instrument × ADV × cap%, indépendant du bruit de
simulation, cf. `chantier_liquidity_capacity_2026-08-23_thresholds.csv`) :

| Palier de capital (plafond 1% ADV) | Ce qui se passe |
|---|---|
| < ~18-25 M€ | Le risque nominal 1,50%/trade reste la SEULE contrainte active sur tous les instruments — le plafond de liquidité ne mord nulle part |
| ~18 M€ → ~660 M€ | Plafonnage progressif, dans l'ordre : GBP/CHF, platine, CHF/JPY, palladium, EUR/CHF (~18-25 M€) → EUR/GBP, AUD/JPY, NZD/USD (~30-65 M€) → DAX40, GBP/JPY, EUR/JPY (~85-135 M€) → argent (~280-335 M€) → USD/CHF, USD/CAD (~465 M€) → AUD/USD (~660 M€) |
| ~660 M€ → ~2,5 Md€ | GBP/USD, NASDAQ100, or (toutes devises) plafonnés |
| > ~2,5 Md€ | USD/JPY, S&P500, **EUR/USD en dernier** (~2,5 Md€, l'instrument le plus liquide de la population) — à partir de là, TOUS les trades sont plafonnés, la croissance devient additive plutôt que composée |

Aux seuils 3% et 5% ADV, chaque palier est multiplié par ~3 et ~5
respectivement (mécanique linéaire du modèle) — la cascade complète ne se
termine qu'entre **~7,4 Md€ (cap 1%) et ~12,4 Md€ (cap 5%)**.

**Interprétation** : le levier "diversification sur 27 instruments" que la
stratégie B exploite déjà (cf. session précédente, piste diversification du
panier de démarrage) a un effet pervers ici — tant qu'AU MOINS UN
instrument à forte ADV (EUR/USD, or, USD/JPY) reste sous son seuil de
plafonnement, ce petit sous-ensemble de trades suffit à maintenir une
composante de croissance non plafonnée qui domine la trajectoire globale.
C'est ce mécanisme, pas un bug du modèle, qui explique pourquoi même un
plafond strict (1% ADV) ne borne pas la croissance à un niveau raisonnable
avant plusieurs milliards d'euros de capital.

---

## 5. Étape 4 — Risque de gap au-delà du stop (scope réduit, mise en file d'attente)

**Non traité en profondeur cette session** (budget de temps, comme prévu
par la consigne "si temps disponible, sinon file d'attente séparée").

Ce qui a été vérifié : l'infrastructure nécessaire existe déjà dans le
projet et rendrait cette analyse faisable sans nouveau pipeline de données —
`dukascopy_ticks.py` télécharge des ticks bid/ask réels (résolution
tick-by-tick, historique remontant à au moins 2010, gratuit, déjà utilisé et
validé pour la mesure de slippage d'entrée dans
`slippage_proxy_dukascopy.py`/`slippage_adjusted_population.py`). Cette
infrastructure mesure aujourd'hui le slippage d'ENTRÉE (~-0,91 pip moyen,
469 trades mesurés) — un mécanisme différent du risque de gap AU-DELÀ DU
STOP lors d'un retournement violent (ce qui est demandé ici), mais
réutilisable : il faudrait identifier, pour chaque trade soldé par un stop
(statut_final ≠ "OBJECTIF ATTEINT"), le tick réel au moment où le prix a
franchi le niveau de stop, et comparer le prix de sortie réellement
disponible au niveau de stop théorique — sur l'ensemble de la population
(n≈1050-1250), pas seulement les 2 épisodes déjà identifiés (SVB -1,01R,
Israël-Hamas -1,03R, chiffres fournis par l'utilisateur, non revérifiés
dans cette session).

**Prochaine étape concrète si cette piste est reprise** : script dédié
réutilisant `dukascopy_ticks.py` pour récupérer les ticks autour de
`resolution_time_est` de chaque trade stoppé, mesurer le gap réel
(différence entre stop théorique et prix de sortie), produire une
distribution empirique du gap sur l'ensemble de la population plutôt que
d'extrapoler sur 2 échantillons. Non lancé cette session — mis en file
d'attente séparée comme demandé.

---

## 6. Ce qui n'a PAS été établi cette session (limites explicites)

- Le plafond de liquidité par instrument (1-5% ADV) est **réfuté** comme
  seule explication de l'écart entre le calcul non contraint et un
  rendement réaliste — mais **aucune contrainte alternative n'a été
  mesurée** pour combler cet écart (capacité broker/LP réelle, dégradation
  de l'edge avec la taille, persistance de l'edge sur 4 ans). Ne pas
  présenter ce document comme ayant "résolu" la question du rendement
  réaliste — il élimine une hypothèse, il n'en confirme pas une autre.
- Plusieurs ADV (crosses FX, palladium, NZD/USD, E-mini S&P) reposent sur
  des proxies non sourcés malgré 2 passes de recherche dédiées. Comme ces
  instruments sont, dans la cascade §4, parmi les PREMIERS à plafonner
  (paliers les plus bas), une erreur sur ces chiffres décale le début de la
  cascade mais ne change pas la conclusion §3 (le plafond global, dominé
  par EUR/USD/or/USD/JPY dont les ADV sont mieux sourcées, reste hors de
  portée d'un compte personnel réel).
- L'approximation `notional = risque_$ / stop_pct` est une simplification
  économique (position value vs ADV), pas une simulation d'exécution —
  n'intègre pas les spécificités de marge/tick d'un broker CFD réel.
- Le régime additif "~740-800%/an" et les rendements Medallion/fonds quant
  cités en §3(b)/(c) sont des chiffres fournis en repère par l'utilisateur
  ou de notoriété publique — **non revérifiés par une recherche sourcée
  dans cette session**, contrairement aux ADV du §1.

