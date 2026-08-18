# Chantier multi-format — synthèse globale (Étapes A à E, 08/08-08/09/2026)

*Document unique de référence pour tout le chantier. Les fichiers
individuels (`etape_a_*`, `etape_b/c/d`, `etape_e_*`) restent la source
détaillée si besoin de creuser un point précis, mais tout ce qui compte
pour comprendre où on en est est ici.*

---

## 1. Le problème de départ

Le moteur de simulation traitait chaque prop firm avec **une seule phase
générique** (8% de cible, 4 jours min, DD 10%), identique pour les 5
firms — une simplification jamais remise en question depuis la conception
initiale du projet. Objectif du chantier : remplacer ça par un moteur qui
simule les vraies conditions de chaque offre de compte, comparer les
formats (2-step / 1-step / instant funding) entre eux, et vérifier si un
autre choix de format bat la config actuelle une fois tout réintégré
proprement.

---

## 2. Étape A — Collecte de données (terminée)

5 agents de recherche en parallèle (un par firm), sources officielles
uniquement. Fichier : `etape_a_formats_comptes_propfirms_2026-08-08.md`.

**Découverte structurante** : le DD max est **statique** pour toute
évaluation (1/2/3-step) et **trailing** pour tout instant funding — pas de
lien avec le nombre de phases comme supposé au départ. Vérifié
explicitement sur les 5 firms, y compris le cas GFT 2-step vs 3-step
(les deux statiques, contrairement au doute initial).

**Copytrade** : les 5 formats du combo finalement testé en Étape D ont
été confirmés (4 par réponse directe du support, 1 par page officielle).

