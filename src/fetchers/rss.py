from datetime import datetime, timezone
from typing import List

import feedparser
from dateutil import parser as dateutil_parser

from .base import BaseFetcher, RawItem
from src.utils.logger import get_logger

logger = get_logger(__name__)


class RSSFetcher(BaseFetcher):
    def fetch(self, window_start: datetime, window_end: datetime) -> List[RawItem]:
        feeds = self.config.get("feeds", [])
        items: List[RawItem] = []

        for feed in feeds:
            try:
                items.extend(self._fetch_feed(feed, window_start, window_end))
            except Exception as e:
                logger.warning("RSS fetch failed for %s: %s", feed.get("name"), e)

        logger.info("RSS: fetched %d items", len(items))
        return items

    def _fetch_feed(self, feed: dict, window_start: datetime, window_end: datetime) -> List[RawItem]:
        name = feed.get("name", "unknown")
        url = feed["url"]
        parsed = feedparser.parse(url)

        items = []
        for entry in parsed.entries:
            published = self._parse_date(entry)
            if published is None:
                continue
            if published < window_start or published >= window_end:
                continue

            link = entry.get("link", "")
            title = entry.get("title", "")
            summary = entry.get("summary", "") or entry.get("description", "") or ""
            external_id = entry.get("id") or link

            items.append(RawItem(
                source=f"rss:{name}",
                external_id=external_id,
                url=link,
                title=title,
                content=summary[:1000] if summary else None,
            ))

        return items

    def _parse_date(self, entry) -> datetime | None:
        for attr in ("published", "updated"):
            raw = getattr(entry, attr, None) or entry.get(attr)
            if raw:
                try:
                    dt = dateutil_parser.parse(raw)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
                except Exception:
                    continue
        return None
