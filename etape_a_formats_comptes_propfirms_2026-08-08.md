# Étape A — Formats de compte par prop firm (2-step / 1-step / instant funding)

*Recherche effectuée le 08/08/2026, 5 agents en parallèle (un par firm), sources
officielles uniquement (help center / pages produit), sauf mention explicite de
source tierce. Chaque donnée porte un niveau de confiance (élevée/moyenne/faible).
Collecte pure — aucun code ni simulation modifié dans cette session. Complète
`synthese_recherche_prop_firms_fiscalite_20260806.md` et
`recherche_comptes_splits_propfirms_20260807.md` (splits déjà couverts à
confiance élevée pour les formats 2-step, non re-vérifiés ici sauf incohérence
trouvée).*

**Ne pas conclure ici sur quel format est "meilleur"** — factuel uniquement, l'analyse comparative viendra à l'Étape C/D une fois le moteur refondu (Étape B).

---

## 0. Finding transverse le plus important : le vrai clivage trailing/statique

Avant cette recherche, le projet supposait la ligne de partage trailing/statique
posée **par format d'évaluation** (ex. "2-step trailing, 3-step statique" chez
GFT). **C'est faux dans les 5 firms.** Le vrai clivage, confirmé indépendamment
par les 5 agents sur les 5 firms, est :

- **Formats avec évaluation (1-step, 2-step, 3-step, quel que soit le nombre de
  phases)** → DD max **STATIQUE**, calculé une fois pour toutes sur le solde de
  départ, ne bouge jamais même si le compte grossit.
- **Formats "instant funding" (financement direct sans évaluation)** → DD max
  **TRAILING**, suit le pic d'équité atteint, généralement se **verrouille**
  (freeze) une fois un certain seuil de profit atteint (breakeven ou plus).

Confirmé sur : FTMO (2-Step statique / 1-Step trailing fin de journée — seule
exception partielle, voir §1), The5%ers (High Stakes statique / Hyper Growth
trailing), Blueberry (Prime+1-Step statique / Instant Elite+Lite trailing),
GFT (1/2/3-Step tous statiques / tous les Instant Funding trailing), FundedNext
(2-Step/Lite/1-Step statiques / Stellar Instant trailing).

**Implication pour la refonte (Étape B)** : le moteur peut probablement traiter
"trailing vs statique" comme une propriété du **type de format** (évaluation vs
instant) plutôt qu'un paramètre par firm à saisir manuellement à chaque fois —
sous réserve de vérifier qu'aucune exception ne subsiste (voir FTMO 1-Step
ci-dessous, cas limite).

---

## 1. FTMO

**Formats disponibles (confirmé exhaustif) : 2-Step (Standard ou Swing), 1-Step.
Pas d'instant funding chez FTMO** — confirmé explicitement par une FAQ officielle
qui ne mentionne aucun produit sans évaluation. Confiance élevée.

### 2-Step — Standard (référence actuelle du projet)

