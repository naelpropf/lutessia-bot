# Handoff — session du 18/08/2026

Lire en premier :
- Ce fichier — chronologie complète de cette session.
- `registre_parametres_projet.md` §1.8bis (nouveau) — correction risque
  Instant régénérée n=600, correction filtre forex-only et impact sur A.
- `registre_strategie_trading.md` §2.45-2.47 (nouveaux) — risque Instant
  détaillé, bug filtre forex-only, routage indices vers B.

## Chronologie complète de la session (dans l'ordre)

1. **Correction du risque Blueberry Instant** — découverte (confirmée
   depuis le site Blueberry lui-même via capture d'écran utilisateur,
   "Max Risk/Trade Idea : 1,5% (Funded)") : Instant Elite/Lite ne
   bénéficient PAS de l'exemption Prime sur le risque par trade, ils sont
   plafonnés à 1,5%/trade sur la taille INITIALE (fixe), pas le risque
   flotte standard (1,90%). Le moteur appliquait 1,90% à tort. **Corrigé,
   confirmé n=600+stress-test H1/H2+4blocs, §1.8 régénéré et remplace
   définitivement les anciens chiffres** (`registre_parametres_projet.md`
   §1.8bis, `registre_strategie_trading.md` §2.45). Dominance stricte
   §1.8 SURVIT à la correction, mais ~33-37% du gain de profit annoncé
   par l'ancien tableau (non corrigé) s'évapore.

2. **Pivot Instant à taille réduite** (5k$/10k$ au lieu de 25k$, coût
   200$/400$ au lieu de 800$) — à 3000$/5000$ (plafond réel), 25k$ reste
   strictement optimal, les tailles réduites n'apportent RIEN. Utile
   seulement aux plafonds serrés (960$/1000$), et même là ne renverse pas
   le rejet historique "Blueberry-adaptatif" de 08/09
   (`registre_strategie_trading.md` §2.45bis).

