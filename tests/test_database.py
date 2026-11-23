from contextlib import closing
import socket
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from database import db


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

    def test_network_diagnostic_reports_dns_and_tcp_by_ip_family(self) -> None:
        db.configure_database(
            "postgresql://user:password@db.example:5432/study"
        )
        addresses = [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("192.0.2.10", 5432),
            ),
            (
                socket.AF_INET6,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("2001:db8::10", 5432, 0, 0),
            ),
        ]
        ipv4_socket = MagicMock()
        ipv4_socket.__enter__.return_value = ipv4_socket
        ipv6_socket = MagicMock()
        ipv6_socket.__enter__.return_value = ipv6_socket
        ipv6_socket.connect.side_effect = OSError("unreachable")

        with (
            patch.object(db.socket, "getaddrinfo", return_value=addresses),
            patch.object(
                db.socket,
                "socket",
                side_effect=[ipv4_socket, ipv6_socket],
            ),
        ):
            result = db.diagnose_database_network()

        self.assertEqual(
            result,
            {
                "dns_resolved": True,
                "ipv4_dns": True,
                "ipv4_tcp": True,
                "ipv6_dns": True,
                "ipv6_tcp": False,
            },
        )
        db.configure_database(None)

    def test_network_diagnostic_reports_dns_failure_without_details(self) -> None:
        db.configure_database(
            "postgresql://user:password@db.example:5432/study"
        )
        with patch.object(
            db.socket,
            "getaddrinfo",
            side_effect=socket.gaierror("sensitive resolver detail"),
        ):
            result = db.diagnose_database_network()

        self.assertEqual(
            result,
            {
                "dns_resolved": False,
                "ipv4_dns": False,
                "ipv4_tcp": False,
                "ipv6_dns": False,
                "ipv6_tcp": False,
            },
        )
        db.configure_database(None)

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
