from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class RawItem:
    source: str
    external_id: str
    url: str
    title: str
    content: Optional[str] = None
    source_score: Optional[float] = None


class BaseFetcher(ABC):
    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def fetch(self, window_start: datetime, window_end: datetime) -> List[RawItem]:
        """Fetch items published within [window_start, window_end]."""
        ...
