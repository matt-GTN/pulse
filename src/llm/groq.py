import json
import os
import time

from openai import OpenAI

from .base import BaseLLMProvider, ScoredResult
from src.utils.logger import get_logger

logger = get_logger(__name__)

_PROMPT_TEMPLATE = """\
You are a concise AI news editor. Given the following item, produce:
1. ONE_LINER: A single sentence summary (max 100 chars). Facts only, no hype.
2. FULL_SUMMARY: 3-5 sentences covering what happened, who's involved, and why it matters technically. No opinions.
3. IMPORTANCE: Score 1-10 for an AI researcher/architect.
   - 10: Major model release, breakthrough paper, industry-shifting announcement
   - 7-9: Significant release, notable research, important product update
   - 4-6: Interesting but incremental, niche but solid
   - 1-3: Minor update, tangential to AI core

Source: {source}
Title: {title}
Content: {content}
URL: {url}

Respond in JSON only: {{"one_liner": "...", "full_summary": "...", "importance": N}}"""

_DEFAULT_MODEL = "llama-3.3-70b-versatile"


class GroqProvider(BaseLLMProvider):
    def __init__(self):
        self._client = OpenAI(
            api_key=os.environ["GROQ_API_KEY"],
            base_url="https://api.groq.com/openai/v1",
        )
        self._model = os.environ.get("GROQ_MODEL", _DEFAULT_MODEL)

    def summarize(self, source: str, title: str, content: str, url: str) -> ScoredResult:
        prompt = _PROMPT_TEMPLATE.format(
            source=source,
            title=title,
            content=(content or "")[:2000],
            url=url,
        )
        for attempt in range(4):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    response_format={"type": "json_object"},
                )
                return self._parse(response.choices[0].message.content)
            except Exception as e:
                e_str = str(e)
                if "429" in e_str or "503" in e_str or "rate" in e_str.lower() or "unavailable" in e_str.lower():
                    wait = 2 ** (attempt + 2)
                    logger.warning("Groq transient error (%s), retrying in %ds", e_str[:40], wait)
                    time.sleep(wait)
                else:
                    raise
        raise RuntimeError("Groq summarize failed after retries")

    def _parse(self, text: str) -> ScoredResult:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text.strip())
        importance = max(1, min(10, int(data["importance"])))
        return ScoredResult(
            one_liner=data["one_liner"][:100],
            full_summary=data["full_summary"],
            importance=importance,
        )
