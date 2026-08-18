# Étape X (08/10 nuit, suite 6) — Décomposition du gain Blueberry + retests piste B et A'

Suite au gain majeur mesuré à l'Étape V (+16,4-16,5% profit REF+V2 après
correction du cap Blueberry), ce rapport clarifie le MÉCANISME du gain
avant toute adoption, et reteste piste B (fongibilité) et piste A' (BBx2)
sous le régime corrigé.

## 1. Décomposition du mécanisme (n=600, même seed, REF+V2 combine)

`etape_w_blueberry_gain_decomposition_2026-08-10.py` — copie exacte de
`etape_q` (V2 + FTMO-10% + GFT Goat Guard), instrumentation ajoutée :
comptes extra par firm, P&L net par firm.

### (a) Comptes extra Blueberry, avant/après

| Plafond | Avant (cap=3) | Après (illimité) |
|---|---|---|
| 1000$ | 1,99 | **6,98** |
| 3000$ | 2,00 | **7,00** |

Confirme le mécanisme exact : plafonné à 2 extras (starter+2=3 comptes)
avant, ~7 après — cohérent avec le calcul théorique
((400 000$-25 000$)/50 000$=7,5).

### (b) Détournement d'autres firms ? Comparaison par firm, avant/après (n=600, 1000$)

| Firm | Extra comptes avant/après | Net $ avant | Net $ après | Δ |
|---|---|---|---|---|
| **Blueberry** | 1,99 → 6,98 | 588 380$ | **1 718 808$** | **+1 130 428$ (+192,2%)** |
| FTMO | 2,99 → 2,99 | 1 793 112$ | 1 790 662$ | -2 450$ (-0,14%) |
| Fivers | — (pas de mécanisme extra) | 1 852 237$ | 1 849 734$ | -2 503$ (-0,14%) |
| GFT | 2,99 → 2,99 | 1 681 905$ | 1 680 087$ | -1 818$ (-0,11%) |
| FundedNext | — (pas de mécanisme extra) | 884 811$ | 883 531$ | -1 280$ (-0,14%) |

(à 3000$, mêmes proportions : Blueberry +1 132 916$/+192,2%, autres firms
-0,05% à -0,11% chacune)

**Verdict clair : PAS de détournement de comptes.** Le nombre d'extra-
comptes FTMO et GFT est **rigoureusement identique** avant/après (2,99
exactement dans les deux cas) — ils saturent déjà leur propre cap $
(400 000$) indépendamment de Blueberry. Il existe un effet de bord
MINEUR (-0,05% à -0,14% de P&L, PAS de compte en moins) sur les 4 autres
firms : Blueberry étant premier dans l'ordre d'itération
`GROWTH_FIRMS_EXTRA=("Blueberry","FTMO","GFT")`, il consomme la réserve
partagée en priorité à certains instants, retardant très légèrement le
financement des extras FTMO/GFT (sans jamais changer leur nombre final
atteint). **Ce coût de trompe-l'œil (~8 000$/1000$ ceiling, ~0,7% du
gain brut) est négligeable face au gain Blueberry (+1 130 428$)** — la
tension EV/$ évoquée en hypothèse (Blueberry classé avant-dernier) ne se
matérialise quasiment pas dans les faits, parce que la réserve partagée
n'est PAS un jeu à somme nulle sur cette flotte (cohérent avec le
diagnostic fongibilité §2.8 : réserve abondante la plupart du temps).

**Réconciliation comptable** (contrôle de cohérence) : somme des Δ par
firm = +1 122 377$ (1000$) = Δ `final_net_split` (avant IS). Δ profit net
mesuré à l'Étape V = +808 843$. Écart = 313 534$ (27,9% du gain brut) =
IS supplémentaire payé sur le profit additionnel généré — logique et
attendu, pas une anomalie.

### (c) Volume pur ou compounding indirect ?

