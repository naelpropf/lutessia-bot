# Résumé de session — 2026-08-01 (Lutessia bot)

Document de sauvegarde avant compactage. Couvre les corrections de méthodologie, le
nouveau régime de référence, et l'état des fichiers du projet.

---

## 1. Bugs identifiés et corrigés

### 1.1 Bug TP1/TP2 ("OBJECTIF ATTEINT" = TP1, pas TP2)
- **Contexte** (déjà connu avant cette session, rappelé ici car fondamental) : le statut
  Lutessia "OBJECTIF ATTEINT" garantit seulement que TP1 a été touché, PAS TP2. De
  nombreux scripts substituaient naïvement `rr_tp2` pour tous les trades gagnants.
- **Impact** : EV naïve +1.523R vs EV réaliste (continuation TP1→TP2 vérifiée par
  bougies H1) +0.822R sur les 472 trades de référence — **surestimation ~85%**.
- **Fix** : `tp2_realistic_payoff.py` (colonne `r_realiste`), puis
  `trailing_payoff_population.py` (colonne `r_trailing`, + trailing 0.2×SL post-TP2,
  EV +0.907R) — convention verrouillée actuelle.

### 1.2 `backtest_analyzer.py` / `analyse_live.py` — bug de payoff live
- MIN_RR resté à 2.0 (obsolète, seuil verrouillé = 1.5) ; payoff naïf `rr_tp2` utilisé
  pour le comparatif live-vs-backtest hebdomadaire (pas du code mort — appelé chaque
  semaine par `app.py`).
- **Fix** : MIN_RR→1.5, comparatif basé sur `trailing_realistic_payoff_detail.csv`
  (`r_trailing`, instantané statique, pas de nouvel appel réseau H1 en live).

### 1.3 Bug de fenêtre calendaire (`daily_dd_pair_analysis.py`)
- `build_trade_day_excursions` mesurait le high/low sur la journée calendaire ENTIÈRE
  au lieu de la fenêtre réelle d'ouverture du trade — fabriquait un faux "duo à risque"
  (GBP/JPY-USD/CHF) et gonflait un vrai chiffre (AUD/JPY-USD/JPY 8.81%→1.00% après fix).

### 1.4 Biais du bootstrap par PERMUTATION (sous-estime le risque de queue)
- **Mécanisme** : mélange l'identité des trades tout en gardant les vraies dates
  d'arrivée — détruit le regroupement temporel réel des séquences de pertes (un
  mauvais trimestre réel groupé dans le temps se retrouve dispersé aléatoirement).
- **Fix** : block bootstrap (blocs contigus de 2 mois, rééchantillonnés avec remise) —
  préserve la vraie structure de clustering.
- **Impact mesuré** (Phase 1, pire cas trésorerie, toutes choses égales par ailleurs) :
  permutation 21 972€ → block bootstrap seul **48 195€** (+26 223€, le bootstrap SEUL
  aggrave, ne réduit pas — contre-intuitif, mais confirmé par ablation).

### 1.5 Réserve NON poolée (chaque compte indépendant)
- **Avant** : chacun des 3 comptes copytrade avait sa PROPRE réserve, alimentée
  uniquement par SES propres gains financés — un compte en difficulté ne bénéficiait
  jamais des gains d'un compte-sœur, alors que c'est le même trader/portefeuille.
- **Fix** : réserve UNIQUE partagée entre les 3 comptes (80% des gains financés de
  N'IMPORTE lequel des 3, utilisable pour N'IMPORTE lequel).
- **Impact** (ablation, pire cas trésorerie) : -27 577€ (le plus gros levier isolé des
  3 corrections structurelles).

### 1.6 Absence de mécanisme d'immunité post-financement
- **Avant** : le budget personnel restait exposé indéfiniment, même après des années
  de rentabilité démontrée.
- **Fix** : dès qu'AU MOINS un des 3 comptes a été financé une première fois
  (`ever_funded=True`, définitif), plus aucun rachat ne tape dans le budget personnel,
  quel que soit l'état de la réserve à cet instant.
