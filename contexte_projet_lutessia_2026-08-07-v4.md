# Contexte projet trading Lutessia — v4, 7 août 2026 (session marathon)

Remplace `contexte_projet_lutessia_2026-08-07-v3.md` comme mémoire de reprise.
Conserve tout ce qui était déjà validé en v3 (config stratégie, séquence de
lancement Blueberry-first — section 1-2 de v3, toujours valides), ajoute
l'intégralité des découvertes d'une session marathon (même journée,
plusieurs heures) sur : split/fiscalité, plafond progressif, stabilité du
signal, et surtout une refonte complète du risque de ruine du plan de
lancement (section 0 à lire en premier — c'est la partie qui change le plus
de choses).

---

## 0. ⚠️ POINTS CRITIQUES — À LIRE EN PREMIER

### 0.1 — Le vrai risque de ruine du plan de lancement a été découvert, caractérisé, et fortement réduit

**Découverte majeure** : la structure de lancement verrouillée en v3 (Blueberry
seul day0, reste de la flotte déclenché au 1er financement, plafond hybride
1000$/3000$) a un **vrai risque de ruine finale non nul** — jamais mesuré
avant cette session. Sous simulation rigoureuse (winrate tiré du posterior
bayésien Beta(260,388) par run, pas un point fixe), **P(profit final < 0) =
34-40% à 1000$, 17-26% à 3000$** sur l'horizon complet (~3,96 ans).

**Mécanisme identifié avec certitude** (pas une hypothèse) :
- 87-100% des cas de ruine viennent d'un **effondrement TOTAL de toute la
  flotte** (0 compte actif), PAS de l'échec du seul compte Blueberry initial
  (12,9%/0% des cas seulement).
- Cause : l'ouverture GROUPÉE du reste de la flotte (FTMO+Fivers+GFT+
  FundedNext, ~3500$ de coût ponctuel, 9 comptes d'un coup) tape lourdement
  dans le plafond juste après le 1er financement Blueberry, quand le coussin
  est encore minimal — l'effondrement survient ~1,5-2,5 mois après.
- **Ce n'est PAS une corrélation entre comptes** (vérifié directement, pas
  supposé) : 0,0% des casses d'un même cluster partagent le même signal
  Lutessia. Le vrai mécanisme est une **attrition indépendante cumulative**
  (chaque compte casse sur SES propres trades, ~7-9 jours d'écart moyen) qui
  épuise le pool de trésorerie partagé plus vite qu'il ne se reconstitue —
  parce que chaque casse coûte cash IMMÉDIATEMENT (rachat) alors que le
  profit n'existe qu'après succès ET financement d'une évaluation.

**Mitigation trouvée et validée (la meilleure combinaison à ce jour)** :
1. **Réserve minimale avant déblocage groupé** : exiger `reserve >= 30 000$`
   (au lieu de rien) avant d'ouvrir le reste de la flotte, tout en gardant
   l'ouverture GROUPÉE (pas de cascade multi-étapes — testée et **dominée**,
   même corrigée avec seuil par étape, cf. section 4).
   → Ruine 34-40%→**19,00%/34,83%** (1000$, au fil des itérations) puis
   affinée à **15,67%** avec la config finale ; 17-26%→**4,33%** (3000$).
2. **Capital d'amorçage protégé 300$** : somme hors-plafond dédiée
   exclusivement à rouvrir Blueberry (le moins cher) SI tous les comptes sont
   simultanément cassés — petit gain net additionnel.
3. **🏆 LA DÉCOUVERTE LA PLUS IMPORTANTE — risque réduit PENDANT L'ÉVALUATION
   uniquement (2,0% au lieu de 2,5%)** : actuellement un compte en évaluation
   (challenge, pas encore financé) passe de 2,0% (rampe) à 2,5% (risque
   cible) après seulement 5 trades — **avant même d'être financé**,
   augmentant inutilement le risque de casse sèche (perte 100%, aucun profit
   jamais généré) sur la phase la plus fragile. Garder 2,0% tout au long de
   l'évaluation (le risque cible normal reprend une fois financé) est un
   **gain gratuit** : réduit la ruine ET augmente le profit simultanément
   (contrairement à réduire le risque de toute la flotte, qui réduit la
   ruine mais coûte ~13-24% de profit).

