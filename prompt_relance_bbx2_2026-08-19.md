# Contexte projet — Lutessia Copytrade — régénération §2.35 et BBx2/BB+GFT sous la pile corrigée

Tu es Claude Code, moteur de simulation Python pour un projet de copytrade.
Reprends le contexte via `session_handoff_2026-08-19_soir2.md` en premier,
puis `registre_strategie_trading.md` §2.35 (lignes 1651-1806) et §2.41-2.42
(lignes 1970-2013), puis `registre_strategie_trading.md` §2.45 (lignes
2160-2229) avant de répondre.

**Découverte de fin de session précédente (rappel)** : §2.35 (rr_tp2>8→×1,6
sizing, chiffre actuellement dans le registre = 8 206 650$/13,17% année1<0
@3000-5000$) et §2.41/§2.42 (BBx2/BB+GFT jour0, 8 487 070$/10,00% @5000$
pour BBx2) sont TOUS LES DEUX construits AVANT deux corrections déjà
appliquées au projet :
1. Cap de risque Instant corrigé 1,90%→1,5% (§2.45, `chantier_S1_8_
   officiel_n600_risque_corrige_2026-08-17.py`) — preuve : la base
   "COMBINÉ" utilisée par §2.35 (7 080 725$) correspond exactement au
   chiffre "non corrigé (ancien)" du tableau §2.45.
2. Bug forex-only corrigé (§1.8bis, population A 631→742 trades).

Sur le COMBINÉ seul, la correction #1 a coûté -5,47% profit et +1,84pt
année1<0 (dégradation réelle) à 3000$/5000$ — un ordre de grandeur
comparable ou pire est probable ici mais jamais mesuré.

**Objectif : relancer §2.35 (rr_tp2 sizing) et BBx2 (piste A, 2 comptes
Blueberry) sous la pile actuelle (cap Instant 1,5% + population 742
trades), et mettre à jour le registre avec les chiffres corrects.**

**Règles méthodologiques :**
- n=300 screening → n=600 + stress-test H1/H2+4blocs pour toute adoption,
  comme l'original.
- Citation exacte fichier:ligne pour tout réemploi de mécanisme.
- Comparer explicitement ancien (stale) vs nouveau (corrigé) chiffre à
  chaque étape, comme fait pour la correction du cap Instant en §2.45.

---

## Étape 1 — Régénération §2.35 (rr_tp2>8→×1,6)

1. Reprendre `chantier_rrtp2_sizing_2026-08-16.py`, vérifier qu'il tourne
   bien sur le cap Instant 1,5% corrigé (`chantier_S1_8_officiel_n600_
   risque_corrige_2026-08-17.py`) et la population 742 trades (`rr_
   threshold_test.build_extended_population`) — sinon adapter.
2. Nouvelle base "COMBINÉ" corrigée (déjà connue : 6 693 474$/15,67%
   année1<0 @3000-5000$, `registre_strategie_trading.md:2212-2213`) —
   confirmer qu'elle sert bien de référence pour le delta §2.35.
3. n=300 puis n=600 + stress-test H1/H2+4blocs, 4 plafonds (960$/1000$/
   3000$/5000$). Comparer explicitement à l'ancien 8 206 650$/13,17%.

## Étape 2 — Régénération BBx2 et BB+GFT jour0

1. Reprendre `chantier_pisteAB_bbx2_bbgft_2026-08-17.py` /
   `chantier_n600_pisteAB_2026-08-17.py`, même vérification cap Instant +
   population 742.
2. Nouvelle base = §2.35 régénéré (Étape 1), pas l'ancien 8 206 650$.
3. n=300 puis n=600 + stress-test, plafond 5000$ (seul plafond où BBx2/
   BB+GFT étaient dominants), 4 axes (profit/solde_neg/hit_ceiling/
   année1<0). Comparer explicitement à l'ancien 8 487 070$/10,00%
   (BBx2) et 8 324 100$/10,17% (BB+GFT).

## Format de réponse attendu

Étape 1 : tableau ancien vs nouveau §2.35 (4 plafonds). Étape 2 : tableau
ancien vs nouveau BBx2/BB+GFT (5000$). Conclusion : les verdicts
d'adoption ("GO technique") tiennent-ils toujours sous la pile corrigée,
et mise à jour explicite du registre avec les chiffres corrects.
