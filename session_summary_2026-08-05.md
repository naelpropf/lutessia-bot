# Résumé de session — 2026-08-05 (Lutessia bot)

Document de sauvegarde avant compactage. Ne remplace PAS `session_summary_2026-08-01.md`
(conservé intact) — ce résumé s'appuie dessus et le complète/corrige là où indiqué.

---

## 1. Rappel bref — acquis de la session du 2026-08-01

Session précédente : correction de 5 bugs structurels du moteur Monte Carlo copytrade
(bootstrap par permutation biaisé → block bootstrap 2 mois ; réserve non poolée →
poolée entre comptes ; absence d'immunité post-financement → ajoutée ; 999€ d'achat
initial des 3 challenges oublié → corrigé ; P&L de phase "challenge" compté à tort
comme profit réel → gaté sur `phase=="funded"`, bug le plus lourd, expliquait à lui
seul 106% de l'écart avec d'anciens chiffres surestimés). Slippage réel mesuré via
ticks Dukascopy (moyenne -0,91 pip, EV +0,907R→+0,850R). Décision verrouillée :
régime B (bascule immédiate au 1er financement, sans seuil de réserve) domine
strictement l'ancien régime C — choix A vs B laissé ouvert. Convention méthodologique
"OBJECTIF ATTEINT" = TP1 uniquement (pas TP2) rappelée comme acquis plus ancien mais
fondamental. Voir `session_summary_2026-08-01.md` pour le détail complet.

---

## 2. Bug découvert aujourd'hui : absence de limite de perte JOURNALIÈRE

### Nature du bug

Vérification demandée du code de casse (`monte_carlo_simulation.py`,
`copytrade_simulation_test.py`, `regime_abc_comparison.py`, et les deux moteurs
écrits ce soir `the5ers_summer_100k_N_accounts_test.py` / `three_firm_fleet_test.py`).
**Constat par grep sur tout le repo** : tous ces scripts importent
`BREAK_DD_PCT=10.0` (défini dans `scaling_simulation.py`) et l'utilisent de façon
identique :
```python
drawdown = peak_since_reset - cumulative_since_reset
if drawdown >= BREAK_DD_PCT / 100 * palier: <casse>
```
C'est un drawdown **trailing depuis le pic atteint depuis le dernier reset**
(challenge ou financement), **pas** une perte journalière calendaire.
**Aucun fichier .py du projet ne contenait de logique de perte journalière**, alors
que les vraies firms en imposent une, SÉPARÉE du max drawdown total :

| Firm | Programme | Perte journalière | Max loss (déjà modélisé, correct) |
|---|---|---|---|
| The5%ers | Summer Plan 2-Step | **3%** | 10% |
| FTMO | 2-Step | **5%** | 10% |
| Blueberry Funded | Two-Step | **5%** | 10% |

Sources : pages officielles/FAQ the5ers.com, ftmo.com, blueberryfunded.com
(consultées ce soir).

### Démonstration sur la trajectoire réelle

Trajectoire historique déterministe (472 trades, 100k palier, 2% risque,
`daily_dd_threshold_verification.py`) : **17 casses** avec seulement le DD trailing
10% (logique d'avant) vs **29 casses (+70,6%)** en ajoutant une limite journalière
3%. Confirme que le bug est significatif → correction lancée sur tous les moteurs.

### Impact chiffré avant/après par configuration (moteurs `*_dailydd.py`, 2000 runs MC)

**a) Régimes A/B/C** (structure 3×50k→200k→500k, réinterprétée comme le segment
croissance FTMO/Blueberry → daily=5%) : **impact quasi nul**.

| | 37,29% avant→après | 32% avant→après |
|---|---|---|
| Profit final moyen, régime A | 7 792 852€ → 7 737 939$ (-0,7%) | 4 657 213€ → 4 603 339$ (-1,2%) |
| P(perte) an1, régime A | 4,70% → 4,65% | 15,30% → 16,00% |
| Cash pire cas, régime A | 9 990€ → 9 990$ (stable) | 10 989€ → 10 989$ (stable) |

