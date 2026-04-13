import os
from datetime import datetime

import requests

from src.utils.logger import get_logger

logger = get_logger(__name__)

_API_BASE = "https://api.telegram.org/bot{token}/sendMessage"
_MAX_CHARS = 4096
_MAX_ITEMS_FALLBACK = 10

_DAILY_MESSAGES = [
    # Energy / motivation
    "Stay sharp out there 🧠",
    "Build something today 🚀",
    "Think deep, move fast ⚡",
    "Curious minds move fast 🏃",
    "Ship it, iterate later 🛳️",
    "Read. Think. Build. Repeat 🔁",
    "Benchmark yourself daily 📏",
    "Strong priors, open mind 🔮",
    "Keep the weights updating 📈",
    "Zero-shot your morning ☀️",
    # Technical / playful
    "Good things take compute ⚙️",
    "The future is compiling 🔧",
    "Another day, another token 🪙",
    "Less noise, more signal 📡",
    "Gradients pointing up today 📊",
    "Great models need great data 🗂️",
    "Your attention is valuable 🎯",
    "Inference time — let's go 💨",
    "Low loss, high vibes ✨",
    "The context window is open 🪟",
    "Entropy decreasing since morning ❄️",
    "Today's paper, tomorrow's product 📄",
    "Fine-tune your day 🎛️",
    "Stay in distribution 🎲",
    "Parallel processing engaged 🤖",
    "No hallucinations today 🙅",
    "Ground truth is out there 🌍",
    "High precision, high recall 🎯",
    "New weights dropped overnight 🌙",
    "Latency low, curiosity high 🔍",
    "Softmax on the day 🌅",
    "Attention is all you need 👁️",
    "Tokens well spent today 💬",
    "Batch size: one good day 📦",
    "Training loss: minimal ✅",
    "Feature complete, ship it 🏁",
    "Sparse but high quality 💎",
    "Embeddings aligned, let's go 🧭",
    "Context loaded, ready to learn 📚",
    "Model deployed, mission started 🎖️",
    # Calm / focus
    "One thing at a time 🎯",
    "Deep work starts now 🔕",
    "Slow down to speed up 🐢",
    "Focus is a superpower 🦸",
    "Cut the noise today 🔇",
    "Quality over quantity, always ⚖️",
    "Small steps, big leaps 🦶",
    "Clear head, sharp output 🪟",
    "Less scroll, more depth 📖",
    "The best run is consistent 🏅",
    # Wit / humor
    "Coffee first, embeddings later ☕",
    "Even GPT has bad days 😅",
    "Not all tokens are equal 🃏",
    "Avoid local minima today 🏔️",
    "Regularize your expectations 📉",
    "Don't overfit to yesterday 🔄",
    "Dropout keeps you humble 🙏",
    "Early stopping is wisdom 🛑",
    "Cross-entropy with your inbox 📧",
    "Normalize before you judge ⚖️",
    "Your bias needs tuning 🎚️",
    "Backprop through your assumptions 🔙",
    "The loss will converge 🌀",
    "Patience: a hyperparameter 🕰️",
    "Skip connection to sanity 🔗",
    # Wonder / science
    "The universe is gradient descent 🌌",
    "Every paper is a gift 🎁",
    "Science moves at inference speed 🔬",
    "Reproduce the results today 🧪",
    "Open source, open mind 🌐",
    "Peer review yourself first 🪞",
    "Ideas compound like interest 💡",
    "Curiosity is the best optimizer 🔭",
    "Understand before you build 🏗️",
    "First principles, always 🧱",
]


def _daily_message(dt: datetime) -> str:
    idx = dt.timetuple().tm_yday % len(_DAILY_MESSAGES)
    return _DAILY_MESSAGES[idx]


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
        dt = datetime.strptime(date_part, "%Y-%m-%d")
        time_label = "08:00" if period == "Morning" else "20:00"
        date_label = dt.strftime(f"%A %-d %B, {time_label}")
    except Exception:
        date_label = date_part
        dt = datetime.now()

    tagline = _daily_message(dt)
    header = f"📅 <b>{date_label}</b>\n{tagline}\n\n🔬 <b>AI Digest</b>\n\n"
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
