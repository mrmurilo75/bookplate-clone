"""Showcases: a reader's public page for one year of reading, at /s/<id>
(lib/showcase.ts, lib/showcaseYear.ts). One per account and year; saving the
same year again keeps its address. Only the reader's choices are stored, so the
page always shows the library as it is now."""

import calendar
import re
import secrets
from dataclasses import dataclass, field
from datetime import date

from sqlmodel import Session, select

from . import library
from .domain import summarize, today_iso
from .models import Book, Showcase

NAME_MAX = 40
FIRST_YEAR = 1900
INCLUDES = ("both", "read", "reading")
MONTHS = list(calendar.month_abbr)[1:]
COVER = re.compile(r"^/api/covers/([^/?]+)(\?.*)?$")


class ShowcaseError(Exception):
    pass


def new_id() -> str:
    """16 characters of base64url: 96 random bits, so addresses can't be guessed."""
    return secrets.token_urlsafe(12)


def is_showcase_id(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{16}", value))


def possessive(name: str) -> str:
    return f"{name}’" if name.endswith("s") else f"{name}’s"


def includes_reading(include: str, year: int, this_year: int) -> bool:
    """Books being read have no year: they belong only to the current one."""
    return include != "read" and year == this_year


def parse_showcase(year: int, include: str, name: str, this_year: int) -> tuple[int, str, str | None]:
    if not FIRST_YEAR <= year <= this_year:
        raise ShowcaseError("Choose a year up to this one.")
    if include not in INCLUDES:
        raise ShowcaseError("Choose which books to show.")
    if include == "reading" and year != this_year:
        raise ShowcaseError("Books you're reading can only go in this year's showcase.")
    name = " ".join("".join(c for c in name if c.isprintable()).split())
    if len(name) > NAME_MAX:
        raise ShowcaseError(f"Keep the name to {NAME_MAX} characters.")
    # "Both" for a past year is just "read": there's nothing being read then.
    return year, "read" if include == "both" and year != this_year else include, name or None


def list_showcases(db: Session, user_id: str) -> list[Showcase]:
    return list(db.exec(select(Showcase).where(Showcase.user_id == user_id).order_by(Showcase.year)))


def save_showcase(db: Session, user_id: str, year: int, include: str, name: str | None) -> Showcase:
    s = db.exec(select(Showcase).where(Showcase.user_id == user_id, Showcase.year == year)).first()
    s = s or Showcase(id=new_id(), user_id=user_id, year=year, include=include)
    s.include, s.name = include, name
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def delete_showcase(db: Session, user_id: str, showcase_id: str) -> None:
    s = db.get(Showcase, showcase_id)
    if s and s.user_id == user_id:
        db.delete(s)
        db.commit()


@dataclass
class ShowcaseYear:
    year: int
    read: list[Book]
    months: list[list[Book]]
    reading: list[tuple[Book, int | None]]
    favourites: list[Book]
    stats: dict = field(default_factory=dict)


def public_book(b: Book, showcase_id: str) -> Book:
    """Only what a showcase shows: never notes, sources or ownership."""
    cover = None
    if b.cover_image and (m := COVER.match(b.cover_image)):
        cover = f"/s/{showcase_id}/covers/{m[1]}{m[2] or ''}"
    return Book(
        user_id="",
        id=b.id,
        title=b.title,
        author=b.author,
        genre=b.genre,
        pages=b.pages,
        status=b.status,
        rating=b.rating,
        date_read=b.date_read,
        color_index=b.color_index,
        added_at=b.added_at,
        cover_image=cover,
    )


def build_year(books: list[Book], progress, year: int, include: str, today: str) -> ShowcaseYear:
    this_year = int(today[:4])
    read = sorted(
        (
            b
            for b in books
            if include != "reading" and b.status == "read" and (b.date_read or "").startswith(f"{year}-")
        ),
        key=lambda b: (b.date_read, b.title),
    )
    reading = []
    if includes_reading(include, year, this_year):
        pairs = [
            (b, s.percent if (s := summarize(b, progress, today)) else None) for b in books if b.status == "reading"
        ]
        reading = sorted(pairs, key=lambda p: (-(p[1] if p[1] is not None else -1), p[0].title))
    months: list[list[Book]] = [[] for _ in MONTHS]
    for b in read:
        months[int(b.date_read[5:7]) - 1].append(b)
    paged = [b for b in read if b.pages]
    pages = sum(b.pages for b in paged)
    days = date.fromisoformat(today).timetuple().tm_yday if year == this_year else 366 if calendar.isleap(year) else 365
    rated = [b for b in read if b.rating > 0]
    longest = max(paged, key=lambda b: b.pages, default=None)
    return ShowcaseYear(
        year=year,
        read=read,
        months=months,
        reading=reading,
        favourites=[b for b in read if b.rating == 5],
        stats={
            "books": len(read),
            "pages": pages,
            "pages_per_day": round(pages / days) if pages else None,
            "rating": round(sum(b.rating for b in rated) / len(rated), 1) if rated else None,
            "longest": longest,
        },
    )


def load_showcase(db: Session, showcase_id: str) -> tuple[Showcase, ShowcaseYear] | None:
    if not is_showcase_id(showcase_id) or not (s := db.get(Showcase, showcase_id)):
        return None
    books = [public_book(b, s.id) for b in library.list_books(db, s.user_id)]
    view = build_year(books, library.list_progress(db, s.user_id), s.year, s.include, today_iso())
    return s, view


def cover_file_of(view: ShowcaseYear, file: str) -> bool:
    """The stored cover a showcase may serve: one belonging to a book it shows."""
    shown = view.read + [b for b, _ in view.reading]
    return any((b.cover_image or "").split("?")[0].endswith(f"/covers/{file}") for b in shown)
