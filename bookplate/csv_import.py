"""Imports a Goodreads or StoryGraph CSV export (lib/csvImport.ts). Columns are
found by name. Re-importing is safe: each row is matched to a book already in
the library — by the id an earlier import gave it, then ISBN, then title and
author — and updated in place, keeping its cover, colour and notes."""

import csv
import hashlib
import io
import random
import re
from dataclasses import dataclass, field

from sqlmodel import Session

from . import library
from .config import config
from .domain import PALETTE
from .models import iso_now
from .validate import is_iso_date


class CsvImportError(Exception):
    pass


@dataclass
class CsvImportSummary:
    source: str
    total: int = 0
    added: int = 0
    updated: int = 0
    read: int = 0
    reading: int = 0
    to_read: int = 0
    dnf: int = 0
    with_isbn: int = 0  # books a cover can be looked up for
    notes: int = 0  # reviews that become notes pages
    skipped: int = 0  # rows without a title or author
    cover_ids: list[str] = field(default_factory=list)


def summary_json(s: CsvImportSummary) -> dict:
    """The summary with the original's camelCase keys."""
    return {re.sub(r"_(\w)", lambda m: m[1].upper(), k): v for k, v in vars(s).items() if k != "cover_ids"}


def col(r: dict, *names: str) -> str:
    lower = {k.lower(): v for k, v in r.items() if k}
    return next((lower[n.lower()] for n in names if lower.get(n.lower())), "")


def clean_isbn(value: str) -> str | None:
    """Goodreads writes ISBNs as ="0123456789" so spreadsheets keep the zeros."""
    digits = re.sub(r"[^0-9Xx]", "", value).upper()
    return digits if len(digits) in (10, 13) else None


def clean_date(value: str) -> str | None:
    m = re.match(r"^(\d{4})[/-](\d{1,2})[/-](\d{1,2})", value)
    day = f"{m[1]}-{int(m[2]):02d}-{int(m[3]):02d}" if m else None
    return day if is_iso_date(day) else None


def clean_rating(value: str) -> float:
    """Bookplate rates in half stars; StoryGraph uses quarters."""
    try:
        n = float(value)
    except ValueError:
        return 0
    return min(5.0, max(0.5, round(n * 2) / 2)) if n > 0 else 0


def clean_title(value: str) -> str:
    """Goodreads appends the series to titles: "Dune (Dune, #1)" → "Dune"."""
    return re.sub(r"\s*\([^()]*#\s*[\d.]+[^()]*\)\s*$", "", value).strip()


def review_to_markdown(value: str) -> str:
    v = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    v = re.sub(r"</?(b|strong)>", "**", v, flags=re.I)
    v = re.sub(r"</?(i|em)>", "*", v, flags=re.I)
    v = re.sub(r"<[^>]+>", "", v)
    for entity, char in (
        ("&quot;", '"'),
        ("&#39;", "'"),
        ("&apos;", "'"),
        ("&lt;", "<"),
        ("&gt;", ">"),
        ("&amp;", "&"),
    ):
        v = v.replace(entity, char)
    return re.sub(r"\n{3,}", "\n\n", v).strip()


# Goodreads has no did-not-finish shelf, so readers make their own under names like these.
DNF_SHELF = re.compile(r"^(dnf|did-?n[o']?-?t-?finish|abandon|gave-?up|unfinished|not-?finished|stopped-?reading)")


def status_from(value: str) -> str:
    v = value.strip().lower()
    if v == "read":
        return "read"
    if v == "currently-reading":
        return "reading"
    return "dnf" if DNF_SHELF.match(v) else "to-read"


def format_from(value: str) -> str | None:
    v = value.lower()
    if "audio" in v:
        return "audiobook"
    return "kindle" if re.search(r"kindle|ebook|digital", v) else None


def hash_id(*parts: str) -> str:
    return hashlib.sha1("\0".join(parts).encode()).hexdigest()[:16]


def detect_source(headers: list[str]) -> str | None:
    has = {h.lower() for h in headers}.__contains__
    if has("exclusive shelf") and has("my rating"):
        return "goodreads"
    if has("read status") and (has("star rating") or has("authors")):
        return "storygraph"
    return None


def goodreads_row(r: dict) -> dict | None:
    title, author = clean_title(col(r, "Title")), " ".join(col(r, "Author").split())
    if not title or not author:
        return None
    isbn = clean_isbn(col(r, "ISBN13")) or clean_isbn(col(r, "ISBN"))
    gr_id = re.sub(r"\D", "", col(r, "Book Id"))
    pages = col(r, "Number of Pages")
    reviews = [review_to_markdown(x) for x in (col(r, "My Review"), col(r, "Private Notes")) if x]
    owned = col(r, "Owned Copies")
    return {
        "sourceId": f"gr-{gr_id}" if gr_id else f"gr-{hash_id(isbn or '', title, author)}",
        "title": title,
        "author": author,
        "isbn": isbn,
        "pages": int(pages) if pages.isdigit() and int(pages) > 0 else None,
        "status": status_from(col(r, "Exclusive Shelf")),
        "rating": clean_rating(col(r, "My Rating")),
        "dateRead": clean_date(col(r, "Date Read")),
        "addedAt": clean_date(col(r, "Date Added")),
        "format": format_from(col(r, "Binding")),
        "copy": True if owned.isdigit() and int(owned) > 0 else None,
        "review": "\n\n---\n\n".join(reviews) or None,
    }


