import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.llm.groq import GroqProvider
from src.utils.errors import PipelineError, describe_error
from src.publisher.telegram import send_error
from src.processor.summarizer import summarize_items
from src.db import repository
from src import main


def response(content='{"one_liner":"News","full_summary":"Summary","importance":7}'):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class ReliabilityTests(unittest.TestCase):
    def provider(self, effects):
        with patch.dict(os.environ, {"GROQ_API_KEY": "test"}, clear=True), patch("src.llm.groq.OpenAI"):
            provider = GroqProvider()
        provider._client.chat.completions.create.side_effect = effects
        return provider

    def test_primary_success_does_not_call_fallback(self):
        provider = self.provider([response()])
        self.assertEqual(provider.summarize("rss", "title", "content", "url").importance, 7)
        calls = provider._client.chat.completions.create.call_args_list
        self.assertEqual([c.kwargs["model"] for c in calls], ["qwen/qwen3.8-27b"])

    def test_fallback_on_missing_model(self):
        error = RuntimeError("private response")
        error.status_code = 404
        provider = self.provider([error, response()])
        provider.summarize("rss", "title", "content", "url")
        self.assertEqual([c.kwargs["model"] for c in provider._client.chat.completions.create.call_args_list], ["qwen/qwen3.8-27b", "openai/gpt-oss-120b"])

    def test_invalid_json_uses_fallback(self):
        provider = self.provider([response("invalid"), response()])
        self.assertEqual(provider.summarize("rss", "title", "", "").importance, 7)

    @patch("src.llm.groq.time.sleep")
    def test_transient_exhaustion_uses_fallback(self, sleep):
        error = RuntimeError("private response")
        error.status_code = 429
        provider = self.provider([error] * 4 + [response()])
        provider.summarize("rss", "title", "", "")
        self.assertEqual(sleep.call_count, 3)
        self.assertEqual(provider._client.chat.completions.create.call_args.kwargs["model"], "openai/gpt-oss-120b")

    def test_both_model_errors_are_safe_and_verbose(self):
        error = RuntimeError("secret-token-canary")
        error.status_code = 404
        provider = self.provider([error, error])
        with self.assertRaises(PipelineError) as caught:
            provider.summarize("rss", "title", "", "")
        message = describe_error(caught.exception)
        self.assertIn("qwen/qwen3.8-27b", message)
        self.assertIn("openai/gpt-oss-120b", message)
        self.assertIn("HTTP 404", message)
        self.assertNotIn("secret-token-canary", message)

    def test_all_summaries_failed_propagates_error(self):
        provider = Mock()
        provider.summarize.side_effect = PipelineError("Both models unavailable")
        with patch("src.processor.summarizer._make_provider", return_value=(provider, 30)):
            with self.assertRaises(PipelineError):
                summarize_items([dict(source="rss", title="title", url="url")])

    @patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test", "TELEGRAM_CHAT_ID": "test"})
    @patch("src.publisher.telegram.requests.post")
    def test_alert_contains_stage_and_safe_database_diagnostic(self, post):
        error = RuntimeError("postgresql://user:password@private-host/db")
        error.pgcode = "42501"
        post.return_value.ok = True
        post.return_value.json.return_value = {"ok": True}
        self.assertTrue(send_error("Initialisation PostgreSQL", error, "2026-09-27-morning"))
        payload = post.call_args.kwargs["json"]
        self.assertIn("42501", payload["text"])
        self.assertIn("Initialisation PostgreSQL", payload["text"])
        self.assertNotIn("password", payload["text"])
        self.assertNotIn("parse_mode", payload)

    def test_existing_schema_needs_no_ddl(self):
        with patch.object(repository, "_get_conn") as connect:
            cursor = connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
            cursor.fetchone.return_value = ("raw_items", "scored_items", "digests", "digest_items")
            repository.init_db()
            self.assertEqual(cursor.execute.call_count, 1)
            self.assertTrue(cursor.execute.call_args.args[0].startswith("SELECT"))

    def test_database_startup_failure_alerts_and_fails(self):
        with patch.object(main, "load_env"), patch.object(main, "load_sources", return_value={}), patch.object(main.repo, "init_db", side_effect=RuntimeError("db failed")), patch.object(main, "send_error") as alert:
            with self.assertRaises(RuntimeError):
                main.main("morning")
            self.assertEqual(alert.call_args.args[0], "Initialisation PostgreSQL")
            alert.assert_called_once()


if __name__ == "__main__":
    unittest.main()
