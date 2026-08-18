# Handoff — session du 17/08/2026

Lire en premier :
- Ce fichier — chronologie complète de cette session (très longue, plusieurs
  chantiers indépendants enchaînés).
- `registre_parametres_projet.md` §8 (nouveau, toute la session y est
  consignée) — plafond efficace, réouvertures Piste A/B/C/D, sections
  doublon-paire et position-cap×risque.
- `registre_strategie_trading.md` §2.36-2.38bis — sizing continu rejeté,
  GFT Instant adapté rejeté, recherche de variable de segmentation
  alternative (rejetée), downsizing temporel (hypothèse réfutée).

## Chronologie complète de la session (dans l'ordre)

1. **Confirmation de la référence de travail** (RR≥1,35/corr0,80, éval
   1,25%/funded 1,90%, Blueberry Prime, §1.8 cascade BB Instant+any-RR,
   §2.35 rr_tp2 sizing) — vérifiée par citation de code, techniquement
   présente et fonctionnelle, mais **toujours PAS marquée "adoptée
   officiellement"** dans le tableau §1.8. Ce statut est INCHANGÉ après
   cette session entière — décision utilisateur finale toujours en
   attente malgré ~15 chantiers construits dessus.

2. **Section A — sizing continu/paliers étendus sur rr_tp2** (3 candidats
   A1/A2/A3, boost gradué ≥1,0× étendu sur plus de la distribution) —
   **REJETÉS**, aucun ne bat le seuil simple déjà adopté (§2.35). Portée
   du rejet précisée : famille "boost ≥1,0×" uniquement, downsizing
   jamais testé à ce stade (§2.36 registre_strategie_trading.md).

3. **Section B — GFT Instant en comptes extra parallèles** — **REJETÉ**,
   diagnostic du mode de casse fait (DD journalier 3,0% domine, trade
   déclencheur sizé rr_tp2≥8 dans 49% des cas vs 15,2% population).
   Portée précisée : stratégie classique rejouée telle quelle (§2.37).

4. **Section C — double starter FTMO 50/50** (jour0, risque partagé
   0,5×/1,0×) — dominance apparente n=300 à 3000$/5000$ (+0,63%),
   ambigu/rejeté à 960$/1000$ (hit_ceiling ×6-11,5). **Jamais poussé en
   n=600** cette session (§8.5 registre_parametres_projet.md) —
   surclassé en pratique par BBx2/BB+GFT jour0 (point 9 ci-dessous).

5. **Réouverture ciblée A/A-bis/B** (changement structurel, pas
   paramétrique) :
   - **Downsizing permanent RR** (A4 décile pire seul, A5 5 déciles
     scattered) : A5 rejeté nettement, A4 **ambigu** (gain année1<0 réel
     mais modeste -0,3 à -1,7pt, coût profit -0,2 à -0,6%, stable 6/6
     sous-périodes mais sans dominance) — jamais tranché.
   - **A-bis (downsizing temporel)** : hypothèse causale (segments faibles
     surreprésentés dans les pertes) **RÉFUTÉE empiriquement**, rien
     construit (§2.38bis).
   - **GFT Instant adapté** (exempté du sizing rr_tp2, +risque plafonné
     1,40%) : mécanisme de casse corrigé (-66% de casses Instant) mais
     **résultat net toujours négatif** à tous les plafonds — REJETÉ avec
     raison précise, pas juste "rejoué à l'identique" cette fois.

6. **Recherche de variable de segmentation alternative à RR** (score_force
   et ATR exclus car déjà testés comme sizing ; ADX/session/asset_class
   sans signal, asset_class inutilisable/une seule catégorie) —
   **distance_SL%** seul candidat à passer le garde-fou out-of-sample
   (stable 6/6 sous-périodes) mais **REJETÉ en flotte** (-2,7% à -3,7%
   profit, non compensé). Conclusion : aucune variable actuellement
   capturée dans le pipeline ne porte un signal exploitable (§2.38).

