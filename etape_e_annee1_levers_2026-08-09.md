# Étape E — Recherche de leviers annee1<0, volets pré/post-déblocage (08/09/2026)

*Suite directe de `etape_e_diagnostic_annee1_2026-08-09.md` (décomposition
57%/43% pré/post-déblocage). Script : `etape_e_annee1_levers_2026-08-09.py`.
Config de base : REF, éval=1,00%/flotte=1,90%/GFT=1,75%, seuils FTMO=1k/
Fivers=15k/GFT=25k/FundedNext=25k, plafond 1000$, n=300 (exploration —
aucun levier n'a montré un effet net positif justifiant une confirmation
n=600, voir conclusion).*

---

## Volet 1 — Pré-déblocage (57% du problème)

Deux leviers 08/08 retestés sous le moteur intégré actuel.

| Config | Profit | Ruine | Année1<0 total | dont pré | dont post | Casses moy. |
|---|---|---|---|---|---|---|
| **Baseline** (FTMO=1000$, gap=0) | 4 646 345$ | 2,67% | 30,67% | **18,00%** | 12,67% | 170 |
| FTMO seuil=500$ | 4 656 149$ | 2,33% | 31,33% | 17,67% | 13,67% | 170 |
| FTMO seuil=250$ | 4 637 156$ | 2,67% | 31,67% | 18,00% | 13,67% | 170 |
| FTMO seuil=0$ | 4 373 272$ | **10,67%** | 34,67% | 21,33% | 13,33% | 157 |
| Étalement gap=1 semaine | 4 604 476$ | 2,67% | 30,67% | 18,00% | 12,67% | 169 |
| Étalement gap=2 semaines | 4 567 536$ | 2,67% | 29,33% | 18,67% | 10,67% | 168 |
| Étalement gap=4 semaines | 4 512 062$ | 2,67% | 28,67% | 19,00% | 9,67% | 167 |

**(a) Seuil de déblocage FTMO abaissé** : aucun effet sur la part
pré-déblocage (18,00% à 1000$ et à 250$, 17,67% à 500$ — écarts dans le
bruit à n=300). **0$ (déblocage FTMO immédiat, sans réserve tampon) est
nettement délétère** : ruine multipliée par 4 (2,67%→10,67%), année1<0
pré-déblocage AGGRAVÉ (18,00%→21,33%) — retirer tout tampon de réserve à
ce stade prive la flotte de cash pour absorber les casses suivantes.
**Levier rejeté** : déjà à son optimum au seuil actuel (1000$), aucune
marge supplémentaire à gratter de ce côté.

**(b) Étalement calendaire minimal entre ouvertures** : l'année1<0 total
baisse en apparence avec le gap (30,67%→28,67% à 4 semaines), mais
**ce n'est pas une vraie réduction du risque pré-déblocage** — la part
*pré* elle-même ne s'améliore pas (18,00%→19,00%, légèrement pire), tout
le mouvement vient de la part *post* qui baisse (12,67%→9,67%). Explication
mécanique cohérente : retarder l'ouverture groupée retarde aussi
`full_structure_month`, ce qui repousse mécaniquement certains runs de la
catégorie "post" (structure complète <12 mois) vers "pré" (structure
complète >12 mois) sans rien changer au risque réel — un artefact de la
frontière de classification, pas un levier. Coût réel en profit (-2,9% à
4 semaines) sans bénéfice net confirmé. **Levier rejeté.**

**Conclusion volet 1** : aucun des deux leviers connus (08/08) ne produit
d'amélioration réelle de la composante pré-déblocage sous le moteur
intégré actuel — le seuil FTMO est déjà optimal, l'étalement calendaire ne
fait que déplacer la frontière de classification.

---

## Volet 2 — Post-déblocage (43% du problème)

### Caractérisation (baseline, n=300)

38/300 runs (12,67%) sont année1<0 post-déblocage. Parmi ces 38 runs,
proportion ayant au moins une casse d'un compte DÉJÀ FINANCÉ après le mois
de structure complète, par firm :

