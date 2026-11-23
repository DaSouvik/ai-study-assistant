import unittest
from unittest.mock import MagicMock, patch

from claude_assistant import (
    MAX_CONTEXT_CHARS,
    MAX_HISTORY_MESSAGES,
    MAX_OUTPUT_TOKENS,
    MODEL_ID,
    build_system_prompt,
    stream_claude_response,
)


class ClaudeAssistantTests(unittest.TestCase):
    def test_stream_uses_recent_history_and_bounded_note_context(self) -> None:
        history = [
            {
                "role": "user" if index % 2 == 0 else "assistant",
                "content": f"history-{index}",
            }
            for index in range(MAX_HISTORY_MESSAGES + 2)
        ]
        stream = MagicMock()
        stream.__enter__.return_value = stream
        stream.text_stream = iter(["Study ", "answer"])
        client = MagicMock()
        client.messages.stream.return_value = stream
        study_notes = ("N" * MAX_CONTEXT_CHARS) + "TRAILING_SENTINEL"

        with patch("claude_assistant.Anthropic", return_value=client):
            response = "".join(
                stream_claude_response(
                    api_key="test-key",
                    history=history,
                    question="Explain this",
                    study_notes=study_notes,
                )
            )

        request = client.messages.stream.call_args.kwargs
        self.assertEqual(response, "Study answer")
        self.assertEqual(request["model"], MODEL_ID)
        self.assertEqual(request["max_tokens"], MAX_OUTPUT_TOKENS)
        self.assertEqual(
            request["messages"][0]["content"],
            "history-2",
        )
        self.assertEqual(
            request["messages"][-1],
            {"role": "user", "content": "Explain this"},
        )
        self.assertIn("[Study notes truncated.]", request["system"])
        self.assertNotIn("TRAILING_SENTINEL", request["system"])

    def test_stream_rejects_empty_api_key(self) -> None:
        response = stream_claude_response(
            api_key=" ",
            history=[],
            question="Hello",
        )

        with self.assertRaisesRegex(ValueError, "api_key"):
            next(response)

    def test_prompt_without_notes_does_not_add_document_context(self) -> None:
        prompt = build_system_prompt()

        self.assertIn("patient study coach", prompt)
        self.assertNotIn("Study notes JSON string", prompt)


if __name__ == "__main__":
    unittest.main()
