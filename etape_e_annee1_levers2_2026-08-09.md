# Étape E — Recherche de leviers annee1<0, round 2 : nouveaux degrés de liberté (08/09/2026)

*Suite de `etape_e_annee1_levers_2026-08-09.md` (4 leviers déjà épuisés :
seuil FTMO, étalement calendaire, rampe classique/ciblée — aucun gain net).
Cette session teste 2 nouveaux mécanismes jamais explorés, plus une
vérification à coût nul. Script : `etape_e_annee1_levers2_2026-08-09.py`.
Config de base : REF, éval=1,00%/flotte=1,90%/GFT=1,75%, seuils actuels,
plafond 1000$, n=300.*

**Conclusion en une phrase : aucun des trois points ne donne de gain net —
un est clairement négatif (point 2), l'autre est dans le bruit partout
(point 3), le troisième n'a pas pu être vérifié faute de données (point 1).
Aucun changement de config, aucune confirmation n=600 déclenchée.**

---

## Point 1 — Vérification p10/p25 sur données existantes (pas de nouvelle simu)

Les fichiers `etape_e_risk_sweep_results.csv` et `etape_e_cascade_check_
results.csv` (derniers resweeps complets) ne contiennent QUE des agrégats
par config (profit moyen, ruine%, année1<0%, casses moyennes) — **aucun
run individuel n'a été conservé**, uniquement calculé en mémoire lors de
l'exécution originale (`etape_e_risk_sweep.py`/`etape_e_cascade_check.py`
ne sauvegardent jamais le DataFrame par-run, seulement `row = dict(...)`
agrégé). **Impossible de calculer p10/p25 rétroactivement sans relancer
les simulations** — conformément à la consigne, ce point n'a déclenché
aucune nouvelle simulation. Si cette question reste pertinente, il
faudrait relancer le resweep en sauvegardant `df` brut par config (coût :
même temps de calcul que le resweep original, ~48 configs à re-simuler).

---

## Point 2 — Redémarrage asymétrique des comptes supplémentaires

Hypothèse testée : à la casse d'un compte SUPPLÉMENTAIRE (Blueberry/FTMO/
GFT, cf. `GROWTH_FIRMS_EXTRA`) déjà financé, le rouvrir au plus petit
palier viable de la firm (`BASE_PALIER[gname]`, moitié du palier extra
standard) au lieu de sa taille d'origine, pour réduire le coût immédiat du
restart.

| Config | Profit | Ruine | Année1<0 (pré/post) | Casses post-déblocage (moy.) | Casse≤30j | Casse≤60j |
|---|---|---|---|---|---|---|
| Baseline (réouverture taille identique) | 4 334 759$ | 1,33% | 27,00% (18,67%/8,33%) | 54,0 | 21,65% | 39,66% |
| Downsize (réouverture au palier de base) | 4 209 294$ (**-2,9%**) | 1,33% | 27,33% | 65,6 (**+21,5%**) | 22,54% | 41,46% |

**Résultat net négatif, sans ambiguïté** : profit -2,9%, année1<0 pas
amélioré (18,67%/8,33% → 18,67%/8,67%), et surtout **le nombre de casses
post-déblocage AUGMENTE de 21,5%** (54,0→65,6) au lieu de baisser — le
levier produit l'effet inverse de l'intention. Explication probable : le
coût de réouverture plus faible accélère le cycle casse→réouverture (moins
d'attente sur la réserve), ce qui multiplie les cycles casse-restart
comptés dans la fenêtre plutôt que de les éviter, sans que le compte
regrossisse jamais (aucun mécanisme de croissance individuelle n'existe
pour compenser, comme documenté dans `etape_e_fleet_integration.py`). Le
cascade check est aussi légèrement dégradé (casse≤30j/60j en hausse).
**Levier rejeté, pas de confirmation n=600.**

---

## Point 3 — Risque dégressif en fin de phase d'évaluation

Réduction du risque par trade quand un compte en phase "challenge"
(éval initiale OU restart après casse) entre dans les X% derniers du
chemin restant vers sa cible de palier.

| Config | Profit | Ruine | Année1<0 total | dont pré | dont post | Casses moy. |
|---|---|---|---|---|---|---|
| Baseline (pas de dégressif) | 4 334 759$ | 1,33% | 27,00% | 18,67% | 8,33% | 186 |
| Fenêtre 10%, facteur 0,5 | 4 338 431$ (+0,08%) | 1,33% | 27,00% | 18,33% | 8,67% | 187 |
| Fenêtre 20%, facteur 0,5 | 4 307 863$ (-0,62%) | 1,33% | **28,67%** | 19,67% | 9,00% | 189 |
| Fenêtre 20%, facteur 0,7 | 4 346 516$ (+0,27%) | 1,33% | 27,67% | 18,33% | 9,33% | 188 |

**Aucune variante ne montre de gain net.** La fenêtre 10%/facteur 0,5 est
neutre (bruit pur, écarts <0,1pt partout). La fenêtre 20%/facteur 0,5 est
franchement pire (année1<0 +1,67pt, profit -0,62%) — réduire le risque sur
une fenêtre trop large ralentit trop la progression vers la cible et
allonge le temps passé en phase challenge (proportionnellement plus de
fenêtres où une casse peut survenir), sans que le gain en probabilité de
casse "au moment critique" compense. La fenêtre 20%/facteur 0,7 (réduction
plus légère) revient à un résultat quasi neutre à légèrement positif sur
le profit mais légèrement négatif sur année1<0 — pas un signal cohérent
dans une direction claire. **Aucune variante retenue, pas de confirmation
n=600.**

---

## Conclusion générale

Sur les 3 points demandés : le point 1 n'a pas pu être vérifié (données
non conservées), le point 2 est net négatif, le point 3 est neutre dans
le bruit sur toutes les variantes testées. **Aucun changement de config
appliqué.** Combiné au round précédent (`etape_e_annee1_levers_2026-08-09.
md`, 4 leviers épuisés : seuil FTMO, étalement calendaire, rampe classique
et ciblée), ce sont maintenant **6 leviers distincts testés sans gain net**
sur année1<0 (~27-31% selon les runs, dans la même bande de bruit à
n=300). Le taux actuel (confirmé n=600 dans `etape_e_diagnostic_annee1_
2026-08-09.md` à 27,8%) semble être un plancher structurel du mécanisme de
restart complet (P1+P2) sous ce moteur, pas un point que ces catégories de
leviers (risque, seuils, calendrier, taille de compte) peuvent déplacer
significativement.
