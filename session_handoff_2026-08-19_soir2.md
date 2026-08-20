# Handoff — session du 19/08/2026 (soirée 2, moteur A+B + gisements + découverte chiffres datés)

Lire en premier :
- Ce fichier — chronologie de cette session (suite de `session_handoff_2026-08-19.md`, la session "maturation B" de l'après-midi).
- Fichiers mémoire créés ce soir : `project_ab_parallele_engine_2026-08-19.md`, `project_bbx2_rrtp2_stale_pending_regen_2026-08-19.md` (🔴 le plus important pour la reprise), `project_gisements_exotiques_actions_closed_2026-08-19.md`, `project_capital_personnel_chantier_2026-08-19.md`.

## Chronologie

1. **Pilote paires exotiques forex** — scraping complet (8 paires, 881 signaux, 1595 pages, 2h40, `chantier_exotiques_pilote_2026-08-19.py`). EV globale +0,0587R, IC95% bootstrap inclut zéro — **fermé, pas de scraping complet justifié**.
2. **Chantier "capital personnel"** — moteur de compounding pur hors prop firm (`chantier_capital_personnel_2026-08-19.py`). Meilleur config : risque 1%/trade + any-RR + sizing rr_tp2>8→×1,6. Contrainte de capacité réelle détectée à 500k-1M$ (12-80% des trades forex bridés selon échelle/risque).
3. **Moteur A+B parallèle** (le chantier principal du soir) — premier moteur du projet à faire tourner A et B comme 2 comptes réellement indépendants (`chantier_ab_parallele_2026-08-19.py`), réserve poolée, blocs alignés. Dominance confirmée n=600+stress-test (4/6, inversions H1/bloc1 connues). **Sweep de taille de pivot** (`chantier_ab_taille_pivot_2026-08-19.py`) : A25k+B5k devient la config recommandée (meilleure efficience ET meilleure résilience bloc1 que A25k+B25k). **Déblocage différé de B** (`chantier_ab_b_differe_2026-08-19.py`) testé et REJETÉ comme levier de risque — ne rapproche pas le profil bloc1 d'A-seul.
4. **Diagnostic faisabilité actions** — vues catégorie Actions Europe/US existent (~4200-5000 pages chacune) mais **bloqué avant scraping** : FundedNext n'a aucune action individuelle (confirmé officiellement), copytrade jamais confirmé sur actions pour aucun des 5 firms.
5. **🔴 Découverte de fin de session (la plus importante à traiter en premier à la reprise)** : en re-vérifiant des chiffres cités plus tôt dans la conversation, j'ai trouvé que **§2.35 (rr_tp2>8→×1,6 sizing, 8 206 650$/13,17% année1<0 @3000-5000$) et §2.41/§2.42 (BBx2/BB+GFT jour0, 8 487 070$/10,00% @5000$) sont TOUS LES DEUX construits AVANT deux corrections déjà appliquées au projet** :
   - Le cap de risque Instant corrigé 1,90%→1,5% (`registre_strategie_trading.md:2160-2229`, §2.45, 08/17-18) — preuve : la base "COMBINÉ" de §2.35 (7 080 725$) correspond exactement au chiffre "non corrigé (ancien)" du tableau §2.45.
   - Le bug forex-only corrigé (`registre_parametres_projet.md:650-699`, §1.8bis, 08/18) — population A 631→742 trades, jamais régénérée pour §2.35/BBx2.
   - Sur le COMBINÉ seul, la correction du cap a coûté -5,47% profit et +1,84pt année1<0 (dégradation réelle, pas juste moins de gain) à 3000$/5000$ — un ordre de grandeur comparable ou pire est probable sur §2.35/BBx2 mais **jamais mesuré**.

## Décision bloquante qui reste ouverte

**Relancer §2.35 et BBx2/BB+GFT sous la pile actuelle** (cap Instant 1,5% + population 742 trades) avant de réutiliser leurs chiffres pour quoi que ce soit — c'est le point de reprise prioritaire.

## Fichiers clés créés ce soir (tous à vérifier suivis par git)

`chantier_exotiques_pilote_2026-08-19.py`, `historique_exotiques_pilote_2026-08-19.csv`,
`chantier_capital_personnel_2026-08-19.py`, `capital_personnel_sweep_2026-08-19.csv`,
`chantier_ab_parallele_2026-08-19.py`, `chantier_ab_stresstest_2026-08-19.py`,
`chantier_ab_taille_pivot_2026-08-19.py`, `chantier_ab_b_differe_2026-08-19.py`.
