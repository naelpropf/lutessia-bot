"""Test mock du câblage réel de app._run_trailing_check_if_due() : simule le
déroulement de la boucle principale (avance manuelle de `now`, sans vraie
connexion MT5) et vérifie que manage_trailing_stops() se déclenche exactement
quand prévu, en alternant polling normal (1h) et rapide (2 min) selon ce que
trade_logger.get_next_poll_delay_seconds() retourne à chaque passage.

Lancer avec : python -m unittest tests.test_adaptive_wiring -v
"""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import app
import trade_logger


class AdaptiveWiringTestCase(unittest.TestCase):
    def test_first_call_always_runs_immediately(self):
        """last_trailing_check=0, next_trailing_delay=0 (état initial de app.py) :
        le tout premier passage doit s'exécuter sans attendre."""
        with patch.object(trade_logger, "manage_trailing_stops") as mock_manage, \
             patch.object(trade_logger, "get_next_poll_delay_seconds",
                           return_value=trade_logger.NORMAL_POLL_INTERVAL_SECONDS):
            last, delay = app._run_trailing_check_if_due(now=1000.0, last_trailing_check=0.0, next_trailing_delay=0.0)

        mock_manage.assert_called_once()
        self.assertEqual(last, 1000.0)
        self.assertEqual(delay, trade_logger.NORMAL_POLL_INTERVAL_SECONDS)

    def test_normal_then_switches_to_fast_once_near_tp2(self):
        """Simule : check à t=0 (normal, rien de proche) -> pas de nouveau check
        avant 3600s -> à t=3600 un trade est maintenant proche de tp2_init,
        get_next_poll_delay_seconds bascule en FAST -> le prochain check doit
        arriver 120s plus tard (pas 3600s), pas avant."""
        delays = [trade_logger.NORMAL_POLL_INTERVAL_SECONDS, trade_logger.FAST_POLL_INTERVAL_SECONDS]
        with patch.object(trade_logger, "manage_trailing_stops") as mock_manage, \
             patch.object(trade_logger, "get_next_poll_delay_seconds", side_effect=delays):
            last, delay = app._run_trailing_check_if_due(now=0.0, last_trailing_check=0.0, next_trailing_delay=0.0)
            self.assertEqual(mock_manage.call_count, 1)
            self.assertEqual(delay, trade_logger.NORMAL_POLL_INTERVAL_SECONDS)

            # Avant l'échéance (1h) : ne doit RIEN faire.
            last, delay = app._run_trailing_check_if_due(now=1800.0, last_trailing_check=last, next_trailing_delay=delay)
            self.assertEqual(mock_manage.call_count, 1)

            # A l'échéance (3600s) : se déclenche, et bascule en FAST pour la suite.
            last, delay = app._run_trailing_check_if_due(now=3600.0, last_trailing_check=last, next_trailing_delay=delay)
            self.assertEqual(mock_manage.call_count, 2)
            self.assertEqual(delay, trade_logger.FAST_POLL_INTERVAL_SECONDS)

            # Avec le nouveau délai rapide (120s) : pas encore dû à +90s...
            last, delay = app._run_trailing_check_if_due(now=3690.0, last_trailing_check=last, next_trailing_delay=delay)
            self.assertEqual(mock_manage.call_count, 2)

            # ...mais dû à +120s.
            with patch.object(trade_logger, "get_next_poll_delay_seconds",
                               return_value=trade_logger.FAST_POLL_INTERVAL_SECONDS):
                last, delay = app._run_trailing_check_if_due(now=3720.0, last_trailing_check=last, next_trailing_delay=delay)
            self.assertEqual(mock_manage.call_count, 3)

    def test_exception_in_manage_trailing_stops_does_not_crash_and_still_reschedules(self):
        """Une exception dans manage_trailing_stops() ne doit jamais arrêter le bot
        (cohérent avec le reste de la boucle principale, cf. verifier_drawdown_comptes) ;
        le prochain délai doit quand même être recalculé."""
        with patch.object(trade_logger, "manage_trailing_stops", side_effect=RuntimeError("boom")), \
             patch.object(trade_logger, "get_next_poll_delay_seconds",
                           return_value=trade_logger.NORMAL_POLL_INTERVAL_SECONDS):
            last, delay = app._run_trailing_check_if_due(now=42.0, last_trailing_check=0.0, next_trailing_delay=0.0)

        self.assertEqual(last, 42.0)
        self.assertEqual(delay, trade_logger.NORMAL_POLL_INTERVAL_SECONDS)

    def test_exception_in_get_next_poll_delay_falls_back_to_normal(self):
        """Si le calcul du délai adaptatif échoue (ex: MT5 indisponible), retombe
        sur le polling normal plutôt que de planter ou de rester bloqué en rapide."""
        with patch.object(trade_logger, "manage_trailing_stops"), \
             patch.object(trade_logger, "get_next_poll_delay_seconds", side_effect=RuntimeError("mt5 down")):
            last, delay = app._run_trailing_check_if_due(now=42.0, last_trailing_check=0.0, next_trailing_delay=0.0)

        self.assertEqual(delay, trade_logger.NORMAL_POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    unittest.main()
