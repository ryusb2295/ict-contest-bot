"""Configuration gates for optional external services."""
import unittest

from src.config import Config


class TestConfig(unittest.TestCase):
    def test_gemini_search_requires_explicit_enablement_and_real_key(self):
        self.assertFalse(Config(gemini_api_key="key", gemini_search_enabled=False).has_gemini)
        self.assertFalse(Config(gemini_api_key="your_gemini_api_key_here", gemini_search_enabled=True).has_gemini)
        self.assertTrue(Config(gemini_api_key="key", gemini_search_enabled=True).has_gemini)
        self.assertFalse(Config(gemini_api_key="key", gemini_refine_enabled=False).has_gemini_refiner)
        self.assertTrue(Config(gemini_api_key="key", gemini_refine_enabled=True).has_gemini_refiner)