def storygraph_row(r: dict) -> dict | None:
    title, author = clean_title(col(r, "Title")), " ".join(col(r, "Authors", "Author").split())
    if not title or not author:
        return None
    isbn = clean_isbn(col(r, "ISBN/UID", "ISBN"))
    dates = re.findall(r"\d{4}[/-]\d{1,2}[/-]\d{1,2}", col(r, "Dates Read"))
    review = col(r, "Review")
    return {
        "sourceId": f"sg-{hash_id(isbn or '', title.lower(), author.lower())}",
        "title": title,
        "author": author,
        "isbn": isbn,
        "pages": None,
        "status": status_from(col(r, "Read Status")),
        "rating": clean_rating(col(r, "Star Rating")),
        "dateRead": clean_date(col(r, "Last Date Read")) or (clean_date(dates[-1]) if dates else None),
        "addedAt": clean_date(col(r, "Date Added")),
        "format": format_from(col(r, "Format")),
        "copy": True if re.match(r"^y", col(r, "Owned?"), re.I) else None,
        "review": review_to_markdown(review) if review else None,
    }


def match_key(title: str, author: str) -> str:
    return re.sub(r"[^a-z0-9|]", "", f"{clean_title(title)}|{author}".lower())


def plan(db: Session, user_id: str, text: str) -> tuple[CsvImportSummary, list[dict], dict[str, str]]:
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    source = detect_source([h.strip() for h in reader.fieldnames or []])
    if not source:
        raise CsvImportError("This doesn't look like a Goodreads or StoryGraph export. No matching columns were found.")
    existing = [library.book_json(b) for b in library.list_books(db, user_id)]
    by_id = {b["id"]: b for b in existing}
    by_isbn = {b["isbn"]: b for b in existing if b.get("isbn")}
    by_key = {match_key(b["title"], b["author"]): b for b in existing}
    noted = library.noted_book_ids(db, user_id)
    to_row = goodreads_row if source == "goodreads" else storygraph_row

    summary, books, notes, seen = CsvImportSummary(source), [], {}, set()
    for record in reader:
        # A row with more fields than the header puts the extras under the key None, as a list.
        row = to_row({k.strip(): (v or "").strip() for k, v in record.items() if k is not None})
        if not row:
            summary.skipped += 1
            continue
        match = (
            by_id.get(row["sourceId"]) or by_isbn.get(row["isbn"]) or by_key.get(match_key(row["title"], row["author"]))
        )
        book_id = match["id"] if match else row["sourceId"]
        if book_id in seen:  # the same book twice in one file
            continue
        seen.add(book_id)
        m = match or {}
        # Reading details come from the export; looks (cover, colour, genre, source) stay as they are.
        book = m | {
            "id": book_id,
            "title": m.get("title", row["title"]),
            "author": m.get("author", row["author"]),
            "isbn": row["isbn"] or m.get("isbn"),
            "pages": row["pages"] or m.get("pages"),
            "status": row["status"],
            "rating": row["rating"] or m.get("rating", 0),
            "dateRead": row["dateRead"] or m.get("dateRead"),
            "format": m.get("format") or row["format"],
            "copy": row["copy"] if row["copy"] is not None else m.get("copy"),
            "colorIndex": m.get("colorIndex", random.randrange(len(PALETTE))),
            "addedAt": m.get("addedAt") or (f"{row['addedAt']}T00:00:00.000Z" if row["addedAt"] else iso_now()),
        }
        books.append(book)
        summary.total += 1
        summary.updated += bool(match)
        summary.added += not match
        status_attr = {"read": "read", "reading": "reading", "dnf": "dnf"}.get(book["status"], "to_read")
        setattr(summary, status_attr, getattr(summary, status_attr) + 1)
        summary.with_isbn += bool(book.get("isbn") and not book.get("coverImage"))
        if row["review"] and book_id not in noted:
            notes[book_id] = row["review"]
            summary.notes += 1
    return summary, books, notes


def apply_csv_import(db: Session, user_id: str, text: str) -> CsvImportSummary:
    summary, books, notes = plan(db, user_id, text)
    if config.limit_books and library.count_books(db, user_id) + summary.added > config.limit_books:
        raise CsvImportError(f"This import would go over the limit of {config.limit_books} books.")
    library.import_records(db, user_id, books, [], notes)
    summary.cover_ids = [b["id"] for b in books if not b.get("coverImage")]
    return summary
