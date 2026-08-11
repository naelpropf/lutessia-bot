# Registre des paramètres du projet Lutessia — chantier multi-format

*Document vivant, à mettre à jour après CHAQUE session future (pas juste
créé une fois). Construit le 2026-08-09 en scannant tous les fichiers
`project_*.md` (mémoire), tous les `etape_*.md`/`contexte_projet_*.md`
(repo racine), et `MEMORY.md`. Objectif : un point d'entrée unique pour
savoir (a) quelle est la valeur actuelle d'un paramètre et si elle est
négociable, (b) si une idée a déjà été testée avant de la re-tester,
(c) quelles contraintes sont réelles vs des choix de modélisation.*

**Comment mettre à jour** : après une session qui change un paramètre ou
teste un nouveau levier, ajouter/modifier la ligne correspondante ici
(pas un nouveau fichier séparé — ce fichier-ci EST la table vivante,
contrairement aux rapports `etape_*.md` qui restent figés une fois
écrits). Toujours dater la modification et citer la session source.

**Dernière mise à jour** : 2026-08-11 (consolidation finale avant clear
de contexte — note critique ajoutée en §1.8 précisant explicitement que
le cycle de payout (§2.26) N'EST PAS inclus dans la référence officielle
et détaillant les 4 points de vérification méthodologique restants
avant adoption possible ; statuts exacts des décisions #2 et #9
clarifiés sans ambiguïté ; tableau récapitulatif §2.27 de toutes les
pistes rejetées cette session avec raison précise et condition de
réouverture, pour éviter tout retest accidentel)

