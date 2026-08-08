# Contexte VPS Lutessia — 6-7 août 2026

Mémoire de reprise côté **VPS/exploitation live** (session Claude Code tournant sur le
serveur Windows qui héberge `app.py`/`monitor.py`/MT5). Complémentaire au contexte
stratégie côté PC (`contexte_projet_lutessia_2026-08-07-v3.md`, simulations Monte
Carlo/dimensionnement flotte) — les deux sessions collaborent uniquement via commits
git sur ce repo, aucune mémoire partagée directe.

## 1. État du bot au moment de l'écriture

- `app.py` et `monitor.py` tournent en arrière-plan sur le VPS (lancés manuellement via
  `nohup ... & disown` dans une session RDP, PAS via un service Windows — MT5 nécessite
  une session interactive, cf. section 4).
- Seul compte actif : `compte_1` (Pepperstone démo, `PepperstoneUK-Demo`, login
  62134005) — c'est le compte qui a servi à tout tester jusqu'ici, pas un vrai compte
  de prop firm.
- Position ouverte : NZD/USD ticket `81685339` (SL 0.5847, TP 0.5989 — corrigé le
  06/08, était resté à l'ancien TP1 0.5921 pendant plusieurs jours, cf. section 3).

## 2. Compte BlueBerry (5104059, BlueBerryMarketsSVG-Live) — EN PAUSE

Compte de test réel (5k€) destiné à collecter des données d'exécution avant
l'ouverture des 3 comptes principaux. **Actuellement commenté dans `.env`** (identifiants
conservés en commentaire) car la connexion programmatique échoue systématiquement :

- Connexion manuelle via l'interface MT5 : **fonctionne** (solde/équité affichés
  normalement, confirmé par capture d'écran).
