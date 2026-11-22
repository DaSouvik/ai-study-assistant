
import sqlite3

def get_connection():
    connection = sqlite3.connect(
        "study_assistant.db"
    )
    connection.row_factory = sqlite3.Row
    return connection


def create_table():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


if __name__ == "__main__":
    create_table()
    print("Database and table are ready!")
