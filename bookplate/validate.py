"""Shape checks for books, words and progress arriving as JSON (lib/validate.ts)."""

import re

ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
WORK_ID_RE = re.compile(r"^OL\d+W$")
STATUSES = ("read", "reading", "to-read", "dnf")


def _optional(o: dict, key: str, *types: type) -> bool:
    v = o.get(key)
    return v is None or (isinstance(v, types) and not (bool not in types and isinstance(v, bool)))


def is_valid_book(b: object) -> bool:
    return (
        isinstance(b, dict)
        and isinstance(b.get("id"), str)
        and bool(ID_RE.match(b["id"]))
        and isinstance(b.get("title"), str)
        and isinstance(b.get("author"), str)
        and (b.get("status") is None or b["status"] in STATUSES)
        and all(_optional(b, k, int, float) for k in ("rating", "colorIndex", "pages"))
        and all(_optional(b, k, str) for k in ("genre", "isbn", "format", "dateRead", "notes", "coverImage", "addedAt"))
        and _optional(b, "copy", bool)
        and (b.get("olWorkId") is None or bool(WORK_ID_RE.match(str(b["olWorkId"]))))
    )


def is_valid_progress(p: object) -> bool:
    return (
        isinstance(p, dict)
        and isinstance(p.get("bookId"), str)
        and bool(ID_RE.match(p["bookId"]))
        and isinstance(p.get("date"), str)
        and bool(DATE_RE.match(p["date"]))
        and isinstance(p.get("percent"), int | float)
        and 0 <= p["percent"] <= 100
        and (p.get("page") is None or (isinstance(p["page"], int) and p["page"] >= 0))
    )


def is_valid_vocab(w: object) -> bool:
    return (
        isinstance(w, dict)
        and isinstance(w.get("id"), str)
        and bool(ID_RE.match(w["id"]))
        and isinstance(w.get("word"), str)
        and isinstance(w.get("definition"), str)
        and all(_optional(w, k, str) for k in ("phonetic", "partOfSpeech", "example", "bookId", "addedAt"))
        and (
            w.get("synonyms") is None
            or (isinstance(w["synonyms"], list) and all(isinstance(s, str) for s in w["synonyms"]))
        )
    )
