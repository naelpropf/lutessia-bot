# Étape Z (08/10 nuit, suite 10) — Seuil copytrade Fivers 500k + vérification de la casse/reset

## Question 1 — Seuil 500k Fivers : DÉPASSEMENT QUASI SYSTÉMATIQUE, très large

`etape_z_fivers_500k_check_2026-08-10.py`, copie exacte de `etape_q`
(config officielle REF+V2+FTMO-10%+GoatGuard, structure Fivers actuelle
à 4 comptes fixes — mécanisme extra-compte déjà testé et rejeté en
Étape Y). Trajectoire trackée à chaque pas de temps :
`fivers_total = Σ(palier + cumulative_since_reset)` sur les comptes
Fivers actifs — cette dernière variable est la meilleure proxy du solde
réel de chaque compte sur la plateforme, puisque le split du trader est
crédité en continu dans `state["reserve"]` sans jamais réduire
`cumulative_since_reset` (voir Question 2 ci-dessous pour la preuve).

**Résultat n=600, aucune tolérance de durée (un seul dépassement, même
d'un trade, compte) :**

| Plafond | % runs dépassant 500k | Pic moyen | Pic pire cas | Mois médian du 1er dépassement |
|---|---|---|---|---|
| 1000$ | **99,17%** | 2 126 237$ | 6 009 396$ | 37,4 |
| 3000$ | **99,67%** | 2 132 396$ | 6 009 396$ | 37,4 |

**Verdict : ce n'est pas un dépassement marginal ou occasionnel — c'est
le comportement NORMAL du modèle.** Quasiment tous les runs (99,2-99,7%)
dépassent 500 000$, en moyenne à **4,3× le seuil** (~2,13M$), et jusqu'à
**12× le seuil** dans le pire cas observé (6,0M$). Le dépassement
survient typiquement après ~3 ans (mois 37), une fois que les comptes
Fivers financés ont accumulé plusieurs années de profit trading sans
jamais avoir été remis à zéro.

**Cause mécanique** : `cumulative_since_reset` (le solde flottant de
chaque compte) n'a **aucun plafond haut** dans le moteur — le DD statique
(mode Fivers High Stakes) ne vérifie que le plancher bas
(`-cumulative_since_reset >= seuil`), jamais un plafond de croissance.
Le risque par trade est calculé sur le **palier fixe** (`risk_amount =
eff_risk/100 * acc["palier"]`), pas sur l'équité courante — donc le
solde croît à peu près linéairement (pas de sizing dynamique qui
ralentirait la croissance), sans jamais être "prélevé" côté plateforme
dans le modèle actuel. Sur 4 comptes × ~4 ans à risque flotte 1,90%, le
cumul dépasse largement 500k$ dans la quasi-totalité des tirages.

**Ce diagnostic ne dit PAS si c'est un bug de modélisation ou un vrai
risque opérationnel** (dans la réalité, un trader recevrait probablement
des retraits périodiques qui videraient le solde régulièrement — le
moteur ne modélise aucun événement de retrait) — juste que **tel que le
moteur est actuellement construit, la contrainte 500k$ confirmée par le
support Fivers serait quasi systématiquement violée** si elle était
appliquée à la lettre. Aucune correction faite — diagnostic seul,
comme demandé.

## Question 2 — Perte de profit non retiré à la casse : **(a) confirmé, aucune perte**

Voir code cité en chat (`engine_multiformat.py:337-367`). Le split du
trader (`total_funded_pnl`) et le versement réel en réserve
(`state["reserve"]`) sont crédités **trade par trade**, dans le même
appel de fonction et AVANT la détection de casse pour ce même trade.
`_reset_trackers()` (appelé sur casse) ne touche QUE les variables de
suivi de drawdown (`cumulative_since_reset`, `peak_since_reset`,
`trading_days_since_reset`, `daily_pnl`, `locked_peak`, `eod_peak`,
`last_day_seen`) — jamais `total_funded_pnl` ni `total_fees_paid`.
**Aucun profit n'est perdu au reset** : le mécanisme capture déjà
correctement ce risque. Pas de quantification nécessaire (montant nul
par construction, pas juste petit).
