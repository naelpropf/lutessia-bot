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

**🔴🆕 PROPOSITION 08/16 — CASCADE GROUPÉE (bascule Blueberry Instant +
any-RR), PRÊTE POUR ADOPTION, décision utilisateur finale en attente.**
Intègre simultanément deux mécanismes validés isolément cette session :
bascule Blueberry Instant (seuil dépendant du plafond, §7.1) et échange
ciblé blocage-corrélation par critère RR planifié (any-RR,
`registre_strategie_trading.md` §2.33). Régénérée dans le MÊME script/
seed que la référence 08/12 ci-dessous (base RR≥1,35/corr0,80 inchangée),
donc directement comparable ligne à ligne. Fichiers :
`chantier_cascade_combined_bb_switch_any_rr_2026-08-16.py`,
`chantier_cascade_combined_decomposition_2026-08-16.py` (tous suivis par
git), n=600+cascade, seed=9999.

**🔴 Correction méthodologique découverte en cours de chantier** : le
moteur hérité de `chantier_position_cap_2026-08-15.py` (et donc utilisé
par tous les chantiers §2.28/§2.32/§2.33 de `registre_strategie_
trading.md`) appliquait une cadence Blueberry fixe à 14 jours à TOUS les
plafonds, omettant le mécanisme Run F (Blueberry 7j + surcharge 20%,
`BB_PAYOUT_7J_CEILINGS={3000.0}`) qui fait pourtant partie de la
référence officielle adoptée le 08/12 à 3000$ (décision #16). Corrigé
dans le moteur de cette cascade groupée (`price_for_bb`/`bb_payout_days`,
appliqué uniquement au format Blueberry CLASSIQUE, jamais à Instant Elite
qui n'a aucune source documentant un équivalent) — **vérifié : le
REF@3000$ corrigé (5 900 859$) correspond EXACTEMENT à la référence
officielle 08/12 ci-dessous**, confirmant le correctif. **Conséquence
pour les chantiers §2.28/§2.32/§2.33** : leurs chiffres absolus en $ à
3000$/5000$ étaient sous-estimés d'environ 0,9% (le manque à gagner du
7j non modélisé) — mais comme chaque chantier comparait sa référence et
ses variantes DANS LE MÊME baseline simplifié (comparaison A/B interne
cohérente), leurs verdicts relatifs (rejet du plafond de position,
confirmation any-RR, etc.) restent valides. Seuls les $ absolus cités à
3000$/5000$ dans ces sections portent désormais cette réserve.

**🔴 2e correction méthodologique découverte le 08/17-18, appliquée ici** :
Blueberry Instant Elite/Lite ne bénéficient PAS de l'exemption Prime sur le
risque par trade — ils sont soumis à un cap réel de 1,5%/trade calculé sur
la taille INITIALE du compte (fixe), pas au risque flotte standard
(1,90%). Vérifié par citation de code (`engine_multiformat.py:46-55`,
aucun champ risque-par-trade dans `format_def()` ; `chantier_cascade_
combined_bb_switch_any_rr_2026-08-16.py:445-453`, le risque appliqué à un
compte Blueberry Instant funded est bien le FLEET_RISK global, identique à
Prime) — le moteur autorisait donc PLUS de risque par trade sur Instant
que la vraie contrainte ne le permet. Correctif intégré en dur (clamp
`r=min(r,1,5%)`, après tout multiplicateur y compris DD-distance V2) dans
`chantier_S1_8_officiel_n600_risque_corrige_2026-08-17.py`, copie figée de
`chantier_cascade_combined_bb_switch_any_rr_2026-08-16.py`. Stress-test
H1/H2+4 blocs k-fold effectué avant n=600 (`chantier_S1_8_stresstest_
risque_instant_2026-08-17.py`, n=100, 2 régimes de plafond) : 10/12
sous-périodes confirment la dominance ; les 2 exceptions (toutes deux
"bloc1", aux deux régimes) sont un artefact de bruit sur une base REF
quasi nulle (347$/965$ contre des millions ailleurs, delta absolu de
-606$/-5522$ seulement) — pas une inversion économique réelle. Détails
complets et chiffres avant/après par plafond :
`registre_strategie_trading.md` §2.45.

**Tableau de référence (n=600+cascade, risque Instant corrigé), 4
plafonds — remplace définitivement les $ précédemment affichés ici :**

| Plafond | Config | Profit moyen/médian | solde_negatif_annee4 | hit_ceiling_pct | Année1<0 |
|---|---|---|---|---|---|
| 960$ | REF (rr135/corr080 seul) | 5 835 876$ / 5 621 512$ | 0,50% | 2,33% | 30,50% |
| **960$** | **COMBINÉ (bb_seuil=5000$ + any-RR, risque Instant corrigé)** | **6 417 256$ / 6 169 700$** | **0,17%** | **0,67%** | **24,00%** |
| 1000$ | REF (= Run C actuel) | 5 836 643$ / 5 621 512$ | 0,50% | 1,50% | 30,50% |
| **1000$** | **COMBINÉ (bb_seuil=5000$ + any-RR, risque Instant corrigé)** | **6 417 256$ / 6 169 700$** | **0,17%** | **0,50%** | **24,00%** |
| 3000$ | REF (= Run F actuel) | 5 900 859$ / 5 630 556$ | 0,33% | 0,33% | 28,83% |
| **3000$** | **COMBINÉ (bb_seuil=0$ + any-RR, risque Instant corrigé)** | **6 693 474$ / 6 461 759$** | **0,00%** | **0,00%** | **15,67%** |
| 5000$ | REF | 5 848 265$ / 5 621 512$ | 0,33% | 0,67% | 30,50% |
| **5000$** | **COMBINÉ (bb_seuil=0$ + any-RR, risque Instant corrigé)** | **6 693 474$ / 6 461 759$** | **0,00%** | **0,00%** | **15,67%** |

**Dominance stricte sur les 4 axes, aux 4 plafonds — CONFIRMÉE n=600 après
correction** : profit +9,95% à +9,96% (960$/1000$) et +13,44% à +14,45%
(3000$/5000$) ; solde_neg/hit_ceiling tous meilleurs ou égaux partout ;
année1<0 meilleur à 960$/1000$ (24,00% vs 30,50%), meilleur mais un peu
moins qu'avant correction à 3000$/5000$ (15,67% vs 28,83% REF, contre
13,83% avant correction — la correction dégrade légèrement cet axe sans
remettre en cause la dominance globale). **~33-37% du gain de profit
annoncé par l'ancien tableau (non corrigé) s'évapore** avec le vrai
risque 1,5% — le gain réel retenu est ~63-69% du gain brut original selon
le plafond, cohérent entre n=300 (screening) et n=600 (confirmation).

**Hypothèse assumée sur le seuil de bascule Blueberry à 1000$/3000$** :
seul 960$ (→seuil 5000$) et 5000$ (→seuil 0$) ont un seuil isolément
mesuré (§7.1). 1000$ a été regroupé avec le régime "tendu" 960$
(seuil 5000$) et 3000$ avec le régime "large" 5000$ (seuil 0$) par
proximité, PAS par mesure directe à ces plafonds précis — signalé
explicitement, pas un résultat validé au même niveau que 960$/5000$.

**Décomposition (même script/seed, isole l'effet net de l'intégration
groupée vs la somme naïve des effets isolés) :**

| Plafond | bb_seul | Δ vs REF | any-RR seul | Δ vs REF | Somme naïve | **COMBINÉ réel** | **Écart** |
|---|---|---|---|---|---|---|---|
| 960$ | 6 135 249$ | +5,13% | 6 399 549$ | +9,66% | +14,79% | **+15,71%** | **+0,92pt** |
| 1000$ | 6 136 110$ | +5,13% | 6 399 549$ | +9,65% | +14,78% | **+15,69%** | **+0,91pt** |
| 3000$ | 6 475 162$ | +9,73% | 6 480 623$ | +9,83% | +19,56% | **+19,99%** | **+0,43pt** |
| 5000$ | 6 475 162$ | +10,72% | 6 410 274$ | +9,61% | +20,33% | **+21,08%** | **+0,75pt** |

**🔴 Verdict décomposition : RENFORCEMENT LÉGER ET SYSTÉMATIQUE, PAS DE
CANNIBALISATION.** Aux 4 plafonds, l'effet combiné mesuré dépasse
légèrement la somme naïve des deux effets isolés (+0,4 à +0,9pt) —
cohérent avec le mécanisme anticipé par le prompt (any-RR change quels
trades entrent en flotte, accélère l'accumulation de réserve, ce qui
avance légèrement le franchissement du seuil de bascule Blueberry). Pas
d'investigation supplémentaire nécessaire (le gain combiné n'est jamais
inférieur à la somme isolée, condition de vigilance du prompt non
déclenchée) — **cohérent aux 4 plafonds, prêt pour adoption.**

**Statut** : any-RR (`registre_strategie_trading.md` §2.33) et la
bascule Blueberry Instant (§7.1 ci-dessous) sont **RÉSOLU/INTÉGRÉS** au
niveau chantier (mécanismes validés, cascade groupée cohérente
démontrée) — reste une décision utilisateur explicite pour figer ce
tableau comme LA nouvelle référence officielle (remplaçant le tableau
08/12 ci-dessous) et régénérer les leviers dérivés qui en dépendent
(comme fait le 08/12 pour RR1,35/corr0,80, §2.63).

**✅ ADOPTÉ (décision utilisateur, 2026-08-23)** — §1.8 (cascade BB
Instant + any-RR) devient officiellement la référence, après re-test sur
données r_trailing corrigées (fix commit `df261dc`, backfill MT5/
Dukascopy/TradingView complet bloc1/bloc2). Ce re-test a lui-même
traversé DEUX corrections avant les chiffres retenus ci-dessous :

1. **Premier passage (`chantier_5leviers_revalidation_2026-08-23.py`,
   n=600, session du 23/08)** : dominance apparemment RENFORCÉE par la
   correction r_trailing — profit +11,97%/+13,73% (1000$/3000$,
   population complète), et **+6,65%/+10,64% sur le sous-échantillon
   bloc1+2 seul** (n=280, la portion 100% exposée au bug), présenté à
   l'époque comme confirmant une "vigilance maximale" — mécanisme
   invoqué : le fix corrigerait justement les gros gagnants que §1.8
   exploite via la bascule Instant.
2. **🔴 Bug moteur découvert ensuite** : ce premier passage réutilisait
   `chantier_rrtp2_sizing_2026-08-16.py` comme moteur (seul script de la
   lignée exposant `size_func`/`routing_field`), qui **date d'AVANT le
   correctif du cap Blueberry Instant 1,5%/trade décrit plus haut dans
   cette même section (08/17-18)** et n'avait jamais été repatché — le
   cap réel n'était donc PAS actif pendant ce premier re-test, gonflant
   artificiellement l'apport mesuré du levier (même mécanisme de biais
   que celui déjà documenté ci-dessus pour le tableau n=600 08/17
   original).

**Chiffres retenus après correction du cap** (`chantier_5leviers_
revalidation_fixed_2026-08-23.py`, **n=300 screening — PAS ENCORE
reconfirmé à n=600**, cap Blueberry Instant 1,5%/trade actif) :
- Population complète : **+5,84% / +7,01%** (1000$/3000$) — direction
  inchangée (toujours net positif), mais nettement plus modeste que le
  premier passage (+11,97%/+13,73%).
- **Sous-échantillon bloc1+2 seul (n=280) : -0,10% / +3,44%** — PAS
  +6,65%/+10,64% comme annoncé au premier passage. **La robustesse de
  §1.8 sur ce sous-échantillon spécifiquement n'est donc PLUS établie
  avec la marge initialement annoncée** : à 1000$, l'apport en profit
  est même LÉGÈREMENT NÉGATIF (quasi neutre), à 3000$ un gain modeste
  (+3,44%) subsiste. L'axe risque (année1<0) reste lui favorable à §1.8
  sur ce sous-échantillon (-1,33pt aux deux plafonds) — c'est
  l'argument qui justifie encore l'adoption sur cette portion, PAS le
  profit.

**Ce qui ne change pas** : la direction d'adoption reste POSITIVE sur la
population complète (profit ET risque) — §1.8 est confirmé, la décision
d'adoption est actée. Ce qui change : l'affirmation "dominance confirmée
MÊME sur la portion la plus exposée au bug" (formulée au premier passage,
avant découverte du bug de cap) doit être **révisée** — sur bloc1+2
spécifiquement, l'effet est désormais quasi neutre en profit, pas une
dominance forte. **Reconfirmation à n=600 (niveau verdict) pas encore
faite avec le cap actif** — à faire avant de citer ces chiffres comme
acquis au même niveau que le reste de ce tableau.

Logs : `log_5leviers_A_refixed_n300_2026-08-23.txt`, scripts
`chantier_5leviers_revalidation_2026-08-23.py` (buggé, cap absent) et
`chantier_5leviers_revalidation_fixed_2026-08-23.py` (corrigé).

---

**🕰️ Référence 08/12 ci-dessous (RR≥1,35/corr0,80 seul, sans les deux
mécanismes ci-dessus) — reste la référence ADOPTÉE tant que la
proposition ci-dessus n'est pas confirmée :**

