"""Database engine and session management using SQLModel."""

import os
from pathlib import Path
from typing import Generator

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from backend.config import settings

# Ensure SQLite directory exists if using local file path
if settings.database_url.startswith("sqlite:///"):
    db_path_str = settings.database_url.replace("sqlite:///", "")
    db_path = Path(db_path_str)
    if not db_path.is_absolute():
        db_path = Path.cwd() / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

connect_args = {}
if "sqlite" in settings.database_url:
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.database_url,
    echo=False,
    connect_args=connect_args,
)


# Enable SQLite foreign key constraints
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection: object, connection_record: object) -> None:
    if "sqlite" in settings.database_url:
        cursor = getattr(dbapi_connection, "cursor", None)
        if callable(cursor):
            cur = cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()


def init_db() -> None:
    """Create all SQLModel tables in database."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """Dependency generator yielding an active database session."""
    with Session(engine) as session:
        yield session
