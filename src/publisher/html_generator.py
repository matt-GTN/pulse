import os
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src.utils.logger import get_logger

logger = get_logger(__name__)

_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"
_OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/app/output"))


def _jinja_env():
    return Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)), autoescape=True)


def _format_dt(dt: datetime) -> str:
    """Format a datetime to 'Apr 13, 08:00'."""
    if dt.tzinfo is not None:
        dt = dt.astimezone()
    return dt.strftime("%b %-d, %H:%M")


def generate_digest_page(slug: str, digest_data: dict) -> Path:
    """
    Render and write the digest HTML page.
    digest_data = {"digest": {...}, "items": [...]}
    Returns the path written.
    """
    env = _jinja_env()
    template = env.get_template("digest.html")

    digest = digest_data["digest"]
    raw_items = digest_data["items"]

    period = "morning" if "morning" in slug else "evening"
    window_start = _format_dt(digest["window_start"])
    window_end = _format_dt(digest["window_end"])
    date_str = digest["window_end"].strftime("%b %-d, %Y") if hasattr(digest["window_end"], "strftime") else slug[:10]

    title = f"AI Digest — {date_str} ({period.capitalize()})"

    items = [
        {
            "one_liner": item["one_liner"],
            "full_summary": item["full_summary"],
            "importance": item["importance"],
            "source": item["source"],
            "url": item["url"],
        }
        for item in raw_items
    ]

    html = template.render(
        title=title,
        period=period,
        window_start=window_start,
        window_end=window_end,
        items=items,
        slug=slug,
    )

    out_dir = _OUTPUT_DIR / "digests"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{slug}.html"
    out_path.write_text(html, encoding="utf-8")
    logger.info("HTML written: %s", out_path)
    return out_path


def update_index(recent_digests: list) -> Path:
    """Re-render index.html from the list of recent digests."""
    env = _jinja_env()
    template = env.get_template("index.html")

    digests = []
    for d in recent_digests:
        slug = d["slug"]
        period = "morning" if "morning" in slug else "evening"
        date_part = slug[:10]  # 2026-04-13
        try:
            dt = datetime.strptime(date_part, "%Y-%m-%d")
            date_label = dt.strftime("%b %-d, %Y")
        except ValueError:
            date_label = date_part
        digests.append({
            "slug": slug,
            "label": f"AI Digest — {date_label} ({period.capitalize()})",
            "date_label": date_label,
            "item_count": d["item_count"],
        })

    html = template.render(digests=digests)
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    index_path = _OUTPUT_DIR / "index.html"
    index_path.write_text(html, encoding="utf-8")
    logger.info("Index updated: %s", index_path)
    return index_path
