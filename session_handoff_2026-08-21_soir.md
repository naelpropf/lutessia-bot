# Handoff — 21/08/2026 soir — r_trailing fixé au primitif, edge re-testée, métaux scopés, bloc1/bloc2 fleet EN ATTENTE

Session très longue, plusieurs découvertes en cascade. Lire dans l'ordre les
mémoires suivantes avant de continuer (toutes dans le dossier memory) :
1. `project_bloc2_extension_artefact_debunked_2026-08-21` — découverte
   initiale (r_trailing plafonné à tort sur bloc1/bloc2).
2. `project_rtrailing_bug_scope_validated_2026-08-21` — ampleur (touche
   TOUTE simulation flotte du projet via `build_flexible_population`).
3. `project_rtrailing_fixed_edge_retest_2026-08-21` — fix implémenté +
   edge officielle re-testée (p=0,0027 -> p=0,8825, tendance disparue).
4. `project_adx_bloc2_prior_contamination_reclassified_2026-08-21` — le
   chiffre ADX bloc2 (51,33-51,67%->46,33%) est réel mais indirect (prior
   partagé, pas un filtrage direct).
5. `feedback_shared_prior_bloc_contamination_pattern` /
   `feedback_index_alignment_bug_pattern` — 2 leçons méthodologiques
   générales à garder en tête pour tout futur test par bloc.

## État du fix (déjà committé, commit `df261dc`, poussé)

- `tp_sequence_analysis.py` : `fetch_h1_history()` utilise le backfill MT5
  (`data/mt5_h1_backfill/`, 19 tickers forex+indices déjà backfillés,
  couverture 2022-01-02->2026-08-20) en source PRIMAIRE, fallback yfinance
  sinon. `analyze_trade()` : garde-fou PROSPECTIF ajouté
  (`resolution_incertaine_horizon_insuffisant`, `MAX_HORIZON_ABS=30j`) --
  symétrique du garde-fou rétrospectif `hors_couverture_historique` déjà
  existant (documenté de longue date dans `tp2_realistic_payoff.py` comme
  un choix conservateur DÉLIBÉRÉ, pas un bug caché -- le backfill MT5 permet
  juste de résoudre ce qui était documenté comme limitation connue).
- `tp2_realistic_payoff.py` : nouveau cas ajouté à `OUT_OF_COVERAGE_CASES`.
- Tout le reste du pipeline (`build_extended_population`,
  `build_realistic_payoff_population`, `build_population_with_trailing`)
  en hérite automatiquement -- vérifié par exécution réelle.

**3 configs régénérées** (fichiers CSV locaux, gitignorés, à régénérer si
besoin via `chantier_rtrailing_recalc_2026-08-21.py`) :
- `officielle_verrouillee` (rr_tp1>=1,5/`MIN_RR_TP1`, trailing=0,2 -- config
  gelée derrière le p=0,0027 du registre ET utilisée chaque semaine par
  `analyse_live.py` -- vestige pré-scission A/B, aucune intention explicite
  trouvée).
- `A_reelle` (rr_tp1>=1,35/`MIN_RR_NEW`, trailing=0,15, n=631 forex-only --
  le fichier brut régénéré contient 742 lignes forex+indices, filtrer par
  `FOREX_PATTERN` pour retrouver le n=631 cité comme "A réelle").
- `B_reelle` (rr_tp1>=0,75, trailing=0,10 -- superset incluant la bande
  1,25-1,35 qui appartient réellement à B, PAS à A, `MIN_RR_NEW`=1,35 étant
  la frontière de routage).

**Résultat du re-test walk-forward** (`chantier_walkforward_retest_2026-08-
21.py`, méthodologie de `walk_forward_gap_investigation.py` reproduite à
l'identique, population ACTUELLE complète pas l'instantané figé à 472) :
officielle p=0,8825 (était 0,0027), A réelle p=0,3139 -- **la narrative
"l'edge s'améliore dans le temps" ne survit pas à la correction**.

## Métaux (Or/Argent/Palladium/Platinum) -- exposition confirmée, partiellement corrigée

- Même bug (yfinance, cutoff ~730j), 51,0% des 349 gagnants métaux
  antérieurs au cutoff.
- **Backfill MT5 métaux reçu et pullé** (commit `b3e054a`, AVANT le commit
  df261dc de cette session) : `data/mt5_h1_backfill/mt5_h1_backfill_
  {XAUUSD,XAGUSD,XAUGBP,XAUEUR,XAUAUD,XAGAUD,XAGEUR,XPDUSD,XPTUSD}.pi_2026-
  08-21.csv`. XAUUSD/XAGUSD/XPTUSD couvrent depuis 2021-03-31 (complet).
  **XAUGBP/XAUEUR/XAUAUD/XAGAUD/XAGEUR/XPDUSD ne démarrent QUE le
  2023-01-19** chez ce courtier (limite réelle confirmée, pas un bug).