Le seuil 5% étant déjà proche de ce qu'impliquait le DD trailing 10%, ajouter la
limite journalière ne change quasiment rien ici. **Les chiffres régime A/B/C du
2026-08-01 restent valides tels quels.**

**b) The5%ers seul, 100k×N (N=3/N=4)** (daily=3%, le seuil le plus strict) :
**impact net et significatif**.

| | 37,29% N=3 avant→après | 37,29% N=4 avant→après |
|---|---|---|
| Profit final moyen | 1 760 266$ → 1 578 025$ (**-10,4%**) | 2 347 021$ → 2 104 033$ (**-10,4%**) |
| Casses moy. (horizon) | 50,7 → 83,6 (**+64,8%**) | 67,7 → 111,4 (**+64,6%**) |
| Cash pire cas | 5 370$ → 7 518$ (+40,0%) | 7 160$ → 10 024$ (+40,0%) |

| | 32% N=3 avant→après | 32% N=4 avant→après |
|---|---|---|
| Profit final moyen | 1 031 272$ → 873 990$ (**-15,3%**) | 1 375 029$ → 1 165 320$ (**-15,2%**) |
| Cash pire cas | 5 907$ → 8 592$ (+45,4%) | 7 876$ → 11 456$ (+45,4%) |

**c) Flotte 3 firms combinée** (5ers 3% + FTMO/Blueberry 5%) : impact intermédiaire,
tiré vers le bas par le segment 5ers.

| | 37,29% avant→après | 32% avant→après |
|---|---|---|
| Profit final moyen | 5 649 365$ → 5 372 936$ (**-4,9%**) | 3 454 413$ → 3 215 356$ (**-6,9%**) |
| P(perte) an1 | 2,75% → 2,70% | 9,90% → 11,25% |
| Cash pire cas | 17 150$ → **20 014$** (+16,7%) | 17 866$ → **21 446$** (+20,0%) |
| Casses moy. (horizon) | 118,6 → 164,3 (+38,6%) | 149,0 → 200,0 (+34,2%) |

Le pire cas de trésorerie perso dépasse désormais nettement l'ancien repère 10k€/$.

### Croisement cash sorti × résultat net (flotte corrigée, analyse complémentaire)

Sur la flotte 3 firms corrigée : dépasser 10 000$ de cash sorti arrive dans
**2,45% (37,29%) à 3,75% (32%)** des runs (pas un cas exceptionnel) ; dépasser
15 000$ dans **0,35-0,50%**. Atteindre ces paliers élevés, y compris le pire cas
absolu (20-21k$), **n'implique pas systématiquement une année négative** : le run au
pire cas absolu termine positif dans les deux winrates (+166 503$ à 37,29%,
+67 544$ à 32%) ; le taux de succès année 1 reste à 80-90% même au-delà de 15 000$
de cash sorti (vs 88,75-97,30% en moyenne globale). Sortir beaucoup de cash signale
des casses répétées en début de parcours, pas un échec probable de l'année.

---

## 3. Chiffres de référence officiels — POST-CORRECTION daily DD (remplacent le §2 du 2026-08-01)

**Régimes A/B/C** : chiffres du 2026-08-01 confirmés valides (voir 2a ci-dessus,
écart <1,5%). Régime B reste stratégiquement dominant sur C ; A vs B toujours ouvert.

**The5%ers 100k×N seul** (moteur `the5ers_summer_100k_N_accounts_dailydd.py`,
palier fixe, pas de scaling, ramp 0,5%→2% après 12 trades/compte) :

