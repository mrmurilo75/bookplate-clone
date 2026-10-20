"""Database engine and sessions (lib/db). Migrations run with Alembic at startup."""

from collections.abc import Iterator
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import event
from sqlmodel import Session, create_engine

from .config import config

ROOT = Path(__file__).resolve().parent.parent


def make_engine(url: str):
    args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=args)
    if url.startswith("sqlite"):
        event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    return engine


engine = make_engine(config.database_url)


def migrate(url: str = config.database_url) -> None:
    """Applies every pending migration, like the original does on start."""
    cfg = AlembicConfig(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
