# Handoff — 23/08/2026 soir — Tâches C/C2/D/E/F terminées, Piste 3 (gate volatilité) en pause décisionnelle

## Contexte

Suite de la session du 23/08 (bug de cap Blueberry Instant découvert et corrigé,
5 leviers revalidés). Cette session a enchaîné : Tâche C2 (risque optimal par
côté), Tâche D (séquentiel B→A@3000$), Tâche E (pivot optimal), Tâche F
(recalcul final), puis une exploration Piste 3 (gate sizing/volatilité) —
**toutes terminées ou en pause propre, aucun run en cours**.

## Ce qui a été fait (résumé condensé, détails dans les commits git)

1. **Tâche C2** — Risque optimal par côté, n=600 verdict :
   **A_seule garde la référence 1,25%/1,90%** (rien ne la bat), **B_tradable_pgp
   passe à 1,50%/1,50% uniforme** (+4,2-4,5% profit vs référence, risque
   identique). Le creux au point 1,75% sur B est réel (confirmé n=600), pas
   du bruit.

2. **BLOCKER trouvé PUIS INVALIDÉ** : un "gel de flotte" après casses précoces
   (17/300 sims figées à ~24 trades au lieu de ~24 000) a d'abord été pris pour
   un bug (`try_emergency_bootstrap`) — **investigation approfondie a montré
   que c'est un mécanisme LÉGITIME** (épuisement plafond personnel + fonds
   d'urgence 300$, paramètre déjà validé dans le registre §2.39/§8.3). **Ne
   pas rouvrir ce point** sauf nouvelle preuve contraire — voir commits
   `7f89e14` (fausse alerte) puis `3085376` (correction).

3. **Tâche D** — Séquentiel B→A@3000$, 3 scénarios n=600 verdict :
   REF (57,33M/60,52M$) > adapté_prudent (choc israel_hamas forcé sur B,
   56,38M/60,43M$) > adapté_marge_sécurité (+ winrate P10 dégradé,
   52,66M/57,20M$). Moteur : `chantier_taskD_sequential_BA_2026-08-23.py`
   (copie patchée de `chantier_ab_metaux_cascade_officiel_2026-08-19.py` —
   S2.35 porté, risque par côté ajouté, degradations optionnelles ajoutées à
   `run_n_sims` en préservant le couplage calendaire A/B).

4. **Tâche E** — Pivot optimal, n=600 verdict : **Blueberry Instant Elite
   2 500$ (100$) bat la référence 25k$ (800$) EN PROFIT ET EN RISQUE** à
   c=1000$ (58,72M$ vs 57,33M$, 0,00% vs 3,17% solde_négatif) — tranche la
   question ambiguë du 18/08. Mécanisme : coût de réouverture plus faible =
   plus de tentatives possibles avant épuisement plafond+fonds urgence.
   Calendrier d'ouverture multi-firm documenté (FTMO@1000$, Fivers@15000$,
   GFT/FundedNext@25000$, cf. `seq_grouped_multi` déjà en usage).

5. **Tâche F** — Recalcul final (pivot 2500$ + séquentiel adapté_prudent +
   5 leviers + risque par côté), n=600 verdict : **0,00% solde_négatif et
   année1<0 sur les 4 blocs historiques et les 2 ceilings**. Profit global
   57,87-58,77M$ vs référence registre §6.5 (17,74-18,03M$, ancienne
   population pré-correction) — **comparaison non homogène méthodologiquement**
   (ceiling ≠ seuil de déclenchement, jamais clarifié) — à ne pas citer comme
   un "+226%" fiable sans requalifier.
   **Décomposition pas-à-pas vérifiée** (commit `afd45c8`) : S2.35 apporte le
   plus (+5,3-5,4%), risque différencié coûte un peu à c=3000$ (-1,7%, normal
   car B baisse son risque), pivot 2500$ gagne à c=1000$ mais coûte un peu à
   c=3000$ (pas besoin de protection à ce ceiling).

