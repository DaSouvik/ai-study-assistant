from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import db
from sqlalchemy.exc import OperationalError


class DatabaseTests(unittest.TestCase):
    def test_postgres_uses_psycopg_and_requires_ssl(self) -> None:
        db.configure_database(
            "postgresql://user:password@localhost:5432/study"
        )
        engine = db._get_engine()

        self.assertEqual(engine.dialect.name, "postgresql")
        self.assertEqual(engine.dialect.driver, "psycopg")
        self.assertEqual(engine.url.query["sslmode"], "require")
        db.configure_database(None)

    def test_database_error_hint_classifies_authentication_safely(self) -> None:
        error = OperationalError(
            "connect",
            {},
            Exception('password authentication failed for user "hidden-user"'),
        )

        hint = db.database_error_hint(error)

        self.assertIn("rejected database authentication", hint)
        self.assertNotIn("hidden-user", hint)

    def test_database_error_hint_classifies_network_route_failure(self) -> None:
        error = OperationalError(
            "connect",
            {},
            Exception("Network is unreachable"),
        )

        self.assertIn(
            "no network route",
            db.database_error_hint(error).casefold(),
        )

    def test_library_search_rejects_invalid_limit(self) -> None:
        with self.assertRaises(TypeError):
            db.find_library_matches(
                "photosynthesis",
                owner_id="google:alice",
                limit=True,
            )
        with self.assertRaises(ValueError):
            db.find_library_matches(
                "photosynthesis",
                owner_id="google:alice",
                limit=0,
            )

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
                connection.execute(
                    """
                    INSERT INTO documents (filename, summary)
                    VALUES (?, ?)
                    """,
                    ("legacy.pdf", "Unassigned shared document"),
                )
                connection.commit()
            finally:
                connection.close()

            with patch.object(db, "DATABASE_PATH", database_path):
                db.configure_database(None)
                db.initialize_database()

                self.assertEqual(db.get_documents(owner_id="google:alice"), [])
                with closing(sqlite3.connect(database_path)) as connection:
                    legacy_owner = connection.execute(
                        "SELECT owner_id FROM documents WHERE id = 1"
                    ).fetchone()[0]
                self.assertIsNone(legacy_owner)

                document_id = db.save_document(
                    "notes.pdf",
                    "Photosynthesis converts sunlight into energy.",
                    "Photosynthesis converts sunlight into energy.",
                    owner_id="google:alice",
                )

                document = db.get_document(
                    document_id,
                    owner_id="google:alice",
                )
                self.assertIsNotNone(document)
                self.assertEqual(document["filename"], "notes.pdf")
                self.assertIn("Photosynthesis", document["content"])
                self.assertEqual(
                    len(db.get_documents(owner_id="google:alice")),
                    1,
                )

                matches = db.find_library_matches(
                    "sunlight",
                    owner_id="google:alice",
                )
                self.assertEqual(len(matches), 1)
                self.assertEqual(matches[0]["id"], document_id)

                db.delete_document(document_id, owner_id="google:alice")
                self.assertIsNone(
                    db.get_document(document_id, owner_id="google:alice")
                )

    def test_library_operations_are_scoped_to_the_owner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "study_assistant.db"
            with patch.object(db, "DATABASE_PATH", database_path):
                db.configure_database(None)
                db.initialize_database()
                alice_document_id = db.save_document(
                    "alice.pdf",
                    "Private photosynthesis notes.",
                    "Photosynthesis notes.",
                    owner_id="google:alice",
                )
                bob_document_id = db.save_document(
                    "bob.pdf",
                    "Private evaporation notes.",
                    "Evaporation notes.",
                    owner_id="google:bob",
                )

                self.assertEqual(
                    [doc["id"] for doc in db.get_documents(owner_id="google:alice")],
                    [alice_document_id],
                )
                self.assertEqual(
                    db.find_library_matches(
                        "evaporation",
                        owner_id="google:alice",
                    ),
                    [],
                )
                self.assertIsNone(
                    db.get_document(bob_document_id, owner_id="google:alice")
                )

                db.delete_document(
                    bob_document_id,
                    owner_id="google:alice",
                )
                self.assertIsNotNone(
                    db.get_document(bob_document_id, owner_id="google:bob")
                )


if __name__ == "__main__":
    unittest.main()
