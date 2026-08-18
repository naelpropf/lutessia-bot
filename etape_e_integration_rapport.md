# Étape E — Intégration des formats gagnants dans le moteur de production

*08-09/08/2026. Objectif : réintégrer les formats comparés à l'Étape D dans
le moteur complet (déblocage échelonné + comptes supplémentaires +
fiscalité), pour une comparaison honnête entre la config actuelle (100%
2-step) et le combo gagnant du criblage simplifié — pas biaisée par
l'absence de croissance de palier comme dans `etape_d_fleet_format_search.py`.*

**Conclusion en une phrase : la config actuelle (100% 2-step) reste
préférable au combo "gagnant" de l'Étape D une fois les vrais mécanismes de
production réintégrés — le résultat de l'Étape D était un artefact de sa
simplification, exactement comme suspecté à l'époque.**

---

## 1. Décisions de conception (raisonnement, avant tout chiffre)

### 1.1 Mécanisme "compte supplémentaire" par format (point 2 de la consigne)

Avant d'écrire le moindre code, j'ai fait auditer le moteur de production
existant (`extra_account_v4_multi.py`, `extra_account_v4_multi_stagger.py`)
pour comprendre EXACTEMENT comment la croissance fonctionne aujourd'hui.
Découverte clé : **aucune croissance individuelle de palier n'existe dans
le moteur de référence** — il n'y a aucun appel à un mécanisme de type
"upgrade de palier" dans le chemin exécuté. La SEULE croissance vient de
l'ouverture de comptes **supplémentaires à taille fixe**
(`EXTRA_UNIT_PALIER = BASE_PALIER × 2`), plafonnée par les vrais caps
firm.

**Conséquence directe (confiance ÉLEVÉE — vérification de code, pas une
hypothèse)** : ce mécanisme se transpose IDENTIQUEMENT aux formats instant
funding. Une "extra account" Instant Elite ou Instant GOAT est exactement
le même concept qu'une extra account 2-step aujourd'hui — un slot de plus
à prix fixe, juste financé immédiatement au lieu de passer par une
évaluation. **Aucune adaptation de mécanisme n'était nécessaire.**

### 1.2 Downgrade-on-reopen (rachat au palier de base pour Blueberry, le starter)

Vérifié dans le code (`reopen_account()`) : ce mécanisme fait
`acc["palier"] = acc["base_palier"]`, qui est DÉJÀ la valeur de création du
compte puisqu'aucune croissance individuelle n'existe (point 1.1). **C'est
un no-op dans le design actuel** (confiance ÉLEVÉE, même vérification) —
reste un no-op de la même façon pour Blueberry en Instant Elite. Conservé
tel quel.

### 1.3 Plafonds par firm (point 3 de la consigne)

Les réponses support obtenues le 08/08 (voir
`etape_a_formats_comptes_propfirms_2026-08-08.md` §6bis) confirment
explicitement que les plafonds portent sur **tout le capital du trader**
("per trader", "across all accounts and programs"), pas par format :
FTMO (400k, réponse support sans carve-out 1-Step), The5%ers (500k,
réponse support explicite "across all accounts and programs"), GFT (400k,
page officielle "tous modèles confondus"). **Confiance ÉLEVÉE** que les
mêmes valeurs s'appliquent identiquement aux formats retenus. Exception :
Blueberry reste sur l'ambiguïté déjà connue et non affectée par cette
session (450k codé vs 2M$ officiel "per trader", jamais tranchée) — valeur
conservatrice 450k conservée par prudence.

### 1.4 Prix réels par format

Le moteur actuel approxime les coûts via `FEE_RATIO` générique ou un proxy
FTMO pour FundedNext. Le nouveau moteur utilise le **prix réel** de chaque
format (issu d'`engine_multiformat.FORMATS`) quand disponible, avec repli
sur `FEE_RATIO` seulement si le palier précis n'est pas dans la grille
connue — amélioration de précision, pas une simplification.

### 1.5 The5%ers Hyper Growth — point ouvert, confiance FAIBLE-MOYENNE

Pas de mécanisme de croissance calendaire connu pour Hyper Growth
(contrairement à High Stakes). Modélisé avec un prix fixe au palier 40 000$
(le plus gros palier confirmé testé dans la recherche), 4 comptes fixes
comme aujourd'hui. **Signalé explicitement** : le vrai mécanisme Hyper
Growth (doublement du compte à chaque palier de profit atteint) n'est PAS
modélisé finement ici — simplifié pour rester comparable au reste du
moteur. Sous cette simplification, Hyper Growth déploie nettement moins de
capital total (4×40k=160k) que High Stakes (4×100k=400k) — **possible
sous-estimation du potentiel réel de ce format**, pas une conclusion
définitive.

---

## 2. Point 1 — Re-calibrage du risque

**Pourquoi c'était nécessaire** : les valeurs verrouillées (éval 2,25%,
flotte 2,75%, GFT 1,75%) avaient été calibrées sur l'ancien moteur 1-phase
flat (DD générique 8%/4j/10%) — pas sur les vraies contraintes DD par
format (trailing/statique, seuils réels).