**Points ouverts non résolus** : ambiguïté Blueberry Prime vs 2-Step
standard (impact mesuré <1%, non bloquant) ; mécanisme de croissance
Hyper Growth simplifié (non pertinent, ce format a perdu à l'Étape D).

---

## 3. Étape B — Refonte du moteur (terminée)

Nouveau module `engine_multiformat.py`, state machine générique N-phases
avec DD statique/trailing/trailing-EOD. **Aucun script existant modifié**
— le chiffre verrouillé du projet reste reproductible via les anciens
scripts. ~18-21 FormatDef peuplés depuis l'Étape A. Validé par smoke test
(cohérence interne, pas de comparaison au chiffre verrouillé — pas censé
matcher, c'est le but).

---

## 4. Étape C — Comparaison solo par format (terminée)

21 formats testés en solo (1 compte, pas de flotte), n=300.

- 1-step finance ~2x plus vite que 2-step mais casse ~1,5x plus souvent
- Instant funding très hétérogène : Blueberry Instant Elite le plus
  stable, Instant Lite et GFT Instant PRO les plus fragiles
- Prix GFT recherchés séparément (confiance moyenne, sources tierces
  divergentes — seule donnée du projet sans source officielle directe)

---

## 5. Étape D — Criblage flotte simplifié (terminée, résultat invalidé par l'Étape E)

48 combinaisons testées, **flotte active jour 0, sans mécanisme de
croissance (comptes supplémentaires) ni fiscalité** — simplification
volontaire pour isoler l'effet du format seul.

**Résultat obtenu à l'époque** : un combo "rapide" (FTMO 1-Step + Fivers
Hyper Growth + Blueberry Instant Elite + GFT Instant GOAT + FundedNext
1-Step) gagnait partout sur profit et trésorerie à 180 jours.

**Réserve posée dès le départ** : sans mécanisme de croissance, le seul
levier de profit restant est "combien de cycles casse/réouverture tiennent
dans la fenêtre" — les formats rapides en font mécaniquement plus, sans
que ce soit une vraie supériorité économique. **Cette réserve s'est
confirmée fondée (voir Étape E).**

---

## 6. Étape E — Intégration dans le moteur complet (le gros du travail, 08/08→08/09)

### 6.1 Verdict principal : le combo "gagnant" de l'Étape D est rejeté

Réintégré le moteur multi-format dans la vraie mécanique de production
(déblocage échelonné + comptes supplémentaires + fiscalité réelle), n=600,
comparaison honnête REF (100% 2-step) vs WINNER (combo Étape D) :

| | Profit (1000$/3000$) | Ruine | Cascade |
|---|---|---|---|
| **REF** | 4 297 185$ / 4 388 789$ (chiffre provisoire initial) | 3,0% / 0,5% | GO |
| **WINNER** | 3 639 957$ / 4 302 618$ | 17,0% / 1,3% | **PAS GO** (casse ≤30j 60% vs 24%, jusqu'à 16% de runs quasi-gelés) |

**REF bat WINNER sur profit ET ruine ET cascade.** La réserve posée à
l'Étape D était fondée : l'avantage des formats rapides était un artefact
du criblage simplifié, pas une vraie supériorité.

**Deux bugs trouvés et corrigés en cours de route** (aucun dans un script
de production existant — tous dans les nouveaux scripts Étape E) :
- `process_trade_mf` ne respectait pas le plafond de cash réel injectable
- Les comptes instant funding (0 phase) ne déclenchaient jamais le
  compteur de déblocage échelonné → sous WINNER, une seule firm tournait
  en réalité, aucune autre ne se débloquait jamais

### 6.2 Audit de suivi — le point de risque initial était sous-optimal

Le premier resweep de risque était à n=100 (sous le plancher
méthodologique n=300 du projet). Re-fait à n=300 puis confirmé à n=600 :
la zone **flotte=1,90%** (jamais testée par la grille initiale, qui
sautait de 1,75 à 2,25) domine nettement l'ancien choix.

Bug bonus trouvé et corrigé pendant ce resweep : clés d'état manquantes
pour la gestion fiscale (`tax_breach_*`), causait un plantage sur
certaines configs de risque. Confirmé sans impact sur les chiffres déjà
produits (le bug ne peut que planter, jamais produire un résultat faux).

### 6.3 Verrouillage — deux points de risque candidats, tous deux GO au cascade check

n=600, deux plafonds, cascade check complet (pas supposé automatique après
la leçon WINNER) :

| Point de risque | Plafond | Profit | Ruine | Cascade |
|---|---|---|---|---|
| éval=1,25%/flotte=1,90% (profit max) | 1000$ | 4 663 331$ | 2,83% | GO |
| | 3000$ | 4 756 842$ | 0,50% | GO |
| **éval=1,00%/flotte=1,90% (recommandé)** | 1000$ | 4 579 059$ | 0,83% | **GO, meilleur profil cascade** |
| | 3000$ | 4 584 524$ | 0,67% | GO |

**Recommandé : éval=1,00%/flotte=1,90%** — casse ≤30j/≤60j nettement plus
basse (21,1%/38,6% vs 24,0%/42,9%) pour seulement -1,8% de profit vs le
point profit max.

### 6.4 Seuils de déblocage + risque GFT — re-vérifiés

- **FTMO, Fivers, GFT** (seuils) et **GFT** (risque éval réduit 1,75%) :
  tous confirmés robustes/quasi-optimaux sous le nouveau moteur, aucun
  changement justifié (écarts <0,5%, bruit).
- **FundedNext (seuil)** : vrai arbitrage trouvé, non tranché — abaisser
  25k→5k donne +2,1-2,3% de profit mais une ruine ~2x plus élevée (mais
  toujours ≤2% en absolu). Cascade GO dans les deux cas. **Pas de défaut
  choisi, décision de tolérance au risque laissée ouverte.**

### 6.5 Diagnostic année1<0 — pourquoi c'est passé de 5,5%/4% à ~27-31%

**Confirmé structurel, pas un bug** (test d'ablation empirique, reconfirmé
n=600) : le redémarrage complet du challenge (P1+P2) à CHAQUE casse — un
mécanisme que l'ancien moteur 1-phase ne pouvait pas représenter — est la
cause dominante. FTMO et Blueberry portent l'essentiel de l'effet.

**Décomposition du mécanisme** (nouveau ce 08/09) :
- 57% des cas année1<0 restent pré-déblocage (grinding Blueberry seule) —
  comme avant, mais BEAUCOUP moins dominant qu'avant (92-100% sous
  l'ancien moteur)
- **43% sont maintenant post-déblocage** (flotte complète active, mais un
  compte déjà financé casse et doit tout rejouer) — un mode de ruine
  quasi inexistant sous l'ancien moteur
- Délai médian de rattrapage : 16 mois (P25=14, P75=18), stable vs les
  13-15 mois d'avant
- Seulement 0,33% de tous les runs ne rattrapent jamais sur l'horizon
  simulé (48 mois) — pas une catégorie de risque cachée plus grave

**Levier testé et rejeté** : réintroduire la rampe de risque protectrice
post-financement (bug historique, jamais corrigé faute de rentabilité
sous l'ancien moteur) — testé à nouveau sous le nouveau moteur, résultat
**net négatif** (-1,7% profit, +1,7pt année1<0), pas juste "pas
rentable". Cause probable : la constante `RAMP_RISK=2,0%` était calibrée
contre l'ancien risque flotte (2,75%), maintenant obsolète face au
nouveau risque flotte plus bas (1,90%).

**Aucun levier de mitigation identifié à ce stade** — la piste ouverte
pour la suite est de chercher un levier qui cible spécifiquement la
composante post-déblocage (43% des cas), pas de recycler les leviers déjà
connus qui ne visaient que le pré-déblocage.

---

## 7. Où en est le chiffre de référence, concrètement

**Le combo gagnant de l'Étape D est définitivement écarté.** La question
qui reste est uniquement : quelle variante de REF (100% 2-step) adopter.

| Paramètre | Statut |
|---|---|
| Format par firm | 100% 2-step (config REF) — Blueberry Prime2Step par défaut, ambiguïté non tranchée mais impact <1% |
| Risque éval/flotte | **éval=1,00%/flotte=1,90% recommandé** (ou 1,25%/1,90% si profit max préféré) |
| Seuils déblocage FTMO/Fivers/GFT | Inchangés (1k/15k/25k), confirmés robustes |
| Seuil déblocage FundedNext | **Non tranché** : 25k (prudent) ou 5k (+2% profit, ruine ~2x) |
| GFT risque éval réduit | Inchangé (1,75%), confirmé quasi-optimal |

**Chiffre REF actuel selon les choix** (n=600, tous confirmés) :

| Risque | Seuil FN | Plafond 1000$ | Plafond 3000$ |
|---|---|---|---|
| éval=1,00/flotte=1,90 | 25k (prudent) | 4 579 059$ | 4 584 524$ |
| éval=1,00/flotte=1,90 | 5k (profit+) | 4 673 628$ | 4 691 764$ |
| éval=1,25/flotte=1,90 | 25k | 4 663 331$ | 4 756 842$ |

**Ce chiffre ne remplace toujours PAS le chiffre verrouillé officiel du
projet** (5 794 566$/5 898 897$, ancien moteur 1-phase) — c'est une
décision séparée et explicite à prendre, pas automatique (moteur
différent, risque recalibré différemment, et le taux année1<0 a
mécaniquement augmenté par la correction d'un vrai angle mort de l'ancien
modèle, pas par une dégradation réelle du projet).

---

## 8. Décisions qui t'appartiennent, en attente

1. **Seuil FundedNext** : 25k (prudent) ou 5k (+2% profit, ruine ~2x) ?
2. **Point de risque** : éval=1,00% (recommandé, meilleure cascade) ou
   1,25% (profit max) ?
3. **Basculer REF comme nouvelle référence officielle du projet**, ou
   garder l'ancien chiffre verrouillé en attendant d'autres vérifications ?
4. **Chercher un levier de mitigation pour la composante post-déblocage**
   de l'année1<0 (43% des cas, jamais adressé) — nouvelle piste ouverte
   par le diagnostic du 08/09, pas encore explorée.

---

## 9. Fichiers du chantier, par ordre chronologique

- `etape_a_formats_comptes_propfirms_2026-08-08.md` — recherche
- `engine_multiformat.py` + `engine_multiformat_smoke_test.py` — moteur (Étape B)
- `etape_c_solo_comparison.py` + `etape_c_solo_comparison_synthese.md` — comparaison solo
- `etape_d_fleet_format_search.py` — criblage simplifié (résultat invalidé, gardé pour traçabilité)
- `etape_e_fleet_integration.py` — moteur intégré production (fichier central de l'Étape E)
- `etape_e_integration_rapport.md` — 1er rapport Étape E (verdict WINNER rejeté)
- `etape_e_audit_2026-08-09.md` — audit bruit + 1er resweep risque
- `etape_e_verrouillage_final_2026-08-09.md` — confirmation n=600 deux plafonds + cascade
- `etape_e_audit_thresholds_gft_2026-08-09.md` — seuils + risque GFT
- `etape_e_diagnostic_annee1_2026-08-09.md` — diagnostic pré/post-déblocage + rampe + délai
- **`etape_e_synthese_globale_2026-08-09.md` — ce document, point d'entrée unique**
