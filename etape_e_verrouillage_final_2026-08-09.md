# Étape E — Verrouillage final (08/09/2026)

*Consolide `etape_e_integration_rapport.md` (figé) et `etape_e_audit_2026-08-09.md`
(figé) avec les deux dernières vérifications : plafond 3000$ pour les
nouveaux points de risque, et cascade check complet sur ces mêmes points.
Nouveau fichier séparé, convention habituelle.*

---

## Tableau final — les deux points de risque candidats, complets

n=600, config REF (100% 2-step : FTMO 2-Step Swing, The5%ers High Stakes,
Blueberry Prime Challenge, GFT 2-Step GOAT, FundedNext Stellar Lite),
déblocage échelonné + comptes supplémentaires + fiscalité réelle.

| Point | Plafond | Profit | Ruine | Année1<0 | Casse≤30j | Casse≤60j | Réserve min. 6 mois | Quasi-gelé | Cascade |
|---|---|---|---|---|---|---|---|---|---|
| **éval=1,25%/flotte=1,90%** | 1000$ | 4 663 331$ | 2,83% | 26,7% | 24,0% | 42,9% | 0$ | 2,0% | GO |
| **éval=1,25%/flotte=1,90%** | 3000$ | 4 756 842$ | 0,50% | 25,7% | 24,1% | 43,0% | 0$ | 0,17% | GO |
| **éval=1,00%/flotte=1,90%** | 1000$ | 4 579 059$ | 0,83% | 27,8% | 21,1% | 38,6% | 0$ | 1,0% | GO |
| **éval=1,00%/flotte=1,90%** | 3000$ | 4 584 524$ | 0,67% | 27,8% | 21,1% | 38,6% | 0$ | 0,0% | GO |

**Les deux points passent le cascade check sans réserve.** Aucune surprise
cachée derrière le profit/ruine — contrairement au combo WINNER de l'Étape
D, où un meilleur profit/ruine apparent masquait un vrai problème de
cascade. Ici, le cascade check confirme plutôt qu'il ne contredit les
métriques profit/ruine.

## Comment choisir entre les deux

- **éval=1,25%/flotte=1,90%** : profit le plus élevé (+1,8% à +2,0% selon
  le plafond), ruine et cascade légèrement moins bons que l'autre option
  mais toujours sains.
- **éval=1,00%/flotte=1,90%** : ruine plus basse au plafond 1000$ (0,83%
  vs 2,83%, 3,4x plus faible) pour seulement -1,8% de profit, ET un
  profil de cascade globalement plus stable (casse ≤30j/≤60j nettement
  plus basse : 21,1%/38,6% vs 24,0%/42,9%) — pas seulement un compromis
  sur la ruine finale, une flotte qui respire mieux tout du long.

**Recommandation** : sauf préférence explicite pour le profit maximal au
prix d'un peu plus de fragilité, **éval=1,00%/flotte=1,90% est le choix le
mieux équilibré** — meilleur sur ruine ET cascade pour un coût de profit
marginal.

## Point 3 — Intégrité des chiffres déjà rapportés

Vérifié par lecture de code : les clés `tax_breach_*` corrigées ne sont
lues que dans la branche `overflow > 1e-9` de
`split_tax_model.handle_tax_payment` (seul endroit où le bug pouvait
provoquer un crash) et ne sont référencées nulle part ailleurs — ni dans
le dict retourné par `run_one`, ni dans l'agrégation des scripts
appelants. **Le bug ne peut produire qu'un plantage immédiat, jamais un
résultat silencieusement faux.** Tout run qui s'est terminé avec succès
n'a donc jamais emprunté ce chemin. Le seul run affecté (premier essai de
`risk_sweep_and_year1.py`, planté au 8ᵉ combo) n'a produit aucune sortie
utilisée et a été intégralement relancé après correction. **Aucun chiffre
de cette session n'est à refaire pour cette raison.**

---

## État final de l'Étape E — ce qui est verrouillé

1. **Le combo gagnant de l'Étape D reste rejeté** — confirmé et renforcé
   par l'ensemble de cette session (profit, ruine, ET cascade en faveur de
   REF).
2. **Nouvelle référence REF, remplace le chiffre provisoire précédent
   (4 297 185$/4 388 789$)** :
   - Profit max : **4 663 331$ (1000$) / 4 756 842$ (3000$)**, risque
     éval=1,25%/flotte=1,90%
   - Équilibré (recommandé) : **4 579 059$ (1000$) / 4 584 524$ (3000$)**,
     risque éval=1,00%/flotte=1,90%
3. **Ne remplace toujours PAS le chiffre verrouillé officiel du projet**
   (5 794 566$/5 898 897$, moteur 1-phase) — reste une décision séparée à
   prendre explicitement, pas automatique (moteur différent, risque
   recalibré différemment).

## Points ouverts restants (hors périmètre de cette session)

- Ambiguïté Blueberry Prime vs Standard (impact <1%, déjà mesuré,
  toujours à trancher par vérification du compte réel avant capital réel)
- Risque de WINNER non re-affiné avec la grille fine (sans impact sur le
  verdict, WINNER perdait déjà)
- Mécanisme de croissance Hyper Growth simplifié (voir rapport initial
  §1.5) — non pertinent tant que WINNER n'est pas reconsidéré
