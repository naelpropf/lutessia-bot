# Contexte projet trading Lutessia — v6, 8 août 2026 (fin de marathon, 5 sessions)

Remplace `contexte_projet_lutessia_2026-08-08-v5.md` comme mémoire de
reprise. v5 s'arrêtait à la fin de la 1ère session du 08/08 (mécanisme
"compte supplémentaire" déplafonné, flotte=2,75%). Quatre sessions
supplémentaires ont eu lieu le même jour, qui ont TOUTES changé le chiffre
de référence. **Lire cette section 0 en entier avant toute action.**

---

## 0. ⚠️ CONFIG FINALE VERROUILLÉE — état en fin de 5e session du 08/08

### 0.0 Résumé express (si tu ne lis qu'un paragraphe)

Après v5 (profit 5 982 779$/6 041 242$, mais jamais confirmé à n=600 —
c'était du n=300 présenté par erreur comme final), quatre sessions
supplémentaires ont : (1) découvert que ce chiffre n=300 était optimiste
d'environ 9% par rapport au vrai n=600 ; (2) remplacé le gate unique à
30k$ par un **déblocage échelonné par firm** (seuils de réserve
indépendants) qui a fait grimper le profit d'environ 60% par rapport au
n=600 réel de v5 ; (3) découvert et corrigé un **bug de données réel** (DD
journalier de The5%ers codé à 3% au lieu du vrai 5% du programme High
Stakes réellement utilisé), encore un free lunch pur. Le chiffre de
profit FIABLE actuel, confirmé n=600, est :

**Profit net (split 80% + IS réel) : 6 029 170$ (plafond 1000$) /
6 130 198$ (plafond 3000$)**, ruine 1,67%/0,00%, P(année1<0) 5,17%/3,50%.

**Ne jamais citer un chiffre de profit sans vérifier qu'il vient du
dernier script listé en section 1, ET qu'il a été confirmé à n=600 (pas
seulement n=300 — n=300 sert uniquement au screening de grilles larges).**

### 0.1 Paramètres de la config finale, verrouillés un par un

| Paramètre | Valeur | Où c'est codé |
|---|---|---|
| Structure de lancement | Blueberry seul jour0 (25k$/166$), puis chaque firm débloquée individuellement dès que sa réserve dédiée atteint son propre seuil | `seq_grouped_multi()` dans `extra_account_v4_multi_stagger.py` |
| Seuil de déblocage FTMO | **1 000$** | `seq_grouped_multi(t_ftmo=1000, ...)` |
| Seuil de déblocage The5%ers (Fivers) | **15 000$** | `seq_grouped_multi(..., t_fivers=15000, ...)` |
| Seuil de déblocage GFT | **25 000$** | `seq_grouped_multi(..., t_gft=25000, ...)` |
| Seuil de déblocage FundedNext (dernier palier) | **25 000$** (abaissé de 30k$, gain marginal — dans le bruit de mesure à n=600) | `seq_grouped_multi(..., t_fundednext=25000)` |
| `fleet_unlocked` (gouverne downgrade Blueberry + éligibilité mécanisme "compte supplémentaire") | passe `True` seulement au DERNIER palier (FundedNext) | `is_final=True` uniquement sur la dernière entrée de `seq_grouped_multi` |
| Amorçage protégé | 300$, Blueberry uniquement, phase pré-déblocage complet | `DEFAULT_EMERGENCY = 300.0` |
| Downgrade-on-reopen | Blueberry uniquement, pré-déblocage complet (`not fleet_unlocked`) | `downgrade_active()` dans `extra_account_v4_multi_stagger.py` |
| Split prop firm | 80% flat toutes firms | `SPLIT_FLAT = 0.80` |
| IS SASU | Réel, calendrier complet (acomptes trimestriels + solde) | `compute_is`/`handle_tax_payment` (`split_tax_model.py`) |
| RESERVE_SHARE | 95% | `FINAL_RESERVE_SHARE = 0.95` |
| Risque en évaluation | 2,25% toutes firms SAUF GFT | `FINAL_EVAL_RISK = 2.25` |
| Risque en évaluation, GFT | 1,75% (DD journalier plus serré → plus de tentatives) | `FINAL_GFT_EVAL_RISK = 1.75` |
| Risque une fois financé | **2,75%** (relevé de 2,5% en session 1 du 08/08) | `FINAL_FLEET_RISK = 2.75` |
| Mécanisme de croissance | "Compte supplémentaire" déplafonné : plusieurs comptes successifs par firm, plafonnés par les VRAIS caps prop firm (pas 1 seul comme avant) | `extra_account_v4_multi.py` puis repris dans `extra_account_v4_multi_stagger.py` |
| Plafond capital combiné FTMO | 400 000$, pas de limite de nombre de comptes | `FIRM_CAPITAL_CAP["FTMO"]` |
| Plafond capital combiné Blueberry | 450 000$ ET max 3 comptes financés | `FIRM_CAPITAL_CAP["Blueberry"]`, `FIRM_MAX_ACCOUNTS["Blueberry"]=3` |
| Plafond capital combiné GFT | 400 000$, pas de limite de nombre | `FIRM_CAPITAL_CAP["GFT"]` |
| Plafond capital combiné The5%ers | 500 000$ (confirmé support), 5ème compte inclus dans le mécanisme | `FIRM_CAPITAL_CAP["Fivers"]`, `FIRM_MAX_ACCOUNTS["Fivers"]=5` |
| **DD journalier The5%ers (Fivers)** | **5%** (corrigé 08/08 session 5, était 3% — bug de données réel, programme High Stakes 8/5% officiel confirmé, pas Bootcamp/Hyper Growth) | `GROUP_DEFS["Fivers"]["dd"]` dans `point2_sequencing_engine.py:49` |
| FundedNext | Fixe à 1 seul compte, palier 200 000$ (plafond mono-compte réel) | `FUNDEDNEXT_FIXED_PALIER = 200000.0` |

