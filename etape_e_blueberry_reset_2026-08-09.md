# Étape E — Mécanisme reset Blueberry (2× prix original) : premier gain net confirmé (08/09/2026)

*Suite de `etape_e_annee1_levers3_2026-08-09.md` (point 1 : recherche de
mécanismes reset officiels par firm). Implémentation et test du mécanisme
Blueberry, confirmé verbatim par le support (confiance élevée). Script :
`etape_e_blueberry_reset_2026-08-09.py`. Config : REF, seuils actuels,
plafond 1000$, testé sur les 2 points de risque candidats
(éval=1,00%/flotte=1,90% et éval=1,25%/flotte=1,90%), n=300 puis n=600.*

**Après 8 leviers rejetés sur 3 sessions (risque, seuils, calendrier,
coût de réouverture, taille de flotte), c'est le premier gain net réel,
confirmé sur les deux points de risque, avec cascade check GO.**

---

## Mécanisme implémenté

Confirmé par le support Blueberry (verbatim, confiance élevée) :
- À la casse d'un compte Blueberry **déjà FINANCÉ**, reset disponible à
  **2× le prix du challenge ORIGINAL** (taille d'achat, pas taille
  actuelle — sans objet ici, aucune croissance individuelle de palier
  n'existe dans ce moteur).
- Le compte reprend **directement au niveau financé**, sans repasser
  P1/P2.
- **Usage unique à vie par compte** — le compte issu du reset ne peut
  plus jamais en bénéficier.
- Fenêtre de 7 jours pour réclamer : **sans effet ici**, le moteur rouvre
  déjà immédiatement dès que la trésorerie le permet (comme tous les
  autres rachats du projet) — vérifié avant implémentation, non modélisée.
- Exclusions "instant funding" et "comptes scaled" (mentionnées dans la
  recherche initiale, absentes de la réponse support) : **vérifiées sans
  objet** — REF utilise Blueberry_Prime2Step (a des phases, pas instant),
  et aucun compte Blueberry du moteur ne "scale" jamais individuellement
  (design confirmé Étape E). Le levier s'applique donc à tous les comptes
  Blueberry actifs (départ + supplémentaires) sans distinction.
- Une casse en phase ÉVALUATION (P1/P2) n'est pas concernée — reste un
  restart normal (la réponse support parle spécifiquement de "funded
  account breaches").

Nouveau flag `_reset_used` par compte Blueberry (False à la création),
implémenté dans un script isolé, aucun script existant modifié.

---

## Résultats confirmés n=600 (les deux points de risque)

| Point de risque | Config | Profit | Ruine | Année1<0 total | dont pré | dont post | Casse≤30j | Casse≤60j | Quasi-gelé |
|---|---|---|---|---|---|---|---|---|---|
| éval=1,00/flotte=1,90 | Baseline | 4 541 657$ | 1,17% | 27,67% | 16,33% | 11,33% | 21,55% | 39,45% | 1,2% |
| | **Reset actif** | **4 678 592$** (+3,02%) | **0,67%** (-43% rel.) | **23,50%** (-4,17pt) | **11,83%** (-4,50pt) | 11,67% (bruit) | 21,53% | 39,75% | 0,7% |
| éval=1,25/flotte=1,90 | Baseline | 4 641 342$ | 3,17% | 26,33% | 13,50% | 12,83% | 24,60% | 43,45% | 3,2% |
| | **Reset actif** | **4 786 043$** (+3,12%) | **1,67%** (-47% rel.) | **22,67%** (-3,66pt) | **10,67%** (-2,83pt) | 12,00% (-0,83pt) | 24,61% | 43,85% | 1,7% |

**Cascade check GO sur les deux points** : casse≤30j/60j statistiquement
inchangées (écarts <0,4pt, dans le bruit habituel), et le taux de "quasi-
gelé" (réserve finale <100$) **s'améliore** (1,2%→0,7% et 3,2%→1,7%) —
aucun signal d'un risque caché introduit par le mécanisme.

**Le gain vient presque entièrement du volet PRÉ-déblocage** (-4,50pt à
-2,83pt selon le point de risque, contre -0,83pt à +0,34pt côté post) —
cohérent avec le mécanisme : Blueberry est le compte STARTER, et une
casse post-financement mais avant que le reste de la flotte s'ouvre est
exactement le scénario où éviter un restart complet P1+P2 accélère le
plus la complétion de la structure (évite le basculement en catégorie
"pré-déblocage jamais complété à 12 mois"). Le volet post-déblocage
bouge peu, cohérent avec la caractérisation du round 2
(`etape_e_annee1_levers_2026-08-09.md`) : le problème post-déblocage est
diffus sur les 5 firms, un levier limité à Blueberry ne peut traiter
qu'une fraction de cette composante.

`bb_resets_used` moyen ≈ 2,9 par run (usage modeste en nombre absolu mais
décisif — chaque reset évite un cycle P1+P2 potentiellement long au
moment le plus critique de la trajectoire).

---

## Conclusion

**Premier levier confirmé gagnant sur les 9 testés au total** (3
sessions). Gain net réel et robuste : +3,0-3,1% profit, ruine quasiment
divisée par 2, année1<0 -3,7 à -4,2pt, aucune dégradation cascade.

**Ce mécanisme n'est PAS encore appliqué au chiffre de référence du
projet** — comme pour les 4 décisions ouvertes déjà documentées dans
`etape_e_synthese_globale_2026-08-09.md`, l'adoption dans REF est une
décision explicite à prendre, pas automatique. Question ouverte
supplémentaire posée par ce résultat : lequel des deux points de risque
adopter avec ce mécanisme actif change légèrement le calcul (l'écart de
ruine entre les deux points se resserre nettement une fois le reset actif
— 0,67% vs 1,67%, contre 1,17% vs 3,17% sans — ce qui pourrait faire
pencher vers éval=1,25% pour le profit un peu supérieur, la ruine restant
basse dans l'absolu).