7. **Re-test de 4 anciennes pistes sous la pile actuelle** (toutes
   antérieures au rebuild RR1,35/corr0,80 du 08/12, jamais re-vérifiées
   depuis) :
   - **Piste A (BBx2)** et **Piste B (BB+GFT jour0)** : n=300 → dominance
     apparente à 5000$ (NOUVEAU, jamais testé à l'époque), rejeté à
     960$/1000$ (comme avant), PAS de dominance à 3000$ (verdict CHANGÉ
     pour BBx2 — hit_ceiling explose maintenant à 0%→12,67%, absent de
     l'ancienne mesure).
   - **Piste C (fonds d'urgence 10%/7j/N2)** : verdict **DÉPLACÉ** de
     3000$ (ancien) vers 1000$ (maintenant) — REF est désormais déjà
     optimal à 3000$/5000$ (rien à gagner), gain modeste à 1000$
     (hit_ceiling ÷2, -0,22% profit). Pas poussé en n=600.
   - **Piste D (contrarian RR 0,75-1,25)** : verdict **INVERSÉ** à
     960$/1000$ (ancien +1,80% → maintenant -15,9% à -16,4%, effondrement),
     tient globalement à 3000$/5000$ mais magnitude réduite (+0,43% vs
     +2,09% ancien). Pas poussé en n=600.

8. **Stress-test H1/H2+4 blocs k-fold** sur BBx2@5000$, BB+GFT@5000$,
   BB+GFT@3000$ (avant tout n=600) — **les 3 passent**, aucune inversion
   de direction. BB+GFT@3000$ montre un coût hit_ceiling reproductible
   dans 4/6 sous-périodes (confirme l'arbitrage réel, pas du bruit).

9. **✅ Confirmation n=600+cascade — 2 GO, 1 arbitrage chiffré** (§8.2
   registre_parametres_projet.md) :
   - **BBx2@5000$ : GO.** Dominance stricte (+3,42% profit, hit_ceiling
     0%=, année1<0 -3,17pt).
   - **BB+GFT jour0@5000$ : GO.** Dominance stricte (+1,43% profit,
     hit_ceiling 0%=, année1<0 -3,00pt).
   - **BB+GFT jour0@3000$ : arbitrage chiffré, PAS de verdict tranché** —
     +113 934$/run-comparable pour +21 runs/600 touchant le plafond
     (0%→3,5%) et -18 runs/600 en année1 négative.
   - **Ni l'un ni l'autre des 2 GO n'est intégré à la référence
     officielle §1.8** — reste une proposition technique, comme toujours
     dans ce projet (décision d'adoption séparée de la confirmation
     technique).

10. **Cartographie du plafond personnel efficace** (`chantier_ceiling_
    sweep_1000_3000_2026-08-17.py` + `chantier_bb_threshold_finegrid_
    2000_2026-08-17.py`) : **🔴 2500$ atteint déjà 100% de la performance
    de 3000$/5000$** (valeurs identiques au $ près) — le vrai plafond
    efficace minimal est entre 2000$ et 2500$, pas 3000$ comme utilisé
    partout jusqu'ici. À 2000$ précisément : vrai arbitrage entre
    bb_threshold=0 (meilleur profit/année1<0) et =500 (meilleur solde_neg/
    hit_ceiling), aucune valeur intermédiaire ne domine les deux.

11. **Section "doublon même paire"** (2 signaux GBP/JPY simultanés
    observés en conditions réelles) — **FERMÉE, rien à changer**.
    Frictions purement proportionnelles/nulles (citation de code),
    risque d'échec d'exécution non modélisé mais uniforme (pas
    spécifique au cas doublon), blocage plafond causé par doublon
    même paire = 0,19% de tous les trades. Statu quo = optimal
    théorique. Aucun candidat construit (arrêt à l'Étape 0, comme
    demandé explicitement).

12. **Sweep plafond de positions (3→6) × risque par trade** — **REJETÉ
    sans ambiguïté**, effet **INVERSE** de l'hypothèse de départ (censé
    réduire la variance sans changer l'EV) : profit -17,7% à -44,9%
    selon la variante, ET année1<0 qui EMPIRE au lieu de s'améliorer.
    Mécanisme : réduire le risque par trade ralentit la progression vers
    l'objectif de challenge, retardant le financement — effet déjà connu
    comme dominant dans ce projet, qui écrase tout bénéfice de
    diversification théorique.

## Fichiers clés créés cette session (tous suivis par git)

Diagnostics : `chantier_A_rr_sizing_diagnostic_2026-08-17.py`,
`chantier_A_rr_sizing_diagnostic2_2026-08-17.py`,
`chantier_B_gft_instant_failure_diagnostic_2026-08-17.py`,
`chantier_segmentation_variables_2026-08-17.py`,
`chantier_positioncap_blocking_diagnostic_2026-08-17.py`.

Screenings n=300 : `chantier_A_rr_sizing_2026-08-17.py`,
`chantier_B_gft_instant_parallel_2026-08-17.py`,
`chantier_C_double_starter_2026-08-17.py`,
`chantier_A_downsizing_2026-08-17.py`,
`chantier_B_gft_instant_adapted_2026-08-17.py`,
`chantier_segmentation_fleet_test_2026-08-17.py`,
`chantier_pisteAB_bbx2_bbgft_2026-08-17.py`,
`chantier_pisteC_fonds_urgence_2026-08-17.py`,
`chantier_pisteD_contrarian_2026-08-17.py`,
`chantier_ceiling_sweep_1000_3000_2026-08-17.py`,
`chantier_bb_threshold_finegrid_2000_2026-08-17.py`,
`chantier_sectionB_poscap_risk_2026-08-17.py`.

Stress-test + confirmation : `chantier_stresstest_pisteAB_2026-08-17.py`,
`chantier_n600_pisteAB_2026-08-17.py`.

## Décisions bloquantes qui restent ouvertes (toutes déjà connues, aucune
nouvellement résolue cette session)

1. **Adoption OFFICIELLE de §1.8** (cascade any-RR + BB Instant +
   rr_tp2) — techniquement prête depuis le 08/16, toujours en attente.
2. **Plafond personnel réel** (décision #9) — désormais encore plus
   pertinent : le vrai plafond efficace est ~2000-2500$, pas 3000$.
   Conditionne aussi le choix bb_threshold=0 vs 500 à 2000$ pile.
3. **BB+GFT jour0@3000$** — arbitrage chiffré (§8.2), décision utilisateur
   requise si ce plafond est le plafond réel.
4. **BBx2@5000$ et BB+GFT jour0@5000$** — 2 GO n=600 confirmés,
   jamais intégrés à la référence officielle (adoption séparée requise).
5. Sections Piste C (fonds urgence) et Piste D (contrarian) : résultats
   plus faibles que l'ancienne mesure, jamais poussés en n=600 — dispo
   sur demande séparée si l'utilisateur le souhaite.
6. Double starter FTMO 50/50 (§8.5) — jamais poussé en n=600 non plus,
   dominé par BBx2/BB+GFT en comparaison indicative n=300.
7. Plafond efficace 2000-2500$ jamais affiné plus finement (2100/2200/
   2300/2400$) — à faire si utile.

## Note de méthode (rappel, déjà connu mais reconfirmé cette session)

Plusieurs verdicts d'anciennes pistes (pré-08/12) ont CHANGÉ une fois
re-testés sous la pile actuelle (Piste A/B/C/D ci-dessus) — parfois en
mieux (BBx2/BB+GFT gagnent un GO propre à 5000$, jamais testé à l'époque),
parfois en pire (Piste D s'effondre à 960$/1000$). **Ne jamais supposer
qu'un ancien résultat tient sous une pile différente — toujours re-tester
avant de combiner.** Convention n=300 screening / n=600 confirmation
toujours respectée partout.
