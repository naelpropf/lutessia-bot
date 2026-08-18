# Étape E — Audit seuils de déblocage + risque GFT (08/09/2026, suite)

*Complète les fichiers Étape E précédents (tous figés). Répond à deux
paramètres hérités de l'ancien moteur flat-8% jamais reconfirmés sous le
nouveau moteur multi-phase : les seuils de déblocage échelonné et le
risque spécifique GFT.*

---

## Point 2 — Risque GFT : confirmé, pas de changement

**Contexte** : le resweep de risque général (éval descendu à 1,00-1,25%)
avait laissé `GFT_EVAL_RISK` fixe à 1,75% (hérité, jamais retesté) — ce
qui inverse la relation d'origine (GFT passe d'un risque RÉDUIT vs les
autres à un risque plus ÉLEVÉ, puisque 1,75% > 1,00-1,25%).

**Test** : grille gft_eval_risk ∈ {1,00 ; 1,25 ; 1,50 ; 1,75 ; 2,00 ; 2,25 ;
2,50 ; 2,75}%, aux deux points de risque général retenus (1,00% et 1,25%),
n=300, plafond 1000$.

**Résultat** : le profit augmente jusqu'à 1,75% puis plafonne (variations
<0,5% de 1,75% à 2,75%, dans le bruit), avec une légère dégradation
d'année1<0 au-delà de 1,75% (ex. eval=1,00% : année1<0 passe de 27,0% à
28,7% entre gft=1,75% et gft=2,25%). **1,75% reste un choix quasi-optimal
sous le nouveau moteur — pas de changement justifié.**

---

## Point 1 — Seuils de déblocage échelonné

**Criblage léger** (un seuil à la fois, n=300, plafond 1000$, risque
éval=1,00%/flotte=1,90%/gft=1,75%) autour des valeurs actuelles
(FTMO=1k/Fivers=15k/GFT=25k/FundedNext=25k) :

| Seuil | Écart max testé | Verdict |
|---|---|---|
| FTMO | +0,22% (à 2000) | Bruit, garder 1000 |
| Fivers | +0,21% (à 10000, mais ruine plus haute) | Bruit/pas d'amélioration nette, garder 15000 |
| GFT | +0,11% (quasi plat sur toute la plage) | Bruit, garder 25000 |
| FundedNext | **+1,03% (à 15000)** | **Signal réel, creusé plus loin** |

**FundedNext creusé** (500 à 17500, n=300) : le profit continue de monter
en descendant le seuil jusqu'à un pic à **5000** (4 678 264$, +2,65% vs
seuil actuel), puis redescend en dessous de 5000 (500-3000 tous moins bons
ET plus risqués). 5000 est le vrai optimum local sur la plage testée.

**Confirmation n=600, deux plafonds, ancien (25k) vs nouveau (5k)** :

| | Plafond | Profit | Ruine | Année1<0 |
|---|---|---|---|---|
| Ancien (25k) | 1000$ | 4 579 059$ | 0,83% | 27,8% |
| **Nouveau (5k)** | 1000$ | 4 673 628$ (+2,1%) | 2,0% (2,4x) | 28,7% |
| Ancien (25k) | 3000$ | 4 584 524$ | 0,67% | 27,8% |
| **Nouveau (5k)** | 3000$ | 4 691 764$ (+2,3%) | 1,33% (2x) | 27,7% |

**Ce n'est PAS un free lunch** — le profit supplémentaire s'accompagne
d'une ruine ~2x plus élevée aux deux plafonds. Cohérent avec le mécanisme
de ruine résiduelle déjà identifié en session précédente (grinding avant
déblocage complet) : débloquer FundedNext plus tôt réduit le temps passé
dans cette phase fragile, mais aussi la marge de sécurité accumulée avant
d'y arriver.

**Cascade check** (n=600, seuil 5k, deux plafonds) :

| Plafond | Casse≤30j | Casse≤60j | Quasi-gelé |
|---|---|---|---|
| 1000$ | 20,9% | 38,1% | 2,0% |
| 3000$ | 20,9% | 38,0% | 0,33% |

**GO aux deux plafonds** — taux de casse même légèrement meilleurs que la
config actuelle (21,1%/38,6%), le seul signal négatif est le quasi-gelé
qui double (1,0%→2,0% à 1000$), cohérent avec et de même ampleur que la
hausse de ruine déjà mesurée — pas un nouveau mode de risque caché, le
même arbitrage vu sous un autre angle.

---

## Décision à prendre

**FTMO, Fivers, GFT (seuil et risque)** : aucun changement — confirmés
robustes sous le nouveau moteur.

**FundedNext, seuil de déblocage** : arbitrage réel entre +2% de profit et
une ruine ~2x plus élevée (mais toujours ≤2% en absolu). Deux options :
- **Garder 25k$ (actuel)** : ruine plus basse (0,67-0,83%), profit
  légèrement moindre
- **Passer à 5k$** : profit +2,1%/+2,3%, ruine 2x plus haute (1,33-2,0%)

Pas de recommandation par défaut cette fois — l'écart de ruine, bien que
petit en absolu, est proportionnellement significatif (x2), et le choix
dépend de la tolérance au risque plutôt que d'un critère objectif clair.

## Chiffres REF actualisés selon le choix

| Config risque + seuil | Plafond | Profit |
|---|---|---|
| éval=1,00%/flotte=1,90%, seuil FN=25k (prudent, recommandé précédemment) | 1000$/3000$ | 4 579 059$ / 4 584 524$ |
| éval=1,00%/flotte=1,90%, seuil FN=5k (profit+) | 1000$/3000$ | 4 673 628$ / 4 691 764$ |
| éval=1,25%/flotte=1,90%, seuil FN=25k (profit max risque) | 1000$/3000$ | 4 663 331$ / 4 756 842$ |
| éval=1,25%/flotte=1,90%, seuil FN=5k | non testé | — |
