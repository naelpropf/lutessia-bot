# Diagnostic — flotte gelée après épuisement plafond+fonds d'urgence (2026-08-23)

## CORRECTIF (2026-08-23, suite) : CE N'EST PAS UN BUG

Ce fichier affirmait initialement qu'il s'agissait d'un bug ("emergency
bootstrap inopérant"). Après vérification plus poussée du code, cette
conclusion est **fausse et corrigée ici** — voir section "Verdict final"
en bas. Le contenu original est conservé ci-dessous pour la traçabilité de
l'investigation, mais NE PAS le prendre comme un verdict.

## Résumé (diagnostic initial, 2026-08-23)

Dans un premier temps, une comparaison appariée (Tâche D, scénario
"adapté prudent" vs référence) a montré 2 simulations sur 40 s'effondrant
à une valeur quasi-identique proche de zéro (~-9 069$ / -5 112$) au lieu
du profit normal. Reproduction instrumentée : la flotte B ne traite que
~24 trades sur toute la simulation (4 ans) au lieu de ~24 000, après 7
casses (`B_total_breaks=7`) très tôt, puis reste inactive pour le reste
du run.

Le même signal a été retrouvé dans le moteur single-fleet officiel
(`chantier_rrtp2_sizing_2026-08-19.py`, B_tradable_pgp, risque 1,50/1,50,
n=300, ceiling=1000$) : 17/300 sims (5,67%) avec `total_opens` effondré à
6-7, dont 11 tombant sur exactement la même valeur `net=-5111.99`.

## Verdict final : mécanisme LÉGITIME, pas un bug

Code vérifié :
- `try_emergency_bootstrap()` (chantier_rrtp2_sizing_2026-08-19.py:374-382) :
  ne relance QUE si `state["emergency_remaining"] >= cost` (tout ou rien).
  `DEFAULT_EMERGENCY = 300.0` (`etape_e_fleet_integration.py:109`) est un
  **paramètre documenté et validé délibérément dans des sessions
  antérieures** (registre §2.39/§8.3, "Piste C — fonds d'urgence", testé et
  "laissé en l'état").
- `handle_cost_hybrid()` (ligne 306-322) : au-delà de la réserve, pioche
  dans le plafond personnel (`ceiling - real_cash_paid`) ; une fois ce
  plafond ET les 300$ d'urgence épuisés, la réouverture reste `pending`
  indéfiniment — SANS autre source de financement possible puisque plus
  aucun trade n'est traité (0 compte actif → pas de revenu → jamais de quoi
  payer la réouverture). C'est un vrai deadlock économique, pas un defaut
  de code : le code fait exactement ce qu'il dit.
- `combined_net() = total_funded_pnl - total_fees_paid` (ligne 297-298) :
  une fois la flotte bloquée, ce total ne dépend plus des tirages
  aléatoires de trades (qui ne sont plus traités), seulement du coût
  cumulé (déterministe, table de prix) des tentatives de réouverture avant
  blocage. **C'est pourquoi plusieurs simulations tombent sur EXACTEMENT
  la même valeur** — pas une signature de bug, juste la conséquence
  normale d'un calcul déterministe une fois la partie aléatoire arrêtée.

## Conclusion pour l'utilisateur

**Les pourcentages `solde_negatif%`/`annee1<0%` cités cette session (Tâche
C, Tâche C2) ne sont PAS surestimés par un bug.** Ce mécanisme (casses
précoces répétées épuisant plafond + fonds d'urgence de 300$, flotte
bloquée définitivement) est un vrai risque de ruine, déjà correctement
compté par le moteur, cohérent avec un paramètre (`DEFAULT_EMERGENCY=300$`)
délibérément choisi et validé dans des sessions antérieures.

Le point resté ouvert (pas un bug, une question de calibration) : l'écart
Tâche D "adapté prudent" vs REF pourrait simplement refléter que la
fenêtre choc forcée (israel_hamas) est intrinsèquement MOINS risquée comme
premier bloc que certains blocs réels de B_tradable_pgp (ex. le tout
premier bloc réel de B, 100% métaux corrélés) — pas une anomalie de mesure,
mais un vrai effet de composition d'actifs à documenter si on veut
comparer proprement REF et scénarios dégradés.
