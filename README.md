# Lutessia Trading Bot & Backtester

Ce dépôt contient l'architecture logicielle pour l'automatisation, l'analyse et le suivi des signaux de trading de l'outil Lutessia (CentralCharts).

## Structure du projet
- `app.py` : Cœur de l'application (alertes en direct et Forward Testing).
- `scraper.py` : Module d'extraction des données d'archives (respect du robots.txt).
- `backtest_analyzer.py` : Moteur statistique pour auditer les performances.
- `procfile` & `requirements.txt` : Configuration pour le déploiement cloud.

## Installation locale

```bash
git clone https://github.com/ton-repo/lutessia-bot.git
cd lutessia-bot
pip install -r requirements.txt
