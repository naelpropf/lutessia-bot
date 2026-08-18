# Synthèse de recherche — Points factuels non sourcés (prop firms & fiscalité SASU)

*Recherche effectuée le 06/08/2026. Chaque affirmation est accompagnée de sa source. Les points non confirmés officiellement sont signalés explicitement.*

---

## 1. Barème de split prop firm par firm et par palier

### FTMO
- **Split initial** : 80% (Challenge 2-Step) / 90% (Challenge 1-Step, mais mécanisme différent — non cumulable au solde). Source officielle : [FTMO FAQ — retrait des profits](https://ftmo.com/en/faq/how-do-i-withdraw-my-profits/), consulté 06/08/2026. Citation : *« You receive 80% of the profit (increases to 90% if Scaling Plan or Premium Programme conditions are met). »*
- **Mécanisme d'évolution** : deux voies indépendantes et cumulables, toutes deux confirmées officiellement :
  - **Scaling Plan** ([page officielle](https://ftmo.com/en/reward-growth-and-scaling-plan/)) : 4 mois d'ancienneté minimum, ≥10% de profit net cumulé, ≥2 payouts traités, solde positif → +25% de taille de compte tous les 4 mois (jusqu'à 2M$), avec bascule à 90% associée.
  - **Premium Programme** ([page officielle](https://ftmo.com/en/premium-programme/)) : niveau « Prime » (4 mois + risque maîtrisé) → 90% ; niveau « Supreme » (3 mois de plus, 3 payouts additionnels, aucun échec) → maintien à 90%.
- **Plafond** : **90%**, confirmé partout, aucune mention d'un split supérieur.
- **Verdict sur l'hypothèse projet (« 80% → +5pt/upgrade → plafonné 90% »)** : point de départ et plafond corrects, **mais le mécanisme réel est une bascule binaire par seuil (80→90%), pas une progression graduelle par paliers de 5 points**. À corriger dans le modèle.

### The5%ers
- **Point de vigilance nom de programme** : le nom actuel officiel n'est pas « Summer Plan » mais **« High Stakes »**. The5%ers propose 4 programmes distincts avec barèmes différents : Bootcamp, Hyper Growth, Pro Growth, High Stakes. Sources officielles : [structure des programmes](https://the5ers.com/challenge-programs-bootcamp-high-stakes-hyper-growth-explained/), [FAQ split JP](https://the5ers.com/jp/faqs/the5ers-利益配分の仕組み/), [page High Stakes](https://the5ers.com/high-stakes/), consultés 06/08/2026.
- **Barème confirmé officiellement** :

| Programme | % initial | % max | Condition de progression |
|---|---|---|---|
| Hyper Growth | 50% | 100% | 10% de profit vs solde |
| Bootcamp | 50% (après passage en live) | 100% | 5% de profit vs solde |
| Pro Growth | 75% | 100% | 10% de profit vs solde |
| High Stakes | 80% | 100% | 10% de profit + 3 jours profitables |

- **Grille détaillée des paliers intermédiaires pour High Stakes (80%→85%→90%→100%+bonus)** : ⚠️ **NON CONFIRMÉ officiellement** — trouvée seulement via sources tierces croisées, non vérifiée sur une page officielle avec grille chiffrée précise.
- **Verdict** : l'hypothèse projet est **fausse** — le vrai plafond est **100%**, pas 90%, et le point de départ varie de 50% à 80% selon le programme choisi (pas uniformément 80%).

### Blueberry Funded
- **Split initial** : 80% dès le premier jour pour les comptes « Instant Access » (Elite & Lite). Source officielle : [Help Center — Profit Split Percentages](https://help.blueberryfunded.com/en/articles/11879956-what-are-the-profit-split-percentages), consulté 06/08/2026. Pour le type « évaluation classique », le split initial n'est **pas confirmé** dans cette source.
- **Mécanisme** : [Help Center — Account Scaling](https://help.blueberryfunded.com/en/articles/9762548-blueberry-funded-account-scaling), citation exacte : *« Earn up to 90% of your profits with possibilities for increases of up to 9%. »* Le solde du compte croît de 25% tous les 3 mois si ≥10% de profit net sur 3 mois consécutifs et ≥4 payouts traités. Le détail des incréments de split par palier **n'est pas publié** — seul le total « jusqu'à +9% » est donné.
- **Plafond** : **90%**, confirmé.
- **Verdict** : départ (80%) et plafond (90%) cohérents avec l'hypothèse projet, mais le mécanisme « +5pt par palier » reste **NON CONFIRMÉ** (source tierce uniquement pour le détail des paliers intermédiaires).

**Recommandation transverse** : contacter par écrit le support de FTMO et Blueberry Funded (comme déjà fait pour The5%ers) pour obtenir la grille exacte de paliers intermédiaires si cela affecte significativement les simulations.

---

## 2. Plafonds de capital combiné pour le copytrade entre comptes

### FTMO — CONFIRMÉ officiellement
Source : [FTMO FAQ — How many accounts can I have?](https://ftmo.com/en/faq/how-many-accounts-can-i-have/), consulté 06/08/2026.
- Aucune limite de nombre de comptes.
- **Plafond de capital cumulé « per trader » : 400 000$** (avant scaling), avec équivalents en devises (€320 000, £280 000, etc.).
- Règle anti-contournement : suspension possible si stratégies identiques sur plusieurs comptes dépassant le plafond cumulé.
- **Point non tranché** : le texte officiel ne précise pas explicitement si ce plafond porte uniquement sur le capital **financé**, ou aussi sur le capital en évaluation (contrairement à The5%ers où c'est explicitement financé uniquement). **À clarifier par écrit avec le support FTMO.**

### Blueberry Funded — chiffre du projet (~400 000$) probablement erroné
Source officielle (document légal PDF) : [Trading Evaluation Outline and Fees, v. 04/03/2026](https://blueberryfunded.com/wp-content/uploads/2026/03/BBF-Trading-Evaluation-Outline-and-Fees.pdf), consulté 06/08/2026.
- Citation exacte (section Scaling Program) : *« Maximum Simulated Capital Allocation per trader of $2 million. »*
- Le copy trading entre comptes détenus par le même trader est explicitement autorisé (via Traders Connect, Duplikum, Social Trader Tools, CopyFx) — [Help Center officiel](https://help.blueberryfunded.com/en/articles/9550602-am-i-allowed-to-copy-trade), consulté 06/08/2026.
- **Ambiguïté restante** : la formulation « per trader » n'indique pas explicitement si les 2M$ sont un plafond cumulé sur tous les comptes financés, ou le plafond atteignable par un seul compte via scaling. Aucune mention d'un nombre max de comptes simultanés.
- **Verdict** : le chiffre de **~400 000$ actuellement utilisé dans le projet ne correspond à aucune source officielle Blueberry Funded trouvée**. Le chiffre officiel trouvé est **2 000 000$ « per trader »**, sous réserve de lever l'ambiguïté cumulé/par-compte par écrit auprès du support. **Écart majeur à corriger dans le modèle, en attendant confirmation écrite.**

---

## 3. Ment Funding — clarification du modèle

Source officielle : [mentfunding.com](https://mentfunding.com) (site à ancres, contenu partiellement extractible), consulté 06/08/2026.

- **Évaluation vs instant funding pour 2M$** : le compte à 2M$ passe par une **évaluation en 1 étape (« 1-step evaluation »)**, il n'y a **pas de programme instant funding sans évaluation** documenté sur le site officiel pour ce palier. Citation trouvée : *« Only direct sizes up to $1M qualify for scaling — the $2M tier is not scalable. »*
- **Grille de prix** : seul le prix du palier 1M$ est confirmé officiellement (8 600$, prix promo affiché sur le site). Le reste de la grille (25k à 2M$) provient de **sources tierces non officielles** (proptrusted.com, tradingfinder.com), cohérentes entre elles et avec le prix officiel du palier 1M — mais **NON CONFIRMÉES officiellement**. À revérifier manuellement sur le sélecteur interactif du site avant tout engagement.
- **Plafond de capital combiné pour copytrade multi-comptes** : **aucune règle explicite trouvée**. Le seul point pertinent dans les [Terms of Service officiels](https://mentfunding.com/terms-of-service.html) : *« Traders are limited to one active account per challenge level, absent prior written approval. »* — un seul compte actif par palier, mais rien n'interdit explicitement un compte par palier différent (25k+50k+...+2M) copytradé ensemble. **Absence de règle écrite ≠ autorisation garantie — à confirmer par écrit avec le support avant de construire la stratégie dessus.**
- **Daily drawdown** : 5% du solde de clôture de la veille (balance-based), reset à 17h00 EST. Drawdown statique global : 6% fixe sous le solde de départ, ne trail pas les profits.
- **Weekend holding** : positions à fermer avant 15h45 EST le vendredi par défaut ; possibilité de garder les positions le week-end uniquement via une option payante additionnelle au checkout.

---

## 4. FXIFY — résolution de l'écart 795k$ vs 805k$

Source officielle : [FXIFY FAQ — What's the max allocation](https://fxify.com/faqs/all-faqs/what-the-max-allocation/), consulté 06/08/2026.

- **Le chiffre « 795 000$ » n'existe nulle part** — ni sur le site officiel FXIFY, ni dans les sources tierces consultées. Il semble erroné à la source dans les documents du projet.
- La FAQ officielle liste elle-même les 8 paliers exacts (5k+10k+15k+25k+50k+100k+200k+400k), soit **805 000$** — cohérent avec les simulations du projet.
- **Mais la même page FAQ énonce ensuite, dans sa prose, « up to 800k »** — un chiffre arrondi incohérent avec sa propre liste de paliers juste au-dessus (805k). C'est une incohérence interne de FXIFY (805k listé vs 800k énoncé), pas un écart avec 795k.
- Une source tierce ([thegodfunded.com](https://thegodfunded.com/en/blog/prop-firms-with-highest-maximum-capital-allocation/)) confirme indépendamment le chiffre de 805 000$.
- **Conclusion : utiliser 805 000$** (somme vérifiable des 8 paliers officiels) comme plafond de capital combiné FXIFY. Le « 800k » de la FAQ est une approximation marketing non mise à jour. L'origine du « 795k » utilisé dans le projet reste à identifier dans vos documents source — aucune trace trouvée en ligne.

---

## 5. Experts-comptables / avocats fiscalistes spécialisés prop firm en France

**Constat général : le marché français ne compte, à ce jour, aucun cabinet avec une preuve solide et vérifiable (avis clients nommés, cas traités publiquement) sur la fiscalité spécifique des prop firms.** Sujet trop récent et trop niche (essor retail 2022-2024).

### Meilleur candidat identifié : Excilio (expert-comptable, Ordre des experts-comptables)
- Page dédiée : [excilio.fr/expert-comptable-prop-firm](https://www.excilio.fr/expert-comptable-prop-firm), + 5 articles dédiés (fiscalité prop firm, statut juridique prop trading, modèle économique 2026, etc.)
- Points couverts avec justesse : payouts = revenus d'activité indépendante (pas des salaires) ; risque de requalification en l'absence de structure ; surveillance des flux internationaux (FTMO en Rép. Tchèque) ; TVA en autoliquidation ; comparatif micro-entreprise / EI réel / SASU-EURL.
- Note Google 4,9/5 (134 avis) mais généraliste digital/e-commerce/crypto — **aucun avis nommant spécifiquement un dossier prop firm**.
- **Niveau de preuve : moyen-bon — meilleur candidat, à contacter directement pour vérifier le nombre réel de dossiers prop firm traités.**

### Candidat secondaire : MON Comptable TRADING (comptable-en-ligne.fr)
- [trading.comptable-en-ligne.fr](https://trading.comptable-en-ligne.fr/), cabinet membre de l'Ordre, spécialisé trading en général (IR/IS/holding), basé en Île-de-France.
- Leur article sur les prop firms ne développe **pas** la fiscalité spécifique — orienté mise en garde anti-arnaque plutôt qu'optimisation fiscale.
- **Niveau de preuve : faible — utile pour la structuration générale, pas de preuve d'expérience prop firm spécifique.**

### Sites écartés (contenu marketing/affiliation, pas des professionnels agréés)
Cercle PPM, Track360, PropFirmLab, TradingPropFirm.com, Bobby Trading, ALTI Trading, Trading Education, Lucas Prop Firm, Portail Propfirm, Finance Héros, Superindep.fr, Légavox/« Droit du Web ». Contenus parfois détaillés mais sans auteur identifié comme expert-comptable ou avocat agréé — utilisables comme lecture de préparation, jamais comme base de décision fiscale.

### Avocats fiscalistes
- **Aucun avocat fiscaliste communiquant explicitement sur les prop firms n'a été identifié.**
- Le « réseau Avocats-litiges-financiers.fr » est positionné sur le contentieux anti-arnaque Forex/crypto, **pas** sur le conseil fiscal amont — non pertinent pour la structuration.
- Pistes générales sans preuve documentée sur le sujet précis : Uzan Avocat (fiscalité internationale), Beaubourg Avocats (fiscaliste crypto — profil adjacent intéressant côté flux internationaux), annuaire Legal 500 Paris (droit fiscal).

**Recommandation** : contacter Excilio en priorité pour évaluer leur expérience réelle prop firm, compléter par une consultation ponctuelle avec un fiscaliste généraliste (international/crypto, ex. Beaubourg Avocats) pour sécuriser la requalification et les flux étrangers.

---

## 6. Charges sociales réelles — président SASU ~50 000€/an

- **PASS 2026 confirmé : 48 060€/an** (4 005€/mois), +2% vs 2025. Sources : [Previssima](https://www.previssima.fr/actualite/cest-officiel-le-pass-setablira-bien-a-48-060-au-1er-janvier-2026.html), [Urssaf.fr](https://www.urssaf.fr/accueil/actualites/plafond-annuel-securite-sociale.html), [Bpifrance Création](https://bpifrance-creation.fr/entrepreneur/actualites/plafonds-securite-sociale-2026). Votre hypothèse de ~47 100€ était légèrement sous-estimée.
- **Limite méthodologique** : le simulateur officiel URSSAF (mon-entreprise.urssaf.fr) est une app JS interactive qui n'a pas pu être exécutée par l'outil de recherche automatisé — **il est recommandé de le faire tourner vous-même** : https://mon-entreprise.urssaf.fr/simulateurs/salaire-brut-net. Les chiffres ci-dessous sont une reconstitution manuelle cotisation-par-cotisation à partir de barèmes 2026 publiés, pas une sortie brute d'un simulateur officiel.
- **Simulation à 50 000€ brut/an (~1 940€ au-dessus du PASS)** : charges patronales ≈19 411€ (38,8%), charges salariales ≈10 409€ (20,8%), net avant IR ≈39 591€, coût total employeur ≈69 411€. **Taux de charges/net ≈ 75,3%.**
- **Comparaison à 30 000€ brut/an (entièrement sous le PASS)** : taux de charges/net ≈ 75,5% — **quasiment identique**.
- **Comparaison pour 50 000€ net/an (brut nécessaire ≈63 100€, en partie en tranche 2 Agirc-Arrco)** : taux de charges/net ≈ 74,4% — **toujours stable**.
- **Explication technique** : au-dessus du PASS, le taux Agirc-Arrco+CEG en tranche 2 (≈24,3%) est plus élevé qu'en tranche 1 (≈10,0%), MAIS la cotisation vieillesse plafonnée (15,45%) et la prévoyance cadre obligatoire (1,5% patronal) disparaissent au-delà du plafond. Ces deux effets s'annulent presque : taux marginal ≈59,7% sous le PASS vs ≈57,1% au-dessus — **le taux marginal baisse légèrement au-delà du plafond**, contrairement à l'intuition.
- **Conclusion : à ~50 000€/an (brut ou net), le taux de charges reste stable dans le bas de la fourchette 65-82% généralement citée, autour de 74-75%, sans rupture liée au PASS.** Il faudrait des rémunérations nettement plus élevées (70-100k€+) pour qu'un effet significatif apparaisse, et même alors l'effet resterait modéré et plutôt à la baisse.
- Sources détail des taux 2026 : [bulletin-paie.com — taux cotisations 2026](https://bulletin-paie.com/cotisations/taux/), [bulletin-paie.com — détail cotisations](https://bulletin-paie.com/outils/detail-cotisations/). Confirmation exclusion chômage/AGS pour le président sans contrat de travail : [lecoindesentrepreneurs.fr](https://www.lecoindesentrepreneurs.fr/pourquoi-protection-sociale-president-sasu-coute-cher/).
- **Point à vérifier séparément** : taux AT/MP réel selon l'activité (utilisé ≈2,12% indicatif) et assujettissement formation professionnelle pour un président sans contrat de travail (point débattu, impact mineur).

---

## Récapitulatif des points nécessitant une confirmation écrite du support (à faire pour sécuriser le modèle)

1. FTMO : le plafond de 400 000$ cumulés porte-t-il sur le capital financé uniquement, ou aussi sur le capital en évaluation ?
2. Blueberry Funded : le chiffre de 2M$ « per trader » est-il un plafond cumulé multi-comptes, ou le plafond atteignable par un seul compte via scaling ?
3. FTMO, Blueberry Funded : grille exacte des paliers intermédiaires de profit-share (entre le point de départ et le plafond).
4. Ment Funding : le copytrade multi-comptes/multi-paliers est-il explicitement autorisé (absence de règle écrite n'étant pas une garantie) ?
5. Ment Funding : grille de prix complète (seul le palier 1M$ est confirmé officiellement).