3. **Piste multi-comptes Instant via copytrade** (diversifier le pivot en
   plusieurs comptes plus petits) — analysée sans simulation : le
   copytrade synchronise les comptes sur les mêmes signaux, donc pas de
   vraie diversification statistique (comptes identiques = corrélation
   parfaite), juste un surcoût. Décalage de timing entre comptes analysé
   mécaniquement : ne fonctionne PAS pour Instant Elite spécifiquement
   (`engine_multiformat.py:145`, `dd_daily_pct=None` — aucune limite
   journalière modélisée, la casse dépend uniquement du cumulatif
   trailing, qu'un décalage de quelques heures ne change pas). Piste
   fermée par analyse, pas testée en simulation (pas nécessaire).

4. **Chantier "amélioration Stratégie B"** (bande RR 1,00-1,35,
   contrarian) — plusieurs sous-chantiers :
   - Baseline B chiffrée : n=401, winrate 49,6% (meilleur que A 39,5%),
     EV +0,80R (moins bon que A +0,89R), fréquence 63,4% de A.
   - rr_tp2 sur B : **REJETÉ**, ne passe pas le stress-test H1/H2+4blocs
     (inversion en H1 entier, pas juste un bloc bruité).
   - Diagnostic "bloqué par corrélation" sur B : signal existant (+0,668R
     bloqués vs admis, même sens que sur A) mais n=16 fragile, 3 trades
     expliquent l'essentiel. Élargi à RR≥0,50 : **aucun effet** — le
     plancher réel de rr_tp1 sur TOUTE la population Lutessia est
     exactement 1,00, rien en dessous. Statut : en attente de plus de
     données, pas fermé.
   - **🔴 Découverte majeure : bug filtre forex-only.**
     `build_extended_population()` (`rr_threshold_test.py:47`, fonction
     fondatrice de TOUTE population du projet) excluait silencieusement
     tout ticker non-forex, indépendamment de tout critère RR — jamais un
     choix méthodologique documenté. **321 trades indices scrapés avec
     succès (DAX40/S&P500/NASDAQ100/DJ30) étaient jetés avant toute
     simulation.** DJ30 (53 lignes) en plus structurellement inutilisable
     (rr_tp1=NaN, bug de parsing distinct, non corrigé).
   - **Correctif appliqué dans le code** (`rr_threshold_test.py:43-61`) —
     remplace le filtre forex par un critère de mappabilité réelle.
     Impact mesuré : **A 631→742 trades (+17,6%)**, EV quasi inchangée
     (+0,7% relatif) ; **B 401→460 trades (+14,7%)**, EV quasi inchangée.
     Stress-test H1/H2+4blocs sur A élargi : propre, aucune inversion
     imputable aux indices.
   - **Faisabilité d'exécution live des indices : NON.** Deux blocages
     confirmés par citation de code dans `app.py` : (1) whitelist
     d'entrée du parsing live n'utilise QUE `TARGET_FOREX_TICKERS`
     (`app.py:225`, pas `_is_target_asset` qui inclut pourtant les
     indices côté scraper d'archives) ; (2) `mt5_symbol = ticker.replace
     ("/", "")` (`app.py:479`) produirait un symbole broker invalide pour
     un ticker indice, aucun mapping ticker→symbole broker n'existe côté
     live. Nécessiterait un travail d'ingénierie séparé (whitelist +
     mapping vérifié contre le Market Watch réel du broker).
   - **Matrice de corrélation étendue aux indices** (14×14→19×19,
     `extend_correlation_matrix_indices_2026-08-18.py`, backup de
     l'ancienne conservé). NASDAQ100↔S&P500=+0,954 (au-dessus du seuil
     0,80, any-RR s'applique réellement) ; indices↔forex faible partout.
   - **Routage optimal des indices vers B** : comparaison flotte réelle
     (B isolation, n=300+stress-test) entre "routage naturel par RR"
     (indices RR<1,35 seulement, B→460) et "tout indices→B" (indépendant
     du RR, B→571). **"Tout indices→B" domine nettement** : profit
     +42,8% à +46,2%, année1<0 -14,66 à -15,00pt, à tous les plafonds.
     Stress-test montre un effet régime-dépendant (aggrave marginalement
     dans les périodes où B échoue déjà totalement, aide nettement
     ailleurs) — nuance réelle mais direction globale claire.
     `registre_strategie_trading.md` §2.47.

## Fichiers clés créés cette session (tous suivis par git sauf indication contraire)

Risque Instant : `chantier_bb_instant_risk_cap_correction_2026-08-17.py`,
`chantier_S1_8_stresstest_risque_instant_2026-08-17.py`,
`chantier_S1_8_officiel_n600_risque_corrige_2026-08-17.py`.

Pivot taille réduite : `chantier_pivot_instant_taille_reduite_2026-08-18.py`.

Délai GFT (semaines) : `chantier_pisteB_delayed_start_2026-08-17.py`
(paramètre `gft_delay_days` ajouté en cours de session).

Stratégie B / indices : `chantier_strategie_b_baseline_2026-08-18.py`,
`chantier_strategie_b_correlation_elargi_2026-08-18.py`,
`chantier_strategie_b_gisement_indices_2026-08-18.py`,
`chantier_reference_A_indices_2026-08-18.py`,
`chantier_strategie_b_correction_bug_2026-08-18.py`,
`extend_correlation_matrix_indices_2026-08-18.py`,
`chantier_strategie_b_isolation_indices_2026-08-18.py`,
`chantier_strategie_b_isolation_stresstest_2026-08-18.py`.

**Fichiers de code partagé MODIFIÉS** (pas des chantiers isolés — affectent
tout le projet) :
- `rr_threshold_test.py:43-61` — filtre forex-only remplacé par critère
  de mappabilité réelle (forex + 3 indices).
- `correlation_matrix.csv` — étendue 14×14→19×19 (backup dans
  `correlation_matrix_forex_only_backup_2026-08-18.csv`).

## Décisions bloquantes qui restent ouvertes

1. **Adoption officielle de §1.8 dans son ensemble** — toujours en
   attente, statut inchangé par cette session (technique prête depuis
   longtemps, décision utilisateur finale jamais prise).
2. **§1.8/§2.35 PAS régénérés en flotte complète avec la population
   élargie (742 trades)** — seulement mesuré en EV isolé + stress-test à
   ce stade. Si le plancher de fondation (population) est adopté, une
   régénération n=600+cascade de §1.8/§2.35 avec 742 trades serait la
   suite logique.
3. **Routage "tout indices→B"** — direction claire (n=300+stress-test)
   mais pas de n=600, ET pas déployable tant que l'exécution live n'est
   pas construite (point 4).
4. **Faisabilité d'exécution live des indices** — travail d'ingénierie
   non fait (whitelist `app.py` + mapping symbole broker MT5 vérifié
   contre le compte réel). Bloquant pour tout déploiement réel du
   routage indices.
5. **Plafond personnel réel** — toujours recentré sur 2000-2500$ (pas
   3000$), point ouvert depuis la session du 17/08, non retouché ici.
6. **BB+GFT délai (jour0 vs différé)** — fenêtre réelle 1-3 semaines
   conserve 47-78% du gain jour0 (2 mois : 23%, 4 mois : 5%), résultat
   préliminaire n=300 de la session du 17/08, non repris ici.
7. **Diagnostic corrélation sur B** (n=16, Δ=+0,668R) — en attente de
   plus de données, le plancher RR≥1,00 empêche tout élargissement de
   population pour ce diagnostic spécifiquement.
8. **Bug DJ30** (rr_tp1=NaN sur toutes ses lignes, ~53 trades) — signalé,
   jamais investigué ni corrigé.
9. **Bug "1-3% risque d'échec de parsing/exécution"** cité une fois dans
   une session antérieure mais jamais retrouvé dans le registre (signalé
   §2.39, pas résolu).

## Note de méthode (rappel)

Deux bugs de fondation trouvés et corrigés cette session (risque Instant,
filtre forex-only) — tous deux des erreurs de prémisse jamais documentées
comme choix méthodologique, découvertes en creusant une question
utilisateur précise plutôt qu'en cherchant activement des bugs. Le
principe "citer le code plutôt que supposer" a payé deux fois de suite.
Un bug de double-comptage supplémentaire (population B dupliquant les
indices RR<1,35) a été trouvé et corrigé EN COURS de la même session, via
un test de fumée systématique avant tout run n=300/600 — réflexe à garder.
