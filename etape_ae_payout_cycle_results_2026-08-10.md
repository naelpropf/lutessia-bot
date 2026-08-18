# Étape AE (08/10 nuit, suite 13) — Cycle de payout réaliste (Blueberry/GFT/Fivers) : résultats

Suite au contact support confirmant que Blueberry, GFT et The5%ers ne
préservent PAS le profit non versé à la casse (contrairement à FTMO et
FundedNext, confirmés préservés), implémentation d'un cycle de payout
réaliste (14 jours, par compte) : les GAINS s'accumulent dans
`pending_payout` (en attente) au lieu d'être crédités instantanément ;
tous les 14 jours ce montant est "versé" (transféré dans le profit
réel) ; sur une CASSE avant le prochain versement, `pending_payout` est
perdu. Les PERTES continuent de frapper immédiatement (jamais protégées
par le cycle). FTMO/FundedNext restent inchangés (crédit instantané,
comme avant — comportement déjà correct pour ces deux firms).

`etape_ad_payout_cycle_2026-08-10.py` (moteur), `etape_ae_payout_cycle_
ablations_2026-08-10.py` (driver, 4 configs), n=300 screening puis
n=600 confirmation, 2 plafonds.

## 1. Chiffre corrigé — n=600

| Config | Plafond 1000$ | Plafond 3000$ |
|---|---|---|
| Référence actuelle (sans cycle payout) | 5 736 759$ / 1,00% / 21,83% | 5 751 134$ / 0,50% / 21,83% |
| **Avec cycle de payout (candidat corrigé)** | **5 510 750$ / 1,33% / 27,67%** | **5 539 307$ / 0,33% / 27,50%** |
| Écart | **-226 009$ (-3,94%)** | **-211 827$ (-3,68%)** |

Ruine quasi inchangée (dans le bruit). **Année1<0 se dégrade nettement
(+5,84pt/+5,67pt)** — le cycle de payout frappe surtout les jeunes
comptes (davantage de casses tôt dans leur vie, avant d'avoir eu le
temps d'accumuler un coussin de profit déjà versé).

## 2. Décomposition par firm (montant moyen perdu par run, n=600, 1000$)

| Firm | Pré-déblocage | Post-déblocage | Total | % du total forfaité |
|---|---|---|---|---|
| **Fivers** | 69$ | 56 208$ | 56 277$ | **42,2%** |
| **Blueberry** | 439$ | 53 204$ | 53 643$ | **40,2%** |
| **GFT** | 0$ | 23 561$ | 23 561$ | **17,7%** |
| **TOTAL** | 508$ | 132 973$ | **133 481$** | 100% |

**Le pré-déblocage ne représente que 0,4% du total perdu** — cohérent
avec le volume de casses déjà quantifié (§2.24 : ~4,4 casses pré vs
~134 post). Le vrai coût du cycle de payout est presque entièrement
POST-déblocage (fréquence de casse × volume de comptes, pas fragilité
initiale). Fivers et Blueberry pèsent chacun ~40% du total, GFT ~18%
(moins de comptes actifs, protégé en partie par Goat Guard).

## 3. Valeur réévaluée de GFT Goat Guard — confirmée LÉGÈREMENT plus précieuse

`corrige` vs `sans_gg` (n=600), isole la valeur de Goat Guard sous le
cycle de payout :

| Plafond | Avec Goat Guard | Sans Goat Guard | Valeur Goat Guard |
|---|---|---|---|
| 1000$ | 5 510 750$ | 5 441 572$ | **+69 178$ (+1,27%)** |
| 3000$ | 5 539 307$ | 5 469 801$ | **+69 506$ (+1,27%)** |

Goat Guard réduit la casse GFT forfaitée d'environ moitié (49 955$→
23 561$ à 1000$, -26 394$). **Verdict : l'hypothèse se confirme
directionnellement mais modestement** — ancienne valeur mesurée (sans
cycle payout) : +1,04% (Goat Guard seul) à +1,21% (combiné avec FTMO
-10%). Nouvelle valeur : +1,27% aux deux plafonds — une hausse réelle
mais faible (+0,06 à +0,23pt), pas une révision majeure. Goat Guard
protégeait déjà surtout contre le coût de restart structurel ; la
protection contre le forfait de payout est un bonus réel mais
secondaire, pas le levier principal.

## 4. Calibrage de V2 — confirmé BIEN calibré, pas de correction nécessaire

`corrige` vs `sans_v2` (n=600), isole la valeur de V2 sous le cycle de
payout :

| Plafond | Avec V2 | Sans V2 | Valeur V2 |
|---|---|---|---|
| 1000$ | 5 510 750$ | 5 444 645$ | **+66 105$ (+1,21%)** |
| 3000$ | 5 539 307$ | 5 545 951$ | **-6 644$ (-0,12%, bruit)** |

**Verdict : l'hypothèse d'un mauvais calibrage n'est PAS confirmée — au
contraire, V2 est LÉGÈREMENT plus utile qu'avant, pas moins.** Ancienne
valeur (sans cycle payout, registre §2.9) : +0,93% à 1000$, ~0% à
3000$. Nouvelle valeur : +1,21% à 1000$ (hausse de +0,28pt), toujours
~0% à 3000$ (inchangé). Écran de dépistage n=300 avait suggéré un doublement
(+1,86%) — **non confirmé à n=600** (retombe à +1,21%, bon exemple de
bruit n=300 corrigé par la reconfirmation).

**Explication** : bien que V2 raisonne sur `cumulative_since_reset`
(solde brut) et non sur `pending_payout` spécifiquement, une casse
évitée pendant la fenêtre de risque DD évite maintenant DEUX coûts
cumulés (coût de restart existant + forfait de payout nouveau) au lieu
d'un seul — la protection reste utile même sans cibler précisément la
bonne variable, parce que réduire la fréquence de casse près du seuil
DD réduit mécaniquement les deux risques à la fois. Un ciblage plus
précis (sur `pending_payout` directement) pourrait théoriquement faire
mieux, mais ce n'est pas urgent : V2 fonctionne déjà, pas de correction
nécessaire.

## Conclusion

**Chiffre candidat corrigé (cycle de payout activé) : 5 510 750$/1,33%/
27,67% à 1000$ (5 539 307$/0,33%/27,50% à 3000$)** — remplace le
5 736 759$/1,00%/21,83% actuellement affiché en référence officielle
SI cette correction est adoptée. Baisse modérée en profit (-3,7 à
-3,9%) mais dégradation notable d'année1<0 (+5,7 à +5,8pt) — impact
réel, pas négligeable, mais pas de l'ampleur du gain Blueberry (+16%).
GFT Goat Guard et V2 restent tous deux valides sous la correction (l'un
légèrement renforcé, l'autre stable) — aucun des deux leviers déjà
adoptés n'est remis en cause. **Pas encore adopté dans le registre
§1.8** — décision d'adoption laissée à l'utilisateur, comme pour la
correction Blueberry avant son feu vert explicite.
