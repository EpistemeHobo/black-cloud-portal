from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app import config


class Base(DeclarativeBase):
    pass


def make_engine(url: str):
    is_sqlite = url.startswith("sqlite")
    if is_sqlite and ":memory:" not in url:
        config.INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False} if is_sqlite else {},
        # A server database drops idle connections (Aurora Serverless pauses, fails
        # over); test each one before use and renew them every half hour.
        **({} if is_sqlite else {"pool_pre_ping": True, "pool_recycle": 1800}),
    )
    if is_sqlite:
        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):
            cursor = dbapi_conn.cursor()
            # SQLite ignores foreign keys unless asked, per connection.
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()
    return engine


# Any fixed number, the same in every container.
_STARTUP_LOCK_ID = 72015301


@contextmanager
def startup_lock(connection):
    """Hold a PostgreSQL advisory lock, so when several containers start at once
    (Beanstalk with more than one instance) only one migrates or seeds at a time.
    SQLite has a single server, so nothing to do."""
    if connection.dialect.name != "postgresql":
        yield
        return
    connection.exec_driver_sql(f"SELECT pg_advisory_lock({_STARTUP_LOCK_ID})")
    connection.commit()  # the lock belongs to the session, not the transaction
    try:
        yield
    finally:
        connection.exec_driver_sql(f"SELECT pg_advisory_unlock({_STARTUP_LOCK_ID})")
        connection.commit()


engine = make_engine(config.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