| Firm | Runs touchés | % | Casses totales |
|---|---|---|---|
| FTMO | 37/38 | 97,4% | 554 |
| Blueberry | 36/38 | 94,7% | 331 |
| Fivers | 36/38 | 94,7% | 484 |
| FundedNext | 36/38 | 94,7% | 121 |
| GFT | 35/38 | 92,1% | 467 |

**Le mécanisme est diffus, pas concentré sur une firm** — contrairement à
l'hypothèse de cadrage (FTMO/Blueberry dominants, par analogie avec
l'ablation du 08/08 sous l'ANCIEN moteur). Sous le nouveau moteur, 92-97%
des runs post-déblocage-négatifs ont une casse financée touchant CHAQUE
firm, sans exception notable. Le nombre total de casses par firm suit
grossièrement le nombre de comptes actifs (FTMO=2 day0, Fivers=4 day0 —
les plus casseurs en absolu — vs Blueberry/GFT/FundedNext=1 chacun), pas
une fragilité structurelle propre à une firm. **Implication directe** : un
levier ciblé sur une seule firm (ex. capital protégé Blueberry, comme
suggéré par le diagnostic pré-déblocage) ne traiterait pas la composante
post — le problème vient de la taille de la flotte elle-même (plus de
comptes financés = plus d'opportunités de casse-restart), pas d'un maillon
faible identifiable.

### Levier testé : rampe recalibrée, restart post-financement uniquement

Contrairement à la rampe globale du 08/09 (RAMP_RISK=2,0% appliqué
partout, invalidée), ce levier active une rampe UNIQUEMENT quand un compte
DÉJÀ financé casse et doit rejouer un cycle complet — pas en éval initiale
— avec des valeurs sous le risque flotte actuel (1,90%) comme recommandé
par le diagnostic précédent.

| Config | Profit | Ruine | Année1<0 total | dont pré | dont post | Casses moy. |
|---|---|---|---|---|---|---|
| Baseline (aucune rampe) | 4 646 345$ | 2,67% | 30,67% | 18,00% | 12,67% | 170 |
| Rampe ciblée 1,50% | 4 652 204$ | 2,33% | 30,33% | 18,67% | 11,67% | 165 |
| Rampe ciblée 1,70% | 4 633 906$ | 2,67% | 31,00% | 19,00% | 12,00% | 169 |

Tous les écarts (profit ±0,3%, ruine ±0,34pt, année1<0 post ±1,0pt) sont
dans la bande de bruit habituelle à n=300 pour ce moteur (cf. l'écart
année1<0 confirmé bruit lors de l'audit du 08/09 sur un écart comparable,
29,3% vs 27,5%). **Aucun signal net positif** — contrairement à la rampe
globale (nettement négative, -1,7% profit confirmé), la version ciblée
n'est ni clairement bénéfique ni clairement délétère : elle est neutre.
**Pas de levier gagnant, mais pas non plus un résultat qui inverse la
conclusion du 08/09** (ne pas réintroduire de rampe sans gain démontré).

---

## Conclusion générale

**Aucun des quatre leviers testés (seuil FTMO réduit, étalement calendaire,
rampe ciblée 1,50%, rampe ciblée 1,70%) ne produit d'amélioration nette
confirmée** — soit neutre dans le bruit, soit franchement délétère (seuil
FTMO=0$). Conformément à la méthodologie du projet, aucun n'est retenu pour
confirmation n=600 et **aucun changement de config n'est appliqué**.

Caractérisation utile pour la suite : la composante post-déblocage n'a pas
de maillon faible identifiable par firm — c'est un effet mécanique de la
taille de la flotte (plus de comptes financés = plus d'occasions de
casse-restart complet), pas un point de fragilité isolable. Un futur levier
efficace devra probablement agir sur le COÛT du restart lui-même (ex.
réduire le nombre de phases à rejouer après une casse en phase financée,
si un tel mécanisme existe chez une firm) plutôt que sur le risque par
trade ou le calendrier de déblocage — piste non explorée ici.
