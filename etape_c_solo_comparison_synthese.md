# Étape C — Comparaison solo par format (n=300, résultats bruts dans `etape_c_solo_comparison_results.csv`)

*Simulation solo (1 compte, pas de flotte, pas d'interaction de trésorerie).
Risque 2,25% en évaluation, 2,75% une fois financé (cohérent avec la config
verrouillée). Horizon simulé 1456j (~4 ans). "Coût connu" = prix trouvé à
l'Étape A ; sinon coût affiché à 0$ (pas un vrai 0, juste non chiffré —
exclure ces lignes de toute comparaison économique).*

**Ne conclut PAS sur quel format est "meilleur"** — ces chiffres solo ne
disent rien de la performance en flotte (vitesse de refinancement,
interactions de trésorerie) — c'est l'objet de l'Étape D à venir.

## Résumé par firm

| Firm | Format | Phases | DD | Palier | Délai financement | Coût connu | Casses post-financement (moyenne sur l'horizon) |
|---|---|---|---|---|---|---|---|
| FTMO | 2-Step (Standard/Swing) | 2 | statique | 100k | 58,8j | 713$ | 15,2 |
| FTMO | 1-Step | 1 | trailing_eod | 100k | 23,6j | 813$ | 24,0 |
| The5%ers | High Stakes | 2 | statique | 100k | 53,9j | 903$ | 16,6 |
| The5%ers | Hyper Growth | 1 | trailing_peak | 10k | 23,6j | 543$ | 34,1 |
| The5%ers | Pro Growth | 1 | statique | 100k | 26,8j | inconnu | 23,9 |
| Blueberry | Prime 2-Step | 2 | statique | 25k | 71,7j | 434$ | 13,7 |
| Blueberry | 2-Step standard | 2 | statique | 25k | 56,9j | inconnu | 16,3 |
| Blueberry | 1-Step | 1 | statique | 25k | 26,8j | inconnu | 23,8 |
| Blueberry | Instant Elite | 0 | trailing_peak (lock 10%) | 25k | 0j | 800$ | **1,4** |
| Blueberry | Instant Lite | 0 | trailing_peak (lock 4%) | 25k | 0j | 185$ | **316,1** |
| GFT | 2-Step GOAT | 2 | statique | 100k | 55,9j | inconnu | 16,4 |
| GFT | 2-Step Standard | 2 | statique | 100k | 56,9j | inconnu | 16,3 |
| GFT | 3-Step | 3 | statique | 100k | 57,8j | inconnu | 16,5 |
| GFT | 1-Step | 1 | statique | 100k | 26,8j | inconnu | 23,9 |
| GFT | Instant GOAT | 0 | trailing_peak | 100k | 0j | inconnu | 71,2 |
| GFT | Instant PRO | 0 | trailing_peak | 100k | 0j | inconnu | 127,1 |
| FundedNext | Stellar 2-Step | 2 | statique | 200k | 62,1j | 1830$ | 14,6 |
| FundedNext | Stellar Lite (actuel) | 2 | statique | 200k | 71,3j | 2242$ | 14,1 |
| FundedNext | Stellar 1-Step | 1 | statique | 200k | 24,3j | 2035$ | 24,1 |
| FundedNext | Stellar Instant | 0 | trailing_peak | **20k (plafond réel, pas comparable directement à 200k)** | 0j | inconnu | 63,8 |

## Lectures factuelles (pas de verdict)

- **1-step vs 2-step, sur toutes les firms** : le 1-step finance ~2x plus
  vite (24-27j vs 54-72j) mais casse ~1,5x plus souvent une fois financé
  (23-24 casses vs 13-17 sur l'horizon). Cohérent avec un DD max plus serré
  en 1-step partout (6-10% vs 8-10% en 2-step, sur une seule phase au lieu
  de deux à franchir).
- **Instant funding, très hétérogène selon la firm/sous-format** : Blueberry
  Instant Elite est de loin le plus stable de tout le tableau (1,4 casses,
  DD max 10% avec verrouillage tardif à 10% de profit) ; à l'opposé,
  Blueberry Instant Lite (316 casses) et GFT Instant PRO (127 casses) sont
  extrêmement fragiles — leur DD max étroit (4%) combiné au verrouillage
  précoce laisse très peu de marge une fois le plancher gelé.
- **3-Step GFT** proche du 2-Step sur tous les indicateurs (57,8j, 16,5
  casses) — pas de différence marquante malgré la phase supplémentaire.
- **Coûts** : les données de prix restent incomplètes pour GFT (aucun prix
  officiel trouvé pour aucun format à l'Étape A) et pour plusieurs formats
  secondaires Blueberry/The5%ers — comparaison économique impossible tant
  que ces prix ne sont pas sourcés.

## Ce que ces chiffres ne disent PAS

- Pas d'effet de trésorerie flotte (un format qui finance vite libère du
  cash plus tôt pour refinancer d'autres comptes — invisible en solo).
- Pas de coût d'échec cumulé réel pour les formats à prix inconnu.
- Le "taux de casse post-financement" est mesuré sur tout l'horizon
  restant après le 1er financement, pas un taux annualisé — les formats
  financés plus tôt (1-step, instant) ont mécaniquement plus de temps pour
  accumuler des casses, donc les compter en absolu sur-pénalise les formats
  rapides. À corriger (taux par an, ou par unité de temps financé) avant
  toute conclusion sérieuse en Étape D.
