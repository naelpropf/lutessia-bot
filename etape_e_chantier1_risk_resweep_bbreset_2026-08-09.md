# Chantier 1 — Re-balayage large du risque avec reset Blueberry actif (08/09/2026)

*Suite de `etape_e_blueberry_reset_2026-08-09.md` (mécanisme confirmé n=600).
Le reset change le coût du restart pour le compte pivot (Blueberry,
STARTER) — le paysage risque/profit mesuré avant son intégration n'était
plus fiable pour choisir le point de risque final. Scripts :
`etape_e_risk_sweep_bbreset_2026-08-09.py` (balayage, n=300, 84 cellules)
puis `etape_e_final_lock_bbreset_2026-08-09.py` (confirmation, n=600 +
cascade). Config : REF, seuils actuels, reset Blueberry actif en dur.*

---

## Balayage large (n=300, 7×6 grille × 2 plafonds = 84 cellules)

Grille : éval ∈ {1,00/1,25/1,50/1,75/2,00/2,25/2,50}%, flotte ∈
{1,50/1,75/1,90/2,25/2,50/2,75}%.

**`flotte=1,90%` reste le point dominant sur toute la grille** — confirmé
une 3e fois indépendamment (après l'audit du 08/09 et la vérification du
08/09 sans reset), pas un artefact de la finesse de grille.

Sur l'axe éval (à flotte=1,90% fixe), comparaison par paire de plafonds
(le point de risque est un choix de stratégie unique, évalué aux deux
plafonds, pas un choix par plafond) :

| éval | Profit 1000$/3000$ | Ruine 1000$/3000$ | Année1<0 1000$/3000$ |
|---|---|---|---|
| 1,00 | 4,93M$/4,95M$ | 0,67%/0,33% | 22,00%/21,67% |
| **1,25 (zone basse)** | 5,12M$/5,14M$ | 1,00%/0,33% | 20,33%/20,00% |
| 1,50 | 5,09M$/5,19M$ | 3,33%/1,00% | 20,00%/18,33% |
| 1,75 (zone haute) | 5,15M$/5,25M$ | 3,33%/0,67% | 18,00%/17,67% |
| 2,00 (zone haute) | 5,02M$/5,29M$ | **6,67%**/0,33% | 19,67%/16,67% |

**Aucun point de la zone haute (éval≥1,75% et/ou flotte≥2,25%) ne domine
ni n'égale 1,25%/1,90%** : chaque gain en profit (+0,6% à +3%) et en
année1<0 (-2 à -4pt) se paie par une ruine nettement plus élevée à
1000$ (jusqu'à ×6,7 à éval=2,00%) — un arbitrage réel, pas une
domination, particulièrement marqué au plafond le plus contraignant.
flotte≥2,25% est systématiquement pire quel que soit éval (profit en
baisse, année1<0 en hausse) — confirmé sans exception sur toute la
grille.

**1,25%/1,90% reste le meilleur point de la "zone basse"** : domine
clairement 1,00%/1,90% (+3,7% profit aux deux plafonds pour seulement
+0,33pt de ruine à 1000$).

Conformément à la consigne, c'est ce point qui est confirmé n=600 +
cascade (branche "sinon" — pas de domination zone haute trouvée).

---

## Confirmation n=600 + cascade check

| Plafond | Profit | Ruine | Année1<0 total | dont pré | dont post | Casse≤30j | Casse≤60j | Quasi-gelé |
|---|---|---|---|---|---|---|---|---|
| 1000$ | **4 827 736$** | **1,67%** | 20,83% | 10,33% | 10,50% | 24,64% | 44,13% | 1,5% |
| 3000$ | **4 892 588$** | **0,50%** | 20,33% | 9,33% | 11,00% | 24,71% | 44,22% | 0,3% |

**Cascade check GO** — casse≤30j/60j et quasi-gelé restent dans la
fourchette historique des configs déjà validées (loin du profil WINNER
rejeté à l'Étape E : casse≤30j=60%, quasi-gelé jusqu'à 16%).

`bb_resets_used` moyen ≈ 2,9/run, cohérent avec la confirmation isolée du
mécanisme (`etape_e_blueberry_reset_2026-08-09.md`).

---

## Chiffre de référence à date (avec reset Blueberry, risque re-confirmé)

**4 827 736$ / 4 892 588$** (plafond 1000$/3000$), éval=1,25%/flotte=1,90%,
GFT=1,75%, seuils inchangés (FTMO=1k/Fivers=15k/GFT=25k/FundedNext=25k),
reset Blueberry actif. Ceci est le chiffre le plus à jour du chantier
multi-format — améliore le chiffre pré-reset (4 663 331$/4 756 842$ à ce
même point de risque) de +3,5%/+2,8%, cohérent avec le gain isolé du
mécanisme reset (+3,0-3,1% mesuré séparément).

**Ne remplace toujours pas le chiffre verrouillé officiel du projet**
(5 794 566$/5 898 897$, ancien moteur 1-phase) — décision explicite
séparée, toujours en attente (cf. `etape_e_synthese_globale_2026-08-09.md`
§8, décision #3).

---

## Chantier 2 (scoping, pas de simulation)

Répondu inline dans la conversation (pas de fichier séparé) : format
adaptatif par seuil de réserve, jugé faisable en session dédiée
(60-90 min), formats rapides déjà disponibles (= formats CONFIG_WINNER),
seuil de bascule recommandé global (réutilise `state["reserve"]`), format
verrouillé à la première création du compte (pas de bascule en cours de
vie ni de ré-évaluation aux réouvertures). Attend le feu vert utilisateur
avant implémentation — et si un format gagnant émerge, le risque devra
être re-balayé une 3e fois pour cette nouvelle configuration (même
méthode que ce document).
