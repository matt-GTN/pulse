import os
import time
from typing import List, Tuple

from src.utils.logger import get_logger

logger = get_logger(__name__)

_RPM_LIMITS = {
    "gemini": 15,
    "groq": 30,
}


def _make_provider():
    llm = os.environ.get("LLM_PROVIDER", "gemini").lower()
    if llm == "groq":
        from src.llm.groq import GroqProvider
        return GroqProvider(), _RPM_LIMITS["groq"]
    from src.llm.gemini import GeminiProvider
    return GeminiProvider(), _RPM_LIMITS["gemini"]


def summarize_items(items: List[dict]) -> List[Tuple[dict, object]]:
    """
    Summarize each item via the configured LLM provider (LLM_PROVIDER env var).
    Returns list of (item, ScoredResult) pairs.
    Items that fail summarization are skipped with a warning.
    """
    provider, rpm = _make_provider()
    seconds_per_call = 60 / rpm
    results = []
    last_error = None

    for i, item in enumerate(items):
        try:
            scored = provider.summarize(
                source=item["source"],
                title=item["title"],
                content=item.get("content") or "",
                url=item["url"],
            )
            results.append((item, scored))
            logger.info("[%d/%d] Scored '%s' → importance=%d", i + 1, len(items), item["title"][:60], scored.importance)
        except Exception as e:
            last_error = e
            logger.warning("Summarize failed for '%s': %s", item["title"][:60], e)

        if i < len(items) - 1:
            time.sleep(seconds_per_call)

    logger.info("Summarized %d/%d items", len(results), len(items))
    if items and not results and last_error is not None:
        raise last_error
    return results