**Mise à jour précédente** : 2026-08-10 nuit, suite 13 (cycle de payout
réaliste implémenté pour Blueberry/GFT/Fivers, confirmés par support
comme ne préservant PAS le profit à la casse — §2.26. Candidat corrigé
5 510 750$/1000$ (-3,94%, année1<0 +5,84pt) / 5 539 307$/3000$ (-3,68%,
+5,67pt), décomposé par firm (Fivers 42%/Blueberry 40%/GFT 18%, 99,6%
post-déblocage). Goat Guard et V2 tous deux reconfirmés valides sous la
correction. PAS encore adopté §1.8, décision #13 en attente)

**Mise à jour précédente** : 2026-08-10 nuit, suite 12 (pas de double
comptage confirmé §2.21 — cumulative_since_reset/reserve sont deux
accumulateurs séparés ; écart profit année1<0/>0 confirmé ~27% sous
moteur corrigé §2.22 ; resweep éval au-delà de 1,25% : pas de free
lunch net, point de retournement 1,75-2,50%, proche d'un vrai gain à
2,00%/3000$ sans être écrasant §2.23 ; casses pré/post par firm
chiffrées §2.24 ; politique casse/payout des 5 firms recherchée et
sourcée §2.25)

**Mise à jour précédente** : 2026-08-10 nuit, suite 10 (🔴 seuil copytrade
Fivers 500k$ dépassé dans 99,2-99,7% des runs REF+V2, jusqu'à 12× le
seuil §2.20 — diagnostic seul, décision de modélisation en attente §4#12
; mécanisme de casse/reset fleet-wide vérifié CORRECT §2.21, aucune
perte de profit à la casse, aucune correction nécessaire)

**Mise à jour précédente** : 2026-08-10 nuit, suite 9 (caps $ FTMO/GFT
vérifiés propres par lecture de code, aucun écart — cap $ FundedNext
jamais confirmé, ni web ni support, nouveau point ouvert §5 ; extension
du mécanisme extra-compte à Fivers testée §2.19 — effet NUL par
construction, cap capital bloque toute croissance avant même de
solliciter la réserve, piste fermée dans sa forme actuelle)

**Mise à jour précédente** : 2026-08-10 nuit, suite 7 (feu vert
utilisateur reçu — cap Blueberry corrigé ADOPTÉ comme référence
officielle §1.8 : 5 736 759$/1,00%/21,83% à 1000$, +16,41% vs l'ancien
chiffre, provenance = correction de paramètre documentée explicitement,
conditionnelle à éval=1,25% ; piste A'/BBx2 documentée comme option
3000$ non adoptée par défaut ; piste B/fongibilité FERMÉE DÉFINITIVEMENT
§2.8 ; décisions §4 actualisées — seules #2 éval et #9 plafond restent
bloquantes)

**Mise à jour antérieure** : 2026-08-10 nuit, suite 4 (cap Blueberry
450k$/3-comptes vérifié empiriquement §2.16 : le cap $ n'est JAMAIS
sollicité — zéro impact, correction cosmétique — mais le cap NOMBRE=3
EST sollicité dans 92,7-100% des runs testés, sous-estimation
structurelle potentielle de Blueberry non quantifiée dans REF+V2)

**Mise à jour précédente** : 2026-08-10 nuit, suite 3 (conflit Blueberry
RÉSOLU par contact support direct §1.3/§4#6 : pas de limite de comptes,
cap 400k$ ; piste A' implémentée et CONFIRMÉE n=600+cascade GO à
ceiling=3000$ §2.15, rejetée à 1000$)

**Mise à jour précédente** : 2026-08-10 nuit (REF+V2+FTMO-10%/GoatGuard
adopté comme référence courante à 1000$ ; éval=1,00% vs 1,25% devient
bloquant §4#2 ; vrai mécanisme de ruine BB+GFT identifié §2.11 ; piste H
rejetée + seuil FTMO reconfirmé §2.12 ; conflit Blueberry comptes
non résolu §4#6)

---

## 1. Registre des paramètres

**Statut** : VERROUILLÉ = contrainte réelle de prop firm non-négociable
(pas un choix de simulation) · LIBRE = variable encore ajustable sans
coût d'implémentation particulier · SEMI-LIBRE = ajustable mais implique
un coût d'implémentation réel (ex. changer de format = restructurer le
moteur de compte).

### 1.1 Risque

| Paramètre | Valeur actuelle | Catégorie | Statut | Confiance | Session où fixé | Déjà testé autour de |
|---|---|---|---|---|---|---|
| Risque éval (challenge) | **1,25%** (profit max) — alternative 1,00% (recommandé, meilleur profil cascade) | risque | LIBRE | élevée (n=600+cascade GO les deux) | 08/09 (Étape E verrouillage) | 1,00 à 2,50% (grille 7 valeurs, chantier1 08/09) |
| Risque flotte (financé) | **1,90%** | risque | LIBRE | élevée (reconfirmé indépendamment 3×) | 08/09 (audit initial, reconfirmé chantier1 avec reset actif) | 1,50 à 2,75% (grille 6 valeurs) — flotte≥2,25% systématiquement pire, zone haute (éval≥1,75%) n'a jamais dominé la zone basse aux deux plafonds |
| Risque éval GFT | **1,75%** | risque | LIBRE | élevée (reconfirmé quasi-optimal sous nouveau moteur) | 08/08 (initial), reconfirmé 08/09 | 1,00 à 2,75% |
| Rampe post-financement (RAMP_RISK) | **désactivée** (aucune rampe dans le moteur intégré actuel) | risque | LIBRE | élevée | 08/09 | 2,0% global (rejeté, net négatif) ; 1,50/1,70% ciblée restart-only (rejeté, neutre) |
| Risque dégressif fin de phase | **désactivé** | risque | LIBRE | élevée | 08/09 | fenêtre 10-20% / facteur 0,5-0,7 (rejeté, neutre à négatif) |

### 1.2 Seuils de déblocage (réserve fleet-wide, sauf mention)

| Firm | Seuil actuel | Catégorie | Statut | Confiance | Session où fixé | Déjà testé autour de |
|---|---|---|---|---|---|---|
| FTMO | **1 000$** | seuil | LIBRE | élevée (reconfirmé robuste, écarts <0,5% = bruit) | 08/08 | 0/250/500/1000/2000/2500/5000$ — 0$ nettement délétère (ruine ×4) |
| The5%ers (Fivers) | **15 000$** | seuil | LIBRE | élevée (reconfirmé robuste) | 08/08 | grille staggered 08/08, reconfirmé 08/09 |
| GFT | **25 000$** | seuil | LIBRE | élevée (reconfirmé robuste) | 08/08 | idem |
| FundedNext | **25 000$** (prudent) — alternative **5 000$** (+2,1-2,3% profit, ruine ~2× mais ≤2% absolu) | seuil | LIBRE | élevée sur les deux chiffres, **décision non tranchée** | 08/09 (audit thresholds+GFT) | 5k/25k/30k, cascade GO dans les deux cas |
| Cadencement continu extra-comptes (délai mini entre ouvertures) | **aucun** (délai=0) | seuil | LIBRE | élevée | 08/09 | 1/2/3 semaines — quasi inerte, le rythme naturel de réserve est déjà plus lent |
| Plafond nb comptes supplémentaires (FTMO/GFT) | **non plafonné** (limité par le cap $ réel seulement) | cap | SEMI-LIBRE | élevée | 08/08 (déplafonnement) reconfirmé 08/09 | cap=1/2/4 extra/firm — cap=1 réduit le risque post-déblocage mais coûte -30,2% profit (arbitrage défavorable, rejeté) |

### 1.3 Caps réels confirmés (capital total $ et/ou nombre de comptes)

| Firm | Cap $ | Cap nb comptes | Statut | Confiance | Source |
|---|---|---|---|---|---|
| Blueberry | **400 000$ "capital simulé total" par trader/foyer** — **CONFIRMÉ 2026-08-10 par contact direct support Blueberry (chat live)**, réponse verbatim : *"There is no fixed limit on the number of active accounts you can run at the same time. The main restriction is the total simulated capital. Maximum allocation per trader/household: $400,000 total. You can split that across any number of accounts (for example: 4 × $100k, or 2 × $200k)... Also, one person can have up to 4 accounts on the same device/IP."* Remplace les deux anciennes valeurs (450 000$ web/2 000 000$ PDF légal — **ni l'une ni l'autre confirmée exacte, entrées conservées ci-dessous par transparence, considérer PÉRIMÉES**). | **PAS de limite fixe de nombre de comptes** — seul le cap $ compte, confirmé sans ambiguïté 2026-08-10. Remplace l'ancienne entrée "3 comptes financés simultanés max" (source secondaire, jamais confirmée par un contact support direct comme celui-ci — considérer PÉRIMÉE). **⚠️ Point de vigilance distinct** : Blueberry limite néanmoins à **4 comptes max sur le même device/IP** — non engageant pour piste A' (2 comptes) mais à surveiller si une architecture future dépasse 4 comptes Blueberry simultanés (ex. copytrade multi-device à prévoir). | VERROUILLÉ | **élevée** (contact support direct, verbatim daté, remplace les sources web contradictoires) | Contact direct support Blueberry, chat live, **2026-08-10** — voir `project_blueberry_account_limit_conflict_2026-08-10.md` (memory, à mettre à jour comme résolu) |
| ~~Blueberry (ancien, PÉRIMÉ)~~ | ~~450 000$ (web) ou 2 000 000$ "per trader" (PDF légal, ambigu)~~ | ~~3 comptes financés simultanés max~~ | **PÉRIMÉ 2026-08-10** | — | conservé pour l'historique de la chaîne de correction uniquement, ne plus citer |
| FTMO | **400 000$**, pas de limite de nombre de comptes | — | VERROUILLÉ | moyenne (ambigu si financé-seul ou +éval) | `project_real_firm_caps_confirmed_2026-08-08.md` |
| GFT | **400 000$**, pas de limite de nombre | — | VERROUILLÉ | élevée | idem |
| The5%ers (Fivers) | **500 000$** — codé dans le moteur SANS marge de sécurité (l'utilisateur avait mentionné vouloir une marge ~400k$, jamais appliquée) | 4 comptes fixes (pas de mécanisme extra) | VERROUILLÉ sur le cap, **LIBRE non exploité** sur la marge de sécurité | moyenne (corroboré support, pas de page officielle unique) | `project_etape_ab_multiformat_engine_2026-08-08.md`, etape_a §0bis/§8 — **point ouvert non résolu** |
| FundedNext | 300 000$ entre comptes FundedNext (non contraignant, un seul compte 200k utilisé) | 1 compte (200k, pas de croissance) | VERROUILLÉ | élevée | etape_a §5-6 |

### 1.4 Paliers (taille de compte) par firm et par format

| Firm | Palier jour-0/base | Palier "extra" (comptes supplémentaires) | Palier format rapide (si différent) | Statut | Confiance |
|---|---|---|---|---|---|
| Blueberry | 25 000$ | 50 000$ (base×2) | **identique** (25 000$, taille indépendante du format dans ce moteur) | LIBRE (taille), VERROUILLÉ (pas de mécanisme de croissance individuelle) | élevée |
| FTMO | 50 000$ | 100 000$ | identique (50 000$) | idem | élevée |
| GFT | 50 000$ | 100 000$ | identique (50 000$) | idem | élevée |
| FundedNext | 200 000$ (fixe, `FUNDEDNEXT_PALIER`) | N/A (pas de comptes extra) | identique | VERROUILLÉ | élevée |
| The5%ers | 100 000$ (High Stakes/REF) | N/A (pas de comptes extra) | **40 000$** (Hyper Growth — SEUL cas où le palier varie réellement par format, taille max confirmée testée à l'Étape A) | VERROUILLÉ (Hyper Growth réellement plus petit) | moyenne (source Étape A) |

*Constantes mécaniques* : `EXTRA_ACCOUNT_MULT=2,0` (taille extra = base×2) · `EXTRA_THRESHOLD_MULT=3,0` (réserve requise = 3× coût du compte extra) · `DEFAULT_EMERGENCY=300$` (capital bootstrap Blueberry pré-déblocage) · `FINAL_RESERVE_SHARE=0,95` (part des gains funded versée en réserve).

### 1.5 Coûts de reopen / reset / downgrade

| Mécanisme | Coût | Applicable à | Statut | Confiance | Notes |
|---|---|---|---|---|---|
| Downgrade-on-reopen (Blueberry STARTER, pré-déblocage) | N/A — **no-op structurel confirmé** | Blueberry avant déblocage complet | VERROUILLÉ (par design du moteur) | élevée | Aucune croissance individuelle de palier n'existe dans le moteur → le "downgrade" réaffirme juste la valeur déjà en place, ne change jamais rien en pratique. Source : notes de conception `etape_e_fleet_integration.py`, confirmé `project_etape_e_fleet_integration_2026-08-08.md`. |
| Reset Blueberry (compte déjà financé) | **2× prix challenge original** = 2×165$ = **330$** (Prime2Step, palier 25k) | Blueberry financé, format Prime2Step (phasé) uniquement | SEMI-LIBRE (mécanisme réel, implémenté) | élevée sur l'existence/mécanique (verbatim support), moyenne sur les exclusions détaillées (page officielle bloquée en fetch direct) | **Usage unique à vie par compte**, exclu pour instant funding et comptes "scaled" (sans objet ici, aucun compte du moteur ne scale). Skip P1/P2, reprend direct au niveau financé. 330$ calculé (`2.0 × acc["base_cost"]`), pas un nombre codé en dur trouvé tel quel dans un fichier narratif — recalculé ici depuis le prix Prime2Step 25k=165$ (`engine_multiformat.py FORMATS["Blueberry_Prime2Step"]`). |
| Reopen Instant Elite (Blueberry) | **800$** plein tarif, à chaque casse, pas de rabais | Blueberry format instant (Chantier 2 uniquement) | VERROUILLÉ (prix réel du format) | élevée (vérifié par citation de code, aucun bug de coût) | Exclu du reset ci-dessus (instant funding non éligible) |
| FTMO -10% rachat <24h | -10% sur le coût de restart FTMO (toute casse, éval ou financé) | FTMO, toute casse | SEMI-LIBRE (implémenté, testé, **confirmé n=600**) | élevée sur la source, élevée sur le résultat | Effet isolé confirmé n=600 : +0,17%/+0,04% profit, ruine égale ou meilleure — quasi mécanique comme attendu, rabais pur sans downside |
| GFT Goat Guard | 1ère casse potentielle → split réduit à 50% pendant 30j (non sourcé, choix du projet) au lieu d'une casse ; 2e occurrence → casse réelle | GFT financé (2-Step, exclut instant funding) | SEMI-LIBRE (implémenté avec approximation documentée, **confirmé n=600**) | **moyenne-faible** sur le mécanisme (le moteur n'a pas de courbe de flottant intra-trade, le vrai déclencheur -2% est approximé par "le trade qui ferait franchir le DD max", ce qui SOUS-ESTIME probablement la fréquence réelle) — élevée sur le résultat mesuré | Effet isolé confirmé n=600 : +1,04%/+1,04% profit, ruine inchangée, casse≤30j -1,78pt (mieux), année1<0 +0,34pt (bruit). **Combiné avec (a) : +1,21%/+1,07% profit, cascade GO — candidat nouveau chiffre de référence, non encore adopté (décision utilisateur en attente)** |
| Downgrade-on-reopen (formats instant, générique) | N/A — no-op (même raison que ci-dessus) | tout compte instant funding | VERROUILLÉ | élevée | |

### 1.6 Formats retenus par firm (config REF actuelle vs WINNER Étape D, rejeté)

| Firm | Format REF (actuel) | Format WINNER (Étape D, rejeté à l'Étape E) |
|---|---|---|
| FTMO | FTMO 2-Step Swing | FTMO 1-Step |
| The5%ers | High Stakes | Hyper Growth |
| Blueberry | Prime Challenge (2-Step) | Instant Elite |
| GFT | 2-Step GOAT Model | Instant GOAT |
| FundedNext | Stellar Lite (2-Step) | Stellar 1-Step |

Statut : LIBRE en théorie (le moteur multi-format permet n'importe quelle
combinaison), mais **SEMI-LIBRE en pratique** — tout changement de format
nécessite un re-balayage complet du risque (leçon du Chantier 1) et,
comme démontré au Chantier 2, un changement de format n'est jamais un
levier "gratuit" (interactions structurelles avec le risque éval/flotte
et avec le mécanisme de reset Blueberry).

### 1.7 Fiscal (`split_tax_model.py`, inchangé depuis 08/07)

| Paramètre | Valeur | Statut | Confiance |
|---|---|---|---|
| Seuil acompte IS | 3 000€ | VERROUILLÉ | élevée |
| Taux IS (bas/haut) | 15% / 25% | VERROUILLÉ | élevée |
| Tranche IS | 42 500€ | VERROUILLÉ | élevée |
| Fraction acompte trimestriel | 25% de l'IS N-1 | VERROUILLÉ | élevée |
| Offsets calendaires acomptes | ~jours 73,5/165,5/257,5/348,5 (mars/juin/sept/déc) | VERROUILLÉ | élevée |
| Offset solde IS | ~jour 105 (mi-avril) | VERROUILLÉ | élevée |
| PASS 2026 | 48 060€/an | VERROUILLÉ | élevée |
| Ratio net/charges SASU président | ~74-75% stable sur la tranche 30-100k€ | VERROUILLÉ | élevée |
| Split FTMO 80%→90% | Seuil binaire (Scaling Plan / Premium), pas graduel | VERROUILLÉ | élevée |
| Split The5%ers max | 100% (pas 90%), varie 50-80% en démarrage selon programme | VERROUILLÉ | élevée |

### 1.8 Chiffres de référence actuels

**🔴🆕 Mise à jour 08/11 (session c) — cadence corrigée CONFIRMÉE n=600
(ferme le point ouvert §2.32/§4#16), Run F (Blueberry 7j) testé n=600 en
CASCADE CHECK EXPLICITE — verdict MIXTE, PAS une dominance stricte, PAS
promu en tête de référence.** Scripts : `etape_ai_payout_cadence_
calibration_2026-08-11.py` (Run C) / `etape_ao_run_f_cout_reel_2026-08-11
.py` (Run F), n=600, seed=9999 identique aux deux, deux plafonds. Durée :
~7,5 min/script (462s/461s mesurés). Résultats bruts sur disque (non
suivis par git, `*.csv` gitignoré projet entier sauf `correlation_matrix
.csv` — même convention que les ~100 autres CSV `etape_*` du dépôt) :
`etape_ai_payout_cadence_calibration_n600.csv`,
`etape_ao_run_f_cout_reel_n600.csv`.

**Étape 1 — Run C (cadence par firm corrigée §2.32, population 721,
payout actif, PAS de Blueberry 7j) : n=600 confirme le n=300, devient la
NOUVELLE RÉFÉRENCE OFFICIELLE, remplace la ligne 08/11 non corrigée
ci-dessous (bug de cadence, §2.32) :**

| Plafond | Profit moyen/médian | solde_negatif_annee4 | hit_ceiling_pct | Année1<0 |
|---|---|---|---|---|
| **1000$** | **5 491 410$ / 5 361 009$** | **1,50%** | **3,50%** | **35,50% (pré=13,83%)** |
| **3000$** | **5 542 103$ / 5 368 386$** | **0,17%** | **1,33%** | **35,33% (pré=13,50%)** |

⚠️ Année1<0 à n=600 (35,50%/35,33%) est SENSIBLEMENT plus élevé que
l'estimation n=300 (32,67%/32,67%, §2.32) — encore un cas où n=300
sous-estime ce métrique bruité (même leçon que pour d'autres leviers
dans ce registre), justifiant a posteriori la convention n=600 pour toute
adoption finale. Ce chiffre n=600 est maintenant LA référence officielle
du projet, remplaçant 5 444 513$/5 494 348$ (36,83%/36,67%) ci-dessous,
qui restait affiché avec un bug de cadence non corrigé.

**Étape 2 — Run F (Blueberry 7j, coût réel +20% intégré, §2.35) : n=600,
CASCADE CHECK COMPLET (4 axes, pas seulement profit+année1<0 comme dans
le tableau initial §2.35) :**

| Plafond | Profit moyen/médian | solde_negatif_annee4 | hit_ceiling_pct | Année1<0 |
|---|---|---|---|---|
| 1000$ | 5 505 336$ / 5 400 317$ | 2,33% | 5,83% | 33,83% (pré=12,83%) |
| 3000$ | 5 589 954$ / 5 457 443$ | 0,33% | 1,33% | 32,83% (pré=11,83%) |

**Comparaison directe Run F vs Run C, même seed, n=600 :**

| Axe | 1000$ | 3000$ |
|---|---|---|
| Profit moyen | **+13 926$ (+0,25%)** ✅ | **+47 851$ (+0,86%)** ✅ |
| Profit médian | **+39 308$ (+0,73%)** ✅ | **+89 057$ (+1,66%)** ✅ |
| Année1<0 | **-1,67pt (mieux)** ✅ | **-2,50pt (mieux)** ✅ |
| solde_negatif_annee4 | **+0,83pt (PIRE)** ❌ | +0,16pt (pire, marginal) ❌ |
| hit_ceiling_pct | **+2,33pt (PIRE, quasi ×1,7)** ❌ | 0,00pt (identique) — |

**Verdict cascade check : PAS UNE DOMINANCE STRICTE — un vrai
arbitrage, pas un free lunch.** Sous le standard utilisé partout ailleurs
dans ce registre pour un "GO" (domination stricte sur les 3 axes profit/
ruine/année1<0, ex. BBx2 §2.18), Run F échoue : il améliore le profit et
année1<0 aux deux plafonds, mais **dégrade solde_negatif_annee4 aux deux
plafonds et fait quasiment exploser hit_ceiling_pct au plafond 1000$
(3,50%→5,83%, +67% relatif)** — ce n'est PAS du bruit d'échantillonnage :
le même écart (~+2,3pt hit_ceiling à 1000$, ~0pt à 3000$) est déjà présent
et de même ampleur à n=300 (Run C n=300 : 3,33%/1,67% ; Run F n=300 :
5,67%/1,67% — voir `etape_ao_run_f_cout_reel_n300.csv`), stable entre les
deux tailles d'échantillon. **Ce tradeoff existait déjà à n=300 mais
n'avait jamais été rapporté dans §2.35** (le tableau original ne
comparait que profit et année1<0) — corrigé ici, voir §2.35 mise à jour.

**Mécanisme cohérent, visible directement dans les colonnes de
forfeiture** : le passage à 7j réduit bien la forfeiture Blueberry comme
conçu (pré+post déblocage : ~57 000$/run en moyenne sous Run C →
~6 500$/run sous Run F, -89%, l'effet recherché fonctionne) — mais le
surcoût +20% appliqué à CHAQUE achat/rachat Blueberry (jour 0, reset,
compte extra) pèse plus sur la trésorerie tendue du plafond 1000$,
produisant plus d'épisodes `hit_ceiling`. Le levier échange donc du
risque de forfeiture ponctuelle contre du risque de tension de cash
généralisée — un vrai choix de profil de risque, pas une amélioration
gratuite.

**Décision : Run F N'EST PAS promu comme référence officielle par
défaut** (la référence officielle du projet reste Run C, étape 1
ci-dessus). Documenté comme option validée n=600+cascade, avec un
compromis explicite (meilleur profit/année1<0, pire ruine/hit_ceiling
notamment à 1000$) — adoption laissée à une décision utilisateur
explicite sur la préférence de risque, pas une clôture automatique. Voir
décision #16 §4 (mise à jour, PAS marquée ✅ ADOPTÉ).

---

**Historique (contenu 08/11 session b, conservé tel quel ci-dessous pour
traçabilité — la "RECONSTRUCTION COMPLÈTE" et son tableau de référence
sont maintenant SUPERSEDED par l'étape 1 ci-dessus, cadence par firm
corrigée §2.32)** :

**🆕 Mise à jour 08/11 — RECONSTRUCTION COMPLÈTE, décision #15 (renommage
métriques) appliquée dans le REPORTING.** À partir de cette entrée, deux
métriques de risque distinctes sont rapportées côte à côte, **jamais l'une
en remplacement de l'autre** (investigation §2.31) :
- **`solde_negatif_annee4`** (ex-"ruine") = profit net négatif à la fin
  des 4 ans simulés. Renommé car ce nom ne correspond PAS à un blocage de
  cash ni à un état irréversible — juste un résultat final défavorable.
- **`hit_ceiling_pct`** (nouveau, jamais rapporté avant le 08/11) = le
  plafond personnel a été entièrement consommé au moins une fois durant
  le run (`state["hit_ceiling"]`). Pas irréversible non plus — 65-70% des
  cas récupèrent (§2.31).
Renommage appliqué à la **couche de reporting du nouveau script de
référence uniquement** (`etape_ah_reference_officielle_2026-08-11.py`,
`summarize()`) — le moteur de calcul (`ruine`/`state["hit_ceiling"]` en
interne) et les ~100 scripts `etape_*.py`/`point*.py` historiques déjà
figés ne sont PAS retouchés (convention "un rapport déjà écrit reste
figé" + hors périmètre demandé). Toute mention de "ruine" dans les
sections §2.x antérieures à cette entrée garde son sens d'origine
(net<0 an4) sans renommage rétroactif.

**Corrections maintenant incluses dans la référence officielle** (les
trois n'étaient PAS toutes réunies avant le 08/11) :
1. **Population 721 trades** (`historique_lutessia_15k_force.csv`, §2.29/
   §4#14) — remplace le fichier périmé 646 trades, corrigé dans le code
   depuis le 08/11 (`rr_threshold_test.py:37`).
2. **Cycle de payout/forfeiture activé** (`payout_cycle=True`, §2.26) —
   Blueberry/GFT/Fivers ne préservent plus le profit en attente à la
   casse ; l'utilisateur confirme retirer manuellement dès déblocage du
   cycle 14j, rendant le modèle automatique un proxy valide.
3. **Config combo V2+FTMO-10%/GFT Goat Guard appliquée IDENTIQUEMENT aux
   DEUX plafonds** (1000$ ET 3000$) — ⚠️ **changement de convention vs
   avant** : jusqu'ici 3000$ utilisait "REF pure" (sans V2, cf. ancien
   §1.8 ci-dessous) car V2 n'y apportait pas de gain isolé. L'utilisateur
   a explicitly demandé la même config complète aux deux plafonds pour
   cette reconstruction du 08/11 — les anciennes lignes "REF pure 3000$"
   restent documentées ci-dessous pour référence historique mais ne sont
   plus la config par défaut à 3000$.

Cap Blueberry corrigé (`FIRM_MAX_ACCOUNTS["Blueberry"]=None`/
`FIRM_CAPITAL_CAP["Blueberry"]=400000`) et éval=1,25%/flotte=1,90%
inchangés (toujours **conditionnel à éval=1,25%**, décision #2 §4
toujours ouverte).

| Référence | Profit moyen/médian | solde_negatif_annee4 | hit_ceiling_pct | Année1<0 | Statut |
|---|---|---|---|---|---|
| ~~RÉFÉRENCE — plafond 1000$~~ | ~~5 444 513$ / 5 324 652$~~ | ~~1,50%~~ | ~~3,50%~~ | ~~36,83%~~ | **SUPERSEDED 08/11 session c** — bug de cadence PAYOUT_CYCLE_DAYS non corrigé (§2.32), remplacé par Run C n=600 confirmé en tête de §1.8 (5 491 410$/35,50%) |
| ~~RÉFÉRENCE — plafond 3000$~~ | ~~5 494 348$ / 5 334 690$~~ | ~~0,17%~~ | ~~1,33%~~ | ~~36,67%~~ | **SUPERSEDED 08/11 session c** — idem, remplacé par 5 542 103$/35,33% |

**Cascade check — décomposition des 2 corrections vs la référence
08/10 précédente** (baseline `ref` n=600 646-trades sans payout,
`etape_ae_payout_ablations_n600.csv` ligne `ref` = 5 736 759$/1000$,
21,83% ; `corrige` = payout seul = 5 510 750$/1000$, 27,67% ;
`etape_af_pop721_impact_2026-08-11.py` n=300 = pop seule =
5 747 336$/1000$, 26,00%) :

| Correction | Profit 1000$ | Δ profit | Année1<0 1000$ | Δ année1<0 |
|---|---|---|---|---|
| Baseline (646, sans payout) | 5 736 759$ | — | 21,83% | — |
| + payout seul | 5 510 750$ | -3,94% | 27,67% | +5,84pt |
| + population 721 seule (n=300) | 5 747 336$ | -3,50% | 26,00% | +4,33pt |
| **Combiné (référence 08/11)** | **5 444 513$** | **-5,09%** | **36,83%** | **+15,00pt** |

⚠️ **L'effet combiné sur année1<0 est plus que la somme des deux effets
isolés** (+15,00pt observé vs ~+10,17pt en additivité naïve) — pas un
signe de bug (config vérifiée : population=721 confirmée, cap Blueberry
confirmé, mécanisme payout smoke-testé séparément §2.28), mais une
**interaction réelle plausible non quantifiée avant ce jour** : une
population légèrement moins favorable ralentit l'accumulation de
réserve, ce qui rend le cycle de payout 14j plus susceptible de perdre
du profit en attente à la casse avant d'avoir pu le verser — les deux
corrections se renforcent l'une l'autre au lieu de s'additionner
simplement. Pas d'investigation plus poussée faite à ce stade — signalé
explicitement plutôt que lissé.

**🔴 MISE À JOUR 08/11 (même session, plus tard) : cause de l'interaction
identifiée.** §2.32 a trouvé et corrigé un bug de calibration
(`PAYOUT_CYCLE_DAYS` constante unique au lieu d'une cadence par firm —
GFT tournait à 14j au lieu de 3j/1,5j réels). Run C recalculé (n=300,
cadence corrigée) : année1<0 **32,67%/32,67%** (vs 36,83%/36,67%
ci-dessus) — explique la quasi-totalité de l'écart "en trop" (§2.32 pour
le détail complet, §2.33 pour un test complémentaire qui réfute
l'hypothèse "rythme de versement" comme cause indépendante).

**✅ 08/11 session c : n=600 relancé, confirmé.** Année1<0 à n=600
(35,50%/35,33%, voir l'encadré tout en haut de §1.8) est plus élevé que
l'estimation n=300 ci-dessus (32,67%/32,67%) mais reste nettement sous
l'ancien chiffre non corrigé (36,83%/36,67%) — la correction de cadence
reste valide et est maintenant la référence officielle du projet.

<details>
<summary>Historique pré-08/11 (figé, conservé pour traçabilité)</summary>

| Référence | Profit 1000$/3000$ | Ruine | Année1<0 | Statut |
|---|---|---|---|---|
| ~~Ancienne référence verrouillée~~ (ancien moteur 1-phase) | 5 794 566$ / 5 898 897$ | 1,83%/0,00% | 5,50%/4,00% | **SUPERSEDED 08/10** — historique de la chaîne de corrections uniquement |
| ~~Référence Étape E pure, ANCIEN cap Blueberry~~ | ~~4 827 736$ / 4 892 588$~~ | ~~1,67%/0,50%~~ | ~~20,83%/20,33%~~ | **PÉRIMÉ 08/10 suite 7** |
| Référence Étape E pure, **cap Blueberry corrigé**, plafond **3000$**, sans V2 | 5 707 481$ | 0,50% | 21,17% (pré=9,33%) | **SUPERSEDED 08/11** — 3000$ utilise maintenant la config combo complète ci-dessus par convention explicite de l'utilisateur, cette ligne n'est plus la référence par défaut mais reste documentée (V2 n'apportait pas de gain isolé à 3000$ sous l'ANCIENNE convention 646-trades/sans payout) |
| ~~REF+V2+FTMO-10%+GFT Goat Guard, plafond 1000$, ANCIEN cap Blueberry~~ | ~~4 927 916$~~ | ~~0,83%~~ | ~~21,00%~~ | **SUPERSEDED 08/10 suite 7** |
| REF+V2+FTMO-10%+GFT Goat Guard, plafond 1000$, cap Blueberry corrigé, **646 trades, sans payout** | 5 736 759$ | 1,00% | 21,83% (pré=8,50%) | **SUPERSEDED 08/11** — remplacé par la nouvelle référence ci-dessus (population 721 + payout activé). Baseline du cascade check ci-dessus. |
| Même config, cap corrigé, plafond 3000$, 646 trades, sans payout | 5 751 134$ | 0,50% | 21,83% | **SUPERSEDED 08/11** |
| ~~FTMO-10%+GFT Goat Guard seuls (sans V2, ancien candidat), ANCIEN cap~~ | ~~4 886 315$ / 4 945 037$~~ | ~~1,50%/0,50%~~ | ~~21,17%/20,67%~~ | Périmé |

</details>

**Piste A' (BBx2, 2× Blueberry parallèle) — option disponible au plafond
3000$, PAS adoptée par défaut** (§2.15, reconfirmée §2.18 sous cap
corrigé) — ⚠️ chiffres ci-dessous mesurés sous l'ANCIENNE convention
(646 trades, sans payout, 3000$=REF pure sans V2) : comparaison directe
avec la nouvelle référence 08/11 non valide tant que BBx2 n'est pas
retesté sous population 721 + payout :

| Référence | Profit | Ruine | Année1<0 | Statut |
|---|---|---|---|---|
| BBx2, plafond 3000$, cap Blueberry corrigé | **5 953 550$ (+4,31% vs REF pure 3000$ ci-dessus)** | **0,33% (meilleure)** | **17,33% (meilleure, -3,84pt)** | n=600+cascade GO (`etape_t_piste_a_prime_2x_blueberry_2026-08-10.py`). Domine strictement REF pure à 3000$ sur les 3 axes. **Non adoptée par défaut** — alternative structurelle (2 comptes Blueberry jour 0 au lieu d'1) qui dépend d'un choix d'architecture, pas juste d'un paramètre de risque ; le chantier n'a pas tranché si "la" référence 3000$ doit être REF pure ou BBx2 (décision #7 §4, toujours ouverte). |
| BBx2, plafond 1000$ | 5 707 817$ (n=300, écran 08/10 suite 5) | 7,67% | 21,33% | **REJETÉ** — dominé par solo_BB à ce plafond (voir REF pure ci-dessus 1000$, ligne à confirmer séparément si besoin). Non pertinent tant que le plafond réel n'est pas tranché en faveur de 3000$. |

**Résumé de la référence officielle par plafond (08/11)** : 1000$ →
config combo complète, population 721, payout activé (**5 444 513$**,
solde_negatif_annee4=1,50%, hit_ceiling_pct=3,50%) ; 3000$ → même config
(**5 494 348$**, solde_negatif_annee4=0,17%, hit_ceiling_pct=1,33%) —
**convention 08/11 : même config aux deux plafonds**, remplace l'ancienne
asymétrie REF+V2 (1000$) / REF pure (3000$). BBx2 reste une option
structurelle documentée mais non retestée sous cette nouvelle référence.
Le chantier n'a **toujours pas tranché** lequel des deux plafonds (1000$
ou 3000$) constitue "le" plafond réel de l'utilisateur (décision #9 §4) —
seul point, avec éval=1,00%/1,25% (décision #2), qui reste réellement
bloquant pour figer une référence unique du projet.

⚠️ **Tout ce qui précède suppose éval=1,25%.** Testé sous éval=1,00%
(08/10 nuit, `etape_p_eval_risk_test_2026-08-10.py`, AVANT la correction
du cap Blueberry) : V2 **ne domine plus** à 1000$ (année1<0 empire) et
devient **pire sur les 3 axes** à 3000$. Le combo V2+FTMO-10/GoatGuard
n'a jamais été retesté sous 1,00%, ni avant ni après la correction du cap
Blueberry — hérite probablement du même problème mais non vérifié. Voir
décision #2 §4 — vrai choix de risque personnel, pas encore tranché, et
désormais la SEULE chose qui sépare la référence actuelle d'un chiffre
pleinement validé sur toute la matrice de décisions ouvertes.

L'écart entre l'ancienne référence verrouillée (ancien moteur) et REF
pure n'est **pas une régression** : année1<0 a augmenté mécaniquement
parce que le nouveau moteur modélise correctement le restart complet
(P1+P2) à toute casse, un risque réel que l'ancien moteur 1-phase ne
pouvait pas représenter (confirmé par ablation empirique).

**🔴 NOTE CRITIQUE (à retenir avant tout clear de contexte) — la
référence officielle ci-dessus (5 736 759$/1000$, 5 707 481$/3000$)
N'INCLUT PAS la correction du cycle de payout/forfeiture (Blueberry/GFT/
Fivers, §2.26).** Cette correction reste au stade CANDIDAT
(5 510 750$/1000$, -3,94% ; 5 539 307$/3000$, -3,68% — voir §2.26 pour
le détail complet), en attente d'une vérification méthodologique en 4
points avant de pouvoir être adoptée avec la même confiance que la
correction du cap Blueberry :
1. **Automaticité du retrait par cycle** — le moteur suppose un
   versement automatique tous les 14j sans action du trader ; jamais
   confronté explicitement à la politique réelle de chaque firm sur ce
   point précis (cadence confirmée ~14j, mais "automatique vs demande
   manuelle" non vérifié séparément).
2. **Disponibilité du profit sécurisé pour `state["reserve"]`** — au
   moment du versement, le montant flushed doit devenir disponible pour
   la réserve partagée du projet avec le bon montant/timing ; implémenté
   et smoke-testé, mais pas audité par un test dédié indépendant comme
   l'a été la décomposition du gain Blueberry (§2.18).
3. **Suivi du cycle 14j par compte** — le compteur `last_payout_time`/
   `pending_payout` doit se réinitialiser correctement à chaque
   réouverture/reset/nouveau compte extra ; implémenté partout où
   identifié nécessaire, mais pas stress-testé indépendamment.
4. **Périmètre casse dure uniquement** — le forfait ne doit s'appliquer
   QUE sur une vraie casse (`elif broke:`), jamais sur un soft-breach
   GFT Goat Guard (qui n'est pas un reset) ; confirmé par construction du
   code (le forfait est dans la branche `broke`, sautée quand Goat Guard
   se déclenche), mais pas vérifié par un test dédié qui isolerait
   spécifiquement ce cas.
**Tant que ces 4 points n'ont pas été explicitement vérifiés (ou que
l'utilisateur ne donne pas un feu vert malgré cette réserve), le chiffre
candidat du cycle de payout reste EXCLU de la référence officielle
ci-dessus.**

**🆕 Vérification méthodologique faite 08/11 (§2.28)** : les 4 points ont
été relus ligne par ligne dans le code (`etape_ad_payout_cycle_2026-08-10
.py`). Points 2/3/4 sont confirmés corrects PAR CONSTRUCTION du code
(disponibilité réserve, cycle par compte, périmètre casse dure). Le
point 1 (automaticité) reste un **choix de modélisation explicite non
confronté à la politique réelle de chaque firm** — le code suppose un
versement automatique sans action du trader, ce qui n'a jamais été vérifié
séparément de la cadence 14j elle-même. La vérification de code ne remplace
donc pas la décision d'adoption utilisateur — voir décision #13 §4,
inchangée.

---

## 2. Journal des leviers

**Verdict** : ADOPTÉ / REJETÉ / ARBITRAGE (vrai compromis, pas de gagnant net) / EN COURS (test non finalisé).

### 2.1 Mécanique de trading (niveau compte unique, avant flotte)

| Levier | Verdict | Raison | Condition de réouverture | Session |
|---|---|---|---|---|
| Pyramiding (+0,5R/+1R) | REJETÉ | Toutes variantes sous-performent (~2,5-4,2M€ vs ~10,3M€ baseline) ; le winrate conditionnel réel (63,9%) ne compense pas la structure R plus faible des unités ajoutées tardivement | Nécessiterait un filtre de sélection différent (momentum), pas juste "toucher +0,5R" | ~07/30 |
| Kelly 50% | REJETÉ | Après correction comptable (P&L financé uniquement), plus de gain significatif (+0,5%, p5 bien pire) | — | ~07/30 |
| Kelly 25% | ARBITRAGE non tranché | +7,6% profit non significatif après correction | **À re-tester sous le moteur multi-phase + reset Blueberry actuel** (jamais refait depuis) | ~07/30 |
| ATR-adjustment seul | REJETÉ (neutre) | Risque réalisé ~2,01% vs cible 2% — sans effet | — | ~07/30 |
| Trailing stop après TP2, 0,2× SL | ADOPTÉ | +9,7 à +11,1% profit vs sortie TP2 dure, casses quasi inchangées | Fenêtre 0,05-0,2× pas finement testée (echantillon réduit) — sweep plus fin possible si slippage Dukascopy intégré | ~07/30 |

### 2.2 Corrections de moteur (pas des leviers, mais ont changé tous les chiffres en aval)

| Correction | Impact | Session |
|---|---|---|
| Bootstrap par blocs (vs permutation naïve) | Cash pire-cas 21 972€→48 195€ (contre-intuitif mais correct) | 08/01 |
| Réserve poolée (vs par compte) | -27 577€ cash pire-cas, plus gros levier des 3 | 08/01 |
| Immunité post-financement (`ever_funded`) | -17 621€ cash pire-cas ; rend le risque personnel indépendant du seuil de bascule | 08/01 |
| P&L financé uniquement (pas challenge) | **Bug le plus lourd** : 10,33M€→7,77M€, explique 106% de la sur-estimation précédente | 08/01 |
| "OBJECTIF ATTEINT" = TP1 pas TP2 | Correction méthodologique projet-wide, sur-estimation ~13× dans un test | avant 08/01 |
| Fenêtre DD journalière (jour calendaire complet vs fenêtre réelle) | A fabriqué la prémisse de la piste #8 (duo GBP/JPY-USD/CHF) ; DD max 91 duos 4,44%→1,20% | ~07/30 |
| Bug DD journalière manquante (aucun moteur ne vérifiait la limite journalière séparément) | +70,6% casses une fois corrigé ; The5%ers-only -10 à -15% profit | 08/05 |
| `backtest_analyzer.py` — bug payoff naïf + MIN_RR obsolète | **PAS ENCORE CORRIGÉ**, script live actif (`analyse_live.py`), sur-estime l'EV de +85% | trouvé, non résolu |

### 2.3 Structure de flotte / croissance (08/05-08/08, avant moteur multi-format)

| Levier | Verdict | Raison | Condition de réouverture | Session |
|---|---|---|---|---|
| Régime A (risque 2% dès jour 1) | ADOPTÉ (verrouillé) | Domine B/C sur profit ET P(perte) | — | 08/05 |
| Délai lancement The5%ers (pré-immunité) | Recommandé, jamais formellement verrouillé | Cash pire-cas -70-75% pour -1,6% profit | Généralisé par le déblocage échelonné 08/08 (obsolète) | 08/06 |
| Structures agressives (FXIFY/Ment Funding) | Différé, pas rejeté sur l'économie | Cash pire-cas 30-35× la référence lancement | Reconsidérer une fois réserve ≥5-10× le pire-cas initial (seuil jamais calculé précisément) | 08/05 |
| Flotte 3-firm scaling 50k→500k | REJETÉ | Cap $400k réel rend le palier 500k inatteignable, profit combiné PLUS BAS que l'ancienne référence 3×50k | Pertinent seulement avec plus de firms à caps plus hauts | 08/05 |
| Bug mécanisme de scaling (upgrade payant instantané, produit fictif) | Corrigé | Le vrai mécanisme (gratuit, +25%/3-4 mois, gated) coûte -60,5% profit une fois corrigé | Correction projet-wide, toute valeur antérieure au 08/08 invalide | 08/08 |
| "Compte supplémentaire" (remplace le vrai scaling) | ADOPTÉ | Récupère ~60% du profit perdu par la correction du bug scaling, sans dépendre d'une survie multi-mois | — | 08/08 |
| Déplafonnement comptes supplémentaires (v3→v4) | ADOPTÉ | +51,9%/+52,1% profit pour risque quasi nul (n=300) | Re-testé (re-plafonner) sous le nouveau moteur 08/09 — **REJETÉ**, arbitrage défavorable (-30,2% profit pour -1,33pt année1<0) | 08/08, re-testé 08/09 |
| Reconfirmation n=300→n=600 (v4) | Leçon méthodologique | Profit surestimé ~9-9,5% à n=300, ruine sous-estimée ~1pt | Règle générale : toujours vérifier le n réel avant de citer un chiffre "verrouillé" | 08/08 |
| Déblocage partiel FTMO seul (seuil réduit) | ADOPTÉ (free lunch confirmé) | +5,0% profit, ruine meilleure, année1<0 -2,84pt à n=600 | Généralisé par le déblocage échelonné 5-étapes (ci-dessous) | 08/08 |
| Étalement calendaire du déblocage groupé (délai 1-4 sem sur LE bloc groupé) | REJETÉ | Ruine AUSSI dégradée à n=600 (pas juste un déplacement neutre) ; re-confirmé 08/09 comme artefact de reclassification pré/post | — | 08/08, re-confirmé 08/09 |
| Déblocage échelonné 5-étapes par firm (seuils indépendants) | ADOPTÉ | +7,2%/+7,8% profit, année1<0 -5pt, cascade clean | Seuils re-vérifiés sous nouveau moteur 08/09 : FTMO/Fivers/GFT robustes, FundedNext = vrai arbitrage (voir §1.2) | 08/08 |
| Seuil FTMO affiné à 1000$ | ADOPTÉ | Free lunch pur au plafond 1000$, favorable-non-strict à 3000$ | — | 08/08 |
| "Déficit catégorie A" (runs qui semblaient pires à 12 mois) | Confirmé artefact de mesure | Contre-factuel pairé : mêmes tirages meilleurs à horizon complet dans 88-96% des cas | — | 08/08 |
| Bug DD journalière The5%ers (3% codé au lieu de 5% réel) | Corrigé, free lunch sur les 3 axes | +1,9% profit, ruine et année1<0 meilleurs | — | 08/08 |
| Seuil FundedNext (ancien moteur, 20/25/30k) | 25k adopté prudemment | Gain dans le bruit à n=600, pas un free lunch confirmé | Re-tranché sous le nouveau moteur (voir §1.2, vrai arbitrage 25k/5k) | 08/08 |
| Bugs DD FundedNext (journalière 5%→4%, max 10%→8%) | Corrigés — vrai resserrement (pas un free lunch) | Chiffre verrouillé officiel du projet ramené de 6,03M$/6,13M$ à 5,79M$/5,90M$ | — | 08/08 |
| Copytrade FundedNext | Résolu (confirmé support) | Autorisé en éval, interdit une fois financé — correspond déjà au design | — | 08/08 |
| Capital bootstrap 300$ (Blueberry, pré-déblocage) | ADOPTÉ | Fait partie du combo qui a réduit la ruine de 34-40%/17-26% à ~7%/1% | Sous le nouveau moteur, utilisé dans 100% des runs ruinés mais insuffisant seul contre une longue série défavorable | 08/07 |
| Réserve ≥30 000$ avant déblocage groupé + risque éval réduit 2,0% | ADOPTÉ (ancien moteur) | Plus gros levier de la crise de ruine initiale ; le risque réduit en éval est un free lunch (réduit ruine ET augmente profit) | Superseded par le déblocage échelonné 5-étapes (08/08) | 08/07 |

### 2.4 Chantier multi-format, Étapes A-E (08/08-08/09)

| Levier | Verdict | Raison | Condition de réouverture | Session |
|---|---|---|---|---|
| Moteur multi-phase générique (`engine_multiformat.py`) | ADOPTÉ (nouvel outillage) | Remplace le modèle flat 8%/10% unique ; découverte structurante : DD statique/trailing dépend du FORMAT, pas du nombre de phases | — | 08/08 |
| Combo WINNER (formats rapides partout, Étape D) | REJETÉ définitivement | Une fois intégré au vrai moteur de production (croissance + fiscalité réelles), perd sur profit ET ruine ET cascade face à REF | Nécessiterait un vrai mécanisme de croissance individuelle pour les formats rapides — jamais tenté | 08/08 |
| Recalibrage risque flotte=1,90% (nouveau moteur) | ADOPTÉ | Reconfirmé indépendamment 3× (audit, chantier1 sans/avec reset) | — | 08/09 |
| Reset Blueberry (2× prix original, saute l'éval) | **ADOPTÉ — SEUL LEVIER GAGNANT** sur les 9 testés | +3,0-3,1% profit, ruine divisée par ~2, année1<0 -3,7 à -4,2pt, n=600+cascade GO | Pas encore promu au chiffre de référence officiel — décision utilisateur en attente | 08/09 |
| Re-balayage risque avec reset actif (Chantier 1) | ADOPTÉ — nouveau chiffre de référence Étape E | Zone haute (éval≥1,75%) testée explicitement, ne domine jamais (ruine disproportionnée) | — | 08/09 |
| Blueberry-adaptatif (format bascule par seuil de réserve, Chantier 2) | REJETÉ (24 configs) | Blueberry inclus : ruine bloquée à 14% (trade au risque flotte dès jour 0, pas de phase protectrice) ; Blueberry exclu : profit systématiquement pire (-2,75 à -8,5%) | Protections testées ensuite (voir §2.5) réduisent mais ne referment pas l'écart | 08/09 |
| FTMO -10%/GFT Goat Guard | **ADOPTÉ (candidat)** — confirmé n=600, cascade GO | (a) quasi mécanique (+0,17%/+0,04%), (b) réel (+1,04% profit, casse≤30j -1,78pt) mais approximation documentée sur le déclencheur -2% ; (c) combiné +1,21%/+1,07% profit, ruine =/mieux, année1<0 dans le bruit | Décision d'adoption dans la config de référence en attente | 08/09 |

### 2.5 Série de mitigation année1<0 (9 leviers, 3 sessions)

| # | Levier | Verdict | Raison | Condition de réouverture |
|---|---|---|---|---|
| 1 | Seuil FTMO encore réduit (500/250/0$) | REJETÉ | 0$ nettement délétère (ruine ×4) ; 500/250 sans effet (déjà optimal) | — |
| 2 | Étalement calendaire (re-test nouveau moteur) | REJETÉ | Confirmé artefact de reclassification, pas une vraie réduction de risque | — |
| 3 | Rampe globale classique (RAMP_RISK=2,0%) | REJETÉ — net négatif | Calibrée contre l'ancien flotte=2,75%, maintenant plus risquée que le flotte actuel 1,90% | Nécessiterait un recalibrage sous 1,90% |
| 4 | Rampe ciblée restart (1,50/1,70%) | REJETÉ (neutre) | Tous les écarts dans le bruit n=300 | — |
| 5 | Redémarrage asymétrique (downsize extra-comptes) | REJETÉ — net négatif | Casses post-déblocage +21,5% (accélère le cycle casse-restart) | — |
| 6 | Risque dégressif fin de phase | REJETÉ | Neutre à négatif sur toutes les variantes | — |
| 7 | Plafond dur comptes supplémentaires | REJETÉ — arbitrage défavorable | -30,2% profit pour -1,33pt année1<0 | — |
| 8 | Cadencement continu (délai extra-comptes) | REJETÉ — quasi inerte | Le rythme naturel est déjà plus lent que 1-3 semaines | — |
| 9 | Reset Blueberry | **ADOPTÉ** | Voir §2.4 | — |

**Diagnostic structurel** (pas un levier, la conclusion de la série) :
année1<0 se décompose 57% pré-déblocage / 43% post-déblocage sous le
nouveau moteur. Réduire le VOLUME de comptes financés simultanés réduit
bien les casses post-déblocage (confirmé 2×) mais tous les leviers
testés le font en réduisant la flotte uniformément (coûteux) plutôt
qu'en ciblant le coût du restart. Piste non explorée : un levier
spécifiquement post-déblocage (jamais tenté).

### 2.6 Levier STRUCTUREL — bootstrap parallèle jour 0 (08/09 soir)

Premier levier non-paramétrique testé sur le chantier (tous les 9
précédents de §2.5 réglaient un mécanisme existant ; celui-ci change la
structure elle-même). Constat de départ : le point de défaillance unique
pré-déblocage (compte Blueberry seul porte 100% de la génération de réserve
avant le seuil FTMO) explique 57% du année1<0 (diagnostic ci-dessus). Idée
testée : ouvrir plusieurs starters bon marché chez des firms différentes en
parallèle dès le jour 0 au lieu d'un seul.

**Coûts jour 0 réels** (vérifiés empiriquement, PAS le plus petit palier de
la grille de prix — GFT et FTMO utilisent tous deux `BASE_PALIER=50 000$`,
pas 25 000$) : Blueberry=165$, GFT=288$, FTMO=345$, Fivers=545$ (écarté,
trop cher), FundedNext=799$ (écarté, trop cher).

**Règle de déblocage retenue** : "premier financé suffit" — se déduit
gratuitement du gate existant `group_funded_count>=1` dans
`seq_grouped_multi` (déjà présent, aucun changement de seuil nécessaire).
Choisi plutôt que "tous financés" qui annulerait le bénéfice de redondance.

**Résultat n=600 + cascade instrumentée** (`etape_f_bootstrap_parallele_
2026-08-09.py`, copie de `etape_e_final_lock_bbreset_2026-08-09.py`,
éval=1,25%/flotte=1,90%, reset Blueberry actif) — **effet CONDITIONNEL au
plafond, jamais vu avant sur ce chantier** :

| Combo | Coût j0 | Plafond 1000$ (profit/ruine/année1<0/pré) | Plafond 3000$ (profit/ruine/année1<0/pré) |
|---|---|---|---|
| solo_BB (référence) | 165$ | 4 827 736$ / 1,67% / 20,83% / 10,33% | 4 892 588$ / 0,50% / 20,33% / 9,33% |
| BB+GFT | 453$ | 4 561 623$ / 10,67% / 24,17% / 13,67% | **5 097 319$ / 0,67% / 15,67% / 3,50%** |
| BB+FTMO | 510$ | 4 470 402$ / 11,50% / 25,00% / 16,00% | 5 052 346$ / 0,83% / 15,83% / 5,67% |
| BB+FTMO+GFT | 798$ | 4 495 527$ / 12,50% / 24,33% / 15,83% | 5 053 366$ / 2,50% / 16,17% / 4,83% |

- **Plafond 1000$ : REJETÉ sans ambiguïté.** Solo domine tous les combos sur
  les 3 axes (marge de cash restante trop faible après le coût jour 0
  cumulé, ruine ×6-7, quasi_gelé 10-14% vs 1,5%).
- **Plafond 3000$ : ADOPTABLE (candidat).** BB+GFT domine strictement solo
  sur profit (+4,2%), année1<0 total (-4,7pt) ET la composante PRÉ ciblée
  (-5,8pt, -62% relatif) pour un coût ruine négligeable (+0,17pt, 4 vs 3
  cas sur 600 — probablement du bruit). Cascade check propre (casse≤30j
  25,07% vs 24,71% solo, quasi_gelé 0,3%=0,3% identique). BB+FTMO+GFT
  (3-way) est STRICTEMENT DOMINÉ par BB+GFT seul (moins de profit, plus de
  ruine, année1<0 similaire) — l'extension à 3 firms n'apporte rien de plus
  et l'ouverture surtaxée (798$) rapproche trop de la zone d'épuisement de
  marge, même à 3000$.

**Verdict : ARBITRAGE, pas un free lunch.** Premier levier du chantier dont
l'adoption dépend explicitement du plafond personnel choisi par
l'utilisateur — les 3000$ ceiling users gagnent net sur tous les axes utiles
(BB+GFT), les 1000$ ceiling users doivent rester en solo_BB. Décision
d'adoption en attente (comme le reset Blueberry et FTMO-10%/Goat Guard).

### 2.7 Coupe-circuit réactif au signal réel (08/09-08/10 nuit)

Idée testée : contrairement à toutes les rampes précédentes (§2.5, #3/#4/
#6) déclenchées par un ÉVÉNEMENT (casse, calendrier), un coupe-circuit
déclenché par la PERFORMANCE RÉALISÉE en continu — fenêtre glissante des N
derniers `trade["outcome_r"]` (signal brut fleet-wide, tous les comptes
copient le même trade), réduction du risque flotte si le R moyen de la
fenêtre tombe sous un seuil d'entrée, retour au risque normal au premier des
deux événements (M trades écoulés OU R moyen remonté au-dessus d'un seuil
de sortie).

**Calibrage** : seuils exprimés en R moyen/trade (indépendants de N),
vérifié empiriquement sur la distribution réelle des trades (moyenne
+0,97R, std 2,95R, winrate 40,1%) avant le sweep. Grille 3×2×2×2=24 configs
(N∈{10,20,30}, entrée∈{0,0;-0,5}, sortie∈{+0,5;+1,0}, réduction∈{30%;50%})
+ baseline, n=300, plafond=1000$ (`etape_g_circuit_breaker_2026-08-09.py`).

**Résultat : REJETÉ — aucune config ne bat la référence de façon nette.**
Baseline (sans coupe-circuit) : profit=5 005 612$, ruine=1,67%,
année1<0=20,33% (pré=11,33%). Sur les 24 configs :
- Entrée=0,0 (déclenchement fréquent, 20-32% du temps en mode réduit,
  8,8-23 activations/run) : profit systématiquement DÉGRADÉ (jusqu'à -3,4%,
  N10_in+0.0_out+1.0_r50), sans amélioration compensatoire fiable de la
  ruine ni de année1<0 (souvent PIRE : 21,0-22,0% vs 20,33%).
- Entrée=-0,5 (déclenchement rare, 0,5-8 activations/run, 2-13% du temps
  en mode réduit) : résultats statistiquement indiscernables de la
  baseline sur les 3 axes (écarts <0,5%, dans le bruit n=300) — le
  mécanisme se déclenche trop rarement pour avoir un effet mesurable.
- Aucune des 24 configs ne domine la baseline sur 2+ axes sans dégrader le
  3e — pas de candidat à confirmer en n=600.

**Explication du mécanisme d'échec** (pas juste "ça ne marche pas", le
pourquoi) : contrairement aux leviers événementiels (une casse = un coût
réel identifiable, une rampe post-restart cible un risque réel de rechute),
une mauvaise passe récente sur ce pool de trades (espérance +0,97R,
variance élevée) est presque toujours du BRUIT statistique autour d'une
espérance positive, pas un signal de dégradation réelle du edge. Réduire le
risque flotte pendant cette passe réduit symétriquement l'ampleur des
pertes ET l'ampleur de la reprise qui suit typiquement (retour à la
moyenne) — un coût d'opportunité qui annule le bénéfice protecteur en
moyenne. Différent des rampes événementielles qui, elles, ciblent un coût
réel et non-symétrique (le prix de rachat après une casse).

**Condition de réouverture** : seulement si un signal MOINS bruité est
proposé (ex. fenêtre bien plus large, ou couplage à un indicateur qui ne
soit pas juste la moyenne R récente d'un processus positif à haute
variance) — pas en resweepant la même grille avec d'autres seuils, le
pattern est cohérent sur les 24 points testés.

### 2.8 Fongibilité inter-firm (08/10 nuit) — FERMÉ DÉFINITIVEMENT

Implémentation complète du scoping §2.6bis (voir mémoire
project_slot_fungibility_scoping_2026-08-09) : queue générique + compétition
unifiée (relances + extra-comptes) triée par EV/$ (source : Étape C
corrigée, project_etape_c_corrigee_ev_par_dollar_2026-08-09 — FundedNext
953,68 > Fivers 783,39 > GFT 638,57 > Blueberry 615,67 > FTMO 578,03).
Reset Blueberry et déblocage initial par firm exclus de la compétition par
design (voir doc du script) ; interaction FTMO-10%/Goat Guard testée sans
crash. `etape_h_fongibilite_slots_2026-08-10.py`.

**Résultat n=300, 2 plafonds : REJETÉ, aucun gain net.**
- Plafond 3000$ : effet NUL (5 084 496$/0,33%/19,67% identique au bruit
  flottant près, baseline=fongible) — la réserve est presque toujours assez
  abondante pour financer tous les candidats simultanés, la priorité EV/$
  n'a jamais l'occasion de trancher quoi que ce soit.
- Plafond 1000$ : légèrement PIRE (4 989 219$ vs 5 005 612$, ruine
  2,00% vs 1,67%, année1<0 20,67% vs 20,33%) — impact uniforme sur les 5
  firms (`pct_zero_active_end_*` identique partout, pas de famine ciblée
  d'une firm faible), donc probablement une redistribution marginale au
  sein des mêmes crises de trésorerie totale plutôt qu'un vrai mécanisme
  différencié.

**Diagnostic** (confirmé par débogage instrumenté, pas juste déduit) : sur
30 simulations individuelles comparées trade-par-trade, seule 1/30 a montré
une DIVERGENCE quelconque entre fongible et baseline (et même celle-là
identique sur le profit final) — dans l'immense majorité des cas, la
réserve dépasse largement le coût total de TOUS les candidats en
compétition simultanément, donc l'ordre de priorité ne change jamais qui
est financé. La fongibilité ne débloque de la valeur QUE dans une fenêtre
étroite de pénurie partielle (assez pour certains candidats, pas tous) —
rare sur cette flotte, qui est soit large ment profitable (réserve
abondante) soit en ruine totale (rien à réordonner).

**Retesté 08/10 nuit suite 6 sous cap Blueberry corrigé (§2.18) —
verdict RECONFIRMÉ, hypothèse du goulot d'étranglement commun RÉFUTÉE.**
L'ancien cap Blueberry (3 comptes max) n'était PAS la cause du rejet
original — sous cap corrigé (illimité), l'écart fongible vs baseline
reste nul/bruit (-276$/1000$, 0$ exact/3000$, n=300). Le vrai mécanisme
reste celui diagnostiqué ci-dessus : réserve non-scarce sur cette
flotte, indépendamment du cap Blueberry.

**FERMÉ DÉFINITIVEMENT 08/10 nuit suite 7** — rejet reconfirmé sous DEUX
régimes de cap Blueberry distincts (ancien 450k$/3-comptes ET corrigé
400k$/illimité), avec l'hypothèse la plus prometteuse de réouverture
(le goulot d'étranglement Blueberry) explicitement testée et réfutée.
**Aucune condition de réouverture plausible ne subsiste** : le mécanisme
root-cause (réserve non-scarce, fenêtre de pénurie partielle trop rare
pour que la priorité EV/$ compte) a maintenant résisté à deux
changements structurels majeurs du moteur sans broncher — il faudrait
une refonte de la flotte elle-même (pas un paramètre) pour que ce levier
ait une chance de compter un jour. Piste fermée, ne plus re-tester sans
un changement d'architecture de flotte, pas juste un paramètre.

### 2.9 Sizing par distance au DD (piste F, 08/10 nuit)

Distinct du coupe-circuit §2.7 (signal de PERTE structurel — distance
propre à chaque compte vis-à-vis de son DD max — pas un signal de
PERFORMANCE récente du pool de trades) et du "risque dégressif fin de
phase" déjà rejeté (§2.5 #6, qui réagissait à la distance à la CIBLE de
profit, pas au DD — vérifié par citation de code
`etape_e_annee1_levers2_2026-08-09.py:228-238`, aucun chevauchement).
`dd_distance_pct()` miroir continu de `_dd_max_breached()` (aucune
modification du moteur), 3 fonctions de multiplicateur testées :
A (linéaire+plancher), B (palier bas+hystérésis, avec état par compte), C
(convexe+plancher). `etape_i_dd_distance_sizing_2026-08-10.py`.

**Résultat n=300, 2 plafonds, 12 configs : REJETÉ — aucune domination
stricte sur 3 axes.** Le mécanisme fonctionne (casse≤30j baisse partout,
23,8%→15,7-24,9% selon intensité), mais A/C interviennent trop souvent
(19-25% du temps) et ralentissent nettement le financement (délai +21% à
+42%, 79-93j vs 65j baseline, confirmé par l'instrumentation dédiée) — le
profit en paie le prix (-4,6% à -12,3%) sans amélioration compensatoire de
ruine/année1<0 (année1<0 empire systématiquement, +3 à +6,7pt).

**B (paliers+hystérésis) nettement meilleur** — intervient rarement
(1,9-5,3% du temps), hystérésis validée empiriquement (3,6-4,4 oscillations
propres par compte, pas de flip-flop), délai de financement quasi
préservé (+1 à +9%). **B_entry20_red50 est le point le plus proche d'un
gain** (profit +1,08%, ruine 0,00% vs 1,67% au plafond 1000$) mais
année1<0 reste dégradé (+1,34pt aux deux plafonds) et le gain de profit ne
se reproduit pas à 3000$ (-0,44%) — ne remplit pas le critère de
domination sur 3 axes, pas de confirmation n=600.

**Condition de réouverture** (piste ouverte, pas fermée comme le
coupe-circuit) : variante B avec seuil d'entrée <20% (zone de danger
encore plus étroite) ou réduction moins agressive que 50%, pour tenter de
fermer l'écart sur année1<0 sans perdre l'avantage profit/ruine déjà
identifié sur B_entry20_red50.

**RECALIBRATION 08/10 nuit (`etape_j_dd_distance_recalibration_2026-08-10.py`)
— GO CONDITIONNEL CONFIRMÉ n=600+cascade au plafond 1000$.**

Décomposition scénario-par-scénario (seed appariée, n=300, plafond=1000$,
matrice complète SAIN/ANNEE1NEG_ONLY/RUINE) : la dégradation d'année1<0 de
B_entry20_red50 N'EST PAS majoritairement une conversion favorable de
ruine — 10 scénarios sains basculent en année1<0 contre seulement 3
conversions ruine→année1<0-survit. Mais asymétrie clé : **RUINE totalement
éliminée (5→0), et B ne crée JAMAIS de nouvelle ruine** (colonne RUINE=0
pour toute ligne baseline) — le coût du sur-déclenchement est plafonné à
"année1<0 temporaire", jamais à une nouvelle catastrophe.

Deux volets testés en recalibration : (1) grille B plus fine
(entry∈{10,15}%, reduction∈{30,40}%) ; (2) B_entry20_red50 restreint à la
fenêtre PRÉ-DÉBLOCAGE uniquement (risque plein dès le déblocage complet).
**Volet 2 est le gagnant** — confirme l'hypothèse que la protection
post-déblocage était du pur coût d'opportunité :

| | Profit | Ruine | Année1<0 (pré) |
|---|---|---|---|
| Baseline n=600 @1000$ | 4 827 736$ | 1,67% | 20,83% (10,33%) |
| **V2 (pré-déblocage seul) n=600 @1000$** | **4 872 626$ (+0,93%)** | **0,83% (÷2)** | **20,67% (8,67%)** |
| Baseline n=600 @3000$ | 4 892 588$ | 0,50% | 20,33% (9,33%) |
| V2 n=600 @3000$ | 4 885 566$ (-0,14%) | 0,33% | 20,67% (pire) |

**GO au plafond 1000$ uniquement** (domination stricte sur les 3 axes,
cascade check propre, casse≤30j 24,57% vs 24,64% baseline). **Pas de gain
au plafond 3000$** (mixte, pas dominant — logique : au plafond large, les
casses sont déjà absorbables sans effort, la réduction de position ne
coûte que de l'opportunité sans contrepartie). Même pattern conditionnel
que le bootstrap parallèle (§2.6), rôles inversés : le bootstrap gagne au
plafond LARGE, celui-ci gagne au plafond SERRÉ — cohérent, les deux
protègent contre l'épuisement de trésorerie, qui n'est un problème réel
qu'au plafond serré.

**Décision d'adoption en attente** (comme le bootstrap parallèle) — le
chantier a maintenant DEUX leviers structurels confirmés, tous deux
conditionnels au plafond personnel choisi par l'utilisateur, pointant en
sens opposés (3000$ → bootstrap parallèle ; 1000$ → sizing DD
pré-déblocage).

### 2.10 Diagnostic délai de rattrapage — chiffre corrigé (08/10 nuit)

⚠️ **Le chiffre "0,33% ne rattrapent jamais" cité depuis le 08/08
(`etape_e_diagnostic_annee1_2026-08-09.md`) est PÉRIMÉ.** Ce run utilisait
éval=1,00% ; re-mesuré le 08/10 sous le moteur actuel (éval=1,25%, n=600,
plafond 1000$, `etape_l_recovery_diagnostic_2026-08-10.py`) :

| | Médiane rattrapage | Jamais rattrapé (% de TOUS les runs) |
|---|---|---|
| REF pure | 14,25 mois | **1,5%** (pas 0,33% — écart ×4,5) |
| REF+V2 | 14,28 mois | **0,83%** |

Médiane proche de l'ancien chiffre (14,25 vs 16 mois), mais la queue
"jamais rattrapé" est nettement plus large que rapporté. Pas réconcilié
si l'écart vient de la dérive éval=1,00→1,25% ou d'autre chose — signalé,
pas creusé davantage. **Verdict inchangé** ("pas alarmant", toujours <2%
en absolu) — c'est une correction factuelle, pas une remise en cause du
risque. **Citer 1,5%/0,83% désormais, pas 0,33%.** Le rapport original du
08/08 reste inchangé par convention (rapport figé) ; cette correction vit
ici et dans `project_recovery_delay_corrected_2026-08-10.md`.

Corrélation délai-déblocage ↔ résultat à 12 mois (autre chiffre du même
diagnostic 08/08, "+0,53/+0,54") : **tient toujours** sous le moteur
actuel, magnitude comparable (r=-0,46 à -0,52), signe probablement
inversé par rapport à la convention de l'étude originale (mesure
différente, pas une contradiction confirmée).

### 2.11 Vrai mécanisme de ruine BB+GFT (08/10 nuit) — confirmé par trace

Suite à la décomposition Étape K (casse rapprochée 3/64, double-réussite
0/600, toutes deux exclues), le mécanisme de remplacement spéculé
("détournement de réserve via `group_funded_count`") a été **testé par
trace directe et RÉFUTÉ** — 0 occurrence sur 600 sims
(`etape_o_ruin_mechanism_2026-08-10.py`).

**Vrai mécanisme, confirmé et chiffré** : épuisement de marge de
trésorerie initiale, pas une histoire de course ou de corrélation.
- Coût moyen avant 1er financement de la flotte : solo_BB=271$ vs
  **BB+GFT=684$ (×2,5)** — BB+GFT consomme bien plus du plafond partagé
  avant tout revenu.
- **28/600 (4,67%) des runs BB+GFT ne financent JAMAIS aucun compte** sur
  ~4 ans (0/600 pour solo_BB).
- Parmi les 64 ruines : **96,9% n'ont jamais complété la structure à 5
  firms** (vs 0% des sains) ; **43,75% n'ont jamais eu le moindre
  financement**. Les runs ruinés ont en fait MOINS de cycles casse-relance
  que les sains (bloqués trop tôt pour en accumuler), pas plus.

**Conclusion** : la ruine BB+GFT à 1000$ est un verrou de trésorerie
initial (le même mécanisme "épuisement de marge" déjà identifié à
l'introduction du bootstrap parallèle, §2.6) — pas un risque de casse
corrélée ni un arbitrage gain/risque sur une double-réussite rapide.
Piste A' et la décorrélation (§4 décisions ouvertes) doivent être scopées
sur CETTE base, pas sur la thèse initiale (invalidée).

### 2.12 Piste H rejetée, seuil FTMO reconfirmé (08/10 nuit)

**Piste H** (routage flotte-wide de la paire AUD/JPY-USD/CHF sur un
sous-ensemble fixe de comptes, ciblant le pattern confirmé "92-97% des
runs post-déblocage négatifs touchent chaque firm") : **REJETÉ, effet nul
confirmé** — `pct_post_neg_touching_all5` reste à 100,0%→100,0%,
strictement inchangé aux deux plafonds (n=300,
`etape_m_piste_h_routing_2026-08-10.py`). Confirme le signal source
identifié trop faible au scoping (corr=-0,09). Ne pas retenter sur cette
paire.

**Seuil FTMO reconfirmé** sous REF+V2 (jamais revérifié depuis l'ancien
moteur) : 1000$ domine sur les 3 axes aux deux plafonds parmi
{0,500,1000,2000,5000}$ (`etape_n_seuil_deblocage_sweep_2026-08-10.py`,
n=300). Aucun changement.

### 2.13 Piste A' — scoping (2× Blueberry parallèle, 08/10 nuit)

Scoping uniquement, pas de code exécuté (rapport complet
`etape_s_piste_a_prime_scoping_2026-08-10.md`). Généralise STARTERS à 2
comptes de la MÊME firm (Blueberry, même risque éval) au lieu de 2 firms
différentes — coût jour 0 330$ (2×165$), moins cher que BB+GFT (453$) ou
BB+FTMO (510$).

**Verdict de faisabilité : élevée, effort faible (~30-45min)** — seuls 2
points du code de `etape_f_bootstrap_parallele` supposent "1 seul starter
par firm" (init jour 0 avec `N_ACCOUNTS_DAY0["Blueberry"]=1` à surcharger ;
`try_emergency_bootstrap()` qui ne regarde que l'index 0). Tout le reste
(casse/relance, reset Blueberry, `structure_complete()`, croissance
extra-comptes) généralise déjà sans changement — indexé par identité de
compte, pas par firm. `FIRM_MAX_ACCOUNTS["Blueberry"]=3` (déjà VERROUILLÉ)
accommode 2 starters même sous la lecture la plus restrictive du conflit
§1.3/§4#6.

**Reste bloqué** sur la résolution du conflit Blueberry (nombre de comptes
simultanés — §4#6, `project_blueberry_account_limit_conflict_2026-08-10.md`)
— pas implémenté par instruction explicite de l'utilisateur (scoping
seulement).

### 2.14 Démarrage différé du 2e starter BB+GFT (08/10 nuit) — REJETÉ

Cible directement le mécanisme de ruine BB+GFT §2.11 (épuisement de marge
initiale) : retarder l'ouverture de GFT jusqu'à un signal de stabilité de
Blueberry (survie 7/14/21j sans casse, OU réserve 100/250/500$ atteinte)
au lieu du jour 0. `etape_r_piste_a_delayed_start_2026-08-10.py`
(généralise STARTERS en `active_starters` mutable + file de déclenchement
dédiée), n=300, 2 plafonds, instrumentation identique à l'Étape O
(cash avant 1er financement, % jamais financé). Rapport complet
`etape_r_piste_a_delayed_start_2026-08-10.md`.

**REJETÉ — aucune domination sur 2+ axes à aucun plafond.**
- Plafond 1000$ : délais en JOURS (7/14/21j) nettement pires que solo_BB
  sur les 3 axes (ruine 10-14% vs 1,67%) — le délai retarde le paiement
  mais engage quand même le plein coût sur le même budget, sans atténuer
  l'épuisement de marge. Délais en RÉSERVE (100/250/500$) quasi
  identiques à solo_BB (cash@1er_financement=272$, IDENTIQUE à solo_BB) —
  le seuil se déclenche trop rarement pour représenter une vraie
  stratégie de diversification, dégénère de facto en solo_BB.
- Plafond 3000$ : toutes les variantes différées font PIRE que
  BB_GFT_day0 (déjà la référence gagnante à ce plafond, §2.6) — retarder
  ne fait que perdre du bénéfice de diversification sans rien gagner,
  le cash n'étant jamais la contrainte active à ce plafond.

**Condition de réouverture** (explicite) : uniquement si (a) le coût
absolu de GFT (288$) baisse significativement — réduirait mécaniquement
la part du plafond engagée par le déclenchement, ou (b) la piste A'
(§2.13, coût plus faible par construction, 330$ pour 2 comptes vs 453$
BB+GFT) est tentée et échoue AUSSI — auquel cas revisiter une fenêtre de
seuil plus étroite sur le démarrage différé resterait possible mais peu
probable vu la dégénérescence observée aux deux extrêmes déjà testées
(jours : engage le coût quand même ; réserve : se déclenche trop rarement
pour compter). Le mécanisme de ruine BB+GFT à 1000$ reste sans solution
de mitigation trouvée (bootstrap day0 rejeté §2.6, démarrage différé
rejeté ici).

**Mise à jour 08/10 nuit suite 3** : condition (b) partiellement évaluée
— piste A' implémentée et testée en jour-0 immédiat (BBx2, §2.15), PAS
en version différée. À 1000$, BBx2 (330$) réduit nettement le verrou de
trésorerie vs BB+GFT (453$) — ruine 8,00% vs 11,00%, cash@1er_financement
487$ vs 680$ — mais reste dominé par solo_BB (donc "échoue aussi" au sens
de ne pas battre la référence). Un démarrage différé de BBx2 lui-même
(2e compte Blueberry retardé plutôt que GFT) n'a PAS été testé — piste
distincte non explorée si la question se repose.

### 2.15 Piste A' — 2× Blueberry parallèle, implémentée et testée (08/10 nuit, suite 3) — CONFIRMÉ à 3000$

Débloquée par la résolution du conflit Blueberry (§1.3, contact support
direct 2026-08-10 : aucune limite fixe de nombre de comptes, cap $400k
total). Implémentée selon le scoping §2.13 :
`etape_t_piste_a_prime_2x_blueberry_2026-08-10.py` généralise STARTERS
avec `STARTER_COUNT` (nb de comptes actifs au jour 0 par firm starter),
permet 2 comptes Blueberry (même risque éval) au lieu d'1 seul ou d'1
Blueberry+1 GFT. Coût jour 0 : 330$ (2×165$), moins cher que BB+GFT
(453$, §2.6) et BB+FTMO (510$). Rapport complet
`etape_t_piste_a_prime_2x_blueberry_2026-08-10.md`.

**Résultats n=300 (criblage 2 plafonds) puis n=600+cascade (ceiling=3000$,
où une domination a été trouvée)** — `solo_BB`/`BB_GFT_day0` reproduisent
exactement les chiffres déjà verrouillés du registre à n=600/3000$
(4 892 588$/0,50%/20,33% et 5 097 319$/0,67%/15,67%), confiance élevée :

| Config | Coût j0 | Plafond 1000$ (n=300) | Plafond 3000$ (n=600, confirmé) |
|---|---|---|---|
| solo_BB (réf) | 165$ | 5 005 612$ / 1,67% / 20,33% | 4 892 588$ / 0,50% / 20,33% |
| BB_GFT_day0 (réf §2.6) | 453$ | 4 738 812$ / 11,00% / 23,67% | 5 097 319$ / 0,67% / 15,67% |
| **BBx2 (piste A')** | **330$** | 4 722 355$ / 8,00% / 21,67% | **4 940 735$ / 0,33% / 17,00%** |

**Verdict — plafond 1000$ : REJETÉ**, BBx2 reste dominé par solo_BB sur
les 3 axes, mais confirme directement l'hypothèse du coût jour 0 plus
bas : vs BB+GFT (déjà rejeté à ce plafond), BBx2 réduit nettement le
verrou de trésorerie (ruine 8,00% vs 11,00%, cash@1er_financement 487$
vs 680$, struct_jamais_complète 7,33% vs 10,33%) — aide réellement, mais
pas assez pour rattraper le fait de ne pas rester solo à ce plafond
serré.

**Verdict — plafond 3000$ : CONFIRMÉ n=600 + cascade GO.** BBx2 domine
STRICTEMENT solo_BB sur les 3 axes (profit +0,98%, ruine -0,17pt,
année1<0 -3,33pt) — nouveau levier structurel validé. Cascade check
propre (casse≤30j 24,99% dans la fourchette des 2 références, quasi_gelé
0,17% meilleur que les 2 références). **Ne dépasse PAS BB_GFT_day0**
(profit/année1<0 supérieurs pour BB_GFT_day0, +3,2%/+1,33pt) mais BBx2
gagne sur la ruine (0,33% vs 0,67%) et le coût d'entrée (-27%) — un vrai
arbitrage à 3 branches (solo_BB < BBx2 < BB_GFT_day0 en profit/année1<0 ;
ordre inverse en ruine/coût), pas une domination totale d'une config sur
toutes les autres. Décision d'adoption (BBx2 vs BB_GFT_day0 vs solo_BB à
3000$) laissée à l'utilisateur.

### 2.16 Vérification empirique du cap Blueberry 450k$/3-comptes (08/10 nuit, suite 4)

Suite à la résolution du conflit Blueberry (§1.3/§4#6), vérification si
l'écart moteur (450k$/3 comptes codés) vs réalité confirmée (400k$
agrégé, aucune limite de nombre) a un impact réel sur les chiffres déjà
produits, plutôt que de le supposer. Méthode :
`etape_u_blueberry_cap_check_2026-08-10.py` (copie instrumentée de
`etape_t`), n=300, solo_BB et BBx2, 2 plafonds — trace le capital
Blueberry agrégé et le nombre de comptes atteints à chaque pas de temps
sur 1200 runs au total.

**Résultat — le point se scinde en deux problèmes de nature opposée** :
- **Cap $ (450k codé vs 400k confirmé) : JAMAIS sollicité.** Capital
  Blueberry max observé = 125 000$ (solo_BB) / 100 000$ (BBx2), très en
  dessous des deux figures. **Correction cosmétique, zéro impact.**
- **Cap NOMBRE (3 codé vs illimité confirmé) : sollicité dans 92,7% à
  100% des runs** — quasi systématique, pas un cas limite. Blueberry
  plafonne à 100-125k$ dans la quasi-totalité des runs, très en dessous
  du potentiel réel (~375k$ avant d'approcher le cap $ réel si le cap
  nombre était supprimé). **Sous-estimation structurelle potentielle et
  non quantifiée de la contribution Blueberry dans toute la chaîne de
  référence produite depuis l'introduction du mécanisme extra-compte
  (08/08)** — REF+V2 et piste A' (§2.15) tous deux concernés (BBx2
  sature aussi ce cap à 92,7-100%, donc la comparaison relative BBx2 vs
  solo_BB reste valide mais le niveau absolu des deux est probablement
  sous-estimé).

**Pas corrigé, pas retesté** — ampleur sur le profit final non mesurée
(nécessiterait un retest avec `FIRM_MAX_ACCOUNTS["Blueberry"]=None`).
Nouveau point ouvert §4#11.

### 2.17 Cap Blueberry CORRIGÉ dans le code + impact mesuré — MAJEUR (08/10 nuit, suite 5)

Suite à §2.16, correction appliquée dans le code (`etape_e_fleet_
integration.py:112-113`, module `ei` importé par TOUS les scripts de
production) : `FIRM_CAPITAL_CAP["Blueberry"]` 450 000$→**400 000$**,
`FIRM_MAX_ACCOUNTS["Blueberry"]` 3→**None** (aucune limite). FTMO/GFT/
Fivers **non touchés** (pas de vérification support équivalente).
Rapport complet `etape_v_blueberry_cap_fix_retest_2026-08-10.md`.

**REF+V2 (référence officielle) — n=600+cascade, avant/après même seed**
(avant à 1000$ reproduit EXACTEMENT le chiffre déjà verrouillé, validation
croisée) :

| Plafond | Avant (verrouillé) | Après (corrigé) | Δ profit |
|---|---|---|---|
| 1000$ | 4 927 916$/0,83%/21,00% | 5 736 759$/1,00%/21,83% | **+16,41%** |
| 3000$ | 4 936 929$/0,50%/21,00% | 5 751 134$/0,50%/21,83% | **+16,49%** |

Cascade check propre (casse≤30j légèrement meilleure, quasi_gelé
inchangé).

**Piste A' (solo_BB, BBx2) — n=300 screening** : +16,35% à +16,72% pour
solo_BB, +20,54% à +20,87% pour BBx2. Verdicts qualitatifs INCHANGÉS
(BBx2 rejeté à 1000$, confirmé à 3000$) mais l'écart à 3000$ SE CREUSE
(BBx2 vs solo_BB : profit +0,88%→+4,51%, ruine égale→meilleure). Pas
encore reconfirmé n=600 pour piste A'.

**Verdict : MAJEUR, pas négligeable ni juste significatif.** +16 à +21%
de profit, écart quasi identique aux deux plafonds (signal fort, pas du
bruit), ruine/année1<0 quasi inchangés en absolu (+0,17 à +0,83pt) — un
pur déblocage de capacité de croissance, pas un arbitrage risque/profit.
**Plus gros effet mesuré sur tout le chantier**, plus grand que tous les
leviers structurels confirmés combinés (reset Blueberry +3%, bootstrap
parallèle jusqu'à +4,2%, sizing DD V2 +0,93%, FTMO-10%/Goat Guard
+1,2%). Ce n'est pas un levier de trading/structure mais la correction
d'un paramètre codé en dur incorrect depuis l'introduction du mécanisme
extra-compte (08/08) — le moteur sous-estimait Blueberry depuis cette
date.

**⚠️ Le registre N'A PAS été mis à jour comme nouvelle référence
officielle** (§1.8 reste inchangé, chiffre 4 927 916$ toujours affiché) —
conformément à la consigne explicite de ne pas promouvoir sans
confirmation n=600+cascade COMPLÈTE (piste A' manquante) et sans décision
utilisateur. Voir décision §4#11 (mise à jour).

### 2.18 Décomposition du mécanisme du gain + retests piste A'/B sous cap corrigé (08/10 nuit, suite 6)

Suite au gain majeur §2.17, décomposition du mécanisme (n=600, même
seed, sans nouveau tirage aléatoire) + retest piste B (fongibilité) et
confirmation piste A' (BBx2) sous le cap corrigé. Rapport complet
`etape_x_gain_decomposition_et_verifs_2026-08-10.md`,
`etape_w_blueberry_gain_decomposition_2026-08-10.py`.

**Mécanisme clarifié — VOLUME pur, pas de détournement significatif :**
- Comptes extra Blueberry : 1,99-2,00 (avant) → **6,98-7,00 (après)**,
  cohérent avec le calcul théorique ((400k-25k)/50k=7,5).
- **Pas de détournement de comptes** : extras FTMO/GFT rigoureusement
  IDENTIQUES avant/après (2,99 exactement) — ils saturaient déjà leur
  propre cap $ indépendamment de Blueberry. Effet de bord P&L mineur sur
  les 4 autres firms (-0,05% à -0,14% chacune, dû à l'ordre d'itération
  `GROWTH_FIRMS_EXTRA` qui donne priorité à Blueberry sur la réserve
  partagée à certains instants) — négligeable face au gain Blueberry
  (+192,2%, +1 130 428$/+1 132 916$). La tension EV/$ redoutée (Blueberry
  classé avant-dernier, §2.8bis) ne se matérialise quasiment pas : la
  réserve n'est pas un jeu à somme nulle sur cette flotte.
- **Gain = volume, pas compounding** : `mean_days_to_fund` (délai moyen
  de financement flotte entière) rigoureusement IDENTIQUE avant/après
  (66,40452486496913j à 13 décimales, les 4 combinaisons plafond×cap) —
  le mécanisme extra-compte ne s'active qu'après déblocage complet, ne
  peut donc pas accélérer le déblocage initial. Confirmé par le fait que
  les 4 autres firms PERDENT (légèrement), pas gagnent, ce qui exclurait
  un effet de synergie de flotte positif.
- Réconciliation comptable : Δ net par firm cumulé (+1 122 377$/+1 128 071$
  avant IS) − Δ profit net mesuré (+808 843$/+814 205$) = IS
  supplémentaire payé sur le gain (~27,9% du gain brut) — cohérent,
  pas une anomalie.

**Piste B (fongibilité, §2.8) retestée n=300 sous cap corrigé — verdict
INCHANGÉ, REJETÉ.** Écart nul/bruit aux 2 plafonds (-276$/1000$,
strictement 0$/3000$) — **hypothèse du goulot d'étranglement commun
RÉFUTÉE** : le rejet original ne venait pas de l'ancien cap Blueberry,
il vient bien de la réserve non-scarce sur cette flotte (cohérent avec
le diagnostic (b) ci-dessus). Pas de reconfirmation n=600 nécessaire
(écart nul, pas juste petit).

**Piste A' (BBx2, §2.15) confirmée n=600+cascade GO sous cap corrigé à
3000$ — écart RENFORCÉ.** solo_BB=5 707 481$/0,50%/21,17% vs
BBx2=**5 953 550$/0,33%/17,33%** — profit **+4,31%** (vs +0,98% sous
l'ancien cap), ruine meilleure, année1<0 -3,84pt. Cascade propre.
Cohérent : BBx2 a 2 starters Blueberry, bénéficie plus du déplafonnement
que solo_BB (1 starter).

**Conclusion** : rien dans ce diagnostic ne s'oppose techniquement à
l'adoption du chiffre corrigé — mais l'adoption formelle en §1.8 reste
une décision utilisateur (§4#11).

### 2.19 Extension du mécanisme extra-compte à Fivers — REJETÉ, effet nul par construction (08/10 nuit, suite 9)

Suite au succès Blueberry (§2.17-2.18), test de la même généralisation
pour Fivers : les valeurs `FIRM_CAPITAL_CAP["Fivers"]=500000`/
`FIRM_MAX_ACCOUNTS["Fivers"]=5` existent déjà dans le code mais ne sont
jamais lues (`GROWTH_FIRMS_EXTRA=("Blueberry","FTMO","GFT")`, Fivers
absent). `etape_y_fivers_growth_test_2026-08-10.py` (copie de `etape_q`,
`growth_firms` paramétré, pas de modification du module `ei` partagé —
hypothèse à tester, pas une correction confirmée).

**Résultat arithmétique, vérifié avant ET après simulation (n=300, 2
plafonds)** : capital initial Fivers = 4×100 000$ (High Stakes) =
400 000$ ; cap agrégé = 500 000$ → marge 100 000$. Unité d'extra-compte
(convention 2×palier, identique à Blueberry/FTMO/GFT) = 200 000$ > marge
→ **le cap CAPITAL bloque structurellement tout extra-compte, avant même
de solliciter la réserve.** Confirmé empiriquement : `fivers_extra_moy
=0,00` sur 100% des 1200 runs (2 configs × 2 plafonds × 300 sims),
résultats baseline et Fivers-extra **bit-identiques** aux deux plafonds.

**Verdict : REJETÉ, effet nul par construction — pas un bug de valeur
comme Blueberry.** La différence : le palier de départ de Blueberry
(25k$) est petit par rapport à son cap (400k$), laissant beaucoup de
marge pour la croissance ; celui de Fivers (100k$ High Stakes) est déjà
large par rapport à son propre cap (500k$), donc la marge résiduelle
après les 4 comptes initiaux (100k$) est plus étroite qu'une seule unité
d'extra-compte (200k$). La concentration de risque Fivers déjà connue
(~75% du cash pire-cas pré-immunité, `project_preimmunity_5ers_delay_
2026-08-06`) ne se matérialise donc PAS avec ce lever — la question ne
se pose jamais empiriquement puisque le mécanisme ne s'active jamais.

**Condition de réouverture** : nécessiterait soit une unité d'extra-
compte plus petite que 2×palier spécifiquement pour Fivers, soit un
format de départ plus petit (Hyper Growth, 40k$) laissant plus de marge
sous le cap 500k$ — changement de format hors périmètre de ce test, non
exploré.

### 2.20 🔴 Seuil copytrade Fivers 500k — DÉPASSEMENT QUASI SYSTÉMATIQUE trouvé (08/10 nuit, suite 10)

Le support Fivers interdit le copytrade au-delà de 500 000$ de capital
géré (paliers + equity non retirée). Vérification directe sur la
config officielle REF+V2 (structure Fivers actuelle, 4 comptes fixes,
sans le mécanisme extra-compte rejeté §2.19) :
`etape_z_fivers_500k_check_2026-08-10.py` trace
`Σ(palier + cumulative_since_reset)` sur les comptes Fivers actifs à
chaque pas de temps, garde le maximum observé sur toute la durée du run
(aucune tolérance de durée).

**Résultat n=600 : 99,17%/99,67% des runs (1000$/3000$) dépassent
500 000$**, avec un pic MOYEN de ~2,13M$ (4,3× le seuil) et un pic PIRE
CAS de 6,0M$ (12× le seuil), typiquement autour du mois 37 (>3 ans).
**Ce n'est pas un dépassement marginal — c'est le comportement normal du
modèle.** Cause mécanique : `cumulative_since_reset` (solde flottant par
compte) n'a aucun plafond haut dans le moteur (seul le plancher bas est
vérifié pour la casse), et le risque par trade est calculé sur le palier
FIXE (pas l'équité courante) — le solde croît sans jamais être "prélevé"
côté plateforme dans le modèle actuel, faute d'événement de retrait
modélisé.

**Diagnostic seul, aucune correction appliquée** (comme demandé) — ne
tranche pas si c'est un bug de modélisation (absence d'événement de
retrait périodique) ou un vrai risque opérationnel non géré par le
projet. Nouveau point ouvert prioritaire §4#12.

### 2.21 Vérification du mécanisme de casse/reset fleet-wide — CONFIRMÉ CORRECT (08/10 nuit, suite 10)

Question distincte de §2.20, plus large (toutes firms) : le profit
accumulé sur un compte au moment de sa casse est-il déjà transféré
ailleurs avant le reset, ou perdu ? Vérifié par lecture de code
(`engine_multiformat.py:308-367`, `process_trade_mf`) :

```python
# lignes 337-341, exécuté a CHAQUE trade AVANT la detection de casse
if acc["phase"] == "funded":
    net_pnl = pnl * split_flat if pnl > 0 else pnl
    acc["total_funded_pnl"] += net_pnl                    # alimente combined_net()
    if net_pnl > 0:
        state["reserve"] += net_pnl * reserve_share        # cash reel transfere immediatement
# lignes 349-367 : _reset_trackers() sur casse ne touche QUE cumulative_since_reset/
# peak_since_reset/trading_days_since_reset/daily_pnl/locked_peak/eod_peak/last_day_seen
# (engine_multiformat.py:259-266) — JAMAIS total_funded_pnl ni total_fees_paid
```

**Verdict : (a) confirmé — aucune perte de profit à la casse.** Le split
du trader et le versement en réserve sont crédités trade par trade,
avant même que la logique de casse ne s'exécute pour ce même trade.
`cumulative_since_reset` est une variable de suivi de drawdown distincte
du profit déjà banké — sa remise à zéro sur casse ne représente jamais
une perte de gains déjà réalisés. Pas de quantification nécessaire (le
montant "perdu" est nul par construction, pas juste faible). Mécanisme
déjà correct, rien à corriger.

**Clarifié 08/10 nuit suite 12** (pas de "double comptage") :
`reserve_share` n'est PAS prélevé sur `cumulative_since_reset` — deux
accumulateurs indépendants dérivés du même `pnl` brut, servant des
usages différents (`cumulative_since_reset` = solde brut compte, sert
au DD ET au diagnostic Fivers 500k §2.20 ; `total_funded_pnl`/`reserve`
= part nette, sert au profit final `combined_net()`). Aucun des deux
n'entre dans l'autre — pas de surestimation du profit REF+V2 à
quantifier. Le vrai problème (déjà identifié §2.20) reste l'ABSENCE
d'événement de retrait simulé, pas un doublon comptable. Vérifié aussi :
`acc["palier"]` (taille de position) ne dépend jamais de
`cumulative_since_reset` — seul `reopen_account()` le modifie, et
uniquement pour le REDESCENDRE à `base_palier` (downgrade-on-reopen),
jamais pour le faire croître. Pas de re-fuite du bug de scaling
interne déjà écarté (`project_scaling_mechanism_bug_2026-08-08`).

### 2.22 Écart de profit année1<0 vs année1>0 sous le moteur corrigé (08/10 nuit, suite 11)

`etape_aa_annee1_profit_gap_2026-08-10.py`, référence officielle
(REF+V2+cap corrigé+FTMO-10/GoatGuard), n=600, même seed :

| Plafond | Profit moyen année1<0 | Profit moyen année1>0 | Écart | % du profit moyen |
|---|---|---|---|---|
| 1000$ | 4 491 195$ | 6 084 668$ | +1 593 473$ | **27,8%** |
| 3000$ | 4 555 432$ | 6 085 115$ | +1 529 682$ | **26,6%** |

**Verdict : l'écart historique (~30%+, mesuré avant la refonte multi-
phase et avant la correction Blueberry) tient toujours**, légèrement
réduit mais du même ordre de grandeur. ~21,8% des runs finissent
année1<0 aux deux plafonds (n_neg=131/600).

### 2.23 Resweep éval au-delà de 1,25% sous moteur corrigé (08/10 nuit, suite 11) — pas de free lunch net

`etape_ab_eval_risk_resweep_2026-08-10.py`, screening n=300
{1,25/1,50/1,75/2,00/2,50/3,00%} puis confirmation n=600 des 2 points
candidats (1,75%/2,00%), flotte=1,90% inchangé.

**Screening n=300** suggérait un pic de profit vers 1,75% — **la
confirmation n=600 révèle que ce n'est PAS un free lunch** :

| éval | Plafond 1000$ (profit/ruine/année1<0) | Plafond 3000$ (profit/ruine/année1<0) |
|---|---|---|
| 1,25% (réf) | 5 736 759$/1,00%/21,83% | 5 751 134$/0,50%/21,83% |
| 1,75% | 5 818 917$ (+1,43%)/2,67%/23,00% | 5 874 891$ (+2,15%)/1,50%/22,50% |
| 2,00% | 5 614 651$ (**-2,13%**)/6,00%/23,17% | 5 880 751$ (+2,26%)/1,17%/**20,67%** |

**Point de retournement : entre 1,75% et 2,50%**, effondrement net
au-delà (screening n=300 seul, non reconfirmé n=600 : à 2,50%
ruine=20,00%/casse≤30j=53,68% à 1000$ ; à 3,00% ruine=22,00%/casse=
59,53%).

**Verdict : pas de domination claire à 1000$** (1,75% coûte 2,7× plus
de ruine pour +1,4% de profit seulement ; 2,00% est net PIRE sur profit
ET ruine — l'apparent presque-pic screening n=300 à 2,00% était du
bruit, confirmé par la reconfirmation n=600). **Proche d'un vrai gain à
3000$ sans être écrasant** : 2,00% domine quasiment (profit +2,26%,
ruine +0,67pt en absolu, année1<0 MEILLEUR -1,16pt) mais le ratio de
ruine reste ×2,3 malgré son faible niveau absolu — pas assez net pour
un GO automatique, décision liée au plafond (#9) et au goût du risque
réel de l'utilisateur, pas un simple calcul technique.

### 2.24 Nombre de casses pré/post-déblocage par firm sous moteur corrigé (08/10 nuit, suite 12)

`etape_ac_breaks_by_firm_2026-08-10.py`, n=600, référence officielle :

| Plafond | PRÉ total | Blueberry | FTMO | Fivers | GFT | FundedNext |
|---|---|---|---|---|---|---|
| 1000$ | 4,42 | 1,41 | 1,99 | 1,03 | 0,00 | 0,00 |
| 3000$ | 4,49 | 1,42 | 2,01 | 1,05 | 0,00 | 0,00 |

| Plafond | POST total | Blueberry | FTMO | Fivers | GFT | FundedNext |
|---|---|---|---|---|---|---|
| 1000$ | 134,23 | 48,32 | 31,81 | 27,38 | 19,06 | 7,66 |
| 3000$ | 134,52 | 48,42 | 31,89 | 27,43 | 19,10 | 7,68 |

GFT/FundedNext n'ont structurellement AUCUNE casse pré-déblocage (pas
starters). Post-déblocage domine massivement en volume (~30× le
pré-déblocage sur les 3 starters) — cohérent avec le diagnostic déjà
établi (fragilité pré-déblocage = concentration/points-de-défaillance-
uniques, pas volume ; le vrai risque post-déblocage vient du VOLUME de
cycles casse-restart, cf. §2.5 diagnostic structurel).

### 2.25 Politique casse/payout des 5 firms — recherche sourcée (08/10 nuit, suite 12)

Recherche web ciblée (agent dédié), sources officielles (help center/
conditions générales) priorisées :

| Firm | Profit non versé perdu à la casse ordinaire ? | Cadence de retrait | Confiance |
|---|---|---|---|
| FTMO | **NON** — Account Agreement Clause 12.3, part au prorata préservée sauf violation grave (12.4) | Dès J14, à la demande ensuite, min 20-50$, ~2-4j ouvrés | Élevée (contrat officiel cité) |
| GFT | Non trouvé officiellement pour casse ordinaire (seule mention explicite = hedging/pratiques interdites) | Tous les 14j, min 100$ (35$ Goat $1), ~2j ouvrés | Moyenne |
| Blueberry | **OUI** — "brought back to funded stage, minus the profits" (help center officiel) | Tous les 14j (option à la demande payante), min 100$, ~1-2j ouvrés | Élevée |
| The5%ers | **Non confirmé officiellement** — pages officielles inaccessibles lors de la recherche, sources tierces uniquement | ~14j, min ~150$, ~72h (sources tierces) | Faible — à vérifier support si besoin |
| FundedNext | Nuancé — dépend de la sévérité/lien avec la violation, pas automatique | Variable par format (5-14j), min 20$, ~24h | Moyenne (page indexée mais fetch direct échoué) |

**Constat pour un futur mécanisme de retrait** : cadence réelle ~14
jours dans presque tous les cas, montants minimaux 20-150$, traitement
1-3 jours. Utile pour scoper un mécanisme de retrait périodique
réaliste si le point ouvert §4#12 (seuil 500k Fivers) est un jour
retenu comme prioritaire à corriger. Aucune correction appliquée à ce
stade — diagnostic seul, comme demandé.

**Contact support 08/10 nuit suite 13** : confirme explicitement que
Blueberry, GFT et The5%ers NE préservent PAS le profit non versé à la
casse (comme Blueberry, déjà su) — FTMO (Clause 12.3) et FundedNext
CONFIRMÉS préservés. Le correctif ci-dessous (§2.26) ne concerne donc
QUE ces 3 firms.

### 2.26 Cycle de payout réaliste implémenté (Blueberry/GFT/Fivers) — impact MODÉRÉ mais réel (08/10 nuit, suite 13)

`etape_ad_payout_cycle_2026-08-10.py` : cycle de payout 14 jours par
compte (Blueberry/GFT/Fivers uniquement) — les GAINS s'accumulent dans
`pending_payout` (en attente), versés tous les 14j, PERDUS sur une
casse avant le prochain versement. Les PERTES frappent toujours
immédiatement (jamais protégées). FTMO/FundedNext inchangés (crédit
instantané, comportement déjà correct — confirmé préservé). Driver
`etape_ae_payout_cycle_ablations_2026-08-10.py`, n=300 screening puis
n=600 confirmation, 2 plafonds. Rapport complet `etape_ae_payout_
cycle_results_2026-08-10.md`.

**Chiffre candidat corrigé (n=600, PAS encore adopté §1.8)** :

| Config | Plafond 1000$ | Plafond 3000$ |
|---|---|---|
| Référence actuelle | 5 736 759$/1,00%/21,83% | 5 751 134$/0,50%/21,83% |
| **Candidat corrigé (cycle payout)** | **5 510 750$/1,33%/27,67%** | **5 539 307$/0,33%/27,50%** |
| Écart | **-3,94%**, ruine ≈inchangée, **année1<0 +5,84pt** | **-3,68%**, ruine ≈inchangée, **année1<0 +5,67pt** |

**Décomposition par firm** (montant moyen forfaité/run, 1000$) :
Fivers 56 277$ (42,2%), Blueberry 53 643$ (40,2%), GFT 23 561$
(17,7%) — **99,6% du montant total (133 481$) est POST-déblocage**
(508$ seulement en pré-déblocage), cohérent avec le volume de casses
déjà quantifié (§2.24, ~4,4 pré vs ~134 post par run).

**GFT Goat Guard reconfirmé, légèrement plus précieux** : valeur isolée
+1,27% aux deux plafonds (vs +1,04-1,21% avant la correction) — Goat
Guard réduit la casse GFT forfaitée d'environ moitié, mais son bénéfice
principal restait déjà le coût de restart structurel — hausse réelle
mais modeste, pas une révision majeure.

**V2 (sizing DD pré-déblocage) reconfirmé BIEN calibré, hypothèse de
mauvais calibrage RÉFUTÉE** : valeur isolée +1,21% à 1000$ (vs +0,93%
avant, hausse légère) et ~0% à 3000$ (inchangé) — V2 est légèrement PLUS
utile sous la correction, pas moins, malgré le fait qu'il raisonne sur
le solde brut et non sur `pending_payout` spécifiquement : éviter une
casse près du seuil DD évite maintenant DEUX coûts cumulés (restart +
forfait) au lieu d'un, donc le ciblage imprécis reste net positif.
Écran n=300 avait suggéré un quasi-doublement (+1,86%), NON confirmé à
n=600 (retombe à +1,21%) — bon exemple de bruit corrigé par
reconfirmation.

**Statut : PAS encore adopté dans le registre §1.8** — décision
d'adoption laissée à l'utilisateur, même convention que la correction
Blueberry avant son feu vert explicite. Nouveau point de décision §4#13.

### 2.27 Tableau récapitulatif — pistes REJETÉES cette session (08/09-08/10, à ne pas retester sans raison nouvelle)

Consolidation de toutes les pistes closes/rejetées produites pendant ce
chantier, pour éviter de les re-proposer par erreur après un clear de
contexte. Détail complet dans la section §2.x citée pour chacune.

| Piste | Section détaillée | Raison précise du rejet | Condition de réouverture |
|---|---|---|---|
| **Fongibilité inter-firm** | §2.8 (implémentée + retestée §2.18) | Réserve NON-scarce sur cette flotte — dans l'immense majorité des cas la réserve dépasse largement le coût total de tous les candidats en compétition simultanément, la priorité EV/$ n'a jamais l'occasion de trancher. Confirmé par débogage instrumenté (1/30 runs a montré une divergence, et même celle-là identique sur le profit final). Retesté sous cap Blueberry corrigé : verdict INCHANGÉ, l'hypothèse du goulot d'étranglement commun est RÉFUTÉE | **FERMÉE DÉFINITIVEMENT** — testée sous 2 régimes de cap Blueberry distincts, aucune piste plausible ne subsiste ; nécessiterait une refonte de l'architecture de flotte elle-même, pas un paramètre |
| **Coupe-circuit réactif** (performance récente) | §2.7 | Signal de mauvaise passe récente = bruit statistique pur sur un pool à edge positif haute variance, pas un vrai signal de dégradation de l'edge. 24 configs testées (3 fenêtres × 2 seuils entrée × 2 seuils sortie × 2 réductions), aucune ne domine la baseline sur 2+ axes | Seulement si un signal MOINS bruité est proposé (fenêtre bien plus large, ou couplage à un indicateur différent) — pas en resweepant la même grille avec d'autres seuils |
| **Saut de phase payant** | (recherche seule, jamais eu de section §2.x dédiée avant cette consolidation) | Recherché sur 8 requêtes web ciblées (par firm + 2 génériques) — confirmé qu'aucune des 5 firms ne vend de produit "sauter la phase 1, démarrer en phase 2/financé" distinct du financement instantané classique déjà connu et déjà écarté (trop cher, cf. §2.6 combos bootstrap parallèle) | Seulement si une nouvelle source apparaît (nouveau produit lancé par une firm, ou info directe support comme celle obtenue pour le reset Blueberry ou le cap 400k$) |
| **Piste H** (routage flotte-wide sur paire corrélée AUD/JPY-USD/CHF) | §2.12 | Effet NUL confirmé — `pct_post_neg_touching_all5` reste à 100,0%→100,0%, strictement inchangé aux deux plafonds. Confirme le signal source déjà identifié trop faible au scoping (corr=-0,09) | Ne pas retenter sur cette paire spécifique |
| **Démarrage différé du 2e starter** (BB+GFT, GFT retardé plutôt que jour 0) | §2.14 | Délais en JOURS (7/14/21j) : engagent quand même le plein coût sur le même budget serré, ne battent jamais solo_BB à 1000$. Délais en RÉSERVE (100/250/500$) : se déclenchent trop rarement, dégénèrent en solo_BB dans la quasi-totalité des runs. Aucune variante ne bat solo_BB@1000$ ni BB_GFT_day0@3000$ | Seulement si le coût absolu de GFT (288$) baisse significativement, ou si piste A' échoue aussi — **piste A' a depuis été CONFIRMÉE à 3000$ (§2.15/§2.18), donc cette branche de la condition ne s'est pas matérialisée** ; démarrage différé reste fermé |
| **Croissance Fivers** (extension du mécanisme extra-compte à Fivers) | §2.19 | Effet NUL par construction, pas un bug de valeur — le capital initial des 4 comptes fixes (400 000$) plus l'unité d'extra-compte (2×palier=200 000$) dépasse le cap agrégé (500 000$) avant même de solliciter la réserve. Confirmé bit-identique (baseline = variante testée) sur 1200 runs (n=300, 2 configs, 2 plafonds) | Nécessiterait une unité d'extra-compte plus petite que 2×palier spécifique à Fivers, ou un format de départ plus petit (Hyper Growth, 40k$, laissant plus de marge sous le cap) — non exploré |
| **Thèse initiale piste A** (ruine BB+GFT causée par "casse rapprochée"/"double-réussite") | §2.11 (mentionnée en passant, jamais eu sa propre ligne récapitulative avant) | Décomposition Étape K : casse rapprochée seulement 3/64 cas, double-réussite 0/600 — les deux mécanismes spéculés sont EXCLUS par les données. La thèse de remplacement (détournement de réserve via `group_funded_count`) a ensuite AUSSI été testée par trace directe et RÉFUTÉE (0/600 occurrences, §2.11) | **INVALIDÉE ET REMPLACÉE** — le vrai mécanisme (épuisement de marge de trésorerie initiale, vérifié par trace directe, BB+GFT dépense 2,5× plus avant le 1er financement) est confirmé et documenté en §2.11 ; ne pas retester ces deux thèses précises, base déjà exclue par les données |

### 2.28 Vérification méthodologique du cycle de payout (08/11) — code confirmé, décision #13 inchangée

Relecture ligne par ligne de `etape_ad_payout_cycle_2026-08-10.py` en
réponse aux 4 sous-questions ouvertes en §1.8 :

1. **Automaticité** — `if use_payout_cycle and acc["active"] and
   acc["last_payout_time"] is not None and now - acc["last_payout_time"]
   >= PAYOUT_CYCLE_DAYS * 86400:` (ligne 375-381) déclenche le versement
   sans condition d'action du trader. **Choix de modélisation explicite,
   non confronté à la politique réelle "automatique vs demande manuelle"
   de chaque firm** — seule la cadence 14j est sourcée.
2. **Disponibilité pour `state["reserve"]`** — le crédit est annulé au
   gain (ligne 361-366 : `state["reserve"] -= delta * reserve_share`)
   puis restitué au flush (ligne 377-380 : `state["reserve"] +=
   acc["pending_payout"] * reserve_share`). Confirmé : l'argent ne sort
   jamais du circuit de simulation, juste retardé.
3. **Suivi par compte** — `acc["last_payout_time"]` est une clé par
   compte, réinitialisée à chaque `reopen_account` (ligne 191),
   `open_group` (ligne 206) et ouverture de compte extra (ligne 248).
   Confirmé PAR COMPTE, pas flotte-wide.
4. **Périmètre casse dure** — le forfait (lignes 397-406, dans `elif
   broke:`) est mutuellement exclusif avec la branche soft-breach Goat
   Guard (`if use_goat_guard:`, lignes 390-396, qui ne touche jamais
   `pending_payout`). Confirmé par construction du code.

**Verdict** : points 2/3/4 confirmés corrects par construction. Point 1
reste une hypothèse de modélisation non vérifiée contre la politique
réelle — la vérification de code ne remplace pas la décision
d'adoption utilisateur. Décision #13 §4 **inchangée** (candidat, pas
adopté).

### 2.29 🔴 Fichier historique flotte périmé (646→721 trades) — impact mesuré, PAS le "faible" attendu

Point ouvert #2 de `registre_strategie_trading.md` (§4) scopé et mesuré :
`rr_threshold_test.py:37` (`HIST_PATH = "historique_lutessia_15k.csv"`,
646 trades filtrés, arrêté au 27/07) est le fichier source utilisé par
`build_extended_population` → `build_realistic_payoff_population` →
`build_population_with_trailing`, donc par TOUS les scripts flotte
courants. Le fichier à jour `historique_lutessia_15k_force.csv` (721
trades filtrés, jusqu'au 30/07, disponible depuis le 01/08) n'est
utilisé nulle part dans le moteur de simulation.

**Mesure d'impact** (`etape_af_pop721_impact_2026-08-11.py`, n=300,
seed=9999, même config que la référence officielle à chaque plafond —
REF+V2+FTMO-10%/GFT Goat Guard à 1000$, solo_BB REF pure à 3000$, cap
Blueberry corrigé) :

| Plafond | Profit (646, baseline existante n=300) | Profit (721) | Δ profit | Ruine (646→721) | Année1<0 (646→721) |
|---|---|---|---|---|---|
| 1000$ | 5 955 479$ | 5 747 336$ | **-208 142$ (-3,50%)** | 1,00%→1,33% | 21,67%→26,00% (+4,33pt) |
| 3000$ | 5 915 842$ | 5 727 768$ | **-188 074$ (-3,18%)** | 0,67%→0,67% (inchangé) | 20,33%→25,00% (+4,67pt) |

**L'effet n'est PAS "faible" comme anticipé** (l'hypothèse de départ,
89,6% de données communes → écart mineur, ne se vérifie pas) — profit
-3,2 à -3,5%, année1<0 +4,3 à +4,7pt aux deux plafonds. Le winrate brut
des deux populations est proche (40,09% vs 40,36%, cf.
`registre_strategie_trading.md`), donc l'écart vient surtout du payoff
réaliste TP1/TP2 (nouvelle vérification de continuation sur les ~75
trades supplémentaires, EV réaliste mesurée +0,815R sur la population
721 — pas de valeur directement comparable loggée pour la population
646 dans cette session).

**PAS appliqué au moteur de production** (le fichier `HIST_PATH` global
n'a pas été modifié — seul un script de mesure isolé l'a patché
temporairement) — écart trop important pour un changement silencieux.
Décision d'adoption laissée à l'utilisateur, même convention que la
correction du cap Blueberry et le cycle de payout. Voir décision #14 §4
(nouvelle).

### 2.30 Resweep éval 1,00/1,25/1,75% reconfirmé (08/11) — 1,75% ne dépasse 1,25% QUE sur l'axe profit

Relance de `etape_ab_eval_risk_resweep_2026-08-10.py` (n=300, seed=9999,
même config officielle, fichier historique 646 inchangé) pour documenter
précisément l'écart 1,75% vs 1,25% déjà entrevu en §2.23 sans chiffres
détaillés à ce triplet exact :

| éval | Plafond | Profit | Ruine | Année1<0 (pré) |
|---|---|---|---|---|
| 1,00% | 1000$ | 5 744 545$ | 1,33% | 25,67% (12,33%) |
| 1,00% | 3000$ | 5 791 455$ | 0,67% | 25,33% (12,00%) |
| **1,25% (réf)** | 1000$ | 5 955 479$ | 1,00% | 21,67% (9,67%) |
| **1,25% (réf)** | 3000$ | 5 964 918$ | 0,67% | 21,67% (9,67%) |
| 1,75% | 1000$ | 6 072 190$ | 1,33% | 23,00% (9,00%) |
| 1,75% | 3000$ | 6 113 521$ | 1,00% | 22,00% (8,00%) |

**1,25% domine 1,00% confirmé** (acquis, pas re-questionné) : profit
meilleur aux deux plafonds, année1<0 meilleur aux deux plafonds
(-4,0pt/-3,7pt), ruine meilleure à 1000$ et à égalité à 3000$ (0,67%
des deux côtés).

**1,75% vs 1,25% — un seul axe favorable, pas un avantage partiel
multi-axes** :
- Profit : 1,75% GAGNE aux deux plafonds (+116 711$/+1,96% à 1000$ ;
  +148 603$/+2,49% à 3000$).
- Ruine : 1,75% PERD aux deux plafonds (+0,33pt/+0,33pt).
- Année1<0 : 1,75% PERD aux deux plafonds (+1,33pt à 1000$ ;
  +0,33pt à 3000$).

Cohérent avec la confirmation n=600 déjà en registre (§2.23,
`etape_ab_eval_risk_resweep_n600.csv`) : 1000$ n=600 profit +1,43%/ruine
+1,67pt (2,7×) ; 3000$ n=600 profit +2,15%/ruine +1,00pt (3×). **Verdict
inchangé** : pas un free lunch, un vrai tradeoff profit-vs-risque, décision
personnelle si adoptée — ne modifie pas le statut de la décision #2 §4
(éval=1,25% reste la référence de travail).

### 2.31 🔴 "ruine" (net<0 an4) ≠ "hit_ceiling" — écart mesuré, aucune des deux ne capture "irréversible" (08/11)

Investigation demandée suite à §2.30/correction de vocabulaire : la
métrique "ruine" rapportée partout (`(net < 0).mean()` à l'année 4) ne
correspond PAS au concept projet "épuisement irréversible du plafond
personnel". `state["hit_ceiling"]` existe mais n'était jamais remonté
dans les résultats — patché dans une copie dédiée
(`etape_ag_hit_ceiling_measure_2026-08-11.py`, ajoute une seule ligne
`"hit_ceiling": state["hit_ceiling"]` au dict de retour, reste identique
au moteur officiel `etape_q_v2_plus_ftmo_gft_2026-08-10.py` sinon).

**1. Condition de déclenchement** — `handle_cost_hybrid()` (lignes
125-141) : quand le coût d'un événement (réouverture de compte cassé,
ouverture d'un groupe de firms) dépasse `state["reserve"]` ET que le
manque (`shortfall`) dépasse la place encore disponible sous le plafond
(`room = ceiling - real_cash_paid`), `real_cash_paid` est poussé
exactement à `ceiling` (toute la place restante consommée) et
`state["hit_ceiling"] = True` est posé **une fois pour toutes** (jamais
remis à False). L'événement lui-même est différé dans une liste
d'attente (`pending_reopen`/`pending_group_open`), retenté à chaque
trade via `process_pending()`. Confirme bien "le plafond personnel est
plein et il manque du cash pour cet événement précis" — mais c'est un
déclencheur PONCTUEL (au moment d'un paiement), pas un état continu
vérifié en permanence.

**2. Taux mesurés** (n=300, seed=9999, config officielle REF+V2+FTMO-10%/
GFT Goat Guard, cap Blueberry corrigé, **population 646 trades** — la
même que les chiffres déjà en registre, PAS encore la 721 corrigée en
§2.29/§4#14, pour comparaison directe) :

| Plafond | ruine (net<0 an4) | hit_ceiling | Croisement |
|---|---|---|---|
| 1000$ | **1,00%** (3/300) | **2,33%** (7/300) | hit_ceiling ET ruine=2 · hit_ceiling SANS ruine=5 · ruine SANS hit_ceiling=1 |
| 3000$ | **0,67%** (2/300) | **1,00%** (3/300) | hit_ceiling ET ruine=1 · hit_ceiling SANS ruine=2 · ruine SANS hit_ceiling=1 |

`hit_ceiling` est plus fréquent que `ruine` aux deux plafonds (2,33× à
1000$, 1,5× à 3000$), mais la majorité des runs `hit_ceiling` NE finissent
PAS ruinés (5/7 à 1000$, 2/3 à 3000$) — ils touchent le plafond
temporairement puis récupèrent. Et environ un tiers (1000$) à la moitié
(3000$) des runs `ruine` n'ont JAMAIS touché le plafond — pure
sous-performance EV sans jamais être bloqués en cash. **Les deux
métriques se recoupent partiellement mais mesurent des choses
différentes.**

**3. La simulation continue après hit_ceiling — code + preuve empirique.**
`process_pending()` est appelé à chaque trade ; dès que
`state["reserve"] >= item["cost_remaining"]`, l'événement différé se
déclenche automatiquement (pas d'arrêt du moteur). Confirmé par les
chiffres ci-dessus : la majorité des runs `hit_ceiling=True` finissent
NET POSITIFS à l'année 4. **`hit_ceiling` ne capture donc PAS non plus
"irréversible" au sens strict** — c'est un blocage de cash temporaire, pas
un game-over.

**4. Recommandation** : aucune des deux métriques existantes ne
correspond exactement au concept projet "épuisement irréversible du
plafond". Renommer pour clarifier plutôt que remplacer :
- `ruine` → renommer en `solde_negatif_annee4` (ou équivalent) : ce que
  le nom actuel ne dit pas, c'est que ce n'est ni un blocage de cash ni
  nécessairement irréversible, juste un résultat final défavorable.
- `hit_ceiling` → l'exposer comme métrique séparée (`plafond_atteint_au_
  moins_une_fois`), mais avec le même avertissement : ~65-70% des cas
  récupèrent, ne pas l'appeler "ruine" non plus sans qualification.
- Un concept "irréversible" au sens strict n'existe dans aucune métrique
  actuelle — s'en approcherait le plus `struct_never_complete_pct` déjà
  utilisé pour le mécanisme de ruine BB+GFT (§2.11, `etape_t`/`etape_o`),
  mais jamais généralisé à toute la flotte. Pas construit ici — décision
  utilisateur nécessaire sur la définition exacte avant de le coder (voir
  décision #15 §4, nouvelle).
**Aucun chiffre de référence n'a été régénéré** — mesure diagnostique
uniquement, comme demandé.

### 2.32 🔴 Bug de calibration trouvé — PAYOUT_CYCLE_DAYS était une constante unique, pas par firm/occurrence (08/11)

Vérification demandée avant de relancer la décomposition délai/
forfeiture : `PAYOUT_CYCLE_DAYS = 14` (`etape_ad_payout_cycle_2026-08-10
.py`/`etape_ah_reference_officielle_2026-08-11.py`, ligne ~54) était bien
**une constante unique, appliquée identiquement aux 3 firms
(Blueberry/GFT/Fivers) et à CHAQUE cycle** (pas de distinction 1er
retrait vs suivants) — confirmé en lisant le code, pas supposé. Ceci
divergeait nettement des cadences réelles confirmées par support :
Blueberry 14j répété (proche du défaut), **GFT 3j au 1er retrait PUIS "à
la demande" ensuite** (très différent), Fivers ~14j (source tierce).

**Corrigé** (`etape_ai_payout_cadence_calibration_2026-08-11.py`) :
`PAYOUT_CYCLE_DAYS_FIRST`/`PAYOUT_CYCLE_DAYS_SUBSEQUENT` indexés par
firm remplacent la constante unique — Blueberry/Fivers restent à 14j,
GFT passe à 3j puis 1,5j ("à la demande" modélisé comme délai minimal,
pas un cycle répété). Chaque compte suit `acc["_first_payout_done"]`
(False à la création/réouverture, passe à True au 1er flush du cycle),
réinitialisé aux 4 mêmes points que `pending_payout`/`last_payout_time`.

**Run C relancé (n=300, seed=9999, config complète + cadence corrigée)** :

| Plafond | Profit moyen/médian | solde_negatif_annee4 | hit_ceiling_pct | Année1<0 |
|---|---|---|---|---|
| 1000$ | 5 588 381$ / 5 336 808$ | 1,33% | 3,33% | **32,67%** |
| 3000$ | 5 629 882$ / 5 361 131$ | 0,33% | 1,67% | **32,67%** |

Comparé à l'ancien résultat n=600 non corrigé (36,83%/36,67% année1<0,
§1.8) : **-4,16pt/-4,00pt** — ⚠️ comparaison n=300 vs n=600, pas
strictement apples-to-apples, mais l'écart "en trop" identifié en §1.8
(interaction super-additive, +15,00pt observé vs +10,17pt attendu en
additivité naïve, soit ~+4,83pt d'excès) **se réduit de façon quasi
exacte** avec cette correction (-4,16/-4,00pt de réduction pour ~4,83pt
d'excès à expliquer). Suggère fortement que la cadence GFT mal calibrée
était le principal moteur de l'interaction non expliquée. **Confirmation
n=600 pas encore relancée** — à faire après la décomposition Run A/B
demandée (pas avant, pour ne pas décomposer un effet encore mal calibré).

### 2.33 Run E — rythme de versement seul, SANS aucune casse (08/11)

Test d'isolation demandé : la config actuelle complète (cadence
corrigée §2.32) mais avec la casse désactivée **au niveau cash
uniquement** (`etape_aj_run_e_no_casse_2026-08-11.py`) — aucun coût de
réouverture, aucune indisponibilité, aucun forfeit de `pending_payout`
sur breach. Le tracking DD interne (`process_trade_mf`, code partagé)
continue de se réinitialiser normalement au moment d'un breach ; seul le
volet CASH de la casse est neutralisé. `state["total_breaks"]` reste
compté pour instrumentation (~297/run en moyenne — les breach
"auraient eu lieu" mais sans aucune conséquence).

**Résultat (n=300, seed=9999, deux plafonds)** :

| Plafond | Profit moyen/médian | solde_negatif_annee4 | hit_ceiling_pct | Année1<0 |
|---|---|---|---|---|
| 1000$ | 6 191 173$ / 5 776 018$ | **0,00%** | **0,00%** | 24,67% |
| 3000$ | 6 191 173$ / 5 776 018$ (identique) | **0,00%** | **0,00%** | 24,67% |

**Réponse nette : le rythme "par paquets" ne crée AUCUN problème de
liquidité en lui-même.** Zéro occurrence de `hit_ceiling` ou
`solde_negatif_annee4` sur 300 runs × 2 plafonds (600 runs) — donc
aucune question de "à quel moment du cycle" à répondre, l'échantillon
est vide. Les résultats sont rigoureusement identiques entre 1000$ et
3000$ (cohérent : sans casse, la seule dépense cash restante est le coût
initial jour 0 + les déblocages de groupe, largement couverts même au
plafond le plus serré). **`hit_ceiling`/`solde_negatif_annee4` dans le
moteur normal sont donc entièrement pilotés par la casse elle-même
(coût de réouverture + forfeiture), PAS par le simple rythme de
versement.** L'hypothèse "creux de trésorerie entre deux flush"
est réfutée.

Note complémentaire : année1<0 reste à 24,67% même sans AUCUN coût de
casse ni contrainte de cash — confirme (comme §2.31 le suggérait déjà)
qu'année1<0 est en bonne partie pilotée par la variance de trading pure
(mauvaise séquence en début de run), pas uniquement par des contraintes
de cash.

---

### 2.34 Décomposition Run A (délai seul) / Run B (forfeiture seule) vs Run E (08/11)

Isole la contribution du délai d'accès au cash vs de la forfeiture réelle
dans les ~8pt d'année1<0 attribuables aux contraintes de cash (§2.33,
Run C − Run E). n=300, seed=9999, config officielle cadence-corrigée.

- **Run A** (`etape_ak_run_a_delai_seul_2026-08-11.py`) : délai
  d'accès au cash conservé, mais sur une casse le `pending_payout` est
  intégralement RÉCUPÉRÉ (comme un flush anticipé) au lieu d'être perdu
  — isole le délai pur.
- **Run B** (`etape_al_run_b_forfeiture_seule_2026-08-11.py`) : crédit
  immédiat (aucun délai), mais un compteur théorique suit la fenêtre de
  cycle et un montant équivalent est retiré RÉTROACTIVEMENT au moment
  d'une casse — isole la forfeiture pure.

| Run | Année1<0 (1000$/3000$) | Écart vs Run E (24,67%) |
|---|---|---|
| **A** (délai seul) | 31,33% / 31,33% | **+6,66pt** |
| **B** (forfeiture seule) | 27,67% / 27,67% | **+3,00pt** |
| **C** (combiné, référence) | 32,67% / 32,67% | **+8,00pt** |

**A+B naïf = 9,66pt vs écart réel C−E = 8,00pt → résidu -1,66pt** (signalé
sans arrondir, pas de tentative de le faire disparaître). Le délai
explique la majorité de l'écart (6,66/8,00 ≈ 83%), la forfeiture réelle
3,00/8,00 ≈ 38% — la somme dépasse le total, donc les deux effets se
**chevauchent partiellement** (une casse tombant juste avant un flush
cumule souvent les deux risques sur le même événement). Résultats
**identiques aux deux plafonds** sur les 4 runs — cet axe de
décomposition semble insensible au plafond sous cette config.

### 2.35 Run F — politique de retrait rapide (Blueberry 7j) (08/11)

Suite logique de §2.34 : le délai domine, donc teste un levier
actionnable — accélérer la cadence réelle là où une option plus rapide
existe. `etape_an_run_f_retrait_rapide_2026-08-11.py` : Blueberry passe
de 14j à **7j** (option confirmée par l'utilisateur, flat, pas de
distinction 1er retrait/suivant). GFT/Fivers inchangés (GFT déjà 3j/
1,5j, Fivers reste 14j faute d'option plus rapide confirmée).
**FTMO/FundedNext : demande "5j pour FundedNext" SANS OBJET** — aucune
des deux n'est dans `PAYOUT_CYCLE_FIRMS`, les deux créditent déjà
INSTANTANÉMENT (0j, plus rapide que 5j) puisque leur profit est déjà
préservé à la casse (confirmé support) — pas de mécanisme de délai à
accélérer pour elles dans ce moteur.

| Config | Année1<0 (1000$/3000$) |
|---|---|
| Run C (référence, Blueberry 14j) | 32,67% / 32,67% |
| **Run F (Blueberry 7j)** | **28,33% / 28,33%** |

**-4,34pt récupérés** par le seul passage Blueberry 14j→7j — soit 54%
de l'écart total C−E (8,00pt), ou ≈65% de l'effet délai isolé en Run A
(6,66pt) si on suppose (approximation, pas une isolation stricte comme
Run A) que l'essentiel du gain de Run F reste sur l'axe délai.

**🔴 CORRECTION 08/11 (même session, suite) : l'option N'EST PAS
gratuite.** Confirmé par l'utilisateur via documentation officielle
Blueberry Funded (help.blueberryfunded.com, "The 7 Day Payout Add-On")
: **+20% sur le prix du challenge**, appliqué "sur la structure
standard" — achat initial ET tout rachat après casse, pas une politique
alternative sans contrepartie. Intégré dans
`etape_ao_run_f_cout_reel_2026-08-11.py` (multiplicateur ×1,20 appliqué
à la source, `price_for_bb()`, sur les 3 points d'achat Blueberry :
`base_palier_cost` jour 0, rachat post-casse, compte extra post-
déblocage — la branche "reset Blueberry" hérite automatiquement du
surcoût via `acc["base_cost"]` déjà majoré).

| Config | Année1<0 (1000$/3000$) | Profit moyen (1000$/3000$) |
|---|---|---|
| Run C (référence, Blueberry 14j) | 32,67% / 32,67% | 5 588 381$ / 5 629 882$ |
| Run F "gratuit" (avant correction) | 28,33% / 28,33% | 5 633 896$ / 5 662 073$ |
| **Run F coût réel (+20%)** | **29,67% / 29,00%** | **5 601 371$ / 5 658 217$** |

**Le levier améliore profit et année1<0 après le vrai coût** — gain
réduit mais pas annulé sur CET axe : **-3,00pt/-3,67pt vs Run C** (au
lieu de -4,34pt/-4,34pt "gratuit"), soit une érosion de 1,34pt (1000$) à
0,67pt (3000$) du bénéfice sur année1<0. Profit moyen reste supérieur à
Run C aux deux plafonds malgré le surcoût. Coût approximatif du surcoût
(delta profit "gratuit" − "réel", proxy pas une mesure directe des $ de
surcoût payés) : ~32 525$/run en moyenne à 1000$ (contrainte de cash
serrée, le surcoût pèse plus), ~3 856$/run à 3000$ (cash plus large,
surcoût quasi anodin).

**🔴 CORRECTION 08/11 (session c) : ce tableau était incomplet — pas un
free lunch, un vrai arbitrage.** La comparaison ci-dessus ne portait que
sur profit et année1<0. En ajoutant `solde_negatif_annee4`/
`hit_ceiling_pct` (déjà calculés par le script mais jamais rapportés
ici), le tableau complet à n=300 (`etape_ao_run_f_cout_reel_n300.csv`)
montre que Run F **dégrade ces deux axes** :

| Config (n=300) | solde_negatif_annee4 (1000$/3000$) | hit_ceiling_pct (1000$/3000$) |
|---|---|---|
| Run C (référence) | 1,33% / 0,33% | 3,33% / 1,67% |
| Run F coût réel | 2,33% / 0,67% | 5,67% / 1,67% |

Confirmé stable à n=600 (cascade check complet, §1.8) : même ordre de
grandeur (+0,83pt/+0,16pt solde_negatif_annee4, +2,33pt/0pt
hit_ceiling_pct) — **pas du bruit d'échantillonnage, un effet réel et
reproductible**. Mécanisme cohérent : le surcoût +20% appliqué à chaque
achat/rachat Blueberry pèse sur la trésorerie précisément quand elle est
la plus tendue (plafond 1000$), même si la forfeiture Blueberry elle-même
chute de ~89% (le mécanisme voulu fonctionne, mais son coût d'entrée crée
un risque de cash ailleurs). **Verdict révisé : Run F n'est PAS une
dominance stricte sur les 3 axes** (contrairement au standard utilisé
partout ailleurs dans ce registre pour un "GO"), c'est un arbitrage
profit/année1<0 meilleurs CONTRE ruine/hit_ceiling pires, particulièrement
marqué au plafond 1000$. **Toujours pas promu en référence officielle**
— décision d'adoption explicite laissée à l'utilisateur, voir §1.8
(cascade check n=600 complet) et décision #16 §4.

**Run G — variante CIBLÉE testée (08/11, suite)** :
`etape_ap_run_g_cible_2026-08-11.py` — au lieu de surcharger dès l'achat
initial, chaque lignée de compte Blueberry (même slot, réouvertures
successives) reste en cadence normale 14j SANS surcoût jusqu'à sa
1ère casse, puis bascule DÉFINITIVEMENT en 7j+surcoût (le rachat qui
suit cette 1ère casse est déjà surchargé). Logique testée : économiser
le surcoût sur les comptes qui ne re-cassent jamais.

| Config | Année1<0 (1000$/3000$) | Profit moyen (1000$/3000$) |
|---|---|---|
| Run C (référence) | 32,67% / 32,67% | 5 588 381$ / 5 629 882$ |
| Run F coût réel (surcoût dès j0) | 29,67% / 29,00% | 5 601 371$ / 5 658 217$ |
| **Run G ciblé (surcoût après 1ère casse)** | **30,67% / 30,00%** | **5 593 190$ / 5 649 830$** |

**Contre-intuitif mais net : Run G est STRICTEMENT PIRE que Run F sur
les deux axes** (année1<0 -2,00pt/-2,67pt vs Run C, moins bon que
Run F's -3,00pt/-3,67pt ; profit aussi légèrement inférieur à Run F aux
deux plafonds). Explication cohérente avec §2.34 (le délai domine
largement la forfeiture) : la 1ère casse d'une lignée Blueberry est
justement le moment le plus critique pour le mécanisme de cash
(§2.36/§2.37 — c'est répétitivement le starter Blueberry qui reste
bloqué en boucle) ; retarder l'accès rapide au cash jusqu'APRÈS cette
1ère casse revient à protéger le compte seulement une fois le pire déjà
en cours, tout en payant quasiment le même surcoût cumulé à long terme
(une fois `_has_broken_before=True`, le compte reste en mode rapide+cher
pour toujours, comme Run F). **Verdict : REJETÉ** — l'application
inconditionnelle (Run F) domine strictement la version ciblée.

### 2.36 Extraction et analyse des journaux de runs négatifs — référence officielle n=600 (08/11)

Journal chronologique complet extrait pour CHAQUE run finissant en
`solde_negatif_annee4=True` sous le moteur cadence-corrigé (721 trades,
config combo complète, payout actif), n=600 aux deux plafonds, seed=9999
(`etape_am_deep_dive_negative_runs_2026-08-11.py`, copie locale de
`process_trade_mf` exposant le type de breach jamais autrement exposé —
module partagé NON modifié). **10 runs négatifs au total** (9/600 à
1000$, 1/600 à 3000$) — journaux bruts dans `deep_dive_logs/*.json`,
analyse dans `deep_dive_analysis_2026-08-11.py`.

⚠️ **Bug d'instrumentation trouvé en passant** (hors périmètre demandé,
signalé) : `state["total_breaks"]` est compté DEUX FOIS par casse réelle
dans TOUT le projet (une fois dans `process_trade_mf` inconditionnellement,
une fois au niveau driver) — n'affecte AUCUN chiffre économique
(`cost_override=0.0` neutralise le doublon côté cash) mais gonfle ~2× tout
comptage "nombre de casses" dérivé de ce compteur (y compris §2.24). Ce
script compte les casses réelles via les événements du journal, pas via
`total_breaks`.

**Point 1 — distribution des casses par firm** : Blueberry est la
**1ère casse dans 10/10 runs négatifs** (100%) et représente 113/260
casses totales (43%) sur des rangs allant de 1 à 96 (casse en continu,
pas seulement au début) — cohérent avec son rôle de starter unique actif
dès le jour 0. FTMO/Fivers/GFT/FundedNext n'apparaissent JAMAIS en
1ère casse (rangs 2+, 20+, 6+, 8+ respectivement) — pas parce qu'elles
cassent "plus tard" intrinsèquement, mais parce que leurs comptes ne
sont tout simplement pas encore actifs avant le déblocage de groupe.

**Point 2 — position dans le cycle de payout au moment des casses** :
⚠️ artefact de mesure trouvé — le flush (s'il se déclenche) s'exécute
AVANT la détection de casse dans la même itération, donc un flush qui
tombe pile sur le même pas que la casse fait mécaniquement remonter
`jours_depuis_dernier_flush≈0` (pas une preuve que les casses arrivent
"juste après un vrai flush"). En excluant ces zéros mécaniques, les
valeurs non nulles (Blueberry : 0,04 à 13,52j sur cadence 14j ; GFT :
0,04 à 1,25j sur cadence ≤3j) sont **réparties sur toute l'étendue du
cycle**, pas concentrées près de la borne haute — pas de signature
"juste avant le prochain flush", plutôt cohérent avec de la variance pure.
Fivers (n=26) fait exception : valeurs très regroupées (2,71j×10,
5,54j×8, 12,12j×8) — mais ces 26 événements viennent de seulement 2 runs
(quasi-identiques, même seed) où plusieurs comptes Fivers cassent en
vagues synchronisées (marché corrélé entre comptes soeurs).

**Point 3 — écarts entre casses consécutives** : très hétérogène selon
le run. 8/10 runs (6-14 casses, 1-2 firms touchées) montrent des casses
ISOLÉES espacées de dizaines de jours (ex. run227 : 73,8/34,4/77,1/
90,9/23,6j). Les 2 runs catastrophiques (92-96 casses, 5 firms) montrent
des RAFALES (nombreux écarts à 0,0j, plusieurs comptes cassant au même
pas) entrecoupées de longues accalmies (70-107j) — pas un seul régime,
deux profils de casse bien distincts selon la gravité du run.

**Point 4 — forfeiture réelle vs simple délai** : sur 182 casses
touchant des firms à cycle de payout (Blueberry/GFT/Fivers), **seules 3
(1,6%) ont réellement perdu du pending_payout** — total forfeité sur
les 10 runs négatifs : **2 360,75$**, entièrement sur Blueberry (Fivers/
GFT : 0$). **Triangule directement avec §2.34** : la forfeiture directe
est rare et de faible montant même dans les runs qui finissent négatifs
— c'est le coût INDIRECT du délai (cash immobilisé qui aurait pu éviter
un hit_ceiling, donc éviter le coût COMPLET d'une casse/réouverture, pas
juste le pending_payout) qui domine, pas la perte d'argent elle-même.

**Point 5 — casses par run négatif, firms distinctes** : distribution
très bimodale, PAS une moyenne représentative :
- **8/10 runs** : 6 à 14 casses, 1-2 firms distinctes (quasi toujours
  Blueberry seule, parfois +FTMO) — le starter Blueberry n'arrête pas de
  redémarrer, la flotte ne se débloque JAMAIS.
- **2/10 runs** (la paire run202@1000$/@3000$, même tirage) : 92-96
  casses, 5 firms distinctes — flotte pleinement débloquée qui
  s'effondre ensuite largement.
Un run négatif est donc typiquement une **flotte qui ne démarre
jamais**, pas une accumulation progressive de petites casses sur une
flotte mature — sauf dans 2/10 cas.

**Point 6 — bascule pré/post-déblocage (1er hit_ceiling)** : **8/10
pré-déblocage, 2/10 post-déblocage, 0/10 sans hit_ceiling** — cohérent
avec le point 5 (les 2 runs post-déblocage sont exactement les 2 runs
"5 firms". Confirme empiriquement, sur données réelles (pas de la
statistique agrégée), que le mécanisme dominant des runs négatifs sous
cette référence est l'échec du starter Blueberry à financer la flotte,
pas un effondrement tardif d'une flotte déjà mature.

### 2.37 🔴 Mécanisme du mode "effondrement flotte mature" identifié — pas une corrélation inter-paires, une VRAIE période historique creuse copytradée (08/11)

Suite à §2.36, creuse spécifiquement les 2 runs "5 firms" (run202@1000$/
@3000$). Rejeu exact reproduit (`deep_dive_replay_run202_2026-08-11.py`,
même seed, mêmes tirages RNG avancés séquentiellement jusqu'à
l'itération 202 — net_final reproduit à l'identique -72 010,33$).

**Point 1 — clustering temporel** : les 92-96 casses sont concentrées
sur les **jours 34,7 à 435,8 de simulation** (~13 mois sur les 4 ans du
run, RIEN après) — pas étalées sur toute la durée. **92,4% des casses
tombent le même jour entier qu'au moins une autre casse.**

**Point 2 — co-occurrence multi-firms** : 14 clusters de 3 à 11 casses
en fenêtre ≤3j, touchant simultanément 2 à 4 firms distinctes à chaque
fois (ex. jour 294 : 6 casses FTMO+GFT+Blueberry ; jour 339 : 7 casses
Blueberry+Fivers+GFT+FundedNext). **Signal de corrélation direct et
sans ambiguïté.**

**Point 3 — régime de marché identifié, MAIS pas via une corrélation
inter-paires** : en traçant `trade["date"]` (survit au block bootstrap,
confirmé via `robustesse_5ers_risk_challenge.build_flexible_population`)
derrière chaque casse groupée, le cluster dense (jours 284-399) retombe
presque entièrement sur la fenêtre historique RÉELLE **2022-11-01 →
2023-01-20** — et le bootstrap de blocs de 2 mois a tiré CE MÊME bloc
historique DEUX FOIS dans ce run (dates identiques répétées à 60j
d'écart en simulation, ex. 2022-12-02/2022-12-08/2022-12-12 chacune
vue 2×). Vérifié directement sur les 721 trades : cette fenêtre réelle
(40 trades) a un **winrate de 17,5% et une EV de -0,466R, contre 40,4%/
+0,890R sur l'échantillon global** — une vraie période creuse de
l'edge, pas un artefact de simulation.

**Conclusion — INFIRME l'hypothèse piste G/décorrélation asymétrique
telle que formulée** : le mécanisme n'est PAS une corrélation entre
paires spécifiques (déjà testé et rejeté séparément, Piste H, §2.12
ancien registre — routage AUD/JPY-USD/CHF, effet nul). C'est plus
simple et plus structurel : **toutes les firms copytradent le MÊME
signal** — quand ce signal traverse une vraie mauvaise période
historique (17,5% winrate sur 2,5 mois réels), TOUTES les firms cassent
ensemble par construction, indépendamment de quelles paires sont
tradées. Aucune règle de routage/exclusion de paires ne peut réduire ce
risque puisqu'il ne vient pas d'une corrélation croisée entre
instruments — il vient de la qualité intrinsèque du signal sur cette
fenêtre réelle, répliquée à l'identique sur tous les comptes. **Piste
G/décorrélation asymétrique : pas de nouveau signal source exploitable
trouvé ici, thèse à considérer close sous cette formulation** (une
piste différente — réduire la taille des blocs de bootstrap pour
limiter la probabilité de tirer une même fenêtre creuse plusieurs fois,
ou accepter ce risque comme une variance réelle et irréductible de
l'edge sur un historique de 721 trades — resterait à évaluer
séparément si jugé utile).

Fichiers : `deep_dive_run202_dates_ceiling1000.json` (mapping casse →
date historique réelle).

---

## 3. Contraintes dures confirmées (non négociables)

- **DD max = propriété du FORMAT, pas de la firm** : tout format avec
  évaluation (1/2/3-step) = DD statique ; tout instant funding = DD
  trailing. Vérifié sur les 5 firms, y compris le cas GFT 2-step vs
  3-step (les deux statiques). Exception partielle : FTMO 1-Step est
  "trailing fin de journée" (recalculé 1×/jour à minuit, pas intraday).
- **Copytrade — formats du combo WINNER confirmés** (mais WINNER
  lui-même rejeté sur l'économie) : FTMO 1-Step (400k$ cap), The5%ers
  Hyper Growth (500k$ cap), Blueberry Instant Elite, GFT Instant GOAT
  (financé uniquement), FundedNext Stellar 1-Step (300k$ cap).
- **Copytrade — règles générales par firm** : GFT interdit
  challenge→challenge et challenge→financé (autorisé financé→financé) ;
  The5%ers interdit Bootcamp↔Bootcamp spécifiquement ; FundedNext
  interdit entre traders différents et entre comptes financés sauf
  FundedNext↔FundedNext (300k$), et Stellar Instant est incompatible
  avec Stellar 1/2-Step/Lite même pour la même personne.
- **Blueberry — contraintes instant funding** : plancher DD ne se
  réinitialise JAMAIS après un retrait une fois verrouillé (piège
  d'érosion de capital réel, non modélisé) ; durée min de trading
  resserrée à 5 jours actifs depuis le 17/02/2026 (était 3j) ; add-on
  payant "3-Day Fast Track" disponible.
- **GFT Instant GOAT** : fermeture définitive si P&L flottant < -2% du
  solde à tout instant — règle plus stricte que le DD max lui-même
  (c'est le vrai déclencheur de Goat Guard, non modélisable finement
  dans ce moteur, voir §1.5).
- **The5%ers Hyper Growth** : DD journalier 3% = PAUSE (pas fermeture),
  différent d'une vraie casse.
- **FundedNext** : depuis le 18/03/2025, seuls les 4 modèles Stellar
  (2-Step/1-Step/Lite/Instant) sont vendus aux nouveaux clients — les
  produits Express/Evaluation cités dans une source tierce sont obsolètes.
- **GFT 2-Step PRO** : arrêté à la vente depuis le 13/06/2026.
- **Blueberry — ambiguïté produit non résolue** : "Prime Challenge"
  (P1 8%/P2 6%, DD 4%/10%) vs "2-Step Challenge" standard (P1 10%/P2 5%,
  DD 5%/10%) — impact mesuré <1%, non bloquant mais jamais tranché.
- **Reset Blueberry — exclusions** : usage unique à vie par compte,
  exclu pour instant funding et comptes "scaled" (sans objet dans ce
  moteur, aucune croissance individuelle n'existe).

---

## 4. Décisions ouvertes (rappel, détaillées dans `etape_e_synthese_globale_2026-08-09.md` §8)

1. Seuil FundedNext : 25k (prudent) ou 5k (+2% profit, ruine ~2×) ?
2. 🔴 **Point de risque : éval=1,00% ou 1,25% ? — BLOQUANT, testé 08/10,
   ce n'est plus juste un dial profit/sécurité.** Sous 1,25%, V2 et le
   combo V2+FTMO-10%/GoatGuard sont confirmés gagnants (§1.8). Sous
   1,00%, **V2 ne domine plus à 1000$ et devient pire sur les 3 axes à
   3000$** (`etape_p_eval_risk_test_2026-08-10.py`) — choisir 1,00%
   revient à renoncer à tous les leviers structurels du chantier au
   plafond 1000$. Vrai choix de risque personnel, pas un verdict
   technique — décision utilisateur nécessaire avant d'aller plus loin.
   **Statut exact (à retenir avant tout clear de contexte)** :
   éval=1,25% est utilisé dans TOUS les chiffres de référence de ce
   registre (§1.8 inclus) comme **hypothèse de travail NON VERROUILLÉE**
   — pas un choix tranché par l'utilisateur, juste la valeur sous
   laquelle les leviers structurels ont été confirmés gagnants. Rien
   n'a été testé sous 1,00% depuis la correction du cap Blueberry ni
   depuis le cycle de payout (§2.17, §2.26) — ces deux corrections
   majeures héritent probablement du même problème sous 1,00% mais ce
   n'est PAS vérifié.
3. Basculer la référence Étape E comme référence officielle du projet,
   ou garder l'ancien chiffre verrouillé (5 794 566$/5 898 897$) ?
   *(Partiellement tranché 08/10 : ancien chiffre marqué SUPERSEDED,
   REF+V2+FTMO-10/GoatGuard adopté comme référence courante à 1000$ —
   voir §1.8 — mais reste sous réserve de la décision #2 ci-dessus.)*
4. Chercher un levier ciblant spécifiquement la composante
   POST-déblocage d'année1<0 (43% des cas, jamais adressée) ?
   *(Partiellement traité : FTMO-10%/GFT Goat Guard ciblent déjà ça,
   adoptés 08/10 combinés à V2 — §1.8.)*
5. ✅ *(RÉSOLU 08/10)* FTMO -10%/GFT Goat Guard rejoignent la config de
   référence — adoptés, combinés à V2, GO n=600+cascade. Voir §1.8.
6. ✅ *(RÉSOLU ET ADOPTÉ 08/10 nuit, suite 3→7)* Cap Blueberry réel :
   **400 000$ total par trader/foyer, aucune limite fixe de nombre de
   comptes** (contact direct support), + limite distincte de 4 comptes
   max par device/IP. **Corrigé dans le code, décomposé, retesté, et
   ADOPTÉ comme référence officielle** — voir §1.3, §2.16-2.18, §1.8, et
   décision #11 ci-dessous (même item, plus de détail). Marge de sécurité
   Fivers (500k$ codé sans marge) toujours pas traitée — seul reliquat
   de cette décision.
7. Bootstrap parallèle jour 0 (BB+GFT) confirmé n=600+cascade GO — mais
   UNIQUEMENT au plafond 3000$ (rejeté sans ambiguïté à 1000$). Adopter
   conditionnellement au plafond choisi par l'utilisateur ? Voir §2.6.
   *(Mécanisme de ruine à 1000$ maintenant identifié avec certitude
   08/10 — épuisement de marge de trésorerie, voir §2.11.)* **Mis à jour
   08/10 nuit suite 3, reconfirmé suite 7** : piste A' (BBx2, §2.15) EST
   un candidat concurrent confirmé au même plafond 3000$ (sous cap
   Blueberry corrigé désormais, écart RENFORCÉ à +4,31% vs REF pure,
   voir §1.8) — profit moindre que BB_GFT_day0 mais ruine et coût
   d'entrée meilleurs. **Choix entre BB_GFT_day0 / BBx2 / REF pure à
   3000$ non tranché** — dépend directement de la décision #9
   (utilisateur choisit-il vraiment 3000$ comme plafond réel ?), pas
   mutuellement exclusif techniquement mais un seul sera adopté en
   pratique.
8. Sizing DD pré-déblocage (piste F, V2) confirmé n=600+cascade GO — mais
   UNIQUEMENT au plafond 1000$ (pas de gain à 3000$), ET seulement sous
   éval=1,25% (voir décision #2). Même arbitrage que la décision 7,
   ceilings inversés.
9. Faut-il demander explicitement à l'utilisateur son plafond personnel
   réel (1000$ ou 3000$) avant d'aller plus loin ? **Toujours sans
   réponse malgré plusieurs relances.** Les leviers structurels du
   chantier en dépendent directement. **Statut exact (à retenir avant
   tout clear de contexte)** : mise en pause VOLONTAIRE de cette
   décision par choix méthodologique du chantier — au lieu d'attendre la
   réponse pour avancer, chaque test de cette session a systématiquement
   couvert LES DEUX plafonds (1000$ ET 3000$) en parallèle, précisément
   pour ne pas bloquer le travail dessus. Ce n'est donc pas un point mort
   par manque de réponse gênant l'avancement — c'est une décision de
   fond qui reste à trancher uniquement pour SAVOIR LAQUELLE des deux
   colonnes de résultats déjà produites est "la" référence unique du
   projet, pas pour savoir quoi tester ensuite.
10. ✅ *(RÉSOLU/CONFIRMÉ 08/10 nuit, suite 3, reconfirmé suite 7)* Piste
    A' (2× Blueberry parallèle) — scopée (§2.13) PUIS implémentée et
    testée (§2.15), reconfirmée sous cap Blueberry corrigé (§2.18).
    CONFIRMÉ n=600+cascade GO à ceiling=3000$ (domine strictement
    solo_BB, écart RENFORCÉ +4,31%), REJETÉ à 1000$ (dominé par solo_BB).
    Voir décision #7 pour l'arbitrage BBx2 vs BB_GFT_day0 à 3000$.
    Démarrage différé du 2e starter BB+GFT — TESTÉ ET REJETÉ (§2.14),
    aucune fenêtre utile trouvée. Décorrélation asymétrique toujours pas
    scopée, informée par le vrai mécanisme de ruine (§2.11).
11. ✅ *(RÉSOLU ET ADOPTÉ 08/10 nuit, suite 7 — feu vert utilisateur
    reçu)* Cap NOMBRE Blueberry — corrigé dans le code (§2.17,
    `FIRM_MAX_ACCOUNTS["Blueberry"]`=3→None, `FIRM_CAPITAL_CAP
    ["Blueberry"]`=450k→400k), mécanisme décomposé (§2.18 : gain de
    VOLUME pur, comptes extra Blueberry 2→7, PAS de détournement d'autres
    firms — FTMO/GFT extras identiques avant/après, effet de bord
    négligeable <0,15%/firm), piste A' et piste B retestées sous le cap
    corrigé (résultats décision #10 et §2.8). **ADOPTÉ COMME RÉFÉRENCE
    OFFICIELLE** : 5 736 759$/1,00%/21,83% à 1000$ remplace
    4 927 916$/0,83%/21,00% dans §1.8 (+16,41% — provenance = correction
    de paramètre, pas nouveau levier). **Reste conditionnel à la
    décision #2 (éval=1,00% vs 1,25%)**, jamais retesté sous 1,00%.

**Bilan 08/10 nuit suite 7 : sur les 11 décisions listées ci-dessus,
seules #2 (éval=1,00%/1,25%) et #9 (plafond personnel 1000$/3000$)
restent réellement bloquantes** — toutes les autres sont résolues,
adoptées, ou dépendent explicitement de l'une de ces deux (décisions #3,
#7, #8 en particulier). Le chantier ne peut pas figer UNE référence
unique du projet sans ces deux réponses, malgré plusieurs relances.

12. 🟡 *(partiellement traité 08/10 nuit, suite 13)* Seuil copytrade
    Fivers 500k$ dépassé dans 99,17%/99,67% des runs REF+V2 (§2.20), pic
    moyen 4,3× le seuil, pic pire cas 12×. Le cycle de payout implémenté
    en §2.26 (14j, Blueberry/GFT/Fivers) répond PARTIELLEMENT à l'option
    (a) ci-dessous (des retraits périodiques sont maintenant modélisés
    pour ces 3 firms) — mais son objectif était de corriger le forfait
    de profit à la casse, PAS spécifiquement de plafonner le solde Fivers
    sous 500k$ (pas revérifié si le seuil 500k est maintenant respecté
    sous le nouveau cycle — probablement pas totalement, puisque le solde
    peut encore grimper PENDANT les 14 jours entre deux versements). Reste
    ouvert : revérifier le taux de dépassement 500k$ sous le nouveau
    cycle de payout si pertinent.
13. ✅ *(RÉSOLU/ADOPTÉ 08/11, cadence par firm confirmée n=600 08/11
    session c)* Cycle de payout réaliste (Blueberry/GFT/Fivers, §2.26) —
    **activé dans la référence officielle** (§1.8, `payout_cycle=True`).
    L'utilisateur confirme retirer manuellement dès déblocage du cycle
    14j, validant le modèle automatique comme proxy réaliste de sa
    politique (répond au point "automaticité" resté ouvert en §2.28).
    Le bug de calibration de cadence trouvé en §2.32 (constante unique
    au lieu d'une cadence par firm) est maintenant CONFIRMÉ n=600
    (35,50%/35,33% année1<0, `etape_ai_payout_cadence_calibration_n600
    .csv`) et constitue la référence officielle en tête de §1.8. Chiffres
    isolés (646-trades, sans le fix population) conservés en §1.8/
    historique pour la décomposition du cascade check.
14. ✅ *(RÉSOLU/ADOPTÉ 08/11)* Fichier historique flotte périmé —
    `historique_lutessia_15k_force.csv` (721 trades) est maintenant
    `HIST_PATH` par défaut ET actif dans la référence officielle
    (§1.8) — désync refermée, le n=600 du 08/11 utilise bien 721 trades
    (vérifié dans les logs : "Population étendue... 721 trades").
15. ✅ *(RÉSOLU 08/11, appliqué au REPORTING uniquement)* Renommage des
    métriques ruine/hit_ceiling — investigation §2.31. `solde_negatif_
    annee4` (ex-"ruine") et `hit_ceiling_pct` sont maintenant rapportées
    côte à côte dans la nouvelle référence officielle (§1.8), avec la
    précision explicite que ni l'une ni l'autre n'est un état
    irréversible. Portée du renommage limitée à `etape_ah_reference_
    officielle_2026-08-11.py` (`summarize()`) — le moteur de calcul
    interne et les ~100 scripts `etape_*.py`/`point*.py` historiques
    déjà figés gardent le nom `ruine`/`state["hit_ceiling"]` sans
    modification (convention "rapport figé" + hors périmètre demandé).
    Un concept "irréversible" au sens strict reste à construire si
    besoin (`struct_never_complete_pct`, §2.11) — pas fait, pas demandé.
16. 🟡 *(n=600+cascade check FAIT 08/11 session c — PAS ✅ ADOPTÉ, verdict
    mixte)* Décomposition délai/forfeiture (§2.34) + retrait rapide
    Blueberry 7j (§2.35) — Run A/B confirment le délai comme moteur
    dominant (+6,66pt vs +3,00pt sur 8,00pt). Run F (Blueberry 7j, coût
    réel +20%) testé n=600, cascade check 4 axes complet (§1.8) :
    **améliore profit (+0,25%/+0,86%) et année1<0 (-1,67pt/-2,50pt) aux
    deux plafonds, MAIS dégrade solde_negatif_annee4 (+0,83pt/+0,16pt) et
    hit_ceiling_pct (+2,33pt/0pt, quasi ×1,7 à 1000$)** — effet stable et
    reproductible entre n=300 et n=600 (pas du bruit), mécanisme identifié
    (surcoût +20% pèse sur le cash tendu au plafond 1000$, alors que la
    forfeiture Blueberry elle-même chute de ~89%, l'effet recherché
    fonctionne). **PAS une dominance stricte sur les 3 axes** (le
    standard utilisé partout ailleurs dans ce registre pour un "GO") —
    **PAS marqué ✅ ADOPTÉ**, reste un candidat documenté nécessitant une
    décision utilisateur explicite sur la préférence de risque
    (profit/année1<0 meilleurs contre ruine/hit_ceiling pires,
    particulièrement au plafond 1000$). La référence officielle du
    projet reste Run C (cadence corrigée, SANS Blueberry 7j, §1.8, décision
    #13 ci-dessus) tant que cette décision n'est pas tranchée.

---

## 5. Gaps identifiés (marqués "à confirmer", pas devinés)

- ~~**Cap $ Blueberry exact**~~ — **RÉSOLU 08/10 nuit suite 3-7** par
  contact direct support (400 000$ agrégé, aucune limite de nombre),
  corrigé dans le code et adopté comme référence officielle. Voir
  §1.3/§2.16-2.18/§4#6/§4#11.
- **Downgrade-on-reopen** : confirmé no-op par construction (pas de
  croissance individuelle dans le moteur), mais aucun fichier ne
  documente explicitement CE calcul avant cette session — résolu ici en
  croisant les notes de conception du code directement.
- **FTMO -10% / GFT Goat Guard** : adopté, fait partie de la référence
  officielle actuelle (§1.8). Plus un point ouvert.
- **Cap $ FTMO/GFT — vérifiés propres 08/10 nuit suite 8** : lecture de
  code (`FIRM_CAPITAL_CAP`/`FIRM_MAX_ACCOUNTS`, `etape_e_fleet_
  integration.py:118-119`) confirme un match EXACT avec les valeurs
  déjà confirmées par ailleurs (FTMO=400k$/GFT=400k$, aucune limite de
  nombre pour les deux) — contrairement à Blueberry, aucun écart trouvé,
  rien à corriger.
- ~~**Marge de sécurité Fivers 500k$ / absence de mécanisme de
  croissance**~~ — **TESTÉ ET FERMÉ 08/10 nuit suite 9** (§2.19) : Fivers
  ajouté à `GROWTH_FIRMS_EXTRA` avec les valeurs déjà codées
  (500 000$/5 comptes), n=300 2 plafonds — **effet rigoureusement NUL**,
  bloqué par l'arithmétique des paliers AVANT même de solliciter la
  réserve (capital initial 400k$ + unité extra 200k$ > cap 500k$). Piste
  fermée dans sa forme actuelle (convention "extra=2×palier de base"),
  pas un bug de valeur comme Blueberry. Voir §2.19 pour la condition de
  réouverture (format Fivers différent, palier plus petit).
- 🔴 **Cap $ FundedNext — JAMAIS confirmé, ni web ni support** (nouveau
  08/10 nuit suite 8) : aucune entrée dans `FIRM_CAPITAL_CAP`/
  `FIRM_MAX_ACCOUNTS` (FundedNext absent de `GROWTH_FIRMS_EXTRA`, un
  seul compte fixe 200k$ via `FUNDEDNEXT_PALIER`, verrouillé par design
  — le "300 000$ entre comptes" du §1.3 est non-contraignant, un seul
  compte utilisé). **Seule vraie question de vérification support
  restante sur le sujet des caps de capital** — contact utilisateur
  nécessaire si la question devient pertinente (ex. si un mécanisme de
  croissance FundedNext est un jour envisagé).
