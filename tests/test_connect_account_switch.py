"""Test mock de app_mt5.connect() : vérifie qu'on ne fait jamais confiance au simple
True de mt5.initialize() -- constaté le 2026-08-06 sur le compte BlueBerry (terminal
resté silencieusement connecté au compte précédent malgré un retour succès). Aucune
connexion MT5 réelle, tout est mocké.

Lancer avec : python -m unittest tests.test_connect_account_switch -v
"""
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import app_mt5


def _account(login=5104059):
    return SimpleNamespace(account_id="compte_test_blueberry", login=login,
                            password="x", server="BlueBerryMarketsSVG-Live")


class ConnectAccountSwitchTestCase(unittest.TestCase):
    def test_initialize_fails_returns_false_immediately(self):
        with patch.object(app_mt5.mt5, "initialize", return_value=False), \
             patch.object(app_mt5.mt5, "last_error", return_value=(-10005, "IPC timeout")):
            self.assertFalse(app_mt5.connect(_account()))

    def test_initialize_true_and_already_correct_account_no_extra_login_call(self):
        with patch.object(app_mt5.mt5, "initialize", return_value=True), \
             patch.object(app_mt5.mt5, "account_info", return_value=SimpleNamespace(login=5104059)), \
             patch.object(app_mt5.mt5, "login") as mock_login:
            self.assertTrue(app_mt5.connect(_account(login=5104059)))
        mock_login.assert_not_called()

    def test_initialize_true_but_wrong_account_still_active_forces_login_and_succeeds(self):
        """Le bug reproduit le 06/08 : initialize() dit True mais account_info() montre
        encore l'ancien compte -- doit forcer mt5.login() et réussir si celui-ci bascule
        effectivement vers le bon compte."""
        infos = iter([SimpleNamespace(login=62134005), SimpleNamespace(login=5104059)])
        with patch.object(app_mt5.mt5, "initialize", return_value=True), \
             patch.object(app_mt5.mt5, "account_info", side_effect=lambda: next(infos)), \
             patch.object(app_mt5.mt5, "login", return_value=True) as mock_login:
            self.assertTrue(app_mt5.connect(_account(login=5104059)))
        mock_login.assert_called_once()

    def test_wrong_account_persists_even_after_forced_login_returns_false(self):
        """Si même après mt5.login() le compte actif ne correspond toujours pas
        (cas BlueBerry observé), connect() doit retourner False, jamais True sur le
        mauvais compte."""
        infos = iter([SimpleNamespace(login=62134005), SimpleNamespace(login=62134005)])
        with patch.object(app_mt5.mt5, "initialize", return_value=True), \
             patch.object(app_mt5.mt5, "account_info", side_effect=lambda: next(infos)), \
             patch.object(app_mt5.mt5, "login", return_value=True):
            self.assertFalse(app_mt5.connect(_account(login=5104059)))

    def test_login_call_itself_fails(self):
        infos = iter([SimpleNamespace(login=62134005)])
        with patch.object(app_mt5.mt5, "initialize", return_value=True), \
             patch.object(app_mt5.mt5, "account_info", side_effect=lambda: next(infos)), \
             patch.object(app_mt5.mt5, "login", return_value=False), \
             patch.object(app_mt5.mt5, "last_error", return_value=(-10004, "No IPC connection")):
            self.assertFalse(app_mt5.connect(_account(login=5104059)))

    def test_account_info_none_after_initialize_forces_login(self):
        infos = iter([None, SimpleNamespace(login=5104059)])
        with patch.object(app_mt5.mt5, "initialize", return_value=True), \
             patch.object(app_mt5.mt5, "account_info", side_effect=lambda: next(infos)), \
             patch.object(app_mt5.mt5, "login", return_value=True) as mock_login:
            self.assertTrue(app_mt5.connect(_account(login=5104059)))
        mock_login.assert_called_once()


if __name__ == "__main__":
    unittest.main()
