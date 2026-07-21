"""
Pulse — AI Digest Pipeline
Usage: uv run python -m src.main morning
"""
import sys
from datetime import datetime, timezone, timedelta

from src.config import load_env, load_sources, build_source_weights
from src.utils.logger import get_logger
from src.db import repository as repo
from src.fetchers.arxiv import ArxivFetcher
from src.fetchers.reddit import RedditFetcher
from src.fetchers.hackernews import HackerNewsFetcher
from src.fetchers.rss import RSSFetcher
from src.fetchers.anthropic import AnthropicFetcher
from src.processor.deduplicator import deduplicate
from src.processor.summarizer import summarize_items
from src.processor.ranker import rank
from src.publisher.html_generator import generate_digest_page, update_index
from src.publisher.telegram import send_digest

logger = get_logger("pulse.main")

_TZ = timezone.utc  # all internal times in UTC


def _time_window(period: str):
    """Return (window_start, window_end, slug) for the given period."""
    now = datetime.now(tz=_TZ)
    today = now.date()

    if period == "morning":
        # Last 24h — single daily digest run at 07:30 Paris (05:30 UTC)
        window_end = now
        window_start = window_end - timedelta(hours=24)
        slug = f"{today.isoformat()}-morning"
    else:
        raise ValueError(f"Unknown period: {period!r}. Use 'morning'.")

    return window_start, window_end, slug


def _run_fetchers(sources: dict, window_start: datetime, window_end: datetime):
    """Run all enabled fetchers, insert to DB, return list of raw item dicts."""
    fetchers = []
    if sources.get("arxiv", {}).get("enabled"):
        fetchers.append(ArxivFetcher(sources["arxiv"]))
    if sources.get("reddit", {}).get("enabled"):
        fetchers.append(RedditFetcher(sources["reddit"]))
    if sources.get("hackernews", {}).get("enabled"):
        fetchers.append(HackerNewsFetcher(sources["hackernews"]))
    if sources.get("rss", {}).get("enabled"):
        fetchers.append(RSSFetcher(sources["rss"]))
    if sources.get("anthropic", {}).get("enabled"):
        fetchers.append(AnthropicFetcher(sources["anthropic"]))

    inserted_items = []
    for fetcher in fetchers:
        try:
            raw_items = fetcher.fetch(window_start, window_end)
            for item in raw_items:
                row_id = repo.insert_raw_item(
                    source=item.source,
                    external_id=item.external_id,
                    url=item.url,
                    title=item.title,
                    content=item.content,
                    source_score=item.source_score,
                )
                if row_id:
                    inserted_items.append({
                        "id": row_id,
                        "source": item.source,
                        "external_id": item.external_id,
                        "url": item.url,
                        "title": item.title,
                        "content": item.content,
                        "source_score": item.source_score,
                    })
        except Exception as e:
            logger.warning("Fetcher %s failed: %s", type(fetcher).__name__, e)

    logger.info("Fetching done: %d items in window", len(inserted_items))
    return inserted_items


def _fallback_telegram(slug: str, raw_items: list):
    """Send raw headlines when LLM is unavailable."""
    logger.warning("Sending fallback Telegram message (no summaries)")
    items = [
        {"one_liner": item["title"][:100], "importance": 5, "position": i + 1}
        for i, item in enumerate(raw_items[:15])
    ]
    send_digest(slug, items)


def main(period: str):
    load_env()
    sources = load_sources()
    repo.init_db()

    window_start, window_end, slug = _time_window(period)
    logger.info("Starting %s digest: %s → %s", period, window_start, window_end)

    # ── 1. Fetch ──────────────────────────────────────────────────────────────
    raw_items = _run_fetchers(sources, window_start, window_end)

    if not raw_items:
        logger.warning("No items fetched — skipping digest")
        return

    # ── 2. Filter already-published items, then deduplicate ──────────────────
    published_ids = repo.get_recently_published_raw_ids(limit_digests=2)
    if published_ids:
        before = len(raw_items)
        raw_items = [i for i in raw_items if i["id"] not in published_ids]
        logger.info("Cross-run dedup: dropped %d already-published items", before - len(raw_items))
    unique_items = deduplicate(raw_items)

    # ── 3. Summarize + Rank ───────────────────────────────────────────────────
    try:
        scored_pairs = summarize_items(unique_items)
        top_pairs = rank(scored_pairs, source_weights=build_source_weights(sources))
    except Exception as e:
        logger.error("LLM pipeline failed: %s — sending fallback", e)
        _fallback_telegram(slug, raw_items)
        return

    if not top_pairs:
        logger.warning("No scored items — skipping digest")
        return

    # ── 4. Persist scored items & digest ─────────────────────────────────────
    scored_ids = []
    for item, scored in top_pairs:
        sid = repo.insert_scored_item(
            raw_item_id=item["id"],
            one_liner=scored.one_liner,
            full_summary=scored.full_summary,
            importance=scored.importance,
            dedup_group=item.get("dedup_group"),
        )
        scored_ids.append(sid)

    digest_id = repo.create_digest(slug, window_start, window_end, scored_ids)

    # ── 5. Publish HTML ───────────────────────────────────────────────────────
    try:
        digest_data = repo.get_digest_by_slug(slug)
        generate_digest_page(slug, digest_data)
        repo.mark_html_generated(digest_id)

        recent = repo.get_recent_digests()
        update_index(recent)
    except Exception as e:
        logger.error("HTML generation failed: %s", e)

    # ── 6. Notify via Telegram ────────────────────────────────────────────────
    try:
        telegram_items = [
            {"one_liner": scored.one_liner, "importance": scored.importance, "position": pos + 1}
            for pos, (_, scored) in enumerate(top_pairs)
        ]
        ok = send_digest(slug, telegram_items)
        if ok:
            repo.mark_telegram_sent(digest_id)
    except Exception as e:
        logger.error("Telegram notification failed: %s", e)

    logger.info("Digest %s complete — %d items", slug, len(top_pairs))


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] != "morning":
        print("Usage: uv run python -m src.main morning", file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1])
