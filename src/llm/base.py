from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ScoredResult:
    one_liner: str
    full_summary: str
    importance: int


class BaseLLMProvider(ABC):
    @abstractmethod
    def summarize(self, source: str, title: str, content: str, url: str) -> ScoredResult:
        """Summarize and score a single item."""
        ...
