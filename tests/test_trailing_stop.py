"""Tests mock (aucune connexion MT5 réelle) pour trade_logger.manage_trailing_stops().

Simule une suite de "ticks" prix en patchant app_mt5.get_open_position_raw /
modify_position_sltp / connect / disconnect / load_accounts, et un
trades_reels.csv temporaire avec une seule position ouverte. Chaque tick
appelle manage_trailing_stops() une fois (comme le ferait un cycle de polling
réel), et l'objet position retourné par get_open_position_raw reflète le SL
tel qu'il aurait été laissé par le tick précédent -- pour vérifier que le
trailing ne se resserre jamais que dans le sens favorable et jamais en
arrière sur un retracement.

Lancer avec : python -m unittest tests.test_trailing_stop -v
"""
import csv
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import app_mt5
import trade_logger


def _assert_call_almost_equal(testcase, call, expected_args):
    """Compare un appel mocké (ticket, symbol, sl, tp) en tolérant l'imprécision
    flottante normale sur sl (cf. TRAILING_EPSILON dans trade_logger.py)."""
    ticket, symbol, sl, tp = call.args
    exp_ticket, exp_symbol, exp_sl, exp_tp = expected_args
    testcase.assertEqual(ticket, exp_ticket)
    testcase.assertEqual(symbol, exp_symbol)
    testcase.assertAlmostEqual(sl, exp_sl, places=6)
    testcase.assertEqual(tp, exp_tp)


def _position(ticket, price_current, sl, symbol="EURUSD", direction_type=None):
    return types.SimpleNamespace(
        ticket=ticket, price_current=price_current, sl=sl, tp=0.0,
        symbol=symbol, type=direction_type,
    )


class TrailingStopTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.trades_path = os.path.join(self.tmpdir.name, "trades_reels.csv")
        self.state_path = os.path.join(self.tmpdir.name, "trailing_stop_state.json")
        self.log_path = os.path.join(self.tmpdir.name, "trailing_stop.log")

        self._patches = [
            patch.object(trade_logger, "TRADES_REELS_PATH", self.trades_path),
            patch.object(trade_logger, "TRAILING_STATE_PATH", self.state_path),
            patch.object(trade_logger, "TRAILING_LOG_PATH", self.log_path),
            patch.object(app_mt5, "connect", return_value=True),
            patch.object(app_mt5, "disconnect"),
            patch.object(app_mt5, "load_accounts",
                         return_value=[app_mt5.MT5Account("compte_1", 1, "x", "y")]),
        ]
        for p in self._patches:
            p.start()
            self.addCleanup(p.stop)

    def _write_open_trade(self, ticket, prix_entree, stop_loss_init, tp2_init):
        with open(self.trades_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(trade_logger.CSV_COLUMNS)
            w.writerow([
                "2026-07-31 00:00:00", "EUR/USD", "Forex", "H1",
                prix_entree, stop_loss_init, tp2_init - 0.002, tp2_init,
                2.0, 4.0, "", "compte_1", "2026-07-31 00:00:00", ticket, "",
            ])

    # --- Achat -----------------------------------------------------------

    def test_buy_arms_tightens_and_never_loosens_on_retrace(self):
        self._write_open_trade(ticket=111, prix_entree=1.2500, stop_loss_init=1.2450, tp2_init=1.2600)

        ticks = [
            _position(111, price_current=1.2590, sl=1.2450, direction_type=app_mt5.POSITION_TYPE_BUY),  # pas encore tp2
            _position(111, price_current=1.2600, sl=1.2450, direction_type=app_mt5.POSITION_TYPE_BUY),  # armement
            _position(111, price_current=1.2620, sl=1.2590, direction_type=app_mt5.POSITION_TYPE_BUY),  # nouveau plus haut
            _position(111, price_current=1.2615, sl=1.2610, direction_type=app_mt5.POSITION_TYPE_BUY),  # retracement
            _position(111, price_current=1.2650, sl=1.2610, direction_type=app_mt5.POSITION_TYPE_BUY),  # nouveau plus haut
        ]

        with patch.object(app_mt5, "get_open_position_raw", side_effect=ticks) as mock_get, \
             patch.object(app_mt5, "modify_position_sltp", return_value=True) as mock_modify:
            for _ in ticks:
                trade_logger.manage_trailing_stops()

        self.assertEqual(mock_get.call_count, 5)
        # Seuls les ticks 2 (armement), 3 (nouveau plus haut) et 5 (nouveau plus
        # haut) doivent déclencher un ajustement réel -- pas le 1er (avant tp2) ni
        # le 4e (retracement, ne doit jamais desserrer/reculer le stop).
        self.assertEqual(mock_modify.call_count, 3)

        calls = mock_modify.call_args_list
        _assert_call_almost_equal(self, calls[0], (111, "EURUSD", 1.2590, 0.0))  # armement
        _assert_call_almost_equal(self, calls[1], (111, "EURUSD", 1.2610, 0.0))  # tick 3
        _assert_call_almost_equal(self, calls[2], (111, "EURUSD", 1.2640, 0.0))  # tick 5

        with open(self.state_path, encoding="utf-8") as f:
            import json
            state = json.load(f)
        self.assertAlmostEqual(state["111"]["extremum"], 1.2650)
        self.assertAlmostEqual(state["111"]["last_sl"], 1.2640)

        # Le SL final (1.2640) est au-dessus du prix de retracement simulé
        # (1.2635) : une position achat se ferme si le prix retombe à/sous le SL.
        final_sl = state["111"]["last_sl"]
        simulated_retrace_price = 1.2635
        self.assertTrue(simulated_retrace_price <= final_sl, "la position se fermerait bien à ce niveau")

    # --- Vente (miroir) ----------------------------------------------------

    def test_sell_arms_tightens_and_never_loosens_on_retrace(self):
        self._write_open_trade(ticket=222, prix_entree=1.2500, stop_loss_init=1.2550, tp2_init=1.2400)

        ticks = [
            _position(222, price_current=1.2410, sl=1.2550, direction_type=app_mt5.POSITION_TYPE_SELL),  # pas encore tp2
            _position(222, price_current=1.2400, sl=1.2550, direction_type=app_mt5.POSITION_TYPE_SELL),  # armement
            _position(222, price_current=1.2380, sl=1.2410, direction_type=app_mt5.POSITION_TYPE_SELL),  # nouveau plus bas
            _position(222, price_current=1.2385, sl=1.2390, direction_type=app_mt5.POSITION_TYPE_SELL),  # retracement
            _position(222, price_current=1.2350, sl=1.2390, direction_type=app_mt5.POSITION_TYPE_SELL),  # nouveau plus bas
        ]

        with patch.object(app_mt5, "get_open_position_raw", side_effect=ticks) as mock_get, \
             patch.object(app_mt5, "modify_position_sltp", return_value=True) as mock_modify:
            for _ in ticks:
                trade_logger.manage_trailing_stops()

        self.assertEqual(mock_get.call_count, 5)
        self.assertEqual(mock_modify.call_count, 3)

        calls = mock_modify.call_args_list
        _assert_call_almost_equal(self, calls[0], (222, "EURUSD", 1.2410, 0.0))
        _assert_call_almost_equal(self, calls[1], (222, "EURUSD", 1.2390, 0.0))
        _assert_call_almost_equal(self, calls[2], (222, "EURUSD", 1.2360, 0.0))

    # --- Position déjà fermée entre deux cycles ----------------------------

    def test_closed_position_clears_orphan_state(self):
        self._write_open_trade(ticket=333, prix_entree=1.2500, stop_loss_init=1.2450, tp2_init=1.2600)

        # Simule un état de trailing déjà armé lors d'un run précédent.
        import json
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump({"333": {"extremum": 1.2650, "last_sl": 1.2640, "activated_at": "x"}}, f)

        with patch.object(app_mt5, "get_open_position_raw", return_value=None), \
             patch.object(app_mt5, "modify_position_sltp") as mock_modify:
            trade_logger.manage_trailing_stops()

        mock_modify.assert_not_called()
        with open(self.state_path, encoding="utf-8") as f:
            state = json.load(f)
        self.assertNotIn("333", state)

    # --- Pas encore armé : aucun appel MT5 de modification -----------------

    def test_not_yet_reaching_tp2_makes_no_calls(self):
        self._write_open_trade(ticket=444, prix_entree=1.2500, stop_loss_init=1.2450, tp2_init=1.2600)

        with patch.object(app_mt5, "get_open_position_raw",
                           return_value=_position(444, price_current=1.2550, sl=1.2450,
                                                   direction_type=app_mt5.POSITION_TYPE_BUY)), \
             patch.object(app_mt5, "modify_position_sltp") as mock_modify:
            trade_logger.manage_trailing_stops()

        mock_modify.assert_not_called()
        if os.path.exists(self.state_path):
            with open(self.state_path, encoding="utf-8") as f:
                content = f.read().strip()
            self.assertIn(content, ("", "{}"))


class AdaptivePollingTestCase(unittest.TestCase):
    """Tests mock pour trade_logger.get_next_poll_delay_seconds() : bascule
    provisoire polling normal / rapide selon la proximité de tp2_init."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.trades_path = os.path.join(self.tmpdir.name, "trades_reels.csv")

        self._patches = [
            patch.object(trade_logger, "TRADES_REELS_PATH", self.trades_path),
            patch.object(app_mt5, "connect", return_value=True),
            patch.object(app_mt5, "disconnect"),
            patch.object(app_mt5, "load_accounts",
                         return_value=[app_mt5.MT5Account("compte_1", 1, "x", "y")]),
        ]
        for p in self._patches:
            p.start()
            self.addCleanup(p.stop)

    def _write_open_trades(self, rows):
        """rows : liste de dicts avec ticket/prix_entree/stop_loss_init/tp2_init."""
        with open(self.trades_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(trade_logger.CSV_COLUMNS)
            for r in rows:
                w.writerow([
                    "2026-07-31 00:00:00", "EUR/USD", "Forex", "H1",
                    r["prix_entree"], r["stop_loss_init"], r["tp2_init"] - 0.002, r["tp2_init"],
                    2.0, 4.0, "", "compte_1", "2026-07-31 00:00:00", r["ticket"], "",
                ])

    def test_no_open_trades_is_normal(self):
        self._write_open_trades([])
        self.assertEqual(trade_logger.get_next_poll_delay_seconds(), trade_logger.NORMAL_POLL_INTERVAL_SECONDS)

    def test_far_from_tp2_is_normal(self):
        # entree=1.2500, tp2=1.2600 (distance 0.0100), prix a 1.2550 -> reste 50% du chemin.
        self._write_open_trades([
            {"ticket": 501, "prix_entree": 1.2500, "stop_loss_init": 1.2450, "tp2_init": 1.2600},
        ])
        with patch.object(app_mt5, "get_open_position_raw",
                           return_value=_position(501, price_current=1.2550, sl=1.2450,
                                                   direction_type=app_mt5.POSITION_TYPE_BUY)):
            delay = trade_logger.get_next_poll_delay_seconds()
        self.assertEqual(delay, trade_logger.NORMAL_POLL_INTERVAL_SECONDS)

    def test_within_last_20_percent_is_fast_buy(self):
        # distance totale 0.0100, derniers 20% = reste <= 0.0020 -> prix >= 1.2580.
        self._write_open_trades([
            {"ticket": 502, "prix_entree": 1.2500, "stop_loss_init": 1.2450, "tp2_init": 1.2600},
        ])
        with patch.object(app_mt5, "get_open_position_raw",
                           return_value=_position(502, price_current=1.2585, sl=1.2450,
                                                   direction_type=app_mt5.POSITION_TYPE_BUY)):
            delay = trade_logger.get_next_poll_delay_seconds()
        self.assertEqual(delay, trade_logger.FAST_POLL_INTERVAL_SECONDS)

    def test_within_last_20_percent_is_fast_sell(self):
        # vente : entree=1.2500, tp2=1.2400 (distance 0.0100), prix a 1.2415 -> reste 15%.
        self._write_open_trades([
            {"ticket": 503, "prix_entree": 1.2500, "stop_loss_init": 1.2550, "tp2_init": 1.2400},
        ])
        with patch.object(app_mt5, "get_open_position_raw",
                           return_value=_position(503, price_current=1.2415, sl=1.2550,
                                                   direction_type=app_mt5.POSITION_TYPE_SELL)):
            delay = trade_logger.get_next_poll_delay_seconds()
        self.assertEqual(delay, trade_logger.FAST_POLL_INTERVAL_SECONDS)

    def test_already_past_tp2_is_fast(self):
        self._write_open_trades([
            {"ticket": 504, "prix_entree": 1.2500, "stop_loss_init": 1.2450, "tp2_init": 1.2600},
        ])
        with patch.object(app_mt5, "get_open_position_raw",
                           return_value=_position(504, price_current=1.2650, sl=1.2590,
                                                   direction_type=app_mt5.POSITION_TYPE_BUY)):
            delay = trade_logger.get_next_poll_delay_seconds()
        self.assertEqual(delay, trade_logger.FAST_POLL_INTERVAL_SECONDS)

    def test_one_far_one_near_is_fast(self):
        """Un seul trade proche de tp2_init parmi plusieurs suffit à accélérer le
        polling global -- pas de moyenne, le cas le plus urgent gagne."""
        self._write_open_trades([
            {"ticket": 505, "prix_entree": 1.2500, "stop_loss_init": 1.2450, "tp2_init": 1.2600},
            {"ticket": 506, "prix_entree": 1.1000, "stop_loss_init": 1.0950, "tp2_init": 1.1100},
        ])
        positions = {
            505: _position(505, price_current=1.2520, sl=1.2450, direction_type=app_mt5.POSITION_TYPE_BUY),  # loin
            506: _position(506, price_current=1.1095, sl=1.0950, direction_type=app_mt5.POSITION_TYPE_BUY),  # proche
        }
        with patch.object(app_mt5, "get_open_position_raw", side_effect=lambda t: positions[t]):
            delay = trade_logger.get_next_poll_delay_seconds()
        self.assertEqual(delay, trade_logger.FAST_POLL_INTERVAL_SECONDS)

    def test_closed_position_does_not_force_fast(self):
        self._write_open_trades([
            {"ticket": 507, "prix_entree": 1.2500, "stop_loss_init": 1.2450, "tp2_init": 1.2600},
        ])
        with patch.object(app_mt5, "get_open_position_raw", return_value=None):
            delay = trade_logger.get_next_poll_delay_seconds()
        self.assertEqual(delay, trade_logger.NORMAL_POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    unittest.main()
