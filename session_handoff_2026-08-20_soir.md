# Handoff — 20/08/2026 soir — §7 rafraîchi sur n=1248, 2 bugs moteur corrigés, 1 bug d'analyse trouvé+corrigé

Suite directe de `session_handoff_2026-08-20_pgp_priors.md` (intégration
palladium/platine + priors, faite côté VPS, pull récupéré et vérifié
indépendamment en début de cette session locale).

## 0. Ce qui a été vérifié/fait cette session (ordre chronologique)

1. **Intégration Pd/Pt du VPS vérifiée indépendamment** (pas juste
   supposée correcte) : population `chantier_gold_silver_pop_B_tradable_
   pgp_2026-08-20.csv` recontrôlée (n=1248, 102 palladium + 95 platinum +
   480 gold/silver + 571 forex/indices, wins=624/losses=624), wrapper
   `chantier_ab_metaux_tradable_pgp_2026-08-20.py` ré-exécuté, assertions
   passées. Tout confirmé propre.

2. **2 bugs moteur trouvés en tentant de lancer le cascade officiel sur
   cette population** (le chantier VPS ne l'avait jamais fait tourner
   end-to-end, hors de son scope) :
   - `correlation_matrix.csv` (33×33) n'avait pas PALLADIUM/PLATINUM →
     `KeyError` dans `precompute_correlation_pairs`. Corrigé :
     `extend_correlation_matrix_pgp_2026-08-20.py` (même méthode Pearson
     sur rendements H1 que l'extension gold/silver), matrice étendue à
     35×35, **commit `dbe7e99` déjà poussé**. Aucune paire Pd/Pt<->reste
     au-dessus du seuil 0,80 (max 0,742 entre les deux).
   - `market_data` n'avait pas d'entrée "unconstrained" pour PALLADIUM/
     PLATINUM (même classe de bug que celui déjà trouvé/corrigé pour
     GOLD/SILVER le 19/08) → `KeyError` dans `feasible_risk_pct`.
     Corrigé PAR WRAPPER dans `chantier_adx_combo_stack_pgp_2026-08-20.py`
     (pas de modification du fichier officiel, convention du projet).

3. **§7 (REF/SEQ_SEUL/ADX_SEUL/COMBO) rafraîchi n=600 sur n=1248**,
   2 plafonds en parallèle (process séparés, `chantier_adx_combo_stack_
   pgp_2026-08-20.py 600 {3000,5000} n600`). ⚠️ **Bug mineur** : les 2
   process partageaient le même `out_tag="n600"` → le CSV de sortie
   consolidé (`chantier_adx_combo_stack_pgp_n600_2026-08-20.csv`) ne
   contient que les données du dernier process à avoir écrit (5000$) —
   **aucune donnée perdue**, tout est dans les 2 logs séparés
   (`_c3000_log.txt`/`_c5000_log.txt`), mais si vous relancez ce genre de
   run en parallèle, utilisez un tag différent par plafond.

## 1. Résultats §7 sur n=1248 — la lecture change sur 2 fenêtres

| Fenêtre | Δ profit (n=1051, ancien) | Δ profit (n=1248, nouveau) |
|---|---|---|
| full | +3,3% | +3,5-3,9% |
| H1 | +24,7% | +24,5-25,3% |
| **H2** | **+0,0%** | **-2,3%** (cohérent aux 2 plafonds) |
| bloc1 | +23,6% | +18,3-18,4% |
| bloc2 | +93,7% | +54,9-55,6% (divisé par ~1,7, reste très positif) |
| bloc3 | -0,7% | +4,2% |
| **bloc4** | **-2,6%** | **-7,5%** (s'aggrave nettement) |

Risque (`annee1<0`) : améliore ou stable sur les 7 fenêtres, y compris
H2/bloc4 — la dégradation est uniquement en profit.

**Verdict provisoire (pas encore une décision d'adoption finale)** :
pile toujours globalement positive (5/7 fenêtres profit, 7/7 risque),
mais plus "propre partout" comme sur l'ancienne population. H2/bloc4
méritent le diagnostic ci-dessous avant adoption formelle.

## 2. Diagnostic causal H2/bloc4 — fait, avec une correction de bug importante

### 2.1 Bug trouvé dans l'analyse causale (PAS dans le moteur de simulation)

Le calcul "part du segment ADX-exclu dans le top 5%/1% des gagnants" de
la session précédente (celui qui disait "0% de représentation, mécanisme
propre") avait un **bug d'alignement d'index** : comparaison de
`set(pop.index[mask])` (index du dataframe trié par DATE) contre
`set(pop_sorted.iloc[:k].index)` où `pop_sorted` a été `reset_index`é
après tri par R — deux espaces d'index incompatibles, intersection donc
essentiellement fausse (faussement proche de 0).

**⚠️ Ce même pattern de bug existe dans le script ORIGINAL du projet**
(`chantier_adx_rrtp1_causal_investigation_2026-08-19.py`, lignes ~79-87)
— celui qui a produit le "×1,65 de sur-représentation" cité dans
`registre_strategie_trading.md` §6.3 pour expliquer le rejet initial
d'ADX sur la population complète (métaux inclus). **Ce chiffre n'a PAS
été re-vérifié cette session** (hors scope du diagnostic H2/bloc4
demandé) — à refaire avant de citer à nouveau ce ×1,65 comme preuve
solide. Les résultats de PROFIT des runs Monte Carlo ne sont pas
affectés (bug d'analyse post-hoc, pas de simulation) — seule
l'EXPLICATION du mécanisme est en cause.

### 2.2 Résultats corrects (recalculés proprement, méthode corrigée)

**Question 1 — l'edge Pd/Pt est-il faible sur H2/bloc4 ? Non, rejeté :**

| Fenêtre | n | EV Pd/Pt | vs global (+1,46R) |
|---|---|---|---|
| H2 | 121 | **+2,29R** (p<0,001) | le plus fort de toutes les sous-périodes |
| bloc4 | 77 | **+2,71R** (p<0,001) | idem |

**Question 2 — interaction avec la pile ? Oui, confirmé (mécanisme
plausible, pas prouvé au niveau granulaire) :**

Sur les 571 trades forex/indices (identiques que Pd/Pt existent ou non,
vérifié byte-à-byte) :

| Fenêtre | Part ADX-exclu dans top5% vs pop | EV exclu vs reste |
|---|---|---|
| Global | 10,3% vs 9,6% (≈proportionnel) | +0,60R vs +0,84R (écart -0,24R) |
| H2 | 11,8% vs 16,1% (sous-représenté x0,73) | +0,60R vs +1,46R (écart **-0,86R**) |
| bloc4 | 10,0% vs 21,4% (sous-représenté x0,47) | +0,68R vs +1,79R (écart **-1,11R**) |

Hypothèse principale : Pd/Pt ajoute +17 à +20% de volume de trades
côté B spécifiquement dans H2/bloc4 (121/706 et 77/392, vs 12-15%
ailleurs) — probable saturation de capacité (`MAX_POSITIONS`) côté
métaux dans ces fenêtres, qui neutralise le bénéfice habituel d'ADX
(libérer de la capacité) tout en continuant à sacrifier des trades
forex/indices dont l'EV y est particulièrement élevée. **Non confirmé
au niveau granulaire** — nécessiterait d'instrumenter `cap_blocked_
count`/`trades_admitted_count` (déjà trackés en interne par
`process_one_account`, non exposés dans `summarize_df`) sur un nouveau
run ciblé, PAS FAIT cette session (hors scope explicite du diagnostic
demandé).

## 3. Décision en attente

**Le §7 n'est PAS encore formellement adopté sur n=1248** — contrairement
à l'ancienne population (n=1051) qui l'était. Options pour la suite :
1. Instrumenter `cap_blocked_count` par fenêtre pour confirmer/infirmer
   l'hypothèse de saturation, avant de trancher.
2. Accepter le coût sur H2/bloc4 tel quel (gain net global toujours
   positif) et adopter quand même.
3. Explorer si un cap `MAX_POSITIONS` plus large (déjà un point ouvert
   séparé du registre §7, jamais testé sur B_tradable seule) réglerait
   aussi ce problème indirectement.

## 4. Chantiers VPS interrompus (session précédente) — À REPRENDRE

Rappel du handoff pgp_priors : 2 chantiers VPS stoppés proprement avant
l'intégration Pd/Pt (`chantier_multifirm_unlock_B_tradable_2026-08-20.py`
retest flotte multi-firms, `chantier6_ev_regime_bandes_reference_2026-08-
20.py` monitoring Phase 1). **Toujours pas relancés** — à faire reposer
sur `chantier_ab_metaux_tradable_pgp_2026-08-20.py` (n=1248,
Beta(625,625)) une fois la décision §7 ci-dessus tranchée, pas avant
(cohérence : pas de sens de retester la flotte multi-firms tant que la
brique ADX+trailing+séquentiel n'est pas stabilisée).

## 5. Fichiers clés de cette session (tous commités, voir git log)

- `extend_correlation_matrix_pgp_2026-08-20.py`, `correlation_matrix.csv`
  (35×35), `correlation_matrix_pre_pgp_backup_2026-08-20.csv` — commit
  `dbe7e99` (déjà poussé avant ce handoff).
- `chantier_adx_combo_stack_pgp_2026-08-20.py` — script §7 rebranché sur
  n=1248 (REF/SEQ_SEUL/ADX_SEUL/COMBO), inclut le fix market_data par
  wrapper.
- `chantier_adx_combo_stack_pgp_n600_2026-08-20.csv` — résultats
  partiels (5000$ seulement, cf. bug §0.3) ; **les résultats complets
  des 2 plafonds sont dans les logs**
  `chantier_adx_combo_stack_pgp_c{3000,5000}_log.txt`.
- `chantier_pop_B_tradable_pgp_adx_fx_only_2026-08-20.csv` — population
  ADX-fx-only filtrée sur n=1248 (n=1193, Beta(607,588)), déjà calculée,
  réutilisable sans recalcul ADX (cache Yahoo H1 déjà chaud).

## 6. Ce qui n'a PAS été fait (hors scope explicite)

- Pas de nouveau run n=600 pour le diagnostic H2/bloc4 (calcul direct
  sur données existantes uniquement, comme demandé).
- Pas de re-vérification du ×1,65 original (registre §6.3) — juste
  signalé comme suspect vu le bug trouvé ailleurs.
- Pas d'instrumentation cap_blocked/trades_admitted par fenêtre.
- Pas de décision d'adoption formelle du §7 sur n=1248.
- Pas de reprise des 2 chantiers VPS interrompus.
