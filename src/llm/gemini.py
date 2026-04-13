import json
import os
import time

from google import genai
from google.genai import types

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


class GeminiProvider(BaseLLMProvider):
    def __init__(self):
        self._client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        self._model = os.environ["GEMINI_MODEL"]

    def summarize(self, source: str, title: str, content: str, url: str) -> ScoredResult:
        prompt = _PROMPT_TEMPLATE.format(
            source=source,
            title=title,
            content=(content or "")[:2000],
            url=url,
        )
        for attempt in range(4):
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=prompt,
                )
                return self._parse(response.text)
            except Exception as e:
                if "429" in str(e) or "quota" in str(e).lower():
                    wait = 2 ** (attempt + 2)
                    logger.warning("Gemini rate limit, retrying in %ds", wait)
                    time.sleep(wait)
                else:
                    raise
        raise RuntimeError("Gemini summarize failed after retries")

    def _parse(self, text: str) -> ScoredResult:
        # Strip markdown code fences if present
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text.strip())
        importance = int(data["importance"])
        importance = max(1, min(10, importance))
        one_liner = data["one_liner"][:100]
        return ScoredResult(
            one_liner=one_liner,
            full_summary=data["full_summary"],
            importance=importance,
        )
