from typing import List, Dict
from urllib.parse import urlparse

from thefuzz import fuzz

from src.utils.logger import get_logger

logger = get_logger(__name__)

_TITLE_THRESHOLD = 78  # fuzzy match % to consider two titles the same story


def _normalize_url(url: str) -> str:
    """Strip scheme, www, and trailing slash for URL comparison."""
    try:
        p = urlparse(url)
        host = p.netloc.lower().removeprefix("www.")
        path = p.path.rstrip("/")
        return f"{host}{path}"
    except Exception:
        return url.lower()


def deduplicate(items: List[dict]) -> List[dict]:
    """
    Group items by URL or fuzzy title similarity.
    Returns one representative item per group, with a dedup_group tag
    and a cross_source_boost flag when the story appeared in multiple sources.
    Each input item must have: id, source, url, title, content, source_score, fetched_at.
    """
    groups: List[List[dict]] = []

    for item in items:
        placed = False
        norm_url = _normalize_url(item["url"])

        for group in groups:
            rep = group[0]
            # Exact URL match
            if _normalize_url(rep["url"]) == norm_url:
                group.append(item)
                placed = True
                break
            # Fuzzy title match
            if fuzz.token_sort_ratio(item["title"], rep["title"]) >= _TITLE_THRESHOLD:
                group.append(item)
                placed = True
                break

        if not placed:
            groups.append([item])

    result = []
    for group in groups:
        sources = {i["source"] for i in group}
        cross_source = len(sources) > 1

        # Pick the item with the highest source_score; fall back to first
        best = max(group, key=lambda i: i.get("source_score") or 0)
        best = dict(best)  # copy
        best["dedup_group"] = str(best["id"]) if not cross_source else f"cross:{best['id']}"
        best["cross_source_boost"] = cross_source

        if cross_source:
            logger.debug("Dedup: merged %d sources for '%s'", len(sources), best["title"][:60])

        result.append(best)

    logger.info("Dedup: %d items → %d unique", len(items), len(result))
    return result
