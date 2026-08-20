# Contexte projet — Lutessia Copytrade — moteur A+B parallèle + adoption trailing B

Tu es Claude Code, moteur de simulation Python pour un projet de copytrade
sur comptes prop firm. Reprends le contexte complet via
`session_handoff_2026-08-19.md`, `registre_parametres_projet.md` §9 et
`registre_strategie_trading.md` §5 avant de répondre à quoi que ce soit
ci-dessous.

**Rappel de l'état actuel** :
- Stratégie B (571 trades, forex[1,00;1,35)+tout-indices) a un levier
  officiellement mûr et confirmé n=600 : **trailing 0,10×SL** (remplace
  0,15× hérité de A), dominance stricte 4 axes/4 plafonds.
- Le blocage principal avant un lancement A+B en parallèle : **aucun
  moteur de simulation ne fait tourner A et B comme 2 comptes séparés
  avec réserve de cash partagée** — les scripts actuels remplacent A par
  B dans la même flotte (isolation), ils ne les combinent jamais.
- Diagnostic corrélation sur B (n=31, delta +0,99R, IC95% positif) reste
  sans mécanisme actionnable trouvé.
- Deux leviers B (filtre ADX>32,27, sizing rr_tp1≤1,25) ont un signal
  statistique propre mais ont été REJETÉS en Monte Carlo fleet — B est
  frequency-starved, réduire le volume coûte plus cher que ça n'économise.

**Règles méthodologiques à respecter strictement** :
- n=300 = screening seulement. n=600 + stress-test H1/H2+4blocs = seul
  niveau de verdict acceptable pour une adoption.
- Toute affirmation sur le code = citation exacte fichier:ligne.
- Se méfier des résultats "trop beaux" — historique du projet plein de
  faux positifs.
- Un signal statistique propre n'implique PAS une confirmation fleet
  (leçon de la session précédente) — toujours vérifier les deux niveaux.

---

## Point 1 — Concevoir le moteur A+B parallèle (chantier d'ingénierie)

Avant tout test, propose une conception (pas de code tout de suite) :

1. Comment représenter 2 flux de signaux indépendants (A et B) alimentant
   2 comptes séparés dans la même flotte, avec une réserve de cash
   commune ? Base-toi sur `chantier_strategie_b_isolation_indices_2026-
   08-18.py` (le moteur d'isolation actuel) et `engine_multiformat.py`
   pour identifier précisément ce qui doit changer.
2. Comment gérer la règle de corrélation/JPY-JPY ENTRE les deux comptes
   (positions simultanées sur des paires corrélées, une sur le compte A,
   une sur le compte B) — partagée ou indépendante par compte ? Justifie
   ton choix par citation de code existant si un précédent existe.
3. Donne une estimation du travail (fichiers à créer/modifier, points de
   risque de bug) avant de commencer à coder.

Implémente ensuite ce moteur, teste-le avec un test de fumée n=5 avant
tout run n=300.

## Point 2 — Comparaison A seul / B seul / A+B parallèle, n=600

Une fois le moteur construit et validé (smoke test propre) : compare aux
4 plafonds habituels (960$/1000$/3000$/5000$) :
1. A seul (REF actuelle)
2. B seul (avec trailing 0,10× déjà adopté)
3. A+B en parallèle (risque hérité de A sur les deux comptes pour ce
   premier test — pas de recalibrage spécifique à B pour l'instant)

Rapporte profit, solde_négatif, hit_ceiling_pct, année1<0. Stress-test
H1/H2+4blocs avant toute conclusion. Verdict : A+B parallèle domine-t-il
A seul (justifiant le lancement à 2 comptes), ou est-ce un arbitrage ?

## Point 3 — SI le Point 2 est concluant : recalibrer le risque par trade sur B dans ce nouveau moteur

Reprends la question différée de la session précédente : calcule un
risque par trade recalibré spécifiquement sur B (même méthode qu'utilisée
à l'origine pour calibrer 1,25%/1,90% sur A — grille sweep n=300 puis
n=600 sur le moteur A+B) et compare au risque hérité de A.

---

## Format de réponse attendu

Point 1 d'abord (conception, donne-moi l'occasion de valider avant de
coder si le design a des choix ambigus). Points 2-3 ensuite avec chiffres
bruts et stress-test. Termine par un verdict explicite : le lancement A+B
en parallèle est-il justifié par les chiffres, ou reste-t-il un chantier
ouvert ?
