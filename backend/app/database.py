from datetime import datetime, timezone

from sqlalchemy import DateTime, create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.types import TypeDecorator

from app.config import DATA_DIR, DATABASE_URL

IS_SQLITE = DATABASE_URL.startswith("sqlite")

if IS_SQLITE:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    DATABASE_URL,
    # The job worker writes from the event loop while request handlers write from the threadpool.
    connect_args={"check_same_thread": False, "timeout": 30} if IS_SQLITE else {},
)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _):
    if IS_SQLITE:
        dbapi_conn.execute("PRAGMA foreign_keys=ON")
        dbapi_conn.execute("PRAGMA journal_mode=WAL")


class UTCDateTime(TypeDecorator):
    """Stores naive UTC, always returns aware UTC (SQLite drops tzinfo otherwise)."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect):
        return value.replace(tzinfo=timezone.utc) if value is not None else None


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
