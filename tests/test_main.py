"""CLI exit status for delivery failures."""
import io
import unittest
from unittest.mock import patch

import main


class TestMain(unittest.TestCase):
    def test_delivery_error_exits_nonzero(self):
        result = {
            "collected_raw": 1,
            "filtered_valid": 1,
            "gemini_excluded": 0,
            "new_contests": 1,
            "updated_contests": 0,
            "deadline_alerts": 0,
            "total_stored": 1,
            "errors": ["Discord digest delivery failed: HTTP 404"],
        }
        with patch("sys.argv", ["main.py"]), patch("main.ContestBot") as bot:
            bot.return_value.run.return_value = result
            with patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(main.main(), 1)


if __name__ == "__main__":
    unittest.main()
