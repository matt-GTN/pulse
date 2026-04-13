from datetime import datetime, timezone
from typing import List

import requests

from .base import BaseFetcher, RawItem
from src.utils.logger import get_logger

logger = get_logger(__name__)

_HEADERS = {"User-Agent": "pulse-digest/1.0 (personal AI news aggregator)"}


class RedditFetcher(BaseFetcher):
    def fetch(self, window_start: datetime, window_end: datetime) -> List[RawItem]:
        subreddits = self.config.get("subreddits", [])
        sort = self.config.get("sort", "hot")
        limit = self.config.get("limit", 30)
        items: List[RawItem] = []

        for sub in subreddits:
            try:
                items.extend(self._fetch_subreddit(sub, sort, limit, window_start, window_end))
            except Exception as e:
                logger.warning("Reddit fetch failed for r/%s: %s", sub, e)

        logger.info("Reddit: fetched %d items", len(items))
        return items

    def _fetch_subreddit(self, sub: str, sort: str, limit: int, window_start: datetime, window_end: datetime) -> List[RawItem]:
        url = f"https://www.reddit.com/r/{sub}/{sort}.json"
        resp = requests.get(url, headers=_HEADERS, params={"limit": limit}, timeout=30)
        resp.raise_for_status()

        posts = resp.json().get("data", {}).get("children", [])
        items = []
        for post in posts:
            d = post.get("data", {})
            created = datetime.fromtimestamp(d.get("created_utc", 0), tz=timezone.utc)

            if created < window_start or created >= window_end:
                continue

            post_id = d.get("id", "")
            title = d.get("title", "")
            selftext = d.get("selftext", "") or ""
            link_url = d.get("url", "")
            score = d.get("score")
            permalink = f"https://www.reddit.com{d.get('permalink', '')}"

            content = selftext[:1000] if selftext and selftext != "[removed]" else None

            items.append(RawItem(
                source=f"reddit:{sub}",
                external_id=post_id,
                url=link_url or permalink,
                title=title,
                content=content,
                source_score=float(score) if score is not None else None,
            ))

        return items
