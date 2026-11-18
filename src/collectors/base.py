"""Abstract base class for contest collectors."""
from abc import ABC, abstractmethod
from typing import List

from src.models import Contest


class BaseCollector(ABC):
    """Abstract interface for collecting contest announcements."""

    @abstractmethod
    def collect(self) -> List[Contest]:
        """Collect contest announcements and return a list of Contest models."""
        pass
