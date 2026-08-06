"""Test mock : quand aucun compte n'est éligible pour un signal (ex: actif corrélé à
une position déjà ouverte), app.executer_signal_reel() doit désormais notifier Telegram
avec la raison, au lieu de rester silencieux -- bug confirmé le 06/08 (signal AUD/USD
ignoré sans aucune trace, corrélé 0.85 à une position NZD/USD déjà ouverte). Aucune
connexion MT5/Telegram réelle, tout est mocké.

Lancer avec : python -m unittest tests.test_no_eligible_account_notifies -v
"""
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import app
import app_mt5
import account_router
import news_filter


class NoEligibleAccountNotifiesTestCase(unittest.TestCase):
    def test_no_eligible_account_sends_telegram_notification(self):
        fake_account = SimpleNamespace(account_id="compte_1")
        with patch.object(news_filter, "apply_news_delay"), \
             patch.object(app_mt5, "load_accounts", return_value=[fake_account]), \
             patch.object(account_router, "eligible_accounts", return_value=[]), \
             patch.object(app, "notifier_telegram_async") as mock_notify:
            app.executer_signal_reel(
                ticker="AUD/USD", direction="buy", stop_loss_init=0.7033,
                tp1_init=0.7118, tp2_init=0.7147, asset_class="FX/Indices",
                timeframe="1H", date_creation="2026-08-05 17:21:34",
                signal_price=0.7055,
            )

        mock_notify.assert_called_once()
        message = mock_notify.call_args[0][0]
        self.assertIn("AUD/USD", message)
        self.assertIn("Trade non pris", message)

    def test_eligible_account_present_does_not_trigger_no_eligible_message(self):
        """Contre-exemple : si un compte est éligible, cette notification spécifique ne
        doit pas partir (le chemin normal d'exécution prend le relais)."""
        fake_account = SimpleNamespace(account_id="compte_1")
        with patch.object(news_filter, "apply_news_delay"), \
             patch.object(app_mt5, "load_accounts", return_value=[fake_account]), \
             patch.object(account_router, "eligible_accounts", return_value=[fake_account]), \
             patch.object(app_mt5, "connect", return_value=False), \
             patch.object(app, "notifier_telegram_async") as mock_notify:
            app.executer_signal_reel(
                ticker="EUR/USD", direction="buy", stop_loss_init=1.1,
                tp1_init=1.11, tp2_init=1.12, asset_class="FX/Indices",
                timeframe="1H", date_creation="2026-08-06 00:00:00",
                signal_price=1.105,
            )

        for call in mock_notify.call_args_list:
            self.assertNotIn("aucun compte éligible", call[0][0])


if __name__ == "__main__":
    unittest.main()
