# Handoff — 20/08/2026 — Intégration palladium/platinum + correction priors B_tradable

## 0. Runs interrompus (demande utilisateur, avant tout le reste)

Deux chantiers tournaient sur le VPS sur une population qui allait changer
(prior/population B) — interrompus proprement, aucune sortie partielle
utilisée :
- `chantier_multifirm_unlock_B_tradable_2026-08-20.py` (retest flotte
  multi-firms, PID 3284) — agent de recherche associé également stoppé.
- `chantier6_ev_regime_bandes_reference_2026-08-20.py` (monitoring live
  EV/regime, **Phase 1**, PID 1664).

`app.py`/`monitor.py` (production, PID 4816/7976) non touchés — hors
scope, pas des "chantiers".

Les deux retests (§7 registre, flotte multi-firms) reviendront dans un
prompt séparé, une fois cette base confirmée propre — pas relancés ici.

## 1. Intégration palladium/platinum

Source : `gaz_palladium_platine_population_trailing_2026-08-20.csv`
(n=280 : Palladium=102, Platinum=95, Natural Gas=83 — **Natural Gas exclu**,
décision déjà actée : EV non significative p=0,07, échantillon trop
mince).

Méthode : réplication exacte du pipeline gold/silver
(`or_argent_population_2026-08-19.py` → `gaz_palladium_platine_population_
2026-08-20.py`, même structure `build_extended_population` →
`tp2_realistic_payoff` → trailing 0,10×, cf. docstring du fichier) — déjà
fait en amont, cette session n'a fait que **pooler** le résultat (Pd+Pt
uniquement) avec `chantier_gold_silver_pop_B_config0_tradable_2026-08-19.
csv` (n=1051, gold/silver 7 tickers tradables), trié par `date_creation`
(ordre chronologique préservé).

**Nouvelle population B_tradable finale** :
`chantier_gold_silver_pop_B_tradable_pgp_2026-08-20.csv`, **n=1248**
(1051 + 102 Palladium + 95 Platinum).

Schéma vérifié compatible (les 9 colonnes de B_tradable sont toutes
présentes dans le CSV gaz/palladium/platine — pas de perte de colonne à
la fusion). Un souci de format de date mixte (`.000` sur les lignes
Pd/Pt vs sans décimales sur B_tradable) a été trouvé et corrigé en
resauvegardant le CSV fusionné (pandas normalise l'écriture) — sinon
`pd.to_datetime` échoue silencieusement sur `format='mixed'` non passé.

Tradabilité BB des 2 tickers **pas revérifiée** (déjà confirmée
précédemment sur le même compte que gold/silver, comme demandé).

## 2. Priors ALPHA_POST_B / BETA_POST_B — état antérieur vérifié par citation

**Réponse à la question posée (item 1 de la demande)** : le calcul cascade
n'utilise PAS 276/297 quand B_tradable est active — ce bug-là était déjà
corrigé le 08/19 (`registre_parametres_projet.md:4629-4643`, §9.6
"RÉOUVERTURE RÉSOLUE"). Mais la situation réelle est plus nuancée qu'un
simple oui/non, et **n'était pas encore complètement propre avant ce
chantier** :

- `chantier_b6_montecarlo_2026-08-19.py` : `ALPHA_POST_B, BETA_POST_B =
  276, 297` — reste correct **pour son propre périmètre** (B sans métaux,
  571 trades), documenté comme tel (`registre_parametres_projet.md:4642-
  4643`). N'est pas le moteur cascade officiel, hors scope ici.
- `chantier_ab_metaux_cascade_officiel_2026-08-19.py:130` : `ALPHA_POST_B_
  METAUX, BETA_POST_B_METAUX = 762, 745` — déjà dérivé correctement, mais
  **sur le pool métaux COMPLET 14 tickers** (n=1505,
  `chantier_gold_silver_pop_B_config0_2026-08-19.csv`, chargé par défaut
  dans `build_pop_B()` ligne 746) — **pas sur B_tradable** (7 tickers,
  n=1051, la population réellement retenue pour le lancement, §6.5 du
  registre stratégie). Le prior spécifique à B_tradable
  (`ALPHA_POST_B_TRADABLE=533, BETA_POST_B_TRADABLE=520`) n'était branché
  que via le wrapper `chantier_ab_metaux_tradable_config2_2026-08-19.py` —
  **le fichier "officiel" lui-même, invoqué nu, restait désaligné avec la
  population de lancement réelle**. Cet écart préexistait déjà avant ce
  chantier-ci, indépendamment de palladium/platine — pas un nouveau bug
  introduit aujourd'hui, mais confirmé pour la première fois par cette
  vérification.

## 3. Prior corrigé sur la population finale

Même méthode que celle ayant produit 533/520 (Beta(1,1) + wins/losses
observés, `wins+1`/`losses+1`) appliquée à la population finale (n=1248) :

- wins = 624 (532 B_tradable + 92 Pd/Pt, `statut_final == "OBJECTIF
  ATTEINT"`)
- losses = 624 (519 B_tradable + 105 Pd/Pt, `statut_final == "INVALIDÉE"`)
- somme = 1248 = n (aucun trade non résolu dans la population finale)

**→ ALPHA_POST_B_TRADABLE_PGP = 625, BETA_POST_B_TRADABLE_PGP = 625**
(winrate exactement 50,00% — coïncidence numérique, vérifiée par calcul
direct, pas une erreur d'arrondi).

## 4. Branchement dans le moteur cascade officiel

Nouveau wrapper `chantier_ab_metaux_tradable_pgp_2026-08-20.py` (même
pattern que `chantier_ab_metaux_tradable_config2_2026-08-19.py` :
`importlib` charge `chantier_ab_metaux_cascade_officiel_2026-08-19.py`
comme module, puis remplace `build_pop_B` + `ALPHA_POST_B_METAUX`/
`BETA_POST_B_METAUX`). Le fichier "officiel" lui-même **n'a pas été
modifié en place** (cohérent avec la convention du projet — les
corrections successives ont toujours été branchées par wrapper, jamais en
mutant le fichier de référence — ses défauts nus restent le pool 14
tickers/762,745, à traiter comme un point de vigilance séparé si quelqu'un
l'invoque directement sans wrapper).

Exécuté et vérifié (`python chantier_ab_metaux_tradable_pgp_2026-08-20.py`) :
```
Population B_tradable+Pd+Pt branchee dans le moteur officiel : n=1248
wins=624 losses=624 (somme=1248, doit valoir n)
Prior branche : Beta(625, 625)
OK -- moteur cascade officiel pret avec population+prior corriges.
```

## Ce qui n'a PAS été fait (hors scope explicite de la demande)

- Aucun run n=300/n=600 sur cette nouvelle base (préparation seule).
- Aucune modification de `registre_strategie_trading.md` ni
  `registre_parametres_projet.md` — consolidation = décision utilisateur
  séparée.
- Aucun commit git.

## Points ouverts pour la suite

1. `chantier_ab_metaux_cascade_officiel_2026-08-19.py` invoqué SANS
   wrapper reste sur le pool 14-tickers/762,745 (pas B_tradable) — risque
   de confusion si un futur script importe le fichier officiel directement
   sans passer par un wrapper à jour. À surveiller.
2. Les retests différés (flotte multi-firms §7, monitoring Phase 1)
   doivent repartir sur `chantier_ab_metaux_tradable_pgp_2026-08-20.py`
   (n=1248, Beta(625,625)) et non sur `chantier_ab_metaux_tradable_
   config2_2026-08-19.py` (n=1051, Beta(533,520)) désormais périmé pour
   tout usage incluant palladium/platine.
