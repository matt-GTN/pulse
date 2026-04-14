import os
from datetime import datetime, timezone
from typing import List

import requests

from .base import BaseFetcher, RawItem
from src.utils.logger import get_logger

logger = get_logger(__name__)

_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
_API_BASE = "https://oauth.reddit.com"
_USER_AGENT = "python:pulse-digest:v1.0 (by /u/mattgtn)"


class RedditFetcher(BaseFetcher):
    def __init__(self, config: dict):
        super().__init__(config)
        self._token: str | None = None

    def _get_token(self) -> str:
        client_id = os.environ["REDDIT_CLIENT_ID"]
        client_secret = os.environ["REDDIT_CLIENT_SECRET"]
        resp = requests.post(
            _TOKEN_URL,
            auth=(client_id, client_secret),
            data={"grant_type": "client_credentials"},
            headers={"User-Agent": _USER_AGENT},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    def fetch(self, window_start: datetime, window_end: datetime) -> List[RawItem]:
        try:
            self._token = self._get_token()
        except Exception as e:
            logger.warning("Reddit OAuth failed — skipping: %s", e)
            return []

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
        url = f"{_API_BASE}/r/{sub}/{sort}.json"
        headers = {"Authorization": f"Bearer {self._token}", "User-Agent": _USER_AGENT}
        resp = requests.get(url, headers=headers, params={"limit": limit}, timeout=30)
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
