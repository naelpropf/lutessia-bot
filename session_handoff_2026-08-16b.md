# Handoff — session du 16/08 (2e partie, après clear de la session `session_handoff_2026-08-16.md`)

Lire en premier :
- Ce fichier — chronologie complète de cette session.
- `registre_strategie_trading.md` §2.32-2.35 (échange par corrélation, any-RR,
  sizing rr_tp1 rejeté, sizing rr_tp2 adopté).
- `registre_parametres_projet.md` §1.8 (proposition cascade groupée) et §7.1
  (vérifications post-intégration).

## Chronologie complète de la session (dans l'ordre)

1. **Cascade groupée Blueberry Instant + any-RR** (intégration de §2.33 et
   §7.1 dans une seule référence proposée, §1.8) : n=600 aux 4 plafonds
   (960$/1000$/3000$/5000$), dominance stricte confirmée partout, effet
   légèrement super-additif (+0,4 à +0,9pt vs somme naïve des effets isolés)
   — pas de cannibalisation. **PROPOSÉ en §1.8, pas encore adopté
   officiellement** (décision utilisateur finale en attente malgré toutes
   les vérifications techniques passées).

2. **Vérification anomalie 1** (convergence exacte $ entre 3000$/5000$ sur
   la ligne COMBINÉ) : confirmée non-bug par citation de code
   (`bb_choose_fmt_key` ne dépend jamais de `ceiling`, `hit_ceiling_pct`=
   0,00% aux deux plafonds donc la branche qui utilise `ceiling` n'est
   jamais atteinte). `bb_threshold` est réellement identique (0,0) entre
   3000$/5000$ par choix de conception, pas un bug.

3. **Vérification anomalie 2** (seuil de bascule Blueberry extrapolé à
   1000$/3000$, pas calibré) : calibration dédiée n=300 avec any-RR actif
   — **extrapolation validée par mesure directe** (bb=5000 domine à 1000$,
   bb=0 domine à 3000$, exactement les seuils déjà utilisés). Aucun
   changement à §1.8.

4. **Décomposition du plancher de variance pure** (Run E) sous l'edge
   actuel : ancien plancher 08/11 = 24,67% (sans any-RR, sans BB Instant).
   Nouveau plancher edge pur (+any-RR, sans BB Instant) = **24,67%
   inchangé** (le 22,67% mesuré à n=300 était du bruit, corrigé à n=600).
   Vrai plancher (+any-RR +BB Instant, cash illimité) = **12,33%**. Combiné
   réel (+trésorerie réelle) = **13,83%**, bien ≥ le vrai plancher (+1,50pt
   cohérent). L'anomalie initiale (combiné < ancien plancher) venait d'un
   plancher mal spécifié (BB Instant élimine aussi le risque de phase
   d'évaluation, pas seulement la friction cash) — résolue.

5. **Sizing par RR planifié (rr_tp1), global** (§2.34) — **REJETÉ**. 3
   fonctions (linéaire/palier/quantile, ×1,30 max) toutes pires que la
   référence combinée sur les 4 axes à 960$/1000$, profit pire à 3000$/
   5000$. Mécanisme : RR planifié quasi non-corrélé à l'EV réalisée
   (Pearson=0,006) et légèrement anti-corrélé au winrate (-0,108) — any-RR
   marche par sélection au moment d'un conflit, pas par pouvoir prédictif
   intrinsèque du RR.

6. **Sizing ciblé sur rr_tp2 (queue haute)** (§2.35) — **ADOPTÉ**, chantier
   le plus abouti de la session. Correction méthodologique : rr_tp1 est
   plafonné à 3,0 par construction (mauvaise variable pour un effet de
   queue) ; rr_tp2 ne l'est pas (distribution 1,74-30,4). Étape 0
   anti-lookahead vérifiée (`scraper.py:239-246`, tp2_init scrapé au même
   instant que tp1_init/prix_entree/stop_loss_init, pas dérivé après coup).
   Seuil rr_tp2>8 (n=96) est le seul à sortir de l'IC95% bootstrap de l'EV
   globale, stable sur 6/6 sous-périodes indépendantes (H1/H2 + 4 blocs
   k-fold, Pearson toujours positif). Variante B (routage ET sizing sur
   rr_tp2, ×1,6) confirmée n=600 : **dominance stricte à 3000$/5000$
   (+15,9% vs combiné)**, **arbitrage à 960$/1000$ (+15,7% profit mais
   hit_ceiling qui double, année1<0 inchangé une fois le bruit n=300
   corrigé)**. Vérifications finales (chevauchement avec any-RR=10,4% très
   faible, chevauchement avec classement de paires rejeté=35,4% sans
   conséquence, mécanisme du rebond de winrate = cible TP2 réellement plus
   loin, pas un artefact) toutes passées. **Adopté sans réserve.**

7. **Section F (cumul de comptes GFT Instant parallèles)** — demandée puis
   **explicitement retirée** par l'utilisateur ("on s'est mal compris, je
   te redonne le bon prompt" — le prompt corrigé ne contenait que la
   correction rr_tp2). **PAS FAITE**, reste à engager si l'utilisateur le
   souhaite. Faisabilité déjà vérifiée : `N_ACCOUNTS_DAY0['GFT']`
   surchargeable proprement, mécanisme de coût cumulé déjà géré nativement
   par `open_group`/`handle_cost_hybrid`.

