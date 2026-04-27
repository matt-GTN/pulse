import os
import yaml
from pathlib import Path

_REQUIRED_ENV_VARS = [
    "DATABASE_URL",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "DIGEST_BASE_URL",
]

_PROVIDER_REQUIRED = {
    "gemini": ["GEMINI_API_KEY", "GEMINI_MODEL"],
    "groq": ["GROQ_API_KEY"],
}


def load_env():
    """Validate required env vars are present. Raises RuntimeError with all missing vars."""
    missing = [v for v in _REQUIRED_ENV_VARS if not os.environ.get(v)]
    provider = os.environ.get("LLM_PROVIDER", "gemini").lower()
    missing += [v for v in _PROVIDER_REQUIRED.get(provider, []) if not os.environ.get(v)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


def load_sources(path=None):
    """Load sources.yaml. Defaults to <project_root>/sources.yaml."""
    if path is None:
        path = Path(__file__).parent.parent / "sources.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


def build_source_weights(sources: dict) -> dict:
    """
    Map each fetcher source string → editorial weight (int, default 1).
    Weight semantics: 1 = baseline, 2 = curated, 3 = top-tier.
    Applied at ranking time as (weight - 1) boost on top of LLM importance.
    """
    weights: dict = {}

    arxiv = sources.get("arxiv") or {}
    aw = arxiv.get("weight", 1)
    for cat in arxiv.get("categories", []):
        weights[f"arxiv:{cat}"] = aw

    reddit = sources.get("reddit") or {}
    default_rw = reddit.get("weight", 1)
    per_sub = reddit.get("weights") or {}
    for sub in reddit.get("subreddits", []):
        weights[f"reddit:{sub}"] = per_sub.get(sub, default_rw)

    hn = sources.get("hackernews") or {}
    weights["hn"] = hn.get("weight", 1)

    rss = sources.get("rss") or {}
    default_fw = rss.get("default_weight", 1)
    for feed in rss.get("feeds", []):
        name = feed.get("name")
        if name:
            weights[f"rss:{name}"] = feed.get("weight", default_fw)

    anthropic = sources.get("anthropic") or {}
    weights["anthropic"] = anthropic.get("weight", 3)

    return weights