### 0.2 Chaîne de découvertes, dans l'ordre (les 5 sessions du 08/08)

**Session 1** (matin/après-midi, → v5) : vérification volets 1+2 (sur/sous-
estimation). Volet 1 : aucun dépassement de plafond réel trouvé. Volet 2 :
mécanisme "compte supplémentaire" déplafonné (auparavant limité
arbitrairement à 1 par firm) → +52% de profit. Re-sweep risque → flotte
2,5%→2,75% (+185k$). Chiffre obtenu : 5 982 779$/6 041 242$ **à n=300
seulement** (erreur méthodologique découverte plus tard).

**Session 2** (réduction P(année1<0)) : n=600 réel du chiffre de session 1
révèle qu'il était optimiste d'environ 9% (vrai n=600 : 5 462 855$/
5 528 183$, ruine 2,17%/1,00%, année1<0 11,17%/10,17%). Rampe post-
financement testée → REJETÉE (aggrave année1<0, arbitrage défavorable).
Déblocage partiel FTMO seul à 10k$ → free lunch confirmé n=600
(5 734 886$/5 812 289$). Étalement calendaire du déblocage groupé →
REJETÉ (aggrave aussi la ruine, pas seulement le profit). Diagnostic :
déficit catégorie A à 12 mois corrélé au délai depuis déblocage (retard
de compounding, pas perte réelle).

**Session 3** (généralisation multi-firm) : le concept FTMO-seul généralisé
à un déblocage échelonné à 5 paliers (1 seuil de réserve par firm). Grille
testée → meilleur combo **5/15/25/30k$** (FTMO/Fivers/GFT/FundedNext),
n=600 : 5 835 623$/5 938 236$, ruine 2,17%/0,33%, année1<0 6,83%/5,67%.
**Cascade check explicite** (point de vigilance demandé) : aucun nouveau
mode de ruine, taux de casse post-ouverture identiques au baseline.
Décomposition catégorie A/B confirmée cohérente.

**Session 4** (affinage FTMO + vérif catégorie A) : balayage du seuil FTMO
seul (Fivers/GFT/FundedNext fixés) → **1 000$** bat 2k/2,5k/3,5k/5k sur
profit et année1<0 (free lunch net à 1000$, léger arbitrage à 3000$ :
ruine 0,33%→0,67% contre +1,1% profit). **Vérification appariée par
seed** (contrefactuel exact, même tirage de trades) : le déficit
catégorie A à 12 mois est un **artefact de mesure confirmé**, pas un
risque caché — même le pire décile (p10) fait mieux à l'horizon complet
sous l'échelonné que sous l'ancien système. Chiffre : 5 912 229$/
6 005 790$, ruine 2,17%/0,67%, année1<0 6,33%/4,67%.