## Fichiers clés créés cette session (tous suivis par git)

- `chantier_cascade_combined_bb_switch_any_rr_2026-08-16.py` — moteur
  combiné (Blueberry Instant + any-RR), avec correctif Run F (BB 7j+20%
  à 3000$ uniquement) intégré en cours de route.
- `chantier_cascade_combined_decomposition_2026-08-16.py` — décomposition
  bb_only/rr_only pour vérifier l'additivité.
- `chantier_cascade_combined_bb_threshold_calibration_2026-08-16.py` —
  calibration dédiée du seuil à 1000$/3000$.
- `chantier_run_e_equivalent_anyrr_2026-08-16.py` /
  `chantier_run_e_equivalent_anyrr_bbinstant_2026-08-16.py` — plancher de
  variance pure, avec et sans Blueberry Instant.
- `chantier_rr_sizing_2026-08-16.py` — sizing rr_tp1 global (REJETÉ, §2.34).
- `chantier_rrtp2_sizing_2026-08-16.py` — sizing/routage rr_tp2 (ADOPTÉ,
  §2.35), variantes A et B, sweep de multiplicateurs.
- `chantier_rrtp2_stability_verification_2026-08-16.py` — vérification
  finale (table complète + stress-test de stabilité H1/H2+k-fold).

## Décisions bloquantes qui restent ouvertes

1. **Adoption OFFICIELLE de §1.8** (cascade groupée any-RR + Blueberry
   Instant + sizing rr_tp2) — techniquement prête et entièrement vérifiée
   (toutes les anomalies signalées ont été résolues), mais nécessite une
   confirmation utilisateur explicite pour remplacer la référence 08/12 et
   régénérer les leviers dérivés (comme fait le 08/12 pour RR1,35/
   corr0,80).
2. **Plafond personnel réel** (960$/3000$/5000$, décision #9) — toujours
   ouvert, conditionne le statut différencié de plusieurs leviers
   (bascule Blueberry, sizing rr_tp2 : dominance à 3000$/5000$ mais
   arbitrage à 960$/1000$).
3. Section F (GFT Instant parallèle) — non engagée, à faire si souhaité.
4. Config 1 vs config 4 dual-trader à 3000$ — jamais tranché (ancien
   point, inchangé).

## Note de méthode

Deux leçons de bruit d'échantillonnage n=300 vs n=600 rencontrées CETTE
session (déjà connues du projet mais reconfirmées) : le plancher Run E
(22,67%→24,67% réel) et le gain apparent sur année1<0 du sizing rr_tp2 à
960$/1000$ (22-24%→24,50% réel, essentiellement nul). **Ne jamais citer un
chiffre n=300 comme définitif sur année1<0 sans confirmation n=600.**
