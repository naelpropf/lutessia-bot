# Prompt pour la prochaine session

Copier-coller le bloc ci-dessous tel quel au début de la prochaine session.

---

CONTEXTE : reprise du projet trading prop firms. Lis dans l'ordre :
1. `session_handoff_2026-08-18.md` (racine du dépôt) — chronologie
   complète de la session précédente (correction risque Instant régénérée
   n=600, découverte + correction d'un bug de filtre forex-only affectant
   toute population du projet, extension de la matrice de corrélation aux
   indices, routage optimal des indices vers Stratégie B).
2. `registre_parametres_projet.md` §1.8bis (nouveau) — correction risque
   Instant + impact du correctif forex-only sur la référence A.
3. `registre_strategie_trading.md` §2.45-2.47 (nouveaux) — risque
   Instant détaillé, bug filtre forex-only, routage indices vers B.

Résume-moi en bref l'état actuel : (1) la correction du risque Instant
(1,5%/trade réel au lieu de 1,90% flotte standard) — confirmée n=600,
§1.8 régénéré et remplace définitivement les anciens chiffres, dominance
stricte SURVIT mais ~33-37% du gain annoncé s'évapore, (2) le bug filtre
forex-only trouvé et CORRIGÉ dans le code (`rr_threshold_test.py:43-61`)
— 321 trades indices étaient jetés silencieusement, impact +17,6% de
volume sur A (631→742) et +14,7% sur B (401→460), EV quasi inchangée
dans les deux cas, (3) la matrice de corrélation étendue aux indices
(19×19, `correlation_matrix.csv`) et la découverte que l'exécution live
des indices n'est PAS possible en l'état (2 blocages précis dans
`app.py`, whitelist + mapping symbole broker manquants), (4) le résultat
du routage optimal des indices vers B ("tout indices→B" domine largement
le routage par RR, +43-46% profit, mais effet régime-dépendant confirmé
par stress-test — nuance à ne pas perdre), (5) les décisions bloquantes
qui restent ouvertes — en particulier §1.8/§2.35 jamais régénérés en
flotte complète avec la population élargie (742 trades, seulement mesuré
en EV isolé jusqu'ici), l'adoption officielle de §1.8 dans son ensemble
(statut inchangé, en attente depuis plusieurs sessions), et le travail
d'ingénierie live (whitelist+mapping broker) non fait si le routage
indices devient prioritaire.

Règles de méthode habituelles : ne jamais faire confiance à un chiffre
sans vérifier sa config exacte ; citer le code plutôt que supposer ;
n=300 exploration / n=600 confirmation avec stress-test H1/H2+4blocs
AVANT tout calcul de sizing ou toute conclusion sur un écart net (deux
bugs de fondation trouvés cette session en creusant des questions
précises, pas en cherchant activement — rester vigilant) ; toujours faire
un test de fumée (n=5) avant un run n=300/600 ; tout résultat va dans le
registre, pas seulement en réponse ; répondre en français.
