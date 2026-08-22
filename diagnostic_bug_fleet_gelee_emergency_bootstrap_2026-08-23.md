# Diagnostic — bug flotte gelée / emergency bootstrap inopérant (2026-08-23)

## Résumé

Bug confirmé (pas du bruit d'échantillonnage) dans le mécanisme de
financement/relance de compte (`handle_cost_hybrid` / `try_emergency_bootstrap`),
**partagé par le moteur single-fleet officiel** (`chantier_rrtp2_sizing_2026-
08-19.py`, utilisé pour TOUTES les Tâches C et C2 de cette session, y compris
les résultats ayant servi à l'adoption formelle de §1.8/§2.35 et à la
conclusion du sweep de risque A/B) **et** le moteur double-flotte
(`chantier_ab_metaux_cascade_officiel_2026-08-19.py`, base de la Tâche D).

## Comment il a été trouvé

En creusant une anomalie Tâche D (le scénario "adapté prudent" montrait un
risque PLUS BAS que la référence, ce qui n'a pas de sens pour une
dégradation), une comparaison appariée par graine identique a montré que 2
simulations sur 40 s'effondraient à une valeur quasi-identique proche de
zéro (~-9 069$ / -5 112$) au lieu du profit normal (dizaines de millions).

## Preuve (moteur double-flotte, reproduction instrumentée)

Sur la simulation défaillante : `B_trades_admitted=24` sur toute la
simulation (4 ans), contre `B_trades_admitted=24 394` sur une simulation
saine avec la même population — la flotte B se retrouve quasi totalement à
l'arrêt après ~24-34 événements alors qu'elle devrait en traiter des
dizaines de milliers. `B_total_breaks=7` juste avant l'arrêt : la flotte
casse 7 fois tôt dans la simulation puis ne rouvre plus jamais.

## Preuve (moteur SINGLE-FLEET, `chantier_rrtp2_sizing_2026-08-19.py`,
B_tradable_pgp, risque 1,50%/1,50%, n=300, ceiling=1000$)

**17 simulations sur 300 (5,67%)** montrent la même signature de gel :
`total_opens` s'effondre à 6-7 (au lieu de dizaines à centaines en régime
normal, cf. distribution triée : 6,6,7,7,7,7,7,7,7,7,7,7,7,7,7,7,10,77,92,96...).

Plus frappant : **11 de ces 17 simulations tombent sur la valeur EXACTEMENT
IDENTIQUE `net=-5111.990000`** (au centime près), malgré des tirages
aléatoires différents en amont (winrate, ordre de bootstrap) — signature
d'un état terminal déterministe (le même coût de compte figé, plus aucune
activité derrière), pas d'un résultat de trading normal.

## Portée / impact

Ce mécanisme (`try_emergency_bootstrap`/`handle_cost_hybrid`) est du code
**partagé**, présent dans toute la lignée de moteurs Monte Carlo du projet
(au moins `chantier_rrtp2_sizing_2026-08-16/19.py` et
`chantier_ab_metaux_cascade_officiel_2026-08-19.py` vérifiés directement ;
probablement present dans le reste de la lignée `-08-17` officielle et
au-delà, NON VÉRIFIÉ ici faute de temps).

**Toutes les statistiques `solde_negatif%`/`annee1<0%` citées cette
session (Tâche C : 5 leviers sur A_seule et B_tradable_pgp ; Tâche C2 :
sweep de risque A/B, y compris la conclusion "B optimal = 1,50%/1,50%") sont
potentiellement contaminées** : une partie non négligeable (~3-7% selon les
runs observés) des simulations classées "ruine" pourrait en réalité être cet
artefact de gel plutôt qu'une vraie perte de trading. Ça ne veut pas dire que
les conclusions directionnelles sont fausses, mais les POURCENTAGES exacts
de risque cités (et donc les décisions d'adoption §1.8/§2.35 et le choix du
risque optimal B=1,50%/1,50%) reposent sur des chiffres à re-vérifier.

## Cause précise -- PAS ENCORE ISOLÉE

Le symptôme est net (n_active_accounts(tid)==0 après plusieurs casses
précoces, `try_emergency_bootstrap` ne relance apparemment pas la flotte),
mais la ligne de code exacte qui empêche le bootstrap de fonctionner n'a
pas été trouvée (aurait demandé une instrumentation plus poussée de
`try_emergency_bootstrap`/`handle_cost_hybrid`/`emergency_remaining`).

## Recommandation

**Ne pas poursuivre les Tâches D/E/F ni faire confiance aux conclusions
C/C2 tant que ce bug n'est pas isolé et corrigé (ou au moins quantifié
précisément).** Prochaine étape suggérée : instrumenter
`try_emergency_bootstrap`/`emergency_remaining` directement pour voir
pourquoi le bootstrap ne relance pas la flotte après le passage à 0 compte
actif.