**Session 5** (cascade re-check + diagnostic fin + **bug DD The5%ers**) :
cascade check refait à FTMO=1k → toujours clean (GO). Diagnostic fin de
la ruine résiduelle : **changement de mécanisme détecté** — sous
l'ancien système (pré-08/08), 87-100% des ruines venaient d'un
effondrement APRÈS déblocage complet ; sous la config échelonnée
actuelle, c'est l'INVERSE : 92-100% des runs ruinés ne débloquent JAMAIS
la flotte complète (bloqués dans un cycle Blueberry casse/réouverture
perpétuel, jamais assez de réserve pour atteindre le seuil FundedNext).
**🔴 Bug de données découvert** : DD journalier The5%ers codé à 3% dans
`point2_sequencing_engine.py`, alors que le vrai programme retenu (High
Stakes, format 8/5%) a un DD officiel de **5%** (confirmé
help.the5ers.com / the5ers.com/faqs — le 3% appartient au Bootcamp/Hyper
Growth, jamais utilisés dans ce projet). Corrigé → free lunch pur sur les
3 axes (+1,9% profit, ruine et année1<0 meilleures). Balayage seuil
FundedNext (20k/25k/30k) sur la base corrigée → effet marginal seulement
(25k$ légèrement mieux que 30k$, dans le bruit de mesure ; 20k$ est
dominé, pire sur tout). Diagnostic firm : la sur-représentation de
The5%ers dans les casses (34-35% avant correction) était **entièrement
un artefact du bug DD** — après correction, sa part colle exactement à
son poids structurel dans la flotte (~24%, comme la moyenne globale tous
runs confondus). **Aucun traitement spécial nécessaire pour The5%ers.**

→ **Chiffre final actuel : 6 029 170$/6 130 198$, ruine 1,67%/0,00%,
année1<0 5,17%/3,50%.**

### 0.3 Bugs trouvés et corrigés (les 5 sessions)

- **Mécanisme "compte supplémentaire" limité à 1/firm** : plafond
  artificiel, sans justification réelle (corrigé session 1).
- **n=300 présenté comme "verrouillé"** : jamais confirmé à n=600, écart
  ~9% optimiste (découvert session 2, leçon méthodologique appliquée
  depuis).
- **DD journalier The5%ers codé à 3%** au lieu du vrai 5% (High Stakes
  8/5%, pas Bootcamp/Hyper Growth) — `point2_sequencing_engine.py:49`,
  corrigé session 5. Un doublon legacy (`DAILY_LOSS_5ERS_REAL=3.0` dans
  `robustness_5ers_risk_challenge.py:40`) existe mais est **confirmé
  inutilisé** par le pipeline `extra_account_v4_*` — laissé tel quel.

### 0.4 Points ouverts critiques jamais résolus

1. **FundedNext copytrade non confirmé par le support** — hérité depuis
   début 08/08, jamais reclarifié. Voir
   `project_fleet_structure_5firms_fundednext_unconfirmed.md`.
2. **Cascade check jamais refait sur la config finale COMPLÈTE actuelle**
   (DD=5% + FundedNext=25k combinés) — fait séparément à
   (DD=3%+FundedNext=30k) puis (DD=3%+FTMO=1k), jamais sur la
   combinaison exacte en vigueur. Recommandé avant tout capital réel.
3. **Seuil FTMO <1000$ jamais testé** (plancher de la grille demandée
   session 4) — gradient toujours favorable à 1k$, pas de retournement
   trouvé encore.
4. **Mécanisme de ruine résiduelle (pré-déblocage, Blueberry grinding)**
   identifié précisément (session 5) mais le seul levier testé contre
   (seuil FundedNext) n'a qu'un effet marginal — pas de vrai remède
   trouvé pour ce mode de ruine spécifique.
5. **[HÉRITÉ, BASSE] Écart code live non appliqué** : `app.py`/`app_mt5.py`
   n'ont reçu AUCUNE des découvertes de risque depuis début août. Argent
   réel en jeu, décision explicite à prendre avant tout lancement.

---

## 1. Scripts de référence — le dernier de chaque famille est la source de vérité