**Config finale recommandée (à valider avant application au code live)** :
plafond hybride + réserve 30 000$ avant déblocage groupé + capital
d'amorçage 300$ + **risque réduit à 2,0% pendant toute la phase
d'évaluation (pas seulement les 5 premiers trades)** →
**ruine 7,00% à 1000$ / 1,00% à 3000$** (contre 34-40%/17-26% initial),
**profit final SUPÉRIEUR** à la config sans cette correction (+6,7%/+1,0%).

**Comparé au repère historique "0% de ruine année 3/4"** (year1_outcome_
recovery_full.py, 31/07) : ce chiffre venait d'un modèle **fondamentalement
différent et depuis invalidé** — plafond personnel infini de facto (la
fiction comptable débunkée le 06-07/08), 3 comptes une seule firm, ancien
régime de risque. Pas une contradiction à corriger, deux modèles différents ;
le nouveau chiffre (7,00%/1,00% avec la config finale) est la référence
désormais.

**Reste ouvert / non testé** : combinaison risque-éval réduit + risque-flotte
réduit (pourrait pousser encore un peu plus bas, coût de profit modéré, pas
chiffrée). Seuils de réserve au-delà de 30k$ : **plateau total confirmé
(flat jusqu'à 150k$)**, ne plus tester cet axe.

### 0.2 — Split prop firm confirmé jamais intégré, maintenant corrigé

Vérifié par lecture directe du code (pas supposé) : AUCUN script du projet
avant cette session n'appliquait de split/profit-share prop firm — tout le
P&L de trading était conservé à 100%. `RESERVE_SHARE=0.80` est un ratio
d'allocation interne (réserve/dispo), pas le split prop firm.

Corrigé dans `split_tax_model.py` : split modélisé par un barème croissant
80%→90% (+5pt par upgrade de palier, plafonné 90%) appliqué aux trades
gagnants uniquement — **approximation, aucun barème exact par firm/palier
n'a jamais été sourcé dans ce projet, à faire confirmer**.

**Impact chiffré** (ceiling=1000$, winrate réel 40,09%) : profit brut
7 792 277$ → net de split **5 758 848$ (-26,1%)**.

### 0.3 — Fiscalité SASU modélisée précisément, risque de conflit avec rachat de comptes : négligeable

Calendrier SASU/IS réel modélisé (année 1 sans acompte, solde ~105j après
clôture ; année 2+ acomptes trimestriels sur IS N-1 si >3000€, puis
régularisation). **0/6400 runs simulés montrent un conflit de trésorerie
entre le solde d'IS et un rachat de compte cassé**, même sous stress
(3 casses corrélées ajoutées artificiellement au moment du solde). Le
mécanisme protège structurellement : l'IS d'une année n'est facturé qu'après
que le profit qui le génère a déjà alimenté la réserve pendant toute l'année.

**Structure holding testée (mère-fille) : aucun bénéfice fiscal, jamais.**
Friction supplémentaire de +0,8-0,9% (capitalisation) ou +0,6-0,9 point
(distribution) vs rester en SASU unique — le régime mère-fille AJOUTE
toujours une couche de taxation (quote-part 5% × IS réel, jamais 1,5%
forfaitaire) là où il n'y en avait pas. Une holding future ne se justifierait
que pour des raisons non-fiscales (séparation patrimoniale, structuration
pour l'associé futur).

### 0.4 — Plafond progressif (1000$→3000$ via réserve du projet) : piste rejetée

Point ouvert #2 (budget réel 1000€ vs optimum statistique 3000$) explicitement
testé et **fermé négativement**. Faire monter le plafond personnel
progressivement (1000$→2000$→3000$) au fil de la croissance de la réserve du
projet ne capture que **~0-3% du gap de profit** (1000$ fixe vs 3000$ fixe)
tant qu'on refuse tout risque de dépassement du budget réel ; même le seuil
le plus agressif testé (1,5x) ne capture que ~18% du gap, avec ~10-12% de
risque réel de dépasser 1000€ (d'environ 1700$ en moyenne). **Aucun seuil
testé n'élimine ce risque à 0% strict.** Le coût réel de démarrer à 1000$ au
lieu de 3000$ (-27,7% de profit final) reste donc presque entièrement à
encaisser.

### 0.5 — Stabilité temporelle du signal : confirmée, P10 bayésien confirmé rigoureux

- **Winrate** : pas de dérive significative (1ère moitié 39,01% vs 2e moitié
  41,18%, test de proportion p=0,574).
- **EV** : dérive significative mais dans le bon sens (+0,43R→+1,52R,
  Mann-Whitney p=0,0011) — amélioration, pas dégradation.
- **Rupture de régime (CUSUM)** : marginalement significative (p=0,044,
  test de permutation), localisée aux ~9 premiers mois du signal (juil 2022-
  mai 2023) — période nettement plus faible (26,45% winrate/-0,235R) que le
  reste (43,24%/+1,249R depuis). À nuancer : point de rupture choisi par le
  test lui-même (effet de double-dipping), pas sur-interpréter, mais
  suggère que le winrate/EV moyen du projet est probablement **conservateur**
  (dilué par une période de rodage), pas optimiste.
- **P10=37,66% confirmé rigoureux** : posterior Beta(260,388) exact
  recalculé = 37,6631% (écart négligeable). Ce n'était PAS une approximation
  grossière.
- **Propager l'incertitude du winrate** (tirage par run dans le posterior
  plutôt que 2 points fixes) élargit l'intervalle P95-P5 de ~7-10%, mais ne
  change QUASIMENT PAS les métriques de risque déjà établies (cash pire cas,
  P(année1<0)) — et donne un profit moyen plus élevé que la méthode 2-points
  (qui sur-pondérait implicitement le scénario pessimiste à 50% au lieu de
  ~10%).

### 0.6 — Frictions d'exécution réelles : données quasi inexistantes, bot jamais tradé en argent réel

`trades_reels.csv` est **vide** (0 ligne) — le bot n'a jamais exécuté de
trade réel. Latence/spread/signaux ratés par incident technique : **non
mesurables** faute de logs (aucun horodatage de signal journalisé à côté de
l'exécution MT5, aucun log de rejet de signal). Ce qui EST mesurable :
- Slippage (proxy Dukascopy déjà existant) : -0,91 pip moyen, EV
  +0,907R→+0,850R.
- Latence architecturale (polling IMAP 60s, mouvement de marché réel mesuré
  via ticks Dukascopy à +30s/+60s) : impact moyen quasi nul (+0,001-0,0015R).
- Signaux bloqués par la règle de corrélation (0,6+JPY) : coût réel ~150-159R
  sur 15,6% du flux (101/646 signaux), **0% de récupération par un autre
  compte de la flotte** — les 9 comptes se comportent comme des clones
  parfaitement synchronisés (mêmes décisions d'éligibilité au même instant).
- **EV réel estimé** (base +0,971R - slippage -0,057R + latence ~0) ≈
  **+0,914R**, reste confortablement dans l'IC95% déjà établi
  [+0,752R,+1,200R] — **aucun ajustement des paramètres Monte Carlo
  justifié** sur cette base.

### 0.7 — Écart code live non appliqué (rappel renforcé)

`app.py`/`app_mt5.py` n'ont JAMAIS été mis à jour pour refléter : RR≥1,25 (a
`MIN_RR=1.5`), trailing 0,15×SL (a 0,2×SL), rampe de risque 2,0%×5→2,5%, ET
maintenant **la nouvelle découverte risque-évaluation 2,0% pendant toute la
phase challenge** (section 0.1). Décision explicite à prendre avant tout
lancement réel — argent réel en jeu, rien n'a été appliqué automatiquement.

---

## 1. Fichiers de référence produits cette session (par ordre logique)

**Split/fiscalité** :
- `split_tax_model.py` — split + calendrier IS SASU, référence pour tout
  calcul net-de-split/fiscalité désormais
- `year1_solde_stress_and_holding.py` — stress-test année 1 + holding
  mère-fille (rejeté, section 0.3)

**Plafond progressif** :
- `progressive_ceiling.py` — piste rejetée (section 0.4)

**Stabilité du signal** :
- `signal_stability_bayesian.py` — stabilité temporelle + posterior bayésien
  rigoureux
- `winrate_uncertainty_propagation.py` — propagation de l'incertitude
  paramétrique dans le Monte Carlo

**Risque de ruine (la partie la plus dense — dans l'ordre des découvertes)** :
- `p5_negative_diagnosis.py` — découverte du P5 négatif + confirmation
  plafond=cause racine (plafond illimité → 0% ruine)
- `ramp_tightening_and_collapse.py` — décomposition catégorie 1 (échec
  Blueberry) vs catégorie 2 (effondrement post-activation) : **catégorie 2
  domine à 87-100%**
- `staggered_ramp_test.py`, `full_cascade_test.py` — réserve minimale avant
  déblocage groupé (**meilleur levier simple**) + cascade multi-étapes
  (dominée, même corrigée avec seuil par étape dans `cascade_reserve_
  per_step.py`)
- `structural_mechanisms_test.py` — capital d'amorçage (B, léger +),
  rachat priorisé (D, inutile), cooldown après cluster (E, **nuisible, à
  écarter**)
- `reserve_threshold_sweep.py`, `attrition_reduction_levers.py` — balayage
  17,5k-150k$ (**plateau total confirmé au-delà de 30k$**), décomposition
  casses éval/post-financement (~51,5%/48,5%), et surtout **risque réduit en
  évaluation = meilleur levier trouvé** (section 0.1)
- `signal_stability_cluster_diagnosis.py` — vérification directe : 0,0% de
  casses groupées sur le même signal, mécanisme = attrition indépendante

**Frictions d'exécution** :
- `missed_signals_replay.py`, `correlation_fleet_replay.py` — coût
  d'opportunité de la règle de corrélation (1 compte vs flotte complète,
  résultat quasi identique — synchronisation totale)
- `latency_window_impact.py` — latence architecturale

---

## 2. Config stratégie et séquence de lancement — INCHANGÉES depuis v3

RR≥1,25 / trailing 0,15×SL / rampe 2,0%×5→2,5% (**sauf pendant l'évaluation
des comptes ouverts au déblocage groupé, cf. 0.1 — nouveau**) / maxpos=3/
corr=0,6+JPY. Blueberry seul (25k) day0, reste de la flotte groupé au 1er
financement **MAIS désormais avec seuil de réserve 30 000$ avant déblocage**
(nouveau, section 0.1). Winrate réel 40,09%, P10 bayésien 37,66% (confirmé
rigoureux).

## 3. Points ouverts, par priorité (mis à jour)

1. **[NOUVEAU, PRIORITÉ HAUTE] Appliquer ou non les découvertes de cette
   session au code live** (`app.py`/`app_mt5.py`) — risque de réserve 30k$
   avant déblocage groupé, capital d'amorçage 300$, risque réduit 2,0% en
   évaluation. Aucune de ces découvertes n'a été appliquée au code réel.
2. Split prop firm + fiscalité : maintenant modélisés (section 0.2-0.3),
   mais barème de split par firm/palier toujours approximatif — à confirmer.
3. Budget réel 1000€ vs optimum 3000$ : piste "montée progressive" fermée
   négativement (section 0.4) — reste un arbitrage à trancher humainement,
   pas une question technique en attente.
4. Combinaison risque-éval réduit + risque-flotte réduit : non testée,
   pourrait encore gagner quelques points de ruine à un coût de profit
   modéré.
5. Frictions d'exécution réelles (spread, latence réelle, incidents
   techniques) : non mesurables tant que `trade_logger.log_trade_execution`
   n'est pas réellement appelé en prod et qu'`account_router.py` ne
   journalise pas les signaux rejetés.
6. Points mineurs hérités de v3 (FundedNext copytrade, plafond Ment Funding,
   swap) : inchangés, toujours en attente de réponse support externe.
