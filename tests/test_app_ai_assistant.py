from pathlib import Path
import unittest

from streamlit.testing.v1 import AppTest


class AppAIAssistantTests(unittest.TestCase):
    def test_ai_assistant_page_explains_cloudflare_setup(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run()

        app.radio[0].set_value("AI assistant").run()

        self.assertIn(
            "Configure a Cloudflare Workers AI account ID and API token in Streamlit Secrets to enable chat.",
            [message.value for message in app.info],
        )
        self.assertTrue(
            any(
                "Every visitor uses the same Cloudflare Workers AI free quota"
                in message.value
                for message in app.warning
            )
        )
        self.assertTrue(
            any(
                "YOUR_CLOUDFLARE_WORKERS_AI_TOKEN" in code.value
                for code in app.code
            )
        )


if __name__ == "__main__":
    unittest.main()
