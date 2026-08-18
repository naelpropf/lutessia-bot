# Chantier 2 — Format adaptatif par seuil de réserve : rejeté (08/09/2026)

*Suite du scoping (voir échanges 08/09) qui avait identifié 2 problèmes
structurels à intégrer à la conception : Fivers exclu (manque à gagner
structurel sans compensation), seuil de bascule indépendant des seuils de
déblocage actuels (1k-25k, bien trop bas). Script :
`etape_e_adaptive_format_2026-08-09.py`. Config : REF, seuils déblocage
inchangés, éval=1,25%/flotte=1,90%/GFT=1,75%, n=300 (criblage, 24
cellules), format figé à la création du compte (jamais ré-évalué à la
réouverture).*

**Conclusion en une phrase : aucune des 24 configurations testées ne bat
le REF pur actuel (4 827 736$/4 892 588$) sur 2 axes sans dégrader le
3e — le signal trésorerie à 180 jours de l'Étape D ne survit pas
l'intégration du vrai mécanisme de croissance et des vraies contraintes
de capital, exactement le risque anticipé avant de lancer ce chantier.
Aucun changement de config, aucune confirmation n=600, aucun cascade
check (pas de gain net à confirmer).**

---

## Implémentation

- Fivers : toujours format REF (Fivers_HighStakes, 100k$/compte),
  jamais adaptatif — conforme au problème structurel #1 identifié au
  scoping.
- FTMO/GFT/FundedNext : basculent en formats CONFIG_WINNER (rapide) avant
  le seuil de réserve fleet-wide, REF (lent) après. Palier inchangé par
  format pour ces 3 firms (confirmé au scoping : `BASE_PALIER`/
  `FUNDEDNEXT_PALIER` sont des constantes firm-level, pas format-level).
- Blueberry : 2 variantes testées séparément (`blueberry_adaptive`
  True/False) — problème structurel #3 du scoping (arbitrage rapide vs
  reset).
- Seuil de bascule : paramètre indépendant, balayé à 10k/20k/30k/50k/
  75k/100k$ (pas hérité des seuils de déblocage 1k-25k, problème
  structurel #2 du scoping).
- Format figé à la première ouverture réelle du compte (activation du
  groupe ou création d'un compte supplémentaire), jamais ré-évalué à une
  réouverture après casse — le compte réutilise son propre format fixé,
  pour toute sa vie.

**Bug trouvé et corrigé pendant le smoke test** : quand Blueberry démarre
en format instant (0 phase, `blueberry_adaptive=True`), il n'existait pas
de détection de "déjà financé dès la création" équivalente à celle
d'`etape_e_fleet_integration.py` — sans cette correction, le compteur de
déblocage de flotte ne s'incrémentait jamais et AUCUNE autre firm ne
s'ouvrait, quel que soit le seuil (profit ~100k$ au lieu de ~4-5M$,
détecté immédiatement car les résultats étaient identiques sur toute la
grille de seuils). Corrigé avant tout lancement à n=300.

---

## Résultats (n=300, 12 configs × 2 plafonds)

### Blueberry adaptatif (`blueberry_adaptive=True`) — rejeté, ruine disqualifiante

| Seuil | Profit 1000$/3000$ | Ruine 1000$/3000$ | Année1<0 1000$/3000$ |
|---|---|---|---|
| 10-20k$ | 4,31M$/5,01M$ | **14,00%**/0,33% | 23,67%/12,33% |
| 30k$ | 4,22M$/4,91M$ | 14,00%/0,33% | 23,00%/11,33% |
| 50-100k$ | 4,13-4,14M$/4,80-4,81M$ | 14,00%/0,33% | 21,67-22,33%/10,00-10,67% |

**La ruine à 1000$ reste bloquée à 14,00% quel que soit le seuil** — cause
structurelle, pas un artefact de seuil : Blueberry Instant Elite démarre
déjà "financé" au jour 0, donc trade au **risque flotte (1,90%) dès le
premier trade**, sans jamais bénéficier du risque éval plus prudent
(1,25%) qui protège normalement la phase de démarrage sous REF. Avec
~200$ de marge au plafond 1000$ (coût Instant Elite 800$), une série de
pertes précoces à ce risque plus élevé épuise vite le coussin de cash.

Les chiffres à 3000$ seuls sont attractifs (profit jusqu'à +2,4% vs REF
pur, année1<0 jusqu'à -8pt) mais **non exploitables** : le point de
risque est un choix de stratégie unique évalué aux deux plafonds, pas un
choix par plafond — la même config est un désastre à 1000$.

### Blueberry exclu (`blueberry_adaptive=False`, comme Fivers)

| Seuil | Profit 1000$/3000$ (vs REF pur) | Ruine 1000$/3000$ | Année1<0 1000$/3000$ |
|---|---|---|---|
| 10-20k$ | 4,69M$/4,75M$ (**-2,75%/-3,0%**) | 1,00%/0,00% | 20,67%/19,33% |
| 30k$ | 4,58M$/4,63M$ (-5,1%/-5,4%) | 1,00%/0,00% | 19,33%/18,00% |
| 50k$ | 4,46M$/4,51M$ (-7,6%/-7,8%) | 1,00%/0,00% | 18,67%/17,67% |
| 75-100k$ | 4,43-4,44M$/4,48-4,48M$ (-8,1%/-8,5%) | 1,00%/0,00% | 18,33%/17,33% |

Ruine et année1<0 s'améliorent légèrement à mesure que le seuil monte
(plus de comptes restent en format lent/protégé plus longtemps), mais le
**profit perd systématiquement face à REF pur, de -2,75% (meilleur cas)
à -8,5%** — jamais assez compensé pour satisfaire le critère "2 axes sans
dégrader le 3e" demandé.

---

## Pourquoi ça ne marche pas : le format rapide n'est pas gratuit dans le vrai moteur

Le criblage simplifié de l'Étape D (sans mécanisme de croissance, sans
contrainte de capital réelle) avait suggéré un avantage des formats
rapides. Ce chantier confirme, sur un axe supplémentaire jamais testé
avant (bascule temporelle plutôt que format fixe), la même conclusion que
l'intégration complète de l'Étape E : le format rapide déplace le
problème plutôt que de le résoudre — soit en sautant l'éval protectrice
pour trader plus tôt au risque flotte plus élevé (cas Blueberry), soit en
échangeant un démarrage plus rapide contre un profit structurellement
plus bas sur toute la durée où le format rapide reste actif (cas
FTMO/GFT/FundedNext, palier identique mais dynamique de progression
différente).

---

## Conclusion

**Chantier 2 fermé, aucun levier retenu.** Le chiffre de référence du
projet reste celui du Chantier 1 : **4 827 736$/4 892 588$** (REF pur,
éval=1,25%/flotte=1,90%, reset Blueberry actif), confirmé n=600 + cascade
GO le 08/09.
