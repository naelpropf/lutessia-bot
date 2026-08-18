# Étape Y (08/10 nuit, suite 9) — Test d'ajout de Fivers au mécanisme extra-compte

## Contexte (recherche mémoire, résumé)

The5%ers concentrait ~75% du risque de trésorerie personnelle pire-cas
pré-immunité dans l'ancien moteur (DD journalier 3% plus strict que
FTMO/Blueberry 5%, `project_preimmunity_5ers_delay_2026-08-06`) — cet
insight a depuis été généralisé dans le déblocage échelonné actuel
(Fivers débloque à réserve≥15 000$, après FTMO/Blueberry). Le copytrade
Fivers est déjà vérifié non-bloquant (confirmé utilisateur), non
retraité ici.

## Implémentation

`etape_y_fivers_growth_test_2026-08-10.py` — copie de `etape_q`
(REF+V2 combine), `growth_firms` paramétré (baseline =
`("Blueberry","FTMO","GFT")` vs test = `+("Fivers",)`), utilisant les
valeurs déjà présentes dans le code (`FIRM_CAPITAL_CAP["Fivers"]=500000`,
`FIRM_MAX_ACCOUNTS["Fivers"]=5`), sans toucher au module `ei` partagé
(hypothèse à tester, pas une correction confirmée comme Blueberry).

**Gap d'implémentation découvert en écrivant le test** : le palier de
base Fivers n'existe pas dans `BASE_PALIER` (dict par firm, corrigé ici
localement via `FIVERS_PALIER[format]`, comme le fait déjà
`base_palier_cost()` dans le moteur pour l'ouverture initiale).

## Résultat arithmétique AVANT toute simulation

Capital initial Fivers = 4 comptes × 100 000$ (High Stakes) = **400 000$**.
Cap agrégé = **500 000$** → marge = **100 000$**. Unité d'extra-compte
(même convention 2× que Blueberry/FTMO/GFT) = 2×100 000$ = **200 000$**
> 100 000$ de marge → **le cap CAPITAL bloque structurellement tout
extra-compte Fivers, quelle que soit la réserve disponible.** Le cap
NOMBRE (5, donc 4+1 max) est encore plus restrictif dans l'absolu mais
n'est même pas la contrainte active.

## Vérification empirique (n=300, 2 plafonds)

| Config | Plafond | Profit | Ruine | Année1<0 | Fivers extra (moy) |
|---|---|---|---|---|---|
| Baseline (sans Fivers extra) | 1000$ | 5 955 479$ | 1,00% | 21,67% | 0,00 |
| **+ Fivers extra** | 1000$ | **5 955 479$ (identique)** | **1,00% (identique)** | **21,67% (identique)** | **0,00** |
| Baseline | 3000$ | 5 964 918$ | 0,67% | 21,67% | 0,00 |
| **+ Fivers extra** | 3000$ | **5 964 918$ (identique)** | **0,67% (identique)** | **21,67% (identique)** | **0,00** |

**Résultat bit-identique entre baseline et Fivers-extra, aux deux
plafonds, sur les 300 runs** — confirme empiriquement la prédiction
arithmétique : `fivers_extra_moy=0,00` partout. Aucun compte Fivers
supplémentaire n'a jamais ouvert.

## Verdict

**La concentration de risque déjà documentée pour Fivers NE SE
MATÉRIALISE PAS avec ce lever — parce que le lever ne s'active jamais.**
Contrairement à Blueberry (où le cap NOMBRE bloquait un mécanisme qui,
une fois débloqué, générait un vrai gain de +16%), le cap CAPITAL de
Fivers bloque le mécanisme AVANT même qu'il puisse produire un seul
compte — la question "est-ce que plus de comptes Fivers aggrave le
risque déjà connu" ne se pose pas empiriquement ici, elle est
structurellement neutralisée par l'arithmétique des paliers.

**Pas de confirmation n=600 nécessaire** (aucune domination, aucun
effet du tout — pas juste petit, rigoureusement nul). Pas un bug de
paramètre comme Blueberry (les valeurs 500 000$/5 sont correctes vis-à-
vis du cap confirmé) — plutôt un décalage entre la convention générique
"extra = 2× palier de base" (calibrée pour Blueberry/FTMO/GFT dont le
palier de départ est petit, 25-50k$) et le cas Fivers dont le palier de
départ (100k$ High Stakes) est déjà large par rapport à son propre cap
agrégé (500k$) — la marge restante après les 4 comptes initiaux est trop
étroite pour absorber un doublement.

**Pour ouvrir cette piste un jour**, il faudrait soit une unité d'extra-
compte plus petite que 2× le palier de base pour Fivers spécifiquement
(ex. un palier partiel), soit un format de départ plus petit (Hyper
Growth, 40k$) qui laisserait plus de marge sous le cap 500k$ — mais
changer de format Fivers est un changement de périmètre plus large,
non demandé ici et non exploré.
