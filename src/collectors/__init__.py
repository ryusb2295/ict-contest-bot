"""Contest collectors package."""
from src.collectors.base import BaseCollector
from src.collectors.daker_collector import DakerCollector
from src.collectors.fallback import FallbackCollectorManager
from src.collectors.gemini_search import GeminiSearchCollector
from src.collectors.wevity_collector import WevityCollector

__all__ = [
    "BaseCollector",
    "GeminiSearchCollector",
    "WevityCollector",
    "DakerCollector",
    "FallbackCollectorManager",
]
