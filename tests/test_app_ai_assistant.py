from pathlib import Path
import unittest

from streamlit.testing.v1 import AppTest


class AppAIAssistantTests(unittest.TestCase):
    def test_ai_assistant_page_explains_local_ollama_setup(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run()

        app.radio[0].set_value("AI assistant").run()

        self.assertIn(
            "Ollama runs the model on the same computer as this app. There is no API key or provider usage bill.",
            [message.value for message in app.info],
        )
        self.assertTrue(
            any(
                "The public Streamlit Cloud app cannot access Ollama on your PC."
                in message.value
                for message in app.warning
            )
        )
        self.assertIn(
            "ollama pull gemma3:1b",
            [code.value for code in app.code],
        )
        self.assertEqual(len(app.chat_input), 1)


if __name__ == "__main__":
    unittest.main()
