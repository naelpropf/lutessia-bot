# Handoff — reprise après clear (2026-08-11, session c)

Lire en premier :
- `registre_parametres_projet.md` — §1.8 (référence ASYMÉTRIQUE par plafond, tout en haut = dernière mise à jour) et §4 (décisions ouvertes ; #13/#16 désormais résolues, restent #2 éval et #9 plafond)
- `registre_strategie_trading.md` — volet edge / coupe-circuit

## État des chantiers

- Référence officielle capital (§1.8) : **🔴 ASYMÉTRIQUE PAR PLAFOND depuis 08/11 session c (décision #16 tranchée)** — PAS une config unique :
  - **1000$ → Run C** (cadence par firm §2.32, Blueberry 14j défaut, sans surcoût) : 5 491 410$/5 361 009$, solde_negatif_annee4=1,50%, hit_ceiling=3,50%, année1<0=35,50% (`etape_ai_payout_cadence_calibration_n600.csv`).
  - **3000$ → Run F** (Blueberry 7j, coût réel +20%) : 5 589 954$/5 457 443$, solde_negatif_annee4=0,33%, hit_ceiling=1,33%, année1<0=32,83% (`etape_ao_run_f_cout_reel_n600.csv`) — choisi car hit_ceiling y est neutre (0,00pt d'écart vs Run C) alors que profit/année1<0 s'améliorent nettement.
  - Raison de l'asymétrie : à 1000$, Run F dégrade hit_ceiling ×1,7 (+2,33pt), jugé non compensé par le gain profit/année1<0 à ce niveau de capital — à 3000$ ce coût disparaît, dominance de fait.
  - Décisions #13 et #16 toutes deux closes/résolues.
  - `etape_ao_run_f_cout_reel_2026-08-11.py` **corrigé 08/11 session c** : appliquait auparavant Blueberry 7j+surcoût de façon UNIFORME aux deux plafonds si réexécuté (bug potentiel pour toute confirmation future) — maintenant conditionné par `ceiling ∈ BB_PAYOUT_7J_CEILINGS = {3000.0}` (§2.35bis du registre paramètres). Les chiffres n=600 déjà cités ci-dessus restent valides (mesurés plafond par plafond dans des runs isolés).
- Décomposition délai/forfeiture (Run A-G) : **terminé**.
- Deep-dive runs négatifs + mécanisme "effondrement flotte mature" (§2.36-2.37) : **terminé**.
- Coupe-circuit réactif, réouverture + pistes 1-9 précurseur : **terminé, toutes rejetées** (§2.16-2.25).
- Piste 10 (détection DXY temps réel en cours d'épisode, vs winrate glissant) : **terminée, rejetée** (§2.26) — le signal DXY est plus LENT que le coupe-circuit winrate déjà rejeté sur C-core, même en scénario optimiste. Aucun coupe-circuit backtesté (signal pas net/rapide, condition non remplie).
- Tests edge ADX/ATR/news (§2.13-2.15) : **terminé**.
- Filtre news historique (§2.9) : **bloqué** — sous-alimenté (n=4), pas de verdict possible sans données M1/tick.
- Décision plafond personnel (1000$/3000$) et éval (1,00%/1,25%) : **toujours bloquant**, non traité cette session.
