# Étape S (08/10 nuit) — Scoping piste A' (2× Blueberry parallèle)

**Scoping uniquement, aucun code écrit.** Bloqué sur le conflit non résolu
du nombre de comptes Blueberry simultanés autorisés (registre §4 décision
#6, `project_blueberry_account_limit_conflict_2026-08-10.md`) — nécessite
un contact support direct de l'utilisateur, pas de nouvelle recherche web.
Ne pas implémenter tant que non confirmé.

## Idée

Généraliser le mécanisme STARTERS (déjà utilisé par le bootstrap parallèle
BB+GFT/BB+FTMO, `etape_f_bootstrap_parallele_2026-08-09.py`) à 2 comptes de
la **même firm** (Blueberry) plutôt qu'à 2 firms différentes. Même risque
éval pour les deux comptes (1,25%, aucune différenciation demandée).

**Coût jour 0** : 2×165$ = **330$** — moins cher que BB+GFT (453$) ou
BB+FTMO (510$), donc structurellement plus attractif au plafond serré
(1000$) où tous les combos multi-firm testés à l'Étape F ont été rejetés
sans ambiguïté (marge de cash trop entamée). C'est la motivation directe :
diversifier le point de défaillance unique pré-déblocage sans payer le
plein tarif d'une 2e firm.

## Analyse du code existant (`etape_f_bootstrap_parallele_2026-08-09.py`)

Le mécanisme STARTERS généralise déjà "firm ouverte en parallèle au jour
0" via une liste de comptes par firm (`accounts_by_group[gname]`, déjà une
LISTE, pas un singleton) — la plupart du code ne suppose PAS qu'un seul
compte par firm est actif. Deux points precis supposent encore
implicitement "1 seul starter par firm" :

1. **Init jour 0** (`n_accs = ei.N_ACCOUNTS_DAY0[gname]` puis seul l'index
   0 est activé si `is_starter`) — `N_ACCOUNTS_DAY0["Blueberry"] = 1`
   (confirmé, `etape_e_fleet_integration.py:114`), donc un seul slot
   Blueberry existe même à créer. Il faut un override dédié (ex.
   `STARTER_COUNT = {"Blueberry": 2}`) pour créer 2 slots Blueberry au
   lieu d'1 et activer les DEUX au jour 0 (au lieu de `i == 0` seulement).
   ~10-15 lignes.
2. **`try_emergency_bootstrap()`** — la liste de candidats ne prend que
   `accounts_by_group[g][0]` (index 0) pour chaque firm starter. Avec 2
   Blueberry starters, il faut itérer TOUS les slots starter inactifs
   (index 0 ET 1), pas seulement le premier. ~5 lignes.

Tout le reste généralise **sans modification** :
- Casse/relance (reset Blueberry, downgrade-on-reopen, coût `base_cost`
  pré-déblocage) : déjà indexé par identité de compte (`id(acc)`), pas par
  firm — s'applique automatiquement à N'IMPORTE quel slot Blueberry,
  starter ou pas.
- `structure_complete()` : vérifie seulement l'index 0 par firm (« au
  moins un compte actif ») — non affecté par un 2e starter Blueberry.
- Croissance extra-comptes (`process_extra_account`) : boucle déjà sur
  `len(accs)` et la capitalisation cumulée, pas sur un compte-index fixe —
  laissera automatiquement moins de place pour un extra-compte futur
  (2 slots déjà pris par les starters au lieu d'1), sans changement de
  code nécessaire.

## Interaction avec le cap de comptes Blueberry

`FIRM_MAX_ACCOUNTS["Blueberry"] = 3` (déjà codé, VERROUILLÉ dans le
registre §1.3 malgré le conflit sur le cap **en dollars**). Même sous la
lecture la PLUS restrictive du conflit actuel (3 comptes max, pas
illimité), 2 starters simultanés tient dans ce plafond (2 ≤ 3) — piste A'
ne serait donc bloquée QUE si le contact support révèle un cap encore plus
bas que 3, ce qui n'a jamais été évoqué par aucune source jusqu'ici. Le
seul coût réel de la piste : elle ne laisse plus qu'1 slot d'extra-compte
Blueberry disponible après déblocage (au lieu de 2), un vrai arbitrage à
mesurer une fois codé, pas un blocage de faisabilité.

## Estimation d'ampleur

**~30-45 minutes d'implémentation + smoke test** — le plus petit levier
structurel scopé sur ce chantier à ce jour :
- Plus petit que le bootstrap parallèle lui-même (qui a dû généraliser
  STARTER string→tuple sur ~5 points de code lors de sa création
  08/09).
- Nettement plus petit que la fongibilité inter-firm (scopée 08/09 à
  "demi-journée à une journée", nécessitait un nouveau modèle de données
  ET une décision de conception sur la fonction de priorité — aucun des
  deux n'est requis ici).
- Comparable en ampleur à la 2e tâche de cette session (démarrage différé
  du 2e starter, `etape_r_piste_a_delayed_start_2026-08-10.py`), qui a
  nécessité une file d'attente de déclenchement dédiée — piste A' n'a
  besoin d'aucune nouvelle logique de déclenchement, juste d'un override
  de comptage au jour 0.

L'estimation ne dépend pas du résultat du contact support (générique à N
comptes d'une même firm, pas câblée en dur à 2) — seule la DÉCISION
d'implémenter est bloquée, pas la faisabilité technique elle-même.

## Verdict

**Faisabilité technique : élevée, effort faible.** Prêt à implémenter dès
que le conflit Blueberry (registre §4 décision #6) est résolu par contact
support direct. Aucun blocage structurel identifié dans le moteur actuel.
