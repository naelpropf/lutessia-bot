# Contexte projet trading Lutessia — v3, 7 août 2026

Remplace `contexte_projet_lutessia_2026-08-05_v2.md` (et toute version antérieure)
comme mémoire de reprise. Conserve tout ce qui était déjà validé en v2 (section 1-2),
ajoute l'intégralité des découvertes de la session du 06-07/08 (optimisation
stratégie, séquençage de lancement, et surtout la découverte critique sur le
mécanisme d'immunité — section 0, à lire en premier).

---

## 0. ⚠️ POINTS CRITIQUES — À LIRE EN PREMIER

### 0.1 — Chiffres de profit encore BRUTS (split + fiscalité non intégrés)

**Aucune simulation à ce jour n'a intégré :**
- Le split prop firm (typiquement 80/20 → 90/10 selon la firm et le palier, jamais
  appliqué aux profits calculés dans tout ce projet)
- La fiscalité (régime non confirmé — statut du trader, IR vs société, prélèvements
  sociaux — nécessite un expert-comptable)

**Risque identifié, similaire au "trou silencieux" du mécanisme d'immunité (0.3)** :
un prélèvement fiscal/social périodique pourrait ponctionner la réserve poolée au
mauvais moment et forcer un dépassement du plafond de risque personnel déjà fixé —
non modélisé.

**Tant que ce point n'est pas tranché, tout chiffre de profit de ce document (et de
tous les scripts de simulation du projet) doit être traité comme BRUT — potentiellement
surestimé de 10-20%+ une fois split et fiscalité appliqués.** Priorité absolue avant
tout lancement de capital réel.

### 0.2 — Le cash pire cas officiel est maintenant 3 000$ (règle hybride), PAS 2 988$/3 154$

Découverte majeure de la session : l'ancien "cash pire cas" (2 988$/3 154$, cf.
section 3) était une **fiction comptable**. Le moteur de simulation calcule bien un
déficit de réserve (`shortfall`) à chaque casse survenant après le premier
financement de la flotte, mais il ne le facture JAMAIS au cash personnel — il
suppose implicitement que les profits futurs combleront ce trou, sans jamais
vérifier si c'est réellement le cas.

**Deux politiques réelles testées pour remplacer cette hypothèse :**
- **"Attente"** : le rachat est retardé jusqu'à ce que la réserve suffise (le compte
  reste fermé entre-temps). Cash pire cas garanti à **166$** (prix du 1er challenge,
  borne mathématique), mais profit final divisé par ~3 et année 1 négative en médiane.
- **"Avance perso"** : le déficit est payé immédiatement, toujours. Profit préservé
  intégralement, mais cash pire cas réel révélé : **132 256$ / 139 765$** (40,09%/37,66%)
  dans les scénarios extrêmes — c'est le vrai risque que l'ancienne hypothèse masquait.

**Règle retenue : hybride** — avance personnelle jusqu'à un plafond défini, puis
bascule en "attente" au-delà (le plafond n'est jamais dépassé, par construction,
vérifié empiriquement sur 2000 runs). Balayage du plafond {500$ à 10 000$} : coude
net de la courbe gain-marginal/risque entre 2 000$ et 3 000$ (le gain marginal chute
d'un facteur ~4,5 à ce point ; à 3 000$, le plafond n'est même atteint que dans 46,5%
des runs — plus de la moitié de la distribution naturelle reste déjà en dessous).

**Plafond optimal statistique : 3 000$** → profit final 9 871 402$/7 832 915$ (82-83%
du profit maximal théorique).

### 0.3 — MAIS le budget réel disponible est 1000€, pas 3000$

Le plafond optimal statistique (3000$) suppose un budget disponible de cet ordre.
**Le budget personnel réellement disponible (capital familial) est 1000€.** Chiffrage
déjà fait à ce plafond : profit final **7 837 470$** (vs 9 871 402$ à 3000$, soit
**-20,6%**).

