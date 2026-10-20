"""Tables (lib/db/schema.ts). Every library row belongs to a user; book and word
ids come from the client or an import, so they are only unique per user."""

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, Column, ForeignKey, String, UniqueConstraint
from sqlmodel import Field, SQLModel


def now() -> datetime:
    return datetime.now(UTC)


def iso_now() -> str:
    return now().isoformat(timespec="milliseconds").replace("+00:00", "Z")


def user_fk(primary_key: bool = False) -> Column:
    return Column(String, ForeignKey("user.id", ondelete="CASCADE"), primary_key=primary_key, nullable=False)


class User(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    email: str = Field(unique=True, index=True)
    password_hash: str
    features: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=now)
    last_seen_at: datetime = Field(default_factory=now)


class Session(SQLModel, table=True):
    token: str = Field(primary_key=True)
    user_id: str = Field(sa_column=user_fk())
    expires_at: datetime


class Book(SQLModel, table=True):
    user_id: str = Field(sa_column=user_fk(primary_key=True))
    id: str = Field(primary_key=True)
    title: str
    author: str
    isbn: str | None = None
    ol_work_id: str | None = None
    genre: str | None = None
    pages: int | None = None
    format: str | None = None  # the book's source: a FORMAT_LABELS key or the reader's own text
    status: str = "to-read"
    has_copy: bool | None = Field(default=None, sa_column=Column("copy", Boolean))  # physical copy at home
    rating: float = 0
    date_read: str | None = None  # ISO yyyy-mm-dd: finished, or for "dnf" when stopped
    short_notes: str | None = None
    cover_image: str | None = None  # /api/covers/<file>?v=…; None = generated cover
    color_index: int = 0
    added_at: str = Field(default_factory=iso_now)


class Note(SQLModel, table=True):
    user_id: str = Field(sa_column=user_fk(primary_key=True))
    book_id: str = Field(primary_key=True)
    markdown: str
    updated_at: datetime = Field(default_factory=now)


class ReadingProgress(SQLModel, table=True):
    """One entry per book per day; a second update the same day replaces it."""

    __tablename__ = "reading_progress"
    user_id: str = Field(sa_column=user_fk(primary_key=True))
    book_id: str = Field(primary_key=True)
    date: str = Field(primary_key=True)
    page: int | None = None
    percent: float


class VocabEntry(SQLModel, table=True):
    __tablename__ = "vocab_entry"
    user_id: str = Field(sa_column=user_fk(primary_key=True))
    id: str = Field(primary_key=True)
    word: str
    phonetic: str | None = None
    part_of_speech: str | None = None
    definition: str
    example: str | None = None
    synonyms: list[str] | None = Field(default=None, sa_column=Column(JSON))
    book_id: str | None = None
    added_at: str = Field(default_factory=iso_now)


class Showcase(SQLModel, table=True):
    """A public page of one year's reading at /s/<id>; only the reader's choices are stored."""

    __table_args__ = (UniqueConstraint("user_id", "year", name="showcase_user_year_idx"),)
    id: str = Field(primary_key=True)
    user_id: str = Field(sa_column=user_fk())
    year: int
    include: str  # "read" | "reading" | "both"
    name: str | None = None
    created_at: datetime = Field(default_factory=now)
