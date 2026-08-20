# Handoff — session du 18-19/08/2026 (soirée, 5 chantiers enchaînés)

Lire en premier :
- Ce fichier — chronologie complète de cette session (la plus longue du
  projet à ce jour, ~40 scripts créés, 5 prompts utilisateur enchaînés).
- `registre_parametres_projet.md` §9 (nouveau) — points 1-5 du premier
  chantier (bug double-comptage indices, diagnostic DD post-objectif,
  staggered unlock reconfirmé, pivot Instant 5k/10k, plafond capital).
- `registre_strategie_trading.md` §2.48+ (nouveaux) — maturation complète
  de Stratégie B (trailing 0,10×, diagnostic corrélation n=31, Force/JPY/
  rr_tp2/structurel, Monte Carlo fleet des leviers B).

## Contexte de départ

Session ouverte pour clore 5 points en attente d'une session précédente
(double-comptage indices, DD inutile post-objectif, staggered unlock,
pivot Instant réduit, plafond capital), puis pivotée vers un chantier de
fond : faire grandir Stratégie B (n=460→571 avec indices, "frequency-
starved" mais jamais recalibrée spécifiquement) pour permettre un
lancement A+B en parallèle.

## Chronologie complète (dans l'ordre)

### Partie 1 — 5 points en attente (chantier initial)

1. **Bug double-comptage tout-indices→B** — vérifié : le bug (trouvé et
   corrigé en interne le 08/18 avant tout résultat publié) n'a PAS
   contaminé les chiffres EV déjà cités (+0,934R/+0,648R, tables A 631→742/
   B 401→460) — confirmé par timestamps fichiers ET recalcul direct.
   **Confirmation n=600 + stress-test du routage tout-indices→B** :
   dominance +41,33% à +44,07% profit (vs +42,8-46,2% en n=300, cohérent),
   nuance nouvelle : hit_ceiling se dégrade légèrement à 960$/1000$
   (+0,3-0,5pt, absent du n=300). Toujours régime-dépendant (H1/bloc0/
   bloc1 inversés, connu).
2. **DD inutile post-objectif de phase** — confirmé par citation exacte
   (`engine_multiformat.py:375-388`) : le moteur continue à trader au
   risque plein après cible atteinte tant que `min_days` (jours DISTINCTS
   avec trade, pas calendaires) n'est pas satisfait. Quantifié n=600 :
   261 498 trades concernés, effet net **+0,43 à +0,49% profit** si
   mitigé (risque quasi nul pendant la fenêtre), amélioration modeste mais
   consistante. **Pas stress-testé** (effet trop petit pour être suspect,
   mais pas fait par manque de temps — à faire avant adoption formelle).
3. **Staggered unlock re-testé sous pile actuelle** — découverte : ce
   n'est PAS un candidat à tester, c'est DÉJÀ le comportement par défaut
   de `ei.seq_grouped_multi(1000,15000,25000,25000)` utilisé partout.
   Reconfirmé n=600+stress-test vs comparateur "groupé" historique
   (seuil unique 30000$) : +5,73% à +7,51% profit, -9,50 à -16,33pt
   année1<0, cohérent avec l'historique 08/08 (+7,2/+7,8%). Rien à
   changer, valeur ajoutée reconfirmée.
4. **Pivot Instant 5k$/10k$ clarifié n=600** — InstantElite5k ≈ nul voire
   légèrement négatif vs Prime25k à 3000$/5000$ (bruit), InstantElite10k
   positif (+1,21%/+1,84%) mais avec un coût structurel NOUVEAU détecté au
   n=600 (solde_neg/hit_ceiling 0,00%→0,17%, absent du n=300 original).
   InstantElite25k (REF) reste strictement optimal à ces plafonds.
5. **Balayage plafond capital 10k$-200k$** — résultat net : profit
   IDENTIQUE au dollar près sur toute la plage (n=300, 0 variance,
   hit_ceiling=0% partout) — le vrai plateau est déjà atteint avant 10k$
   (cohérent avec le point ouvert 2000-2500$ de la session 08/17). Pas de
   n=600 nécessaire (pas d'ambiguïté statistique à trancher).

### Partie 2 — Chantier B, maturation complète (4 sous-chantiers enchaînés)

**Sous-chantier "leviers transposés + risque"** :
- Trailing post-TP2 : sweep 0,10/0,15/0,20/0,25×SL sur B (571 trades) —
  **0,10× domine en EV statique** (+0,89% vs 0,15× actuel), monotone sur
  toute la plage testée. Bug corrigé en route (filtre `rr_tp1>=1.0` trop
  strict, artefact flottant, corrigé pour matcher la méthode officielle).
- Risque par trade recalibré pour B — **DIFFÉRÉ sur demande utilisateur**,
  nécessite un moteur A+B parallèle (2 flux signaux + réserve partagée)
  jamais construit — pas fait cette session, architecture à concevoir.
- Paires exotiques RR≥1,00 — **prémisse infirmée** : aucune paire exotique
  n'existe dans les données scrapées (whitelist scraper = majeures+
  croisées+métaux uniquement, jamais d'exotiques ciblées).
- Diagnostic corrélation B — n=16→**n=31** avec la population élargie,
  delta EV +0,668R→**+0,9861R**, IC95% bootstrap [+0,81;+2,68], stress-test
  4/6.

**Sous-chantier "amélioration EV/winrate B (statistique seule)"** :
- Chantier 1 — slippage sur trailing 0,10×/0,15× : gain de 0,10× **robuste**
  au slippage testé jusqu'à 5 pips (delta constant +0,0398R, décalage
  parallèle mathématique).
- Chantier 2 — diagnostic corrélation avec matrice 19×19 : confirmé n=31
  (repris ci-dessus).
- Chantier 3 — segmentation 4 variables (session/asset_class/distance_SL%/
  ADX) : **ADX>32,27 = signal net, stress-testé 6/6, propre**. session et
  asset_class = bruit/non-discriminant. distance_SL% signalé en coupe
  simple mais **non stable en stress-test** (rejeté, contrairement à A où
  cette variable était le candidat stable).

**Sous-chantier "leviers de A transposés + caractérisation structurelle"** :
- Chantier A — Force sur indices B : pas de signal (p=0,104, non
  significatif, stress-test sans cohérence).
- Chantier B — règle JPY-JPY : tient sur B (1,32% DD flottant combiné,
  même ordre que A), indices jamais concernés (aucun label JPY),
  corrélation JPY↔indices max 0,156 (loin du seuil 0,80).
- Chantier C — mécanisme rr_tp2 : corrélation rr_tp2↔distance_TP2%
  comparable à A (ratio 0,76), mécanisme pas structurellement cassé, mais
  stress-test échoue systématiquement dans les mêmes sous-périodes à
  faible n (H1/bloc0/bloc1) quel que soit le seuil — pas assez de données
  pour trancher, PAS un rejet définitif.
- Chantier D — corrélation + shrinkage bayésien : signal survit même à
  k=50 (shrinkage agressif), delta shrunk +0,43R minimum.
- **Chantier E (le plus structurant)** — caractérisation complète A vs B,
  8 axes : découverte clé = **B a une géométrie de trade différente de A**
  (stop plus large +18%, TP1 plus proche -32% en médiane), pas juste "A
  avec un seuil RR plus bas". 3 hypothèses formulées.

**Sous-chantier "fiche d'identité 31 trades + hypothèses E"** :
- Fiche complète des 31 trades bloqués-corrélation : **dominé à ~26% par
  le seul couple NASDAQ100-MINI/S&P500-MINI** (corrélation 0,954).
  Catégorisation : A=16 (RR bloqué>occupant), B=15, C=0 (aucun conflit
  multiple). **Trace dynamique du swap any-RR** : 15 swaps réels au total
  (pas 3 comme le comptage net le suggérait), dont 8 à gain nul et 2
  négatifs — explique pourquoi any-RR capture si peu (+0,01R) malgré un
  signal statistique fort.
- 2 mécanismes proposés (marge RR minimale, priorité ciblée NASDAQ100/
  S&P500) — les deux signalés fragiles, à k-fold avant tout usage.
- Décomposition forex/indices : trailing 0,10× et ADX>32,27 tiennent
  indépendamment des deux côtés (pas un artefact de composition).
- Test des 3 hypothèses structurelles (Chantier E) : **rr_tp1≤1,25
  prometteur (5/6 stress-test)**, sizing distance_SL% rejeté (et sa
  prémisse structurelle invalidée : le moteur normalise déjà le risque $
  indépendamment de la distance SL), timeout traîne longue **rejeté
  nettement** (aucune corrélation durée↔R, effet inverse à l'hypothèse dû
  à un artefact de confusion temporelle).

**Sous-chantier final — k-fold + Monte Carlo fleet** :
- Marge RR minimale (piste 1.1) : **PAS MÛR** — amélioration statique
  réelle (+3,93R→+6,42R à marge=1,20) mais seulement 2-8 événements par
  sous-période de stress-test, non tranchable.
- Segmentation rr_tp1≤1,25 (piste 1.2) : **MÛR** — 5/6 stress-test,
  échantillons solides (n=51-182/sous-période), seuil voisin 1,20/1,30
  nettement moins stables (3/6 chacun) donc 1,25 n'est pas arbitraire.
  Mécanisme retenu : sizing ×0,7 (pas exclusion, B reste positif sur ce
  segment et est déjà frequency-starved).
- **Monte Carlo fleet n=300 puis n=600** (4 leviers : trailing 0,10×,
  ADX>32,27, rr_tp1-sizing ×0,7 ; marge RR exclue car pas mûre) :
  - **Trailing 0,10× : DOMINANCE STRICTE CONFIRMÉE n=600**, 4 axes, 4
    plafonds, +2,20% à +2,65% profit, sans exception.
  - **ADX>32,27 : REJETÉ au niveau fleet** malgré signal statistique
    propre (6/6 stress-test) — coûte -5% à -7% de profit en flotte réelle
    (exclut 9,6% du volume, B est frequency-starved, la perte de
    fréquence coûte plus que le gain de qualité). **Résultat le plus
    important méthodologiquement de la session** : confirme qu'un signal
    statistique confirmé n'implique PAS une confirmation fleet.
  - **rr_tp1-sizing ×0,7 : REJETÉ au niveau fleet** — coût profit sévère
    (-14% à -16%).
  - Pas de cascade (un seul levier validé sur les 4 testés, il en faut
    ≥2).

## Décisions bloquantes qui restent ouvertes

1. **RIEN n'a été consigné dans les registres avant la toute fin de cette
   session** — écriture faite en clôture (voir §9/§2.48+), à vérifier
   que tout y est bien passé avant de faire confiance à une relecture
   future sans revenir à ce fichier.
2. **Trailing 0,10× sur B** : validé n=600 isolément, mais **jamais
   combiné avec le reste de la pile REF actuelle en configuration finale**
   — l'adoption officielle (comme pour §1.8) reste une décision utilisateur
   séparée, jamais tranchée dans ce projet par principe.
3. **Diagnostic corrélation B (n=31)** : signal solide, **aucun mécanisme
   actionnable trouvé qui capture une part significative** du gisement
   +0,99R (any-RR simple = quasi nul, marge RR = pas mûr, priorité ciblée
   NASDAQ100/S&P500 = fragile, pas testé en Monte Carlo). Piste ouverte,
   pas fermée.
4. **Risque par trade recalibré pour B** : jamais fait, nécessite un
   moteur de simulation A+B parallèle (2 comptes, réserve partagée) qui
   n'existe pas dans le code actuel — chantier d'ingénierie à part entière,
   différé sur demande utilisateur, pas de date de reprise fixée.
5. **rr_tp2 sur B (mécanisme, pas seuil)** : ni confirmé ni rejeté
   définitivement — corrélation comparable à A mais échantillon
   insuffisant en sous-période pour trancher. Rouvrir si le volume de
   données de B augmente.
6. **3 hypothèses structurelles du Chantier E** : géométrie SL-large/TP1-
   proche de B jamais exploitée (aucun mécanisme concret proposé pour
   ça spécifiquement, seulement diagnostiquée) — piste réellement neuve,
   jamais transposée de A, à explorer plus avant.
7. **Bug DJ30** (rr_tp1=NaN) : toujours signalé, toujours pas corrigé,
   mentionné depuis plusieurs sessions.
8. **Diagnostic "1-3% risque d'échec parsing/exécution"** (§2.39
   ancien) : toujours pas retrouvé, toujours pas résolu.

## Fichiers clés créés cette session (tous à vérifier suivis par git)

Chantiers 1-5 (points en attente) : `chantier_p2_dd_post_objectif_2026-08-19.py`,
`chantier_p3_staggered_retest_2026-08-19.py`,
`chantier_p3_staggered_stresstest_2026-08-19.py`,
`chantier_p4_pivot_n600_2026-08-19.py`,
`chantier_p5_capital_ceiling_sweep_2026-08-19.py`.

Chantier B (trailing/risque/exotiques/corrélation) :
`chantier_b1_trailing_sweep_2026-08-19.py`.

Chantier B-EV (amélioration statistique) :
`chantier_b_ev1_slippage_trailing_2026-08-19.py`,
`chantier_b_ev2_correlation_diag_2026-08-19.py`,
`chantier_b_ev3_segmentation_2026-08-19.py`.

Chantier B4 (leviers A transposés + structurel) :
`chantier_b4_a_force_indices_2026-08-19.py`,
`chantier_b4_b_jpy_rule_2026-08-19.py`,
`chantier_b4_c_rrtp2_diagnostic_2026-08-19.py`,
`chantier_b4_e_caracterisation_2026-08-19.py`.

Chantier B5 (fiche d'identité + décomposition + hypothèses) :
`chantier_b5_1_fiche_identite_2026-08-19.py`,
`chantier_b5_swap_trace_2026-08-19.py`,
`chantier_b5_5_decomposition_2026-08-19.py`,
`chantier_b5_6_hypotheses_e_2026-08-19.py`.

Chantier B6 (k-fold + Monte Carlo fleet final) :
`chantier_b6_1_swap_margin_2026-08-19.py`,
`chantier_b6_2_rrtp1_threshold_2026-08-19.py`,
`chantier_b6_montecarlo_2026-08-19.py` (moteur fleet complet, 4 leviers,
copie figée de `chantier_strategie_b_isolation_indices_2026-08-18.py` avec
size_func recevant le trade entier + population variant configurable).

## Note de méthode (rappel)

Cette session a validé deux fois de suite le principe "statistique propre
≠ fleet-confirmé" (ADX et rr_tp1-sizing, tous deux signaux statistiques
stress-testés mais rejetés en flotte réelle) — leçon méthodologique la
plus importante de la session, à appliquer systématiquement avant toute
adoption future d'un levier B. Un bug de filtre flottant (`rr_tp1>=1.0`)
a aussi été trouvé et corrigé en route — troisième bug de ce type trouvé
dans ce projet (après le forex-only et le double-comptage indices),
confirme la valeur du réflexe "citer le code plutôt que supposer".