| Winrate | N | Profit an1 moyen | Profit horizon complet moyen | P(perte) an1 | Cash pire cas | Casses moy. |
|---|---|---|---|---|---|---|
| 37,29% | 3 | +360 633$ | +1 578 025$ | 2,55% | 7 518$ | 83,6 |
| 37,29% | 4 | +480 844$ | +2 104 033$ | 2,55% | 10 024$ | 111,4 |
| 32% | 3 | +197 429$ | +873 990$ | 13,50% | 8 592$ | 100,8 |
| 32% | 4 | +263 239$ | +1 165 320$ | 13,50% | 11 456$ | 134,3 |

**Flotte 3 firms combinée** (moteur `three_firm_fleet_dailydd.py`, 4×100k 5ers +
2×FTMO/1×Blueberry croissance 50k→200k→500k plafonnée) :

| Winrate | Profit an1 moyen | dont 5ers / croissance | Profit horizon complet moyen | dont 5ers / croissance | P(perte) an1 | Cash pire cas | Casses moy. |
|---|---|---|---|---|---|---|---|
| 37,29% | +1 151 418$ | +480 844$ / +670 574$ | +5 372 936$ | +2 104 033$ / +3 268 903$ | 2,70% | 20 014$ | 164,3 |
| 32% | +658 276$ | +263 239$ / +395 037$ | +3 215 356$ | +1 165 320$ / +2 050 036$ | 11,25% | 21 446$ | 200,0 |

**Rappel important (toujours valable)** : la flotte 3 firms reste **moins profitable**
que l'ancien plan 3×50k avec scaling libre jusqu'à 500k (delta net négatif, -4,9% à
-6,9% en plus de l'ancien écart déjà négatif calculé avant la correction daily DD),
parce que les plafonds de capital combiné par firm (400k) rendent le palier 500k
inatteignable. Voir §4.

---

## 4. Plafonds de capital combiné confirmés par firm + structure de flotte retenue

| Firm | Plafond capital combiné (copie inter-comptes) | Source |
|---|---|---|
| The5%ers | **500 000$** | Confirmé directement par le support The5%ers (utilisateur) |
| FTMO | **400 000$** (avant scaling) | FAQ officielle FTMO |
| Blueberry Funded | **400 000$** | Help Center officiel Blueberry |

**Structure de flotte retenue** :
- **The5%ers** : 4 comptes 100k fixes (Summer Plan 2-Step 8/5, 179$/challenge),
  jamais upgradés, profits retirés régulièrement. 4×100k = 400k < 500k → sous le
  plafond.
- **FTMO** : 2 comptes croissance (mécanisme 50k→200k→500k, réserve poolée 80%) —
  plafonnés en pratique à 200k chacun (2×200k=400k pile), le palier 500k étant
  structurellement inatteignable dès qu'un seul compte le dépasserait déjà à lui
  seul le plafond de 400k.
- **Blueberry Funded** : 1 compte croissance, même mécanisme, même plafonnement
  effectif à 200k (500k > 400k même seul).
- Conséquence : **857 tentatives d'upgrade bloquées/run en moyenne** (37,29%,
  confirmé empiriquement) — le palier 500k n'est JAMAIS atteint avec cette
  répartition.

---

## 5. Point ouvert non résolu : viabilité de The5%ers vu son daily DD strict (3%)

Le seuil journalier de 3% chez The5%ers (le plus strict des trois firms, contre 5%
chez FTMO/Blueberry) inflige à lui seul un coût de -10 à -15% de profit et +65% de
casses sur ce segment (§2b). Trois options n'ont **pas encore été chiffrées ni
tranchées** :
1. **Garder The5%ers tel quel** (100k×4, risque 2% après ramp) — accepter le coût
   du seuil strict pour la diversification/plafond de copie généreux (500k).
2. **The5%ers à risque réduit** (rester à 0,5-1% même après la période de ramp, au
   lieu de basculer à 2%) — réduirait les casses dues au 3% journalier mais aussi le
   profit brut ; effet net non quantifié.
