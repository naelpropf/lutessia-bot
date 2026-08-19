# Contexte VPS Lutessia — 15-19 août 2026

Mémoire de reprise côté **VPS/exploitation live** (session Claude Code tournant sur le
serveur Windows qui héberge `app.py`/`monitor.py`/MT5). Complémentaire au contexte
stratégie côté PC (chercher le `contexte_projet_lutessia_*.md` ou `NEXT_SESSION_PROMPT.md`
le plus récent — simulations Monte Carlo, dimensionnement flotte, recherche stratégie) —
les deux sessions collaborent uniquement via commits git sur ce repo, aucune mémoire
partagée directe. **Toujours faire un `git pull` en tout début de session.**

## 1. État à l'écriture de ce doc

- `app.py` et `monitor.py` tournent via le **nouveau garde-fou** (section 3) — plus de
  lancement manuel `nohup` nécessaire en usage normal.
- Deux comptes actifs en copytrade (même flux de signaux, exécution indépendante) :
  - `compte_1` — Pepperstone démo (`PepperstoneUK-Demo`, login 62134005).
  - `compte_blueberry` — BlueBerry Funded, challenge **Prime Phase 1** (5000$, login
    5104059, serveur `BlueberryMarketsSVG-Live` — **attention à la casse**, `b`
    minuscule à "berry", cf. section 4).
- Drawdown au 19/08 : compte_1 ~3.1% (a déclenché l'alerte précoce à 3%, PAS une pause
  — seuil de pause 5%), compte_blueberry ~2.1%. Rien d'anormal, cf. section 6.
- Dernier commit poussé : `ad06c56`.

## 2. Bugs trouvés et corrigés cette session (tous testés, déployés, poussés)

Six bugs distincts, plusieurs de la même famille ("MT5 renvoie une donnée
transitoirement invalide juste après une connexion/action, le code ne le détecte pas") :

1. **EUR/JPY validé mais jamais exécuté** : tick vide (ask=0) juste après
   `symbol_select()`, le temps que le flux de prix démarre. `_ensure_symbol_visible()`
   attend maintenant un tick valide (~2s). Commit `0971bca`.
2. **EUR/GBP jamais pris sur BlueBerry** : ce broker suffixe ses symboles forex
   (`EURGBP.pi`, pas `EURGBP`) — le code construisait un seul nom de symbole partagé
   entre tous les comptes. Ajout de `MT5Account.symbol_suffix`
   (`MT5_SYMBOL_SUFFIX_2=.pi` dans `.env`) + `to_mt5_symbol()`/`strip_symbol_suffix()`.
   Corrige aussi un bug latent identique dans `account_router.eligible_accounts()`
   (comparaison de symboles pour la détection de corrélation). Commit `46b4c93`.
3. **Pause automatique fantôme (drawdown ~100%)**, déclenchée deux fois (12/08 et
   16/08, ce dernier un week-end marchés fermés) : `mt5.account_info()` peut renvoyer
   un objet "placeholder" juste après une bascule de compte — balance=equity=0.0 —
   probable collision entre `app.py` et `monitor.py` interrogeant le même terminal
   partagé au même moment. Le premier fix (`connect()` seul) était incomplet :
   `check_drawdown()`/`check_drawdown_warning()` font chacun leur propre appel
   `account_info()` après coup. Validation centralisée dans
   `get_validated_account_info()` (login correct + données non dégénérées, retry
   ~2s), utilisée par les trois. Commits `3793d2d`, `fcd14e3`.
4. **5 signaux bloqués en une journée (14/08)** alors que le backtest prévoit ~5
   blocages en 4 ans : les 2 comptes étaient à 3/3 positions (plafond structurel, pas
   un bug de seuil de corrélation — vérifié : aucune des positions occupantes ne
   dépassait 0.45 de corrélation croisée). `compte_blueberry` sert uniquement à
   collecter un maximum de données d'exécution (pas d'objectif de profit) : plafond
   relevé à 50 et risque/trade réduit à 0.25% (au lieu de 0.5%) en contrepartie, via
   nouveaux overrides par compte `MT5Account.max_positions`/`risk_pct`
   (`MT5_MAX_POSITIONS_2`/`MT5_RISK_PCT_2` dans `.env`). `compte_1` inchangé (3
   positions / 0.5%). Commit `8dda4dd`.
