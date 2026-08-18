# Étape T (08/10 nuit, suite 3) — Piste A' (2× Blueberry parallèle) implémentée et testée

Débloquée par la résolution du conflit sur le nombre de comptes Blueberry
(contact direct support, chat live 2026-08-10 : *"There is no fixed limit
on the number of active accounts... main restriction is the total
simulated capital ($400,000 total)... you can split that across any
number of accounts"*). Suit le scoping `etape_s_piste_a_prime_scoping_
2026-08-10.md` : généralise STARTERS avec un `STARTER_COUNT` (nombre de
comptes actives au jour 0 par firm), permettant 2 comptes Blueberry (même
risque éval) au lieu d'un seul, ou d'un Blueberry+GFT.

**Méthode** : `etape_t_piste_a_prime_2x_blueberry_2026-08-10.py`. n=300
(criblage 2 plafonds), n=600 (confirmation ceiling=3000$ uniquement, où
une domination a été trouvée). `solo_BB`/`BB_GFT_day0` reproduisent
EXACTEMENT les chiffres de référence déjà verrouillés du registre à
n=600/ceiling=3000$ (4 892 588$/0,50%/20,33% et 5 097 319$/0,67%/15,67%)
— validation croisée, confiance élevée sur BBx2.

## Résultats — criblage n=300

| Config | Coût j0 | Plafond 1000$ (profit/ruine/année1<0) | Plafond 3000$ (profit/ruine/année1<0) |
|---|---|---|---|
| solo_BB (réf) | 165$ | 5 005 612$ / 1,67% / 20,33% | 5 084 496$ / 0,33% / 19,67% |
| BB_GFT_day0 (réf Étape F) | 453$ | 4 738 812$ / 11,00% / 23,67% | 5 282 666$ / 1,00% / 16,00% |
| **BBx2 (piste A')** | **330$** | 4 722 355$ / 8,00% / 21,67% | 5 129 226$ / 0,33% / 16,67% |

Métriques de verrou de trésorerie (n=300) :

| Config | Plafond | jamais_financé | struct_jamais_complète | cash@1er_financement |
|---|---|---|---|---|
| solo_BB | 1000$ | 0,00% | 1,33% | 272$ |
| BB_GFT_day0 | 1000$ | 4,00% | 10,33% | 680$ |
| BBx2 | 1000$ | 4,33% | 7,33% | 487$ |
| solo_BB | 3000$ | 0,00% | 0,00% | 272$ |
| BB_GFT_day0 | 3000$ | 0,00% | 0,33% | 815$ |
| BBx2 | 3000$ | 0,00% | 0,00% | 544$ |

## Résultats — confirmation n=600, ceiling=3000$ (cascade check inclus)

| Config | Profit | Ruine | Année1<0 (pré/post) | casse≤30j | quasi_gelé |
|---|---|---|---|---|---|
| solo_BB (réf) | 4 892 588$ | 0,50% | 20,33% (9,33/11,00) | 24,71% | 0,33% |
| BB_GFT_day0 (réf) | 5 097 319$ | 0,67% | 15,67% (3,50/12,17) | 25,07% | 0,33% |
| **BBx2** | **4 940 735$** | **0,33%** | **17,00% (5,33/11,67)** | 24,99% | 0,17% |

Cascade check propre : casse≤30j (24,99%) dans la même fourchette que les
deux références (24,71%-25,07%), quasi_gelé (0,17%) meilleur que les deux
références, reserve_min_6mo(pire cas)=0,0$ identique aux 3 configs (pas
une anomalie — convention déjà observée sur toutes les configs GO du
projet).

## Verdict

**Plafond 1000$ : REJETÉ** — BBx2 reste dominé par solo_BB sur les 3 axes
(profit -5,7%, ruine 8,00% vs 1,67%, année1<0 21,67% vs 20,33%). Mais
**confirme directement l'hypothèse du coût jour 0 plus bas** : par
rapport à BB+GFT (déjà rejeté à ce plafond), BBx2 réduit nettement le
verrou de trésorerie — ruine quasi divisée par 1,4 (8,00% vs 11,00%),
jamais_financé similaire mais struct_jamais_complète -3pt (7,33% vs
10,33%), cash@1er_financement -28% (487$ vs 680$). Le coût jour 0 plus
bas aide bien, mais pas assez pour rattraper le fait de ne PAS
diversifier du tout à ce plafond serré.

**Plafond 3000$ : CONFIRMÉ n=600 + cascade GO — BBx2 domine strictement
solo_BB sur les 3 axes** (profit +0,98%, ruine -0,17pt, année1<0 -3,33pt).
Nouveau levier structurel validé. **Ne dépasse PAS BB_GFT_day0** (qui
reste supérieur sur profit et année1<0 à ce plafond, +3,2%/+1,33pt) mais
BBx2 gagne sur la ruine (0,33% vs 0,67%) et le coût d'entrée (330$ vs
453$, -27%) — un vrai arbitrage à 3 branches, pas une domination totale
d'une config sur toutes les autres. BBx2 est une alternative viable pour
un profil qui privilégie une ruine plus faible et un engagement de cash
initial plus faible, au prix d'un peu moins de profit/année1<0 que
BB_GFT_day0.

**Résumé à 3000$** : solo_BB (baseline, dominé par BBx2) < BBx2 (ruine la
plus faible, coût le plus faible parmi les 2 diversifications) <
BB_GFT_day0 (profit/année1<0 les meilleurs, ruine et coût plus élevés).
Décision d'adoption (BBx2 vs BB_GFT_day0 vs solo_BB à ce plafond) laissée
à l'utilisateur — les deux leviers de diversification (§2.6, cette étape)
sont maintenant candidats confirmés au même plafond, pas mutuellement
exclusifs sur le plan technique mais mutuellement exclusifs en pratique
(un seul choix de structure jour 0 par run).
