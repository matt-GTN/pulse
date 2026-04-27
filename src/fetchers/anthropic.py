import re
from datetime import datetime, timezone
from typing import List

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser

from .base import BaseFetcher, RawItem
from src.utils.logger import get_logger

logger = get_logger(__name__)

_BASE_URL = "https://www.anthropic.com"
_NEWS_URL = f"{_BASE_URL}/news"
_DATE_RE = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}\b"
)


class AnthropicFetcher(BaseFetcher):
    def fetch(self, window_start: datetime, window_end: datetime) -> List[RawItem]:
        try:
            resp = requests.get(
                _NEWS_URL,
                timeout=30,
                headers={"User-Agent": "Mozilla/5.0 (compatible; PulseBot/1.0)"},
            )
            resp.raise_for_status()
        except Exception as e:
            logger.warning("Anthropic fetch failed: %s", e)
            return []

        items = self._parse(resp.text, window_start, window_end)
        logger.info("Anthropic: fetched %d items", len(items))
        return items

    def _parse(self, html: str, window_start: datetime, window_end: datetime) -> List[RawItem]:
        soup = BeautifulSoup(html, "html.parser")
        seen_ids: set = set()
        items: List[RawItem] = []

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not (href.startswith("/news/") and len(href) > len("/news/")):
                continue

            title = a.get_text(strip=True)
            if not title or len(title) < 5:
                continue

            external_id = href.lstrip("/")  # e.g. "news/claude-opus-4-7"
            if external_id in seen_ids:
                continue

            pub_date = self._find_date(a)
            if pub_date is None:
                continue
            if pub_date < window_start or pub_date >= window_end:
                continue

            seen_ids.add(external_id)
            items.append(RawItem(
                source="anthropic",
                external_id=external_id,
                url=_BASE_URL + href,
                title=title,
            ))

        return items

    def _find_date(self, a_tag) -> datetime | None:
        """Walk up parent elements looking for a date string near this link."""
        node = a_tag.parent
        for _ in range(5):
            if node is None:
                break
            text = node.get_text(" ", strip=True)
            match = _DATE_RE.search(text)
            if match:
                try:
                    dt = dateutil_parser.parse(match.group(0))
                    return dt.replace(tzinfo=timezone.utc)
                except Exception:
                    pass
            node = node.parent
        return None