5. **`prix_entree` loggé à 0.0 sur TOUS les trades BlueBerry** (RR calculés faux dans
   `trades_reels.csv`, proches de 1.0 au lieu des vraies valeurs) : `result.price`
   (renvoyé par `order_send()`) n'est pas fiable sur ce broker — le ticket de deal y
   diffère du ticket d'ordre/position, contrairement à Pepperstone où ils coïncident.
   `_resolve_real_fill_price()` récupère maintenant le vrai prix via
   `history_deals_get(position=result.order)`. Les 5 lignes historiques du CSV ont été
   réparées manuellement avec les vrais prix. Commit `ad06c56`.
6. **Config live désynchronisée de la config décidée** : `MIN_RR` relevé à 1.35 (était
   1.25) et seuil de corrélation à 0.80 (était 0.60, dans `scaling_simulation.py`,
   source unique importée par `account_router.py`). Commit `f655d72`.

Bugs déjà connus/documentés de sessions précédentes (non retouchés cette session) :
symbole EURCHF invisible (`_ensure_symbol_visible`), notifs Telegram manquantes sur
certains rejets, TP resté à l'ancien TP1 — tous corrigés avant le 07/08, cf. git log.

## 3. Garde-fou de relance automatique (nouveau, 18/08)

**Contexte** : le bot était resté silencieux plus de 5h le 18/08 (12:21→17:15 UTC), et
un **crash système inattendu** est survenu entre-temps (14:38 UTC) — confirmé par
l'event Windows `Kernel-Power ID 41` ("the system has rebooted without cleanly
shutting down"), **PAS un reboot volontaire**. Absence de bugcheck Windows (code ET
string vides) → ressemble à un arrêt brutal déclenché depuis l'**hôte KVM**
(maintenance/incident fournisseur VPS) plutôt qu'un crash noyau Windows ou un bug du
bot. Cause du silence *avant* le crash (12:21→14:37, alors que les services Windows
tournaient normalement) non identifiée avec certitude — le garde-fou ne dépend pas de
comprendre la cause exacte.

**Ce qui a été fait** :
- `start_bot.ps1` réécrit : surveille maintenant `app.py` ET `monitor.py` (boucles de
  relance indépendantes, `monitor.py` via `Start-Job`). Trois bugs latents corrigés au
  passage — **ce script n'avait en réalité jamais pu s'exécuter** avant ce jour
  (fichier sans BOM UTF-8 → erreur de syntaxe au parsing ; `PYTHONUNBUFFERED` absent →
  logs vides pendant des heures ; redirection PowerShell `*>>` qui réencode en UTF-16 →
  mojibake sur les accents/emojis, remplacée par une redirection `cmd.exe` brute au
  niveau OS). Testé en conditions réelles : kill manuel de chaque process, relance
  automatique confirmée en ~10-15s à chaque fois. Commit `5a31ef5`.
- **Branché sur le dossier Démarrage de l'utilisateur**
  (`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\lutessia_watchdog.cmd`),
  PAS sur les tâches planifiées existantes : cette session n'a **aucun droit admin**
  (`Access is denied` sur `schtasks /Change` ET `/Disable`, testé explicitement). Le
  dossier Démarrage, lui, ne nécessite aucune élévation.

