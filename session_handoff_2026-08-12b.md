# Handoff — reprise après clear (session du 08/12, suite b)

Lire en premier :
- `registre_parametres_projet.md` — §1.8 (référence, VIENT DE CHANGER),
  §2.59-2.64 (tout ce qui a été fait cette session), §4 décisions #33-37
- `registre_strategie_trading.md` — §2.8bis (RR adopté), §2.9 (news filter,
  toujours non concluant, section fermée par l'utilisateur cette session)

## 🔴 CHANGEMENT MAJEUR CETTE SESSION : nouvelle référence officielle adoptée

**RR≥1,35 + corrélation 0,80** remplacent RR≥1,25/corr 0,6 comme référence
officielle du projet (§1.8, §2.62-2.63). Tout l'ancien contenu du registre
antérieur à cette session (daté 08/11 et avant) reste RR1,25/corr0,6 et est
marqué SUPERSEDED — ne jamais le lire comme la référence courante sans
vérifier la date.

**Nouvelle référence officielle (§1.8), n=600+cascade :**
| Plafond | Config | Profit moyen/médian | solde_neg | hit_ceiling | Année1<0 |
|---|---|---|---|---|---|
| 1000$ | Run C | 5 836 643$/5 621 512$ | 0,50% | 1,50% | 30,50% |
| 3000$ | Run F | 5 900 859$/5 630 556$ | 0,33% | 0,33% | 28,83% |

## Chronologie complète de la session (dans l'ordre)

1. **Chantier cluster Blueberry 1,5%** (repris depuis avant le clear
   précédent) : confusion Prime/Standard clarifiée (compte live = Standard,
   soumis au cluster ; référence simulait Prime par erreur depuis le
   début). 3 options comparées, **Option A (bascule vers Prime) adoptée**
   — confirmé n=600, **audit de fidélité 8/8 points conforme** (RR/DD/prix/
   split/levier tous vérifiés par citation de code). `CONFIG_REF` reste
   inchangé dans le code (déjà correct). Chantier définitivement clos
   (§2.59, décision #33).

2. **Chantier 1 — paramètres portefeuille/entrée** : 3 sections en
   parallèle sous RR1,25/corr0,6 (base d'alors) :
   - **Règle JPY-JPY** : reconfirmée (garder), max DD flottant réel mesuré
     1,53% (vs 8,81% historique pré-fix).
   - **Seuil corrélation** : 0,8 identifié meilleur que 0,6 (n=300).
   - **Grille RR affinée** : 1,35 domine strictement 1,25 sur les 4 axes
     (n=300).
   - Filtre news : section annulée par vous en cours de route (déjà statué
     08/11, non concluant, n=4/460).

3. **Confirmation combinée RR1,35+corr0,8** : redensification corrélation
   SOUS RR1,35 (0,80 confirmé, pattern quasi-monotone), n=600+cascade GO
   sur la combinaison — adopté (§2.62).

4. **🔴 CASCADE COMPLÈTE d'adoption** (la plus grosse partie de la
   session) — régénération de TOUTE la chaîne dépendante :
   - **Section 0** : zone morte T1/T2 trouvée et corrigée dans
     `dual_trader_2026-08-11.py` (bande Stratégie B élargie 0,75-1,25 →
     0,75-1,35, constante `MIN_RR_T1` désormais partagée).
   - **Section 1** : Run C/Run F régénérés (`etape_aq_run_c_rr135_
     corr080_2026-08-12.py` / `etape_ar_run_f_rr135_corr080_2026-08-12
     .py`) — nouvelle référence §1.8 ci-dessus.
   - **Section 2** : config 1/4 dual-trader régénérées n=600. **Config
     1@1000$ passe de "hors jeu" (hit_ceiling 23,50%) à un profil
     beaucoup plus sain (7,83%)** — changement de statut à noter (décision
     #37, PAS de recommandation automatique, choix utilisateur toujours
     ouvert). Décomposition du mécanisme de sauvetage reconfirmée (T2
     sauve T1 71% à 1000$, quasi identique à l'ancien 69,7%).
   - **Section 3** : Blueberry Prime A/B/C rafraîchi — **verdict qualitatif
     inchangé** (A domine toujours B/C).
   - Piste 1 (fonds d'urgence) explicitement NON touchée par la cascade
     (candidat jamais adopté, séparé).

5. **Chantier rank-and-rent → plafond personnel** (le plus récent,
   §2.64) : décision "40$ vers rank-and-rent pour viser 5-10k$" analysée
   sous la NOUVELLE référence :
   - **Vrai palier optimal = 5000$** (pas 10 000$ : profit et solde_neg
     plafonnent exactement là, balayage {960...10000}$ refait à neuf).
   - **Coût de 960$ vs 1000$ : négligeable** (-0,03% profit), mais
     hit_ceiling monte réellement (2,00%→3,33%).
   - **Attendre ne vaut JAMAIS le coup** (testé 3/6/9/12 mois) : démarrer
     maintenant à 960$ puis basculer à 5000$ dès que le rank-and-rent
     rapporte domine strictement d'attendre, à TOUS les délais testés —
     aucun point de bascule trouvé, l'écart croît même avec le délai.
   - **Conclusion actionnable : démarrer maintenant à 960$, basculer à
     5000$ plus tard.** Décision utilisateur, pas encore explicitement
     confirmée en retour au moment du clear.

## Fichiers clés créés cette session (tous suivis par git sauf CSV)

- `blueberry_cluster_options_2026-08-12.py` / `..._rr135_corr080_2026-08-12
  .py` — chantier cluster Blueberry (options B/C).
- `chantier1_jpy_rule_test_2026-08-12.py`, `chantier1_corr_threshold_sweep_
  2026-08-12.py`, `chantier1_corr_under_rr135_2026-08-12.py`,
  `chantier1_rr_grid_2026-08-12.py`, `chantier1_combined_confirm_n600_2026-
  08-12.py`, `chantier1_strategyb_band_check_2026-08-12.py` — Chantier 1 +
  confirmation combinée.
- `etape_aq_run_c_rr135_corr080_2026-08-12.py`, `etape_ar_run_f_rr135_
  corr080_2026-08-12.py` — nouvelle référence officielle (copies figées de
  etape_ai/etape_ao, seuls RR/corr changés).
- `dual_trader_2026-08-11.py` — MODIFIÉ en place (MIN_RR_T1/CORR_TH_ADOPTED
  centralisés, plus une constante dupliquée).
- `dual_trader_config4_decomposition_2026-08-12.py` — MODIFIÉ (solo_ref mis
  à jour).
- `chantier_ceiling_sweep_2026-08-12.py`, `chantier_rank_and_rent_2026-08-
  12.py` — chantier rank-and-rent (le 2e ajoute `ceiling_schedule`/
  `start_delay_seconds`, capacités réutilisables pour tout futur scénario
  de plafond variable dans le temps).
- `engine_multiformat.py` — MODIFIÉ (prix Blueberry Standard 170$, docstring
  Prime/Standard clarifiée).

## Décisions bloquantes qui restent ouvertes (rappel §4)

1. Choix final config 1 vs config 4 à 3000$ (profit max vs risque quasi
   nul) — dual-trader, toujours jamais tranché, chiffres régénérés cette
   session mais le choix reste à vous.
2. Config 1@1000$ : son statut a changé (moins "hors jeu" qu'avant, décision
   #37) — pas encore rediscuté avec vous.
3. Éval 1,00% vs 1,25% (décision #2, très ancienne, jamais retouchée).
4. Plafond personnel réel : la cascade a confirmé 5000$ comme cible
   d'atterrissage, mais le choix "1000$ vs 3000$ vs 5000$" comme référence
   *unique* du projet reste formellement ouvert (décision #9, ancienne).
5. Rank-and-rent : conclusion "démarrer maintenant à 960$" livrée, pas
   encore confirmée par vous en retour.
