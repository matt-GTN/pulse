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
from src.publisher.telegram import send_digest, send_error
from src.utils.errors import PipelineError, describe_error

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
    failures = []
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
            failures.append(f"{type(fetcher).__name__}: {describe_error(e)}")
            logger.warning("Fetcher failed: %s", failures[-1])

    if failures and not inserted_items:
        raise PipelineError("Collecte impossible. " + " ; ".join(failures))
    logger.info("Fetching done: %d items in window", len(inserted_items))
    return inserted_items


def _run(period: str, state: dict):
    load_env()
    sources = load_sources()
    state["stage"] = "Initialisation PostgreSQL"
    repo.init_db()

    window_start, window_end, slug = _time_window(period)
    logger.info("Starting %s digest: %s → %s", period, window_start, window_end)

    # ── 1. Fetch ──────────────────────────────────────────────────────────────
    state["stage"] = "Collecte des sources"
    raw_items = _run_fetchers(sources, window_start, window_end)

    if not raw_items:
        logger.warning("No items fetched — skipping digest")
        return

    # ── 2. Filter already-published items, then deduplicate ──────────────────
    state["stage"] = "Déduplication et lecture PostgreSQL"
    published_ids = repo.get_recently_published_raw_ids(limit_digests=2)
    if published_ids:
        before = len(raw_items)
        raw_items = [i for i in raw_items if i["id"] not in published_ids]
        logger.info("Cross-run dedup: dropped %d already-published items", before - len(raw_items))
    unique_items = deduplicate(raw_items)

    # ── 3. Summarize + Rank ───────────────────────────────────────────────────
    state["stage"] = "Résumés et classement LLM"
    scored_pairs = summarize_items(unique_items)
    top_pairs = rank(scored_pairs, source_weights=build_source_weights(sources))
    if unique_items and not top_pairs:
        raise PipelineError("Aucun résumé exploitable n’a été produit.")
    if not top_pairs:
        return

    # ── 4. Persist scored items & digest ─────────────────────────────────────
    state["stage"] = "Enregistrement PostgreSQL"
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

    state["stage"] = "Publication HTML"
    # ── 5. Publish HTML ───────────────────────────────────────────────────────
    digest_data = repo.get_digest_by_slug(slug)
    generate_digest_page(slug, digest_data)
    repo.mark_html_generated(digest_id)

    recent = repo.get_recent_digests()
    update_index(recent)

    state["stage"] = "Notification Telegram"
    # ── 6. Notify via Telegram ────────────────────────────────────────────────
    telegram_items = [
        {"one_liner": scored.one_liner, "importance": scored.importance, "position": pos + 1}
        for pos, (_, scored) in enumerate(top_pairs)
    ]
    ok = send_digest(slug, telegram_items)
    if not ok:
        raise PipelineError("Telegram a refusé la notification du digest.")
    repo.mark_telegram_sent(digest_id)

    logger.info("Digest %s complete — %d items", slug, len(top_pairs))


def main(period: str):
    state = {"stage": "Configuration"}
    try:
        _run(period, state)
    except Exception as error:
        slug = f"{datetime.now(tz=_TZ).date().isoformat()}-{period}"
        send_error(state["stage"], error, slug)
        raise


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] != "morning":
        print("Usage: uv run python -m src.main morning", file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1])
