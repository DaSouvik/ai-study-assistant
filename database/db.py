
from contextlib import contextmanager
from collections.abc import Generator
from pathlib import Path
import sqlite3


DATABASE_PATH = Path(__file__).resolve().parents[1] / "study_assistant.db"


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_database() -> None:
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(documents)")
        }
        if "content" not in columns:
            connection.execute(
                "ALTER TABLE documents "
                "ADD COLUMN content TEXT NOT NULL DEFAULT ''"
            )


def save_document(filename: str, content: str, summary: str) -> int:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO documents (filename, content, summary)
            VALUES (?, ?, ?)
            """,
            (filename, content, summary),
        )
        return int(cursor.lastrowid)


def get_documents() -> list[dict[str, object]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, filename, summary, created_at, length(content) AS char_count
            FROM documents
            ORDER BY created_at DESC, id DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_document(document_id: int) -> dict[str, object] | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, filename, summary, content, created_at
            FROM documents
            WHERE id = ?
            """,
            (document_id,),
        ).fetchone()
    return dict(row) if row is not None else None


def find_library_matches(query: str, *, limit: int = 50) -> list[dict[str, object]]:
    if not isinstance(query, str):
        raise TypeError("query must be a string.")
    if type(limit) is not int:
        raise TypeError("limit must be an integer.")
    if limit < 1:
        raise ValueError("limit must be at least 1.")
    if not query.strip():
        return []
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, filename, content
            FROM documents
            WHERE instr(lower(content), lower(?)) > 0
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (query.strip(), limit),
        ).fetchall()
    return [dict(row) for row in rows]


def delete_document(document_id: int) -> None:
    with get_connection() as connection:
        connection.execute(
            "DELETE FROM documents WHERE id = ?",
            (document_id,),
        )


if __name__ == "__main__":
    initialize_database()
    print("Database and table are ready!")