**Méthode** : balayage grille élargie (éval 1,00 à 2,75%, flotte 1,75 à
3,25%), n=100, séparément par config (REF/WINNER), au plafond 1000$ (le
plus contraignant).

**Résultat inattendu et important** : au premier passage (grille resserrée
autour des anciennes valeurs), REF montrait déjà 12-43% de ruine — bien
au-dessus de l'ancien 1,83%/0%. Un premier bug a été trouvé et corrigé
(voir §4). Une fois corrigé et la grille élargie vers le bas, le vrai
optimum s'est révélé à un risque **nettement plus bas** que l'ancien :

| Config | Éval retenu | Flotte retenu | Profit (n=100) | Ruine | Année1<0 |
|---|---|---|---|---|---|
| REF | 1,25% | 1,75% | 4 216 279$ | 3% | 23% |
| WINNER | 1,25% | 2,25% | 3 690 459$ | 14% | 23% |

Pour WINNER, un vrai arbitrage a été identifié : le point à profit maximal
(éval 2,75%/flotte 2,75%) donnait 4 247 165$ mais avec **27% de ruine** —
soit seulement +15% de profit pour +13 points de ruine par rapport au point
retenu. Choix explicite de privilégier le point équilibré plutôt que de
maximiser aveuglément le profit (cohérent avec la pratique déjà établie
dans ce projet, ex. l'arbitrage FundedNext 25k vs 30k).

**Confiance** : ÉLEVÉE sur la méthode (reproduit fidèlement la logique du
`extra_account_v4_risk_sweep.py` original — maximiser le profit à un niveau
de ruine acceptable). MOYENNE sur le point exact retenu — une grille plus
fine (pas de 0,25 au lieu de 0,5) pourrait affiner marginalement, non fait
par souci de temps de calcul.

**Point le plus important de cette section** : même après re-calibrage, la
ruine et le P(année1<0) restent BIEN PLUS ÉLEVÉS que l'ancienne référence
(1,83%/0%, 5,5%/4%) pour LES DEUX configs. Ce n'est probablement pas un bug
résiduel — c'est la conséquence directe et attendue du remplacement de la
cible flat 8% par les vraies cibles par phase, dont certaines sont plus
dures que ce que l'ancien moteur supposait (FTMO/Blueberry réels 10% en
P1, contre 8% supposé avant — exactement le risque signalé dès l'audit du
08/08 qui a lancé ce chantier). **Confiance MOYENNE** sur cette
interprétation — je ne l'ai pas isolée avec un test dédié (ex. reproduire
REF avec la cible flat 8% mais les vraies phases pour confirmer que la
hausse de ruine vient bien de là et pas d'ailleurs) ; recommandé si ce
point devient bloquant pour une décision de capital réel.

---

## 3. Point 5 — Comparaison finale n=600, apples-to-apples

| Config | Plafond | Profit | Ruine | Année1<0 | Breaks moy. |
|---|---|---|---|---|---|
| REF | 1000$ | **4 297 185$** | **3,0%** | 27,5% | 205 |
| REF | 3000$ | **4 388 789$** | **0,5%** | 26,5% | 210 |
| WINNER | 1000$ | 3 639 957$ | 17,0% | 22,7% | 993 |
| WINNER | 3000$ | 4 302 618$ | 1,3% | 9,3% | 1174 |