**⚠️ Action manuelle requise (le user doit le faire, pas la session Claude Code)** :
les tâches planifiées `LutessiaBotApp` et `LutessiaBotWrapper` existent toujours et se
déclencheront **en parallèle** du nouveau garde-fou au prochain logon. Pas dangereux
(`app.py` a son propre verrou mono-instance `app.lock`, donc pas de doublon
d'exécution réel — juste un process qui échoue proprement), mais à désactiver/supprimer
via l'interface graphique du Planificateur de tâches pour éviter toute confusion
future. Ni l'un ni l'autre n'ont jamais fonctionné correctement de toute façon
(`LutessiaBotApp` : pas de boucle de relance ; `LutessiaBotWrapper` : trigger "At
system startup" + "Interactive only" contradictoire, ne s'est jamais déclenché en
pratique, `Last Run Time` reste à `11/30/1999`).

**Déploiement manuel si besoin** (le garde-fou gère normalement tout seul, mais pour
forcer un redéploiement après un changement de code) :
```powershell
# Trouver et tuer app.py/monitor.py + leur wrapper parent (voir tasklist/Get-CimInstance),
# supprimer app.lock, puis :
Start-Process powershell.exe -ArgumentList '-ExecutionPolicy Bypass -WindowStyle Hidden -File "C:\Users\Administrator\lutessia-bot\start_bot.ps1"' -WindowStyle Hidden
```
Ou plus simplement : tuer app.py/monitor.py directement (`taskkill /PID ... /F`), le
garde-fou déjà en cours d'exécution les relance seul en ~10s avec le code à jour.

## 4. BlueBerry — connexion API (résolu le 07/08, pour référence)

Cause racine de plusieurs jours de blocage : faute de casse dans `.env`
(`BlueBerryMarketsSVG-Live` vs le vrai nom `BlueberryMarketsSVG-Live`, b minuscule à
"berry"). L'API Python résout le nom de serveur de façon sensible à la casse
(contrairement au login GUI), d'où des timeouts IPC systématiques malgré des
identifiants corrects. Aucune restriction broker (confirmé par leur support). Compte
maintenant pleinement opérationnel, cf. sections 2 et 6.

## 5. Config live actuelle (vérifiée en mémoire, cf. section 2.6)

- `MIN_RR` = 1.35 (`app.py`)
- `CORR_THRESHOLD` = 0.80 (`scaling_simulation.py`, source unique)
- `TRAILING_STOP_FACTOR` = 0.15 (`trade_logger.py`)
- `RISK_PCT_PER_TRADE` = 0.5% (`app_mt5.py`, global — compte_1) / **0.25%
  spécifique compte_blueberry**
- `MAX_POSITIONS_PER_ACCOUNT` = 3 (`account_router.py`, global — compte_1) / **50
  spécifique compte_blueberry**
- Rampe de risque 2.0%→2.5% : **toujours pas appliquée**, décision explicite
  (changement structurel à part, cf. sessions précédentes).

## 6. Performance live au 19/08 (analyse faite cette session, cf. conversation)

9 trades clôturés (7 compte_1, 2 compte_blueberry, même flux copytradé) : **-1.1R net,
-0.12R/trade en moyenne, winrate 33%**. Point notable : les 2 seuls gagnants sont le
**même signal GBP/JPY** (copytradé sur les deux comptes, TP2 plein, +1.94R chacun) —
tous les 6 autres trades clôturés (paires différentes) ont fini en stop loss. n=9 est
largement insuffisant pour confirmer ou infirmer l'edge (le backtest tourne sur des
centaines/milliers de trades) — à suivre, pas à interpréter comme un verdict. 5
positions encore ouvertes au 19/08 (détail dans l'historique de conversation si besoin
de le retrouver, sinon relire directement `trades_reels.csv` + positions MT5 live).

Le drawdown de 3.1% sur compte_1 au 19/08 (alerte précoce Telegram, PAS une pause) est
directement lié à cette séquence de 4 stops secs — comportement normal du système
d'alerte, rien à corriger.

## 7. Point important côté PC (à surveiller, pas encore un problème vécu)

Le dernier `NEXT_SESSION_PROMPT.md`/doc PC signale que la matrice de corrélation a été
étendue aux indices (19×19), et qu'un routage optimal indices→Stratégie B a été
identifié en simulation — MAIS que **l'exécution live des indices n'est PAS possible
en l'état** : 2 blocages précis dans `app.py` (whitelist des tickers suivis +
mapping symbole broker manquants pour les indices). Si jamais un signal indice
(CAC/DAX/etc.) est un jour validé côté live avant que ce travail soit fait côté code,
il sera très probablement ignoré silencieusement en `hors_perimetre` — pas une
urgence tant que personne n'a demandé l'activation des indices en live, mais à garder
en tête.

## 8. Prochaines étapes probables

- User : désactiver/supprimer `LutessiaBotApp`/`LutessiaBotWrapper` via le
  Planificateur de tâches (droits admin requis, section 3).
- Continuer à suivre la performance live (section 6) — pas assez de données pour agir,
  mais surveiller si la proportion de stops secs vs gagnants se stabilise vers ce que
  prédit le backtest.
- Si un signal indice apparaît un jour : vérifier qu'il est bien rejeté proprement
  (hors_perimetre) et pas silencieusement perdu, cf. section 7.
- Décider (séparément, côté PC) si/quand appliquer la rampe de risque 2.0%→2.5%.
