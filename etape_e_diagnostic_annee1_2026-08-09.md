# Étape E — Diagnostic année1<0 (08/09/2026)

*Diagnostic uniquement, aucune config changée. Complète les fichiers
Étape E précédents (tous figés). Config de référence : REF, éval=1,00%/
flotte=1,90%, seuils actuels (FTMO=1k/Fivers=15k/GFT=25k/FundedNext=25k),
plafond 1000$, n=600 pour les points 1 et 3, n=300 pour le point 2
(conclusion négative, pas de changement retenu donc pas de confirmation
n=600 jugée nécessaire).*

---

## Point 1 — Décomposition pré/post-déblocage : le mécanisme a changé de nature

**Méthode** : parmi les runs année1<0 (167/600, 27,8%), classement
"pré-déblocage" si la flotte complète n'était pas encore active au mois 12
(`full_structure_month is None or > 12`), sinon "post-déblocage" — même
critère que la catégorisation A/B du 08/08.

| | Sous l'ancien moteur (08/08) | Sous le nouveau moteur (08/09) |
|---|---|---|
| Pré-déblocage | 92-100% | **56,9%** (95/167) |
| Post-déblocage | 0-8% | **43,1%** (72/167) |

**Le mécanisme n'est plus dominé à 92-100% par le grinding pré-déblocage
— c'est maintenant un partage 57/43.** Le pré-déblocage reste majoritaire
mais le post-déblocage est passé d'un phénomène marginal à une part
substantielle. Explication cohérente avec la découverte structurelle
principale de la session (restart complet P1+P2 à toute casse) : sous
l'ancien moteur, un compte déjà financé qui cassait rachetait un challenge
unique bon marché et repartait vite ; sous le nouveau moteur, ce même
compte doit rejouer les deux phases complètes avant de re-générer du
profit, ce qui peut faire basculer une trajectoire déjà débloquée en
année1<0 — un mode de dégradation qui n'existait quasiment pas avant.

**Implication directe** : contrairement à l'hypothèse de cadrage ("si
c'est toujours majoritairement pré-déblocage, le vrai problème est la
survie du tout premier compte Blueberry"), **le problème n'est plus
seulement celui de Blueberry seule** — près de la moitié des cas
viennent maintenant de casses en phase financée n'importe où dans la
flotte déjà débloquée. Un levier de mitigation centré uniquement sur
l'amorçage Blueberry (ex. augmenter le capital protégé initial) ne
traiterait donc qu'environ 57% du problème, pas sa totalité.

---

## Point 2 — Bug rampe post-financement : le rapport coût/bénéfice s'est inversé

**Rappel du bug** : `RAMP_RISK=2,0%` pour les `RAMP_N=5` premiers trades
après financement, mais `trades_taken` ne se réinitialise jamais (ni à la
réouverture, ni à la transition éval→financé) — la rampe protectrice ne
s'applique donc qu'une seule fois dans la vie du compte, pas à chaque
refinancement. Sous l'ancien moteur : ~1pt de gain ruine/année1<0 pour
5-6% de coût en profit, jugé non rentable.

**Sous le nouveau moteur, le moteur intégré actuel (`etape_e_fleet_
integration.py`) n'a AUCUNE rampe du tout** — pas même la version
"buguée" une-fois-dans-la-vie de l'ancien moteur. Testé une variante avec
la rampe réintroduite et correctement réinitialisée à chaque
(re)financement (compteur séparé `_ramp_trades`, reset à chaque passage
challenge→financé, y compris les réouvertures après casse) :

| Variante (n=300) | Profit | Ruine | Année1<0 |
|---|---|---|---|
| Baseline (aucune rampe) | 4 381 617$ | 1,0% | 30,0% |
| Rampe corrigée | 4 307 596$ (**-1,7%**) | 1,0% | **31,7%** (+1,7pt, pire) |

**Résultat inversé par rapport à l'ancien moteur : réintroduire la rampe
est maintenant net négatif sur profit ET année1<0**, pas juste "pas
rentable" — carrément contre-productif. Explication probable (non testée
plus loin, hors périmètre de cette demande) : `RAMP_RISK=2,0%` est une
constante héritée, calibrée comme protectrice quand le risque flotte
cible était 2,75% (ancien verrouillé). Le resweep du 08/09 a abaissé le
risque flotte à 1,90% — la même rampe à 2,0% est donc maintenant PLUS
risquée que le risque flotte courant, elle ajoute du risque au lieu d'en
retirer pendant les 5 premiers trades post-financement.

**Conclusion** : ne pas réintroduire ce mécanisme avec sa valeur actuelle.
Si le concept de rampe protectrice est reconsidéré, il faudrait d'abord
recalibrer `RAMP_RISK` en dessous de 1,90% (ex. tester 1,00-1,50%), pas
réutiliser 2,0% tel quel — piste non explorée ici, à traiter séparément
si jugée utile.

---

## Point 3 — Délai de rattrapage : légèrement plus long, mais pas de queue catastrophique

| | Ancien moteur (08/08) | Nouveau moteur (08/09) |
|---|---|---|
| Délai médian de rattrapage | 13-15 mois | **16 mois** (P25=14, P75=18) |
| Ne rattrapent jamais (horizon 48 mois) | non mesuré précisément | **1,2%** des runs année1<0 (0,33% de tous les runs) |

Le délai médian s'allonge légèrement (cohérent avec la pénalité de
restart complet), mais reste dans le même ordre de grandeur. La proportion
de trajectoires qui ne rattrapent JAMAIS sur l'horizon simulé reste très
faible (0,33% de tous les runs) — **pas une catégorie de risque caché
plus grave qu'une année1<0 classique**, juste une queue rare à noter.

---

## Synthèse pour la recherche d'un levier de mitigation

1. **Le problème est maintenant à moitié post-déblocage** — un levier
   centré uniquement sur l'amorçage/la survie de Blueberry seule (ex.
   augmenter `DEFAULT_EMERGENCY`) ne peut traiter qu'environ 57% des cas.
   Tout futur levier de mitigation candidat doit être évalué séparément
   sur les deux sous-catégories, pas seulement sur le total.
2. **La rampe post-financement (version corrigée) n'est PAS un levier
   utile en l'état** — testé et rejeté, net négatif.
3. **Le délai de rattrapage n'est pas le problème principal** — la quasi-
   totalité des trajectoires année1<0 finissent par redevenir positives
   dans un délai raisonnable (médiane 16 mois) ; la vraie question reste
   la fréquence (27,8%) plus que la gravité individuelle des cas.

**Aucun changement de config recommandé à ce stade** — ce diagnostic
confirme la nature du mécanisme mais n'a pas identifié de levier de
mitigation gagnant. Prochaine étape logique (non commencée) : chercher un
levier qui cible spécifiquement la composante post-déblocage (43% des cas)
plutôt que de re-tester des leviers déjà connus pour cibler uniquement la
composante pré-déblocage.
