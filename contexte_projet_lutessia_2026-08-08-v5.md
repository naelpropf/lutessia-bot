# Contexte projet trading Lutessia — v5, 8 août 2026 (suite marathon 07-08/08)

Remplace `contexte_projet_lutessia_2026-08-07-v4.md` comme mémoire de reprise.
Session continue directement la marathon du 07/08 (section 0 de v4) : reprend
la découverte du risque de ruine et sa mitigation (réserve 30k + amorçage
300$), puis enchaîne une série de corrections et raffinements qui ont
TOTALEMENT changé les chiffres de référence. **Lire cette section 0 en
entier avant toute action — plusieurs découvertes majeures invalident des
chiffres cités plus tôt dans la même session.**

---

## 0. ⚠️ CONFIG FINALE VERROUILLÉE — état au 08/08 fin de session

### 0.0 Résumé express (si tu ne lis qu'un paragraphe)

Après une longue chaîne de corrections (split réaliste, downgrade-on-reopen,
IS réel, RESERVE_SHARE optimisé, grille de risque, diagnostic année1<0,
**correction majeure du mécanisme de scaling — l'ancien était un bug qui
surestimait le profit de ~60%**, puis remplacement par un mécanisme "compte
supplémentaire" plus réaliste, FundedNext fixé à son vrai plafond mono-compte
200k$, risque réduit spécifiquement pour GFT), le chiffre de profit final
FIABLE actuel est :

**Profit net (split 80% + IS réel) : 3 733 811$ (plafond 1000$) /
3 771 839$ (plafond 3000$)**, ruine 1,33%/0,33%, P(année1<0) 10,33%/9,33%.

Ce chiffre a beaucoup bougé plusieurs fois dans la même session (7 792 277$
sans rien → 5 763 351$/5 817 008$ avec un mécanisme de scaling buggé →
2 274 631$/2 298 627$ après correction du bug → 3 733 811$/3 771 839$ avec le
mécanisme "compte supplémentaire" + ajustements fins). **Ne jamais citer un
chiffre de profit de cette session sans vérifier qu'il vient bien du dernier
script listé en section 1.**

### 0.1 Paramètres de la config finale, verrouillés un par un