**Piste ouverte, non encore chiffrée** : démarrer avec un plafond hybride à 1000$,
puis AUGMENTER progressivement ce plafond au fur et à mesure que la réserve du
projet lui-même grossit (pas via un nouvel apport personnel) — logique similaire à
la bascule par seuil de réserve déjà validée pour FXIFY/Ment Funding (section 5.4).
Reste à modéliser précisément : à quel rythme/seuil de réserve le plafond personnel
peut-il être remonté sans jamais re-solliciter le budget familial au-delà de 1000€ ?

---

## 1. Stratégie de trading — configuration verrouillée (mise à jour 06-07/08)

- **Seuil d'entrée : RR≥1,25** (CHANGÉ — était 1,5). Découverte majeure : domine
  largement RR≥1,5 en Monte Carlo flotte complet malgré une EV brute par trade plus
  faible (+0,97R vs +0,91R) — la fréquence de trades plus élevée (646 vs 472 sur
  l'échantillon) compense largement via l'effet de compounding. **+43,5% de profit
  final, P(an1<0) 4x meilleure**, pour seulement +16,7% de cash pire cas (avant prise
  en compte de 0.2).
- **Trailing stop post-TP2 : 0,15×SL** (CHANGÉ — était 0,2×SL)
- **Winrate réel de référence : 40,09%** (n=646, 259 gagnants, population RR≥1,25) —
  REMPLACE 37,29% (n=472, RR≥1,5, désormais obsolète pour toute nouvelle simulation)
- **P10 bayésien recalibré : 37,66%** (posterior Beta(260,388), prior uniforme
  Beta(1,1), méthode vérifiée par reproduction de l'IC95% historique connu) —
  REMPLACE 32% (calibré sur l'ancien échantillon n=472, ne plus utiliser)
- **Risque par trade : rampe 2,0% × 5 premiers trades par compte, puis 2,5%** (CHANGÉ
  — remplace le ramp 0,5%×12 trades historique). Améliore profit ET P(perte)
  simultanément. Au-delà de 2,5%, effet de falaise (3% touche le daily DD The5%ers
  3% avec zéro marge de sécurité — casses et P(perte) explosent).
- **Plafond de positions simultanées : 3, corrélation 0,6+JPY** — INCHANGÉ, confirmé
  optimal (maxpos=2/corr=0,7 dégrade en fait la performance sous la nouvelle
  population RR≥1,25, contrairement à ce qui semblait vrai sous l'ancienne
  population — ne jamais réutiliser cette combinaison)
- Cette combinaison (RR1,25/trail0,15/maxpos3/corr0,6/rampe2,0%×5) est un optimum
  conjoint vérifié — testé contre de nombreuses combinaisons alternatives, aucune ne
  fait mieux sur l'ensemble profit/cash/P(perte).

## 2. Séquence de lancement définitive

**Blueberry SEULE (palier réduit 25k) au jour 0** — remplace toute séquence
précédente (FTMO seule day0 était un faux optimum : son format inclut nativement 2
comptes, doublant l'exposition day0 sans que ça ait été identifié avant cette
session). Comparaison des 5 firms testées seules : Blueberry ET FundedNext
(1 compte) sont à égalité au meilleur niveau (cash pire cas ~50% inférieur à FTMO
seule), Blueberry retenue car aucune incertitude réglementaire (contrairement à
FundedNext, voir 5.3).

**Reste de la flotte (FTMO + The5%ers + GFT + FundedNext si activée) activé
ENSEMBLE dès le premier financement Blueberry** — déclencheur ÉVÉNEMENTIEL
uniquement (jamais un délai calendaire fixe : testé, ~3x plus risqué en cash pire
cas pour un gain de profit <1% ; jamais un seuil de réserve non plus : testé,
toujours dominé par l'événementiel, même cash mais délai plus long et profit
légèrement inférieur).

Délai médian pour atteindre la structure complète : ~32 jours (1er mois). Sous 2000
simulations : 100% des runs atteignent le seuil de réserve FXIFY (50k$) et Ment
Funding (20k$) DÈS l'année 1 (médiane mois 2-3) — la structure génère assez de
réserve poolée pour ces extensions très tôt.

**Plancher structurel du cash pire cas (hors régle hybride, cf. 0.2)** : le cash est
un multiple exact du coût du challenge le moins cher (166$ pour Blueberry 25k) —
médiane = 166$ (aucune casse dans plus de la moitié des runs), le plancher absolu
incompressible est ce prix d'entrée, tout le reste vient des casses avant le tout
premier financement de la flotte (risque de queue probabiliste).

## 3. Historique — ce qui a changé depuis la v2 (05/08)

- Régime A (2% risque uniforme) verrouillé en v2 → **remplacé par RR1,25/trail0,15/
  rampe2,0%×5→2,5%** (section 1), verdict re-testé et confirmé robuste (autre seed,
  5000 runs, bornes IC winrate 32,9-41,7%, stress RR -10/-20%, slippage réel intégré
  — le classement tient dans TOUS les cas)
- Cash pire cas ancien 39 046$/43 406$ (3 firms day0, The5%ers non retardée) →
  9 324$ (FTMO seule day0, The5%ers+reste ensemble après 1er fin.) → **9 324$→4 662$
  (Blueberry seule remplace FTMO)** → **2 988$/3 154$ (+ 1er palier 25k, ancien
  modèle)** → **finalement 3 000$ sous la règle hybride réaliste (0.2), 132 256$ dans
  le pire cas si on ignore la contrainte de liquidité**
- Correction FTMO : plafonds réels confirmés (200k$/compte max, jamais 500k$, vraie
  séquence 50k→100k→200k avec palier 100k intermédiaire absent de l'ancien modèle) —
  impact $ marginal (FIRM_CAP=400k bloquait déjà 500k), impact sur la cadence
  casses/upgrades plus significatif
- Pyramiding et Kelly/ATR : déjà rejetés le 30/07 (régime antérieur, sans daily DD),
  **re-testés sous la config actuelle (daily DD + 3-firms + RR1,25) — rejet confirmé
  et renforcé** (Kelly prescrit un risque moyen 5,3-10,6%, largement au-dessus de la
  falaise 3% découverte cette session ; pyramiding toujours structurellement perdant)
- Fermeture forcée 24h/week-end : testée globalement (coûte -18% de profit, aucun
  bénéfice de cash — à écarter pour les firms déjà en place) et sélectivement pour
  une firm hypothétique future nécessitant cette contrainte (gain net réel mais pas
  gratuit : même risque de cash qu'une firm normale, juste moins de profit)
- Swap/rollover/gap week-end : durée de détention réelle très courte (médiane 7,6h,
  8,7% des trades >24h) — contredit l'hypothèse initiale de détention longue ;
  impact swap estimé (non sourcé précisément) ~1,8% du profit total, petit mais pas
  strictement nul
- Slippage réel (Dukascopy) déjà mesuré et intégré au re-test de robustesse : ne
  change pas le classement des niveaux de risque

## 4. Prop firms — statut définitif

| Firm | Statut | Daily DD | Palier max/plafond | Notes |
|---|---|---|---|---|
| Blueberry Funded | **Firm de démarrage (jour 0)** | 5% | 200k$/compte, 400k$ combiné | 25k$ initial, séquence 25k→50k→100k→200k |
| FTMO | Retenu, activé après 1er financement BB | 5% | 200k$/compte (JAMAIS 500k), 400k$ combiné (2 comptes) | Séquence corrigée 50k→100k→200k |
| The5%ers | Retenu, activé après 1er financement BB | 3% (plus strict) | 100k$ fixe, jamais upgradé | Prix réaliste 179$→545$ à 26j (Summer Plan) |
| Goat Funded Trader (GFT) | **Nouveau, confirmé support** | 4% | 400k$ combiné, ouverture séquentielle (pas de bundle façon Summer Plan) | Prix approximés sur modèle FTMO, non sourcés précisément |
| FundedNext | **Nouveau, hypothèse basse — 1 SEUL compte** | 5% (Stellar 2-Step) | 200k$ (mono-compte) | ⚠️ Copytrade confirmé INTERDIT entre comptes financés — clarification en attente sur un compte unique piloté par le même bot (pas de copie entre comptes FundedNext) |
| FXIFY | Extension future, seuil réserve 50k$ | 4% | 805 000$ combiné (8 paliers distincts) | Bascule par seuil déjà validée, élimine le risque de cash du lancement immédiat |
| Ment Funding | Extension future, seuil réserve 20k$ | 2,5-5% selon palier | Plafond combiné réel non confirmé (borne basse : 1×2M$) | Type de DD (statique/trailing) non tranché avec certitude |

## 5. Points ouverts, par priorité

1. **[PRIORITÉ ABSOLUE] Split prop firm + fiscalité non intégrés** (section 0.1) —
   tous les chiffres de profit sont bruts tant que ce n'est pas tranché
2. **Réconcilier plafond hybride optimal (3000$) avec budget réel (1000€)** — piste
   de plafond progressif via la réserve du projet, pas encore chiffrée (section 0.3)
3. Clarification support FundedNext sur la portée exacte de l'interdiction copytrade
   (1 seul compte vs plusieurs comptes FundedNext) — réponse en attente
4. Plafond de capital combiné Ment Funding non confirmé — contacter leur support
5. Type de max drawdown Ment Funding (statique vs trailing) non tranché avec
   certitude (2 sources sur 3 en faveur de trailing, utilisé par défaut)
6. Taux de swap réel non sourcé précisément (impact jugé petit mais non nul, ~1,8%
   du profit total)
7. **Écart entre la config verrouillée par simulation et le bot LIVE actuel** :
   `app.py` utilise encore `MIN_RR = 1.5` (pas 1,25) ; le trailing stop live est
   câblé à 0,2×SL (pas 0,15×SL, cf. `trade_logger.py`) ; le sizing live
   (`RISK_PCT_PER_TRADE` dans `app_mt5.py`) n'a jamais été mis à jour vers le régime
   rampe 2,0%×5→2,5%. **Ces changements de paramètres live n'ont PAS été appliqués
   automatiquement lors de cette session — décision explicite à prendre avant de les
   répercuter dans le code de trading réel** (risque direct sur l'argent réel,
   contrairement aux scripts de simulation).

## 6. Fichiers de référence (état au 07/08/2026)

**Moteurs de simulation à jour, à utiliser pour toute nouvelle analyse** :
- `robustness_5ers_risk_challenge.py` — moteur de base (FTMO corrigé, immunité
  globale, ramp/risque paramétrables), importé par la plupart des scripts suivants
- `point3a_ramp_fixed.py` — rampe de risque correcte (bypass le ramp interne
  hardcodé de l'ancien moteur, bug corrigé en session)
- `point123_startingfirm_optimization.py` — comparaison des firms de démarrage,
  GROUP_DEFS = source de vérité pour les paramètres de chaque firm (paliers, DD,
  coûts, plafonds)
- `point_liquidity_hybrid.py` — moteur de la règle hybride avance/attente,
  RÉFÉRENCE OFFICIELLE pour tout calcul de cash pire cas désormais
- `point_roadmap_year1.py` — feuille de route mensuelle année 1

**Obsolètes, ne plus utiliser comme référence** :
- Tout ce qui utilise RR≥1,5/trailing 0,2×SL comme population (winrate 37,29%,
  P10 32%) — remplacé par RR≥1,25/trailing 0,15×SL (winrate 40,09%, P10 37,66%)
- `three_firm_fleet_dailydd.py`, `hybrid_reserve_switch_test.py` et tout ce qui
  précède la découverte du biais FTMO 2-comptes-day0 — cash pire cas obsolète
- Toute mention de 2 988$/3 154$ ou de 39 046$/43 406$ comme "cash pire cas" —
  remplacé définitivement par 3 000$ (règle hybride, sous réserve du budget réel
  1000€, section 0.2-0.3)
