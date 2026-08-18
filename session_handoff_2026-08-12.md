# Handoff — reprise après clear (2026-08-12)

Lire en premier :
- `registre_parametres_projet.md` — §1.8 (référence par plafond) et §4
  (décisions ouvertes, jusqu'à la décision #32 inclus)
- `registre_strategie_trading.md` — volet edge/coupe-circuit (fermé,
  rien de nouveau côté edge cette session)

## Référence officielle capital (§1.8, décision #16) — INCHANGÉE

Asymétrique par plafond : **Run C à 1000$** (cadence Blueberry 14j,
5 491 410$, année1<0=35,50%), **Run F à 3000$** (Blueberry 7j+surcoût
20%, 5 589 954$, année1<0=32,83%). Rien touché à ça cette session.

## Chantier principal de la session : dual-trader (capital combiné, 2 traders)

Fichier moteur : `dual_trader_2026-08-11.py`. Historique complet dans
`registre_parametres_projet.md` §2.50-2.58, décisions #27-32.

**État final (n=600+cascade confirmé, §2.53)** :
- **Config 1** (même stratégie sur T1/T2, réserves de trading séparées,
  plafond personnel COMBINÉ 1000$/3000$ total — pas par trader,
  correction méthodologique appliquée 08/12) : 3000$ = **10 041 125$**,
  hit_ceiling 2,00% — meilleur profit.
- **Config 4** (T1=stratégie A signal principal, T2=stratégie B canal
  contrarian RR 0,75-1,25, réserve de trading COMMUNE) : 3000$ =
  **6 084 214$**, hit_ceiling 0,83% — risque quasi nul, -39% de profit
  vs config 1.
- **Config 1@1000$ confirmée trop risquée** (hit_ceiling 23,50% à
  n=600) — hors jeu.
- **Choix final entre les 2 options à 3000$ (profit max vs risque quasi
  nul) laissé à l'utilisateur, jamais tranché.** C'est le point de
  décision n°1 en attente.

**Mécanisme de sauvetage croisé (config 4) décomposé (§2.57)** : le
sens du sauvetage s'inverse selon le plafond (à 1000$ T2 est sauvé
69,7% du temps ; à 3000$ c'est T1 à 85,7%). T1 ne gagne PAS en moyenne
de son association avec T2 (légèrement pire que solo, -3%, à cause du
plafond personnel partagé) — toute la valeur de config 4 vient de la
contribution propre de T2. Un bug de calcul (oubli de soustraire
l'impôt par trader) a été trouvé et corrigé en cours de route avant de
publier ces chiffres.

**Audit préventif fait (§2.54, décision #31)** : 3 problèmes mineurs
trouvés, aucun ne remet en cause les résultats (IS calculé par trader
au lieu de la SAS combinée, impact <0,001% ; emergency_capital 300$ non
fusionné ; biais d'ordre T1-avant-T2 sur réserve commune). Rien
d'autre trouvé.

**Stratégie B isolée confirmée n=600 (§2.55, décision #32)** : échoue
à 76-77% en année 1 si elle doit porter une flotte seule (vs ~30% pour
le signal principal) — n'est PAS un moteur de croissance robuste,
seulement un diversificateur marginal en complément.

**Risque optimal Stratégie B (§2.58)** : eval=1,75% domine 1,25% en
isolation (profit +7,1%, tous risques meilleurs). Mais réappliqué à T2
dans config 4 : effet mitigé, pas de gain net (dégrade même le
mécanisme de sauvetage à 1000$, hit_ceiling +1,67pt). **Pas adopté.**

**Architecture infra VPS1→VPS2 (§2.56)** : webhook HTTP recommandé,
heartbeat séparé pour la détection de panne (pas un simple timeout sur
absence de signal), hystérésis au retour pour éviter de recréer
l'incident du 29/07. Analyse seule, rien codé — à faire avant tout
contact support prop firm.

## ⚠️ CHANTIER EN COURS, NON TERMINÉ : cluster Blueberry 1,5%

**Dernier message reçu juste avant ce handoff, PAS ENCORE traité.**
Découverte confirmée officiellement : sur Blueberry, toutes les
positions FX Majors simultanées partagent un seul budget de risque de
1,5% (pas 1,5% par position individuelle) — un cluster-risk jamais
modélisé dans le moteur jusqu'ici.

Trois options à comparer en n=300, tableau à 4 axes standard, sur la
config de référence (éval=1,25%/funded=1,90%) :
- **(A)** Passer Blueberry au format PRIME (specs P1=8%/P2=6%, DD
  journalier 4%, DD max 10% statique, levier 1:30, split 80%, PAS de
  restriction cluster). Prix exact du palier 25k$ à rechercher (source
  connue donne juste une fourchette 30$-1170$). Vérifier aussi si la
  contrainte de faisabilité levier 1:30 (déjà repérée comme gênante à
  partir de 500k$ dans une session antérieure — référence exacte pas
  encore retrouvée) s'aggrave sur les paliers Blueberry visés par le
  scaling (jusqu'à 2M$).
- **(B)** Garder Blueberry en 2-Step mais modéliser le vrai cluster :
  sizing dynamique qui réduit le risque par position selon le nombre de
  positions FX Majors déjà ouvertes simultanément sur le même compte.
- **(C)** Retirer Blueberry entièrement de la flotte — modéliser quelle
  firm reprend le rôle de starter jour 0 bon marché (FTMO/GFT/
  The5%ers/FundedNext, la moins chère), impact sur le délai de
  déblocage et le profit final. **Traiter avec la même rigueur que les
  2 autres options, pas comme un choix par défaut.**

**Progrès fait avant l'interruption** : découverte qu'`engine_
multiformat.py` contient déjà DEUX définitions Blueberry 2-step
ambiguës et jamais tranchées : `Blueberry_Prime2Step` (P1=8%/P2=6%,
DD4%/10% statique, prix 165$@25k — matche EXACTEMENT les specs Prime
données par l'utilisateur) et `Blueberry_2StepStandard` (P1=10%/P2=5%,
DD5%/10%, prix non trouvé). `CONFIG_REF` (la référence officielle du
projet) utilise déjà `Blueberry_Prime2Step` — donc soit la référence
actuelle EST déjà en pratique le format Prime (mais sans jamais avoir
modélisé le levier 1:30 ni le cluster, aucun des deux n'étant dans
`format_def`), soit il y a une confusion de nommage historique à
clarifier avant de coder l'option (A) pour de vrai. Aucune recherche de
prix web n'a encore été faite (session interrompue juste avant). Aucun
code de simulation pour les 3 options n'a été écrit.

**Prochaine étape immédiate à la reprise** : reprendre exactement là —
(1) clarifier la confusion Prime2Step/2StepStandard dans le code
existant, (2) chercher le prix réel du palier 25k$ Blueberry Prime
(WebSearch/WebFetch), (3) retrouver la session antérieure qui a
identifié la contrainte de faisabilité levier 1:30 à partir de 500k$
(chercher "feasible_risk_pct", "margin_per_lot", "500k" dans le
dépôt — recherche commencée, pas aboutie), (4) construire et lancer les
3 options en n=300.

## Fichiers clés créés cette session (tous suivis par git sauf indication)

- `pistes_survie_2026-08-11.py`, `edge_amplification_*_2026-08-11.py`,
  `structure_pistes_2026-08-11.py`, `structure_section2_diagnostic_
  2026-08-11.py` — chantiers pistes 1-5 + amplification + structure A-D
  (tous fermés/documentés, rien à reprendre).
- `dual_trader_2026-08-11.py` — moteur principal du chantier dual-trader,
  modes : `matrix`, `confirm`, `screen` (périmé), `spec` (périmé).
- `dual_trader_config4_decomposition_2026-08-12.py`,
  `dual_trader_config4_t2_risk_optimized_2026-08-12.py`,
  `strategy_b_isolation_confirm_2026-08-12.py`,
  `strategy_b_risk_sweep_2026-08-12.py` — scripts de la fin de session,
  tous exécutés avec succès, résultats dans le registre.
- CSV/logs de résultats : non versionnés (gitignore projet-wide sauf
  `correlation_matrix.csv`), régénérables en relançant les scripts avec
  le même seed=9999.

## Décisions bloquantes qui restent ouvertes (rappel §4)

1. Choix final config 1 vs config 4 à 3000$ (profit max vs risque quasi
   nul) — dual-trader, jamais tranché.
2. Éval 1,00% vs 1,25% (décision #2, ancienne, toujours ouverte).
3. Plafond personnel réel 1000$ vs 3000$ (décision #9, ancienne,
   partiellement contournée en testant les deux partout).
4. **Nouveau** : réponse au cluster Blueberry 1,5% (chantier démarré,
   pas fini, voir section dédiée ci-dessus).
