from pathlib import Path
import unittest

from streamlit.testing.v1 import AppTest


class AppAuthenticationTests(unittest.TestCase):
    def test_missing_private_configuration_blocks_app_content(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run()

        self.assertIn(
            "Private sign-in and storage are not configured.",
            [error.value for error in app.error],
        )
        self.assertEqual(len(app.button), 0)
        self.assertEqual(len(app.radio), 0)


if __name__ == "__main__":
    unittest.main()
