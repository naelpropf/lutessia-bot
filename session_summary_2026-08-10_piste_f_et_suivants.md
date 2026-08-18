# Résumé de session — 2026-08-09 soir → 2026-08-10 nuit
### Bootstrap parallèle → Piste F (sizing DD) → REF+V2 → diagnostics associés

*Document autonome, pensé pour être collé dans un projet Claude sans perdre le fil. Contient tous les chiffres, tous les verdicts, et les décisions encore ouvertes. Les scripts cités existent tous dans le repo (racine du projet).*

---

## 0. TL;DR

- **Deux leviers structurels confirmés cette session** (n=600 + cascade check), tous deux **conditionnels au plafond de cash personnel**, et pointant vers des plafonds opposés :
  - **Bootstrap parallèle (BB+GFT)** → gagnant à **3000$**, rejeté à 1000$.
  - **Sizing DD pré-déblocage (V2)** → gagnant à **1000$**, pas de gain à 3000$.
- **REF+V2 est maintenant la référence officielle du projet au plafond 1000$** (remplace l'ancien chiffre verrouillé 5 794 566$/5 898 897$).
- **Deux points bloquants non résolus** à trancher avant d'aller plus loin (section 3).
- **Quatre pistes testées et rejetées** cette session (fongibilité, coupe-circuit réactif, piste H routage, et — sur données déjà produites — la thèse initiale de piste A "casse rapprochée").
- **Ton plafond personnel réel (1000$ ou 3000$ ?) n'a toujours pas de réponse** — c'est la question qui débloquerait le plus de décisions d'un coup.

---

## 1. Référence officielle actuelle

⚠️ **Tout ce qui suit utilise éval=1,25% (profit max), PAS éval=1,00%** (l'alternative "recommandée" jamais testée avec V2 par-dessus — voir point bloquant #1 section 3).

| Plafond | Référence | Profit | Ruine | Année1<0 |
|---|---|---|---|---|
| **1000$** | **REF + V2** (sizing DD pré-déblocage) | **4 872 626$** | **0,83%** | **20,67%** (pré=8,67%) |
| 1000$ | REF pure (sans V2) | 4 827 736$ | 1,67% | 20,83% (pré=10,33%) |
| **3000$** | **REF pure** (V2 n'y gagne pas) | **4 892 588$** | **0,50%** | **20,33%** (pré=9,33%) |
| 3000$ | Bootstrap parallèle BB+GFT (si 3000$ retenu comme plafond) | 5 097 319$ | 0,67% | 15,67% (pré=3,50%) |

Le chantier n'a **pas encore tranché** lequel des deux plafonds constitue "la" référence unique du projet.

---

## 2. Les deux leviers structurels confirmés

### 2.1 Bootstrap parallèle (BB+GFT) — gagnant à 3000$

Au lieu d'un seul compte Blueberry (165$) au jour 0, ouvrir Blueberry + GFT en parallèle (453$ au jour 0, 3× moins cher que 3 firms). Règle de déblocage : "premier financé suffit".

| Plafond | Profit | Ruine | Année1<0 (pré) |
|---|---|---|---|
| 1000$ solo (baseline) | 4 827 736$ | 1,67% | 20,83% (10,33%) |
| 1000$ BB+GFT | 4 561 623$ | 10,67% | 24,17% (13,67%) — **rejeté sans ambiguïté** |
| 3000$ solo (baseline) | 4 892 588$ | 0,50% | 20,33% (9,33%) |
| **3000$ BB+GFT** | **5 097 319$ (+4,2%)** | **0,67%** | **15,67% (pré=3,50%, -62% relatif)** |

Script : `etape_f_bootstrap_parallele_2026-08-09.py`.

### 2.2 Sizing DD pré-déblocage (V2) — gagnant à 1000$

Réduit le risque flotte quand un compte approche de son propre DD max (statique ou trailing selon le format), UNIQUEMENT avant le déblocage complet (post-déblocage = risque plein, la flotte est déjà diversifiée). Mécanisme B : seuil d'entrée=20% de marge restante, réduction=50%, hystérésis +10pt.

| Plafond | Profit | Ruine | Année1<0 (pré) |
|---|---|---|---|
| **1000$ REF+V2** | **4 872 626$ (+0,93%)** | **0,83% (÷2)** | **20,67% (pré=8,67%, -1,66pt)** |
| 3000$ REF+V2 | 4 885 566$ (-0,14%) | 0,33% | 20,67% (pire) — **pas de gain** |

Scripts : `etape_i_dd_distance_sizing_2026-08-10.py` (sweep initial 12 configs), `etape_j_dd_distance_recalibration_2026-08-10.py` (décomposition + recalibration + confirmation n=600).

**Pourquoi les deux pointent vers des plafonds opposés** : les deux protègent contre l'épuisement de trésorerie. Le sizing DD a de la valeur quand éviter une casse compte vraiment (plafond serré = 1000$) ; à 3000$ les casses sont déjà absorbables sans effort, donc réduire la taille ne fait que coûter de l'opportunité. Le bootstrap parallèle, lui, immobilise plus de cash dès le jour 0 — supportable seulement si le plafond est large (3000$).

---

## 3. Points bloquants — non résolus, à trancher

### 🔴 Bloquant #1 — éval=1,00% ou 1,25% ?
Ta consigne de documentation disait "REF (éval=1,00%/flotte=1,90%)" mais **tout ce qui a été testé et confirmé cette session (V2 inclus) utilise éval=1,25%** (vérifié par citation de code à plusieurs reprises). Le point de risque 1,00% était resté une décision ouverte jamais tranchée. Si tu veux vraiment 1,00%, il faut reconfirmer V2 sous ce risque avant de le documenter comme référence officielle — actuellement documenté sous 1,25% par défaut (c'est ce que l'évidence supporte).

### 🔴 Bloquant #2 — ton plafond personnel réel : 1000$ ou 3000$ ?
Les deux leviers structurels du chantier (bootstrap parallèle, sizing DD V2) sont **conditionnels au plafond** et pointent en sens opposés. Impossible de choisir une config finale sans cette info.

### 🟡 Conflit non résolu — Blueberry : limite en nombre de comptes ou en capital ?
Recherche web (08/10) : 3 sources convergentes disent que Blueberry n'impose **aucune limite de nombre de comptes**, seulement une limite de **capital total** (~400k$ initial, jusqu'à 2M$ scaling). Ça **contredit** le registre existant ("3 comptes financés simultanés max, confirmé séparément" — source antérieure, probablement un chat support plus précis). Aucune des deux sources n'est tranchée comme la bonne.

---

## 4. Pistes testées et REJETÉES cette session

| Piste | Verdict | Raison en une phrase |
|---|---|---|
| **Fongibilité inter-firm** (redirection de capital vers le meilleur EV/$ à la casse) | Rejeté | Réserve bimodale (abondante ou ruine totale) — la fenêtre où rediriger compterait vraiment est trop rare sur cette flotte |
| **Coupe-circuit réactif** (réduction de risque sur mauvaise passe récente) | Rejeté, fermé | Le pool a un edge positif à forte variance — une mauvaise passe est presque toujours du bruit, pas un vrai signal |
| **Piste H** (routage flotte-wide, exclusion JPY-JPY pour un sous-ensemble de comptes) | Rejeté | Effet nul confirmé empiriquement (100%→100% de runs post-négatifs touchant les 5 firms, inchangé) — le signal source (AUD/JPY-USD/CHF, corr=-0,09) était trop faible dès le départ |
| **Piste A "casse rapprochée"** (thèse initiale sur BB+GFT) | Invalidée par les données | Ce n'est pas une histoire de casses corrélées — GFT gagne systématiquement la course de financement (64,7% vs 30,7% pour Blueberry), un mécanisme de course asymétrique, pas de double-casse |

**Piste F (sizing DD) reste ouverte** pour calibrage plus fin, contrairement au coupe-circuit — voir §2.2, le signal lui-même (distance au DD, pas la performance récente) n'est pas rejeté en principe.

---

## 5. Diagnostics (pas des leviers, juste des mesures)

### 5.1 Délai de rattrapage (année1<0 → retour positif), n=600, plafond 1000$

| | REF pure | REF+V2 |
|---|---|---|
| Médiane | 14,25 mois | 14,28 mois |
| P25 / P75 | 12,86 / 17,72 | 12,63 / 17,44 |
| Jamais rattrapé (% de TOUS les runs) | **1,5%** | **0,83%** |

⚠️ Le chiffre "0,33% ne rattrapent jamais" cité depuis le 08/08 est **obsolète sous le moteur actuel** — le vrai chiffre est 1,5% sous REF pure (×4,5). Toujours classé "pas alarmant" (reste <2%), mais à corriger dans le registre. V2 réduit la queue extrême (1,5%→0,83%) mais **pas** le délai médian.

Corrélation délai-de-déblocage ↔ résultat à 12 mois : **r=-0,46 à -0,52** (magnitude comparable au 0,53-0,54 cité en 08/08, tient toujours sous le moteur actuel).

### 5.2 Réconciliation FTMO-10%/GFT Goat Guard (n=600, confirmé, aucun bug)

| | Profit 1000$/3000$ | Ruine | Année1<0 |
|---|---|---|---|
| Baseline n=600 | 4 827 736$ / 4 892 588$ | 1,67%/0,50% | 20,83%/20,33% |
| (a) FTMO -10% | 4 835 966$ / 4 894 313$ | 1,50%/0,50% | inchangé |
| (b) GFT Goat Guard | 4 877 869$ / 4 943 231$ | 1,67%/0,50% | +0,33pt |
| (c) combiné | 4 886 315$ / 4 945 037$ | 1,50%/0,50% | +0,33pt |

Candidat séparé, **pas encore combiné avec V2** (interaction non testée). Cible le mode d'échec post-déblocage (restart complet sur compte déjà financé).

### 5.3 Seuil de déblocage FTMO — reconfirmé optimal sous REF+V2

Balayage {0$, 500$, 1000$, 2000$, 5000$}, n=300, 2 plafonds : **1000$ (valeur déjà en place) domine sur les 3 axes aux deux plafonds**. Aucun changement recommandé.

---

## 6. Scoping fait, pas encore codé

| Piste | Statut | Résumé |
|---|---|---|
| **Fonction de priorité EV/$** (Étape C régénérée) | Fait, disponible | FundedNext (953,68) > Fivers (783,39) > GFT (638,57) > Blueberry (615,67) > FTMO (578,03) — classement INVERSÉ par rapport à une lecture naïve par coût seul |
| **Piste G** (exclusion corrélée conditionnée à l'état DD, complément de V2) | Scopé, faisable (~1h) | Réutilise `dd_distance_pct` — mais pas de paire corrélée robuste identifiée à date, ne pas implémenter sans meilleur signal |
| **Piste A'** (2× Blueberry parallèle) | Scoping conditionnel — pas encore fait | Débloqué par la recherche Blueberry (§3) mais le mécanisme exact (state par firm, pas par compte) doit être vérifié |
| **Décorrélation asymétrique** (piste A/A') | Scoping conditionnel — pas encore fait | La prémisse initiale (arbitrage gain/risque sur double-réussite) est invalidée par §4 — à reformuler avant de scoper |

---

## 7. Scripts produits cette session (repo root)

| Script | Rôle |
|---|---|
| `etape_f_bootstrap_parallele_2026-08-09.py` | Bootstrap parallèle multi-firm |
| `etape_g_circuit_breaker_2026-08-09.py` | Coupe-circuit réactif (rejeté) |
| `etape_h_fongibilite_slots_2026-08-10.py` | Fongibilité inter-firm (rejeté) |
| `etape_i_dd_distance_sizing_2026-08-10.py` | Piste F sweep initial (12 configs) |
| `etape_j_dd_distance_recalibration_2026-08-10.py` | Piste F décomposition + recalibration + V2 confirmé |
| `etape_k_piste_a_decomposition_2026-08-10.py` | Décomposition BB+GFT (course asymétrique) |
| `etape_l_recovery_diagnostic_2026-08-10.py` | Diagnostic délai de rattrapage |
| `etape_m_piste_h_routing_2026-08-10.py` | Piste H routage (rejeté) |
| `etape_n_seuil_deblocage_sweep_2026-08-10.py` | Reconfirmation seuil FTMO |
| `etape_c_solo_comparison_corrige_2026-08-09.py` | Étape C régénérée, ratio EV/$ |

Toute la traçabilité détaillée (raisons, code cité, conditions de réouverture) est dans `registre_parametres_projet.md` §2.6-2.9 et §4, et dans les fichiers mémoire `project_*_2026-08-1{0,9}.md`.

---

## 8. Prochaines étapes suggérées

1. **Trancher les 2 points bloquants** (§3) — c'est ce qui débloque le plus de décisions en aval.
2. Décider si (a) et (b) de la réconciliation (§5.2) rejoignent V2 dans la config de référence.
3. Scoper piste A' et la décorrélation asymétrique (§6) une fois le plafond personnel connu.
4. Mettre à jour le chiffre "délai de rattrapage jamais atteint" dans le registre (1,5% pas 0,33%).