**⚠️ SCRIPT DE RÉFÉRENCE ACTUEL** : `extra_account_v4_multi_stagger.py`
(`seq_grouped_multi(t_ftmo, t_fivers, t_gft, t_fundednext)`,
`run_one`/`run_propagated`) — appelé avec `seq_grouped_multi(1000, 15000,
25000, 25000)` pour la config finale verrouillée. Dépend de
`extra_account_v4_multi.py` (constantes `FINAL_*`, `FIRM_CAPITAL_CAP`,
`FIRM_MAX_ACCOUNTS`, `EXTRA_UNIT_PALIER`, `cost_for_extra`,
`make_growth_acc`) et de `point123_startingfirm_optimization.GROUP_DEFS`
→ `point2_sequencing_engine.GROUP_DEFS` (DD Fivers=5% désormais correct).

**Scripts de sweep/diagnostic utilisés cette journée** (dans l'ordre) :
- `lotcap_feasibility_check.py` — vérif cap 100 lots/marge (négligeable ≤200k$/compte)
- `extra_account_v4_risk_sweep.py` — re-sweep éval/flotte (2,75% retenu)
- `extra_account_v4_year1_diagnosis.py` — décomposition catégorie A/B (v1)
- `extra_account_v4_postfund_ramp.py` — rampe post-financement (REJETÉ)
- `extra_account_v4_partial_unlock.py` — FTMO seul, seuils variables (SUPERSEDED)
- `extra_account_v4_staggered_unlock.py` — étalement calendaire (REJETÉ)
- `extra_account_v4_multi_stagger.py` — **moteur final**, 5 paliers à seuils indépendants
- `extra_account_v4_multi_stagger_diagnosis.py` — décomposition catégorie A/B sous moteur final
- `extra_account_v4_cascade_check.py` — vérif absence de cascade (taux casse post-ouverture, réserve min post-déblocage)
- `extra_account_v4_ftmo_sweep.py` — balayage seuil FTMO seul (1k retenu)
- `extra_account_v4_category_a_horizon.py` — appariement par seed, verdict artefact de mesure
- `extra_account_v4_full_diagnosis.py` — diagnostic complet (break_log par run, firm/timing des casses, rattrapage 18/24 mois, mécanisme de ruine)
- `extra_account_v4_fundednext_sweep.py` — balayage seuil FundedNext (25k retenu, marginal)

## 2. Points ouverts, par priorité

1. **[HAUTE]** Cascade check sur la config finale complète (DD=5%+FundedNext=25k) — jamais fait exactement sur cette combinaison.
2. **[HAUTE]** FundedNext non confirmé par le support (copytrade) — décision humaine nécessaire avant capital réel.
3. **[MOYENNE]** Mécanisme de ruine résiduelle (pré-déblocage) identifié mais pas résolu — chercher un levier plus efficace que le seuil FundedNext (ex. augmenter l'amorçage protégé 300$, ou un mécanisme de secours dédié pour Blueberry).
4. **[MOYENNE]** Seuil FTMO <1000$ jamais testé — gradient toujours favorable, plancher réel inconnu.
5. **[BASSE, HÉRITÉ]** Écart code live (`app.py`/`app_mt5.py`) jamais mis à jour avec aucune découverte depuis début août — argent réel en jeu.
6. **[BASSE]** Split prop firm toujours approximé à 80% flat, aucun barème exact par firm/palier jamais sourcé.

## 3. Mémoire persistante à consulter (fichiers dans `memory/`)

Lire `MEMORY.md` (index) puis, dans l'ordre chronologique pour le fil du
08/08 :
- `project_real_firm_caps_confirmed_2026-08-08.md`
- `project_extra_account_v4_multi_2026-08-08.md` (mécanisme, SUPERSEDED sur les chiffres)
- `project_v4_n600_reconfirmation_2026-08-08.md` (leçon n=300 vs n=600)
- `project_annee1_reduction_2026-08-08.md` (FTMO seul 10k, SUPERSEDED)
- `project_staggered_unlock_2026-08-08b.md` (5 paliers, SUPERSEDED sur FTMO)
- `project_ftmo_threshold_and_category_a_verdict_2026-08-08.md` (FTMO=1k + verdict artefact)
- `project_final_diagnosis_ftmo1k_2026-08-08.md` (mécanisme de ruine flippé)
- **`project_the5ers_dd_fix_and_fundednext_2026-08-08.md`** — **MÉMOIRE LA PLUS RÉCENTE, chiffres actuels**

Toute mémoire antérieure citant un chiffre de profit sans préciser "n=600
confirmé, DD Fivers=5%" est probablement obsolète.
