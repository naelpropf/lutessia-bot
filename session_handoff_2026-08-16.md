# Handoff — reprise après clear (session du 08/15→08/16)

Lire en premier :
- `registre_strategie_trading.md` §2.28 (plafond 3 positions, REJETÉ),
  §2.29 (stabilité/bayésien), §2.30 (frottements réels + EV plancher),
  §2.31 (ADX/ATR mis à jour)
- `registre_parametres_projet.md` §6 (instant funding Phase 1+2 +
  exploration GFT élargie), §7 (bascule conditionnelle flotte complète —
  🔴 NOUVEAU CE JOUR, décision utilisateur en attente)

Éval=1,25% confirmé par l'utilisateur en début de session (décision #2
du registre, longtemps bloquante — **désormais tranchée**, ne plus la
traiter comme ouverte).

## Chronologie complète de la session (dans l'ordre)

1. **Chantier plafond de 3 positions simultanées** — mesure de l'ampleur
   (0,8% de la population bloquée par le cap, EV négative sur ces cas),
   cap=4 et swap RR-préventif tous deux testés n=300 : **REJETÉ**, gain
   dans le bruit ou carrément négatif. Section 4 (4e slot temporaire) non
   engagée (gating explicite du prompt respecté). Correction méthodo
   reçue de l'utilisateur en cours de route : les comptes d'une même firm
   (clones day-0) bloquent en LOCKSTEP PARFAIT en copytrade (pas de
   redondance "un autre compte peut prendre le relais" intra-firm, ça
   n'existe qu'entre firms différentes) — corrigée dans le registre.

2. **Vérification 14/08 (clustering de signaux)** — demande de
   l'utilisateur suite à une observation live (2 signaux même jour,
   00:22/13:24). Vérifié : 29,6% des jours actifs ont 2+ signaux (14/08
   NORMAL, pas un outlier), aucun bug de granularité jour/heure dans
   Section 1 du chantier précédent (comparaison de timestamps complets,
   correcte), écart naïf/temps-réel seulement 1,4x. Verdict du chantier 1
   confirmé, pas de sous-comptage structurel.

