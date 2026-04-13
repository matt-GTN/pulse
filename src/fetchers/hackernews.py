from datetime import datetime, timezone
from typing import List

import requests

from .base import BaseFetcher, RawItem
from src.utils.logger import get_logger

logger = get_logger(__name__)

_API = "https://hn.algolia.com/api/v1/search_by_date"


class HackerNewsFetcher(BaseFetcher):
    def fetch(self, window_start: datetime, window_end: datetime) -> List[RawItem]:
        query = self.config.get("query", "AI OR LLM")
        min_points = self.config.get("min_points", 20)
        limit = self.config.get("limit", 30)
        items: List[RawItem] = []

        try:
            items = self._fetch(query, min_points, limit, window_start, window_end)
        except Exception as e:
            logger.warning("HackerNews fetch failed: %s", e)

        logger.info("HackerNews: fetched %d items", len(items))
        return items

    def _fetch(self, query: str, min_points: int, limit: int, window_start: datetime, window_end: datetime) -> List[RawItem]:
        # Algolia ANDs multi-word queries — split on OR and merge results
        terms = [t.strip() for t in query.split(" OR ") if t.strip()]
        numeric_filters = f"points>={min_points},created_at_i>={int(window_start.timestamp())},created_at_i<{int(window_end.timestamp())}"

        seen_ids: set = set()
        all_hits = []
        for term in terms:
            params = {
                "query": term,
                "tags": "story",
                "numericFilters": numeric_filters,
                "hitsPerPage": limit,
            }
            resp = requests.get(_API, params=params, timeout=30)
            resp.raise_for_status()
            for hit in resp.json().get("hits", []):
                oid = hit.get("objectID")
                if oid not in seen_ids:
                    seen_ids.add(oid)
                    all_hits.append(hit)

        hits = all_hits
        items = []
        for hit in hits:
            object_id = hit.get("objectID", "")
            title = hit.get("title", "")
            url = hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}"
            points = hit.get("points")
            num_comments = hit.get("num_comments")

            content_parts = []
            if points is not None:
                content_parts.append(f"{points} points")
            if num_comments is not None:
                content_parts.append(f"{num_comments} comments")

            items.append(RawItem(
                source="hn",
                external_id=object_id,
                url=url,
                title=title,
                content=", ".join(content_parts) or None,
                source_score=float(points) if points is not None else None,
            ))

        return items
