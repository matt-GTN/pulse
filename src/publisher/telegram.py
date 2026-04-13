import os

import requests

from src.utils.logger import get_logger

logger = get_logger(__name__)

_API_BASE = "https://api.telegram.org/bot{token}/sendMessage"
_MAX_CHARS = 4096
_MAX_ITEMS_FALLBACK = 10


def send_digest(slug: str, items: list, base_url: str = None) -> bool:
    """
    Format and send the digest via Telegram Bot API.
    items: list of dicts with keys: one_liner, importance, position (1-based)
    Returns True on success.
    """
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    base_url = base_url or os.environ.get("DIGEST_BASE_URL", "")

    digest_url = f"{base_url}/digests/{slug}.html"
    date_part = slug[:10]
    period = "Morning" if "morning" in slug else "Evening"

    try:
        from datetime import datetime
        dt = datetime.strptime(date_part, "%Y-%m-%d")
        date_label = dt.strftime("%b %-d, %H:%M").replace("00:00", "08:00" if period == "Morning" else "20:00")
    except Exception:
        date_label = date_part

    header = f"🔬 <b>AI Digest</b> — {date_label}\n\n"
    footer = f"\n\n📰 <a href=\"{digest_url}\">Full digest</a>"

    lines = []
    for item in items:
        pos = item.get("position", len(lines) + 1)
        one_liner = item["one_liner"]
        item_url = f"{digest_url}#item-{pos}"
        lines.append(f"{pos}. {one_liner}\n   → <a href=\"{item_url}\">{item_url}</a>")

    # Build message, truncate to fit 4096 chars
    body = "\n\n".join(lines)
    message = header + body + footer

    if len(message) > _MAX_CHARS:
        lines = lines[:_MAX_ITEMS_FALLBACK]
        body = "\n\n".join(lines)
        message = header + body + footer
        logger.warning("Telegram message truncated to %d items", _MAX_ITEMS_FALLBACK)

    url = _API_BASE.format(token=token)
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    resp = requests.post(url, json=payload, timeout=15)
    if not resp.ok:
        logger.error("Telegram send failed: %s — %s", resp.status_code, resp.text)
        return False

    logger.info("Telegram message sent for %s", slug)
    return True
