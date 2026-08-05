"""Test mock de slippage_logger.log_slippage() : pas de connexion MT5, juste des
valeurs simulées, dans un répertoire temporaire (aucun fichier réel touché).

Lancer avec : python -m unittest tests.test_slippage_logger -v
"""
import csv
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import slippage_logger


class SlippageLoggerTestCase(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._patcher = patch.object(
            slippage_logger, "SLIPPAGE_LOG_PATH",
            os.path.join(self._tmpdir.name, "slippage_log.csv"),
        )
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        self._tmpdir.cleanup()

    def _read_rows(self):
        with open(slippage_logger.SLIPPAGE_LOG_PATH, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def test_buy_positive_slippage_worse_fill(self):
        # Achat : fill plus haut que le signal = slippage défavorable (positif en pips).
        sent = datetime(2026, 8, 1, 9, 0, 0, tzinfo=timezone.utc)
        executed = sent + timedelta(seconds=45)
        row = slippage_logger.log_slippage(
            "EUR/USD", "buy", "compte_test", 12345,
            signal_price=1.10000, fill_price=1.10015,
            email_sent_at=sent, date_execution=executed,
        )
        self.assertAlmostEqual(row["slippage_pips"], 1.5, places=5)
        self.assertEqual(row["latency_seconds"], 45.0)
        self.assertEqual(row["session"], "londres")

    def test_sell_positive_slippage_worse_fill(self):
        # Vente : fill plus BAS que le signal = défavorable -> doit rester positif.
        row = slippage_logger.log_slippage(
            "GBP/USD", "sell", "compte_test", 999,
            signal_price=1.30000, fill_price=1.29985,
        )
        self.assertAlmostEqual(row["slippage_pips"], 1.5, places=5)

    def test_jpy_pip_size(self):
        row = slippage_logger.log_slippage(
            "USD/JPY", "buy", "compte_test", 1,
            signal_price=150.000, fill_price=150.030,
        )
        self.assertAlmostEqual(row["slippage_pips"], 3.0, places=5)

    def test_no_email_sent_at_omits_latency_but_still_logs(self):
        row = slippage_logger.log_slippage(
            "EUR/USD", "buy", "compte_test", 2,
            signal_price=1.10000, fill_price=1.10000,
        )
        self.assertIsNone(row["latency_seconds"])
        self.assertIsNone(row["email_sent_at"])

    def test_appends_multiple_rows_with_single_header(self):
        for i in range(3):
            slippage_logger.log_slippage(
                "EUR/USD", "buy", "compte_test", i,
                signal_price=1.1, fill_price=1.1001,
            )
        rows = self._read_rows()
        self.assertEqual(len(rows), 3)

    def test_session_labels(self):
        cases = [(3, "asie"), (10, "londres"), (14, "londres_ny"), (18, "new_york"), (22, "creux")]
        for hour, expected in cases:
            dt = datetime(2026, 8, 1, hour, 0, 0, tzinfo=timezone.utc)
            self.assertEqual(slippage_logger._session_horaire(dt), expected)


if __name__ == "__main__":
    unittest.main()
