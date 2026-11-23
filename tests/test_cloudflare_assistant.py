from collections.abc import Iterator
from io import BytesIO
import json
import unittest
from urllib.error import HTTPError, URLError
from unittest.mock import patch

from cloudflare_assistant import (
    MAX_CONTEXT_CHARS,
    MAX_HISTORY_MESSAGES,
    MAX_OUTPUT_TOKENS,
    MODEL_ID,
    CloudflareConfigurationError,
    CloudflareQuotaExceededError,
    CloudflareUnavailableError,
    build_system_prompt,
    stream_cloudflare_response,
)


ACCOUNT_ID = "0123456789abcdef0123456789abcdef"


def _response(events: Iterator[dict[str, object]]) -> BytesIO:
    body = b"".join(
        b"data: "
        + json.dumps(event).encode("utf-8")
        + b"\n\n"
        for event in events
    )
    return BytesIO(body + b"data: [DONE]\n\n")


class CloudflareAssistantTests(unittest.TestCase):
    def test_stream_uses_recent_history_and_bounded_note_context(self) -> None:
        history = [
            {
                "role": "user" if index % 2 == 0 else "assistant",
                "content": f"history-{index}",
            }
            for index in range(MAX_HISTORY_MESSAGES + 2)
        ]
        events = iter(
            [
                {"choices": [{"delta": {"role": "assistant"}}]},
                {"choices": [{"delta": {"content": "Study "}}]},
                {"choices": [{"delta": {"content": "answer"}}]},
            ]
        )
        study_notes = ("N" * MAX_CONTEXT_CHARS) + "TRAILING_SENTINEL"

        with patch(
            "cloudflare_assistant.urlopen",
            return_value=_response(events),
        ) as urlopen:
            response = "".join(
                stream_cloudflare_response(
                    account_id=ACCOUNT_ID,
                    api_token="test-token",
                    history=history,
                    question="Explain this",
                    study_notes=study_notes,
                )
            )

        request = urlopen.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(response, "Study answer")
        self.assertTrue(
            request.full_url.startswith(
                f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/"
            )
        )
        self.assertEqual(
            request.get_header("Authorization"),
            "Bearer test-token",
        )
        self.assertEqual(payload["model"], MODEL_ID)
        self.assertEqual(payload["stream"], True)
        self.assertEqual(payload["max_tokens"], MAX_OUTPUT_TOKENS)
        self.assertEqual(payload["messages"][1]["content"], "history-2")
        self.assertEqual(
            payload["messages"][-1],
            {"role": "user", "content": "Explain this"},
        )
        self.assertIn(
            "[Study notes truncated.]",
            payload["messages"][0]["content"],
        )
        self.assertNotIn(
            "TRAILING_SENTINEL",
            payload["messages"][0]["content"],
        )

    def test_stream_rejects_invalid_account_id(self) -> None:
        with self.assertRaises(CloudflareConfigurationError):
            list(
                stream_cloudflare_response(
                    account_id="not-an-account-id",
                    api_token="test-token",
                    history=[],
                    question="Hello",
                )
            )

    def test_stream_maps_quota_response(self) -> None:
        with patch(
            "cloudflare_assistant.urlopen",
            side_effect=HTTPError(
                "https://api.cloudflare.com",
                429,
                "Too Many Requests",
                hdrs=None,
                fp=None,
            ),
        ):
            with self.assertRaises(CloudflareQuotaExceededError):
                list(
                    stream_cloudflare_response(
                        account_id=ACCOUNT_ID,
                        api_token="test-token",
                        history=[],
                        question="Hello",
                    )
                )

    def test_stream_reports_unavailable_service(self) -> None:
        with patch(
            "cloudflare_assistant.urlopen",
            side_effect=URLError("connection refused"),
        ):
            with self.assertRaises(CloudflareUnavailableError):
                list(
                    stream_cloudflare_response(
                        account_id=ACCOUNT_ID,
                        api_token="test-token",
                        history=[],
                        question="Hello",
                    )
                )

    def test_prompt_without_notes_does_not_add_document_context(self) -> None:
        prompt = build_system_prompt()

        self.assertIn("patient study coach", prompt)
        self.assertNotIn("Study notes JSON string", prompt)


if __name__ == "__main__":
    unittest.main()