**Lecture** : au plafond 1000$ (le scénario le plus contraignant, donc le
plus représentatif d'un démarrage réel), REF domine clairement WINNER sur
les deux axes — profit +18% ET ruine 6x plus faible (3% vs 17%). Au plafond
3000$, l'écart de profit se resserre (REF reste légèrement devant, +2%)
mais REF garde une ruine plus basse (0,5% vs 1,3%). **Sur aucun des deux
plafonds WINNER ne bat REF sur les deux axes profit ET ruine
simultanément.**

C'est l'inverse exact du résultat de l'Étape D (criblage simplifié), qui
donnait WINNER gagnant sur toutes les firms. Confirme l'hypothèse déjà
posée à l'époque : ce résultat était un artefact de l'absence de mécanisme
de croissance dans le criblage — une fois la vraie économie de croissance
(comptes supplémentaires + plafonds réels + fiscalité + coût du plafond de
cash) réintégrée, l'avantage de vitesse des formats rapides ne compense pas
le fait qu'ils déploient in fine moins de capital cumulé par cycle que les
2-step qui peuvent enchaîner plus de comptes supplémentaires avant de
plafonner.

---

## 4. Point 6 — Cascade check (obligatoire avant toute conclusion)

| Config | Plafond | Casse ≤30j | Casse ≤60j | Réserve min. 6 mois (pire cas) | % runs quasi-gelés |
|---|---|---|---|---|---|
| REF | 1000$ | 23,9% | 43,0% | 0$ | 2,3% |
| REF | 3000$ | 24,0% | 43,0% | 0$ | 0,0% |
| WINNER | 1000$ | **60,0%** | **84,1%** | 0$ | **16,2%** |
| WINNER | 3000$ | **60,1%** | **84,2%** | 0$ | 0,8% |

**Verdict cascade : GO pour REF (comportement cohérent avec les cascades
déjà vérifiées lors des sessions précédentes). PAS GO en l'état pour
WINNER** — taux de casse ≤30j/≤60j 2,5x plus élevés, et jusqu'à 16% des
runs quasi-gelés au plafond serré (1000$), contre 2,3% pour REF. Ce
n'est pas un nouveau mode de ruine caché (le mécanisme reste le même :
casses répétées avant déblocage complet, déjà identifié en session
précédente) mais une AMPLIFICATION nette de ce mécanisme sous WINNER —
cohérent avec le fait que les formats rapides/instant du combo gagnant
cassent et se rouvrent beaucoup plus vite (déjà visible dans les métriques
solo de l'Étape C : 316 casses/horizon pour Blueberry Instant Lite par
exemple, même si ce format précis n'est pas dans le combo retenu, la
tendance générale des formats rapides est la même).

**Ce résultat renforce plutôt qu'il ne contredit la conclusion de la
section 3** : le combo gagnant de l'Étape D n'est pas seulement moins
rentable une fois la vraie économie réintégrée, il a aussi un profil de
risque de cascade nettement moins bon.

---

## 5. Bug trouvé et corrigé pendant cette session

