import time
from typing import List, Tuple

from src.llm.gemini import GeminiProvider
from src.utils.logger import get_logger

logger = get_logger(__name__)

_RPM_LIMIT = 15
_SECONDS_PER_CALL = 60 / _RPM_LIMIT  # 4 seconds between calls


def summarize_items(items: List[dict]) -> List[Tuple[dict, object]]:
    """
    Summarize each item via Gemini.
    Returns list of (item, ScoredResult) pairs.
    Items that fail summarization are skipped with a warning.
    """
    provider = GeminiProvider()
    results = []

    for i, item in enumerate(items):
        try:
            scored = provider.summarize(
                source=item["source"],
                title=item["title"],
                content=item.get("content") or "",
                url=item["url"],
            )
            results.append((item, scored))
            logger.debug("[%d/%d] Scored '%s' → importance=%d", i + 1, len(items), item["title"][:60], scored.importance)
        except Exception as e:
            logger.warning("Summarize failed for '%s': %s", item["title"][:60], e)

        # Rate limit: stay under 15 RPM
        if i < len(items) - 1:
            time.sleep(_SECONDS_PER_CALL)

    logger.info("Summarized %d/%d items", len(results), len(items))
    return results