| Paramètre | Valeur | Source | Confiance |
|---|---|---|---|
| Phases / cibles | P1 10%, P2 (Verification) 5% | [Trading Objectives](https://ftmo.com/en/trading-objectives/) | Élevée |
| DD journalier | 5% du capital initial, reset 00:00 CE(S)T | idem | Élevée |
| DD max | 10%, **statique** (plancher fixe capital initial −10%, jamais recalculé) | [Academy — Maximum Loss](https://academy.ftmo.com/lesson/maximum-loss/) | Élevée |
| Durée min | 4 jours/phase, pas de limite de temps totale | [2-Step Challenge](https://ftmo.com/en/2-step-challenge/) | Élevée |
| Prix (50k/100k/200k) | €345 / €439 / €1 080 | ftmo.com/en/2-step-challenge/ | Élevée |
| Copytrade | Toléré sous plafond cumulé 400 000$/trader, pas de phrase "autorisé" explicite, pas d'interdiction non plus | [FAQ — combien de comptes](https://ftmo.com/en/faq/how-many-accounts-can-i-have/) | Moyenne |

### 2-Step — Swing (variante détention week-end, utilisée dans le projet)

Sous-type du 2-Step, pas un format séparé. Mêmes phases/cibles/DD/durée min que
Standard (aucune valeur différente trouvée officiellement). Différences réelles :
autorise news/overnight/week-end, **levier réduit 1:30** (vs 1:100 Standard,
confiance moyenne — via résultats croisés, pas citation verbatim directe). Prix
Swing non listé séparément (probablement identique Standard, non confirmé).
Copytrade spécifique au sous-type Swing : **non confirmé** (le FAQ 400k$ ne
nomme que 1-Step/2-Step, jamais les sous-types).

### 1-Step

| Paramètre | Valeur | Source | Confiance |
|---|---|---|---|
| Phase / cible | 1 phase, 10% | [1-Step Challenge](https://ftmo.com/en/1-step-challenge/) | Élevée |
| DD journalier | 3% du capital initial, reset 00:00 CE(S)T | [Trading Objectives](https://ftmo.com/en/trading-objectives/) | Élevée |
| DD max | 10%, **trailing fin de journée** — recalculé à minuit sur le plus haut solde de clôture atteint (jamais intraday) | idem, [Blog 1-Step](https://ftmo.com/en/blog/introducing-the-1-step-ftmo-challenge/) | Élevée |
| Durée min | Aucune (illimité) | [1-Step Challenge](https://ftmo.com/en/1-step-challenge/) | Élevée |
| Prix (50k/100k/200k) | €319 / €499 / €999 (non remboursable, vs 2-Step remboursable) | idem | Élevée |
| Copytrade | Même statut que 2-Step (plafond 400k$ commun aux deux produits, confirmé applicable au 1-Step explicitement) | FAQ 400k$ | Moyenne |
| Contrainte cachée | **"Best Day Rule" 50%** : aucun jour gagnant ne doit dépasser 50% du profit total des jours gagnants — absente du 2-Step | idem | Élevée |
| Split | 90% dès le départ (vs 80%→90% pour 2-Step) | idem | Élevée |

**Point non confirmé** : le plafond 400k$ porte-t-il sur le capital financé
uniquement ou aussi en évaluation — toujours non tranché malgré une 2e recherche.

---

## 2. The5%ers

**Formats disponibles : 4 programmes distincts, pas seulement des splits
différents — de vraies structures d'évaluation différentes.**

| Programme | Structure | Phases |
|---|---|---|
| High Stakes | 2-step | 2 |
| Bootcamp | 3-step | 3 (non retenu projet) |
| Hyper Growth | 1-step, brandé "Instant Funding" | 1 |
| Pro Growth | 1-step | 1 |

**Clarification "Instant Funding" chez The5%ers** : ce n'est **pas** un produit
sans condition — c'est le nom marketing de **Hyper Growth** (page officielle
titrée *"Pass the One Step Program Challenge and Get Instant Funding"*). Le
"Level 1" impose une cible résiduelle de 10%, mais le trading se fait en argent
réel dès le départ (différence réelle vs High Stakes/Bootcamp, où le trading en
évaluation est en démo). Confiance moyenne — structurellement proche d'une
évaluation déguisée, mais avec une vraie différence (argent réel dès J1).

### High Stakes (2-step, actuel projet)

| Paramètre | Valeur | Source | Confiance |
|---|---|---|---|
| Phases / cibles | P1 8% (variante originale, utilisée par le projet) ou 10% (nouvelle variante d'entrée, prix plus bas) ; P2 5% dans les deux cas | the5ers.com/high-stakes/ | Élevée (8%) / Moyenne (10%, à confirmer laquelle le projet a réellement souscrite) |
| DD journalier | 5%, calculé sur le plus haut entre équité de clôture et solde de la veille, reset 00:00 serveur | help.the5ers.com/what-is-the-drawdown-rule-for-high-stakes/ | Élevée (déjà connu, reconfirmé) |
| DD max | 10% du solde initial, **statique** (plancher fixe, l'exemple officiel montre que le "montant affiché" bouge mais le plancher réel non) | idem | Élevée |
| Durée min | 3 jours profitables/phase, pas de limite de temps | the5ers.com/high-stakes/ | Élevée |
| Prix 100k$ | ~545$ (annoncé janv. 2025, pas reconfirmé récent) | x.com/the5erstrading | Moyenne |
| Copytrade | Autorisé même trader ; plafond combiné **500 000$** (voir §0bis ci-dessous) | recherche agrégée + précision utilisateur | Moyenne |

### Hyper Growth (1-step, "Instant Funding")

| Paramètre | Valeur | Source | Confiance |
|---|---|---|---|
| Phase / cible | 1 phase (Level 1), 10% par palier (puis à chaque doublement) | the5ers.com/hyper-growth/ | Élevée |
| DD journalier | 3% — déclenche une **pause** (compte suspendu, PAS fermé), reprise le lendemain 00:00 MT5 | help.the5ers.com/how-does-the-hyper-growth-program-work/ | Élevée |
| DD max | 6% du solde initial, **TRAILING** — le stop-out monte réellement avec le solde ; les retraits réduisent d'autant le DD dispo | idem | Élevée — inverse de High Stakes (statique) |
| Durée min | Aucune | the5ers.com/hyper-growth/ | Élevée |
| Prix | 10k≈260$, 20k≈450$, 40k≈850$ ; capital max en évaluation 40 000$ | source tierce agrégée | Moyenne |
| Copytrade | Autorisé même trader, sous plafond 500k$ commun | agrégée + utilisateur | Moyenne |
| Split | Démarre bas (50%), progresse avec scaling | the5ers.com/your-guide-.../ | Moyenne |

### Pro Growth (1-step) — non détaillé en profondeur

Cible 10%, DD journalier 3% (ferme le compte, pas de pause contrairement à Hyper
Growth), DD max 6%, 3 jours profitables min, split initial 75%. Trailing/statique
**non confirmé séparément** — faible confiance sur ce point précis.

### Bootcamp (3-step) — non retenu dans le projet, non détaillé

3 phases à 6% chacune, DD max 5%/phase en évaluation puis 4% financé, DD
journalier 3% (pause seulement une fois financé). Copytrade **interdit entre
deux comptes Bootcamp**, autorisé Bootcamp↔High Stakes/Hyper Growth (confiance
moyenne, corroboré par 2 sources tierces + précision utilisateur).

### §0bis — Copytrade The5%ers, intégration de la précision utilisateur

Aucune page officielle unique trouvée énonçant toutes les règles. Corroboré à
confiance moyenne par sources tierces convergentes + votre précision : copytrade
même trader autorisé (y compris autres firms/comptes perso — non retrouvé
spécifiquement), interdit Bootcamp↔Bootcamp, autorisé pour les autres
combinaisons, **plafond combiné 500 000$** au-delà duquel le copytrade
inter-comptes n'est plus autorisé.

**⚠️ Point ouvert critique déjà signalé** : le code du projet fixe
`FIRM_CAPITAL_CAP["Fivers"] = 500 000$` (5 comptes × 100k, pile la limite), sans
la marge de sécurité à 400k mentionnée par l'utilisateur pour absorber la
croissance du solde des comptes dans le temps. Pas corrigé dans cette session
(collecte de données uniquement) — voir section "Points ouverts" en fin de doc.

---

## 3. Blueberry Funded

**Ambiguïté prioritaire résolue (confiance élevée)** : "Instant Access" et le
2-step du projet sont **deux familles de produits séparées**, pas la même chose :
1. **Évaluation classique** : "Prime Challenge (2-Step)" + variante "2-Step
   Challenge" standard plus ancienne (les deux semblent coexister) + "1-Step
   Challenge".
2. **Instant funding réel** : noms officiels **"Instant Elite"** et **"Instant
   Lite"** — financement direct, pas de cible de profit, mais règles de risque
   toujours actives.

Le split "80% dès le premier jour, Instant Access (Elite & Lite)" cité dans les
docs de recherche antérieures concerne le produit **instant funding séparé**,
**pas** le compte 2-step actuellement utilisé dans le projet — les deux docs de
06/08 et 07/08 avaient mal attribué cette donnée. À corriger mentalement dans
toute lecture future de ces docs.

### Prime Challenge (2-Step) — probable format actuel du projet

| Paramètre | Valeur | Source | Confiance |
|---|---|---|---|
| Phases / cibles | P1 8%, P2 6% | help.blueberryfunded.com — "Prime Challenge (2-Step)" | Élevée |
| DD journalier | 4% du solde/equity de départ (le plus élevé), reset quotidien | help.blueberryfunded.com — "2 Step - Daily/Max Drawdown" | Élevée |
| DD max | 10%, **statique**, ne bouge jamais | idem | Élevée |
| Durée min | 5 jours actifs (≥0,5% profit clôturé/jour) | help.blueberryfunded.com | Élevée |
| Prix 25k | ~165$ (promo tierce non confirmée à 99$) | blueberryfunded.com | Moyenne |
| Copytrade | Règle plateforme générale uniquement (même trader, via Traders Connect/Duplikum/etc.), pas de déclinaison par format trouvée | help.blueberryfunded.com — "Am I allowed to copy trade?" | Moyenne |

**⚠️ Ambiguïté résiduelle importante non résolue** : un produit officiel distinct
**"2-Step Challenge" standard** (plus ancien, encore actif) existe avec des
chiffres différents — **cible 10%/5%, DD journalier 5%, DD max 10%, 3 jours
min**. Le code du projet utilise actuellement **dd=5.0, dd_max=10.0**
(`point2_sequencing_engine.py:57`), ce qui correspond à ce "2-Step Challenge"
standard (5%/10%), **pas** à Prime Challenge (4%/10%, cibles 8%/6%). **Il faut
vérifier sur le contrat/dashboard réel du compte Blueberry souscrit lequel des
deux produits s'applique** — impossible à trancher depuis la recherche seule.
Si c'est Prime, le DD journalier codé (5%) est trop large par rapport au vrai
(4%) — même famille de bug que les corrections FundedNext/Fivers déjà faites.

### 1-Step Challenge

Cible 10%, DD journalier 4% statique, DD max 6% statique, 3 jours min. Prix 25k
non isolé dans les sources (faible confiance). Copytrade non confirmé
spécifiquement.

### Instant Elite (vrai instant funding)

| Paramètre | Valeur | Source | Confiance |
|---|---|---|---|
| Phase/cible | 0 phase, financement direct, pas de cible | help.blueberryfunded.com — "Instant Access Sim Account" | Élevée |
| DD journalier | **Aucune limite** | help.blueberryfunded.com — "How Is Drawdown Calculated?" | Élevée |
| DD max | 10%, **trailing**, se **verrouille au solde de départ (breakeven)** une fois 10% de profit atteint, ne bouge plus après | idem | Élevée |
| Durée min | 5 jours actifs/cycle payout (durci depuis 17/02/2026, était 3j avant ; add-on payant "3-Day Fast Track" existe) | idem | Moyenne-élevée |
| Prix 25k | ~800$ plein tarif (source tierce) | tradingpilot.com | Faible-moyenne |
| Contrainte cachée | Le plancher ne se réinitialise **jamais après un retrait** — si on retire l'essentiel des profits une fois verrouillé au solde de départ, quasi aucune marge de perte restante | help.blueberryfunded.com | Élevée |

### Instant Lite (instant funding, version plus stricte)

DD journalier 2% statique/jour, DD max 4% **trailing** (même mécanisme de
verrouillage que Elite, mais marge de base 4x plus étroite), 5 jours min/cycle
(idem durcissement 17/02/2026). Prix 25k ~145-225$ (faible confiance, source
tierce). Même risque de "plancher verrouillé sans marge après retrait" que
Elite mais amplifié.

---

## 4. GFT (Goat Funded Trader)

**Formats confirmés** : 1-Step, 2-Step Standard, 2-Step PRO (⚠️ discontinué à la
vente depuis le 13/06/2026, probablement obsolète pour la modélisation), 2-Step
GOAT Model (actuel projet), 3-Step, et **plusieurs sous-variantes Instant
Funding** (GOAT/PRO/Standard/Premium/HERO — plus riche que prévu).

### Récapitulatif phases/DD par format évaluation (tous confirmés STATIQUES, contrairement à l'hypothèse initiale — voir §0)

| Format | Phases/cibles | DD journalier | DD max | Durée min | Confiance |
|---|---|---|---|---|---|
| 2-Step GOAT Model (actuel) | P1 8%, P2 6% | 4% | **10%, statique** ("Absolute Floor") | 3j/phase | Élevée |
| 2-Step Standard | P1 10%, P2 5% | 5% | 10%, statique | 3j/phase | Élevée |
| 2-Step PRO (discontinué 13/06/2026) | P1 8%, P2 4% | 4% | 8%, statique | 3j/phase | Élevée |
| 3-Step | 3×6% | 4% | 8%, statique | Aucun minimum | Élevée |
| 1-Step | 10% | 4% (3% dès 01/08/2026) | 6%, statique | 3j min | Élevée |

**Vérification explicite 2-Step GOAT vs 3-Step (question directe : les deux ont-ils
été vérifiés séparément, et contredisent-ils le doute initial ou la règle
universelle du §0 ?)** — Réponse : les deux ont été vérifiés séparément, avec
citation distincte pour chacun, et les deux sont bien STATIQUES. Ça **contredit
le doute initial de cadrage de cette recherche** (qui supposait 2-Step trailing
/ 3-Step statique) et **confirme la règle universelle du §0** (toute évaluation
= statique, quel que soit le nombre de phases) :
- **2-Step GOAT Model** : source [help.goatfundedtrader.com/en/articles/13575348-2-step-goat-model](https://help.goatfundedtrader.com/en/articles/13575348-2-step-goat-model),
  libellé officiel *"10% (Static)"* dans le tableau comparatif de la page,
  citation verbatim : *"This is your Absolute Floor. Your account equity or
  balance must never drop below 90% of your starting capital."*
- **3-Step Model** : source [help.goatfundedtrader.com/en/articles/10630343-3-step-model](https://help.goatfundedtrader.com/en/articles/10630343-3-step-model),
  libellé officiel *"(Static)"*, citation verbatim : *"never drop below 92% of
  your starting capital"*.

La vraie différence entre 2-Step et 3-Step chez GFT n'est donc pas
trailing/statique (les deux sont statiques) mais le niveau du DD max (10% vs
8%) et l'absence de minimum de jours en évaluation sur le 3-Step.

Prix : non trouvés par palier officiellement pour aucun format (faible
confiance) — seule confirmation : tailles 2,5k$ à 400k$, plafond capital
combiné **400 000$ tous modèles confondus** (confirmé, mais sans préciser si ce
plafond diffère par format).

### Instant Funding — sous-variantes (tous TRAILING, cohérent avec §0)

| Sous-modèle | DD journalier | DD max | Durée min | Confiance |
|---|---|---|---|---|
| Instant GOAT | 3% trailing | 6% trailing | 5j non-consécutifs, ≥0,5%/j | Élevée |
| Instant PRO | Aucun DD journalier | 4% trailing (incohérence non résolue avec une source tierce citant 8%) | ≥5j avant demande de reward | Moyenne (DD max) |
| Instant Standard | Page officielle inaccessible (404) | — | — | Non confirmé |
| Instant Premium / HERO | Existence détectée, contenu non extrait | — | — | Non confirmé |

**Contrainte cachée Instant GOAT** : règle de perte flottante intraday sévère —
*"if floating PnL drops below -2% of account balance at any moment, account
permanently closed"* — mécanisme résiduel malgré l'absence d'évaluation
formelle, comme observé ailleurs (The5%ers Hyper Growth).

**Copytrade** : aucune page par format ne le mentionne. Règle générale trouvée :
copytrade interdit challenge→challenge et challenge→financé, mais comptes
financés du même trader peuvent être fusionnés ou gérés séparément — règle
globale firme, pas déclinée par format explicitement (surtout 1-step/instant
non confirmés).

---

## 5. FundedNext

**Découverte majeure** : depuis le **18/03/2025**, FundedNext ne vend plus
Express et Evaluation aux nouveaux clients — seuls les **4 modèles Stellar**
(2-Step, 1-Step, Lite, Instant) sont disponibles à l'inscription. Le doc tiers
cité en référence (quantvps.com, utilisé dans `recherche_comptes_splits_...
20260807.md`) est donc **obsolète** sur ce point — à corriger mentalement.

| Format | Phases/cibles | DD journalier/max | Trailing/statique | Durée min | Prix 200k$ | Confiance |
|---|---|---|---|---|---|---|
| Stellar 2-Step | P1 8%, P2 5% | 5%/10% | Statique | 5j/phase | 1 099,99$ | Élevée |
| **Stellar Lite (actuel projet)** | P1 8%, P2 4% | **4%/8%** (déjà corrigé dans le code) | **Statique, confirmé officiellement** | 5j/phase | 798,99$ | Élevée |
| Stellar 1-Step | 10% | 3%/6% | Statique | 2j (non consécutifs) | 1 099,99$ | Élevée |
| Stellar Instant | Pas de cible | Pas de DD journalier / **6% max, trailing** | Trailing (seul format trailing chez FundedNext) | — | Pas de palier 200k$ — **plafonné à 20k$ max** | Élevée |

**Copytrade** : confirmé en détail — autorisé entre comptes challenge du même
trader ; interdit entre traders différents ; sur compte financé, interdit sauf
entre comptes FundedNext du même trader (**plafond cumulé 300 000$**, pas
400k) ; interdit avec d'autres firms. Stellar Instant a sa propre règle :
autorisé entre comptes Stellar Instant du même trader, mais **interdit avec
Stellar 1-Step/2-Step/Lite même pour le même individu**.

**Implication directe pour le projet** : le mécanisme actuel (1 seul compte
FundedNext à 200k$, `fleet_unlocked` déclenché au dernier palier) reste
cohérent avec cette règle — un seul compte ne pose pas de problème de plafond
cumulé. Mais si un jour plusieurs comptes FundedNext étaient envisagés, le vrai
plafond à respecter est 300k$, pas 400k$ comme utilisé ailleurs dans le
projet pour d'autres firms.

---

## 6. Récapitulatif — plafonds de capital combiné (copytrade) par firm

| Firm | Plafond officiel confirmé | Valeur codée dans le projet | Écart |
|---|---|---|---|
| FTMO | 400 000$/trader (ambiguïté financé-seul vs +évaluation non tranchée) | 400 000$ | Cohérent |
| Blueberry | 2 000 000$ "per trader" (source légale officielle, mais ambiguïté cumulé vs par-compte non levée) | 450 000$ | Le chiffre codé ne correspond à aucune source officielle trouvée — reste à confirmer par écrit, voir doc 06/08 |
| GFT | 400 000$ tous modèles confondus | 400 000$ | Cohérent |
| The5%ers (Fivers) | 500 000$ (confiance moyenne, corroboré tiers + utilisateur) | **500 000$ pile** | **Pas de marge de sécurité** — l'utilisateur a mentionné une décision de plafonner à 400k pour absorber la croissance du solde des comptes ; pas appliquée dans le code |
| FundedNext | 300 000$ (comptes financés, confirmé officiellement) | Non pertinent (1 seul compte fixe) | Cohérent tant qu'un seul compte |

---

## 6bis. Statut copytrade — les 5 formats du combo gagnant de l'Étape D (vérifié 08/08, sans extrapoler depuis le 2-Step de la même firm)

Ajouté a posteriori suite à une demande de vérification explicite. Combo
gagnant testé en Étape D : FTMO 1-Step + The5%ers Hyper Growth + Blueberry
Instant Elite + GFT Instant GOAT + FundedNext Stellar 1-Step.

**Mise à jour 08/08 (suite)** : les 4 formats initialement non confirmés ont
été directement vérifiés par l'utilisateur auprès du support de chaque firm
(chat support, réponses citées ci-dessous). Ce ne sont pas des pages
officielles publiques citables par URL, mais des réponses directes et
explicites du support — traitées ici comme confirmées, à un niveau de
confiance légèrement inférieur à une page officielle publique stable (le
support peut se tromper ou changer de position), mais bien supérieur à une
règle générale extrapolée ou une source tierce.

| Format | Statut copytrade | Source | Verdict |
|---|---|---|---|
| **FTMO 1-Step** | Support FTMO (Mateo) : *"Yes. Copy trading is allowed at FTMO as long as you are personally managing the accounts and your setup does not exceed the maximum capital allocation of $400,000 ... per trader or trading strategy."* Pas de carve-out sur le 1-Step. | Réponse support FTMO, 08/08/2026 (utilisateur) | **Confirmé** — cohérent avec le plafond 400k déjà connu |
| **The5%ers Hyper Growth** | Support The5%ers : *"Copy trading is allowed on Hyper Growth instant-funding accounts only when you are copying trades from your own accounts, including other prop firm or personal accounts... copying trades between two different Bootcamp accounts is not allowed... once you manage more than $500K in capital across all accounts and programs, you are no longer permitted to copy trades."* | Réponse support The5%ers, 08/08/2026 (utilisateur) | **Confirmé spécifiquement pour Hyper Growth** — plafond 500k$ également reconfirmé par la même réponse |
| **Blueberry Instant Elite** | Support Blueberry : *"Yes, you can copy trade. You are allowed to use various copy trade software, such as Traders Connect, Duplikum, Social Trader Tools, and CopyFx, to copy trade between accounts you own... copy trading is only permitted between accounts under your ownership even if they are on different platforms."* Pas de carve-out par type de compte. | Réponse support Blueberry, 08/08/2026 (utilisateur) | **Confirmé** — réponse générale sans restriction de format mentionnée |
| **GFT Instant GOAT** | Support GFT : *"Copy trading is allowed only between your own funded accounts, including instant accounts... Copy trading is not permitted between challenge or evaluation accounts, or from an evaluation account to a funded account."* | Réponse support GFT, 08/08/2026 (utilisateur) | **Confirmé explicitement pour les comptes instant** — Instant GOAT est financé dès l'ouverture (0 phase d'évaluation), donc directement couvert |
| **FundedNext Stellar 1-Step** | Autorisé entre comptes challenge du même trader ; interdit entre traders différents ; "account merging" jusqu'à 300 000$ une fois financé. | [help.fundednext.com/en/articles/8021061](https://help.fundednext.com/en/articles/8021061) | **Confirmé officiellement (page publique)**, spécifiquement pour ce format |

**Verdict global : les 5 formats du combo gagnant ont maintenant un statut de
copytrade confirmé** — 1 via page officielle publique (FundedNext), 4 via
réponse directe du support (FTMO, The5%ers, Blueberry, GFT). Mis à jour dans
`engine_multiformat.py` (`copytrade_confirmed=True` sur les 5 FormatDef
concernés). Nuance qui reste : les réponses support ne sont pas publiques/
citables comme une page officielle, et aucune n'a été demandée par écrit
(email) pour laisser une trace formelle — recommandé avant tout capital réel
si ce combo est retenu, mais ce n'est plus un point bloquant pour continuer
le travail de simulation.

---

## 7. Points non confirmés officiellement malgré la recherche (tous firms)

1. **FTMO** : prix du compte Swing (probablement = Standard, non confirmé) ; copytrade spécifique au sous-type Swing ; plafond 400k$ financé-seul ou +évaluation.
2. **The5%ers** : grille de prix Hyper Growth/Pro Growth complète ; prix High Stakes 100k$ à jour (545$ datait de janv. 2025) ; trailing/statique de Pro Growth et Bootcamp non vérifié séparément ; quelle variante High Stakes (8%/5% vs 10%/5%) le projet a réellement souscrite.
3. **Blueberry** : **lequel de Prime Challenge (8%/6%, DD 4%/10%) ou "2-Step Challenge" standard (10%/5%, DD 5%/10%) correspond au compte réellement souscrit par le projet** — écart potentiel direct avec le code actuel (dd=5.0 codé, qui matche le standard, pas Prime) ; copytrade par format non confirmé ; prix exacts hors 25k.
4. **GFT** : incohérence non résolue sur le DD max Instant PRO (4% vs 8% trailing selon la source) ; page Instant Standard inaccessible ; grille de prix par palier/format quasi absente ; copytrade par format non confirmé.
5. **FundedNext** : détail exact des paliers de split "jusqu'à 95%" ; seuils exacts du "Tier 3" Stellar Instant (70%→80%).
6. **Transverse** : statut de copytrade CONFIRMÉ par format (pas juste par firm) reste largement non trouvé partout sauf FundedNext — seules des règles générales "au niveau firme" existent pour FTMO/Blueberry/GFT/The5%ers, jamais déclinées explicitement par format.

---

## 8. Points ouverts à traiter avant l'Étape B (refonte du moteur)

1. **Blueberry — vérifier manuellement (dashboard/contrat) quel produit 2-step est réellement souscrit** (Prime vs standard) — impacte directement si le DD journalier codé (5%) est un bug comme les précédents (Fivers, FundedNext) ou déjà correct.
2. **The5%ers — corriger le plafond `FIRM_CAPITAL_CAP["Fivers"]` (actuellement 500 000$ pile, sans marge) selon la décision de marge de sécurité à 400k mentionnée par l'utilisateur** — pas fait dans cette session (hors périmètre collecte de données), à traiter séparément ou avec la refonte.
3. **Confirmer par écrit auprès de FTMO et Blueberry** les points d'ambiguïté déjà notés en 06/08 (plafond financé-vs-évaluation FTMO, 2M$ cumulé-vs-par-compte Blueberry) si ça affecte significativement les futures simulations multi-format.
4. Le clivage trailing(instant)/statique(évaluation) confirmé sur les 5 firms (§0) simplifie la future refonte — mais vérifier qu'aucune autre exception n'existe avant de le coder comme règle générale (FTMO 1-Step est un cas limite : trailing mais recalculé seulement en fin de journée, pas un vrai trailing intraday comme les instant funding).