6. **Piste 3 (gate sizing conditionné à la volatilité réalisée)** — EN PAUSE,
   décision utilisateur attendue avant de continuer :
   - Proxy retenu : **ATR H1 fenêtre 40 barres** (le plus stable sur les 28
     tickers testés, sans exception).
   - Vérifié sur 3 chocs (SVB, israel_hamas, carry-unwind août 2024) : le gate
     "ticker-propre" protège 100% (SVB), 53% (israel_hamas), **seulement 8%**
     (carry-unwind, l'épisode le plus grave, -1,65/-1,79R).
   - Signal cross-marché JPY testé sur demande : **8%→100% sur carry-unwind**
     (bond spectaculaire, cohérent — c'est un choc JPY), mais **53%→0% sur
     israel_hamas** (signal JPY totalement muet, choc non-JPY).
   - **Verdict actuel : aucun signal unique ne protège les 3 chocs
     simultanément** — chaque choc a son propre canal d'alerte précoce. Un
     gate combiné (ticker-propre + JPY + un 3e canal pour israel_hamas)
     risquerait le sur-ajustement (choisi a posteriori en connaissant déjà
     ces 3 chocs précis).
   - **Étape 3 (simulation coûteuse du gate en flotte) PAS lancée** — en
     attente de décision : arrêter Piste 3 ici (verdict négatif documenté) ou
     explorer un gate combiné en assumant le risque de sur-ajustement.

## Fichiers clés de cette session (tous committés/poussés)

- `chantier_rrtp2_sizing_2026-08-19.py` — moteur single-fleet officiel (PAS
  `-08-16`, qui manque le cap Blueberry Instant 1,5% — piège déjà tombé une
  fois, ne pas réutiliser `-08-16`).
- `chantier_taskD_sequential_BA_2026-08-23.py` — moteur double-flotte
  séquentiel B→A à jour (pivot, risque par côté, S2.35, dégradations).
- `chantier_taskC2_risque_sweep_AB_2026-08-23.py`,
  `chantier_taskE_pivot_2026-08-23.py`, `chantier_taskF_final_2026-08-23.py`,
  `chantier_taskF_decomp_2026-08-23.py` — scripts de mesure des tâches
  correspondantes, réutilisables tels quels.
- `chantier_piste3_volgate_2026-08-23.py`, `chantier_piste3_episodes_2026-08-23.py`,
  `chantier_piste3_crossmarket_2026-08-23.py` — Piste 3, réutilisables pour
  reprendre l'exploration.
- `diagnostic_bug_fleet_gelee_emergency_bootstrap_2026-08-23.md` — **lire le
  correctif en haut du fichier avant tout**, le titre est trompeur (annonce un
  bug qui n'existe pas, corrigé dans le corps du texte).

## Ce qui n'a PAS été fait

- Piste 3 étape 3 (chiffrage du coût réel du gate en régime normal) et étape 5
  (stress-test flotte) — en pause, décision utilisateur en attente.
- Aucune mise à jour du registre officiel (`registre_strategie_trading.md`/
  `registre_parametres_projet.md`) avec les résultats C2/D/E/F de cette
  session — seulement les logs/scripts sont committés, pas encore intégrés
  au registre narratif. À faire si ces résultats doivent devenir "officiels".
- Fichiers non trackés datés du 20/08 (chantier multifirm/stresstest,
  diagnostics) — confirmés obsolètes (pop B_tradable_pgp corrigée après),
  toujours pas committés, volontairement laissés de côté.

## Piège à ne pas retomber dedans

Le diagnostic "bug flotte gelée" (`diagnostic_bug_fleet_gelee_...md`) a été
écrit puis corrigé DANS LA MÊME SESSION après vérification code — si une
future session lit seulement le titre ou un ancien commit sans lire la
section "CORRECTIF" en haut du fichier, elle risque de re-halted le projet
pour rien. Le mécanisme est légitime, pas un bug.
