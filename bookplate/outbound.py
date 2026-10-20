"""The only outside services: Open Library and iTunes (search and covers) and
Wiktionary (word lookups), proxied so the browser stays same-origin
(lib/openLibrary.ts, lib/coverLookup.ts, app/api/define)."""

import html
import re
import threading
import time
import unicodedata
from urllib.parse import quote

import httpx

from .config import config
from .storage import detect_image_type

SEARCH_FIELDS = "key,title,author_name,number_of_pages_median,cover_i,first_publish_year"
_cache: dict[str, tuple[float, object]] = {}
_cache_lock = threading.Lock()
CACHE_MAX = 2000  # keys are typed searches and words, so the cache must not grow without end
DAY = 86400


def _get(url: str, timeout: float = 10) -> httpx.Response:
    return httpx.get(url, headers={"User-Agent": config.user_agent}, timeout=timeout, follow_redirects=True)


def _cached(key: str, fetch):
    hit = _cache.get(key)
    if hit and hit[0] > time.time():
        return hit[1]
    value = fetch()
    with _cache_lock:
        if len(_cache) >= CACHE_MAX:
            now = time.time()
            for k in [k for k, (expires, _) in _cache.items() if expires <= now]:
                del _cache[k]
            while len(_cache) >= CACHE_MAX:  # still full: drop the oldest entries
                del _cache[next(iter(_cache))]
        _cache[key] = (time.time() + DAY, value)
    return value


def work_id_from_key(key: str | None) -> str | None:
    m = re.match(r"^/works/(OL\d+W)$", key or "")
    return m[1] if m else None


def search_books(q: str) -> list[dict]:
    """Open Library catalogue search, shaped for the add-book form."""

    def fetch():
        res = _get(f"https://openlibrary.org/search.json?limit=8&fields={SEARCH_FIELDS}&q={quote(q)}")
        res.raise_for_status()
        return [
            {
                "title": d["title"],
                "author": (d.get("author_name") or [""])[0],
                "pages": d.get("number_of_pages_median"),
                "coverId": d.get("cover_i"),
                "year": d.get("first_publish_year"),
                "workId": work_id_from_key(d.get("key")),
            }
            for d in res.json().get("docs", [])
            if d.get("title")
        ]

    return _cached("search:" + q.lower(), fetch)


def _norm(v: str) -> str:
    v = unicodedata.normalize("NFKD", v.lower())
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", v).split())


def same_book(result: dict, title: str, author: str) -> bool:
    """The title (before any subtitle) and the author's surname must both match."""
    want = _norm(re.split(r"[:(]", title)[0])
    got = _norm(re.split(r"[:(]", result.get("trackName", ""))[0])
    surname = (_norm(author).split() or [""])[-1]
    if not (want and got and surname):
        return False
    return surname in _norm(result.get("artistName", "")) and (got.startswith(want) or want.startswith(got))


def _jpeg_or_none(res: httpx.Response, min_size: int = 1000) -> bytes | None:
    ok = res.is_success and len(res.content) > min_size and detect_image_type(res.content) == "image/jpeg"
    return res.content if ok else None


def find_cover(cover_id: int | None = None, isbn: str | None = None, title: str = "", author: str = "") -> bytes | None:
    """Open Library (by cover id or ISBN) first, then iTunes ebook artwork by title and author."""
    urls = []
    if cover_id:
        urls.append(f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg")
    if isbn:
        urls.append(f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg?default=false")
    for url in urls:
        try:
            if data := _jpeg_or_none(_get(url)):
                return data
        except httpx.HTTPError:
            pass  # unreachable or slow — try the fallback
    if not title:
        return None
    try:
        res = _get(f"https://itunes.apple.com/search?term={quote(f'{title} {author}'.strip())}&media=ebook&limit=5")
        match = next((r for r in res.json().get("results", []) if same_book(r, title, author)), None)
        if match and match.get("artworkUrl100"):
            return _jpeg_or_none(_get(re.sub(r"100x100bb\.jpg$", "600x0w.jpg", match["artworkUrl100"])))
    except (httpx.HTTPError, ValueError):
        pass
    return None


def strip_html(fragment: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]*>", "", fragment)).split())


def _usages(title: str) -> list[dict] | None:
    def fetch():
        res = _get("https://en.wiktionary.org/api/rest_v1/page/definition/" + quote(title, safe=""))
        if res.status_code == 404:
            return None
        res.raise_for_status()
        return res.json().get("en") or None

    return _cached("define:" + title, fetch)


def define(raw: str) -> dict | None:
    """English senses from Wiktionary, or None when the word has no entry."""
    word = raw.strip().lower()
    headword, usages = word, _usages(word)
    if not usages and raw.strip() != word:
        headword, usages = raw.strip(), _usages(raw.strip())
    if not usages:
        return None
    senses = []
    for u in usages:
        for d in u.get("definitions", []):
            example = ((d.get("parsedExamples") or [{}])[0].get("example")) or (d.get("examples") or [None])[0]
            if definition := strip_html(d.get("definition", "")):
                senses.append(
                    {
                        "partOfSpeech": (u.get("partOfSpeech") or "").lower(),
                        "definition": definition,
                        "example": strip_html(example) if example else None,
                    }
                )
    return {"word": headword, "phonetic": None, "senses": senses[:10]}
