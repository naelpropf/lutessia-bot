# Handoff — reprise après clear (2026-08-11, session c)

Lire en premier :
- `registre_parametres_projet.md` — §1.8 (référence, tout en haut = dernière mise à jour) et §4 (décisions ouvertes, notamment #13/#16)
- `registre_strategie_trading.md` — volet edge / coupe-circuit

## État des chantiers

- Référence officielle capital (§1.8) : **cadence par firm (§2.32) CONFIRMÉE n=600 08/11 session c** — nouvelle référence officielle 5 491 410$/5 542 103$, année1<0 35,50%/35,33% (`etape_ai_payout_cadence_calibration_n600.csv`). Décision #13 close.
- Run F (Blueberry 7j, coût réel +20%) : **cascade check n=600 FAIT 08/11 session c — verdict MIXTE, PAS adopté**. Améliore profit/année1<0, dégrade solde_negatif_annee4/hit_ceiling_pct (surtout à 1000$, hit_ceiling quasi ×1,7) — pas une dominance stricte 3-axes. Reste un candidat documenté, décision utilisateur explicite nécessaire (§1.8, §2.35, décision #16). `etape_ao_run_f_cout_reel_n600.csv`.
- Décomposition délai/forfeiture (Run A-G) : **terminé**.
- Deep-dive runs négatifs + mécanisme "effondrement flotte mature" (§2.36-2.37) : **terminé**.
- Coupe-circuit réactif, réouverture + pistes 1-9 précurseur : **terminé, toutes rejetées** (§2.16-2.25).
- Piste 10 (détection DXY temps réel en cours d'épisode, vs winrate glissant) : **terminée, rejetée** (§2.26) — le signal DXY est plus LENT que le coupe-circuit winrate déjà rejeté sur C-core, même en scénario optimiste. Aucun coupe-circuit backtesté (signal pas net/rapide, condition non remplie).
- Tests edge ADX/ATR/news (§2.13-2.15) : **terminé**.
- Filtre news historique (§2.9) : **bloqué** — sous-alimenté (n=4), pas de verdict possible sans données M1/tick.
- Décision plafond personnel (1000$/3000$) et éval (1,00%/1,25%) : **toujours bloquant**, non traité cette session.
