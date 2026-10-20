"""Pure library rules shared by pages, API and tests (lib/types.ts, palette.ts,
ratings.ts, progress.ts)."""

import math
from dataclasses import dataclass
from datetime import date

from .models import Book, ReadingProgress

STATUS_LABELS = {"read": "Read", "reading": "Reading", "to-read": "TBR", "dnf": "Didn’t finish"}

# Built-in places a book can come from, kept under the `format` key for data compatibility.
FORMAT_LABELS = {
    "bookstore": "Book store",
    "kindle": "Kindle",
    "audiobook": "Audiobook",
    "borrowed": "Borrowed",
    "secondhand": "Second hand",
    "gifted": "Gifted",
    "library": "Library",
}

# Optional per-reader features (lib/featureList.ts); off by default, switching off only hides.
FEATURES = {
    "source": "Where each book came from (a book store, Kindle, the library…), with a chart on Statistics.",
    "copy": "Whether you own a physical copy, with a column in the Ledger.",
}

# Generated-cover binding colours: (name, bg, deep, ink). Books store an index,
# so only ever append — reordering would recolour existing books.
PALETTE = [
    ("Vermilion", "#ff3b1f", "#e02d13", "#ffffff"),
    ("Kelly", "#00994d", "#00713a", "#ffffff"),
    ("Klein Blue", "#1a34d6", "#1226a8", "#ffffff"),
    ("Signal Yellow", "#ffd400", "#e8bf00", "#111111"),
    ("Hot Pink", "#ff5fa2", "#e23d84", "#111111"),
    ("Steel", "#5b6670", "#414a52", "#ffffff"),
    ("Orange", "#ff8a00", "#d97200", "#111111"),
    ("Cyan", "#00b6d8", "#008fab", "#111111"),
    ("Purple", "#6a2ecf", "#4d1fa1", "#ffffff"),
    ("Grey", "#b8b4aa", "#9a968c", "#111111"),
    ("Paper", "#f4f2ec", "#e0dcd2", "#111111"),
    ("Ink", "#111111", "#000000", "#ffffff"),
]


def palette_for(color_index: int) -> tuple[str, str, str, str]:
    return PALETTE[color_index % len(PALETTE)]


def date_label(status: str) -> str:
    return "Stopped" if status == "dnf" else "Finished"


def source_label(fmt: str | None) -> str | None:
    return FORMAT_LABELS.get(fmt, fmt) if fmt else None


def normalise_source(typed: str) -> str:
    """Typing "kindle" or "Book store" gives the built-in rather than a look-alike."""
    t = typed.strip()
    for key, label in FORMAT_LABELS.items():
        if t.lower() in (key, label.lower()):
            return key
    return t


# ── Ratings: only books read to the end count ──────────────────────────────


def rated_reads(books: list[Book]) -> list[Book]:
    return [b for b in books if b.status == "read" and b.rating > 0]


def average_rating(books: list[Book]) -> float | None:
    rated = rated_reads(books)
    return sum(b.rating for b in rated) / len(rated) if rated else None


# ── Reading progress ───────────────────────────────────────────────────────


def today_iso() -> str:
    return date.today().isoformat()


def days_between(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def entry_percent(book: Book, e: ReadingProgress) -> float:
    """Recomputed from the page when possible, so a corrected page count shows straight away."""
    raw = e.page / book.pages * 100 if book.pages and e.page is not None else e.percent
    return max(0.0, min(100.0, raw))


@dataclass
class ProgressSummary:
    entries: list[ReadingProgress]
    unit: str  # "page" | "percent"
    percent: int
    page: int | None
    started: str
    days_reading: int
    per_day: float | None
    days_left: int | None
    read_in_days: int | None


def summarize(book: Book, progress: list[ReadingProgress], today: str | None = None) -> ProgressSummary | None:
    entries = sorted((e for e in progress if e.book_id == book.id), key=lambda e: e.date)
    if not entries:
        return None
    today = today or today_iso()
    unit = "page" if book.pages else "percent"
    first, last = entries[0], entries[-1]

    def value(e: ReadingProgress) -> float:
        if unit == "percent":
            return e.percent
        return e.page if e.page is not None else e.percent / 100 * book.pages

    per_day = days_left = None
    span = days_between(first.date, last.date)
    if span > 0 and (gained := value(last) - value(first)) > 0:
        per_day = gained / span
        remaining = (book.pages if unit == "page" else 100) - value(last)
        days_left = math.ceil(remaining / per_day) if remaining > 0 else 0
    read_in = (
        max(1, days_between(first.date, book.date_read))
        if book.status == "read" and book.date_read and book.date_read >= first.date
        else None
    )
    return ProgressSummary(
        entries=entries,
        unit=unit,
        percent=round(entry_percent(book, last)),
        page=(last.page if last.page is not None else round(value(last))) if unit == "page" else None,
        started=first.date,
        days_reading=max(0, days_between(first.date, today)),
        per_day=per_day,
        days_left=days_left,
        read_in_days=read_in,
    )
