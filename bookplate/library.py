"""User-scoped data access (lib/library.ts). Every function takes the signed-in
user's id and only ever touches that user's rows and files. Books, words and
progress travel as camelCase dicts, the original's JSON/export format."""

import re

from sqlmodel import Session, col, delete, func, select

from . import storage
from .models import Book, Note, ReadingProgress, VocabEntry, now

COVER_NAME = re.compile(r"/api/covers/([^/?]+)")

BOOK_FIELDS = {  # JSON key → column
    "id": "id",
    "title": "title",
    "author": "author",
    "isbn": "isbn",
    "olWorkId": "ol_work_id",
    "genre": "genre",
    "pages": "pages",
    "format": "format",
    "status": "status",
    "copy": "has_copy",
    "rating": "rating",
    "dateRead": "date_read",
    "notes": "short_notes",
    "coverImage": "cover_image",
    "colorIndex": "color_index",
    "addedAt": "added_at",
}
VOCAB_FIELDS = {
    "id": "id",
    "word": "word",
    "phonetic": "phonetic",
    "partOfSpeech": "part_of_speech",
    "definition": "definition",
    "example": "example",
    "synonyms": "synonyms",
    "bookId": "book_id",
    "addedAt": "added_at",
}


def to_json(row, fields: dict[str, str]) -> dict:
    return {k: v for k, attr in fields.items() if (v := getattr(row, attr)) is not None}


def from_json(model, user_id: str, data: dict, fields: dict[str, str]):
    return model(user_id=user_id, **{attr: data[k] for k, attr in fields.items() if data.get(k) is not None})


def book_json(b: Book) -> dict:
    return to_json(b, BOOK_FIELDS)


def cover_file(cover_image: str | None) -> str | None:
    """The stored file a book's cover URL points at, when it is one of ours."""
    m = COVER_NAME.search(cover_image or "")
    return m[1] if m and storage.is_safe_file(m[1]) else None


def progress_json(p: ReadingProgress) -> dict:
    d = {"bookId": p.book_id, "date": p.date, "percent": p.percent}
    return d | ({"page": p.page} if p.page is not None else {})


# ── Books ──────────────────────────────────────────────────────────────────


def list_books(db: Session, user_id: str) -> list[Book]:
    return list(db.exec(select(Book).where(Book.user_id == user_id)))


def count_books(db: Session, user_id: str) -> int:
    return db.exec(select(func.count()).select_from(Book).where(Book.user_id == user_id)).one()


def get_book(db: Session, user_id: str, book_id: str) -> Book | None:
    return db.get(Book, (user_id, book_id))


def save_book(db: Session, book: Book) -> Book:
    """Creates or replaces one book."""
    db.merge(book)
    db.commit()
    return db.get(Book, (book.user_id, book.id))


def delete_book(db: Session, user_id: str, book_id: str) -> None:
    """Removes the book together with its notes, pasted images, progress and cover."""
    book = get_book(db, user_id, book_id)
    if book and (name := cover_file(book.cover_image)):
        storage.delete(storage.cover_key(user_id, name))
    if book:
        db.delete(book)
    db.exec(delete(ReadingProgress).where(ReadingProgress.user_id == user_id, ReadingProgress.book_id == book_id))
    db.commit()
    delete_notes(db, user_id, book_id)


# ── Notes ──────────────────────────────────────────────────────────────────


def read_notes(db: Session, user_id: str, book_id: str) -> str | None:
    note = db.get(Note, (user_id, book_id))
    return note.markdown if note else None


def write_notes(db: Session, user_id: str, book_id: str, markdown: str) -> None:
    """Saves the notes and removes stored images the text no longer references."""
    if markdown.strip():
        db.merge(Note(user_id=user_id, book_id=book_id, markdown=markdown, updated_at=now()))
    elif note := db.get(Note, (user_id, book_id)):
        db.delete(note)
    db.commit()
    for key in storage.list_dir(storage.notes_dir(user_id, book_id)):
        if f"/api/notes/images/{book_id}/{key.rsplit('/', 1)[1]}" not in markdown:
            storage.delete(key)


def all_notes(db: Session, user_id: str) -> dict[str, str]:
    """Every book's notes, by book id, in one query."""
    return {n.book_id: n.markdown for n in db.exec(select(Note).where(Note.user_id == user_id))}


def noted_book_ids(db: Session, user_id: str) -> set[str]:
    return set(db.exec(select(Note.book_id).where(Note.user_id == user_id)))


def delete_notes(db: Session, user_id: str, book_id: str) -> None:
    if note := db.get(Note, (user_id, book_id)):
        db.delete(note)
        db.commit()
    storage.delete_prefix(storage.notes_dir(user_id, book_id))


# ── Reading progress ───────────────────────────────────────────────────────


def list_progress(db: Session, user_id: str) -> list[ReadingProgress]:
    q = select(ReadingProgress).where(ReadingProgress.user_id == user_id).order_by(col(ReadingProgress.date))
    return list(db.exec(q))


def save_progress(db: Session, user_id: str, book_id: str, day: str, percent: float, page: int | None) -> None:
    """Saves a day's progress, replacing any earlier update from the same day."""
    db.merge(ReadingProgress(user_id=user_id, book_id=book_id, date=day, percent=percent, page=page))
    db.commit()


def delete_progress(db: Session, user_id: str, book_id: str, day: str) -> None:
    if entry := db.get(ReadingProgress, (user_id, book_id, day)):
        db.delete(entry)
        db.commit()


# ── Vocabulary ─────────────────────────────────────────────────────────────


def list_vocabulary(db: Session, user_id: str) -> list[VocabEntry]:
    return list(db.exec(select(VocabEntry).where(VocabEntry.user_id == user_id)))


def count_words(db: Session, user_id: str) -> int:
    return db.exec(select(func.count()).select_from(VocabEntry).where(VocabEntry.user_id == user_id)).one()


def save_vocab(db: Session, entry: VocabEntry) -> None:
    db.merge(entry)
    db.commit()


def delete_vocab(db: Session, user_id: str, word_id: str) -> None:
    if entry := db.get(VocabEntry, (user_id, word_id)):
        db.delete(entry)
        db.commit()


# ── Bulk (import) ──────────────────────────────────────────────────────────


def import_records(
    db: Session,
    user_id: str,
    books: list[dict],
    words: list[dict],
    notes: dict[str, str],
    progress: list[dict] | None = None,
) -> None:
    """Writes a whole library in one transaction; records with the same ids are overwritten."""
    for b in books:
        db.merge(from_json(Book, user_id, b, BOOK_FIELDS))
    for w in words:
        db.merge(from_json(VocabEntry, user_id, w, VOCAB_FIELDS))
    for p in progress or []:
        db.merge(
            ReadingProgress(
                user_id=user_id, book_id=p["bookId"], date=p["date"], percent=p["percent"], page=p.get("page")
            )
        )
    for book_id, markdown in notes.items():
        db.merge(Note(user_id=user_id, book_id=book_id, markdown=markdown, updated_at=now()))
    db.commit()
