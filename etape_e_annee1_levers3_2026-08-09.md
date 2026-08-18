# Étape E — Recherche de leviers annee1<0, round 3 : exposition simultanée + recherche reset (08/09/2026)

*Suite de `etape_e_annee1_levers_2026-08-09.md` et `etape_e_annee1_levers2_
2026-08-09.md` (6 leviers déjà épuisés sur 3 familles : risque/seuil/
calendrier, coût de réouverture — aucun gain net). Cette session teste la
4e famille (volume d'exposition simultanée) + une recherche officielle sur
les mécanismes de reset moins cher par firm. Script :
`etape_e_annee1_levers3_2026-08-09.py`. Config de base : REF,
éval=1,00%/flotte=1,90%/GFT=1,75%, seuils actuels, plafond 1000$, n=300.*

**Conclusion en une phrase : aucun des deux points ne domine la config
actuelle — le point 2 est un arbitrage réel mais nettement défavorable
(coût disproportionné par rapport au gain), le point 3 n'a quasiment
aucun effet (la contrainte ne se déclenche presque jamais). Aucun
changement de config, aucune confirmation n=600 déclenchée.**

---

## Point 1 — Recherche officielle : reset/retry moins cher par firm

Recherche web ciblée (help centers officiels + recherche générale),
sourcée firm par firm.

| Firm | Mécanisme trouvé | S'applique à un compte DÉJÀ FINANCÉ qui casse ? | Confiance |
|---|---|---|---|
| **FTMO** | -10% sur le rachat si effectué dans les 24h suivant la casse | Oui (toute casse, éval ou financé) — repart quand même de P1, juste 10% moins cher | Élevée (plusieurs sources, cohérentes) |
| **The5%ers** | Aucun mécanisme de reset ("The5%ers ne propose pas de reset actuellement") | N/A — confirmé absent | Élevée |
| **Blueberry** | Reset à 2× le prix du challenge ORIGINAL (pas 2× la taille financée), reprend DIRECTEMENT au niveau financé — aucune phase à rejouer | **Oui, spécifiquement pour ce cas** — mais **une seule fois par compte** (à vie), et exclu pour les comptes instant funding et les comptes "scaled" (probablement les comptes supplémentaires) | Moyenne — page officielle bloquée en fetch direct (HTTP 403), information recoupée via extraits de recherche indexés, pas vérifiée en primaire |
| **GFT** | "Goat Guard" — pas un reset, un coupe-circuit : ferme les positions à -2% de perte flottante sur un compte financé, transformant une 1ère casse potentielle en "soft breach" (split réduit à 50% au lieu d'une fermeture) ; la 2e devient une vraie casse. Exclut les comptes instant funding | Catégorie différente (réduit la FRÉQUENCE des casses plutôt que leur coût) | Moyenne (page officielle récupérée directement) |
| **FundedNext** | Reset ~10% moins cher, mais **explicitement limité à la phase éval/challenge** — "une fois le compte financé acquis, l'option de reset n'est plus disponible" | **Non** — confirme que le modèle actuel (restart plein tarif post-financement) est déjà correct pour cette firm | Élevée |

**Seul le mécanisme Blueberry (reset 2× prix original, saute l'éval)
traite directement le coût du restart post-déblocage** identifié comme
piste ouverte par les rapports précédents — mais avec deux contraintes
fortes (usage unique à vie, exclusion instant/scaled) qui en limitent
fortement la portée sur un compte qui casse plusieurs fois dans la
simulation (48 mois). **Non implémenté dans cette session** (hors scope :
recherche + quantification demandées, pas nouveau code) — piste candidate
pour une session dédiée si retenue.

---

## Point 2 — Plafond dur sur les comptes supplémentaires

Réduit le nombre max de comptes SUPPLÉMENTAIRES simultanés par firm
(FTMO/GFT — Blueberry a déjà un plafond réel de 3 comptes totaux, non
modifié ici) en dessous du niveau actuel (limité seulement par le plafond
de capital réel).

| Config | Profit | Ruine | Année1<0 (pré/post) | N extra moy. | Casses post-déblocage | Casse≤30j | Casse≤60j |
|---|---|---|---|---|---|---|---|
| Baseline (non plafonné) | 4 676 954$ | 1,67% | 31,33% (17,33%/14,00%) | 7,87 | 53,1 | 21,07% | 39,06% |
| Cap=4 extra/firm | 4 676 954$ (identique) | 1,67% | identique | 7,87 | 53,1 | identique | identique |
| Cap=2 extra/firm | 4 046 856$ (**-13,5%**) | 1,67% | 31,00% (17,33%/13,67%) | 5,90 | 46,8 (-11,9%) | 20,54% | 38,11% |
| Cap=1 extra/firm | 3 263 014$ (**-30,2%**) | 1,67% | 30,00% (17,33%/**12,67%**) | 2,95 | 37,4 (-29,6%) | 20,21% | 37,46% |

**Cap=4 n'a aucun effet** : la limite naturelle de capital (FTMO/GFT
plafonnent déjà à ~3 comptes supplémentaires chacun avant cap=4) est plus
stricte que le plafond testé — confirme que le plafond de capital réel
par firm était déjà le facteur limitant, pas un choix de modélisation
laxiste.

**Cap=2 et cap=1 montrent un vrai arbitrage, mais nettement défavorable** :
à cap=1, la part POST-déblocage de l'année1<0 baisse réellement (14,00%→
12,67%, -1,33pt, ~9,5% relatif — pas du bruit, cohérent avec la baisse de
-29,6% des casses post-déblocage), mais le **coût en profit est de -30,2%**
pour ce gain, et **la ruine ne bouge pas du tout** (1,67% partout). Le
ratio gain-risque/coût-profit est très défavorable — bien pire qu'un
arbitrage proportionnel "moins de comptes = moins de risque ET moins de
profit à parts égales" : ici on perd ~23x plus de profit (en points de %)
que ce qu'on gagne en réduction de risque post-déblocage. **Aucune
domination** — pas un point à adopter, mais bien un arbitrage réel et
clairement défavorable, pas un déplacement neutre.

---

## Point 3 — Cadencement continu des ouvertures de comptes supplémentaires

Délai minimum entre deux ouvertures successives d'un compte supplémentaire
pour une même firm, appliqué en continu sur toute la simulation
(contrairement à l'étalement déjà testé, qui ne portait que sur le
déblocage initial ponctuel).

| Config | Profit | Ruine | Année1<0 (pré/post) | N extra moy. | Casse≤30j | Casse≤60j |
|---|---|---|---|---|---|---|
| Baseline (gap=0) | 4 676 954$ | 1,67% | 31,33% (17,33%/14,00%) | 7,87 | 21,07% | 39,06% |
| Gap=1 semaine | 4 659 995$ (-0,36%) | 1,67% | 31,33% (identique) | 7,87 | 20,88% | 38,93% |
| Gap=2 semaines | 4 646 308$ (-0,66%) | 1,67% | 31,00% (17,33%/13,67%) | 7,87 | 20,90% | 38,95% |
| Gap=3 semaines | 4 631 383$ (-0,97%) | 1,67% | 31,00% (17,33%/13,67%) | 7,87 | 20,96% | 38,99% |

**Le nombre moyen de comptes supplémentaires ouverts (n_extra_moy) est
IDENTIQUE (7,87) sur toutes les valeurs de gap testées (0 à 3 semaines)** —
preuve directe que la contrainte ne se déclenche presque jamais : le
rythme naturel d'accumulation de réserve entre deux ouvertures successives
est déjà, la plupart du temps, plus lent que 1-3 semaines. Les petites
baisses de profit (-0,36% à -0,97%) et de casse≤30j/60j viennent des rares
cas où la contrainte mord réellement, pas d'un effet structurel. **Aucun
gain net, aucun coût réel non plus — un levier essentiellement inerte à
ces valeurs de gap.**

---

## Conclusion générale

**Ni le point 2 ni le point 3 ne montrent de domination** (meilleur ratio
profit/risque que la config actuelle) :
- Point 2 est un arbitrage RÉEL mais très défavorable (perte de profit
  ~23x supérieure au gain de risque post-déblocage, ruine inchangée) —
  moins bon qu'un simple compromis proportionnel.
- Point 3 est quasi inerte — la contrainte testée (1-3 semaines) ne mord
  presque jamais compte tenu du rythme naturel d'accumulation de réserve.

**Aucune confirmation n=600, aucun changement de config appliqué.**

**Bilan cumulé sur 3 sessions : 8 leviers distincts testés** (seuil FTMO,
étalement calendaire ponctuel, rampe classique, rampe ciblée, redémarrage
asymétrique, risque dégressif, plafond comptes supplémentaires,
cadencement continu), **aucun n'a produit de gain net dominant**. Le seul
signal cohérent sur 3 sessions : réduire le NOMBRE de comptes financés
simultanés réduit bien le volume de casses post-déblocage (confirmé
maintenant 2 fois : ici via le plafond, et indirectement via le
redémarrage asymétrique qui l'avait AGGRAVÉ en accélérant le cycle) — mais
le coût en profit de cette réduction est structurellement disproportionné
avec les leviers testés jusqu'ici, car ils réduisent la flotte de façon
uniforme plutôt que de cibler spécifiquement le coût du restart.

**Piste la plus prometteuse restante (non testée)** : le mécanisme réel
Blueberry (reset 2× prix original, saute l'éval, identifié au point 1) est
le seul mécanisme trouvé qui réduit le coût du restart SANS réduire le
volume de comptes actifs — mais implique un changement structurel du
moteur (usage unique par compte, exclusions) plutôt qu'un simple paramètre,
et n'a pas été testé ici (hors scope de cette session).