- **Impact** (ablation) : -17 621€.
- **Découverte majeure dérivée** : ce mécanisme rend le risque de trésorerie perso
  **rigoureusement identique** quel que soit le seuil de bascule choisi (Immédiat à
  10 000€) — prouvé run-par-run (0/2000 runs diffèrent entre les deux extrêmes). Voir
  section 3.

### 1.7 Bug comptable des 999€ (achat initial des 3 challenges)
- **Découvert en construisant l'ablation** du pire cas de trésorerie (21 972€→2 997€).
- Les moteurs "réserve poolée" écrits cette nuit (`three_regime_cash_comparison.py`,
  `slippage_impact_simulation.py`, `two_regime_full_distribution_test.py`)
  initialisaient `real_cash_paid = 0.0`, alors que le tout premier achat de challenge
  (333€×3 comptes = 999€) est nécessairement payé cash dès le départ (aucune réserve
  n'existe encore à t=0).
- **Fix** : `real_cash_paid = CHALLENGE_COST[palier] * N_ACCOUNTS` à l'initialisation,
  appliqué uniformément dans tous les moteurs corrigés depuis.
- **Impact exemple** : régime hybride, pire cas trésorerie année 1 : 1 998€ (avant
  fix) → **2 997€** (après fix, chiffre correct).

### 1.8 Bug de comptabilité challenge/financé dans `monte_carlo_simulation.run_one`
- **Le plus gros bug en impact €** — jamais propagé depuis sa correction dans
  `sizing_fleet_test.py` plus tôt dans le projet.
- **Mécanisme** : `total_trading_pnl += pnl` s'exécutait pour CHAQUE trade, y compris
  en phase "challenge" (P&L jamais réellement encaissable, juste un chiffre théorique
  avant financement) — comptait ce P&L comme profit réel.
- **Découverte** : en investiguant pourquoi les chiffres de référence cités
  (~2,63M€ à 0,5% jusqu'à ~13,39M€ à 3%, source `risk_levels_trailing_02_summary.csv`
  du 30/07) ne matchaient pas les chiffres recalculés cette nuit (-14,8% à -28,9%
  d'écart, croissant avec le risque).
- **Fix** : gaté par `if phase == "funded": total_trading_pnl += pnl` — même pattern
  que `sizing_fleet_test.py`, appliqué à `monte_carlo_simulation.run_one` ET
  `copytrade_simulation_test.simulate_account_with_events`/`run_copytrade_one`.
- **Impact** (ablation, risque 2%, horizon complet) : V0 (bug, reproduit 10 333 737€
  ≈ chiffre cité 10 335 102€) → V1 (+comptabilité financé-seulement) = 7 770 787€ —
  **le bug explique à lui seul 106,1% de l'écart total** (bootstrap et pooling
  n'expliquent presque rien sur le PROFIT MOYEN, contrairement à leur fort effet sur
  le pire cas de trésorerie — deux métriques différentes, deux mécanismes différents).
- **Pourquoi l'écart croît avec le risque** : plus de risque → plus de casses → plus de
  temps passé en re-challenge → plus de P&L à tort compté comme profit dans l'ancienne
  version. Casses observées (corrigées) : 2,14 (0,5%) → 80,09 (3%).

### 1.9 Slippage réel mesuré (Dukascopy, remplace le proxy H1 jugé insuffisant)
- yfinance limité à 730 jours en H1 (insuffisant pour l'historique 2022-2026) ; testé
  et confirmé : M5=60j max, M1=8j max — inutilisables. MT5 broker testé : seulement
  ~3 mois d'historique M1 sur le compte connecté — insuffisant aussi.
- **Solution retenue** : ticks bid/ask Dukascopy (gratuit, sans auth, profondeur
  testée jusqu'à 2010), résolution sub-seconde, matching médian à 0,52-0,61s du
  timestamp réel du signal sur 469/472 trades.
- **Résultat mesuré** : slippage moyen **-0,91 pip**, médian -0,70 pip, écart-type
  2,85 pips, P5/P95 [-4,22 ; +1,90] pips. Par classe : JPY -1,05, CHF -1,37, CAD -1,23,
  GBP -0,85, USD -0,46 pips. Impact sur l'EV : +0,907R (sans) → +0,850R (avec,
  méthode empirique).
- Bug annexe rencontré et corrigé pendant l'implémentation : rate-limiting Dukascopy
  (HTTP 429) mal mis en cache comme "marché fermé" — corrigé avec retry/backoff.

---

## 2. Tableau de référence officiel final

Moteur complet : block bootstrap 2 mois + réserve poolée + immunité post-financement +
correctif 999€. Copytrade 3 comptes, seuil rr_tp1≥1.5, payoff réaliste + trailing
0.2×SL, plafond 3 positions/compte, corrélation 0.6+JPY, faisabilité marge(1:30)/100
lots. **Sans slippage** (isolé du sujet winrate/régime — voir 1.9 pour l'effet
slippage séparément mesuré, ~-6% sur l'EV).

| | A. 2% direct | B. Hybride amélioré (bascule immédiate) | C. Hybride actuel (@5000€, **obsolète**) |
|---|---|---|---|
| **Winrate 37,29% (réel)** | | | |
| Profit an1 moy/médian | **+1 567 618€ / +1 480 521€** | +1 282 578€ / +1 154 394€ | +962 743€ / +788 822€ |
| Profit horizon complet (~3,96 ans) moy/médian | **+7 792 852€ / +7 720 252€** | +7 489 163€ / +7 375 250€ | +7 111 446€ / +7 012 129€ |
| P(perte) an1 | **4,70%** | 9,80% | 18,85% |
| Trésorerie moy / pire cas | 1 535€ / 9 990€ | 1 057€ / 3 996€ | 1 057€ / 3 996€ |
| P(>3000/5000/10000€) | 6,20% / 1,30% / 0,00% | 0,05% / 0% / 0% | 0,05% / 0% / 0% |
| Casses (horizon complet) | 48,11 | 44,94 | 40,96 |
| **Winrate 32% (borne bayésienne P10)** | | | |
| Profit an1 moy/médian | **+850 165€ / +742 952€** | +652 359€ / +493 433€ | +458 430€ / +160 869€ |
| Profit horizon complet moy/médian | **+4 657 213€ / +4 532 262€** | +4 419 492€ / +4 277 112€ | +4 127 746€ / +4 020 571€ |
| P(perte) an1 | **15,30%** | 24,60% | 36,80% |
| Trésorerie moy / pire cas | 1 678€ / 10 989€ | 1 123€ / 4 995€ | 1 123€ / 4 995€ |
| P(>3000/5000/10000€) | 7,70% / 2,75% / 0,10% | 0,20% / 0% / 0% | 0,20% / 0% / 0% |
| Casses (horizon complet) | 60,59 | 55,68 | 48,65 |

Remplace intégralement les anciens chiffres ~2,63M€-13,39M€ (bug §1.8) et le régime C
comme référence par défaut (voir §3).

---

## 3. Décision verrouillée mise à jour

**Ancien** : bascule 0,5%→2% de risque une fois la réserve poolée ≥5000€.
**Nouveau** : **bascule immédiate au premier financement d'un compte** (`ever_funded`),
sans seuil de réserve — régime B.

### Raisonnement complet
1. **Le seuil de réserve n'a plus aucun effet protecteur** sous le modèle poolé +
   immunité : le risque de trésorerie perso est entièrement déterminé par les
   événements survenant AVANT le premier financement — prouvé au niveau du code
   (`real_cash_paid` n'est jamais incrémenté si `ever_funded=True`, condition
   totalement indépendante de `switched`/seuil) ET empiriquement (0/2000 runs
   diffèrent entre le déclencheur "Immédiat" et "Réserve≥10000€", tous percentiles
   confondus P(>1000/2000/3000€) identiques).
2. **C est strictement dominé par B** : même profil de trésorerie exact (aucune
   différence), mais B a un meilleur profit ET un meilleur P(perte) à tous les
   niveaux testés (voir tableau §2). Retarder la bascule ne protège rien, ça coûte
   seulement du profit.
3. **B vs A reste un choix ouvert** selon la capacité réelle de mobilisation de
   trésorerie de secours — voir §5.

---

## 4. Fichiers/scripts désormais obsolètes (ne plus utiliser comme référence)

### Directement remplacés cette nuit par une version corrigée régénérée
- `risk_levels_trailing_02_summary.csv`, `risk_levels_trailing_summary.csv`,
  `risk_levels_realistic_summary.csv` — régénérés avec le moteur corrigé (§1.8),
  utiliser les versions actuelles sur disque.
- `copytrade_vs_fleet_trailing_02_summary.csv`, `copytrade_vs_fleet_trailing_summary.csv`,
  `copytrade_vs_fleet_realistic_summary.csv` — idem.
- `year1_breakdown_trailing_02_summary.csv` — idem.

### Obsolètes, PAS régénérés (à ignorer ou recalculer si besoin futur)
- `risk_switch_threshold_summary.csv`, `risk_switch_threshold_block_bootstrap_summary.csv`
  — ancienne méthodologie (permutation et/ou non poolée, bug §1.8 sur la colonne
  profit) ; remplacés par `risk_switch_threshold_corrected_summary.csv` (nouveau,
  confirme que le seuil n'a plus d'effet — §3).
- `real_cash_risk_year1_mc_detail.csv`, `real_cash_risk_switch5000_detail.csv` —
  bootstrap par permutation, pré-correctifs pooling/immunité/999€.
- `three_regime_cash_0.5%_pur.csv`, `three_regime_cash_2.0%_direct.csv`,
  `three_regime_cash_hybride_0.5-2.0.csv` — pré-correctif 999€ (chiffres cash
  sous-estimés d'~999€).
- `two_regime_full_dist_2pct_debloque.csv`, `two_regime_full_dist_hybride_ref.csv` —
  remplacés par `two_regime_updated_*.csv` (correctif 999€ + slippage intégrés).
- `copytrade_simulation_summary.csv`, `copytrade_risk_levels_summary.csv` —
  utilisent encore `fleet_simulation_test.build_trades` (payoff `rr_tp1` seul, EV
  théorique +0.140R, PAS le payoff réaliste+trailing verrouillé) — jamais dans le
  périmètre des corrections de cette nuit, à traiter séparément si besoin (voir §5).
- Tout fichier `winrate28_*` (scénario 28% remplacé par le scénario 32% bayésien,
  §voir conversation — le 28% reste utile pour contraste historique seulement, pas
  comme référence de stress-test).

### Toujours valides (non affectés par les bugs de cette nuit)
- `slippage_proxy_dukascopy_detail.csv`, `population_with_force.csv`,
  `trailing_realistic_payoff_detail.csv` — données de mesure brute, pas de moteur de
  simulation, non concernées.
- `force_score_analysis.py` / `force_weighting_test.py` — conclusion (Force non
  exploitable) indépendante des bugs de moteur, reste valide.

---

## 5. Points encore ouverts

1. **Choix définitif A vs B** : dépend de la vraie capacité de mobilisation de
   trésorerie de secours du trader. A domine sur profit ET P(perte) mais pire cas de
   trésorerie ~10-11k€ (P(>5000€) jusqu'à 2,75%) ; B est un plafond de sécurité
   ~5000€ (jamais dépassé dans l'historique testé) au prix d'un profit/P(perte)
   dégradés. **Non tranché — attend la contrainte réelle de l'utilisateur.**
2. **`copytrade_simulation_test.py`'s own `main()` demo et `copytrade_risk_levels_test.py`**
   utilisent encore le payoff `rr_tp1` seul (via `fleet_simulation_test.build_trades`)
   au lieu du payoff réaliste+trailing verrouillé — incohérence résiduelle non
   corrigée cette nuit (hors périmètre explicite demandé), à signaler si ces sorties
   sont un jour citées.
3. **Fonctions de trajectoire déterministe mensuelle** (`simulate_account_with_events`
   via `run_deterministic_monthly_std`) restent en réserve NON poolée (3 comptes
   indépendants) — approximation acceptée pour le calcul de `monthly_std_pct`/
   `net_profit_deterministic` dans les CSV régénérés, pas au niveau du Monte Carlo
   principal (qui, lui, est poolé). Écart mineur, non quantifié précisément.
4. **Rescraping Force** : arrêté à la demande une fois la couverture des 1773 trades
   de référence confirmée à 100% (jusqu'à 2022-01-27, largement suffisant) — ticket
   fermé, pas un point ouvert à proprement parler, mentionné pour mémoire.