`mean_days_to_fund` (délai moyen de financement, TOUS événements de
financement confondus, flotte entière) est **rigoureusement identique**
avant/après aux 2 plafonds (66,40452486496913 jours, à 13 décimales
près — vérifié dans les CSV de l'Étape V). Le mécanisme extra-compte ne
s'active QU'APRÈS `fleet_unlocked=True` (`process_extra_account`) — la
correction du cap ne peut donc PAS accélérer le déblocage initial de la
structure à 5 firms, seulement ajouter des comptes APRÈS ce déblocage.

**Verdict : gain quasi exclusivement VOLUME**, pas compounding indirect.
Confirmé par (b) : si le gain venait d'un déblocage plus rapide de la
flotte profitant à toutes les firms, on verrait les 4 autres firms
gagner aussi — elles perdent (légèrement) à la place. Le mécanisme est
simple : Blueberry, dont le format (Prime2Step + reset) est déjà
rentable et rapide, tournait juste avec 3,5× moins de comptes que son
propre potentiel de croissance ne le permettait — pas un déblocage de
synergie de flotte.

## 2. Retest piste B (fongibilité) sous cap corrigé — n=300, 2 plafonds

`etape_h_fongibilite_slots_2026-08-10.py`, mode "screen", relancé tel
quel (le module `ei` partagé porte déjà la correction) :

| Plafond | Baseline REF (non-fongible) | Fongible (EV/$) | Δ |
|---|---|---|---|
| 1000$ | 5 842 728$ / 1,67% / 20,67% | 5 842 452$ / 1,67% / 20,67% | **-276$ (bruit)** |
| 3000$ | 5 915 842$ / 0,67% / 20,33% | 5 915 842$ / 0,67% / 20,33% | **0$ (IDENTIQUE)** |

**Verdict INCHANGÉ : REJETÉ.** L'hypothèse du goulot d'étranglement
commun (l'ancien cap Blueberry aurait masqué le gain de fongibilité) est
**RÉFUTÉE** — sous cap corrigé, l'écart reste nul/bruit, exactement comme
sous l'ancien cap (§2.8, rejeté 2026-08-10). Cohérent avec (b) ci-dessus :
la réserve n'est pas un jeu à somme nulle sur cette flotte, donc la
redistribuer par priorité EV/$ ne change presque rien — ni avant ni
après la correction du cap Blueberry. Pas de reconfirmation n=600
nécessaire (écart nul, pas juste petit).

## 3. Confirmation piste A' (BBx2) sous cap corrigé — n=600+cascade, 3000$

| Config | Profit | Ruine | Année1<0 (pré/post) | casse≤30j |
|---|---|---|---|---|
| solo_BB | 5 707 481$ | 0,50% | 21,17% (9,33/11,83) | 23,38% |
| **BBx2** | **5 953 550$** | **0,33%** | **17,33% (5,33/12,00)** | 23,36% |

**CONFIRMÉ n=600+cascade GO — écart RENFORCÉ vs l'ancien cap.** BBx2
domine solo_BB sur les 3 axes : profit **+4,31%** (vs +0,98% sous
l'ancien cap au n=600 déjà confirmé), ruine meilleure (0,33% vs 0,50%),
année1<0 -3,84pt. Cascade check propre. Cohérent avec la logique de
l'Étape V : BBx2 a 2 starters Blueberry au lieu d'1, donc bénéficie
davantage du déplafonnement que solo_BB.

## Conclusion générale

Le gain +16,4% n'est ni un artefact ni un trompe-l'œil au sens où le
craignait l'hypothèse initiale (Blueberry mal classé en EV/$) : c'est un
gain de VOLUME quasi pur, avec un coût de détournement négligeable
(<0,15% par firm affectée, pas de perte de comptes). Les deux retests
demandés (piste B, piste A') sont maintenant complets et cohérents avec
ce diagnostic : piste B reste rejetée (réserve non-scarce, comme avant),
piste A' reste confirmée et même renforcée à 3000$.

**Recommandation** : rien dans ce diagnostic ne s'oppose à l'adoption du
chiffre corrigé comme nouvelle référence officielle — mais l'adoption
formelle reste, comme convenu, une décision utilisateur (registre §4#11).