| Paramètre | Valeur | Où c'est codé |
|---|---|---|
| Structure de lancement | Blueberry seul day0 (25k$/166$) puis reste de la flotte (FTMO+The5%ers+GFT+FundedNext) débloqué en bloc | `SEQ_GROUPED` dans tous les scripts finaux |
| Seuil de réserve avant déblocage groupé | 30 000$ | `DEFAULT_RESERVE = 30000.0` |
| Amorçage protégé | 300$, Blueberry uniquement | `DEFAULT_EMERGENCY = 300.0` |
| Downgrade-on-reopen | Blueberry uniquement, **phase pré-déblocage seulement** (se désactive une fois `fleet_unlocked=True`) | `downgrade_active() = not fleet_unlocked` |
| Split prop firm | 80% flat (PAS le barème croissant 80→90% de l'ancien `split_tax_model.py`) | `SPLIT_FLAT = 0.80` |
| IS SASU | Réel, calendrier complet (acomptes trimestriels + solde), réutilisé de `split_tax_model.py` (`compute_is`, `handle_tax_payment`) | tous les scripts depuis `canonical_run_and_reserve_share_sweep.py` |
| RESERVE_SHARE | **95%** (pas 80% par défaut) — testé 80/85/90/95%, 95% domine sans coût identifiable (scénario capitalisation pure, rien distribué) | `FINAL_RESERVE_SHARE = 0.95` |
| Risque en évaluation | **2,25%** pour toutes les firms SAUF GFT | `FINAL_EVAL_RISK = 2.25` |
| Risque une fois financé | **2,5%** pour toutes les firms | `FINAL_FLEET_RISK = 2.5` |
| Risque en évaluation, GFT spécifiquement | **1,75%** (DD journalier plus serré chez GFT → 2,7x plus de tentatives à 2,25%) | `gft_eval_risk_override` dans `extra_account_v3_gft_risk.py` |
| Mécanisme de croissance | **"Compte supplémentaire"**, PAS le Scaling Plan A1 ni l'ancien achat direct A2 (bug) — voir 0.3 | `extra_account_v3_gft_risk.py` |
| FundedNext | **Fixe à 1 seul compte, palier 200 000$** (plafond mono-compte réel, confirmé web + doc v3), pas de mécanisme de croissance pour cette firm | `FUNDEDNEXT_FIXED_PALIER = 200000.0` |

### 0.2 Chaîne de découvertes de la session (dans l'ordre, pour comprendre le pourquoi)

1. **Plateau de ruine à 30k$-150k$ expliqué** : au-delà de 30k$, augmenter le
   seuil de réserve est inutile — 100% des runs encore ruinés à 150k$
   n'atteignent JAMAIS ce seuil (Blueberry seul reste bloqué), 0% l'atteignent
   puis cassent quand même. Le vrai levier restant est le risque en
   évaluation, pas le tampon.
2. **Split 80% flat appliqué à la modélisation du risque de ruine pour la
   première fois** : fait bondir la ruine de référence de 7,00%/1,00% (v4,
   sans split) à 18,33%/4,17% — les anciens chiffres 7,00%/1,00% sont
   **obsolètes**.
3. **Downgrade-on-reopen découvert** : Blueberry, une fois scalé (25k→200k
   via l'ancien Scaling Plan, cf. point 6), coûtait 1000$ à racheter après
   une casse au lieu de 166$ (palier de base) — un quasi free-lunch : le
   forcer à toujours racheter au palier de base pendant la phase
   pré-déblocage réduit la ruine de ~4x en AUGMENTANT le profit de 9%.
4. **Grille de risque élargie (éval×flotte)** : optimum trouvé à
   éval=2,25%/flotte=2,5% (pas 1,25%/2,0% comme suggéré initialement par la
   découverte "risque réduit en éval" de v4 — ce chiffre a été affiné).
5. **Diagnostic P(année1<0)** : contre-intuitivement, réduire le risque en
   évaluation en dessous de 2,0% AGGRAVE P(année1<0) (ralentit le
   financement, prolonge la phase frais-sans-profit) — il existe un optimum
   intermédiaire, pas une relation monotone. Catégorie A (flotte débloquée
   mais déficit) domine à 62-72% des cas année1<0 ; catégorie B (Blueberry
   encore bloqué) le reste. ~73% du déficit catégorie A est de la variance de
   trading ordinaire, pas des postes isolables.
6. **🔴 DÉCOUVERTE MAJEURE — le mécanisme de scaling était un bug, pas juste
   une approximation.** Vérifié par recherche web (FTMO + Blueberry Funded,
   sources officielles) : le vrai Scaling Plan est **gratuit**, +25% tous les
   3-4 mois, sous condition de 10% de profit net sur la période. L'ancien
   code (`process_growth_upgrade`, utilisé PARTOUT dans le projet, pas
   seulement cette session) modélisait un **achat direct instantané**
   (payer 1000$/3000$ dès que la réserve suffit, saut direct 50k→200k→500k).
   Corrigé (`corrected_scaling_mechanism.py`) : **-60,5% de profit**
   (5 763 351$/5 817 008$ → 2 274 631$/2 298 627$), ruine quasi inchangée,
   P(année1<0) légèrement pire.
7. **Mécanisme alternatif "compte supplémentaire"** : au lieu de faire
   grossir un compte existant (exige qu'il survive 3-4 mois consécutifs
   profitables — irréaliste vu l'attrition ~7-9j entre casses), ouvrir un
   NOUVEAU compte séparé à un palier plus gros dès que la réserve a un
   surplus, en plus des comptes existants. Récupère ~60% du profit perdu
   (contre ~4% pour le vrai Scaling Plan) : 3 472 902$/3 508 220$. **Meilleur
   mécanisme réaliste trouvé.**
8. **FundedNext corrigé** : plafond mono-compte réel confirmé = 200 000$
   (web + doc v3, cohérent). Fixé à 1 seul compte 200k$ dès le départ, pas de
   "compte supplémentaire" pour cette firm (le multi-compte y est
   probablement interdit — cf. 0.4). → 3 733 658$/3 771 648$.
9. **Décomposition du coût "compte supplémentaire"** : GFT nécessite ~18,3
   tentatives d'évaluation avant financement (vs 8,5 FTMO/Blueberry) à cause
   de son DD journalier plus serré (4% vs 5%) — coût cumulé 7 664-7 714$.
   99,5% finissent quand même par réussir : c'est un coût de TEMPS, pas
   d'échec définitif. Une inefficacité mineure de prix a aussi été trouvée et
   corrigée (FTMO/GFT au palier 100k facturé 666$ au lieu du vrai prix
   sourcé 500$).
10. **Risque GFT réduit à 1,75%** : coupe son coût d'évaluation de 63%
    (7 664$→2 873$) pour -0,2 à -0,4% de profit global seulement. Adopté.
    → **3 733 811$/3 771 839$, chiffre final actuel.**
11. **Rampe post-financement testée (Partie B, incomplète)** : le compteur
    `trades_taken` qui détermine la fin de la rampe 2,0%→2,5% n'est **jamais
    réinitialisé** (ni au rachat, ni à la transition éval→financé) — un
    compte financé démarre quasi toujours à risque plein (2,5%), sans
    coussin. Une rampe post-financement dédiée (5 trades à 2,0% après
    financement) a été testée UNE FOIS (durée=5/risque=2,0%, pas de grille) :
    réduit ruine et P(année1<0) d'~1 point mais coûte 5,2-5,9% de profit —
    **pas retenue par défaut**. Grille complète (durées 2/3/5/8 ×
    risques 1,75/2,0/2,25%) demandée mais **jamais lancée** (session
    interrompue par la découverte du bug de scaling).

### 0.3 Bugs trouvés et corrigés cette session (au-delà du scaling)

- **`process_growth_upgrade` = achat instantané, pas le vrai Scaling Plan**
  (section 0.2 point 6) — bug le plus important, présent dans TOUT le projet
  avant cette session, pas seulement les scripts d'aujourd'hui.
- **`state["tax_breach_*"]` manquant** dans 3 scripts (`risk_sweep_and_year1.py`,
  `year1_negative_diagnosis.py` avant fix, `corrected_scaling_mechanism.py`,
  `extra_account_vs_scaling.py`) — crash `KeyError` sur dépassement de
  plafond pendant un paiement d'IS. Corrigé partout. N'a jamais faussé de
  résultat déjà cité (c'est un crash, pas une corruption silencieuse) mais a
  fait échouer certains runs qui ont dû être relancés.
- **Coût FTMO/GFT au palier 100k surfacturé** (666$ au lieu de 500$ sourcé)
  dans le mécanisme "compte supplémentaire" — corrigé dans
  `extra_account_v3_gft_risk.py`.

### 0.4 Point ouvert critique jamais résolu : FundedNext

**FundedNext repose sur une clarification support jamais obtenue depuis le
07/08 v3** : la restriction de copytrade évoquée par le support n'a jamais
été confirmée dans sa portée exacte. Hypothèse retenue cette session (08/08,
logique mais NON confirmée par support) : la restriction ne peut concerner
que la copie ENTRE plusieurs comptes FundedNext, pas entre FundedNext et
d'autres firms — d'où la décision de garder FundedNext mais de le limiter à
1 seul compte (200k$, son plafond mono-compte réel). **Tous les chiffres de
profit de cette session (07/08 et 08/08) incluent FundedNext comme 9e/10e
compte actif.** Si la clarification support s'avère plus restrictive,
recalculer sans FundedNext.

Mémoire : `project_fleet_structure_5firms_fundednext_unconfirmed.md`.

---

## 1. Scripts de référence, dans l'ordre logique (le dernier de chaque famille est la source de vérité)

**Diagnostic ruine/plateau** :
- `ruin_plateau_and_scenario_b.py` — diagnostic plateau 30k-150k + grille
  scénario B initiale (eval×flotte, AVANT le combo final retenu)
- `reopen_downgrade_test.py` — découverte downgrade-on-reopen

**Config canonique + sensibilité** :
- `canonical_run_and_reserve_share_sweep.py` — premier run combinant tous
  les leviers + IS réel ; sweep RESERVE_SHARE 80-95% → 95% retenu
- `risk_sweep_and_year1.py` — grille éval×flotte élargie (30 combos), retenu
  éval2,25%/flotte2,5%
- `year1_negative_diagnosis.py` — décomposition catégorie A/B de
  P(année1<0)
- `postfunding_ramp_test.py` — test unique (pas grille) de la rampe
  post-financement, non retenu

**⚠️ Correction majeure du mécanisme de scaling (LIRE AVANT TOUT AUTRE
CHIFFRE DE PROFIT)** :
- `corrected_scaling_mechanism.py` — le vrai Scaling Plan A1 (gratuit, gated
  durée+profit) — remplace l'ancien mécanisme buggé partout dans le projet
- `extra_account_vs_scaling.py` — mécanisme alternatif "compte
  supplémentaire", v1 (FundedNext inclus dans le mécanisme, pas encore fixé)
- `extra_account_confirm.py` — confirmation n=600 de v1
- **`extra_account_v2_fundednext_fixed.py`** — FundedNext fixé à 200k
  mono-compte + diagnostic du coût d'échec de challenge
- **`extra_account_v3_gft_risk.py`** — **SCRIPT FINAL ACTUEL** : corrige le
  coût FTMO/GFT (500$ au lieu de 666$) + risque GFT réduit à 1,75% —
  `run_one`/`run_propagated` de ce fichier sont la référence à réutiliser
  pour toute suite
- `gft_confirm.py` — confirmation n=600 du combo GFT=1,75% vs baseline

## 2. Points ouverts, par priorité

1. **[HAUTE] Partie B non terminée** : grille complète rampe post-financement
   (durées 2/3/5/8 trades × risques 1,75/2,0/2,25%) jamais lancée — seul un
   point (5/2,0%) a été testé, sur l'ANCIEN mécanisme de scaling (avant la
   découverte du bug). À refaire sur `extra_account_v3_gft_risk.py` si jugée
   encore pertinente après tous les changements.
2. **[HAUTE] Partie C jamais commencée** : 2 leviers ciblés sur les causes de
   P(année1<0) — (1) déblocage partiel anticipé (débloquer FTMO seul à un
   seuil de réserve réduit 10k/15k/20k, reste gaté à 30k) ciblant la
   catégorie B ; (2) étalement léger du déblocage groupé (1/2/4 semaines
   entre chaque groupe au lieu d'instantané) ciblant la catégorie A. Jamais
   testés, diagnostic (`year1_negative_diagnosis.py`) toujours valide comme
   base pour les concevoir.
3. **[HAUTE] FundedNext non confirmé par support** (section 0.4) — décision
   humaine ou nouvelle clarification support nécessaire avant capital réel.
4. **[MOYENNE] Compte supplémentaire limité à 1 par firm** — pas
   d'empilement testé (plusieurs comptes supplémentaires successifs par
   firm). Pourrait capturer plus de profit, non mesuré.
5. **[MOYENNE] Split prop firm** : toujours approximé à 80% flat, aucun
   barème exact par firm/palier jamais sourcé.
6. **[BASSE, HÉRITÉ v4] Écart code live non appliqué** : `app.py`/`app_mt5.py`
   n'ont TOUJOURS reçu aucune des découvertes de risque depuis le 06/08.
   Argent réel en jeu, décision explicite à prendre avant tout lancement.
7. **[BASSE] Frictions d'exécution réelles** : toujours non mesurables,
   `trades_reels.csv` toujours vide.

## 3. Mémoire persistante à consulter (fichiers dans memory/)

- `project_fleet_structure_5firms_fundednext_unconfirmed.md` — structure 5
  firms + statut FundedNext non confirmé (section 0.4 ci-dessus)
- `project_ruin_risk_and_mitigation_2026-08-07.md` — découverte initiale du
  risque de ruine (SUPERSEDED sur les chiffres exacts par cette v5, mais le
  mécanisme causal décrit reste valide)
- `project_final_config_and_open_points_2026-08-07.md` — SUPERSEDED sur
  ruine/profit (voir v5), toujours valide pour fiscalité SASU générale/
  holding/plafond progressif
- Toute mémoire antérieure citant un chiffre de profit/ruine sans préciser
  "après correction du scaling" ou "après compte supplémentaire" est
  probablement obsolète — vérifier contre la section 0.1 de ce document.