- **Synthèse par taux croisé validée** (`chantier_bloc2_metaux_synthese_
  mt5_2026-08-21.py`, logique de `gold_silver_yahoo_mapping_2026-08-19.py`
  réappliquée avec legs MT5 : XAUUSD.pi/XAGUSD.pi x EURUSD.pi/GBPUSD.pi/
  AUDUSD.pi) : écart moyen 0,012-0,031% sur >13600 points de recouvrement
  par ticker, AUCUN biais systématique -- réduit le trou de GOLD-GBP/EUR/AUD
  et SILVER-AUD/EUR de 2021-04->2023-01 (21 mois) à 2021-04->2022-01
  (~9 mois résiduels, limite de la jambe FX MT5 elle-même).
- **Palladium reste sans solution H1** pour 2021-04->2023-01-19 (~21 mois) :
  confirmé indisponible chez Dukascopy (HTTP 404 sur XPDUSD, testé
  directement), MT5 broker (même limite 2023-01-19), stooq.com (bloqué par
  un mur anti-bot JavaScript sur TOUTE requête, y compris des contrôles
  positifs -- inconclusif, pas une absence confirmée), Yahoo Finance
  (PA=F disponible en DAILY seulement sur toute la fenêtre -- confirme que
  le marché COMEX a bien coté, mais résolution insuffisante pour le
  trailing H1 ; XPDUSD=X n'existe pas chez Yahoo). Piste TradingView
  présentée (export manuel officiel si profondeur de plan suffisante, VS
  extraction automatisée en zone grise de ToS) -- **décision utilisateur en
  attente**, rien tenté.
- Gap Platinum (147j, 2024-02-29->2024-07-26) vérifié : chevauche bloc3,
  **0 trade Platinum de bloc3 affecté** (confirmé, pas un problème réel ici).

**Exposition résiduelle bloc1/bloc2 par ticker** (population B_tradable+pgp,
`chantier_bloc2_metaux_recalc_2026-08-21.csv`) :
- bloc1 : GOLD-AUD 80% non résolu, SILVER-EUR 80%, SILVER-AUD 69%, GOLD-GBP/
  EUR 50%, **PALLADIUM 100% non résolu** (4/4 gagnants). GOLD-USD/SILVER-USD/
  PLATINUM 100% résolus.
- bloc2 : tout résolu à 100% SAUF Palladium (40% non résolu, 4/10).

**EV recalculée (meilleure donnée dispo, garde-fou appliqué sur le reste,
PAS un plafonnement silencieux) par bloc, métaux seuls** :
bloc1 n=159 EV +0,40R->+2,37R ; bloc2 n=151 EV +0,04R->+2,51R ; bloc3 n=165
+1,53R->+2,38R ; bloc4 n=201 +2,61R->+2,73R.

## 🔴 CE QUI N'A PAS ÉTÉ FAIT -- priorité immédiate à la reprise

**Point D non conclu** : recalculer le solde_négatif%/profit moyen FLOTTE
(pas juste l'EV trade-level ci-dessus) pour bloc1/bloc2 sur B_tradable avec
r_trailing corrigé (forex+indices ET métaux combinés), et comparer aux
chiffres déjà cités au registre (`registre_strategie_trading.md` §6.5,
ligne ~2930) : **bloc1 29-40% solde_négatif selon hypothèse de durée (test
de sensibilité `chantier_bloc1_sensibilite_duree_2026-08-19.py`, ×0,5-2,0
sur la durée métaux bloc1) vs A-seule 92% ; bloc2 32-38% vs 60-61%**. Ce
test datait de la population B_tradable Config0 ORIGINALE (n=1051, 08-19),
PAS la pgp (n=1248) -- population source et méthodologie de sensibilité
(`chantier_bloc1_sensibilite_duree_2026-08-19.py`,
`chantier_bloc2_sensibilite_duree_2026-08-19.py`) déjà identifiées, lues en
partie (variable `MEDIAN_DUR`, fonction `build_perturbed_bloc1`), mais le
run flotte réel (via le moteur cascade officiel, `date_subperiods` +
`run_n_sims`) sur données r_trailing corrigées **n'a pas encore été
lancé**. C'est la suite naturelle et la priorité #1 de la prochaine
session.

**Autres points en attente** :
- Décision Palladium (source alternative ou gap accepté).
- Les 5 leviers adoptés (V2, §1.8, §2.35, FTMO-10%/GFT Goat Guard,
  payout/forfeiture -- ce dernier directement concerné par bloc2) restent
  TOUS non re-vérifiés sur données corrigées -- explicitement mis en attente
  jusqu'à ce que bloc1/bloc2/edge soient tranchés.
- `chantier_piste2_confluence_multihorizon_2026-08-21.py` (Piste 2) reste
  un chantier fermé/diagnostiqué (filtre confluence rejeté, mécanisme
  compris) -- pas de suite prévue sauf nouvelle idée.

## Fichiers clés de cette session (tous committés, commit `df261dc`)

Voir la liste complète dans le message de commit. CSV de résultats
(gitignorés, locaux uniquement, régénérables via les scripts ci-dessus si
perdus) : `chantier_rtrailing_recalc_{officielle_verrouillee,A_reelle,
B_reelle}_2026-08-21.csv`, `chantier_bloc2_metaux_recalc_2026-08-21.csv`,
`chantier_bloc2_mecanisme_extension_signaux_2026-08-21.csv`,
`chantier_piste2_signaux_2026-08-21.csv`.
