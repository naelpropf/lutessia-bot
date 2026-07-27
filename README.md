# Lutessia Trading Bot & Backtester

Ce dépôt contient l'architecture logicielle pour l'automatisation, l'analyse et le suivi des signaux de trading de l'outil Lutessia (CentralCharts).

## Structure du projet

- **`app.py`** : Cœur de l'application gérant les alertes en direct et le Forward Testing.
- **`scraper.py`** : Module d'extraction des données d'archives en respectant le `robots.txt`.
- **`backtest_analyzer.py`** : Moteur statistique pour auditer les performances, calculer le winrate global et segmenter par classe d'actif / R:R.
- **`procfile` & `requirements.txt`** : Configuration pour le déploiement sur le cloud.

## Installation locale

1. Cloner le dépôt :
   ```bash
   git clone [https://github.com/ton-repo/lutessia-bot.git](https://github.com/ton-repo/lutessia-bot.git)
   cd lutessia-bot
pip install -r requirements.txt