**Bug** : les comptes instant funding (0 phase d'évaluation) sont créés
directement en `phase="funded"` (cf. `engine_multiformat.make_acc_mf`).
Le compteur de déblocage échelonné (`group_funded_count`) ne se
déclenchait que sur une transition détectée "challenge→funded" — jamais
observable pour un compte qui démarre déjà financé. Résultat avant
correction : sous WINNER, Blueberry (le starter, en Instant Elite) ne
s'enregistrait jamais comme "financé", donc **aucune autre firm ne se
débloquait** — toute la simulation WINNER tournait en réalité sur un seul
compte Blueberry isolé (visible au symptôme : profit anormalement bas et
zéro sensibilité au risque d'évaluation dans le premier balayage).
**Corrigé** dans `etape_e_fleet_integration.py` (pas dans
`engine_multiformat.py`, qui reste intact) via un crédit explicite du
compteur à l'activation pour les formats à 0 phase. Tous les chiffres de
ce rapport utilisent la version corrigée.

Deuxième correction (architecture, avant le bug ci-dessus) : `process_
trade_mf` gère en interne le coût de casse (déduction directe sur la
réserve) sans respecter le plafond de cash réel injectable (`ceiling`) ni
la file d'attente de réouverture différée (`pending_reopen`) du moteur de
production. Neutralisé en passant `cost_override=0.0` à `process_trade_mf`
et en gérant le coût réel et la réouverture différée dans le nouveau
script, à l'identique du moteur de production original.

---

## 6. Fichiers produits (aucun script existant modifié)

- `etape_e_fleet_integration.py` — moteur intégré (multi-format + déblocage
  échelonné + comptes supplémentaires + fiscalité)
- `etape_e_risk_sweep.py` / `etape_e_risk_sweep_results.csv` — balayage de
  risque
- `etape_e_final_comparison.py` / `etape_e_final_comparison_results.csv` —
  comparaison n=600
- `etape_e_cascade_check.py` / `etape_e_cascade_check_results.csv` —
  cascade check

---

## 6bis. Audit de suivi (08/09) — trois points bloquants levés

### Point 1 — Cause de la hausse de P(année1<0) : ISOLÉE, PAS UN BUG

**Audit de code (hypothèse b)** : relecture ligne par ligne de
`process_trade_mf` (transition de phase, calcul `min_days` via
`trading_days_since_reset`, reset des compteurs) et de la détection de
casse dans `etape_e_fleet_integration.py`. Aucune anomalie trouvée — la
logique de transition P1→P2→funded, le comptage des jours distincts par
phase, et le reset des trackers à chaque transition (succès ou casse) sont
cohérents avec le comportement attendu.

**Test d'ablation empirique (hypothèse a)**, n=300, plafond 1000$, risque
retenu — remplace la structure de phases d'UNE SEULE firm à la fois par
l'ancienne cible flat (8%, 1 phase, 4 jours), en gardant son vrai DD
inchangé, les 4 autres firms restant sur leur vrai format :

| Variante | Année1<0 | Δ vs baseline |
|---|---|---|
| BASELINE (tout réel) | 29,3% | — |
| TOUT-FLAT (aucune firm réelle) | 12,3% | **-17,0 pts** |
| FTMO seule en flat | 21,3% | -8,0 pts |
| Blueberry seule en flat | 22,0% | -7,3 pts |
| Fivers seule en flat | 24,3% | -5,0 pts |
| GFT seule en flat | 27,3% | -2,0 pts |
| FundedNext seule en flat | 28,3% | -1,0 pt |

**Verdict : hypothèse (a) confirmée, ce n'est pas un bug.** Repasser
TOUTES les firms en cible flat fait retomber l'année1<0 de 29,3% à 12,3%
— la structure réelle à 2 phases (avec redémarrage complet à P1 en cas de
casse à N'IMPORTE quel stade, y compris financé) est bien la cause
dominante. **FTMO et Blueberry portent l'essentiel de l'effet** (-8,0 et
-7,3 points), cohérent avec l'hypothèse de départ — pas seulement à cause
de leur cible P1 plus dure (FTMO 10% vs 8% flat), mais surtout à cause du
**redémarrage complet du challenge** (P1 ET P2 à refaire) à chaque casse,
un mécanisme qui n'existait pas dans l'ancien moteur 1-phase et qui
compound la difficulté bien plus que la seule différence de cible.

**Répartition des casses par phase** (n=200, même config), pour vérifier
si la dégradation est concentrée en P2 :

| Firm | P1 | P2 | Financé |
|---|---|---|---|
| FTMO | 7,4% | 5,5% | 14,6% |
| Blueberry | 3,9% | 3,1% | 8,7% |
| Fivers | 5,3% | 5,3% | 12,2% |
| GFT | 9,3% | 6,6% | 12,1% |
| FundedNext | 2,0% | 1,2% | 2,8% |

**Pas de concentration en P2** — P1 accumule systématiquement autant ou
plus de casses que P2 (P2 représente 42-45% du total P1+P2 pour
FTMO/Blueberry/GFT, exactement 50% pour Fivers). Les casses en phase
"financé" restent la plus grosse catégorie individuelle partout, mais sans
dominer disproportionnellement (43-55% du total selon la firm). **La
dégradation vient de la COMBINAISON des deux phases à passer
séquentiellement avec redémarrage complet en cas d'échec — pas d'une
phase P2 spécifiquement fragile.**

**Confiance : ÉLEVÉE.** Contrairement au rapport précédent (confiance
MOYENNE, non isolé), ce point est maintenant tranché par un test
d'ablation empirique direct, pas seulement par un raisonnement.

### Point 2 — Ambiguïté Blueberry Prime vs Standard, clarifiée

Les deux produits Blueberry 2-step réels (recherche Étape A) :

| | Prime Challenge (2-Step) | 2-Step Challenge (standard, plus ancien) |
|---|---|---|
| Cibles | P1 8%, P2 6% | P1 10%, P2 5% |
| DD journalier | 4% | 5% |
| DD max | 10% (statique) | 10% (statique) |
| Jours min | 5j/phase | 3j/phase |
| Prix (25k$) | 165$ | inconnu |

**Pourquoi l'ambiguïté existe** : le code actuel du projet
(`point2_sequencing_engine.py:57`, dd=5.0/dd_max=10.0) matche les valeurs
du produit "standard", mais aucune vérification du compte réellement
souscrit par le projet n'a été faite — les deux produits coexistent chez
Blueberry et rien dans la documentation du projet ne précise lequel a été
acheté.

**Format utilisé dans REF pour cette session** : Prime Challenge
(`Blueberry_Prime2Step`), choisi par défaut car documenté comme "actuel"
dans la recherche Étape A — pas une vérification du compte réel.

**Pourquoi non tranché avant la comparaison finale** : ça nécessite de
vérifier le dashboard/contrat réel du compte Blueberry détenu, une
information hors de portée d'une recherche documentaire — signalé comme
point ouvert dès l'Étape A, jamais résolu depuis.

**Impact sur les chiffres REF** — testé maintenant (n=300, même risque,
plafond 1000$) :

| | Profit | Ruine | Année1<0 |
|---|---|---|---|
| Prime (retenu) | 4 111 798$ | 3,33% | 29,33% |
| Standard (alternative) | 4 152 466$ | 2,67% | 28,00% |

**Écart <1% sur le profit, <1,5 point sur ruine/année1<0 — dans la marge
de bruit Monte Carlo à n=300.** L'ambiguïté ne change PAS significativement
les chiffres de REF. Peut être laissée ouverte sans remettre en cause les
résultats de la section 3, mais reste à trancher avant tout déploiement de
capital réel (contrat/dashboard à vérifier).

### Point 3 — Niveau n du risk resweep, clarifié

Le balayage de risque (`etape_e_risk_sweep.py`) a tourné entièrement à
**n=100** (pas n=300 comme supposé) — indiqué explicitement dans le script
(`N_SIMS = 100`), un choix de vitesse d'itération pour explorer une grille
large (24 combinaisons × 2 configs). Le **point final retenu** (REF :
éval=1,25%/flotte=1,75%) a bien été reconfirmé à **n=600** — c'est
exactement ce qu'a fait `etape_e_final_comparison.py` (section 3 de ce
rapport, déjà reporté).

**Vérification supplémentaire demandée** : reconfirmation à n=600 du point
concurrent le plus proche (éval=1,00%/flotte=1,75%, qui avait une ruine
plus basse à n=100) :

| Risque | n | Profit | Ruine | Année1<0 |
|---|---|---|---|---|
| éval=1,25% (retenu) | 600 | 4 297 185$ | 3,0% | 27,5% |
| éval=1,00% (concurrent) | 600 | 4 214 407$ | 1,2% | 27,5% |

**Le classement directionnel tient à n=600** (éval=1,25% reste plus
rentable, éval=1,00% reste moins risqué — même relation qu'à n=100, pas un
retournement dû au bruit). L'écart profit (+2%) est modeste face à l'écart
ruine (3,0% vs 1,2%, soit 2,5x) — **éval=1,00%/flotte=1,75% est une
alternative légitime et plus prudente**, à considérer sérieusement plutôt
que de trancher uniquement sur le point retenu. Année1<0 est identique
entre les deux (confirme que ce taux est piloté par la structure de phases,
pas par le réglage fin du risque — cohérent avec le point 1).

---

## 7. Verdict final et recommandation

**Ne pas adopter le combo gagnant de l'Étape D.** La config actuelle
(100% 2-step) reste préférable une fois la vraie économie de croissance et
le cascade check pris en compte — profit comparable ou supérieur, ruine
nettement plus basse, cascade propre. L'Étape D a rempli son rôle
méthodologique (isoler l'effet du format), mais son résultat ne survit pas
à l'intégration dans le moteur complet, exactement comme anticipé quand la
limite de l'Étape D avait été signalée.

**Ce qui reste ouvert, par ordre de priorité** :
1. Confirmer si la hausse générale de ruine/année1<0 (même sous REF, vs
   l'ancienne référence 1,83%/0%) vient bien des vraies cibles par phase
   plus dures (FTMO/Blueberry 10% réel) et pas d'un autre effet non isolé —
   test dédié recommandé avant de considérer ce chiffre comme le nouveau
   verrouillé.
2. Trancher l'ambiguïté Blueberry Prime vs 2-Step standard (point ouvert
   depuis l'Étape A) — affecte directement REF.
3. Le mécanisme de croissance Hyper Growth simplifié (§1.5) sous-estime
   peut-être son potentiel réel — sans impact sur la conclusion actuelle
   (WINNER perd déjà sans ce potentiel), mais à garder en tête si Hyper
   Growth est reconsidéré isolément un jour.
4. Ce chiffre (REF, 4 297 185$/4 388 789$) **ne remplace pas encore** le
   chiffre verrouillé actuel (5 794 566$/5 898 897$) comme référence
   officielle du projet — il utilise un risque re-calibré différent et un
   moteur multi-phase différent, pas directement comparable terme à terme
   sans une décision explicite de bascule. À trancher séparément.