3. **CHANTIER 2 — Rigueur statistique** (population mise à jour RR≥1,35/
   corr0,80/631 trades, pas l'ancienne base 721/RR1,25) :
   - Section 2 (stabilité+bayésien) : pas de dérive temporelle
     significative (p=0,15), P10/P50/P90=37,0/39,5/42,0%, P(EV<0)=0,09%.
   - Section 1 (frottements a-f, slippage retesté sur 628/631 trades via
     nouveaux appels Dukascopy) : EV plancher réaliste +0,7319R
     (largement positif) ; EV plancher absolu (P10 winrate + formule EV
     simple + tous frottements pessimistes cumulés) légèrement négatif
     (-0,0336R) mais c'est un double stress-test, pas un scénario
     probable — pas d'alarme sur l'edge.
   - Section 3 (ADX/ATR) : couverture inchangée 52%, extension Dukascopy
     chiffrée 18-61h et REFUSÉE (disproportionné). Verdict mis à jour
     sur la nouvelle base : signe ne s'inverse plus en sous-période
     (mieux qu'en 08/11) mais toujours pas significatif (IC traverse
     zéro). PAS ADOPTÉ, pas rejeté non plus — statut inchangé.

4. **🆕 CHANTIER instant funding** (nouveau sujet, 3 phases dans la même
   session) :
   - **Phase 1 (recherche sourcée, pages officielles)** : seuls
     Blueberry et GFT ont une vraie offre instant funding comparable au
     palier actuel. FTMO n'en a pas, The5%ers (Hyper Growth) garde une
     éval déguisée, FundedNext plafonne à 20k$ (vs 200k$ palier projet).
   - **Phase 2 (modélisation, compte isolé, trésorerie infinie)** :
     **Blueberry INSTANT GAGNE** (+17 230$/4ans, casses 6,66→0,90, cash
     sûr dès ~5000$). **GFT CLASSIQUE GAGNE** (DD instant 6% trailing
     bien plus serré que le 10% statique classique, casses ×6,2, cash
     ×9,7, pas sûr même à 10 000$ de plafond). Sweep de risque GFT
     confirmé monotone (baisser le risque ne sauve rien).
   - **Exploration GFT élargie** (Stratégie B + RR relevé + cap position
     réduit + exclusion de paire + combos, n=300) : **PISTE FERMÉE,
     confirmée sans ambiguïté** — aucun levier ne bat le classique de
     façon significative (meilleur cas +0,56% pour 9× plus de
     trésorerie). Ne pas retester sans idée structurellement nouvelle.
   - **🔴 Bascule conditionnelle FLOTTE COMPLÈTE (pas compte isolé)** —
     Blueberry : **seuil optimal dépend du plafond personnel** — à
     960$, seuil=5000$ domine tout (y compris 100% classique ET seuil=0,
     qui est un PIÈGE à ce plafond : +2,6% profit mais hit_ceiling ×3,7,
     solde_neg ×30) ; à 5000$ de plafond, seuil=0 (bascule immédiate)
     devient le meilleur choix sur les 4 axes (+11,3% profit, risques
     tous meilleurs). **PAS ENCORE ADOPTÉ dans la référence officielle**
     — chantier isolé, cascade complète nécessaire avant tout chiffre
     définitif (décision utilisateur en attente). GFT : en attente
     (aucun candidat de l'exploration à intégrer).

## Fichiers clés créés cette session (tous suivis par git)

- `chantier_position_cap_2026-08-15.py`,
  `verif_clustering_14aout_2026-08-15.py` — chantier plafond de position.
- `chantier2_section1_slippage_631_2026-08-15.py`,
  `chantier2_section1_frictions_bdef_2026-08-15.py`,
  `chantier2_section1_assemble_2026-08-15.py`,
  `chantier2_section2_stability_bayes_2026-08-15.py` — Chantier 2 rigueur
  statistique.
- `chantier_instant_funding_phase2_2026-08-15.py`,
  `chantier_instant_funding_risk_sweep_2026-08-15.py`,
  `chantier_gft_instant_exploration_2026-08-15.py` — instant funding
  compte isolé (Phase 2 + exploration GFT).
- `chantier_blueberry_switch_2026-08-15.py` — 🔴 bascule conditionnelle
  FLOTTE COMPLÈTE (copie modifiée de `chantier_position_cap_2026-08-15
  .py`/etape_aq, format Blueberry devient un attribut PAR COMPTE au lieu
  d'être fixé par groupe — pattern réutilisable si un futur chantier GFT
  a besoin du même mécanisme).

## Décisions bloquantes qui restent ouvertes

1. **Adoption du seuil de bascule Blueberry** (§7.1) — dépend du choix
   de plafond personnel (960$ vs 5000$, décision #9 toujours ouverte par
   ailleurs). Si adopté, nécessite une régénération complète de la
   cascade (comme le 08/12 pour RR1,35/corr0,80) avant de figer §1.8.
2. Choix final config 1 vs config 4 dual-trader à 3000$ (ancien, jamais
   tranché, inchangé cette session).
3. Plafond personnel réel unique (960$/3000$/5000$) — décision #9,
   toujours ouverte, prend maintenant une importance directe pour le
   seuil Blueberry ci-dessus.
4. Rank-and-rent : conclusion "démarrer maintenant à 960$" toujours pas
   confirmée explicitement en retour par l'utilisateur (inchangé).

## Note de méthode nouvelle cette session

Le pattern "format par compte" introduit dans
`chantier_blueberry_switch_2026-08-15.py` (chaque `acc` porte son propre
`_fmt_key`, réévalué à chaque ouverture/réouverture selon l'état de la
réserve, au lieu d'un format fixe par groupe de firm) est réutilisable
tel quel pour un futur chantier GFT bascule conditionnelle, ou tout autre
mécanisme de format dynamique — pas besoin de le réécrire depuis zéro.
