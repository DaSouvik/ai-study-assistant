from pathlib import Path
import unittest

from streamlit.testing.v1 import AppTest


class AppAIAssistantTests(unittest.TestCase):
    def test_ai_assistant_page_explains_missing_api_key(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run()

        app.radio[0].set_value("AI assistant").run()

        self.assertIn(
            "Claude isn't configured yet. Add your API key to Streamlit Secrets:",
            [message.value for message in app.info],
        )
        self.assertIn(
            '[anthropic]\napi_key = "YOUR_ANTHROPIC_API_KEY"',
            [code.value for code in app.code],
        )


if __name__ == "__main__":
    unittest.main()
