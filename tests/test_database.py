import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import db


class DatabaseTests(unittest.TestCase):
    def test_library_search_rejects_invalid_limit(self) -> None:
        with self.assertRaises(TypeError):
            db.find_library_matches("photosynthesis", limit=True)
        with self.assertRaises(ValueError):
            db.find_library_matches("photosynthesis", limit=0)

    def test_migrates_existing_table_and_persists_documents(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "study_assistant.db"
            connection = sqlite3.connect(database_path)
            try:
                connection.execute(
                    """
                    CREATE TABLE documents (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        filename TEXT NOT NULL,
                        summary TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            finally:
                connection.close()

            with patch.object(db, "DATABASE_PATH", database_path):
                db.initialize_database()
                document_id = db.save_document(
                    "notes.pdf",
                    "Photosynthesis converts sunlight into energy.",
                    "Photosynthesis converts sunlight into energy.",
                )

                document = db.get_document(document_id)
                self.assertIsNotNone(document)
                self.assertEqual(document["filename"], "notes.pdf")
                self.assertIn("Photosynthesis", document["content"])
                self.assertEqual(len(db.get_documents()), 1)

                matches = db.find_library_matches("sunlight")
                self.assertEqual(len(matches), 1)
                self.assertEqual(matches[0]["id"], document_id)

                db.delete_document(document_id)
                self.assertIsNone(db.get_document(document_id))


if __name__ == "__main__":
    unittest.main()
