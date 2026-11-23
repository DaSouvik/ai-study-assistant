from collections.abc import Iterator
from io import BytesIO
import json
import unittest
from urllib.error import URLError
from unittest.mock import patch

from local_assistant import (
    MAX_CONTEXT_CHARS,
    MAX_HISTORY_MESSAGES,
    MAX_OUTPUT_TOKENS,
    MODEL_ID,
    OLLAMA_CHAT_URL,
    LocalModelError,
    LocalModelNotFoundError,
    LocalModelUnavailableError,
    build_system_prompt,
    stream_local_response,
)


def _response(events: Iterator[dict[str, object]]) -> BytesIO:
    body = b"".join(
        json.dumps(event).encode("utf-8") + b"\n"
        for event in events
    )
    return BytesIO(body)


class LocalAssistantTests(unittest.TestCase):
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
                {"message": {"role": "assistant", "content": "Study "}},
                {
                    "message": {"role": "assistant", "content": "answer"},
                    "done": True,
                },
            ]
        )
        study_notes = ("N" * MAX_CONTEXT_CHARS) + "TRAILING_SENTINEL"

        with patch("local_assistant.urlopen", return_value=_response(events)) as urlopen:
            response = "".join(
                stream_local_response(
                    history=history,
                    question="Explain this",
                    study_notes=study_notes,
                )
            )

        request = urlopen.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(response, "Study answer")
        self.assertEqual(request.full_url, OLLAMA_CHAT_URL)
        self.assertEqual(payload["model"], MODEL_ID)
        self.assertEqual(payload["stream"], True)
        self.assertEqual(
            payload["options"]["num_predict"],
            MAX_OUTPUT_TOKENS,
        )
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

    def test_stream_rejects_empty_question(self) -> None:
        response = stream_local_response(history=[], question=" ")

        with self.assertRaisesRegex(ValueError, "question"):
            next(response)

    def test_stream_reports_missing_model(self) -> None:
        response = _response(
            iter([{"error": "model 'gemma3:1b' not found"}])
        )
        with patch("local_assistant.urlopen", return_value=response):
            with self.assertRaises(LocalModelNotFoundError):
                list(stream_local_response(history=[], question="Hello"))

    def test_stream_reports_unavailable_ollama_service(self) -> None:
        with patch(
            "local_assistant.urlopen",
            side_effect=URLError("connection refused"),
        ):
            with self.assertRaises(LocalModelUnavailableError):
                list(stream_local_response(history=[], question="Hello"))

    def test_stream_rejects_incomplete_response(self) -> None:
        response = _response(
            iter([{"message": {"role": "assistant", "content": "Partial"}}])
        )
        with patch("local_assistant.urlopen", return_value=response):
            with self.assertRaisesRegex(LocalModelError, "before completion"):
                list(stream_local_response(history=[], question="Hello"))

    def test_prompt_without_notes_does_not_add_document_context(self) -> None:
        prompt = build_system_prompt()

        self.assertIn("patient study coach", prompt)
        self.assertNotIn("Study notes JSON string", prompt)


if __name__ == "__main__":
    unittest.main()
