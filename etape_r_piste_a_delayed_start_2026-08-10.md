# Étape R (08/10 nuit) — Seuil de démarrage différé du 2e starter (BB+GFT)

Cible directement le mécanisme de ruine BB+GFT confirmé par trace à
l'Étape O (registre §2.11) : épuisement de marge de trésorerie initiale
(BB+GFT dépense 2,5× plus avant le 1er financement que solo_BB, 4,67% des
runs ne financent jamais rien à plafond 1000$). Idée testée : retarder
l'ouverture du 2e starter (GFT) jusqu'à un petit signal de stabilité du
1er (Blueberry) plutôt que de payer les deux au jour 0.

**Méthode** : `etape_r_piste_a_delayed_start_2026-08-10.py`, copie de
`etape_f_bootstrap_parallele_2026-08-09.py` généralisée avec un
`active_starters` mutable — GFT rejoint le mécanisme "starter" (coût
`base_cost` pré-déblocage, éligible au capital d'urgence) soit au jour 0
(référence `BB_GFT_day0`), jamais (référence `solo_BB`, GFT suit
uniquement le palier normal 25 000$), soit dès qu'un déclencheur DÉDIÉ et
bien plus bas se déclenche : survie sans casse de Blueberry (7/14/21j) ou
réserve accumulée (100/250/500$). n=300, plafonds 1000$/3000$, éval=1,25%.
`solo_BB` reproduit exactement la référence n=300 déjà connue
(`etape_g_circuit_breaker`, profit=5 005 612$/ruine=1,67%/année1<0=20,33%
pre=11,33%) — validation croisée, pas un bug.

## Résultats

**Plafond 1000$** — aucune variante ne bat solo_BB :

| Config | Profit | Ruine | Année1<0 | jamais_financé | cash@1er_financement |
|---|---|---|---|---|---|
| solo_BB (réf) | 5 005 612$ | 1,67% | 20,33% | 0,00% | 272$ |
| BB_GFT_day0 (réf Étape F) | 4 738 812$ | 11,00% | 23,67% | 4,00% | 680$ |
| delay_7j | 4 552 222$ | 14,33% | 25,67% | 6,33% | 636$ |
| delay_14j | 4 597 848$ | 13,33% | 25,00% | 5,33% | 648$ |
| delay_21j | 4 731 951$ | 10,33% | 22,33% | 3,33% | 630$ |
| delay_100/250/500$ | 5 044 299$/5 044 299$/5 043 825$ | 2,33%/2,33%/2,33% | 19,00%/19,00%/18,67% | 0,00% | 272$ |

**Plafond 3000$** — BB_GFT_day0 reste le meilleur, aucune variante ne le
dépasse :

| Config | Profit | Ruine | Année1<0 | cash@1er_financement |
|---|---|---|---|---|
| solo_BB (réf) | 5 084 496$ | 0,33% | 19,67% | 272$ |
| BB_GFT_day0 (réf Étape F) | 5 282 666$ | 1,00% | 16,00% | 815$ |
| delay_7j | 5 273 405$ | 0,67% | 15,33% | 790$ |
| delay_14j | 5 258 210$ | 0,67% | 15,67% | 806$ |
| delay_21j | 5 243 999$ | 1,00% | 15,33% | 743$ |
| delay_100/250/500$ | 5 159 439$/5 159 439$/5 156 221$ | 0,33% | 18,00%/18,00%/17,67% | 272$ |

## Verdict : REJETÉ — aucune domination sur 2+ axes à aucun plafond

**Plafond 1000$** : les délais en JOURS (7/14/21j) restent nettement pires
que solo_BB sur les 3 axes (ruine 10-14% vs 1,67%, année1<0 22-26% vs
20,33%) — un délai de quelques semaines ne suffit pas à protéger le
budget partagé, le coût de GFT (288$) reste engagé sur le même plafond
serré une fois le délai écoulé. Les délais en RÉSERVE (100/250/500$)
donnent des résultats quasi identiques à solo_BB (cash@1er_financement
= 272$, IDENTIQUE à solo_BB) : le seuil ne se déclenche quasiment jamais
avant que Blueberry finance déjà seul — ces 3 variantes convergent de
facto vers "ne jamais ouvrir de 2e starter" dans la plupart des runs à ce
plafond, donc l'écart (marginal, +0,8% profit / -1,3pt année1<0 / +0,67pt
ruine) est un effet de bord résiduel, pas une vraie stratégie de
diversification.

**Plafond 3000$** : toutes les variantes différées font PIRE que
BB_GFT_day0 sur profit ET année1<0 (delay_7j le plus proche, encore
-0,2% profit et +0,3pt ruine) — retarder l'ouverture ne fait ici que
perdre une partie du bénéfice de diversification sans rien gagner en
retour, puisqu'à ce plafond le cash n'est de toute façon jamais la
contrainte active.

**Diagnostic** (confirmé par les métriques de trace, pas déduit) : le
délai en JOURS ne cible pas le bon levier — il retarde le PAIEMENT dans
le temps mais engage quand même le plein coût sur le même budget total,
donc n'atténue pas l'épuisement de marge identifié à l'Étape O ; les
runs `jamais_financé` (6,33%/5,33%/3,33% pour 7j/14j/21j) restent du même
ordre de grandeur que BB_GFT_day0 (4,00%), voire pires pour les délais
courts. Le délai en RÉSERVE cible la bonne variable (disponibilité de
cash) mais aux seuils testés (100-500$), il se déclenche trop rarement
pour avoir un effet distinct de "ne jamais ouvrir GFT" — protège le
budget uniquement en annulant de facto la diversification recherchée.

**Condition de réouverture** : seuils de réserve nettement plus élevés
(au-delà de 500$, testant jusqu'à un point proche du seuil normal GFT de
25 000$ où le lever perd tout son intérêt) ne sont pas prometteurs a
priori — la fenêtre utile semble étroite ou inexistante entre "trop tôt
(épuise le budget)" et "trop tard (dégénère en solo_BB)". Pas de piste
concrète identifiée pour la rouvrir ; le mécanisme de ruine BB+GFT à
1000$ reste donc sans solution de mitigation trouvée à ce jour (bootstrap
parallèle day0 = rejeté §2.6, démarrage différé = rejeté ici).

Pas de confirmation n=600 (aucun candidat ne remplit le critère de
domination sur 2 axes sans dégrader le 3e).
