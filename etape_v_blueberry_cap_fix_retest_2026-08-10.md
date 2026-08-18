# Étape V (08/10 nuit, suite 5) — Correction du cap Blueberry et retest REF+V2/piste A'

Suite à la vérification empirique (§2.16, `etape_u`) qui a scindé le point
en deux : cap $ (450k codé vs 400k réel) jamais sollicité, cap NOMBRE (3
codé vs aucune limite réelle) sollicité dans 92,7-100% des runs. Cette
étape applique la correction et mesure l'impact réel plutôt que de le
supposer.

## 1. Correction appliquée

`etape_e_fleet_integration.py:112-113` (module `ei` importé par TOUS les
scripts de production, y compris `etape_q_v2_plus_ftmo_gft_2026-08-10.py`
= REF+V2 officiel, `etape_t`/`etape_u` = piste A') :

```python
# AVANT
FIRM_CAPITAL_CAP = {"Blueberry": 450000.0, "FTMO": 400000.0, "GFT": 400000.0, "Fivers": 500000.0}
FIRM_MAX_ACCOUNTS = {"Blueberry": 3, "FTMO": None, "GFT": None, "Fivers": 5}

# APRÈS
FIRM_CAPITAL_CAP = {"Blueberry": 400000.0, "FTMO": 400000.0, "GFT": 400000.0, "Fivers": 500000.0}
FIRM_MAX_ACCOUNTS = {"Blueberry": None, "FTMO": None, "GFT": None, "Fivers": 5}
```

FTMO/GFT/Fivers **non touchés** — leurs caps n'ont pas été vérifiés par un
contact support direct équivalent, ne pas généraliser sans vérification
propre (commentaire ajouté dans le code à cet effet).

## 2. REF+V2 (référence officielle) — n=600 + cascade check

Avant/après mesurés au MÊME seed (9999), même n, via un driver dédié
(`etape_v_blueberry_cap_retest_driver.py`) qui isole la config
"REF_V2 + (a)+(b) combine" de `etape_q`. Le chiffre "avant" à 1000$
(4 927 916$/0,83%/21,00%) reproduit EXACTEMENT la référence déjà
verrouillée du registre — validation croisée.

| Plafond | Avant (verrouillé) | Après (corrigé) | Δ profit | Δ ruine | Δ année1<0 |
|---|---|---|---|---|---|
| 1000$ | 4 927 916$ / 0,83% / 21,00% | **5 736 759$ / 1,00% / 21,83%** | **+808 843$ (+16,41%)** | +0,17pt | +0,83pt |
| 3000$ | 4 936 929$ / 0,50% / 21,00% | **5 751 134$ / 0,50% / 21,83%** | **+814 205$ (+16,49%)** | 0,00pt | +0,83pt |

Cascade check propre : casse≤30j LÉGÈREMENT MEILLEURE (22,72%→21,67% /
22,74%→21,68%), quasi_gelé quasi inchangé (0,67%→0,83% / 0,33%→0,33%).
Aucune anomalie.

## 3. Piste A' (solo_BB, BBx2) — n=300 screening (pas encore n=600)

| Config | Plafond | Avant | Après | Δ profit |
|---|---|---|---|---|
| solo_BB | 1000$ | 5 005 612$/1,67%/20,33% | 5 842 728$/1,67%/20,67% | +837 116$ (+16,72%) |
| solo_BB | 3000$ | 5 084 496$/0,33%/19,67% | 5 915 842$/0,67%/20,33% | +831 346$ (+16,35%) |
| BBx2 | 1000$ | 4 722 355$/8,00%/21,67% | 5 707 817$/7,67%/21,33% | +985 462$ (+20,87%) |
| BBx2 | 3000$ | 5 129 226$/0,33%/16,67% | 6 182 876$/0,33%/16,33% | +1 053 650$ (+20,54%) |

**Verdicts qualitatifs INCHANGÉS, l'un des deux RENFORCÉ :**
- **1000$ : BBx2 reste REJETÉ** — solo_BB (5 842 728$/1,67%/20,67%)
  bat toujours BBx2 (5 707 817$/7,67%/21,33%) sur les 3 axes. Écart de
  ruine quasiment identique avant/après (8,00%→7,67%) : la correction
  du cap n'aide pas le mécanisme de verrou de trésorerie initial
  (celui-ci est déterminé par le coût jour 0 vs plafond, pas par le
  plafond de croissance ultérieur).
- **3000$ : BBx2 reste CONFIRMÉ, et l'écart se creuse.** Avant : profit
  +0,88% / ruine égale / année1<0 -3,00pt vs solo_BB. Après : profit
  **+4,51%** / ruine **meilleure** (0,33% vs 0,67%) / année1<0 -4,00pt.
  BBx2 bénéficie DAVANTAGE de la correction que solo_BB (2 starters
  Blueberry au lieu d'1 profitent tous les deux du déplafonnement).

**Pas encore confirmé n=600+cascade pour piste A'** — recommandé comme
prochaine étape avant d'adopter formellement ces chiffres, par cohérence
avec la confirmation déjà faite pour REF+V2 ci-dessus.

## Verdict global : MAJEUR, pas négligeable ni juste significatif

**+16,4% à +16,5% de profit sur REF+V2** (confirmé n=600+cascade, écart
quasi identique aux deux plafonds — signal fort, pas du bruit), **+16,3%
à +20,9% sur solo_BB/BBx2** (n=300, cohérent avec REF+V2). Ruine et
année1<0 bougent très peu en absolu (+0,17 à +0,83pt) — le gain de profit
n'est pas un arbitrage risque/profit, c'est un déblocage pur de capacité
de croissance auparavant artificiellement plafonnée.

**Pour référence, c'est le plus gros effet mesuré sur l'ensemble du
chantier** — plus grand que tous les leviers structurels confirmés
combinés (reset Blueberry +3%, bootstrap parallèle jusqu'à +4,2%, sizing
DD V2 +0,93%, FTMO-10%/Goat Guard +1,2%). Ce n'était pas un levier au
sens propre (aucun choix de trading/structure) mais la correction d'un
paramètre codé en dur qui ne correspondait pas à la réalité — d'où
l'ampleur : le moteur sous-estimait Blueberry depuis l'introduction du
mécanisme extra-compte (08/08).

**Conformément à la consigne : le registre n'a PAS été mis à jour comme
nouvelle référence officielle.** Le chiffre verrouillé actuel
(4 927 916$/0,83%/21,00% à 1000$) reste affiché comme référence dans
`registre_parametres_projet.md` §1.8, avec une note pointant vers ce
rapport et vers la décision ouverte §4#11 (mise à jour, maintenant
quantifiée). Adoption formelle laissée à la décision de l'utilisateur.
