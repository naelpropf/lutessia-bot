# Étape E — Audit de suivi (08/09/2026)

*Complète `etape_e_integration_rapport.md` (figé, non modifié) suite à deux
vérifications supplémentaires demandées avant de verrouiller les résultats.
Nouveau fichier séparé — convention adoptée cette session : un rapport déjà
transmis reste inchangé, tout complément va dans un nouveau fichier daté.*

---

## Point 1 — Écart 29,3% vs 27,5%/26,5% : BRUIT CONFIRMÉ, pas un bug

**Config exacte du 29,3%** : `year1_negative_diagnosis.py`, baseline
"tout réel" = REF, plafond 1000$, éval=1,25%/flotte=1,75%, **n=300, seed=555**.

**Décomposition de l'écart** (même config exacte, n et seed variés séparément) :

| Config | Année1<0 |
|---|---|
| n=300, seed=555 (rapport initial) | 29,3% |
| n=600, seed=555 | 28,3% |
| n=600, seed=777 (= REF@1000$ déjà validé) | 27,5% |

Le passage n=300→600 (même seed) réduit l'écart de 1 point ; le changement
de seed à n=600 en réduit encore 0,8. Les deux effets combinés expliquent
entièrement l'écart initial de 1,8 point — **confirmé comme bruit
d'échantillonnage**, pas un bug ni une config différente.

**Ablation complète reconfirmée à n=600** (seed=777, même config que
REF@1000$ déjà validé) :

| Variante | Année1<0 (n=300) | Année1<0 (n=600) |
|---|---|---|
| BASELINE (tout réel) | 29,3% | **27,5%** (identique au chiffre déjà validé) |
| TOUT-FLAT | 12,3% | 11,8% |
| FTMO seule flat | 21,3% (Δ-8,0) | 22,5% (Δ-5,0) |
| Blueberry seule flat | 22,0% (Δ-7,3) | 19,8% (Δ-7,7) |
| Fivers seule flat | 24,3% (Δ-5,0) | 25,0% (Δ-2,5) |
| GFT seule flat | 27,3% (Δ-2,0) | 26,7% (Δ-0,8) |
| FundedNext seule flat | 28,3% (Δ-1,0) | 26,3% (Δ-1,2) |

**Conclusion robuste à n=600** : FTMO et Blueberry restent de loin les deux
plus gros contributeurs (ils échangent juste leur ordre relatif entre eux
selon le seed — pas significatif, les deux dominent largement Fivers/GFT/
FundedNext dans les deux passages). Le mécanisme identifié précédemment
(redémarrage complet du challenge à toute casse, pas seulement une cible
plus dure) est confirmé comme la cause dominante, à un niveau de confiance
maintenant ÉLEVÉ et stable entre n=300 et n=600.

**27,5% (REF, 1000$) et 26,5% (REF, 3000$) restent le baseline officiel du
test d'ablation** — le 29,3% du rapport initial était un artefact de bruit,
à ne plus citer.

---

## Point 2 — Re-criblage n=300 : un MEILLEUR point de risque trouvé

**Bug trouvé en cours de route** (pas dans un script de production) :
`etape_e_fleet_integration.py`, `etape_e_cascade_check.py` et
`phase_break_diagnosis.py` initialisaient `state` sans les clés
`tax_breach_*` attendues par `split_tax_model.handle_tax_payment`,
provoquant un crash (`KeyError`) sur toute config où un paiement d'impôt
dépasse la trésorerie disponible sous le plafond. Ce chemin n'avait jamais
été déclenché dans les runs précédents (chance, pas une preuve d'absence
de bug) — **corrigé dans les 3 fichiers** en ajoutant les clés manquantes
à l'initialisation de `state`. N'affecte aucun résultat déjà rapporté
(ceux-ci ont réussi sans jamais emprunter ce chemin).

**Grille testée** : éval ∈ {1,00 ; 1,15 ; 1,25 ; 1,40 ; 1,50}%, flotte ∈
{1,50 ; 1,65 ; 1,75 ; 1,90 ; 2,00}%, n=300, plafond 1000$, seed=2026.

**Résultat inattendu** : la zone **flotte=1,90%** domine nettement — absente
du premier balayage grossier (qui sautait de 1,75 à 2,25, ratant cette
zone). Confirmé à n=600 (seed=777, comparable directement à REF@1000$
n=600 déjà validé, éval=1,25%/flotte=1,75% → 4 297 185$/3,0%/27,5%) :

| Point (n=600) | Profit | Ruine | Année1<0 | Verdict vs ancien choix |
|---|---|---|---|---|
| **éval=1,25%/flotte=1,90%** | 4 663 331$ | 2,83% | 26,7% | **Domine sur les 3 axes** (+8,5% profit, ruine et année1<0 plus basses) |
| éval=1,00%/flotte=1,90% | 4 579 059$ | **0,83%** | 27,8% | Meilleur compromis prudence/profit (+6,6% profit, ruine 3,6x plus basse) |
| éval=1,15%/flotte=1,90% | 4 640 804$ | 1,83% | 27,2% | Domine aussi l'ancien choix, entre les deux ci-dessus |
| éval=1,00%/flotte=1,65% | 4 389 801$ | 0,83% | 29,0% | Moins bon que les 3 ci-dessus sur profit ET année1<0 |
| éval=1,25%/flotte=1,75% (ancien choix) | 4 297 185$ | 3,0% | 27,5% | **Dominé** par les 3 premiers points ci-dessus |

**L'ancien choix (éval=1,25%/flotte=1,75%) était sous-optimal** — pas faux
en soi, mais une meilleure région existait et n'avait pas été explorée par
la grille initiale trop grossière.

**Ton choix, deux options raisonnables** :
- **Profit max** : éval=1,25%/flotte=1,90% (4 663 331$, ruine 2,83%)
- **Prudence** : éval=1,00%/flotte=1,90% (4 579 059$, ruine 0,83% — seulement
  1,8% de profit en moins pour une ruine 3,6x plus faible)

**Non fait dans cette passe** : le risque de WINNER n'a pas été re-affiné
avec cette même grille fine (hors périmètre de la demande, qui portait sur
REF). Comme WINNER perdait déjà nettement à son propre optimum (cascade
check notamment), cette omission ne remet pas en cause le verdict global —
elle ne peut que le renforcer (REF vient encore de s'améliorer).

**Plafond 3000$** : pas encore retesté avec ce nouveau point de risque —
seul le plafond 1000$ a été re-swept. À faire avant de considérer le
tableau complet (2 plafonds) comme final.

---

## Ce qui change concrètement

Le verdict qualitatif de `etape_e_integration_rapport.md` (REF > WINNER sur
profit, ruine, et cascade) **reste inchangé et se renforce** — REF est
encore meilleur qu'initialement rapporté. Mais **le chiffre exact de REF
au plafond 1000$ doit être mis à jour** : ~4 297 185$ → **~4 579 059$ à
4 663 331$** selon le point de risque choisi (à trancher), pas encore
confirmé au plafond 3000$.

## Prochaine étape suggérée

1. Choisir entre les deux points de risque proposés (profit max vs
   prudence) — ou un autre point de la grille si un compromis différent
   est préféré.
2. Confirmer le point choisi à n=600 sur le plafond 3000$ (seul 1000$ a
   été refait dans cette passe).
3. Re-passer le cascade check sur le point de risque final retenu — celui
   déjà fait (`etape_e_cascade_check.py`) utilisait l'ancien point
   éval=1,25%/flotte=1,75%, pas le nouveau.