3. **The5%ers en tremplin temporaire seulement** (l'utiliser le temps de constituer
   une réserve/capital initial, puis migrer le capital vers FTMO/Blueberry où le
   daily DD est plus permissif) — logique de transition non modélisée.
4. **Abandonner The5%ers** pour ce segment et concentrer les 4 emplacements de
   compte supplémentaires sur plus de comptes FTMO/Blueberry (repousserait
   peut-être aussi le plafond 500k du palier croissance si assez de comptes/firms
   sont ajoutés).

**Décision en attente des scénarios à tester** — aucune des 4 options n'a de
chiffrage Monte Carlo à ce jour, à faire dans une session future si le sujet reste
pertinent.

---

## 6. Fichiers/scripts obsolètes après la correction daily DD (ne plus utiliser)

### Remplacés directement par une version `_dailydd` ce soir

- `regime_abc_*.csv`, `regime_abc_comparison_summary.csv` — remplacés par
  `regime_abc_dailydd_*.csv`, `regime_abc_dailydd_summary.csv`. **Écart négligeable
  (<1,5%)**, mais utiliser la version corrigée par principe de traçabilité.
- `the5ers_100k_N{3,4}_*.csv` (sans suffixe), `the5ers_100k_N_accounts_summary.csv`
  — remplacés par `the5ers_100k_N{3,4}_*_dailydd.csv`,
  `the5ers_100k_N_accounts_dailydd_summary.csv`. **Écart significatif (-10 à -15%
  profit)** — ne pas réutiliser les anciens chiffres.
- `three_firm_fleet_{37_29pct,32pct}.csv`, `three_firm_fleet_summary.csv` —
  remplacés par `three_firm_fleet_dailydd_*.csv`,
  `three_firm_fleet_dailydd_summary.csv`. **Écart significatif (-5 à -7% profit,
  pire cas cash +17-20%)**.

### Scripts moteurs devenus obsolètes (logique incomplète, pas de daily DD)

- `regime_abc_comparison.py`, `the5ers_summer_100k_N_accounts_test.py`,
  `three_firm_fleet_test.py` — gardés pour l'historique/audit, mais NE PAS relancer
  pour produire de nouveaux chiffres : utiliser leurs équivalents `*_dailydd.py`.
- Par extension, `monte_carlo_simulation.py` et `copytrade_simulation_test.py`
  (jamais corrigés ce soir, daily DD toujours absent) : toute sortie chiffrée de ces
  deux scripts sous-estime les casses / surestime le profit. Non prioritaire à
  corriger si leurs sorties ne sont plus la référence citée (le pooled-reserve
  multi-comptes a migré vers les scripts `regime_abc`/`the5ers`/`three_firm`), mais
  à garder en tête si on les réutilise un jour.

### Analyse déjà obsolète avant même la correction (rappel §4 du 2026-08-01)

- Toujours valables telles quelles : `slippage_proxy_dukascopy_detail.csv`,
  `population_with_force.csv`, `trailing_realistic_payoff_detail.csv`,
  `force_score_analysis.py`/`force_weighting_test.py` — non concernées par le bug
  daily DD (mesures brutes, pas de moteur de casse).
- `copytrade_simulation_summary.csv`, `copytrade_risk_levels_summary.csv` — déjà
  signalés obsolètes le 2026-08-01 (payoff `rr_tp1` seul, pas réaliste+trailing) ;
  toujours obsolètes, ET en plus jamais dotés du daily DD.

### Outils de diagnostic produits ce soir (à conserver, pas des résultats à citer)

- `daily_dd_threshold_verification.py` — script de démonstration/preuve du bug (pas
  une source de chiffres de référence, juste la trajectoire déterministe de test).
- `cash_vs_year1_outcome_crosstab.py` — analyse croisée cash/résultat, pointait à
  l'origine sur les CSV régime A pré-correction ; réutilisé manuellement (pas via le
  script lui-même) sur les CSV `three_firm_fleet_dailydd_*.csv` pour l'analyse du §2.
