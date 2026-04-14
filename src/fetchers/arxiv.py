import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List

import requests

from .base import BaseFetcher, RawItem
from src.utils.logger import get_logger

logger = get_logger(__name__)

_API = "https://export.arxiv.org/api/query"
_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


class ArxivFetcher(BaseFetcher):
    def fetch(self, window_start: datetime, window_end: datetime) -> List[RawItem]:
        categories = self.config.get("categories", [])
        max_results = self.config.get("max_results", 50)
        items: List[RawItem] = []

        for category in categories:
            try:
                items.extend(self._fetch_category(category, max_results, window_start, window_end))
            except Exception as e:
                logger.warning("arXiv fetch failed for %s: %s", category, e)
            time.sleep(3)  # be polite

        logger.info("arXiv: fetched %d items", len(items))
        return items

    def _fetch_category(self, category: str, max_results: int, window_start: datetime, window_end: datetime) -> List[RawItem]:
        # arXiv published date = submission date, not announcement date.
        # Papers take 1-3 days to appear after submission (longer after weekends).
        # We use a 4-day lookback instead of the strict digest window — DB dedup
        # (UNIQUE on source+external_id) handles papers already seen.
        from datetime import timedelta
        lookback_start = datetime.now(tz=timezone.utc) - timedelta(days=4)

        params = {
            "search_query": f"cat:{category}",
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "max_results": max_results,
        }
        resp = requests.get(_API, params=params, timeout=30)
        resp.raise_for_status()

        root = ET.fromstring(resp.text)
        items = []
        for entry in root.findall("atom:entry", _NS):
            published_str = entry.findtext("atom:published", namespaces=_NS)
            if published_str:
                published = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
                if published < lookback_start:
                    continue

            arxiv_id_raw = entry.findtext("atom:id", namespaces=_NS) or ""
            arxiv_id = arxiv_id_raw.split("/abs/")[-1]
            title = (entry.findtext("atom:title", namespaces=_NS) or "").strip().replace("\n", " ")
            abstract = (entry.findtext("atom:summary", namespaces=_NS) or "").strip().replace("\n", " ")
            pdf_url = arxiv_id_raw.replace("/abs/", "/pdf/")

            items.append(RawItem(
                source=f"arxiv:{category}",
                external_id=arxiv_id,
                url=arxiv_id_raw,
                title=title,
                content=abstract,
            ))

        return items
