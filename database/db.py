from functools import lru_cache
from pathlib import Path

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    MetaData,
    Table,
    Text,
    create_engine,
    func,
    inspect,
    text,
)
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.pool import NullPool


DATABASE_PATH = Path(__file__).resolve().parents[1] / "study_assistant.db"
_configured_database_url: URL | None = None

_metadata = MetaData()
_documents = Table(
    "documents",
    _metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("owner_id", Text),
    Column("filename", Text, nullable=False),
    Column("content", Text, nullable=False, server_default=""),
    Column("summary", Text),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
    ),
)
_owner_created_index = Index(
    "ix_documents_owner_created",
    _documents.c.owner_id,
    _documents.c.created_at,
)


def configure_database(database_url: str | None) -> None:
    global _configured_database_url

    if database_url is None:
        _configured_database_url = None
        return
    if not isinstance(database_url, str) or not database_url.strip():
        raise ValueError("database_url must be a non-empty string.")

    url = make_url(database_url.strip())
    if url.drivername in {"postgres", "postgresql", "postgresql+psycopg"}:
        url = url.set(drivername="postgresql+psycopg")
        query = dict(url.query)
        query.setdefault("sslmode", "require")
        url = url.set(query=query)
    elif url.drivername not in {"sqlite", "sqlite+pysqlite"}:
        raise ValueError("Only Supabase PostgreSQL or SQLite URLs are supported.")

    _configured_database_url = url


@lru_cache(maxsize=8)
def _create_engine(database_url: str) -> Engine:
    url = make_url(database_url)
    connect_args: dict[str, object] = {}
    engine_options: dict[str, object] = {}
    if url.drivername.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        engine_options["poolclass"] = NullPool
    else:
        connect_args["connect_timeout"] = 10
        engine_options.update(
            pool_size=5,
            max_overflow=5,
            pool_recycle=300,
        )
    return create_engine(
        url,
        connect_args=connect_args,
        pool_pre_ping=True,
        **engine_options,
    )


def _get_engine() -> Engine:
    if _configured_database_url is None:
        database_url = URL.create("sqlite", database=str(DATABASE_PATH))
    else:
        database_url = _configured_database_url
    return _create_engine(str(database_url))


def _validate_owner_id(owner_id: str) -> str:
    if not isinstance(owner_id, str):
        raise TypeError("owner_id must be a string.")
    if not owner_id.strip() or len(owner_id) > 512:
        raise ValueError("owner_id must contain between 1 and 512 characters.")
    return owner_id


def initialize_database() -> None:
    engine = _get_engine()
    with engine.begin() as connection:
        if connection.dialect.name == "postgresql":
            connection.execute(
                text(
                    "SELECT pg_advisory_xact_lock("
                    "hashtext('study-desk-schema'))"
                )
            )
        _metadata.create_all(connection)
        columns = {
            column["name"]
            for column in inspect(connection).get_columns("documents")
        }
        if "content" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE documents "
                    "ADD COLUMN content TEXT NOT NULL DEFAULT ''"
                )
            )
        if "owner_id" not in columns:
            connection.execute(
                text("ALTER TABLE documents ADD COLUMN owner_id TEXT")
            )
        _owner_created_index.create(connection, checkfirst=True)


def save_document(
    filename: str,
    content: str,
    summary: str,
    *,
    owner_id: str,
) -> int:
    owner_id = _validate_owner_id(owner_id)
    with _get_engine().begin() as connection:
        result = connection.execute(
            _documents.insert()
            .values(
                owner_id=owner_id,
                filename=filename,
                content=content,
                summary=summary,
            )
            .returning(_documents.c.id)
        )
        return int(result.scalar_one())


def get_documents(*, owner_id: str) -> list[dict[str, object]]:
    owner_id = _validate_owner_id(owner_id)
    with _get_engine().begin() as connection:
        rows = connection.execute(
            text("""
                SELECT id, filename, summary, created_at,
                       length(content) AS char_count
                FROM documents
                WHERE owner_id = :owner_id
                ORDER BY created_at DESC, id DESC
            """),
            {"owner_id": owner_id},
        ).mappings().all()
    return [dict(row) for row in rows]


def get_document(
    document_id: int,
    *,
    owner_id: str,
) -> dict[str, object] | None:
    owner_id = _validate_owner_id(owner_id)
    with _get_engine().begin() as connection:
        row = connection.execute(
            text("""
                SELECT id, filename, summary, content, created_at
                FROM documents
                WHERE id = :document_id AND owner_id = :owner_id
            """),
            {"document_id": document_id, "owner_id": owner_id},
        ).mappings().one_or_none()
    return dict(row) if row is not None else None


def find_library_matches(
    query: str,
    *,
    owner_id: str,
    limit: int = 50,
) -> list[dict[str, object]]:
    owner_id = _validate_owner_id(owner_id)
    if not isinstance(query, str):
        raise TypeError("query must be a string.")
    if type(limit) is not int:
        raise TypeError("limit must be an integer.")
    if limit < 1:
        raise ValueError("limit must be at least 1.")
    if not query.strip():
        return []

    engine = _get_engine()
    search_expression = (
        "instr(lower(content), lower(:query)) > 0"
        if engine.dialect.name == "sqlite"
        else "strpos(lower(content), lower(:query)) > 0"
    )
    with engine.begin() as connection:
        rows = connection.execute(
            text(f"""
                SELECT id, filename, content
                FROM documents
                WHERE owner_id = :owner_id AND {search_expression}
                ORDER BY created_at DESC, id DESC
                LIMIT :limit
            """),
            {
                "owner_id": owner_id,
                "query": query.strip(),
                "limit": limit,
            },
        ).mappings().all()
    return [dict(row) for row in rows]


def delete_document(document_id: int, *, owner_id: str) -> None:
    owner_id = _validate_owner_id(owner_id)
    with _get_engine().begin() as connection:
        connection.execute(
            text("""
                DELETE FROM documents
                WHERE id = :document_id AND owner_id = :owner_id
            """),
            {"document_id": document_id, "owner_id": owner_id},
        )


if __name__ == "__main__":
    initialize_database()
    print("Database and table are ready!")