**🔴🆕 DÉCISION FINALE 08/12 — CASCADE COMPLÈTE, RR≥1,35 + CORRÉLATION 0,80
ADOPTÉS COMME NOUVELLE RÉFÉRENCE OFFICIELLE DU PROJET (§2.62/§2.63).** Le
seuil `min_rr=1,25` et `CORR_TH=0,6` utilisés dans TOUT le contenu ci-dessous
(daté 08/11 et antérieur) sont désormais **SUPERSEDED**, conservés tels
quels pour traçabilité historique — ne jamais les lire comme la référence
courante. La structure asymétrique par plafond (Run C à 1000$/Run F à
3000$, décision #16) **reste inchangée dans son principe**, seuls les 2
paramètres d'entrée (RR, corrélation) et les chiffres qui en découlent ont
changé.

**Référence officielle du projet (08/12), valeurs à retenir :**

| Plafond | Config | Profit moyen/médian | solde_negatif_annee4 | hit_ceiling_pct | Année1<0 |
|---|---|---|---|---|---|
| **1000$** | **Run C** (BB 14j, RR≥1,35, corr 0,80) | **5 836 643$ / 5 621 512$** | **0,50%** | **1,50%** | **30,50%** |
| **3000$** | **Run F** (BB 7j, RR≥1,35, corr 0,80) | **5 900 859$ / 5 630 556$** | **0,33%** | **0,33%** | **28,83%** |

n=600+cascade, seed=9999, `etape_aq_run_c_rr135_corr080_2026-08-12.py` /
`etape_ar_run_f_rr135_corr080_2026-08-12.py` (copies exactes de `etape_ai`/
`etape_ao`, seuls `min_rr` et `CORR_TH` changés — aucune autre logique
touchée, scripts originaux conservés intacts pour comparaison historique).
**Domine strictement l'ancienne référence sur les 4 axes aux deux
plafonds** : profit +6,3%/+5,6%, solde_negatif_annee4 -1,00pt/égal,
hit_ceiling -2,00pt/-1,00pt, année1<0 -5,00pt/-4,00pt. Détail complet de la
cascade (Section 0-3, tous les leviers/chantiers dérivés régénérés) : §2.63.

---

**🕰️ Contenu historique ci-dessous (08/11 et antérieur, RR=1,25/corr=0,6,
SUPERSEDED 08/12) — conservé tel quel pour traçabilité, ne pas utiliser
comme référence courante :**

**🔴🆕 DÉCISION FINALE 08/11 (session c, décision #16 TRANCHÉE) — LA
RÉFÉRENCE OFFICIELLE DU PROJET EST DÉSORMAIS ASYMÉTRIQUE PAR PLAFOND, PAS
UNE CONFIG UNIQUE. Ne pas lire une seule ligne de ce registre comme "la"
référence sans vérifier le plafond concerné :**
- **Plafond 1000$ → Run C** (cadence de payout par firm corrigée §2.32,
  Blueberry cadence PAR DÉFAUT 14j, PAS de surcoût +20%) —
  `etape_ai_payout_cadence_calibration_2026-08-11.py`. Choisi car le
  gain de Run F (Blueberry 7j) à ce plafond ne compense pas la
  dégradation hit_ceiling ×1,7.
- **Plafond 3000$ → Run F** (Blueberry 7j, coût réel +20% intégré,
  §2.35) — `etape_ao_run_f_cout_reel_2026-08-11.py`. Choisi car
  hit_ceiling y est neutre (0,00pt) tandis que profit et année1<0
  s'améliorent nettement, sans contrepartie mesurée à ce plafond.

Ce n'est PAS une adoption pure et simple de Run F ni un rejet pur : c'est
un arbitrage tranché conditionnellement au plafond personnel (décision
utilisateur explicite, 08/11 session c). `etape_ao_run_f_cout_reel_2026-
08-11.py` a été corrigé pour appliquer cette asymétrie automatiquement
(Blueberry 7j+surcoût actifs UNIQUEMENT si `ceiling` ∈
`BB_PAYOUT_7J_CEILINGS = {3000.0}` — avant cette correction, une
exécution multi-plafonds du script appliquait 7j aux DEUX plafonds sans
distinction, voir §2.35bis) — mais les chiffres n=600 déjà produits (ci-
dessous) restent valides tels quels : ils ont été mesurés en isolant
chaque plafond dans son propre run dédié (Run C pur d'un côté, Run F pur
de l'autre), donc aucun recalcul n'est nécessaire pour cette adoption.

**Référence officielle du projet, valeurs à retenir :**

| Plafond | Config | Profit moyen/médian | solde_negatif_annee4 | hit_ceiling_pct | Année1<0 |
|---|---|---|---|---|---|
| **1000$** | **Run C** (BB 14j) | **5 491 410$ / 5 361 009$** | **1,50%** | **3,50%** | **35,50%** |
| **3000$** | **Run F** (BB 7j) | **5 589 954$ / 5 457 443$** | **0,33%** | **1,33%** | **32,83%** |

---

**Historique de la mesure (contexte de la décision ci-dessus, conservé
tel quel) :** cadence corrigée CONFIRMÉE n=600 (ferme le point ouvert
§2.32/§4#16), Run F (Blueberry 7j) testé n=600 en CASCADE CHECK EXPLICITE
— verdict MIXTE, PAS une dominance stricte aux DEUX plafonds à la fois
(d'où l'adoption conditionnelle ci-dessus plutôt qu'un choix uniforme).
Scripts : `etape_ai_payout_cadence_calibration_2026-08-11.py` (Run C) /
`etape_ao_run_f_cout_reel_2026-08-11.py` (Run F), n=600, seed=9999
identique aux deux, deux plafonds. Durée : ~7,5 min/script (462s/461s
mesurés). Résultats bruts sur disque (non suivis par git, `*.csv`
gitignoré projet entier sauf `correlation_matrix.csv` — même convention
que les ~100 autres CSV `etape_*` du dépôt) :
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

**✅ DÉCISION FINALE 08/11 (session c) : adoption CONDITIONNELLE au
plafond, tranchée par l'utilisateur.** Run F remplace Run C comme
référence officielle UNIQUEMENT au plafond 3000$ (hit_ceiling y est
neutre, 0,00pt d'écart — gain net sur profit et année1<0 sans
contrepartie mesurée). Au plafond 1000$, Run C reste la référence
officielle : le hit_ceiling ×1,7 (+2,33pt) à ce niveau de capital n'est
pas jugé compensé par le gain de profit/année1<0. Voir le tableau
récapitulatif en tête de §1.8. Décision #16 §4 marquée ✅ RÉSOLU.

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

### 1.8bis Filtre forex-only — bug de population CORRIGÉ, impact sur la référence A (08/18)

**Découverte** : `build_extended_population()` (`rr_threshold_test.py:47`,
fonction fondatrice de TOUTE population utilisée dans ce projet, y compris
la référence officielle A ci-dessus) appliquait un filtre forex-only codé
en dur, indépendant de tout critère RR — **321 trades indices scrapés
avec succès (DAX40/S&P500/NASDAQ100/DJ30) étaient silencieusement
éliminés avant toute simulation**, jamais un choix méthodologique
documenté. Détails complets (citation de code, git log, mécanisme) :
`registre_strategie_trading.md` §2.46.

**Correctif appliqué le 08/18** (`rr_threshold_test.py:43-61`) : filtre
remplacé par un critère de mappabilité réelle (forex + 3 indices gérés
par `INDEX_KEYWORD_MAP`, DJ30 exclu naturellement — rr_tp1=NaN, bug de
parsing distinct non corrigé).

**Impact sur A (RR≥1,35, référence officielle)** :

| | Avant | Après | Δ |
|---|---|---|---|
| n | 631 | **742** | **+111 trades (+17,6%)** |
| Winrate | 39,5% | 39,9% | +0,4pt (négligeable) |
| EV | +0,8934R | +0,8995R | +0,0061R (+0,7% relatif, négligeable) |
| Fréquence | 11,71/mois | 13,77/mois | +17,6% |

**Qualité d'edge quasi inchangée (EV/winrate dilués à l'échelle de 631-742
trades), volume réellement augmenté de 17,6%.** Stress-test H1/H2+4 blocs
(`chantier_reference_A_indices_2026-08-18.py`, n=742) : EV positive dans
5/6 sous-périodes, la seule limite (bloc0, -0,009R quasi nul) est un
régime de marché difficile déjà présent dans le forex seul (-0,082R) —
les indices y sont même stabilisateurs (+0,402R). **Aucune inversion de
direction imputable aux indices, comportement de vraie diversification.**

**Statut** : correctif de code appliqué immédiatement (corrige un bug,
pas un nouveau levier à débattre). **Mais PAS encore intégré au vrai
moteur Monte Carlo flotte (§1.8/§2.35 restent construits sur l'ancienne
population 631 trades à ce jour)** — deux prérequis avant toute
régénération n=300/n=600 :
1. Faisabilité d'exécution live (le setup MT5/broker actuel peut-il
   trader DAX40/S&P500/NASDAQ100 ?) — en cours de vérification.
2. Matrice de corrélation indices↔indices et indices↔forex
   (`correlation_matrix.csv` ne couvre aujourd'hui que le forex, 14
   paires) — nécessaire pour que le mécanisme any-RR route correctement
   les trades indices en simulation flotte réelle. En cours de
   construction.

Tant que ces deux points ne sont pas tranchés, **la référence officielle
§1.8/§2.35 reste inchangée** — ce §1.8bis documente une correction de
fondation mesurée en amont (EV isolée), pas encore propagée à la
simulation flotte complète.

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

#### 2.35bis Décision #16 tranchée + correction du code (08/11 session c, plus tard)

L'utilisateur tranche pour une adoption CONDITIONNELLE
au plafond (voir §1.8 tête de section, décision #16 §4) : Run F à 3000$
uniquement, Run C à 1000$. Vérification faite : `etape_ao_run_f_cout_
reel_2026-08-11.py` appliquait Blueberry 7j+surcoût +20% de façon
UNIFORME aux deux plafonds dans son bloc `__main__` (boucle `for ceiling
in ceilings_arg`, `PAYOUT_CYCLE_DAYS_FIRST/SUBSEQUENT["Blueberry"]=7` et
`price_for_bb()` appliquaient le surcoût sans condition de plafond) —
CORRIGÉ : nouvelle constante `BB_PAYOUT_7J_CEILINGS = {3000.0}`, les
tables de cadence Blueberry redeviennent 14j par défaut et
`price_for_bb()`/`payout_cycle_days()` prennent désormais `ceiling` en
paramètre pour n'activer 7j+surcoût que si le plafond simulé est dans
cet ensemble. Aucun autre script de production/référence ne code cette
cadence (vérifié : `etape_ah_reference_officielle_2026-08-11.py`, le
script qui précède, ne contient aucune référence à un cycle 7j
Blueberry). Les chiffres n=600 déjà cités dans ce registre (Run C pur,
Run F pur, chacun mesuré dans son propre run isolé par plafond) restent
valides tels quels — cette correction ne change que le comportement
d'une future réexécution multi-plafonds du script, pas les résultats
déjà produits.

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

### 2.38 5 pistes de survie face aux séries de casses (08/11) — condition de test commune

Prompt utilisateur 08/11 : 5 pistes réactives à des faits déjà réalisés
(casses survenues) ou structurelles, AUCUNE ne prédit une mauvaise
période (chantier précurseur fermé, 10 pistes rejetées, §2.16-2.26
`registre_strategie_trading.md`). Base engine commune :
`pistes_survie_2026-08-11.py`, référence officielle par plafond déjà
adoptée (décision #16 §1.8/§2.35bis — Run C/BB14j à 1000$, Run F/BB7j à
3000$), n=300, seed=9999, population 721 trades, cadence payout par
firm, cap Blueberry corrigé. Détail par piste ci-dessous (§2.39-2.43).

### 2.39 Piste 1 — Fonds d'urgence déclenché par casses réalisées — REJETÉ à 1000$, candidat n=300 à 3000$ (08/11)

Portion `p1_emergency_pct` (10%/20%) de chaque crédit positif à
`state["reserve"]` déviée vers un bucket verrouillé
`state["reserve_emergency"]`, déversé d'un coup dans la réserve normale
dès que `p1_break_trigger` (2 ou 3) casses surviennent dans une fenêtre
`p1_window_days` (7/14/30j). Grille réduite à 6 combos (pas les 18 du
produit cartésien complet) pour rester dans un temps de calcul
raisonnable à n=300 : (10%,7j,2), (10%,14j,3), (10%,30j,2), (20%,7j,2),
(20%,14j,3), (20%,30j,2).

| Plafond | Config | Profit moyen | Δ profit | solde_negatif_annee4 | hit_ceiling_pct | Année1<0 |
|---|---|---|---|---|---|---|
| 1000$ | référence (Run C) | 5 588 381$ | — | 1,33% | 3,33% | 32,67% |
| 1000$ | 10%/7j/N2 | 5 574 355$ | -0,25% | 1,33% | 3,00% | 33,00% |
| 1000$ | 10%/14j/N3 | 5 568 669$ | -0,35% | 1,33% | 3,33% | 32,67% |
| 1000$ | 10%/30j/N2 | 5 574 805$ | -0,24% | 1,33% | 3,33% | 33,00% |
| 1000$ | 20%/7j/N2 | 5 559 651$ | -0,51% | 1,33% | **7,33% (×2,2)** | 32,33% |
| 1000$ | 20%/14j/N3 | 5 550 366$ | -0,68% | 1,33% | **9,67% (×2,9)** | 31,67% |
| 1000$ | 20%/30j/N2 | 5 560 194$ | -0,51% | 1,33% | **7,67% (×2,3)** | 32,33% |
| 3000$ | référence (Run F) | 5 658 217$ | — | 0,67% | 1,67% | 29,00% |
| 3000$ | 10%/7j/N2 | 5 659 896$ | **+0,03%** | **0,33%** | **0,67%** | 29,00% |
| 3000$ | 10%/14j/N3 | 5 652 218$ | -0,11% | 0,33% | 0,67% | 29,00% |
| 3000$ | 10%/30j/N2 | 5 659 896$ | **+0,03%** | **0,33%** | **0,67%** | 29,00% |
| 3000$ | 20%/7j/N2 | 5 646 840$ | -0,20% | 0,33% | 0,67% | 29,33% |
| 3000$ | 20%/14j/N3 | 5 640 396$ | -0,31% | 0,33% | 0,67% | 28,67% |
| 3000$ | 20%/30j/N2 | 5 646 932$ | -0,20% | 0,33% | 0,67% | 29,33% |

**À 1000$ : REJETÉ, surtout à 20%.** Verrouiller 20% de chaque crédit
retarde le déblocage normal au point de FAIRE EXPLOSER hit_ceiling
(×2,2 à ×2,9) — le mécanisme retire du cash précisément quand le
plafond serré en a le plus besoin. À 10%, effet net neutre à légèrement
négatif (-0,24 à -0,35% profit, aucun gain de risque mesurable) — pas un
mécanisme utile à ce plafond.

**À 3000$ : signal positif net, n=300 seulement.** Les 6 configs
améliorent OU maintiennent solde_negatif_annee4 (0,67%→0,33%, ÷2) et
hit_ceiling_pct (1,67%→0,67% pour 10%, ÷2,5) simultanément, pour un coût
de profit nul à faible (+0,03% à -0,31% selon config). **Meilleure config :
10%/7j/N2 (= 10%/30j/N2, résultats identiques car peu de fenêtres
7j déclenchent réellement 2 casses sans en déclencher aussi en 30j)** :
profit +0,03% (bruit, essentiellement gratuit), solde_negatif_annee4 et
hit_ceiling_pct divisés par 2-2,5. **Candidat pour n=600+cascade check
avant adoption** (règle explicite du prompt) — pas encore confirmé,
pas encore adopté. Fichier : `pistes_survie_2026-08-11.py` mode `p1`,
résultats `pistes_p1_n300.log` (log de session, non versionné).

### 2.40 Piste 2 — Sizing réduit après casse récente, orthogonal à V2 — REJETÉ sur l'ensemble n=300, effet réel mais localisé sur les runs catastrophiques (08/11)

Réduction temporaire du risque (`p2_sizing_reduction` 25%/50%) sur TOUT
compte ayant cassé dans les `p2_duration_days` (5/10/15) derniers jours,
peu importe la cause — multiplicatif avec la réduction DD-distance V2
déjà adoptée (§2.9x), pas un remplacement.

**n=300 complet, deux plafonds :**

| Plafond | Config | Profit moyen | Δ profit | solde_negatif_annee4 | hit_ceiling_pct | Année1<0 |
|---|---|---|---|---|---|---|
| 1000$ | référence | 5 588 381$ | — | 1,33% | 3,33% | 32,67% |
| 1000$ | -25%/5j | 5 579 964$ | -0,15% | 1,00% | 3,00% | 32,67% |
| 1000$ | -25%/10j | 5 564 579$ | -0,42% | 1,33% | 3,00% | 33,67% |
| 1000$ | -25%/15j | 5 540 292$ | -0,86% | 1,00% | 4,33% | 32,33% |
| 1000$ | -50%/5j | 5 520 565$ | -1,21% | 2,00% | 3,67% | 32,33% |
| 1000$ | -50%/10j | 5 448 698$ | -2,50% | 2,00% | 4,00% | 34,00% |
| 1000$ | -50%/15j | 5 289 050$ | **-5,36%** | 3,33% | 5,67% | 35,33% |
| 3000$ | référence | 5 658 217$ | — | 0,67% | 1,67% | 29,00% |
| 3000$ | -25%/5j | 5 624 581$ | -0,59% | 0,67% | 1,00% | 29,67% |
| 3000$ | -25%/10j | 5 616 081$ | -0,74% | 0,67% | 1,00% | 30,33% |
| 3000$ | -25%/15j | 5 573 780$ | -1,49% | 0,67% | 1,00% | 30,33% |
| 3000$ | -50%/5j | 5 605 599$ | -0,93% | 0,67% | 1,00% | 29,67% |
| 3000$ | -50%/10j | 5 551 974$ | -2,17% | 0,67% | 0,67% | 31,00% |
| 3000$ | -50%/15j | 5 469 786$ | -3,32% | 0,33% | 0,67% | 32,00% |

Coût de profit monotone croissant avec la sévérité/durée de la
réduction, sans amélioration nette compensatoire sur les axes de
risque (année1<0 empire systématiquement au-delà de -25%/5j). **REJETÉ
sur l'ensemble n=300 — aucune config ne domine.**

**Diagnostic ciblé demandé explicitement (replay exact run_idx=202,
même technique que `edge_circuit_breaker_v2` mode_point2, RNG avancé
séquentiellement 0..201 sans capture) — les 2 runs catastrophiques déjà
identifiés :**

| Run | Config | Net final | Δ vs baseline |
|---|---|---|---|
| ceiling1000_run202 | référence | -72 010$ | — |
| ceiling1000_run202 | -25%/5j | -63 762$ | **+11,5%** |
| ceiling1000_run202 | -25%/10j | -71 978$ | +0,0% |
| ceiling1000_run202 | -25%/15j | -76 405$ | -6,1% |
| ceiling1000_run202 | -50%/5j | -63 627$ | **+11,6%** |
| ceiling1000_run202 | -50%/10j | -75 883$ | -5,4% |
| ceiling1000_run202 | -50%/15j | -75 521$ | -4,9% |
| ceiling3000_run202 | référence | -131 594$ | — |
| ceiling3000_run202 | -25%/5j | -120 897$ | **+8,1%** |
| ceiling3000_run202 | -50%/5j | -118 454$ | **+10,0%** |
| ceiling3000_run202 | (10j/15j) | -118 454$ à -130 878$ | +0,5% à +10,0% |

**Résultat clé, pas un artefact de sélection** : la durée courte (5j,
peu importe 25% ou 50% de réduction) réduit reproductiblement la perte
du run catastrophique de 8 à 12% aux deux plafonds — l'effet EXISTE et
est mesurable sur le cas qu'il était censé traiter. Mais ce même effet
**ne généralise pas** à l'ensemble n=300 : le coût de la réduction de
sizing sur les trajectoires de récupération NORMALES (qui dominent
l'échantillon) dépasse le gain concentré sur les rares clusters de
casses. **Verdict : REJETÉ sur le portefeuille complet malgré un effet
réel et reproductible sur le sous-cas ciblé** — distinction utile,
mesurée explicitement comme demandé, pas supposée. Fichiers :
`pistes_survie_2026-08-11.py` modes `p2`/`p2_run202`, logs
`pistes_p2_n300.log`/`pistes_p2_run202.log` (non versionnés).

### 2.41 Piste 3 — Double starter (dilution du point de défaillance unique) — GFT reconfirme le pattern déjà connu, FundedNext REJETÉ aux deux plafonds (08/11)

⚠️ **Déviation méthodologique documentée** : "capital initial divisé, pas
dupliqué" n'est pas littéralement implémentable — les paliers de
challenge sont des tiers fixes par firm (25k/50k/50k/50k/200k selon
firm), pas une grandeur continue divisible. Testé comme 2 firms actives
dès le jour 0, chacune à SON propre palier/coût standard (même
convention que le bootstrap parallèle BB+GFT déjà testé §2.6 — ce script
le RETESTE sous la config actuelle, principe de fraîcheur, car §2.6 date
d'avant la cadence payout par firm et la population 721) — PAS une
duplication du même montant (ça, c'est Piste A'/BBx2, §2.15, différente).
Candidats testés : GFT (coût 288$, 2e moins cher après Blueberry 165$)
et FundedNext (coût 798,99$, meilleur EV/$ théorique mais bien plus cher
à l'entrée).

| Plafond | Config | Profit moyen | Δ profit | solde_negatif_annee4 | hit_ceiling_pct | Année1<0 | Déblocage médian |
|---|---|---|---|---|---|---|---|
| 1000$ | référence (solo BB) | 5 588 381$ | — | 1,33% | 3,33% | 32,67% | 6,5 mois |
| 1000$ | BB+GFT day0 | 5 394 283$ | -3,47% | **9,33% (×7)** | **33,00% (×10)** | 30,33% | 3,5 mois |
| 1000$ | BB+FundedNext day0 | 1 912 609$ | **-65,77%** | **29,67%** | **64,33%** | 42,00% | 3,4 mois |
| 3000$ | référence (solo BB) | 5 658 217$ | — | 0,67% | 1,67% | 29,00% | 6,2 mois |
| 3000$ | BB+GFT day0 | 5 933 280$ | **+4,86%** | 1,33% (pire) | 2,67% (pire) | **21,33% (-7,67pt)** | 3,6 mois |
| 3000$ | BB+FundedNext day0 | 2 577 419$ | **-54,44%** | 4,67% | 20,67% | 22,33% | 3,6 mois |

**BB+GFT (2e starter connu)** : reconfirme exactement le pattern déjà
documenté (§2.6/§2.11) sous la config actuelle — REJETÉ à 1000$ (le
coût combiné 453$ épuise la trésorerie de départ, hit_ceiling explose),
arbitrage à 3000$ (profit et année1<0 nettement meilleurs, ruine/
hit_ceiling légèrement pires — pas une dominance stricte 3-axes, décision
d'adoption toujours en attente, §4 décision #7 déjà ouverte, pas
rouverte ici).

**BB+FundedNext : REJETÉ SANS AMBIGUÏTÉ aux DEUX plafonds** — le coût
d'entrée (798,99$, soit 4,8x celui de GFT) domine tout avantage EV/$
théorique dans un rôle de starter jour 0 : à 1000$ il consomme 96% du
plafond immédiatement (963,99$ sur 1000$), provoquant hit_ceiling dans
64% des runs ; même à 3000$ le profit s'effondre de moitié. **Le
classement EV/$ (§2.8, utilisé pour la Piste 4 ci-dessous) ne se
transpose PAS à un rôle de capital immédiat** — un firm avec un excellent
rendement par dollar UNE FOIS FINANCÉ peut être un très mauvais choix de
capital de démarrage si son ticket d'entrée est élevé. Fichier :
`pistes_survie_2026-08-11.py` mode `p3`, résultats `pistes_p3_n300.log`
(non versionné).

### 2.42 Piste 4 — Réouverture fongibilité inter-firm sous config actuelle — REJETÉ, reconfirmé sans changement (08/11)

**Config exacte du rejet original retrouvée** (principe de fraîcheur
demandé explicitement) : `etape_h_fongibilite_slots_2026-08-10.py`,
testé 08/10 nuit (§2.8 ci-dessus), retesté une fois sous cap Blueberry
corrigé (08/10 nuit suite 6) — mais **jamais retesté après la cadence
payout par firm (§2.32, 08/11) ni la population 721 trades (§2.29,
08/11)**, les deux corrections majeures les plus récentes. Reteste donc
intégralement sous la config actuelle avant de considérer le rejet
toujours valide, comme demandé.

Port fidèle du mécanisme (queue unifiée relances+extra-comptes, triée
EV/$ décroissant, `EV_PER_DOLLAR` = FundedNext 953,68 > Fivers 783,39 >
GFT 638,57 > Blueberry 615,67 > FTMO 578,03, source Étape C corrigée)
dans le moteur actuel.

| Plafond | Config | Profit moyen | Δ profit | solde_negatif_annee4 | hit_ceiling_pct | Année1<0 |
|---|---|---|---|---|---|---|
| 1000$ | référence (non fongible) | 5 588 381$ | — | 1,33% | 3,33% | 32,67% |
| 1000$ | fongible | 5 588 662$ | +0,005% (bruit) | 1,33% | 3,33% | 32,67% |
| 3000$ | référence (non fongible) | 5 658 217$ | — | 0,67% | 1,67% | 29,00% |
| 3000$ | fongible | 5 658 217$ | **0,000% (identique au $ près)** | 0,67% | 1,67% | 29,00% |

**REJETÉ, RECONFIRMÉ sans aucun changement sous la config actuelle** —
même diagnostic qu'en 08/10 : la réserve fleet est presque toujours soit
largement abondante (tous les candidats financés simultanément, l'ordre
de priorité ne tranche jamais rien), soit en crise totale (rien à
réordonner). Les corrections cadence payout/population 721 n'ont
strictement rien changé à ce mécanisme — cohérent avec le fait que ces
corrections affectent le NIVEAU de trésorerie, pas la FRÉQUENCE des
fenêtres de pénurie partielle où la fongibilité pourrait apporter de la
valeur. Fichier : `pistes_survie_2026-08-11.py` mode `p4`, résultats
`pistes_p4_n300.log` (non versionné).

### 2.43 Piste 5 — Décorrélation du starter secondaire (isolation liquidité vs corrélation copytrade) — signal fort, corrélation copytrade identifiée comme mécanisme dominant du rejet à 1000$ (08/11)

Isole les 2 mécanismes mélangés dans le rejet de BB+GFT day0 à 1000$
(§2.6/§2.11/§2.41 ci-dessus) : liquidité en rafale (2 comptes financés
au même palier de capital, consomment la réserve simultanément) vs
corrélation copytrade (les 2 comptes prennent EXACTEMENT les mêmes
trades aux mêmes instants, donc cassent ensemble). Variante
"décorrélée" : le 2e starter (GFT) reçoit un flux de trades tiré d'une
permutation propre et indépendante de la MÊME population (même
distribution marginale, ordre différent) au lieu du flux partagé
copytrade — isole l'effet de timing/corrélation sans changer la
distribution de trades sous-jacente. n=300, plafond 1000$ uniquement
(c'est le plafond où le rejet existe, seul pertinent pour cette
décomposition).

| Config | Profit moyen | Δ vs référence | solde_negatif_annee4 | hit_ceiling_pct | Année1<0 |
|---|---|---|---|---|---|
| Référence (solo BB) | 5 588 381$ | — | 1,33% | 3,33% | 32,67% |
| BB+GFT CORRÉLÉ (réel, = Piste 3) | 5 394 283$ | -3,47% | 9,33% | 33,00% | 30,33% |
| BB+GFT DÉCORRÉLÉ (flux indépendant) | **6 025 346$** | **+7,82%** | 3,67% | 17,33% | **13,00%** |

**Résultat net et bien mesuré (n=300, effet large, pas du bruit)** : la
décorrélation à elle seule récupère la quasi-totalité du dommage et
DÉPASSE même la référence solo sur profit (+7,82%) et année1<0 (13,00%
vs 32,67%, -19,67pt) — tout en restant supérieure à la référence sur
hit_ceiling (17,33% vs 3,33%, toujours pire) et solde_negatif_annee4
(3,67% vs 1,33%, toujours pire), mais BEAUCOUP moins que la version
corrélée (hit_ceiling 33,00%→17,33%, quasi divisé par 2 ; solde_negatif_
annee4 9,33%→3,67%, divisé par 2,5).

**Décomposition claire** : sur l'écart total référence→BB+GFT corrélé
(hit_ceiling +29,67pt, solde_negatif_annee4 +8,00pt, profit -3,47%), la
DÉCORRÉLATION seule explique la majorité de la dégradation (hit_ceiling
retombe à +14,00pt residuel, solde_negatif_annee4 à +2,34pt résiduel une
fois décorrélé) — **la corrélation copytrade est le mécanisme DOMINANT
du rejet de Piste A à 1000$, pas la pure liquidité en rafale** (qui
persiste comme un residuel réel mais nettement plus petit, cohérent avec
2 comptes consommant simultanément la même réserve de démarrage même
sans jamais casser ensemble). **Diagnostic pur, pas une piste
d'adoption** — la décorrélation artificielle n'est pas un mécanisme
actionnable dans la vraie vie (le copytrade réel synchronise
nécessairement les comptes sur le même signal) ; ce résultat sert à
comprendre PLUTÔT QU'À CORRIGER le rejet de Piste A/BB+GFT à 1000$, et
pourrait informer une vraie piste de décorrélation future si un
mécanisme réaliste de désynchronisation partielle (délai d'exécution,
routage différent) était un jour proposé. Fichier :
`pistes_survie_2026-08-11.py` mode `p5`, résultats `pistes_p5_n300.log`
(non versionné).

### 2.44 Chantier "remise en question structurelle" — condition de test commune (08/11)

Prompt utilisateur 08/11 : contrairement aux pistes 1-5 (§2.38-2.43, réactives
à des faits déjà réalisés), ce chantier teste si des changements de
STRUCTURE peuvent casser le mécanisme de corrélation copytrade identifié
comme cause racine du rejet de Piste A/BB+GFT à 1000$ (Piste 5 §2.43 :
13,0% vs 32,7% d'année1<0 si décorrélation artificielle). Base engine :
`structure_pistes_2026-08-11.py`, référence officielle par plafond
(décision #16 §1.8/§2.35bis), n=300, screening — rien n'est adopté sans
n=600+cascade. Seuil BB7j généralisé en `ceiling>=3000$` (au lieu du set
exact `{3000.0}`) pour couvrir le balayage Section D.

**Référence (baseline, sans changement structurel), mesurée dans ce
chantier** — sert de comparaison à toutes les sections ci-dessous :

| Plafond | Profit moyen | solde_negatif_annee4 | hit_ceiling_pct | Année1<0 | Clustering casses |
|---|---|---|---|---|---|
| 1000$ | 5 588 407$ | 1,33% | 3,33% | 32,67% | 97,0% |
| 3000$ | 5 657 334$ | 0,67% | 1,67% | 29,00% | 97,0% |

**Métrique de clustering** : % de casses (poolées sur les n=300 runs)
tombant le même jour calendaire de simulation qu'au moins une autre
casse — même convention que le 92,4% mesuré sur run202 (§2.36
registre). 97,0% poolé sur n=300 est cohérent avec ce chiffre de
référence (mesuré sur UN seul run).

### 2.45 Section A — Répartition des 14 paires forex en 2 groupes par firm — REJETÉ, coût de profit écrasant malgré un mécanisme qui marche (08/11)

FTMO+Blueberry → groupe 1, GFT+Fivers → groupe 2, FundedNext garde accès
aux 14 paires (diversification complète). Groupes construits par un
algorithme glouton équilibré en fréquence historique (721 trades),
best-effort pour séparer les clusters de corrélation connus
(`correlation_matrix.csv` — cluster "USD-majors" AUD/USD·EUR/USD·
GBP/USD·NZD/USD à 0,68-0,85, cluster "JPY-crosses" à 0,41-0,80),
documenté comme non exhaustivement optimisé :
- Groupe 1 (FTMO+Blueberry, n=358/721) : NZD/USD, GBP/JPY, USD/CAD,
  USD/JPY, USD/CHF, EUR/JPY, GBP/CHF.
- Groupe 2 (GFT+Fivers, n=363/721) : AUD/JPY, AUD/USD, EUR/GBP, CHF/JPY,
  EUR/USD, GBP/USD, EUR/CHF.

| Plafond | Profit moyen | Δ profit | solde_negatif_annee4 | hit_ceiling_pct | Année1<0 | Clustering |
|---|---|---|---|---|---|---|
| 1000$ | 3 708 212$ | **-33,6%** | 0,33% (meilleur) | 0,67% (meilleur) | 36,33% (pire, +3,7pt) | **65,9%** (vs 97,0%) |
| 3000$ | 3 734 769$ | **-34,0%** | 0,00% (meilleur) | 0,00% (meilleur) | 37,67% (pire, +8,7pt) | **66,4%** |

**Le mécanisme MARCHE** (clustering chute de 31pt, solde_negatif_annee4
et hit_ceiling s'effondrent quasiment à zéro) mais **le coût est
écrasant** : restreindre chaque firm à la moitié des paires affame sa
fréquence de trading bien plus que la décorrélation n'apporte de
protection — un tiers du profit disparaît, et année1<0 empire
nettement (surtout à 3000$). **REJETÉ.**

### 2.46 Section B — Parité temporelle du flux de signaux — REJETÉ, moins pire que A mais toujours écrasant (08/11)

FTMO+GFT ne prennent que les rangs impairs (1er, 3e...) du flux
RÉELLEMENT EXÉCUTÉ (indice de slot dans la séquence bootstrap — pas le
rang dans l'historique brut non-rééchantillonné, le bootstrap mélangeant
déjà l'ordre, déviation documentée), Blueberry+Fivers+FundedNext les
rangs pairs.

| Plafond | Profit moyen | Δ profit | solde_negatif_annee4 | hit_ceiling_pct | Année1<0 | Clustering |
|---|---|---|---|---|---|---|
| 1000$ | 3 777 043$ | **-32,4%** | 0,00% (meilleur) | 0,00% (meilleur) | 33,00% (~stable) | **87,7%** (vs 97,0%) |
| 3000$ | 3 793 193$ | **-32,9%** | 0,00% (meilleur) | 0,00% (meilleur) | 29,33% (~stable) | **88,4%** |

Décorrèle moins bien que A (clustering ne chute que de 9pt vs 31pt pour
A) mais préserve mieux année1<0 (stable au lieu de +3,7/+8,7pt). Le coût
de profit reste néanmoins du même ordre de grandeur écrasant (-32,4%/
-32,9%). **REJETÉ.**

### 2.47 Section C — Compte contrarian sur la bande RR 0,75-1,25 — ★ CANDIDAT n=600+cascade (08/11)

Compte dédié (palier Blueberry, le plus petit disponible), actif dès le
jour 0 en parallèle du starter normal, trade EXCLUSIVEMENT la bande
0,75≤rr_tp1<1,25 (jamais tradée par le reste de la flotte — filtre
standard du projet ≥1,25). Flux indépendant, bootstrappé séparément,
fusionné par le temps avec le flux principal.

**Pré-vérification demandée explicitement (avant intégration flotte)** :
`build_population_with_trailing(min_rr=0.75)` filtré à `<1.25` → n=311
trades, **winrate 50,5%, EV +0,781R** — canal positif net, pas un canal
à EV négative (winrate même supérieur aux 40,4% du canal principal,
RR moyen par trade plus faible mais fréquence de victoire plus haute).

| Plafond | Profit moyen | Δ profit | solde_negatif_annee4 | hit_ceiling_pct | Année1<0 | Clustering |
|---|---|---|---|---|---|---|
| 1000$ | 5 689 062$ | **+1,80%** | 1,00% (meilleur) | 4,33% (**pire**, +1pt) | 29,67% (meilleur, -3,0pt) | 96,5% (~stable) |
| 3000$ | 5 775 387$ | **+2,09%** | 0,00% (meilleur) | 0,33% (**meilleur**, ÷5) | 26,00% (meilleur, -3,0pt) | 96,4% (~stable) |

**Seule section qui AJOUTE du profit plutôt que d'en retirer** —
différence structurelle clé vs A/B : au lieu de restreindre le volume
des comptes existants, elle ajoute un canal de profit positif
indépendant. Résultat quasi propre à 3000$ (dominance sur les 3 axes de
risque + profit), un seul axe dégradé à 1000$ (hit_ceiling +1pt, gain de
profit/année1<0 en contrepartie). Clustering quasi inchangé (le compte
contrarian est 1 compte parmi ~15-20, dilué dans la métrique poolée —
attendu, ce n'est pas son mécanisme d'action). **★ Candidat prioritaire
pour n=600+cascade check avant adoption.**

### 2.48 Section D — Balayage du plafond personnel (1000$→10 000$) — le critère strict <1% n'est atteint par AUCUN plafond testé (08/11)

Config référence (Run C sous 3000$, Run F à 3000$ et au-delà — seuil
généralisé), sans changement structurel.

| Plafond | Profit moyen | solde_negatif_annee4 | hit_ceiling_pct | Année1<0 |
|---|---|---|---|---|
| 1000$ | 5 588 407$ | 1,33% | 3,33% | 32,67% |
| 2000$ | 5 629 755$ | 0,33% | 1,67% | 32,67% |
| 3000$ | 5 657 334$ | 0,67% | 1,67% | 29,00% |
| 5000$ | 5 657 039$ | 0,67% | **1,00%** | 29,00% |
| 7500$ | 5 657 001$ | 0,67% | **1,00%** | 29,00% |
| 10000$ | 5 673 232$ | 0,33% | **1,00%** | 29,00% |

**hit_ceiling_pct plafonne exactement à 1,00% à partir de 5000$ et ne
descend JAMAIS sous ce seuil, même à 10 000$ (10× le budget actuel)** —
résidu incompressible, pas un problème de liquidité personnelle
(diagnostiqué et confirmé en §2.49 ci-dessous : c'est le mode
"effondrement flotte mature" déjà identifié, aucun plafond ne protège
contre). solde_negatif_annee4 plafonne aussi tôt (~0,3-0,7% dès
2000-3000$, jamais 0,00% exact). Année1<0 plafonne à 29,00% dès 3000$
(la composante liée à la vitesse de déblocage disparaît, ce qui reste
est indépendant du capital). **Le critère strict utilisateur (<1% sur
les DEUX axes simultanément) n'est atteint par aucun plafond testé** —
le "vrai seuil de sécurité" semble se situer autour de 5000$ (au-delà,
plus aucun gain mesurable), mais le plancher de 1% lui-même n'est pas
éliminable par le capital.

### 2.49 Section 2 (chantier "trois volets") — Diagnostic du résidu 1% hit_ceiling à 10 000$ — CONFIRMÉ : même mode "effondrement flotte mature", aucun mécanisme nouveau (08/11)

Suite directe de §2.48. Reproduction EXACTE des n=300 runs du sweep D
à 10000$ (même seed=9999, même population/config — vérifié déterministe)
avec extraction complète du journal d'événements
(`structure_section2_diagnostic_2026-08-11.py`, copie du mécanisme de
journal de `edge_circuit_breaker_v2_2026-08-11.py`, seuil BB7j généralisé
ajouté). Détection du mode "effondrement flotte mature" (§2.36-2.37) :
cluster de 3-11 casses en fenêtre ≤3j simulés, touchant ≥2 firms
distinctes, ET dont au moins une casse du cluster tombe dans la vraie
fenêtre de creux d'edge vérifiée sur données réelles (2022-11-01 →
2023-01-20).

**Résultat exact** : hit_ceiling touché par **3/300 runs (1,00%,
identique au sweep D — confirme la reproduction déterministe)** :
runs 67, 95, 202. **Les 3 correspondent au mode "effondrement flotte
mature" (100% de correspondance, aucun mécanisme différent trouvé)** —
run 202 est le run catastrophique déjà connu (net final -140 944$ à
10000$, cohérent avec -72 010$/-131 594$ mesurés à 1000$/3000$
respectivement dans les chantiers précédents, la perte augmentant avec
le plafond puisque le mécanisme n'est pas lié au capital).

**Probabilité empirique du mode sur l'ENSEMBLE n=300 (pas seulement les
runs extrêmes, demandé explicitement)** : **91/300 (30,33%)** des runs
montrent au moins un cluster correspondant à la signature complète —
bien plus fréquent que le taux de hit_ceiling lui-même (1,00%). **Nuance
clé** : le mécanisme sous-jacent (casses groupées pendant une vraie
période de marché difficile) est courant (~30% des runs), mais à
10 000$ de capital il est presque toujours absorbé sans toucher le
plafond — seuls les tirages les plus sévères de ce même mécanisme (1
run sur 30 environ parmi ceux qui le montrent) épuisent effectivement la
trésorerie.

**Verdict demandé explicitement par le prompt** : **"même mécanisme déjà
connu, le résidu de 1% est bien le plancher réel du projet et doit être
accepté comme tel."** Cohérent avec la conclusion déjà tirée sur la
Piste G/décorrélation asymétrique (fermée pour la même raison, §2.37) —
aucun plafond de trésorerie, aussi élevé soit-il, ne protège contre une
vraie période de marché défavorable qui touche plusieurs firms
copytradées simultanément. Journaux complets des 3 runs sur disque :
`structure_section2_logs/ceiling10000_run{67,95,202}.json` (non
versionnés, comme tous les JSON de deep-dive du projet).

### 2.50 Section 1 (chantier "trois volets") — Capital combiné, deux traders, réplication identique (08/11)

Contexte confirmé par 3 firms : FTMO/GFT = 400k$ **par trader** (un
associé réel — VPS, comptes, décisions distincts — est un trader
distinct, plafond remis à zéro sur ces 2 firms, PAS de coordination
nécessaire entre les 2 fleets). Blueberry = 400k$ "per trader OR
household", ambiguïté non résolue, traité conservativement comme
NON-DOUBLABLE (capital combiné 400k$ partagé). Fivers/FundedNext :
statut non vérifié, traités par défaut comme FTMO/GFT (hypothèse
signalée, pas confirmée). Moteur : `dual_trader_2026-08-11.py`, bug
trouvé et corrigé en debug AVANT le premier run n=300 (`ever_funded`
figé à `True` dans un proxy gelait `just_funded` à `False` en
permanence, bloquant tout déblocage de groupe au-delà du starter
Blueberry jour 0 — profit ~30× trop bas en smoke test, cause identifiée
et corrigée par un dump manuel de l'état).

**Étape 1 — screening architecture × variante Blueberry, 3000$/3000$
uniquement (économie de calcul explicite documentée : 16 configs
complètes aurait été trop long pour un screening n=300, donc criblage
d'abord sur la combinaison de plafond la plus représentative, puis
balayage complet uniquement sur la config gagnante)** :

| Config | Profit moyen | solde_negatif_annee4 | hit_ceiling combiné | (T1/T2) | Année1<0 | Clustering |
|---|---|---|---|---|---|---|
| Séparé, BB solo1 | 10 211 141$ | 0,33% | 1,67% | 1,67%/1,00% | 28,00% | 99,8% |
| **Séparé, BB split** | **10 205 794$** | 0,67% | **1,00%** | 1,00%/1,00% | 28,00% | 99,9% |
| Poolé, BB solo1 | 10 397 852$ | 0,67% | 3,33% | 2,33%/3,33% | 28,33% | 99,7% |
| Poolé, BB split | 10 400 996$ | 0,67% | 3,33% | 2,33%/3,33% | 28,00% | 99,9% |

**Architecture "poolée" (réserve société commune) TRIPLE hit_ceiling
(1,00%→3,33%) pour seulement +1,9% de profit** — la réserve partagée ne
diversifie PAS le risque puisque les 2 fleets cassent quasi-simultanément
(clustering ~99,8% poolé, cohérent avec le point de vigilance demandé
explicitement : le mécanisme de corrélation copytrade s'applique bien
aux 2 fleets à la fois). Pooler une réserve n'aide QUE si les demandes de
cash sont désynchronisées — ici elles ne le sont presque jamais, donc
pooler double la demande simultanée sur le même pool au lieu de la
lisser. **Architecture "séparée" gagnante** (chaque trader garde sa
propre trésorerie protégée) — variante Blueberry "split" (capacité de
croissance partagée au fil de l'eau, plafonnée à 400k$ combinés)
légèrement plus équilibrée entre traders que "solo1" (tout à T1) pour un
profit quasi identique. **Bonne nouvelle implicite pour le point de
vigilance posé** : malgré un clustering quasi total, hit_ceiling combiné
(1,00%) reste PROCHE du hit_ceiling simple-fleet à 3000$ (1,67%,
référence §2.44) — il ne s'additionne PAS entre les 2 traders sous
architecture séparée, contrairement à la crainte initiale.

**Étape 2 — balayage des 4 combinaisons de plafond, architecture séparée
+ BB split (config gagnante) :**

| Config (T1$/T2$) | Profit moyen | solde_negatif_annee4 | hit_ceiling combiné | (T1/T2) | Année1<0 | Clustering |
|---|---|---|---|---|---|---|
| 1000$/1000$ | 10 107 146$ | 1,33% | 3,00% | 3,00%/3,00% | 31,33% | 99,9% |
| 1000$/3000$ | 10 169 296$ | 0,67% | 2,67% | 2,67%/1,00% | 30,33% | 99,6% |
| 3000$/1000$ | 10 171 791$ | 0,67% | 2,67% | 1,00%/2,67% | 30,33% | 99,6% |
| **3000$/3000$** | **10 205 794$** | **0,67%** | **1,00%** | 1,00%/1,00% | **28,00%** | 99,9% |

**Symétrie T1↔T2 confirmée** (1000$/3000$ et 3000$/1000$ donnent des
résultats quasi identiques avec les rôles T1/T2 inversés, bon test de
cohérence du moteur — pas de biais structurel favorisant un trader).
**3000$/3000$ domine strictement les 3 autres combinaisons sur tous les
axes** (profit le plus haut, hit_ceiling le plus bas, année1<0 le plus
bas) — sans surprise (plus de capital des deux côtés aide toujours dans
ce moteur), mais confirme qu'il n'y a pas d'effet pervers à donner plus
de marge aux deux traders simultanément. Le plafond 1000$/1000$ reste le
pire sur tous les axes, cohérent avec la flotte simple.

### 2.51 Section 1bis (chantier "trois volets") — Spécialisation par segment de signal, capitaux séparés — AUCUNE variante ne bat la réplication simple (08/11)

Teste si donner à CHAQUE trader son propre capital séparé (contrairement
aux Sections A/B du chantier structurel, où le capital restait partagé
DANS un seul trader) permet à la spécialisation de signal d'échapper au
coût de volume qui les a fait rejeter. 3 variantes, 3000$/3000$
uniquement, architecture séparée + BB split (config gagnante Section 1) :

| Variante | Profit moyen | Δ vs réplication | solde_negatif_annee4 | hit_ceiling combiné | (T1/T2) | Année1<0 | Clustering |
|---|---|---|---|---|---|---|---|
| Réplication (référence) | 10 205 794$ | — | 0,67% | 1,00% | 1,00%/1,00% | 28,00% | 99,9% |
| RR-band (T2=bande contrarian 0,75-1,25 seule) | 6 098 112$ | **-40,2%** | 0,33% (meilleur) | 2,00% (pire) | 1,67%/0,33% | 28,67% | 96,1% |
| Paires (T1=groupe1, T2=groupe2, chacun sur TOUTES ses firms) | 6 216 474$ | **-39,1%** | 0,00% (meilleur) | 0,00% (meilleur) | 0,00%/0,00% | 36,33% (pire, +8,3pt) | 88,7% |

**L'hypothèse du prompt (capital séparé = pas de coût de volume) est
RÉFUTÉE empiriquement.** Le coût de profit est en réalité PIRE ici
(-39/-40%) que dans les Sections A/B du chantier structurel précédent
(-32/-34%, §2.45-2.46) — parce que la spécialisation par trader restreint
TOUTES les firms de ce trader (5/5), alors que Section A/B ne
restreignaient que 2 des 5 firms d'une flotte unique (les 3 autres, dont
FundedNext, gardaient l'accès complet). Avoir son propre capital séparé
n'aide en rien si c'est TOUT ce capital qui trade un signal appauvri —
le problème n'a jamais été le partage de capital, c'est la réduction de
fréquence de trading elle-même, quelle que soit sa cause structurelle.
⚠️ Le clustering de la variante "paires" (88,7%) est numériquement plus
haut que celui de la Section A single-fleet (66,4%, §2.45) malgré une
logique de séparation analogue — probablement un artefact de la métrique
poolée (2× plus de comptes/opportunités de casse avec 2 traders qu'avec
1 seule flotte, gonflant mécaniquement le taux de coïncidence même jour
sans rapport avec la vraie corrélation structurelle), pas une preuve que
la décorrélation "marche moins bien" à 2 traders — signalé explicitement,
pas lissé. **Aucune des 3 variantes ne bat la réplication simple** — la
réplication reste la config Section 1 de référence pour ce chantier,
la spécialisation par trader est fermée dans sa forme testée ici.

⚠️ **§2.50-2.51 SUPERSEDED sur l'architecture de plafond personnel par
§2.52 ci-dessous (08/12)** — les chiffres et verdicts qualitatifs restent
valides pour l'ARCHITECTURE (séparé bat poolé pour une réplication
identique), mais les VALEURS EXACTES supposaient un plafond personnel
1000$/3000$ PAR TRADER (donc 2000$/6000$ combinés en réalité) au lieu
d'un budget unique combiné comme prévu — corrigé en §2.52.

### 2.52 Correction méthodologique — plafond personnel COMBINÉ (pas par trader) + nouvelle variante décorrélation+réserve commune (08/12)

**Correction demandée explicitement par l'utilisateur** : le filet de
sécurité personnel (cash sorti de la poche en dernier recours, PAS
`state["reserve"]` qui reste la trésorerie de trading réinvestie) est un
**budget UNIQUE partagé entre les 2 traders** (1000$ ou 3000$ **total**,
pas chacun) — les chiffres de §2.50-2.51 doublaient involontairement ce
budget. Corrigé dans `dual_trader_2026-08-11.py` : `ceilings` (dict par
trader) → `ceiling_combined` (un seul float), `real_cash_paid`/
`hit_ceiling` passés d'un état par trader à un état combiné partagé
(`combined_cash`), consommé par le premier des deux traders qui en a
besoin. `state["reserve"]` reste séparée par trader sous l'architecture
"séparée" (inchangé, ne pas confondre les deux mécaniques). Démarrage
simultané jour 0 des deux flottes : vérifié déjà correct (aucun décalage
de calendrier dans le code), confirmé par les journaux d'audit
(`j=0.0` pour T1 et T2 identiquement).

**Vérification méthodologique effectuée avant relance (3 points demandés
explicitement, tous clarifiés avant tout calcul)** :
1. `hit_ceiling_pct` = logique **OR** ("au moins un trader épuise le
   pool"), pas AND — code cité (`combined_hit_ceiling = st["T1"]["hit_
   ceiling"] or st["T2"]["hit_ceiling"]`, devenu `combined_cash["hit_
   ceiling"]` après correction), structurellement identique à la flotte
   simple (même `handle_cost_hybrid`, juste paramétré par trader).
   Vérifié arithmétiquement sur les runs déjà générés : à 3000$/3000$
   (ancienne architecture), OR≡AND≡individuel (chevauchement total, 3/3/3
   runs) ; sur les combos asymétriques, OR≠AND (8 vs ≤3), confirmant la
   bonne sémantique.
2. Le bug `ever_funded` (trouvé et corrigé avant le premier run n=300,
   voir note dans §2.50) **n'affectait PAS** la référence flotte simple —
   vérifié en lisant le code : `structure_pistes_2026-08-11.py` et
   `etape_ao_run_f_cout_reel_2026-08-11.py` (générateur des chiffres
   officiels Run C/Run F) passent le dict `state` persistant directement
   à `process_trade_mf`, jamais de proxy jetable. Aucune régénération
   nécessaire.
3. Audit manuel de 3 runs aléatoires (`random.Random(12345).sample(
   range(300), 3)` → runs 5, 152, 213) avec journal complet : plafond
   Blueberry combiné vérifié à CHAQUE instant du run (pas juste à la
   fin), jamais dépassé (max observé = 400 000$ exactement dans les 3
   cas, split 225k$ T1 / 175k$ T2 dans les 3 cas — cohérence du
   comportement "split" premier-arrivé-premier-servi).

**Nouvelle config testée (jamais essayée avant) : spécialisation A/B +
réserve de trading COMMUNE** (contrairement à Section 1bis §2.51 qui
gardait les réserves séparées). Hypothèse : la réserve de l'un peut
refinancer l'autre precisément parce que leurs mauvais jours ne
coïncident pas (contrairement au cas identique où pooler empire
toujours, §2.50).

**Tableau complet, 4 configs × 2 plafonds combinés, n=300, architecture
BB "split" :**

| # | Config | Plafond combiné | Profit moyen | solde_negatif_annee4 | hit_ceiling_pct | Année1<0 | Clustering |
|---|---|---|---|---|---|---|---|
| 1 | Même stratégie, réserves séparées | 1000$ | 9 593 520$ | 5,33% | 22,33% | 32,67% | 99,8% |
| 2 | Même stratégie, réserve commune | 1000$ | 9 951 136$ | 5,67% | **24,67% (pire)** | 31,00% | 99,8% |
| 3 | A/B, réserves séparées | 1000$ | 5 968 565$ | 1,67% | 15,33% | 32,33% | 96,1% |
| **4** | **A/B, réserve commune** | **1000$** | **6 108 417$** | **0,67%** | **4,33%** | **29,33%** | 96,2% |
| 1 | Même stratégie, réserves séparées | 3000$ | 10 167 514$ | 1,00% | 1,67% | 28,00% | 99,9% |
| 2 | Même stratégie, réserve commune | 3000$ | 10 360 400$ | 1,00% | **4,33% (pire, ×2,6)** | 28,00% | 99,9% |
| 3 | A/B, réserves séparées | 3000$ | 6 097 967$ | 0,33% | 2,00% | 28,67% | 96,1% |
| **4** | **A/B, réserve commune** | **3000$** | **6 190 208$** | **0,00%** | **0,00%** | **27,33%** | 96,2% |

**Config 4 domine strictement config 3 sur les 4 axes, aux DEUX
plafonds** — première fois dans tout le chantier (single-fleet ou
dual-trader) qu'un pooling de réserve AIDE plutôt que nuit. Contraste
net avec config 1→2 (pooler entre 2 flottes IDENTIQUES empire toujours
le risque, cohérent avec le clustering quasi-total 99,8-99,9% —
confirmé sous le plafond corrigé) : pooler entre 2 flottes DÉCORRÉLÉES
(A/B, clustering 96,1-96,2%) élimine quasiment tout hit_ceiling.

**Mécanisme illustré concrètement (demandé explicitement, pas juste les
chiffres)** — run 67, seed=9999, plafond combiné 1000$, même tirage de
marché pour les 2 architectures : le compte Blueberry de T1 (starter
jour 0) casse au jour 334,6 (perte EUR/USD). Sous réserves séparées, T1
n'a plus de cash propre pour rouvrir ET le plafond combiné est déjà
épuisé (`real_cash_paid_combined=1000,0$` au moment de la casse) → T1
bloqué, ne se relève jamais (net final -11 338$, flotte jamais
débloquée). Sous réserve commune, même événement, mais la réserve de T2
(canal contrarian, capacité dormante à ce moment) couvre la réouverture
→ T1 repart, finit à **+5 691 886$**. T2 change à peine (-218k$→-54k$) :
cette capacité ne lui manquait pas. **Pas un cas isolé** : sur les 80
premiers runs scannés à 1000$, 14 montrent ce schéma (séparées cassent,
commune sauve) — **zéro cas dans le sens inverse**. Fichiers :
`dual_trader_2026-08-11.py` mode `matrix` (4 configs corrigées),
`dual_trader_mechanism_example_2026-08-12.py` (scan 80 runs),
`dual_trader_run67_deepdive_2026-08-12.py` (journal complet run 67).

**Config 4 (spécialisation A/B + réserve commune) est un nouveau
candidat n=600+cascade** — distinct de et supérieur à toutes les autres
configs dual-trader testées à ce jour, avec un mécanisme causal
identifié (pas une coïncidence statistique). Pas encore confirmé, pas
encore adopté.

### 2.53 Confirmation n=600+cascade — Config 1 vs Config 4, deux plafonds (08/12)

Demandé explicitement : confirmation n=600 des 2 configs retenues à
l'issue du screening n=300 (§2.52) — config 1 (même stratégie, réserves
séparées) et config 4 (spécialisation A/B, réserve de trading commune),
chacune aux 2 plafonds combinés (1000$, 3000$). Pas de recommandation
unique tranchée automatiquement — livraison des chiffres définitifs pour
un choix utilisateur entre profit maximal et risque quasi nul.

| Config | Plafond | n | Profit moyen | solde_negatif_annee4 | hit_ceiling_pct | Année1<0 |
|---|---|---|---|---|---|---|
| 1. Même stratégie, séparé | 1000$ | 300 | 9 593 520$ | 5,33% | 22,33% | 32,67% |
| 1. Même stratégie, séparé | 1000$ | **600** | **9 317 773$** | **6,83%** | **23,50%** | **37,33%** |
| 4. A/B, réserve commune | 1000$ | 300 | 6 108 417$ | 0,67% | 4,33% | 29,33% |
| 4. A/B, réserve commune | 1000$ | **600** | **5 985 710$** | **0,83%** | **5,17%** | **32,67%** |
| 1. Même stratégie, séparé | 3000$ | 300 | 10 167 514$ | 1,00% | 1,67% | 28,00% |
| 1. Même stratégie, séparé | 3000$ | **600** | **10 041 125$** | **0,83%** | **2,00%** | **32,17%** |
| 4. A/B, réserve commune | 3000$ | 300 | 6 190 208$ | 0,00% | 0,00% | 27,33% |
| 4. A/B, réserve commune | 3000$ | **600** | **6 084 214$** | **0,00%** | **0,83%** | **30,17%** |

**Verdict cascade check : STABLE, aucune inversion de dominance.** Les 4
configs suivent le même schéma n=300→n=600 : profit quasi inchangé
(-1% à -3%), solde_negatif_annee4/hit_ceiling stables à légèrement plus
élevés, année1<0 systématiquement +3 à +5pt (biais déjà documenté
projet-wide — n=300 sous-estime toujours ce métrique bruité, pas
spécifique à une config ici). **Config 1@1000$ confirmée trop risquée**
(hit_ceiling 23,50% à n=600, pire qu'à n=300 — hors jeu). **Deux options
définitives restantes, non tranchées ici par choix explicite** :
- **Profit maximal — Config 1@3000$** : 10 041 125$, hit_ceiling 2,00%,
  solde_negatif_annee4 0,83%.
- **Risque quasi nul — Config 4@3000$** : 6 084 214$ (-39% vs Config
  1@3000$), hit_ceiling 0,83%, solde_negatif_annee4 0,00%.
- Config 4@1000$ reste une option intermédiaire si le budget réel est
  contraint à 1000$ (hit_ceiling 5,17%, profit 5 985 710$).

**Décision utilisateur finale entre les 2 options 3000$ toujours en
attente** — pas de recommandation automatique par consigne explicite du
prompt. Fichiers : `dual_trader_2026-08-11.py` mode `confirm`,
`dual_trader_confirm_c{1000,3000}_n600.csv` (non versionnés).

### 2.54 Audit structuré préventif de `dual_trader_2026-08-11.py` (08/12)

Demandé explicitement AVANT toute confirmation supplémentaire (chercher
les bugs proactivement plutôt que d'attendre qu'un chiffre suspect les
révèle, comme pour `ever_funded`). Méthode : 3 questions imposées
(comportements attendus vérifiés un par un, traçage du chemin de
l'argent, comparaison ligne par ligne au moteur flotte-simple
`structure_pistes_2026-08-11.py` déjà audité), pas un scan aveugle.

**Vérifié et confirmé correct** : plafond personnel combiné
(`combined_cash["real_cash_paid"]`, initialisé à la somme des coûts
jour-0 des 2 traders, consommé par le premier qui en a besoin) ;
routage réserve séparée/commune (`get_reserve`/`add_reserve`/
`sub_reserve`) ; aucune fuite ou confusion de compte entre T1/T2
(chaque compte appartient structurellement à un seul `accounts[tid]`) ;
logique casse/réouverture/DD-sizing/payout cycle identique bloc par
bloc à `structure_pistes.py` (juste paramétrée par `tid`) ; cap
Blueberry combiné 400k$ (déjà audité §2.52 par 3 journaux complets).

**3 problèmes trouvés (mineurs), aucun ne remet en cause les chiffres
déjà publiés (§2.52/§2.53) :**
1. **IS calculé séparément par trader** au lieu d'une fois sur le
   profit combiné de la SAS (T1/T2 sont associés de la MÊME société,
   cf. contexte Section 1) — le barème progressif (15%/25%, seuil
   42 500€) s'applique deux fois au lieu d'une. Impact chiffré : au
   plus ~4 250€/an de différentiel, **<0,001% des profits multi-
   millions en jeu** — sous le bruit d'échantillonnage. Trouvé, non
   corrigé (impact négligeable).
2. **`emergency_capital` (300$) reste indépendant par trader**, pas
   fusionné comme le plafond personnel — incohérent avec la philosophie
   de la correction §2.52, mais mécanisme rarissime (ne se déclenche
   que si TOUS les comptes d'un trader tombent à zéro simultanément) et
   montant minime. Trouvé, non corrigé.
3. **Ordre T1-avant-T2 au sein du même instant simulé** quand la
   réserve est commune — un biais de priorité arbitraire mais fixe
   (pas un vol ni un double-comptage). Trouvé, documenté, pas un bug
   fonctionnel.

**Rien de plus trouvé** — dit explicitement, comme demandé. Aucun des 3
points ne justifie de relancer le n=600 déjà produit.

### 2.55 Confirmation n=600+cascade — Stratégie B SEULE, en isolation (08/12)

Demandé explicitement : Stratégie B (canal contrarian, RR 0,75-1,25)
n'avait été validée qu'en screening n=300 comme PETIT COMPTE
SUPPLÉMENTAIRE (Section C du chantier structurel, §2.47) — jamais
confirmée seule. Testée ici en isolation totale : un seul trader, flotte
simple standard (5 firms, architecture identique à Run C/Run F), mais
alimentée EXCLUSIVEMENT par la population contrarian (311 trades) au
lieu de la population standard (721 trades, RR≥1,25).

| Plafond | n | Profit moyen | solde_negatif_annee4 | hit_ceiling_pct | Année1<0 |
|---|---|---|---|---|---|
| 1000$ | 600 | 652 284$ | 24,67% | 2,00% | **76,50%** |
| 3000$ | 600 | 657 735$ | 24,17% | 0,67% | **77,50%** |

**Résultat très différent de la référence signal principal** (~5,5-
6,8M$, ~1% solde_negatif_annee4, ~29-33% année1<0) — profit ÷8 environ,
année1<0 plus que doublé (76-77% vs ~30%). **Pas une contradiction avec
§2.47** : contexte radicalement différent. En Section C, la Stratégie B
bénéficiait du cash-flow déjà établi par une flotte alimentée par le
signal principal (un petit compte de plus, profit marginal positif). Ici
elle doit à elle seule financer la croissance structurelle des 5 firms
— sa fréquence de signal bien plus faible (311 vs 721 trades sur la
même période 4,5 ans) ne suffit pas à soutenir ce rythme de croissance.
**Conclusion : Stratégie B n'est PAS un moteur de croissance robuste en
autonomie complète — seulement un diversificateur marginal en
complément du signal principal établi.**

**Implication directe pour le chantier dual-trader (§2.50-2.53)** : dans
les configs 3/4, T2 (piloté par Stratégie B) a sa propre mini-flotte
5-firms qui, isolée, échouerait dans ~77% des cas en année 1. Ça
n'invalide PAS les résultats déjà publiés (année1<0 y est mesuré sur le
profit COMBINÉ T1+T2, dominé par T1) — mais ça confirme et explique
pourquoi T2 a si souvent besoin d'être refinancé par la réserve de T1
dans le mécanisme déjà illustré (run 67, §2.52) : Stratégie B seule est
structurellement fragile, ce qui rend le pooling de réserve (config 4)
encore plus justifié comme mécanisme de sauvetage plutôt qu'un luxe
optionnel. Fichier : `strategy_b_isolation_confirm_2026-08-12.py`,
résultats `strategy_b_isolation_n600.csv` (non versionné).

### 2.56 Architecture infra — relais de signal VPS1→VPS2 (analyse, 08/12)

Analyse demandée avant tout contact support prop firm. Contexte vérifié
dans le code : l'incident du 29/07 (`app.py:570-590`) était causé par
des requêtes CONCURRENTES vers la même fiche CentralCharts (protection
anti-bot Cloudflare 403/429), pas par la fréquence de scraping — déjà
corrigé côté VPS1 par un verrou mono-instance. Pipeline réel : poll
mail toutes les 60s (`app.py:661`) → fetch détail CentralCharts (délai
crawl 3s, `scraper.py:11`) → parse → exécution.

**Mécanisme recommandé : webhook HTTP** (VPS1 `POST` vers VPS2), avec
log local d'attente sur VPS1 (append-only, marqué livré après succès)
et retry court (2-3 tentatives, timeout 5-10s). Préféré à une file
partagée (mauvais fit, 2 VPS séparés) et à une queue dédiée (overkill
pour ce volume) — cohérent avec la stack Python existante.

**Repli sur point de défaillance unique** : un simple "pas de signal
depuis X min" est un MAUVAIS détecteur (signaux naturellement espacés
de plusieurs jours, 721 sur 4,5 ans). Design recommandé : heartbeat
séparé du flux de signal (5-10 min), VPS2 bascule en scraping de
secours après 2-3 battements manqués (~15-20 min), avec notification
Telegram explicite (réutilise `notifier_telegram_async`, déjà en place,
non-bloquant). Hystérésis au retour de VPS1 (2 heartbeats consécutifs
avant de relâcher) pour éviter le flapping et recréer l'incident du
29/07 par la bascule elle-même.

**Latence** : fichier de l'analyse nocturne du 31/07 référencé par
l'utilisateur NON RETROUVÉ dans le dépôt malgré recherche — chiffre non
cité pour ne pas fabriquer une référence non vérifiée. Estimation à
partir des constantes de code mesurables : le pipeline actuel a déjà
une latence dominante de jusqu'à 60s (poll mail) + quelques secondes
(fetch CentralCharts) ; un webhook ajoute un aller réseau simple,
typiquement sub-seconde entre 2 VPS correctement provisionnés —
négligeable face à l'existant. `slippage_logger.py` mesure déjà la
latence email→exécution en conditions réelles si une mesure fraîche est
nécessaire.

### 2.57 Décomposition directionnelle du mécanisme de sauvetage config 4 (08/12)

n=600, mêmes runs que la confirmation §2.53 (même seed 9999) —
`dual_trader_config4_decomposition_2026-08-12.py`, rejoue séparée vs
commune sur les MÊMES tirages de marché (T1 et T2 appariés), puis rejoue
avec journal complet les runs "sauvetage" pour déterminer quel trader a
déclenché `hit_ceiling_touche` sous réserves séparées.

**Fréquence et sens du sauvetage :**

| Plafond | Sauvetages (séparée casse, commune sauve) | Sens inverse | T1 sauvé | T2 sauvé |
|---|---|---|---|---|
| 1000$ | 66/600 (11,00%) | 1/600 (0,17%) | 20 (30,3%) | **46 (69,7%)** |
| 3000$ | 7/600 (1,17%) | 2/600 (0,33%) | **6 (85,7%)** | 1 (14,3%) |

**Le sens du sauvetage s'inverse selon le plafond** — à 1000$ (budget
serré), T2 (Stratégie B, fragile en isolation, §2.55) est le plus
souvent sauvé ; à 3000$ (sauvetages rares), c'est T1 (croissance plus
rapide, coûts de réouverture plus élevés) qui est le plus souvent sauvé
par la réserve dormante de T2.

**Décomposition du profit combiné (net d'impôt) :**

| Plafond | T1 séparée | T1 commune | Δ pooling T1 | T2 séparée | T2 commune | Δ pooling T2 | Réf. T1 solo |
|---|---|---|---|---|---|---|---|
| 1000$ | 5 378 709$ | 5 376 808$ | -1 902$ | 468 965$ | 608 903$ | +139 938$ | 5 588 407$ |
| 3000$ | 5 525 726$ | 5 471 163$ | -54 563$ | 475 134$ | 613 051$ | +137 917$ | 5 657 334$ |

**Réponse à la question posée** : T1 ne gagne PAS de son association avec
T2 — il perd légèrement, dans les DEUX architectures (T1 commune ET T1
séparée sont tous deux inférieurs à la référence solo, -3,29%/-3,79%
resp. -2,33%/-3,75%). Cette perte vient presque entièrement du **plafond
personnel partagé** (actif dans les 2 architectures) — pas du pooling de
réserve lui-même (Δ pooling T1 marginal, -1 902$ à -54 563$). **Toute la
valeur de config 4 par rapport à "T1 seul" vient de la contribution
PROPRE de T2** (608 903$/613 051$), pas d'un gain net de T1. T1 accepte
une perte marginale sur son profit moyen en échange d'une protection
contre les cas catastrophiques (85,7% des sauvetages à 3000$ sont pour
lui) — une logique d'assurance, pas un gain en espérance.

⚠️ **Bug méthodologique trouvé et corrigé en cours de route** : la
première passe de ce calcul oubliait de soustraire l'impôt (`is_paid_
cum`) par trader — trouvé en recoupant contre le total déjà publié en
§2.53 (écart ~30%, trop gros pour être du bruit). Le comptage sauvetage/
direction (basé sur les flags `hit_ceiling`, pas sur les montants)
n'était pas affecté et n'a pas eu besoin d'être refait.

### 2.58 Balayage du risque par trade — Stratégie B isolée (08/12)

n=300, plafond 3000$, un axe à la fois (funded fixe à la référence
pendant le sweep éval et vice-versa), GFT eval_risk fixe à 1,75%
(calibrage indépendant) — `strategy_b_risk_sweep_2026-08-12.py`.

| Axe | Valeur | Profit moyen | solde_neg_an4 | hit_ceiling | Année1<0 |
|---|---|---|---|---|---|
| Éval | 0,75% | 518 319$ | 32,33% | 0,00% | 81,67% |
| Éval | 1,00% | 606 250$ | 25,67% | 0,00% | 78,00% |
| Éval | **1,25% (réf A)** | 670 404$ | 23,33% | 0,67% | 76,67% |
| Éval | **1,75%** | **717 704$** | **20,67%** | 0,33% | **76,33%** |
| Éval | 2,25% | 700 320$ | 22,67% | 5,67% | 78,33% |
| Funded | 1,00% | 337 325$ | 23,33% | 0,00% | 83,67% |
| Funded | 1,40% | 485 710$ | 22,67% | 0,00% | 79,67% |
| Funded | **1,90% (réf A)** | 670 404$ | 23,33% | 0,67% | 76,67% |
| Funded | 2,40% | 688 935$ | 24,67% | 1,67% | 76,00% |
| Funded | 2,90% | 605 339$ | 26,00% | 2,00% | 74,33% |

**Éval=1,75% domine la référence 1,25%** sur profit (+7,1%), solde_neg,
hit_ceiling et année1<0 — un vrai optimum différent pour Stratégie B.
**Funded reste optimal à 1,90%** dans la plage testée (2,40%/2,90%
dégradent le risque pour un gain marginal ou négatif).

**Retest config 4 dual-trader avec T2 à eval=1,75% (T1 inchangé
1,25%/1,90%), n=300, deux plafonds** — `dual_trader_config4_t2_risk_
optimized_2026-08-12.py` :

| Plafond | Config | Profit moyen | solde_neg | hit_ceiling | Année1<0 |
|---|---|---|---|---|---|
| 1000$ | Baseline (T2 eval=1,25%) | 6 108 417$ | 0,67% | 4,33% | 29,33% |
| 1000$ | T2 eval=1,75% | 6 118 473$ | 0,33% | **6,00% (pire)** | 29,00% |
| 3000$ | Baseline | 6 190 208$ | 0,00% | 0,00% | 27,33% |
| 3000$ | T2 eval=1,75% | 6 195 308$ | 0,00% | 0,00% | 26,00% |

**Résultat mitigé, pas de gain structurel net.** À 3000$, léger mieux
(année1<0 -1,33pt). À 1000$, dégrade le mécanisme de sauvetage lui-même
(hit_ceiling +1,67pt) — un risque T2 plus élevé consomme sa part du
plafond personnel partagé plus vite, réduisant la marge disponible pour
protéger T1. **Pas de recommandation d'adoption** — effet trop faible
et non uniforme entre les 2 plafonds.

### 2.59 🔴 Chantier cluster Blueberry 1,5% — clarification + 3 options A/B/C lancées (08/12, reprise après interruption)

**Clarification (avant tout code) :** confirmation utilisateur — le compte
Blueberry réellement souscrit en live est le **"2-Step Challenge" standard**
(10%/5%, DD 5%/10%), **PAS Prime**, et la règle de budget de risque cluster
FX Majors (toutes les positions FX Majors simultanées sur un même compte
partagent un seul budget de risque de 1,5%, jamais 1,5% par position)
**s'applique spécifiquement à Standard, PAS à Prime**.

**🔴 Découverte majeure en reprenant le chantier** : `CONFIG_REF`
(`etape_e_fleet_integration.py:123-125`), utilisé par TOUTE la référence
officielle du projet (§1.8, Run C/Run F), utilise `Blueberry_Prime2Step`
depuis l'Étape E (08/09) — **la référence officielle actuelle simule donc le
mauvais produit Blueberry** (Prime, moins cher, jamais soumis au cluster) au
lieu du produit réellement tradé (Standard, soumis au cluster). Ce n'est pas
un bug de calcul mais un choix de modélisation jamais confronté au compte
réel — même famille de problème que les autres corrections de format déjà
faites dans ce chantier (FundedNext, Fivers).

**Prix vérifiés par recherche web (08/12)** :
- Prime 25k$ : **165$ régulier / 99$ promo tierce** (propfirmmatch.com,
  code MATCH -30%) — confirme EXACTEMENT le prix déjà codé et sa note de
  confiance. Rien à corriger côté Prime.
- Standard 25k$ : **170$** (tradingpilot.com, table complète cohérente
  5K=48$/10K=70$/25K=170$/50K=315$/100K=620$/200K=1240$) — remplace le
  `None` précédent dans `engine_multiformat.py:125` (`FORMATS["Blueberry_
  2StepStandard"]`), jamais sourcé jusqu'ici.

**Contrainte de faisabilité levier 1:30 (retrouvée, session antérieure
`contexte_projet_lutessia_2026-08-05.md`)** : déjà modélisée génériquement
dans `scaling_simulation.feasible_risk_pct()`, branchée sur CHAQUE trade
dans `engine_multiformat.py:323` — PAS spécifique à Blueberry, s'applique à
tous les comptes/firms via `forex_market_data.json` (`margin_per_lot`,
levier implicite ~1:30-1:33 cohérent avec la source). `lotcap_feasibility_
check.py` a déjà mesuré cette contrainte comme marginale jusqu'à 500 000$
de palier. Le cap Blueberry réel confirmé (décision #6 §4) est **400 000$
agrégé** (pas 2M$, l'ancienne ambiguïté "2M$ cumulé vs par compte" citée
dans le handoff 08/12 est l'ambiguïté déjà résolue par le contact support
08/10) — donc cette contrainte ne devient jamais bloquante pour Blueberry.
**Point fermé, aucun retest nécessaire.**

**3 options construites (`blueberry_cluster_options_2026-08-12.py`, copie
étendue du moteur officiel `etape_ai_payout_cadence_calibration_2026-08-11
.py` — V2 DD-distance, FTMO -10%, GFT Goat Guard, payout cycle, pop 721,
seed=9999, TOUS actifs comme dans Run C ; PAS Run F/BB-7j, pour isoler ce
chantier du levier retrait-rapide déjà tranché séparément)** :
- **Option A (bascule réelle vers Prime)** : mécaniquement IDENTIQUE à
  `CONFIG_REF` actuel (déjà Prime). **Pas ré-exécutée** — réutilise
  directement les chiffres Run C déjà produits n=600+cascade (§1.8) :
  1000$ = 5 491 410$/1,50%/3,50%/35,50% ; 3000$ = 5 542 103$/0,17%/1,33%/
  35,33%.
- **Option B (rester Standard, modéliser le vrai cluster)** : nouveau —
  `Blueberry_2StepStandard` + limiteur de risque cluster FX Majors (budget
  partagé 1,5%, tracking parallèle à `acc["open_positions"]` sans toucher
  au moteur partagé `process_trade_mf`, 7 paires majeures USD).
- **Option C (retirer Blueberry, GFT reprend le rôle de starter jour 0)** :
  nouveau — flotte réduite à 4 firms, GFT confirmé moins cher des
  alternatives (50k=288$ vs FTMO 345$/Fivers 545$/FundedNext ~799$, déjà
  établi décision #19).

**Résultats n=300 (B et C), comparés à A (n=600 réutilisé) — 08/12,
`blueberry_cluster_options_n300.csv`** :

| Plafond | Option | Profit moyen/médian | solde_negatif_annee4 | hit_ceiling_pct | Année1<0 |
|---|---|---|---|---|---|
| 1000$ | **A — bascule Prime** | **5 491 410$/5 361 009$** | **1,50%** | **3,50%** | 35,50% |
| 1000$ | B — Standard + cluster | 5 013 556$/4 821 505$ | 6,67% | 13,00% | 34,33% |
| 1000$ | C — retrait BB (GFT starter) | 4 038 789$/4 052 009$ | 13,67% | 19,67% | **31,00%** |
| 3000$ | **A — bascule Prime** | **5 542 103$/5 368 386$** | 0,17% | 1,33% | 35,33% |
| 3000$ | B — Standard + cluster | 5 380 800$/5 055 332$ | **0,00%** | 0,67% | 32,00% |
| 3000$ | C — retrait BB (GFT starter) | 4 683 868$/4 411 533$ | 0,33% | 0,67% | **20,00%** |

**Verdict n=300 (screening, pas encore confirmé n=600)** : **Option A
domine ou égale B sur PROFIT/solde_neg/hit_ceiling aux deux plafonds** —
rester en Standard (B) coûte du profit (-8,7%/-2,9%) et dégrade solde_neg
et hit_ceiling aux deux plafonds, sans compenser sur année1<0 (gain marginal
seulement, -1,17pt/-3,33pt). Le mécanisme est cohérent : le cluster limite
concrètement le sizing FX Majors sur Standard, ET Standard coûte plus cher
à l'achat (170$ vs 165$, écart faible mais non nul), sans aucun bénéfice
compensatoire puisque Prime évite structurellement le problème plutôt que
de le mitiger. **A ne domine PAS B au sens strict** : à situation
équivalente, A reste supérieur sur 3 axes sur 4, mais année1<0 est
légèrement pire pour A aux deux plafonds — pas une dominance à 4 axes,
mais un écart net en faveur de A.

**Option C (retrait Blueberry) n'est PAS un choix par défaut malgré son
année1<0 remarquable à 3000$ (20,00%, -15,33pt vs A)** : coûte -15,5% de
profit à 3000$ (-26,5% à 1000$) et dégrade solde_neg/hit_ceiling à 1000$
(13,67%/19,67%, nettement pires que A et B) — un vrai arbitrage
profit-vs-risque, pas une amélioration gratuite, cohérent avec le refus
déjà établi de BB+FundedNext (décision #19, coût d'entrée élevé du starter
alternatif) même si GFT est moins cher que FundedNext.

**Recommandation de ce chantier (pas une décision automatique)** : si le
compte live PEUT réellement être basculé en Prime (vérification support
nécessaire — pas encore faite), **Option A est le choix le plus net** :
meilleur profit ET meilleur risque sur 3 axes sur 4 aux deux plafonds, sans
qu'aucun autre chantier n'ait identifié de contrepartie cachée à Prime
(DD journalier plus serré 4% vs 5%, mais jamais mesuré comme un problème
séparé — point non vérifié explicitement, à noter). Si la bascule est
impossible (ex. compte déjà en cours, condition contractuelle), **B reste
préférable à C** sauf si la réduction drastique d'année1<0 à 3000$ (C,
20,00%) est jugée prioritaire sur le profit par l'utilisateur — c'est un
vrai choix de profil de risque personnel, pas tranché ici.

**Point ouvert laissé pour une session future** : n=600+cascade check
requis avant toute adoption formelle (ce chantier n'est qu'un screening
n=300) ; si Option A est retenue, il faudra aussi vérifier auprès du
support Blueberry si un compte Standard déjà ouvert PEUT être basculé vers
Prime sans repasser par un nouveau challenge payant.

**✅ Confirmation n=600+cascade — Option A (08/12, plus tard)** : rejouée
avec `etape_ai_payout_cadence_calibration_2026-08-11.py` (= `CONFIG_REF`
inchangé = Option A par construction, seed=9999 identique), sous le moteur
`engine_multiformat.py` corrigé (prix Standard 170$ ajouté, prix Prime 165$
inchangé) :

| Plafond | Profit moyen/médian | solde_negatif_annee4 | hit_ceiling_pct | Année1<0 |
|---|---|---|---|---|
| 1000$ | 5 491 410$ / 5 361 009$ | 1,50% | 3,50% | 35,50% |
| 3000$ | 5 542 103$ / 5 368 386$ | 0,17% | 1,33% | 35,33% |

**Résultat STRICTEMENT IDENTIQUE, au chiffre près**, au résultat n=300
"Option A" du tableau ci-dessus (qui était déjà une réutilisation de ce
même Run C n=600 — pas une nouvelle simulation) et à la référence
historique Run C déjà verrouillée en §1.8. **Confirme que rien ne casse**
avec le prix Standard désormais présent dans `engine_multiformat.py` — la
correction n'affecte que le chemin de code `Blueberry_2StepStandard`,
jamais emprunté par Option A/Prime. Aucun nouveau chiffre découvert, comme
attendu (ce cascade check valide la non-régression du moteur, pas un
levier).

**Comparaison à Run F (référence officielle 3000$, BB-7j+surcoût, §1.8)** :
Run F = 5 589 954$/5 457 443$/0,33%/1,33%/32,83% à 3000$ — légèrement
meilleur que Option A pure sur profit (+0,86%) et année1<0 (-2,50pt) mais
pire sur solde_negatif_annee4 (0,33% vs 0,17%), cohérent avec l'arbitrage
déjà documenté du levier BB-7j (décision #16 §4) — les deux chantiers
restent orthogonaux : le choix Prime/Standard (ce chantier) et le choix de
cadence de retrait Blueberry 14j/7j (décision #16) peuvent en principe se
combiner, non testé conjointement ici (hors périmètre de ce chantier).

**✅ DÉCISION FINALE 08/12 (chantier cluster Blueberry 1,5% CLOS)** :
**Blueberry en format Prime pour tout compte futur de la flotte réelle**
(Option A adoptée) — confirmé par l'utilisateur comme choix retenu pour le
vrai lancement au palier 25k$, sans coût de transition puisqu'aucun compte
Standard réel de flotte n'a encore été ouvert. Le compte Standard 5k$
actuellement utilisé en live reste **un outil de collecte de données
séparé**, indépendant de cette décision de format — il ne sera PAS
concerné par le passage à Prime et continue tel quel. `CONFIG_REF`
(`etape_e_fleet_integration.py:123-125`) reste donc inchangé (`Blueberry
="Blueberry_Prime2Step"`) — ce n'était PAS une erreur à corriger dans le
code, seulement une hypothèse de modélisation qui s'avère être le bon choix
une fois la question posée explicitement. Options B (cluster sizing sur
Standard) et C (retrait Blueberry) restent documentées ci-dessus pour
mémoire mais ne sont plus des candidats actifs pour la flotte réelle.

**✅ Audit de fidélité Prime (08/12, plus tard) — 8/8 points confirmés
conformes, aucune correction, aucun relancement nécessaire** (vérification
demandée explicitement par l'utilisateur avant de considérer le chantier
définitivement clos) :
1. Cibles P1/P2 8%/6% — `engine_multiformat.py:117`.
2. DD journalier 4% — même ligne, ET activement enforcé (`daily_broke`,
   `engine_multiformat.py:349-352`), pas un champ mort.
3. DD max 10% statique — même ligne.
4. Levier ~1:23-1:34 confirmé par calcul sur `forex_market_data.json`
   (nulle part proche de 1:50), contrainte de faisabilité recalculée par
   trade avec le `palier` courant (`engine_multiformat.py:323`). Le
   "jusqu'à 2M$ de scaling" évoqué au lancement du chantier ne s'applique
   PAS : `etape_e_fleet_integration.py` n'a AUCUNE croissance individuelle
   de palier (confirmé code, docstring point 1) — palier Blueberry
   individuel max réel = 50 000$ (compte extra, taille fixe), très
   en-dessous des 500 000$ déjà validés marginaux (`lotcap_feasibility_
   check.py`).
5. Split 80% — `engine_multiformat.py:315/344`, seule exception codée =
   GFT sous Goat Guard, jamais Blueberry.
6. Min. 5 jours actifs par phase — enforcé comme gate réel de progression
   (`engine_multiformat.py:375-377`), pas décoratif. Nuance non modélisée
   (≥0,5% profit/jour, pas juste 1 trade) déjà connue, pas une erreur
   nouvelle.
7. Prix 165$@25k — `engine_multiformat.py:118`, confirmé exact.
8. Aucune limite cluster FX Majors dans Run C/F ni dans `dual_trader_2026-
   08-11.py` (`CONFIG_REF` réutilisé identiquement, sa fonction
   `clustering_pct()` mesure la coïncidence de casses même jour — sans
   rapport avec un plafond de risque par paire). Le limiteur cluster écrit
   pour l'Option B (`blueberry_cluster_options_2026-08-12.py`) est gardé
   par un test de format explicite, jamais atteint quand Blueberry=Prime.

**Chantier cluster Blueberry 1,5% définitivement clos.**

### 2.60 ✅ *(RECONFIRMÉ n=600+cascade, 08/12)* Règle d'exclusion JPY-JPY — JUSTIFIÉE EMPIRIQUEMENT, pas juste "prudence structurelle"

Contexte : la règle (`is_jpy(a) and is_jpy(b)` dans `monte_carlo_simulation.
precompute_correlation_pairs`, `scaling_simulation.py`) interdit deux
positions JPY DIFFÉRENTES simultanées sur un même compte, indépendamment de
leur corrélation mesurée. Justification d'origine : le cas concret AUD/JPY-
USD/JPY affichait 8,81% de DD flottant combiné, corrigé à une valeur plus
faible après le fix du bug de fenêtre calendaire de `build_trade_day_
excursions` (`daily_dd_pair_analysis.py`, session_summary_2026-08-01.md
§1.3). Jamais retestée sous la population 721/config actuelle.

**Volet A — diagnostic historique direct** (`chantier1_jpy_rule_test_2026-
08-12.py`, réutilise `build_trade_day_excursions`/`analyze_pairs` de
`daily_dd_pair_analysis.py` sur la population ACTUELLE 721 trades, corrigée
— l'ancien defaut du fichier, `historique_lutessia.csv`/MIN_RR=2.0/68
trades, est bien trop stale et n'a pas été réutilisé) : max DD flottant
combiné observé sur les 10 duos JPY-JPY = **1,53%** — loin des 8,81%
d'origine, mais pas nul (`chantier1_jpy_excursion_duos.csv`).

**Volet B — simulation flotte n=600+cascade** (moteur officiel Run C =
Option A/Prime) :

| Plafond | Config | Profit moyen/médian | solde_negatif_annee4 | hit_ceiling_pct | Année1<0 |
|---|---|---|---|---|---|
| 1000$ | **AVEC règle (réf)** | **5 491 410$/5 361 009$** | **1,50%** | **3,50%** | 35,50% |
| 1000$ | SANS règle | 5 340 076$/5 285 884$ | 2,33% | 4,83% | 34,17% |
| 3000$ | **AVEC règle (réf)** | **5 542 103$/5 368 386$** | **0,17%** | **1,33%** | 35,33% |
| 3000$ | SANS règle | 5 414 050$/5 297 326$ | 0,83% | 1,17% | 33,83% |

**Verdict : garder la règle.** AVEC domine SANS sur profit (+2,8%/+2,4%) et
solde_negatif_annee4 aux deux plafonds ; hit_ceiling légèrement pire à 1000$
sans elle, légèrement mieux à 3000$ (bruit, pas un signal net) ; seul
année1<0 s'améliore marginalement sans la règle (-1,3pt/-1,5pt), pas assez
pour compenser. **Limite explicite du volet B** : le moteur flotte ne
modélise que des résultats R discrets par trade (pas de prix flottant intra-
trade), donc il mesure l'effet BUSINESS d'admettre plus de trades JPY-JPY
simultanés, pas un vrai DD flottant simulé — seul le volet A le peut.
`jpy_concurrent_events_moy` confirme le mécanisme : 0 événement croisé
JPY-JPY réel avec la règle active (comme attendu), ~290-295/run sans elle.
**Règle CONFIRMÉE, adoptée avec justification empirique fraîche** — plus
seulement "par prudence". Condition de réouverture : nouvelle mesure du DD
flottant JPY-JPY si la population change significativement (nouveau lot de
trades JPY).

### 2.61 🟡 *(CANDIDAT n=300, 08/12)* Seuil de corrélation inter-positions — 0,8 domine 0,6 sur les 4 axes

`CORR_TH=0.6` (`point_liquidity_rules.py:34`) jamais balayé en tant que
paramètre isolé. Balayage {0,4/0,5/0,6 réf/0,7/0,8}, n=300, moteur flotte
officiel (Option A/Prime, config Run C), règle JPY-JPY inchangée (active,
question orthogonale) — `chantier1_corr_threshold_sweep_2026-08-12.py` :

| Plafond | Seuil | Profit moyen/médian | solde_negatif_annee4 | hit_ceiling_pct | Année1<0 |
|---|---|---|---|---|---|
| 1000$ | 0,4 | 5 682 181$/5 412 701$ | 1,67% | 3,33% | 35,00% |
| 1000$ | 0,5 | 5 254 612$/5 033 783$ | 2,00% | 5,00% | 35,67% |
| 1000$ | **0,6 (réf)** | **5 588 381$/5 336 808$** | **1,33%** | **3,33%** | **32,67%** |
| 1000$ | 0,7 | 5 603 098$/5 263 231$ | 1,00% | 2,33% | 32,33% |
| 1000$ | **0,8** | **5 724 300$/5 446 256$** | **1,33%** | **2,67%** | **32,67%** |
| 3000$ | 0,4 | 5 753 219$/5 470 959$ | 0,33% | 0,67% | 35,00% |
| 3000$ | 0,5 | 5 321 352$/5 084 415$ | 0,33% | 1,33% | 35,33% |
| 3000$ | **0,6 (réf)** | **5 629 882$/5 361 131$** | **0,33%** | **1,67%** | **32,67%** |
| 3000$ | 0,7 | 5 637 560$/5 263 231$ | 0,00% | 0,00% | 32,33% |
| 3000$ | **0,8** | **5 771 194$/5 446 256$** | **0,00%** | **0,00%** | **32,33%** |

**0,8 domine ou égale 0,6 sur les 4 axes aux deux plafonds** (profit
+2,4%/+2,5%, solde_neg identique/meilleur, hit_ceiling meilleur, année1<0
identique/meilleur) — mécanisme cohérent : un seuil plus lâche admet plus
de trades (moins d'exclusions par corrélation), sans dégrader le risque
mesuré sur cette grille. 0,7 domine aussi 0,6 mais avec une marge plus
faible. 0,4/0,5 sont nettement pires (0,5 en particulier, -6,0%/-5,5%
profit) — un seuil trop strict coûte du volume sans bénéfice de risque net.
**N'est PAS monotone au sens strict** (0,7 < 0,8 en profit, mais 0,5 < 0,4
< 0,6 — pas une simple fonction croissante du seuil), donc pas justifié
d'extrapoler au-delà de 0,8 sans le tester explicitement. **n=600+cascade
requis avant adoption** (standard du projet), candidat prioritaire =
seuil 0,8. Point ouvert : interaction non testée avec le levier RR
(§2.8bis de `registre_strategie_trading.md`, candidat 1,35) — les deux
leviers touchent le même mécanisme (volume de trades admis), effet combiné
inconnu.

### 2.62 ✅ *(CONFIRMÉ n=600+cascade, GO — 08/12)* Confirmation combinée RR≥1,35 + corrélation 0,80

**Étape A — redensification du seuil de corrélation SOUS RR≥1,35** (pas
1,25, pour éviter de choisir le seuil sur la mauvaise base), n=300,
{0,60/0,65/0,70/0,75/0,80/0,85} — `chantier1_corr_under_rr135_2026-08-12
.py` : pattern globalement croissant de 0,70 à 0,85 (0,75 et 0,80
STRICTEMENT IDENTIQUES — aucune paire de corrélation mesurée entre ces deux
bornes, matrice discrète), un seul creux isolé à 0,65 (sous la référence
0,60) — traité comme un point de bruit isolé, pas un pattern non-monotone
généralisé (contrairement à la crainte initiale). **0,80 retenu** :
meilleur compromis — 0,85 gagne un peu plus de profit (+0,2% vs 0,80) mais
coûte +1,0pt de hit_ceiling à 1000$ (2,67% vs 2,00%), non justifié pour un
gain marginal.

**Étape B — confirmation n=600, 4 scénarios isolés au même niveau de
confiance** (`chantier1_combined_confirm_n600_2026-08-12.py`, moteur
officiel Option A/Prime, config Run C) :

| Plafond | Config | Profit moyen/médian | solde_negatif_annee4 | hit_ceiling_pct | Année1<0 |
|---|---|---|---|---|---|
| 1000$ | **Référence (RR1,25+corr0,60)** | 5 491 410$/5 361 009$ | 1,50% | 3,50% | 35,50% |
| 1000$ | RR1,35 seul (corr0,60) | 5 710 066$/5 652 458$ | 0,50% | 1,83% | 33,17% |
| 1000$ | Corr0,80 seul (rr1,25) | 5 660 833$/5 504 145$ | 1,33% | 2,83% | 33,67% |
| 1000$ | **Combiné (rr1,35+corr0,80)** | **5 836 643$/5 621 512$** | 0,50% | **1,50%** | **30,50%** |
| 3000$ | **Référence** | 5 542 103$/5 368 386$ | 0,17% | 1,33% | 35,33% |
| 3000$ | RR1,35 seul | 5 717 829$/5 652 458$ | 0,33% | 0,83% | 33,17% |
| 3000$ | Corr0,80 seul | 5 707 393$/5 504 145$ | 0,00% | 0,50% | 33,33% |
| 3000$ | **Combiné** | **5 847 908$/5 621 512$** | 0,33% | **0,67%** | **30,50%** |

**Additivité mesurée (combiné vs somme naïve des 2 effets isolés, delta vs
référence)** : **profit/solde_negatif_annee4/hit_ceiling_pct SOUS-additifs**
(effet combiné legèrement inférieur à la somme des effets isolés — profit
observé +6,29%/+5,52% vs +7,07%/+6,15% en additivité naïve, chevauchement
attendu puisque les deux leviers agissent sur le même mécanisme, admission
de trades) ; **année1<0 SUPER-additif** (-5,00pt/-4,83pt observé vs
-4,16pt/-4,16pt en additivité naïve — les deux leviers se renforcent
spécifiquement sur cet axe, mécanisme non creusé plus loin).

**Verdict : combiné domine strictement la référence sur les 4 axes à
1000$, et sur 3/4 à 3000$** (solde_negatif_annee4 marginalement pire,
+0,16pt, sur ~1 run/600 — dans le bruit, pas un signal). Profit
+6,3%/+5,5%, année1<0 -5,0pt/-4,8pt aux deux plafonds. **Standard "GO" du
projet atteint** (dominance 3+ axes aux 2 plafonds). **✅ ADOPTÉ 08/12
(cascade complète §2.63)** — `min_rr=1.25→1.35` et `CORR_TH=0.6→0.80`
désormais la référence officielle §1.8.

### 2.63 ✅ *(CASCADE COMPLÈTE 08/12)* Adoption RR≥1,35 + corrélation 0,80 — régénération de toute la chaîne dépendante

Suite à la cartographie des dépendances (§4#36 devenu obsolète, remplacé
par cette section), 4 sections traitées dans l'ordre, chacune dépendant de
la précédente. Piste 1 (fonds d'urgence) explicitement LAISSÉE TELLE
QUELLE — candidat jamais adopté, hors périmètre de cette cascade, sera
rafraîchi séparément si ce chantier reprend.

**Section 0 — zone morte T1/T2 résolue** (`dual_trader_2026-08-11.py`) :
la borne haute de la bande contrarian T2 était un littéral dupliqué
indépendant de T1 (1,25 codé séparément aux deux endroits) — élargie à
0,75≤rr_tp1<1,35 via une constante **`MIN_RR_T1=1.35` désormais partagée**
entre le filtre T1 et la bande T2 (`CONTRARIAN_BAND_LOW=0.75` documentée
séparément), pour que tout futur changement de seuil RR ne recrée pas le
même risque de zone morte. Revérification solo (`chantier1_strategyb_
band_check_2026-08-12.py`) : ancienne bande n=311/EV=+0,7809R, nouvelle
bande n=401/EV=+0,8005R — **pas de dilution, les 90 trades récupérés de
l'ancienne zone morte ont même une EV plus élevée (+0,8684R)**. Feu vert
pour la suite.

**Section 1 — référence officielle régénérée** (`etape_aq_run_c_rr135_
corr080_2026-08-12.py` / `etape_ar_run_f_rr135_corr080_2026-08-12.py`,
copies exactes de `etape_ai`/`etape_ao`, seuls `min_rr`/`CORR_TH` changés) :
voir tableau et verdict en tête de §1.8. **Domine strictement l'ancienne
référence sur les 4 axes aux deux plafonds.**

**Section 2 — config 1 / config 4 dual-trader régénérées**, n=600+cascade,
mêmes 2 plafonds (`dual_trader_2026-08-11.py` mode `confirm`, hérite
automatiquement de `MIN_RR_T1`/`CORR_TH_ADOPTED` de la Section 0) :

| Config | Plafond | Profit moyen/médian | solde_negatif_annee4 | hit_ceiling_pct | Année1<0 |
|---|---|---|---|---|---|
| 1. Même stratégie, séparé | 1000$ | **10 445 044$/10 128 616$** | 1,67% | **7,83%** | 30,33% |
| 4. A/B, réserve commune | 1000$ | **6 811 102$/6 683 913$** | 0,17% | 2,33% | 24,67% |
| 1. Même stratégie, séparé | 3000$ | **10 663 273$/10 209 581$** | 0,33% | 0,33% | 27,83% |
| 4. A/B, réserve commune | 3000$ | **6 875 909$/6 754 315$** | 0,00% | 0,00% | 22,50% |

**Les 4 configs dominent strictement leurs anciennes valeurs n=600 (§2.53)
sur les 4 axes.** 🔴 **Changement de conclusion, pas juste de chiffres** :
Config 1@1000$, jusqu'ici "confirmée trop risquée, hors jeu" (hit_ceiling
23,50% sous l'ancienne base), tombe à **hit_ceiling=7,83%** sous la
nouvelle — toujours plus risqué que Config 4@1000$ (2,33%), mais son statut
de "hors jeu" n'est plus automatique. Ne rouvre pas le choix profit-max vs
risque-quasi-nul (toujours laissé à l'utilisateur), mais élargit
concrètement les options disponibles à 1000$.

**Décomposition directionnelle refaite** (`dual_trader_config4_
decomposition_2026-08-12.py`, référence solo T1 mise à jour avec les vrais
n=600 Section 1 : 5 836 643$/1000$, 5 900 859$/3000$) :

| Plafond | Runs sauvetage | Direction (T1 sauvé / T2 sauvé) | Δ pooling T1 | Δ pooling T2 | T1 commune vs solo |
|---|---|---|---|---|---|
| 1000$ | 31/600 (5,17%) | 29,0% / 71,0% | -18 385$ | **+162 176$** | -2,93% |
| 3000$ | 4/600 (0,67%) | 50,0% / 50,0% (n trop petit) | -43 612$ | **+151 336$** | -2,91% |

**Mécanisme CONFIRMÉ intact** : à 1000$, T2 sauve T1 71,0% du temps —
quasi identique à l'ancien 69,7% (§2.57), robuste au changement de base.
**T2 continue d'apporter une contribution nette positive et non
négligeable** (+151-162k$ de gain de pooling, pas un rôle d'assurance à
coût nul), tandis que T1 reste légèrement pénalisé par le plafond partagé
(-2,9% vs solo aux deux plafonds, quasi identique à l'ancien -3%). **À
3000$, l'échantillon de sauvetage est trop petit (n=4) pour confirmer ou
infirmer l'ancienne asymétrie directionnelle (85,7% T1 sauvé)** — signalé
explicitement comme non concluant, PAS traité comme un renversement.

**Section 3 — Blueberry Prime (Option A/B/C) rafraîchie**
(`blueberry_cluster_options_rr135_corr080_2026-08-12.py` pour B/C, Option A
= réutilisation directe des chiffres Run C Section 1, convention "Run C
style aux deux plafonds" inchangée pour ce chantier isolé) :

| Plafond | Option | Profit moyen/médian | solde_negatif_annee4 | hit_ceiling_pct | Année1<0 |
|---|---|---|---|---|---|
| 1000$ | **A — Prime** | **5 836 643$/5 621 512$** | **0,50%** | **1,50%** | 30,50% |
| 1000$ | B — Standard+cluster | 5 610 493$/5 375 657$ | 1,67% | 5,00% | 30,67% |
| 1000$ | C — retrait BB | 4 605 992$/4 480 966$ | 7,67% | 17,00% | **23,00%** |
| 3000$ | **A — Prime** | **5 847 908$/5 621 512$** | 0,33% | 0,67% | 30,50% |
| 3000$ | B — Standard+cluster | 5 722 598$/5 437 853$ | 0,33% | 0,67% | 29,67% |
| 3000$ | C — retrait BB | 4 927 268$/4 588 981$ | **0,00%** | **0,33%** | **19,33%** |

**✅ Verdict qualitatif VÉRIFIÉ INCHANGÉ** : Option A domine toujours B sur
3/4 axes aux deux plafonds (profit, solde_neg, hit_ceiling), exactement le
même schéma qu'avant la cascade (§2.59). Option C garde son profil
distinct (meilleur année1<0, nettement moins de profit) — même arbitrage
qu'avant. Aucun changement de conclusion sur ce chantier, seulement des
chiffres absolus plus élevés partout.

**Bilan cascade** : 4/4 sections traitées, aucune contradiction ni
inversion de dominance détectée sauf le changement de statut de Config
1@1000$ (signalé explicitement ci-dessus). Piste 1 non concernée, laissée
en l'état.

### 2.64 ✅ *(CONFIRMÉ n=300, 08/12)* Décision rank-and-rent — 40$ vers un fonds de sécurité 5-10k$

Trois volets, sous la référence post-cascade (RR≥1,35/corr 0,80).

**Section 1 — vrai palier optimal** (`chantier_ceiling_sweep_2026-08-12
.py`, balayage {960/1000/2000/3000/5000/7500/10000}$, BB7j généralisé en
`ceiling>=3000` comme Section D de `structure_pistes_2026-08-11.py`,
ancien balayage §2.48 obsolète car RR1,25/corr0,6) :

| Plafond | Profit moyen | solde_negatif_annee4 | hit_ceiling_pct | Année1<0 |
|---|---|---|---|---|
| 960$ | 5 914 410$ | 0,33% | 3,33% | 28,00% |
| 1000$ | 5 915 946$ | 0,33% | 2,00% | 28,00% |
| 2000$ | 5 917 925$ | 0,33% | 1,00% | 28,00% |
| 3000$ | 5 969 019$ | 0,33% | 0,67% | 26,67% |
| **5000$** | **5 986 943$** | **0,00%** | 0,67% | 26,67% |
| 7500$ | 5 987 075$ | 0,00% | 0,33% | 26,67% |
| 10000$ | 5 987 006$ | 0,00% | 0,33% | 26,67% |

**5000$ est le vrai plateau** : profit et solde_negatif_annee4 cessent de
bouger exactement à ce palier (5 986 943$ vs 5 987 075$ à 7500$, delta
0,002% = bruit ; solde_neg atteint son plancher 0,00%). Au-delà, seul
hit_ceiling continue de baisser marginalement (0,67%→0,33%), sans gain de
profit — pas justifié de viser plus que 5000$ sur cette seule base. Cible
= bas de la fourchette personnelle visée (5-10k$), pas un chiffre rond.

**Section 2 — coût de 960$ vs 1000$** : profit -1 536$ (-0,03%,
négligeable), solde_negatif_annee4 et année1<0 identiques. **Seul
hit_ceiling bouge réellement** (2,00%→3,33%, +1,33pt, relatif +67%) — pas
totalement nul, mais un coût mineur au vu de la marge sur les autres axes.

**Section 3 — attendre vs démarrer maintenant** (`chantier_rank_and_rent_
2026-08-12.py`, capacités nouvelles : `ceiling_schedule` pour la bascule de
plafond sans nouvel apport personnel au-delà du saut lui-même, `start_
delay_seconds` pour le report d'activité avec horizon actif réduit
d'autant — PAS un horizon de 4 ans gelé artificiellement) :

| Délai | A — Attendre | B — Rester à 960$ | C — Démarrer puis basculer |
|---|---|---|---|
| 3 mois | 5 411 019$ (hc 0,67%) | 5 914 410$ (hc 3,33%) | **5 961 711$ (hc 1,00%)** |
| 6 mois | 5 098 249$ (hc 0,00%) | 5 914 410$ (hc 3,33%) | **5 966 019$ (hc 2,33%)** |
| 9 mois | 4 771 393$ (hc 0,33%) | 5 914 410$ (hc 3,33%) | **5 940 064$ (hc 2,67%)** |
| 12 mois | 4 293 739$ (hc 0,33%) | 5 914 410$ (hc 3,33%) | **5 935 196$ (hc 3,00%)** |

**Verdict net : A ne rattrape JAMAIS C ni même B dans toute la plage
testée (3-12 mois) — aucun point de bascule trouvé.** Le profit de A
décroît quasi linéairement avec le délai (temps de trading pur perdu,
non récupérable), tandis que C reste quasi plat. A est même dominé par B
(rester à 960$ pour toujours, sans jamais toucher au rank-and-rent) dès 3
mois. **Démarrer maintenant à 960$ domine dans tous les scénarios
testés — attendre n'est jamais la bonne option dans ce modèle.**

**Conclusion globale** : retirer 40$ du filet de sécurité coûte quasi rien
(-0,03% profit, +1,33pt hit_ceiling — mineur), et attendre le rank-and-rent
avant de démarrer coûte cher et croissant avec le délai. Démarrer
maintenant à 960$ puis basculer à 5000$ dès que le rank-and-rent rapporte
domine toutes les alternatives testées.

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
16. ✅ *(RÉSOLU 08/11 session c — Adopté CONDITIONNELLEMENT, pas une
    adoption pure et simple ni un rejet)* Décomposition délai/forfeiture
    (§2.34) + retrait rapide Blueberry 7j (§2.35) — Run A/B confirment le
    délai comme moteur dominant (+6,66pt vs +3,00pt sur 8,00pt). Run F
    (Blueberry 7j, coût réel +20%) testé n=600, cascade check 4 axes
    complet (§1.8) : améliore profit (+0,25%/+0,86%) et année1<0
    (-1,67pt/-2,50pt) aux deux plafonds, mais dégrade solde_negatif_
    annee4 (+0,83pt/+0,16pt) et hit_ceiling_pct (+2,33pt/0pt, quasi ×1,7
    à 1000$) — effet stable et reproductible entre n=300 et n=600 (pas du
    bruit), mécanisme identifié (surcoût +20% pèse sur le cash tendu au
    plafond 1000$, alors que la forfeiture Blueberry elle-même chute de
    ~89%, l'effet recherché fonctionne). Pas de dominance stricte sur les
    3 axes aux DEUX plafonds simultanément — **décision utilisateur
    explicite reçue 08/11 (session c, plus tard) : adoption
    CONDITIONNELLE au plafond.** Run F à 3000$ uniquement (hit_ceiling
    neutre, 0,00pt d'écart, à ce plafond — dominance de fait), Run C à
    1000$ (hit_ceiling ×1,7 non compensé par le gain profit/année1<0 à ce
    niveau de capital). La référence officielle du projet est désormais
    ASYMÉTRIQUE par plafond — voir le tableau récapitulatif en tête de
    §1.8. `etape_ao_run_f_cout_reel_2026-08-11.py` corrigé pour appliquer
    cette asymétrie automatiquement si réexécuté (§2.35bis) ; les
    chiffres n=600 déjà produits restent valides (mesurés plafond par
    plafond, pas besoin de relancer un calcul pour cette adoption).
17. 🟡 *(nouveau 08/11)* Piste 1 — fonds d'urgence réactif (§2.39) :
    REJETÉ à 1000$ (20% de skim fait exploser hit_ceiling ×2,2 à ×2,9 ;
    10% neutre à légèrement négatif, aucun gain). **Candidat n=300 à
    3000$** (10%/7j-ou-30j/N2 : profit +0,03% quasi gratuit,
    solde_negatif_annee4 et hit_ceiling_pct divisés par 2-2,5) — **n=600+
    cascade check requis avant toute adoption**, pas encore fait.
18. ✅ *(RÉSOLU/REJETÉ 08/11)* Piste 2 — sizing réduit post-casse,
    orthogonal à V2 (§2.40) : REJETÉ sur l'ensemble n=300 aux deux
    plafonds (coût de profit monotone, aucun gain net de risque). Nuance
    mesurée explicitement : un effet réel et reproductible existe sur les
    2 runs catastrophiques ciblés (+8 à +12% sur leur perte, durée courte
    5j) mais ne généralise pas — le coût sur les récupérations normales
    dépasse le gain concentré sur les clusters de casses rares. Fermé,
    pas de réouverture prévue sans nouveau signal.
19. ✅ *(RÉSOLU/REJETÉ 08/11)* Piste 3 — double starter (§2.41) : BB+GFT
    reconfirme le pattern déjà connu (§2.6/§2.11) sous la config
    actuelle, ne change rien à la décision #7 déjà ouverte (arbitrage
    3000$ non tranché, rejeté à 1000$). BB+FundedNext REJETÉ SANS
    AMBIGUÏTÉ aux deux plafonds — le coût d'entrée élevé (798,99$)
    domine le bon EV/$ théorique dans un rôle de capital de démarrage.
    Fermé.
20. ✅ *(RÉSOLU/REJETÉ 08/11)* Piste 4 — fongibilité inter-firm retestée
    sous la config actuelle (§2.42, principe de fraîcheur appliqué,
    rejet original de 08/10 datait d'avant cadence payout/population
    721) : RECONFIRMÉ sans aucun changement (effet nul aux deux
    plafonds). Fermé, même diagnostic qu'en 08/10 (réserve jamais
    scarce au bon moment pour que la priorité EV/$ tranche quoi que ce
    soit).
21. ✅ *(DIAGNOSTIC FAIT, PAS UNE ADOPTION 08/11)* Piste 5 — décorrélation
    du starter secondaire (§2.43) : identifie la corrélation copytrade,
    pas la liquidité en rafale, comme mécanisme DOMINANT du rejet de
    BB+GFT à 1000$ (la décorrélation seule récupère la quasi-totalité du
    dommage, dépasse même la référence solo sur profit et année1<0).
    Diagnostic pur — la décorrélation artificielle n'est pas actionnable
    en conditions réelles de copytrade. Point ouvert : une vraie piste
    de désynchronisation partielle (délai d'exécution, routage
    différent) pourrait être scopée si proposée un jour, informée par ce
    résultat.
22. ✅ *(RÉSOLU/REJETÉ 08/11)* Section A — répartition des paires par firm
    (§2.45) : mécanisme de décorrélation fonctionnel (clustering
    97,0%→65,9%, solde_negatif_annee4/hit_ceiling quasi nuls) mais coût
    de profit écrasant (-33,6%/-34,0%) et année1<0 empire. Fermé.
23. ✅ *(RÉSOLU/REJETÉ 08/11)* Section B — parité temporelle du flux de
    signaux (§2.46) : moins décorrélant que A (clustering 97,0%→87,7%)
    mais coût de profit tout aussi écrasant (-32,4%/-32,9%). Fermé.
24. 🟡 *(CANDIDAT n=300, 08/11)* Section C — compte contrarian bande RR
    0,75-1,25 (§2.47) : SEULE section qui améliore profit ET risque
    simultanément (+1,80%/+2,09% profit, année1<0 -3,0pt aux deux
    plafonds, dominance 3-axes à 3000$). **n=600+cascade check requis
    avant adoption**, pas encore fait — candidat prioritaire du chantier
    structurel.
25. ✅ *(DIAGNOSTIC FAIT 08/11)* Section D — balayage plafond 1000$-
    10000$ (§2.48) : critère strict <1% sur les 2 axes jamais atteint ;
    hit_ceiling_pct plafonne à 1,00% dès 5000$, ne descend plus même à
    10000$. Confirmé être le mode "effondrement flotte mature" en §2.49
    (décision #26), pas un problème de liquidité résolvable par le
    capital — le "vrai seuil de sécurité" (au-delà duquel plus aucun
    gain mesurable) se situe autour de 5000$.
26. ✅ *(RÉSOLU 08/11)* Diagnostic résidu 1% hit_ceiling à 10000$ (§2.49) :
    **confirmé le même mode "effondrement flotte mature" déjà identifié**
    (100% des runs hit_ceiling à 10000$ correspondent, aucun mécanisme
    nouveau). Le mode lui-même touche 30,33% des runs mais n'épuise la
    trésorerie que dans ~1 cas sur 30 de ses occurrences (absorbé le
    reste du temps même à 10000$). **Verdict accepté comme plancher réel
    du projet** — aucun plafond de trésorerie ne protège contre une vraie
    période de marché défavorable touchant plusieurs firms copytradées
    simultanément, cohérent avec Piste G/décorrélation asymétrique
    (§2.37, fermée pour la même raison).
27. 🟡 *(SCREENING n=300, corrigé 08/12)* Section 1 — capital combiné 2
    traders, réplication identique (§2.50, chiffres SUPERSEDED par la
    correction §2.52 — plafond personnel combiné, pas doublé) :
    architecture "séparée" (chaque trader garde sa propre réserve de
    trading) gagne toujours sur "poolée" pour une réplication identique
    (confirmé sous plafond corrigé, §2.52 config 1 vs 2 — pooling
    empire hit_ceiling de ×1,1 à ×2,6). Variante Blueberry "split"
    inchangée (gagnante). **n=600+cascade check requis avant toute
    adoption** — candidat maintenant concurrencé par la décision #30
    (config 4, meilleure).
28. ✅ *(RÉSOLU/REJETÉ 08/11)* Section 1bis — spécialisation par segment de
    signal, capitaux séparés (§2.51) : hypothèse du prompt (capital séparé
    évite le coût de volume de A/B) RÉFUTÉE — les 2 variantes testées
    (bande RR, paires) coûtent EN FAIT plus cher (-39/-40%) que les
    Sections A/B single-fleet (-32/-34%), car la spécialisation par
    trader restreint TOUTES ses firms (5/5) au lieu de 2/5 comme dans
    A/B. Aucune ne bat la réplication simple. Fermé dans sa forme testée.
29. 🟡 *(nouveau 08/11)* Section 2 diagnostic (§2.49) et Sections 1bis
    (§2.51) suggèrent que la métrique de clustering poolée est sensible
    au nombre total de comptes/traders (2× plus de comptes avec 2
    traders gonfle mécaniquement le taux de coïncidence même-jour, cf.
    §2.51 note sur 88,7% vs 66,4%) — pas encore normalisée par le nombre
    d'opportunités de casse. Point ouvert méthodologique, pas bloquant
    pour les verdicts déjà rendus (les comparaisons WITHIN une même
    configuration de comptage restent valides), mais à corriger avant de
    comparer des clustering_pct entre chantiers à nombre de comptes
    différent.
30. 🟡 *(CONFIRMÉ n=600+cascade 08/12, §2.53 — décision utilisateur finale
    entre les 2 options 3000$ toujours en attente)* Correction plafond
    personnel combiné + nouvelle config A/B+réserve commune (§2.52) :
    plafond personnel corrigé (1000$/3000$ TOTAL partagé, pas par
    trader) — vérifié par 3 points de méthodologie explicitement
    demandés AVANT toute relance (définition OR de hit_ceiling, bug
    ever_funded confirmé sans impact sur la référence flotte simple,
    audit de 3 journaux complets confirmant le plafond Blueberry jamais
    dépassé). **Config 4 (spécialisation A/B + réserve de trading
    COMMUNE) domine strictement config 3 (A/B + réserves séparées) sur
    les 4 axes aux deux plafonds** — mécanisme identifié et illustré
    concrètement (run 67 : réserve de T2 refinance la réouverture
    Blueberry de T1 au moment critique, T1 passe de -11 338$ à
    +5 691 886$ ; 14/80 runs scannés montrent ce schéma, 0 dans le sens
    inverse). Premier cas du chantier entier où pooler une réserve AIDE.
    **Confirmé n=600+cascade stable, aucune inversion** (§2.53) — les
    2 options 3000$ restent : Config 1 (profit max, 10 041 125$,
    hit_ceiling 2,00%) vs Config 4 (risque quasi nul, 6 084 214$,
    hit_ceiling 0,83%). Config 1@1000$ confirmée trop risquée (hit_
    ceiling 23,50%). Choix final entre les 2 options 3000$ laissé à
    l'utilisateur, pas de recommandation automatique.
31. ✅ *(RÉSOLU 08/12)* Audit préventif de `dual_trader_2026-08-11.py`
    (§2.54) : 3 problèmes mineurs trouvés (IS calculé par trader au lieu
    de la SAS combinée, impact <0,001% négligeable ; emergency_capital
    300$ non fusionné entre traders, mécanisme rarissime ; biais d'ordre
    T1-avant-T2 sur réserve commune, pas un bug). Aucun ne remet en
    cause les chiffres n=600 déjà publiés. Rien d'autre trouvé.
32. ✅ *(RÉSOLU 08/12)* Stratégie B confirmée n=600+cascade en isolation
    totale (§2.55) : **PAS un moteur de croissance robuste seule**
    (année1<0 76,50%/77,50%, profit ÷8 vs signal principal) — contraste
    net avec son rôle de petit compte supplémentaire validé en §2.47
    (contexte radicalement différent, pas une contradiction). Explique
    directement pourquoi T2 (piloté par Stratégie B) bénéficie tant du
    pooling de réserve dans le chantier dual-trader (décision #30) — sa
    fragilité en autonomie rend le refinancement par T1 structurellement
    utile, pas un luxe optionnel.
33. ✅ *(RÉSOLU/ADOPTÉ 08/12)* Chantier cluster Blueberry 1,5% (§2.59) :
    clarifié que le compte live actuel est Standard (soumis au cluster) et
    que la référence officielle (Run C/F) simulait Prime depuis le début
    (jamais confronté au produit réel avant cette session). 3 options
    comparées n=300 puis Option A confirmée n=600+cascade — **Blueberry en
    format Prime adopté pour tout compte futur de la flotte réelle**, sans
    coût de transition, `CONFIG_REF` reste inchangé. Le compte Standard 5k$
    actuel reste un outil de collecte de données séparé, hors décision.
    Options B (cluster sizing) et C (retrait Blueberry) fermées comme
    candidats actifs.
34. ✅ *(RÉSOLU/CONFIRMÉ 08/12)* Règle JPY-JPY (§2.60) : n=600+cascade
    reconfirme la règle actuelle — AVEC domine SANS sur profit et
    solde_negatif_annee4 aux deux plafonds, année1<0 seul point favorable
    à la retirer (marginal). **Règle conservée**, justification empirique
    fraîche remplace l'ancienne "prudence structurelle".
35. 🟡 *(CANDIDAT n=300, 08/12, SUPERSEDED par #36)* Seuil de corrélation
    0,8 (§2.61) : domine ou égale 0,6 sur les 4 axes aux deux plafonds.
    Confirmé n=600 en combinaison avec RR 1,35, voir #36.
36. ✅ *(RÉSOLU/ADOPTÉ 08/12)* Combinaison RR≥1,35 + corrélation 0,80
    (§2.62) : domine strictement la référence sur 4/4 axes à 1000$, 3/4 à
    3000$ (solde_neg marginalement pire, dans le bruit). Profit
    +6,3%/+5,5%, année1<0 -5,0pt/-4,8pt. Effet combiné sous-additif sur
    profit/solde_neg/hit_ceiling, super-additif sur année1<0. **ADOPTÉ
    comme référence officielle §1.8** ; cascade complète de régénération
    de toute la chaîne dépendante faite (§2.63) : dual-trader config1/4,
    Blueberry Prime A/B/C, zone morte T1/T2 résolue. Piste 1 (fonds
    d'urgence) explicitement non concernée, laissée en l'état.
37. 🟡 *(nouveau 08/12)* Statut de Config 1@1000$ (dual-trader, §2.63) :
    sous l'ancienne base (RR1,25+corr0,6), "confirmée trop risquée, hors
    jeu" (hit_ceiling 23,50%). Sous la nouvelle base (RR1,35+corr0,80),
    hit_ceiling tombe à 7,83% — toujours plus risqué que Config 4@1000$
    (2,33%) mais plus automatiquement "hors jeu". Le choix profit-max vs
    risque-quasi-nul à 1000$ reste ouvert, pas de recommandation
    automatique (même convention que la décision #30/§2.53), mais l'espace
    de choix réel à ce plafond s'est élargi — point à signaler si
    l'utilisateur reprend ce chantier.

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

## 6. Chantier instant funding (2026-08-15)

### 6.1 Phase 1 — Recherche sourcée (pages officielles uniquement)

| Firm | Offre instant funding réelle ? | Détail |
|---|---|---|
| **FTMO** | ❌ N'existe pas | Le "1-Step" (`FTMO_1Step`, déjà dans `FORMATS`) reste une évaluation à passer (cible retirée mais DD/durée toujours à respecter) — ce n'est PAS un skip d'évaluation. Confirmé par recherche croisée (aggregateurs + absence de mention officielle FTMO). **Exclu de la Phase 2.** |
| **GFT (Goat Funded Trader)** | ✅ Confirmé, 2 produits | **Instant GOAT** : DD journalier 3%, DD max **6% trailing** (pas de lock documenté, suit l'équité en continu), pas de cible, split 80%→100%, payout 14j, règle de consistency (aucun jour >15% du profit total), min 5 jours de trading avant retrait, règle de perte flottante -2% = fermeture définitive intrajournalière (non modélisée dans le moteur actuel). **Instant PRO** : DD **4% trailing** (confirmé, corrige l'ambiguïté 4%/8% non résolue du 08/08 — `GFT_InstantPRO` déjà codé à 4%, CONFIRMÉ exact), pas de limite journalière, même split/payout. Prix Instant GOAT confirmés par recoupement indépendant à ±3% des valeurs déjà codées (100k : 815-838$, 200k : 1663-1708$) ; Instant PRO **exactement confirmé** (25k=328$/50k=498$/100k=858$, match parfait avec le code existant). Sources : [Instant Funding GOAT Model](https://help.goatfundedtrader.com/en/articles/13574117-instant-funding-goat-model), recoupement prix via agrégateurs indépendants. |
| **Blueberry Funded** | ✅ Confirmé, 2 produits | **Instant Elite** : DD max **10% trailing lock** (verrouille en montant), aucune limite journalière, 25k=**800$ confirmé exact** (match parfait avec le code existant), split 80% dès le jour 1, payout 14j (add-on 7j ou à la demande disponibles), **NON éligible au scaling** (confirmé explicitement : "no tiered structures, scaling milestones, or delays for Instant accounts" — mais le moteur du projet ne modélise de toute façon AUCUN scaling individuel pour Blueberry classique non plus, donc **pas de coût différentiel réel sur ce point précis dans ce projet**). **Instant Lite** : DD journalier 2%, DD max 4% (verrouille au même niveau), prix ~145-185$ (confiance moyenne). Sources : [Blueberry Instant Funding](https://blueberryfunded.com/instant-funding/), [Daily/Max Loss Limits](https://help.blueberryfunded.com/en/articles/11880026-what-are-the-daily-and-maximum-loss-limits-for-instant-funding-accounts). |
| **The5%ers** | ❌ Pas un vrai instant funding | Hyper Growth garde une phase d'évaluation réelle (cible de profit 10% à atteindre avant financement — "Complete Level 1 immediately when reaching the profit target"), contrairement à ce que son nom marketing suggère. Ne correspond PAS à la définition "financement immédiat, sans phase d'évaluation" du chantier. **Exclu de la Phase 2.** Note additionnelle : DD max trouvé "Stop Out Level 6% statique" sur la doc actuelle, ce qui contredit le trailing_peak actuellement codé (`Fivers_HyperGrowth`) — écart non résolu, mais sans objet puisque le format est de toute façon exclu ici. |
| **FundedNext** | ⚠️ Existe mais non comparable | Stellar Instant confirmé plafonné à **20 000$ d'allocation de base** (scaling possible jusqu'à 2M$ mais en partant de très bas), très loin du palier actuel du projet (200 000$, `FUNDEDNEXT_PALIER`). Adopter Stellar Instant nécessiterait une refonte complète de l'architecture FundedNext du projet (actuellement 1 seul compte fixe 200k$, aucun mécanisme de croissance individuelle modélisé) — hors périmètre de ce chantier. **Exclu de la Phase 2**, prix confirmés par ailleurs (2k$=59,99$/5k$=149,99$/10k$=299,99$/20k$=599,99$) si jamais une refonte est envisagée plus tard. Source : [Maximum Allocation Stellar Instant](https://help.fundednext.com/en/articles/11641400-what-is-the-maximum-allocation-for-the-stellar-instant-account).

**Conclusion Phase 1 : seuls Blueberry et GFT ont une offre instant funding réelle ET comparable au palier déjà utilisé par le projet.** Phase 2 limitée à ces deux firms.

### 6.2 Phase 2 — Modélisation économique (Blueberry et GFT)

Méthodologie : simulation compte unique (pas la flotte complète), population
réelle RR≥1,35, block bootstrap 2 mois, 4 ans, n=300, éval=1,25% (GFT
1,75%)/funded=1,90% (référence actuelle du projet). Piste classique (format
déjà retenu par firm) vs piste instant (financée dès t=0, format instant
réel, **prix de réouverture = plein tarif instant à chaque casse**, pas de
rabais — cohérent avec la philosophie du point 5 du prompt). Fichiers :
`chantier_instant_funding_phase2_2026-08-15.py`,
`chantier_instant_funding_risk_sweep_2026-08-15.py` (suivis par git).

**Temps économisé (point 1)** — durée pour être financé en classique :
Blueberry médiane **68,8j** (moyenne 91,0j, P90 188,1j) ; GFT médiane
**44,5j** (moyenne 60,4j, P90 129,2j). L'instant funding saute
intégralement ce délai par construction.

**Blueberry — verdict : INSTANT GAGNE.** Sur 4 ans (n=300) : profit net
classique +120 504$ vs instant **+137 734$** (delta **+17 230$**, capture
directement le gain d'opportunité du temps sauté, point 2). Casses moyennes
: classique 6,66 vs instant **0,90** (le DD instant 10% trailing lock est
globalement COMPARABLE au 10% statique classique une fois financé — la
différence vient surtout du fait que l'instant évite entièrement la
fréquence de casse plus élevée de la phase d'éval elle-même, pas d'un DD
plus permissif). Cash total payé (entrée+réouvertures) : classique 1264$ vs
instant 1520$ (surcoût net modeste, point 3 — pas de perte de split/scaling
mesurable, cf. Phase 1).

**GFT — verdict : CLASSIQUE GAGNE (marginal).** Sur 4 ans (n=300) : profit
net classique +253 738$ vs instant +250 085$ (delta **-3 653$**). Mais le
vrai signal est ailleurs : casses moyennes classique 9,19 vs instant
**57,36** (×6,2) — le DD réel d'Instant GOAT (6% trailing) est BIEN PLUS
serré que le 10% statique hérité de la phase 2 d'éval sur le format
classique actuellement utilisé (point 4, effet du DD trailing-lock
QUANTIFIÉ et massif pour GFT, quasi nul pour Blueberry). Cash total payé :
classique 2935$ vs instant **28 478$** (×9,7) — l'écart domine largement le
delta de profit, l'EV brute reste positive mais le VRAI problème est la
trésorerie, pas la rentabilité espérée (voir seuil ci-dessous).

**Effet du risque (point 5, sweep `chantier_instant_funding_risk_sweep_
2026-08-15.py`, n=300 CONFIRMÉ)** — GFT instant, risque funded testé
0,75%→1,90% :

| Risque | Profit moyen | Cash payé moyen | Casses moyennes |
|---|---|---|---|
| 0,75% | +106 714$ | 3 676$ | 6,53 |
| 1,00% | +139 526$ | 7 673$ | 14,72 |
| 1,25% | +171 072$ | 12 969$ | 25,58 |
| 1,50% | +200 656$ | 20 106$ | 40,20 |
| 1,90% | +250 085$ | 28 478$ | 57,36 |

**Confirmé monotone croissant sur les 2 axes** (profit ET cash requis
augmentent ensemble avec le risque) — pas de "risque optimal" qui
maximiserait le profit sous contrainte de trésorerie modeste : c'est un
arbitrage continu, pas un point d'inflexion. **Même au risque le plus bas
testé (0,75%, cash moyen 3 676$, plausible P95≈4 400$ par extrapolation du
ratio P95/moyenne≈1,2 observé à 1,90%), le profit (+106 714$) reste
NETTEMENT INFÉRIEUR au format classique au risque normal (+253 738$,
cash payé moyen 2 935$ seulement)** — autrement dit, réduire le risque de
GFT instant pour le rendre soutenable en trésorerie lui fait perdre
l'essentiel de son avantage de profit, ET il reste dominé par le
classique sur cet axe. **Verdict définitif point 5/6 pour GFT : aucun
niveau de risque testé ne rend l'instant funding préférable au format
classique — le classique domine à la fois sur le profit ET sur la
trésorerie requise, à tous les niveaux de risque réalistes.**

Blueberry, même sweep (rappel, DD instant proche du DD classique, effet du
risque plus doux) :

| Risque | Profit moyen | Cash payé moyen | Casses moyennes |
|---|---|---|---|
| 1,00% | +72 584$ | 1 088$ | 0,36 |
| 1,25% | +90 792$ | 1 179$ | 0,47 |
| 1,50% | +109 010$ | 1 341$ | 0,68 |
| 1,90% | +137 734$ | 1 520$ | 0,90 |

Pas d'arbitrage nécessaire ici : le risque actuel du projet (1,90%)
reste le meilleur choix testé, cash requis toujours modeste (P95≈4000$,
cf. tableau plafonds ci-dessus).

**Seuil de trésorerie (point 6)**, distribution du cash total payé sur 4
ans (n=300), comparée à la grille de plafonds déjà balayée par le projet
(960$-10 000$, `chantier_ceiling_sweep_2026-08-12.py`) :

| Plafond | P(cash Blueberry instant > plafond) | P(cash GFT instant > plafond, risque actuel 1,90%) |
|---|---|---|
| 960$ | 35,0% | 100,0% |
| 1000$ | 35,0% | 100,0% |
| 3000$ | 12,3% | 100,0% |
| 5000$ | 3,7% | 100,0% |
| 10000$ | 0,0% | 100,0% |

**Verdict Blueberry : rentable à quasiment tout plafond personnel déjà
envisagé par le projet**, avec une marge de sécurité réelle seulement à
partir de ~5000$ (P95 empirique ≈4000$) — en dessous de 3000$, ~1 run sur
8 dépasserait le plafond sur 4 ans. **Verdict GFT (au risque actuel
1,90%) : PAS rentable sous AUCUN plafond testé par le projet** — même
10 000$ est dépassé dans 100% des runs sur 4 ans (P95≈34 184$). **Sweep de
risque n=300 CONFIRMÉ (§6.2 ci-dessus, mise à jour finale) : réduire le
risque ne sauve pas GFT instant** — même au risque le plus bas testé
(0,75%, cash moyen ramené à 3 676$, dans la zone soutenable), le profit
résultant (+106 714$) reste nettement inférieur au format classique au
risque normal (+253 738$, cash payé 2 935$ seulement). **Verdict ferme :
GFT instant n'est PAS recommandé, à aucun niveau de risque testé — le
format classique domine sur profit ET trésorerie simultanément.**

**Note de méthode** : cette simulation compte unique utilise une réserve
infinie pour isoler l'effet propre de chaque firm (pas de compétition pour
le cash avec le reste de la flotte) — le seuil de trésorerie ci-dessus est
donc une approximation (pic de cash nécessaire sur repos isolé), PAS une
simulation complète de flotte avec plafond personnel dynamique partagé
entre 5 firms comme le fait `registre_parametres_projet.md` §1.8. Si
Blueberry Instant ou GFT Instant sont un jour candidats à l'adoption dans
la référence officielle, une régénération complète de la cascade (comme
celle faite le 08/12 pour RR1,35/corr0,80) serait nécessaire avant tout
chiffre définitif.

### 6.3 GFT Instant — exploration élargie (08/15/16) : REJETÉ sous toutes les variantes testées

Suite explicitement demandée après le rejet de GFT Instant sous Stratégie A
(§6.2) — objectif : vérifier si une stratégie/config différente peut
mieux s'accommoder du DD 6% trailing de GFT Instant. Même méthodologie
(compte isolé, trésorerie infinie, n=300, 4 ans). Fichier :
`chantier_gft_instant_exploration_2026-08-15.py` (suivi par git),
`chantier_gft_instant_exploration_n300.csv` (non suivi).

**Référence classique GFT** : +253 738$/4ans, cash 2 935$, 9,19 casses
(rappel §6.2).

| Variante | Profit moyen | Δ vs classique | Cash moyen | Casses moy. |
|---|---|---|---|---|
| A — Stratégie B, risque standard (1,90%) | +168 164$ | -85 574$ | 8 070$ | 15,54 |
| A — Stratégie B, sweep risque 0,75%→1,90% | +68 325$ à +168 164$ | toujours négatif | 1 287$-8 070$ | 1,64-15,54 |
| B1 — RR≥1,75 | +112 276$ | -141 462$ | 17 918$ | 35,72 |
| B1 — RR≥2,00 | +113 483$ | -140 255$ | 13 588$ | 26,84 |
| B1 — RR≥2,25 | +72 499$ | -181 239$ | 8 481$ | 16,38 |
| B2 — cap positions=1 | +185 321$ | -68 417$ | 18 834$ | 37,59 |
| B2 — cap positions=2 | +227 424$ | -26 314$ | 29 378$ | 59,20 |
| **B3 — exclusion EUR/GBP** | **+255 148$** | **+1 410$** | 26 936$ | 54,20 |
| B3 — exclusion EUR/GBP+USD/CAD | +251 147$ | -2 591$ | 24 460$ | 49,12 |
| B3 — exclusion EUR/GBP+USD/CAD+EUR/CHF | +247 574$ | -6 164$ | 22 267$ | 44,63 |
| B4 — combo (2 meilleurs B, exclusion×2) | +251 147$ | -2 591$ | 24 460$ | 49,12 |

**Note méthodologique sur B3** : `daily_dd_pair_ranking.csv` (demandé
explicitement) a été vérifié puis ÉCARTÉ — fichier daté du 28/07 (avant
la population RR≥1,35), métrique de **paire-de-paires** (excursion
conjointe de 2 tickers ouverts ensemble) et non de ticker individuel, et
surtout **quasi vide** (17/91 combinaisons non-nulles, toutes ≤1% de DD)
— signal trop faible et hors-sujet pour fonder une exclusion. Substitué
par un classement EV/ticker sur la population actuelle (631 trades) —
EUR/GBP est le ticker le plus faible (EV moyen +0,061R vs +0,36R à
+1,42R pour les autres), substitution documentée explicitement plutôt
que forcée silencieusement.

**Verdict Section A : confirmé défavorable, aucun niveau de risque ne
sauve Stratégie B sur GFT Instant** — même constat structurel qu'avec
Stratégie A (§6.2) : le profit croît avec le risque mais reste dominé
par le classique à tout niveau testé.

**Verdict Section B1/B2 : REJETÉS sans ambiguïté** — RR relevé DÉGRADE le
résultat au lieu de l'améliorer (population plus petite = moins
d'opportunités pour un DD qui punit la fréquence, pas juste la taille
des pertes — l'hypothèse du prompt ne se vérifie pas). Plafond de
position réduit dégrade aussi (moins de diversification instantanée =
plus de concentration du risque par trade sur le DD agrégé, effet
inverse de celui espéré).

**Verdict Section B3 : techniquement le seul lever qui bat le classique,
mais l'écart (+1 410$, +0,56%) est un bruit statistique, PAS une vraie
victoire** — et même dans ce cas le plus favorable, le cash requis
(26 936$ moyen, P95 vraisemblablement >30 000$) reste **~9× plus élevé
que le format classique** pour un gain de profit nul en pratique. Aucun
scénario de trésorerie réaliste ne rend ce candidat intéressant.

**🔴 VERDICT FINAL GFT INSTANT (toutes explorations 08/15-16
confondues) : PISTE FERMÉE, aucun candidat prêt pour la cascade flotte.**
Le mécanisme reste le même partout : le DD réel 6% trailing de GFT
Instant est structurellement trop serré pour ce style de trading
(fréquence de trade, distribution de R) quel que soit le levier testé —
risque réduit, RR relevé, plafond de position réduit, ou exclusion de
paire, aucun ne compense l'écart avec le 10% statique du format
classique déjà utilisé. Rouvrir cette piste nécessiterait une idée
structurellement différente de celles testées ici (ex. un produit GFT
Instant avec un DD plus large, ou une stratégie encore non caractérisée
dans ce projet), pas une variante supplémentaire du même type de levier.

## 7. Bascule conditionnelle instant funding — seuil de trésorerie réel, flotte complète (2026-08-16)

Contrairement aux §6.2/6.3 (compte isolé, trésorerie infinie), ce
chantier intègre le mécanisme de bascule dans le VRAI moteur de flotte
(copie de `chantier_position_cap_2026-08-15.py`, convention "copie
figée, seuls les points marqués `<<< CHANTIER` changés") avec le vrai
plafond personnel et la vraie trajectoire de réserve. Fichier :
`chantier_blueberry_switch_2026-08-15.py` (suivi par git),
`chantier_blueberry_switch_n300.csv` (non suivi).

### 7.1 Section 1 — Blueberry

Mécanisme : tant que `state["reserve"] < bb_threshold`, tout compte
Blueberry (starter jour 0 ou réouverture après casse ou extra-compte)
reste en `Blueberry_Prime2Step` (classique). Dès que la réserve atteint
le seuil, tout NOUVEAU compte Blueberry (pas les comptes déjà actifs,
décision prise uniquement à l'ouverture/réouverture) bascule sur
`Blueberry_InstantElite`. Le reset à prix réduit (2× prix challenge,
`_reset_used`) reste réservé au format classique — aucune source ne le
documente pour Instant Elite (§6.1) ; une casse en instant paie toujours
plein tarif. n=300, RR≥1,35/corr0,80, éval=1,25%/funded=1,90% (config
actuelle complète), 2 plafonds personnels (960$/5000$, la fourchette
déjà établie start/cible par le chantier rank-and-rent), 5 seuils + la
référence 100% classique :

**Plafond personnel 960$ :**

| bb_threshold | Profit moyen | Δ vs 100% classique | solde_neg_an4 | hit_ceiling | Année1<0 |
|---|---|---|---|---|---|
| REF 100% classique | 5 914 410$ | — | 0,33% | 3,33% | 28,00% |
| 0$ (instant dès le départ) | 6 066 695$ | +152 285$ (+2,6%) | **10,00%** ⚠️ | **12,33%** ⚠️ | 21,00% |
| **5000$** | **6 224 533$** | **+310 123$ (+5,2%)** | 0,33% | **2,67%** | 25,00% |
| 15000$ | 6 208 229$ | +293 819$ (+5,0%) | 0,33% | 2,67% | 25,67% |
| 30000$ | 6 175 898$ | +261 488$ (+4,4%) | 0,33% | 3,33% | 27,00% |
| 50000$ (≈seuil déblocage flotte) | 6 137 632$ | +223 222$ (+3,8%) | 0,33% | 3,33% | 27,33% |

**Plafond personnel 5000$ :**

| bb_threshold | Profit moyen | Δ vs 100% classique | solde_neg_an4 | hit_ceiling | Année1<0 |
|---|---|---|---|---|---|
| REF 100% classique | 5 920 407$ | — | 0,33% | 1,00% | 28,00% |
| **0$ (instant dès le départ)** | **6 588 372$** | **+667 965$ (+11,3%)** | **0,00%** | **0,00%** | **14,67%** |
| 5000$ | 6 226 958$ | +306 551$ (+5,2%) | 0,33% | 0,33% | 25,00% |
| 15000$ | 6 211 565$ | +291 158$ (+4,9%) | 0,33% | 0,33% | 25,67% |
| 30000$ | 6 181 573$ | +261 166$ (+4,4%) | 0,33% | 1,00% | 27,00% |
| 50000$ | 6 143 330$ | +222 923$ (+3,8%) | 0,33% | 1,00% | 27,33% |

**🔴 Résultat central : le seuil optimal DÉPEND du plafond personnel —
confirme précisément l'intuition de départ du prompt, avec un mécanisme
clair.**

- **À 960$ (trésorerie tendue)** : `bb_threshold=0` (bascule immédiate)
  est un PIÈGE — gain de profit (+2,6%) mais solde_negatif_annee4
  explose ×30 (0,33%→10,00%) et hit_ceiling ×3,7 (3,33%→12,33%). Casser
  un compte instant coûte le plein tarif (800$) au lieu du prix éval
  classique (165$) ou du reset à prix réduit (330$) — à ce niveau de
  trésorerie, cette dépense répétée sature le plafond personnel bien
  plus souvent. **`bb_threshold=5000$` domine strictement la référence
  ET domine `bb_threshold=0`** sur tous les axes simultanément (+5,2%
  profit, hit_ceiling MEILLEUR que la référence à 2,67% vs 3,33%,
  année1<0 meilleur à 25,00% vs 28,00%) — exactement le "point
  intermédiaire" anticipé par le prompt. Les seuils plus élevés
  (15000-50000$) dégradent progressivement le profit sans gain de
  risque supplémentaire (rendements décroissants, hit_ceiling remonte à
  3,33%=référence dès 30000$) — attendre au-delà de 5000$ n'apporte
  rien à ce plafond.
- **À 5000$ (trésorerie plus large)** : le mécanisme s'inverse
  complètement — `bb_threshold=0` (bascule immédiate) devient le
  MEILLEUR choix, dominant strictement sur les 4 axes (+11,3% profit,
  solde_neg 0,00%, hit_ceiling 0,00%, année1<0 14,67% contre 28,00% pour
  la référence — quasi divisé par 2). Le plafond plus large absorbe
  sans problème la fréquence de casse plus élevée de l'instant, et le
  démarrage financé immédiat compose plus vite sur toute la durée de
  vie du compte.

**Mécanisme qui explique le tout** : chaque casse d'un compte Blueberry
Instant coûte 800$ plein tarif (vs 165-330$ en classique) — ce n'est pas
le NOMBRE de casses qui augmente radicalement (l'instant évite même les
casses de la phase d'éval elle-même, cf. §6.2), c'est le COÛT PAR CASSE
qui grimpe fortement. Tant que le plafond personnel est trop serré pour
absorber cette dépense répétée sans y consacrer une part disproportionnée
de la trésorerie disponible, la bascule prématurée sature le plafond
(hit_ceiling) plutôt que de convertir le gain de temps en profit net. Au
même seuil de réserve mais avec un plafond personnel plus généreux, ce
même coût par casse devient absorbable et l'avantage structurel de
l'instant (financement immédiat, moins de casses totales) domine sans
contrepartie.

**Verdict opérationnel : PAS un seuil universel — dépend du plafond
personnel choisi (décision utilisateur toujours ouverte, décision #9 du
registre_strategie_trading.md).** Si plafond=960$ (valeur de départ déjà
adoptée par le chantier rank-and-rent) : **seuil recommandé 5000$**. Si
plafond=5000$ (cible d'atterrissage déjà identifiée) : **seuil
recommandé 0$ (bascule immédiate)** — cohérent, puisqu'à ce
plafond-cible la trésorerie n'est plus le facteur limitant. **Prêt pour
la cascade flotte complète (régénération de la référence officielle
§1.8)** si l'utilisateur valide l'adoption — pas encore fait ici
(chantier isolé du reste de la référence, convention du projet).

**✅ RÉSOLU/INTÉGRÉ 08/16** — cascade groupée avec any-RR
(`registre_strategie_trading.md` §2.33) régénérée et cohérente (§1.8
ci-dessus, effet légèrement super-additif aux 4 plafonds, pas de
cannibalisation). Seuil par plafond utilisé dans la cascade : 960$/1000$
→ 5000$, 3000$/5000$ → 0$ (1000$/3000$ extrapolés par proximité de
régime, pas mesurés isolément à ces plafonds précis — signalé dans
§1.8). Adoption officielle en §1.8 en attente de confirmation
utilisateur finale.

**✅ Vérifications post-intégration (08/16, chantier de contrôle avant
adoption définitive)** — deux anomalies signalées, toutes deux résolues :

1. **Convergence exacte 3000$/5000$ (ligne COMBINÉ)** : confirmée par
   citation de code, pas un bug. `bb_choose_fmt_key()`
   (`chantier_cascade_combined_bb_switch_any_rr_2026-08-16.py:150-151`)
   ne dépend QUE de `state["reserve"]` et `bb_threshold` (jamais de
   `ceiling`) ; avec `bb_threshold=0,0`, `state["reserve"]>=0` est
   toujours vrai (réserve prouvablement ≥0 tout du long). `ceiling`
   n'intervient que dans `handle_cost_hybrid` (ligne 237, `room = max(0,
   ceiling - real_cash_paid)`) pour poser `hit_ceiling=True` — or
   `hit_ceiling_pct=0,00%` aux DEUX plafonds (n=600 chacun), cette
   branche n'a jamais été atteinte : `ceiling` n'a donc mathématiquement
   aucune prise sur la trajectoire dans ce scénario. Contre-preuve que
   `ceiling` est bien threadé différemment (pas un bug de paramètre
   figé) : REF (même plomberie) donne des résultats différents entre
   3000$/5000$ via le mécanisme Run F (`BB_PAYOUT_7J_CEILINGS`), qui
   teste `ceiling` directement. `bb_threshold` est en revanche
   réellement identique (0,0) entre 3000$/5000$ — par choix de
   conception documenté, pas un bug.
2. **Seuil extrapolé à 1000$/3000$, pas calibré** : calibration dédiée
   lancée (`chantier_cascade_combined_bb_threshold_calibration_2026-08-
   16.py`, n=300, grille 0/5000/15000/30000/50000 + référence classique,
   any-RR actif). **Résultat : l'extrapolation est validée par mesure
   directe.** À 1000$, bb=0 est un piège confirmé (solde_neg/hit_ceiling
   à 11,33%, pire qu'à 960$) et bb=5000 domine tous les seuils testés
   sur le profit en restant sûr (+5,68% vs référence classique) — seuil
   déjà utilisé en §1.8. À 3000$, bb=0 domine sur les 4 axes (+9,62%,
   solde_neg/hit_ceiling à 0,00%/0,00%) — seuil déjà utilisé en §1.8.
   **Aucun changement à la proposition ci-dessus.**

**✅ Décomposition du plancher de variance pure sous l'edge actuel
(08/16)** — vérification demandée après l'intégration any-RR : le
plancher historique de 24,67% (Run E, 08/11, `registre_parametres_
projet.md` §2.33 ancien, population 721/RR≥1,25, SANS any-RR) a-t-il
bougé avec le nouvel edge ? Chaîne complète (n=600 partout, cascade
check) :

| Étape | Année1<0 | Script |
|---|---|---|
| Ancien plancher (08/11, sans any-RR, sans BB Instant) | 24,67% | `etape_aj_run_e_no_casse_2026-08-11.py` |
| Nouveau plancher edge pur (+any-RR, population 631, sans BB Instant) | **24,67%** (inchangé) | `chantier_run_e_equivalent_anyrr_2026-08-16.py` |
| Vrai plancher (+any-RR +BB Instant seuil=0, cash illimité) | **12,33%** | `chantier_run_e_equivalent_anyrr_bbinstant_2026-08-16.py` |
| **Combiné réel** (+contraintes de trésorerie réelles, §1.8) | **13,83%** | (déjà mesuré ci-dessus) |

**Verdict : any-RR NE DÉPLACE PAS le plancher de variance pure**
(24,67%→24,67%, exactement identique à n=600 — le 22,67% mesuré à n=300
lors d'un premier passage était du bruit d'échantillonnage, cf. la
leçon déjà connue sur ce projet pour cette métrique bruitée). Le gain
massif du plancher (24,67%→12,33%) vient exclusivement de Blueberry
Instant, qui élimine non seulement la friction cash mais AUSSI le
risque de phase d'évaluation (le compte jour 0, `ei.STARTER=Blueberry`,
devient financé instantanément avec seuil=0, au lieu de devoir d'abord
réussir un challenge 2 étapes) — un effet structurel, pas juste une
réduction de friction. **Anomalie initialement détectée (combiné 13,83%
< ancien floor naïf) résolue** : le combiné réel (13,83%) est bien
≥ le VRAI plancher (12,33%, +1,50pt de friction résiduelle réelle,
cohérent) — la comparaison initiale utilisait un plancher mal spécifié
(sans Blueberry Instant, alors que le combiné l'inclut), pas un bug de
simulation.

### 7.2 Section 2 — GFT

**En attente du chantier d'exploration GFT.** L'exploration élargie
(§6.3, terminée le 08/16) n'a trouvé AUCUN candidat compétitif face au
format classique GFT sous aucune variante testée (Stratégie A, Stratégie
B, RR relevé, plafond de position réduit, exclusion de paire, ou
combinaisons) — il n'y a donc rien à intégrer dans un mécanisme de
bascule conditionnelle pour GFT à ce stade. Pas de test prématuré
lancé, conformément à la consigne explicite du prompt. Ce point se
rouvrira automatiquement si une future piste GFT Instant produit un
candidat compétitif en compte isolé (préalable nécessaire avant tout
passage à la flotte complète, même logique que Blueberry).

## 8. Session 2026-08-17 — plafond efficace, réouvertures ciblées, confirmations n=600

Référence de travail utilisée pour tout ce qui suit : §1.8 (cascade BB
Instant+any-RR) + rr_tp2 sizing (`registre_strategie_trading.md` §2.35).
Toujours PAS marquée adoptée officiellement dans le tableau §1.8 — décision
utilisateur finale toujours en attente, statut inchangé par cette session.

### 8.1 Plafond personnel — vrai seuil efficace entre 1000$ et 3000$

n=300, `chantier_ceiling_sweep_1000_3000_2026-08-17.py`, 2 régimes de
bascule Blueberry (5000/0) testés à chaque plafond intermédiaire (960$
seul mesuré directement en S7.1, 1000$/3000$ extrapolés par proximité en
S1.8 — jamais calibrés finement entre les deux avant cette session) :

| Plafond | Meilleur régime | Profit | Hit_ceiling |
|---|---|---|---|
| 1000$ | 5000 | 7 911 585$ | 1,33% |
| 1500$ | 5000 | 7 912 593$ | 0,33% |
| 2000$ | zone de creux, aucun régime dominant (voir §8.1bis) | 7 912 591$ (rég.5000) / 8 240 743$ (rég.0) | 0,33% / 2,00% |
| **2500$** | **0** | **8 334 629$** (identique 3000$/5000$ au $ près) | **0,00%** |
| 3000$ | 0 | 8 334 629$ | 0,00% |

**🔴 Trouvaille : 2500$ atteint déjà 100% de la performance de 3000$/5000$** (valeurs identiques au dollar près) — le vrai plafond efficace minimal est **entre 2000$ et 2500$**, pas 3000$ comme utilisé partout dans le projet jusqu'ici. Non affiné plus finement (2100-2400$) — à faire si utile. N'affecte aucun chiffre déjà publié (3000$ reste un point de mesure valide, juste pas le minimum).

### 8.1bis Balayage fin bb_threshold à 2000$ — vrai arbitrage, pas de valeur dominante

n=300, `chantier_bb_threshold_finegrid_2000_2026-08-17.py`, grille 0/500/1000/.../5000 à ceiling=2000$ uniquement :

| bb_threshold | Profit | Solde_neg | Hit_ceiling | Année1<0 |
|---|---|---|---|---|
| 0 | **8 240 743$** (meilleur) | 1,67% | 2,00% | **12,67%** (meilleur) |
| 500 | 7 945 714$ | **0,00%** (meilleur) | **0,00%** (meilleur) | 22,33% |
| 1000-5000 | ~7 912-7 919$ (plateau quasi flat) | 0,33% | 0,33% | 22,33% |

Aucune valeur intermédiaire ne domine les 2 régimes connus — bb_threshold=0 forme un régime qualitativement différent (meilleur profit/année1<0, moins sûr), tout ce qui est ≥500 converge vers un plateau "sûr" (500 est le meilleur point de ce plateau). Vrai choix de profil de risque à 2000$ si ce plafond s'avère être le plafond réel, pas un problème de calibration résoluble.

### 8.2 Réouverture Piste A (BBx2) et Piste B (BB+GFT jour0) sous la pile actuelle — 2 GO confirmés n=600

Rappel : anciennement testées sous la pile PRE-08/12 (avant rebuild RR1,35/
corr0,80, avant §1.8) — confirmé 3000$/rejeté 1000$ pour BBx2 (ancien
§2.15), arbitrage 3000$/rejeté 1000$ pour BB+GFT (ancien §2.6/§2.41).
Re-testées à l'identique (2e compte day0 SANS scaling de risque, contrairement
au double starter FTMO 50/50 de §8.6) sous §1.8+S2.35, n=300 puis n=600+
cascade avec stress-test H1/H2+4 blocs k-fold intermédiaire (aucune
inversion trouvée sur les 3 tests). Fichiers :
`chantier_pisteAB_bbx2_bbgft_2026-08-17.py` (screening n=300, 4 plafonds),
`chantier_stresstest_pisteAB_2026-08-17.py` (stress-test),
`chantier_n600_pisteAB_2026-08-17.py` (confirmation finale, tous suivis
par git).

**Verdict n=300 (4 plafonds)** : dominance apparente à 5000$ pour les 2
pistes, hit_ceiling explose à 960$/1000$ pour les 2 (rejeté), pas de
dominance stricte à 3000$ pour aucune des 2 (hit_ceiling non nul).

**✅ Confirmation n=600+cascade (2 GO, 1 arbitrage chiffré)** :

| Config | Profit | Δ vs REF | Solde_neg | Hit_ceiling | Année1<0 |
|---|---|---|---|---|---|
| REF@5000$ | 8 206 650$ | — | 0,00% | 0,00% | 13,17% |
| **BBx2@5000$** | **8 487 070$** | **+3,42%** | 0,00%(=) | 0,00%(=) | **10,00% (-3,17pt)** |
| **BB+GFT jour0@5000$** | **8 324 100$** | **+1,43%** | 0,00%(=) | 0,00%(=) | **10,17% (-3,00pt)** |
| REF@3000$ | 8 206 650$ | — | 0,00% | 0,00% | 13,17% |
| BB+GFT jour0@3000$ | 8 320 584$ | **+1,39% (+113 934$)** | 0,00%(=) | **0,00%→3,50% (+21 runs/600)** | 10,17% (-3,00pt, -18 runs/600) |

**✅ BBx2@5000$ : GO, dominance stricte confirmée n=600.**
**✅ BB+GFT jour0@5000$ : GO, dominance stricte confirmée n=600.**
**🟡 BB+GFT jour0@3000$ : arbitrage chiffré, PAS de verdict tranché** —
+113 934$/run-comparable pour +21 runs/600 touchant le plafond (0%→3,5%)
et -18 runs/600 en année1 négative. Décision utilisateur explicite requise
si ce plafond est retenu (voir décision #9 toujours ouverte).

Aucun des 2 candidats GO n'est encore intégré à la référence officielle
§1.8 — comme d'habitude, décision d'adoption formelle en attente.

### 8.3 Réouverture Piste C (fonds d'urgence 10%/7j/N2) — verdict DÉPLACÉ de 3000$ vers 1000$

Rappel ancien (S2.39, pré-08/12) : rejeté à 1000$, candidat n=300 seulement
à 3000$ (jamais confirmé n=600). Re-testé à l'identique sous §1.8+S2.35,
n=300, 4 plafonds (`chantier_pisteC_fonds_urgence_2026-08-17.py`) :

| Plafond | Δ profit | Δ solde_neg | Δ hit_ceiling | Δ année1<0 |
|---|---|---|---|---|
| 960$/1000$ | -0,22% | 0,00%(=) | **÷2 (1,33%→0,67% à 1000$)** | +0,34pt (légèrement pire) |
| 3000$/5000$ | -0,28% | 0,00%(=) | 0,00%(=, déjà optimal) | +0,33pt (légèrement pire) |

**Verdict CHANGÉ** : à 3000$/5000$, REF est désormais déjà à 0% sur les
axes de risque (rien à gagner, contrairement à l'ancienne mesure). Le
bénéfice s'est déplacé à 1000$ (hit_ceiling divisé par 2 pour -0,22% de
profit). **Résultat modeste, PAS poussé en n=600** — candidat trop faible
pour l'instant selon arbitrage explicite de l'utilisateur, disponible sur
demande séparée si besoin.

### 8.4 Réouverture Piste D (compte contrarian RR 0,75-1,25) — verdict INVERSÉ à 960$/1000$

Rappel ancien (S2.47, pré-08/12) : marchait aux DEUX plafonds
(+1,80%/+2,09% profit), marqué "candidat prioritaire n=600+cascade",
jamais repris. Reconstruit par PORTAGE (architecture différente du script
source `structure_pistes_2026-08-11.py`, mécanisme identique — compte
dédié day0, bande RR jamais tradée par le reste de la flotte, flux
indépendant fusionné par le temps) sous §1.8+S2.35, n=300, 4 plafonds
(`chantier_pisteD_contrarian_2026-08-17.py`). Population contrarian
vérifiée identique à l'époque (n=311 trades, 0,75≤rr_tp1<1,25).

| Plafond | Δ profit | Δ année1<0 |
|---|---|---|
| **960$/1000$** | **-15,9% à -16,4% (effondrement)** | -5,0pt (meilleur, seul axe positif) |
| 3000$/5000$ | +0,43% (dominance légère) | -0,67pt (meilleur) |

**Verdict CHANGÉ radicalement à 960$/1000$** (ancien +1,80% → -15,9%,
inversion complète) — mécanisme non-bug (population vérifiée identique),
cohérent avec la sensibilité accrue de la pile actuelle aux coûts de
trésorerie jour0 additionnels (plus de mécanismes gated par seuil de
réserve qu'en 08/11 : bascule BB Instant, Run F 7j, etc.). **3000$/5000$
tient globalement mais magnitude réduite** (+0,43% vs +2,09% ancien).
**REJETÉ sans ambiguïté à 960$/1000$, candidat faible à 3000$/5000$ — PAS
poussé en n=600**, disponible sur demande séparée.

### 8.5 Double starter FTMO 50/50 (jour0, risque partagé) — candidat n=300 non poursuivi

Distinct des pistes A/B ci-dessus (2e compte FTMO day0 à risque PARTAGÉ
0,5x/1,0x, pas plein) — testé en Section C d'un prompt antérieur cette
session (`chantier_C_double_starter_2026-08-17.py`), n=300+n=600 partiel :

| Config | Profit | Hit_ceiling |
|---|---|---|
| REF@3000$/5000$ | 8 334 629$ | 0,00% |
| **50/50 (parité complète)@3000$/5000$** | **8 387 340$ (+0,63%)** | 0,00%(=) |
| 50/50@960$/1000$ | +0,47%/+1,94% | **explose ×6 à ×11,5** |
| Asymétrique fav. BB (frac=0,5) | dominé partout | — |

Dominance apparente à 3000$/5000$ (n=300 seulement), ambigu/rejeté à
960$/1000$. **Jamais poussé en n=600** — le screening cette session a
priorisé BBx2/BB+GFT jour0 (§8.2, confirmés GO à 5000$ avec un profit
supérieur : BBx2 8 487 070$ > BB+GFT 8 324 100$ > FTMO 50/50 8 387 340$
à titre de comparaison indicative seulement, bases n différentes). FTMO
50/50 reste le plus prudent des 3 (jamais de hit_ceiling élevé nulle
part à 3000$+), à confirmer séparément si retenu.

### 8.6 Section "doublon même paire" — FERMÉE, rien à changer

Contexte : observation terrain (2 positions GBP/JPY simultanées, signal 2
validé pendant signal 1 actif). Vérification Étape 0 AVANT toute
construction de candidat (comme demandé) :

- **Frictions (spread/commission)** : `feasible_risk_pct`
  (scaling_simulation.py:121-147) ne gère QUE l'arrondi de lot/marge —
  **aucun terme de spread/commission en $ dans le moteur**. `pnl =
  trade["outcome_r"] * risk_amount` (engine_multiformat.py:331) est
  purement proportionnel à la taille — confirmé par citation, pas déduit.
- **Risque d'échec d'exécution/parsing** : citation exacte "1-3%" non
  retrouvée dans le registre malgré recherche large (signalé, pas
  inventé). Vérifié par le code : `app.py` logge bien des échecs réels
  (`failed_emails.log`) en production, mais ce risque **n'est modélisé
  nulle part dans le moteur de simulation** — angle mort réel mais
  UNIFORME sur toute la population, pas spécifique au cas doublon.
- **Blocage plafond spécifique aux doublons même paire** (mesuré,
  `chantier_positioncap_blocking_diagnostic_2026-08-17.py`, n=300, pile
  actuelle) : taux global de blocage plafond = **1,91%** (vs 0,79-1,11%
  ancien, pré-S1.8/S2.35) ; part causée par un doublon même ticker = 10%
  des blocages, soit **0,192% de tous les trades offerts**.

**Conclusion : ARRÊT à l'Étape 0, conformément à la règle explicite du
prompt.** Les 3 composantes fixes sont nulles/proportionnelles, non
modélisées mais uniformes, ou négligeables (0,19%). Statu quo (2 trades
séparés) = optimal théorique. Pas de candidat construit.

### 8.7 Sweep plafond de positions (3→6) × risque par trade — REJETÉ, effet INVERSE de l'hypothèse

Hypothèse testée : répartir le même risque total simultané sur plus de
positions plus petites réduirait la variance (hit_ceiling/solde_neg/
année1<0) sans changer l'EV — infirmée. n=300, 4 plafonds, risque agrégé
pire-cas maintenu ~constant (3,75-3,76%),
`chantier_sectionB_poscap_risk_2026-08-17.py` :

| Config | Δ profit (tous plafonds) | Δ année1<0 |
|---|---|---|
| V1 (4×0,94%) | **-17,7% à -18,0%** | **pire** (+1,0 à +1,3pt) |
| V2 (5×0,75%) | **-32,7% à -33,1%** | **pire** (+3,3pt) |
| V3 (6×0,625%) | **-44,2% à -44,9%** | **pire** (+3,7 à +5,7pt) |

solde_neg/hit_ceiling s'améliorent marginalement (REF déjà proche de 0%,
peu de marge). **Mécanisme identifié** : réduire le risque par trade
ralentit la progression vers l'objectif de challenge (% fixe du palier),
retardant le financement — effet déjà connu comme dominant dans ce
projet (vitesse de financement), qui écrase tout bénéfice de
diversification. Composition des slots au-delà de l'ancien plafond 3 :
24,4% doublons même paire, 75,6% paires nouvelles (mesuré séparément).
**REJETÉ sans ambiguïté, les 3 variantes, tous plafonds. Fermé.**

## 9. Session 2026-08-19 — 5 points en attente clos (double-comptage indices, DD post-objectif, staggered unlock, pivot Instant, plafond capital)

Détails complets : `session_handoff_2026-08-19.md`. Tous testés n=600 +
stress-test H1/H2+4blocs sauf indication contraire.

### 9.1 Bug double-comptage tout-indices→B — n'a PAS contaminé les chiffres déjà cités, routage reconfirmé n=600

Vérifié par timestamps fichiers (les scripts qui ont produit les chiffres
EV +0,934R/+0,648R et les tables A 631→742/B 401→460 ont tourné et
sauvegardé AVANT que le patch introduisant le bug n'existe sur disque) ET
par recalcul direct depuis les CSV sauvegardés — **aucune correction à
apporter à ces chiffres déjà consignés en §1.8bis**.

Le bug lui-même (trouvé dans `chantier_strategie_b_isolation_indices_
2026-08-18.py`, corrigé avant tout résultat publié) n'affecte que le
routage tout-indices→B, reconfirmé ici n=600+cascade+stress-test :

| Plafond | naturel | tout_indices | Δ profit | Δ année1<0 |
|---|---|---|---|---|
| 960$/1000$ | ~1 545-1 550k$ | ~2 221-2 233k$ | **+43,7% / +44,1%** | -13,84pt |
| 3000$/5000$ | 1 726k$ | 2 440k$ | **+41,3%** | -13,83pt |

Cohérent avec le n=300 (+42,8-46,2%). **Nuance nouvelle au n=600** :
hit_ceiling se dégrade légèrement à 960$/1000$ (+0,3 à +0,5pt, absent du
n=300) — dominance n'est plus stricte sur cet axe précis à ces plafonds,
à garder en tête avant adoption finale de §2.47.

### 9.2 DD inutile post-objectif de phase — confirmé, effet mesuré, PAS ENCORE stress-testé

Citation exacte (`engine_multiformat.py:375-388`) : une fois la cible de
phase atteinte, si `min_days` (jours DISTINCTS avec au moins un trade,
pas calendaires) n'est pas encore satisfait, le compte continue à
recevoir tous les signaux au risque plein — aucun mécanisme de pause
n'existe. Quantifié n=600, 4 plafonds (variante "risque quasi nul pendant
la fenêtre" vs REF) :

| Plafond | Δ profit | Δ année1<0 |
|---|---|---|
| 960$/1000$ | **+0,49%** | -0,50pt |
| 3000$/5000$ | **+0,43%** | -1,33pt |

261 498 trades concernés sur 2400 runs, 8 casses directement dans cette
fenêtre. Effet petit mais cohérent aux 4 plafonds sans exception.
**PAS stress-testé H1/H2+4blocs** (faute de temps, effet jugé trop petit
pour être suspect mais reste à faire avant toute adoption formelle).

### 9.3 Staggered unlock — n'est PAS un candidat, c'est déjà le comportement REF actif, valeur reconfirmée n=600

`ei.seq_grouped_multi(1000, 15000, 25000, 25000)` (etape_e_fleet_
integration.py:144-151) EST le mécanisme échelonné déjà en usage dans
tous les scripts backant §1.8 — pas un levier séparé à activer. Valeur
ajoutée vs comparateur "groupé" historique (seuil unique 30000$, ancien
DEFAULT_RESERVE pré-08/08) reconfirmée n=600+stress-test :

| Plafond | Δ profit | Δ année1<0 |
|---|---|---|
| 960$/1000$ | **+5,73%** | -9,50pt |
| 3000$/5000$ | **+7,51%** | -16,33pt |

Cohérent avec l'historique 08/08 (+7,2%/+7,8%). Stress-test H1/H2+4blocs :
2/6 sous-périodes en inversion (H1, bloc0 — régime difficile déjà connu
pour d'autres leviers), 4/6 cohérentes. Rien à changer.

### 9.4 Pivot Instant 5k$/10k$ clarifié n=600 — InstantElite25k reste optimal, nuance structurelle nouvelle

| Config | Profit@3000$ | Profit@5000$ | vs Prime25k | vs InstantElite25k (REF) |
|---|---|---|---|---|
| Prime25k | 6 459 445$ | 6 429 909$ | — | — |
| InstantElite5k | 6 440 699$ | 6 451 105$ | -0,29% / +0,33% (bruit) | -4,00% / -3,85% |
| InstantElite10k | 6 537 675$ | 6 548 004$ | **+1,21% / +1,84%** | -2,56% / -2,40% |
| InstantElite25k (REF) | 6 709 267$ | 6 709 267$ | +3,88%/+4,34% | — |

Confirme le n=300 déjà consigné (§2.45bis) : à 3000$/5000$, InstantElite25k
strictement optimal. **Nuance nouvelle détectée au n=600** (absente du
n=300 original, qui ne couvrait pas cette colonne à ces plafonds) :
solde_neg et hit_ceiling passent de 0,00% à 0,17% pour 5k/10k — coût
structurel léger mais réel, jusqu'ici non documenté à 3000$/5000$.

### 9.5 Balayage plafond capital 10k$-200k$ — plateau confirmé déjà atteint avant 10k$, pas de n=600 nécessaire

n=300, 9 paliers (10k/20k/30k/40k/50k/75k/100k/150k/200k) : **profit
identique au dollar près sur toute la plage** (6 809 976$ partout,
hit_ceiling=0,00% à chaque palier, 0 variation sur 2700 tirages). Pas
d'ambiguïté statistique à trancher (contrairement à un effet marginal
proche d'un seuil) — n=600 jugé inutile. Confirme et affine le point
ouvert de la session 08/17 : le vrai plateau est **avant 10 000$**, dans
la zone 2000-2500$ déjà identifiée, pas au-delà.

**Condition de réouverture (les 5 points)** : aucune pour 9.1/9.3/9.5
(confirmations propres). 9.2 nécessite un stress-test H1/H2+4blocs avant
adoption formelle. 9.4 reste "pas utile à 3000$/5000$" mais le coût
structurel nouveau (0,17%) doit être ajouté à toute décision future sur
5k/10k à des plafonds plus serrés.

### 9.6 🔴 BUG confirmé (08/19) — `ALPHA_POST`/`BETA_POST` de la Stratégie A réutilisé tel quel pour la Stratégie B dans les MC flotte B6 — dérivation posée, **PAS ENCORE corrigé dans le code**

**Constat.** `ALPHA_POST, BETA_POST = 260, 388` (`etape_e_fleet_
integration.py:100`) pilote `wr_draw = rng_wr.betavariate(ALPHA_POST,
BETA_POST)` dans `run_propagated()` — un tirage de winrate cible que
`build_flexible_population_with_rr()` force ensuite sur CHAQUE run Monte
Carlo, en re-labellisant gagnants/perdants de la population fournie.
`chantier_b6_montecarlo_2026-08-19.py:625-626` importe ce module
(`import etape_e_fleet_integration as ei`) et appelle `run_propagated()`
avec `pop_v` = `build_pop_B_variant(...)`, donc une population **Stratégie
B** (rr_tp1<1,35 + tout_indices) — mais `ei.ALPHA_POST`/`ei.BETA_POST`
n'ont jamais été recalculés pour B, ils restent ceux calibrés sur A.

**Dérivation reconstituée de 260/388 (Stratégie A).** Aucun commentaire
dans le code ; retrouvé par recoupement avec la ligne "Ancienne pop.
encore utilisée par les sims flotte (646 trades) | 646 | 40,09%" du
tableau §comparaison-populations (cf. aussi
[[project_backtest_analyzer_live_bug]] / [[project_pop721_impact_measured]])
: le fichier `historique_lutessia_15k.csv` **figé au 27/07** (646 trades
filtrés statut terminal, avant l'extension 646→721→631(RR≥1,35)→742 du
08/18) donne wins=259/losses=387 (winrate 40,09%). Avec un prior uniforme
Beta(1,1) — pas le Jeffreys(0,5;0,5) documenté en §2.29, un autre choix de
prior pour un autre usage — posterior = Beta(259+1, 387+1) = **Beta(260,
388)**. Confirmé exactement : 260+388=648=646+2 (les 2 pseudo-observations
du prior uniforme), moyenne 260/648=40,12%≈40,09% observé. **Donc 260/388
est déjà un chiffre PÉRIMÉ pour A elle-même** (population gelée au 27/07,
jamais mise à jour vers les 742 trades actuels) — un second problème,
distinct de la réutilisation sur B, non traité ici (déjà tracé dans
[[project_backtest_analyzer_live_bug]]).

**Calcul de l'équivalent B, même méthodologie (prior Beta(1,1) + wins/
losses observés), sur la population EXACTE que construit
`build_pop_B_variant()`** (source `historique_lutessia_15k_force.csv`,
courant/non figé — reproduit hors bougies H1, `statut_final` et `rr_tp1`
venant directement du CSV source, indépendants du calcul de continuation
TP1→TP2) :
- Volet forex (`rr_tp1` ∈ [0,75 ; 1,35[, non-index, ticker mappable) :
  n=401
- Volet indices (`tout_indices` — DAX40/S&P500/NASDAQ100, AUCUN filtre
  rr_tp1, cf. `load_index_population_with_payoff`) : n=170
- **Total B (b6) : n=571, wins=275, losses=296, winrate=48,16%**
- → **ALPHA_POST_B, BETA_POST_B = 276, 297** (moyenne 48,17%)

**⚠️ Écart NON résolu avec une autre mesure B citée cette session** :
`chantier_gold_silver_pop_B_config0_2026-08-19.csv` donne n=1505 (761
`OBJECTIF ATTEINT`/744 `INVALIDÉE`), winrate=50,56% — près de 3x plus
grand que les n=571 ci-dessus. Écart expliqué a priori par le périmètre :
ce CSV vient de la session métaux/routage A↔B du 08/19 soir
([[project_session_2026-08-19_soir3_metaux_routage]], "Config 2 routing
gagne", **pas encore intégré au registre**) qui ajoute or/argent et
probablement une règle de routage différente — **`build_pop_B_variant()`
dans b6 n'inclut PAS les métaux**. Les deux chiffres mesurent donc deux
définitions différentes de "Stratégie B", pas la même population vue
sous deux angles. **Tant que le périmètre officiel de B (avec ou sans
métaux/nouveau routage) n'est pas tranché, appliquer 276/297 corrige le
bug de réutilisation d'A mais peut lui-même devenir périmé dès que
métaux+routage sont adoptés** — retour ici obligatoire à ce moment-là.

**Portée du bug** : tous les runs `chantier_b6_montecarlo_2026-08-19.py`
et tout script import qui appelle `run_propagated()`/`build_flexible_
population_with_rr()` sur une population B avec `ei.ALPHA_POST/BETA_POST`
non substitués — déclassement systématique d'environ 40,1%→48,2%
observé, soit ~8pt de winrate sous-tiré à chaque tirage (pas 10,5pt comme
l'estimation initiale au doigt mouillé, qui comparait à tort au 50,6% du
périmètre métaux plutôt qu'aux 48,2% du périmètre b6 réel).

**Statut : CORRIGÉ (08/19)**, arbitrage utilisateur explicite en faveur
du périmètre b6 actuel (sans métaux) plutôt que d'attendre l'intégration
métaux/routage. `ALPHA_POST_B, BETA_POST_B = 276, 297` ajouté dans
`chantier_b6_montecarlo_2026-08-19.py` (juste après `INDEX_KEYWORDS`),
et `wr_draw = rng_wr.betavariate(ei.ALPHA_POST, ei.BETA_POST)` (ligne
625) remplacé par `betavariate(ALPHA_POST_B, BETA_POST_B)`. Seul point
d'appel de `run_propagated()` dans ce fichier, toujours sur `pop_v` issu
de `build_pop_B_variant()` — aucun autre call site à corriger dans ce
script. **Aucun run déjà publié dans ce registre ne s'appuyait sur ce
script** (chantier_b6_montecarlo_2026-08-19.py n'a pas encore de
résultats consignés ailleurs dans ce fichier), donc rien à invalider
rétroactivement. **Point de réouverture** : si le périmètre métaux/
routage (08-19 soir) est adopté plus tard, recalculer ALPHA_POST_B/
BETA_POST_B sur la nouvelle population B officielle. Script de
vérification : `compute_alpha_beta_b.py` (scratchpad de session, non
committé).

**✅ RÉOUVERTURE RÉSOLUE (08/19-20 soir/nuit)** — le périmètre métaux/
routage a été adopté (Config2, puis décision de lancement séquentiel
B→A, `registre_strategie_trading.md` §6). Deux nouvelles dérivations
distinctes, MÊME méthode (Beta(1,1) + wins/losses observés), documentées
dans `registre_strategie_trading.md` §6.2 :
- Population B Config0/Config2 complète (571 forex/indices + 934 métaux
  14 tickers, n=1505) : **ALPHA_POST_B_METAUX=762, BETA_POST_B_METAUX=745**
  (winrate 50,56%).
- Population B_tradable (571 forex/indices + 480 métaux 7 tickers
  réellement tradables sur le compte Blueberry de lancement, n=1051,
  population RETENUE pour le lancement) : **ALPHA_POST_B_TRADABLE=533,
  BETA_POST_B_TRADABLE=520** (winrate 50,62%).
Bug corrigé dans `chantier_ab_metaux_cascade_officiel_2026-08-19.py` (pas
dans `chantier_b6_montecarlo_2026-08-19.py`, qui reste sur 276/297 pour
son propre périmètre sans métaux, toujours correct pour son usage).
