import os
import yaml
from pathlib import Path

_REQUIRED_ENV_VARS = [
    "DATABASE_URL",
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "DIGEST_BASE_URL",
]


def load_env():
    """Validate required env vars are present. Raises RuntimeError with all missing vars."""
    missing = [v for v in _REQUIRED_ENV_VARS if not os.environ.get(v)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


def load_sources(path=None):
    """Load sources.yaml. Defaults to <project_root>/sources.yaml."""
    if path is None:
        path = Path(__file__).parent.parent / "sources.yaml"
    with open(path) as f:
        return yaml.safe_load(f)
