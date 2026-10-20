import httpx2
from conftest import jpeg
from pytest_bdd import given, parsers, scenarios, then, when

from bookplate import outbound

scenarios("outside_services.feature")

# The autouse fixture stubs these three for every other scenario; here the real ones run.
REAL = {name: getattr(outbound, name) for name in ("search_books", "define", "find_cover")}


def answer(monkeypatch, routes: dict):
    """Answers outbound GETs by URL prefix, like the services would."""

    def fake_get(url, timeout=10):
        for prefix, response in routes.items():
            if url.startswith(prefix):
                response.request = httpx2.Request("GET", url)
                return response
        return httpx2.Response(404)

    monkeypatch.setattr(outbound, "_get", fake_get)
    outbound._cache.clear()


@given(parsers.parse('Open Library answers a search with "{title}" by "{author}", work "{key}", cover {cover:d}'))
def ol_search(monkeypatch, title, author, key, cover):
    doc = {"key": key, "title": title, "author_name": [author], "cover_i": cover, "first_publish_year": 1965}
    answer(monkeypatch, {"https://openlibrary.org/search.json": httpx2.Response(200, json={"docs": [doc, {}]})})


@when(parsers.parse('the catalogue is searched for "{q}"'))
def search(ctx, q):
    ctx["result"] = REAL["search_books"](q)


@then(parsers.parse('the first result is "{title}" by "{author}" with work id "{work}" and cover {cover:d}'))
def first_result(ctx, title, author, work, cover):
    assert len(ctx["result"]) == 1  # the untitled doc is dropped
    r = ctx["result"][0]
    assert (r["title"], r["author"], r["workId"], r["coverId"], r["pages"]) == (title, author, work, cover, None)


@given(parsers.parse("Wiktionary answers \"{word}\" with the definition '{definition}'"))
def wiktionary(monkeypatch, word, definition):
    body = {"en": [{"partOfSpeech": "Noun", "definitions": [{"definition": definition, "examples": []}]}]}
    answer(
        monkeypatch, {f"https://en.wiktionary.org/api/rest_v1/page/definition/{word}": httpx2.Response(200, json=body)}
    )


@when(parsers.parse('the dictionary is asked for "{word}"'))
def ask(ctx, word):
    ctx["entry"] = REAL["define"](word)


@then(parsers.parse('the first sense is a "{pos}" meaning "{meaning}"'))
def first_sense(ctx, pos, meaning):
    assert ctx["entry"]["senses"][0] == {"partOfSpeech": pos, "definition": meaning, "example": None}


@given(parsers.parse('Open Library has no cover and iTunes lists "{a}" by "{author}" then "{b}" by "{author2}"'))
def itunes(monkeypatch, a, author, b, author2):
    results = [
        {"trackName": a, "artistName": author, "artworkUrl100": "https://art/a/100x100bb.jpg"},
        {"trackName": b, "artistName": author2, "artworkUrl100": "https://art/b/100x100bb.jpg"},
    ]
    answer(
        monkeypatch,
        {
            "https://itunes.apple.com/search": httpx2.Response(200, json={"results": results}),
            "https://art/b/600x0w.jpg": httpx2.Response(200, content=jpeg(600, 900, "blue")),
            "https://art/a/600x0w.jpg": httpx2.Response(200, content=jpeg(600, 900, "green")),
        },
    )


@when(parsers.parse('a cover is found for "{title}" by "{author}"'))
def find(ctx, title, author):
    ctx["cover"] = REAL["find_cover"](None, None, title, author)


@then(parsers.parse('the iTunes artwork for "{title}" is used'))
def used(ctx, title):
    assert ctx["cover"] == jpeg(600, 900, "blue")
