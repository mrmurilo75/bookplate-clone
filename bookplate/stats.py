"""The Statistics page's numbers and drill-downs (components/StatsView.tsx)."""

from collections import Counter
from datetime import date

from .domain import FORMAT_LABELS, average_rating, rated_reads, source_label, summarize
from .models import Book, ReadingProgress

RATING_STEPS = [5, 4.5, 4, 3.5, 3, 2.5, 2, 1.5, 1, 0.5]


def genre_of(b: Book) -> str:
    return (b.genre or "").strip() or "Unspecified"


def year_counts(books: list[Book]) -> list[dict]:
    """Books finished per year, with empty years filled in up to this one."""
    counts = Counter(int(b.date_read[:4]) for b in books if b.status == "read" and b.date_read)
    if not counts:
        return []
    return [{"year": y, "count": counts[y]} for y in range(min(counts), max(*counts, date.today().year) + 1)]


def all_genres(books: list[Book]) -> list[dict]:
    return [{"label": g, "count": n} for g, n in Counter(map(genre_of, books)).most_common()]


def overview(books: list[Book], progress: list[ReadingProgress]) -> dict:
    read = [b for b in books if b.status == "read"]
    this_year = date.today().year
    rated = rated_reads(books)
    genres = all_genres(books)
    top = genres[:6]
    if rest := sum(g["count"] for g in genres[6:]):
        top.append({"label": "Other", "count": rest})
    by_source = Counter(b.format for b in books if b.format)
    sources = sorted(
        [{"source": f, "label": source_label(f), "count": by_source.get(f, 0)} for f in FORMAT_LABELS]
        + [{"source": f, "label": f, "count": n} for f, n in by_source.items() if f not in FORMAT_LABELS],
        key=lambda s: -s["count"],
    )
    if unsourced := sum(1 for b in books if not b.format):
        sources.append({"source": "", "label": "Unspecified", "count": unsourced})

    reading = sorted(
        ({"book": b, "summary": summarize(b, progress)} for b in books if b.status == "reading"),
        key=lambda r: -(r["summary"].percent if r["summary"] else -1),
    )
    tracked = [s.read_in_days for b in read if (s := summarize(b, progress)) and s.read_in_days is not None]
    return {
        "read": len(read),
        "read_this_year": sum(1 for b in read if (b.date_read or "").startswith(str(this_year))),
        "this_year": this_year,
        "pages": sum(b.pages or 0 for b in read),
        "avg": average_rating(books),
        "years": year_counts(books),
        "ratings": [
            {"rating": n, "label": f"{n:g} ★", "count": sum(1 for b in rated if b.rating == n)} for n in RATING_STEPS
        ],
        "genres": top,
        "sources": sources,
        "reading": reading,
        "avg_days": round(sum(tracked) / len(tracked)) if tracked else None,
        "tracked": len(tracked),
    }


def _best_first(books: list[Book]) -> list[Book]:
    return sorted(books, key=lambda b: (-b.rating, b.title.lower()))


def drill(books: list[Book], kind: str, value: str) -> dict | None:
    """One drill-down: a year, genre, rating or source, or all genres."""
    if kind == "year" and value.isdigit():
        items = sorted(
            (b for b in books if b.status == "read" and (b.date_read or "").startswith(value)),
            key=lambda b: b.date_read or "",
        )
        rated = [b for b in items if b.rating > 0]
        top = max((b.rating for b in items), default=0)
        best = [b for b in items if top and b.rating == top]
        return {
            "title": f"Read in {value}",
            "sub": f"{len(items)} books · {sum(b.pages or 0 for b in items):,} pages · average "
            + (f"{sum(b.rating for b in rated) / len(rated):.1f} ★" if rated else "—"),
            "sections": ([(f"Highest rated ({top:g} ★)", best)] if best and len(best) < len(items) else [])
            + [("In reading order", items)],
        }
    if kind == "genres":
        return {"title": "All genres", "sub": "", "genres": all_genres(books), "sections": []}
    if kind == "genre":
        items = _best_first([b for b in books if genre_of(b) == value])
        return {"title": value, "sub": f"{len(items)} books, best first", "sections": [("", items)]}
    if kind == "source":
        items = _best_first([b for b in books if (b.format or "") == value])
        title = source_label(value) if value else "Unspecified source"
        return {"title": title, "sub": f"{len(items)} books, best first", "sections": [("", items)]}
    if kind == "rating":
        try:
            n = float(value)
        except ValueError:
            return None
        items = sorted((b for b in rated_reads(books) if b.rating == n), key=lambda b: b.title.lower())
        return {"title": f"Rated {n:g} ★", "sub": f"{len(items)} books", "sections": [("", items)]}
    return None