- `MetaTrader5.initialize()`/`.login()` en Python : échoue avec `IPC timeout` (-10005),
  ou pire, retourne un succès silencieux tout en restant connecté à un AUTRE compte
  déjà actif sur le même terminal (bug de contournement corrigé côté code, cf. section 3
  point 2 — mais le vrai problème d'authentification BlueBerry lui-même reste entier).
- Reproduit de façon isolée (bot et monitor coupés, aucune contention), donc pas un
  problème de concurrence — l'hypothèse retenue est une restriction broker sur l'accès
  API/trading automatisé, distincte du login GUI classique.
- **Ticket support ouvert auprès de BlueBerry** (message envoyé le 06/08, réponse
  attendue sous 1-2 jours). Ne rien retenter tant que le support n'a pas répondu — le
  user préviendra.
- Pour réactiver une fois débloqué : décommenter les 4 lignes `MT5_LOGIN_2`/
  `MT5_PASSWORD_2`/`MT5_SERVER_2`/`MT5_ACCOUNT_ID_2` dans `.env`, relancer `app.py`/
  `monitor.py`.

## 3. Bugs trouvés et corrigés cette session (tous testés en mock, déployés, poussés)

1. **`app_mt5.connect()` faisait confiance à `mt5.initialize()` sans vérifier le compte
   réellement actif** — un compte déjà connecté peut faire échouer silencieusement la
   bascule vers un autre compte tout en rapportant un succès. Corrigé par une
   vérification post-connexion (`account_info().login`) + retentative via `mt5.login()`
   explicite. Risque réel pour la flotte copytrade à plusieurs comptes (mauvais compte
   utilisé pour l'exécution/sizing). Commit `9e3fc93`.
2. **Signal rejeté par "aucun compte éligible" (actif corrélé, plafond atteint) ne
   notifiait jamais Telegram** — contrairement à tous les autres rejets. Reproduit
   avec un vrai cas (AUD/USD du 05/08, corrélé 0.85 à NZD/USD déjà ouvert, seuil 0.6).
   Corrigé. Commit `9e3fc93`.
3. **TP du ticket NZD/USD 81685339 resté à l'ancien TP1 (0.5921) au lieu de tp2_init
   (0.5989)** pendant plusieurs jours (le bug de fond avait été corrigé dans le code le
   31/07, mais jamais répercuté sur la position déjà ouverte). Corrigé manuellement le
   06/08 via `modify_position_sltp`.
4. **AutoTrading désactivé côté terminal MT5** (probablement suite à un reboot VPS du
   02/08 — ce paramètre revient souvent à OFF par défaut au redémarrage du terminal) —
   bloquait silencieusement TOUT ordre/modification. Réactivé manuellement dans
   l'interface. À surveiller après tout futur reboot du VPS.
5. **Symbole EURCHF invisible dans le Market Watch** → `calculate_position_size()`
   échouait silencieusement (`symbol_info_tick()` retourne `None` tant que le symbole
   n'est pas sélectionné, même si `symbol_info()` existe). Cause d'un vrai trade EUR/CHF
   manqué le 06/08. Corrigé via `app_mt5._ensure_symbol_visible()` (appelle
   `symbol_select`), appliqué avant tout calcul de taille/passage d'ordre — protège
   contre n'importe quelle paire suivie mais jamais encore tradée sur un compte donné.
   Commit `529e233`.
6. **Deux autres branches d'échec silencieuses dans `executer_signal_reel()`**
   (connexion MT5 impossible, taille de position incalculable) — notifications Telegram
   ajoutées par cohérence avec le point 2. Commit `529e233`.
7. **Tâches planifiées Windows en doublon et cassées** : `LutessiaBotApp` (trigger "At
   logon", fonctionne mais sans boucle de relance) vs `LutessiaBotWrapper` (boucle de
   relance résiliente via `start_bot.ps1`, mais trigger "At system startup" +
   "Interactive only" contradictoire, ne s'est jamais déclenché). **Fix préparé mais PAS
   encore appliqué** (nécessite des droits admin que la session Claude Code n'a pas) :
   commandes `schtasks` à lancer par le user lui-même :
   ```
   schtasks /Change /TN "LutessiaBotApp" /TR "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File \"C:\Users\Administrator\lutessia-bot\start_bot.ps1\""
   schtasks /Delete /TN "LutessiaBotWrapper" /F
   ```

## 4. Notes d'infrastructure importantes (déjà découvertes, ne pas re-déduire)

- MT5 Python (`MetaTrader5` package) nécessite une session Windows **interactive**
  (limitation Session 0) — pas de service Windows classique possible. D'où l'usage de
  tâches planifiées "At logon"/"Interactive only" plutôt qu'un service NSSM.
- Une session RDP **déconnectée** (croix rouge) reste active en arrière-plan côté
  serveur — seul un **logoff complet** ou un **reboot** tue le process. Donc pas besoin
  de garder la RDP ouverte en permanence.
- Un reboot VPS remet potentiellement l'AutoTrading MT5 à OFF (cf. point 4 ci-dessus) —
  à vérifier après chaque reboot, en plus de relancer `app.py`/`monitor.py`.
- Un seul terminal MT5 (`terminal64.exe`) partagé entre tous les comptes — les
  connexions concurrentes (plusieurs process Python appelant `mt5.initialize()` en
  parallèle) peuvent causer des `IPC timeout`, distinct du blocage Cloudflare
  CentralCharts (protection anti-bot du site, cf. verrou mono-instance déjà en place
  dans `app.py`).
- Déploiement manuel standard (tant que le fix scheduled-task n'est pas appliqué) :
  ```
  taskkill //PID <ancien_pid> //F   (x2, app.py + monitor.py)
  rm -f app.lock
  export PYTHONUNBUFFERED=1
  nohup python app.py > app_run.log 2>&1 &
  disown
  nohup python monitor.py > monitor_run.log 2>&1 &
  disown
  ```

## 5. Config live actuelle vs config verrouillée par simulation (07/08)

Le doc PC (`contexte_projet_lutessia_2026-08-07-v3.md`, section 1) a verrouillé une
config optimisée par Monte Carlo. État de son application au code réel :

- ✅ `MIN_RR` : 1.25 (appliqué le 06/08, `app.py`)
- ✅ `TRAILING_STOP_FACTOR` : 0.15 (appliqué le 06/08, `trade_logger.py`)
- ❌ **Rampe de risque 2.0%×5 trades→2.5%** : PAS appliquée, volontairement — décision
  explicite du user de séparer ce changement structurel (nécessite de compter les
  trades par compte, pas juste changer une constante). `RISK_PCT_PER_TRADE` reste fixe
  à 0.5% dans `app_mt5.py`. À faire dans une session dédiée si le user le demande.
- Séquence de lancement recommandée (Blueberry seule, palier 25k) : sans lien direct
  avec le compte de test 5k configuré ici, qui sert uniquement à collecter des
  données avant le vrai lancement.

## 6. Fonctionnalités ajoutées cette session (hors bugfixes)

- `slippage_logger.py` : mesure prix signal vs fill réel, latence email→exécution,
  session horaire — écrit dans `slippage_log.csv` (gitignored), aucun impact sur
  l'exécution.
- Notification Telegram "Signal validé" inclut désormais le R:R (TP1).

## 7. Prochaines étapes probables

- Attendre la réponse BlueBerry, réactiver le compte de test une fois débloqué.
- Appliquer les 2 commandes `schtasks` (section 3.7) pour fiabiliser le redémarrage
  après un futur reboot VPS.
- Décider (séparément) si/quand appliquer la rampe de risque 2.0%→2.5%.
- Point ouvert côté stratégie (pas ce fichier) : split prop firm + fiscalité jamais
  intégrés aux simulations de profit, plafond de cash "pire cas" (3000$) vs budget réel
  (1000€) — cf. doc PC, section 0.
