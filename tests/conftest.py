"""Shared fixtures and steps. Every scenario runs the real app (migrations
included) against a fresh SQLite database and uploads folder."""

import dataclasses
import io
import os
import re
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="bookplate-tests-"))
# TEST_DATABASE_URL runs the suite against e.g. Postgres; SQLite by default.
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{_tmp / 'test.db'}"
os.environ["UPLOADS_DIR"] = str(_tmp / "uploads")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402
from pytest_bdd import given, parsers, then, when  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402

from bookplate import auth, config, outbound, storage  # noqa: E402
from bookplate.db import engine  # noqa: E402
from bookplate.main import app  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    with TestClient(app):  # runs the migrations once the database exists
        pass
    with engine.begin() as conn:
        for table in reversed(SQLModel.metadata.sorted_tables):
            conn.execute(table.delete())
    storage.delete_prefix("")
    # No outside services in tests.
    monkeypatch.setattr(outbound, "search_books", lambda q: [])
    monkeypatch.setattr(outbound, "find_cover", lambda *a, **k: None)
    monkeypatch.setattr(outbound, "define", lambda w: None)


@pytest.fixture
def open_registration(monkeypatch):
    monkeypatch.setattr(auth, "config", dataclasses.replace(config.config, registration_open=True))


@pytest.fixture
def ctx():
    """What a scenario remembers between steps: readers (one client each), the last response, ids."""
    return {"readers": {}, "ids": {}}


def jpeg(width: int, height: int, color="red") -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (width, height), color).save(out, "JPEG")
    return out.getvalue()


def reader(ctx) -> TestClient:
    return ctx["readers"][ctx["current"]]


def new_client() -> TestClient:
    return TestClient(app, follow_redirects=True)


def sign_up(ctx, name: str) -> None:
    client = new_client()
    res = client.post("/signup", data={"name": name, "email": f"{name.lower()}@example.com", "password": "password123"})
    assert res.status_code == 200, res.text
    ctx["readers"][name] = client
    ctx["current"] = name


def add_book(ctx, **fields) -> str:
    data = {"title": "Untitled", "author": "Anon", "status": "to-read", "rating": "0"} | fields
    res = reader(ctx).post("/books", data=data)
    assert res.status_code == 200, res.text
    book_id = str(res.url).rsplit("/", 1)[1]
    ctx["ids"][data["title"]] = book_id
    return book_id


# ── Shared steps ───────────────────────────────────────────────────────────


@given(parsers.parse('"{name}" has an account'))
@given(parsers.parse('"{name}" has signed up'))
def given_account(ctx, name):
    sign_up(ctx, name)


@given(parsers.parse('"{name}" is signed in'))
def given_signed_in(ctx, name):
    ctx["current"] = name


@given(parsers.parse('the library has "{title}" by "{author}" with status "{status}"'))
def given_book(ctx, title, author, status):
    add_book(ctx, title=title, author=author, status=status)


@given(parsers.parse('the library has "{title}" by "{author}", {pages:d} pages, read on {day} rated {rating}'))
def given_read_book(ctx, title, author, pages, day, rating):
    add_book(ctx, title=title, author=author, status="read", pages=str(pages), date_read=day, rating=rating)


@when(parsers.parse('they open "{path}"'))
def open_path(ctx, path):
    for title, book_id in ctx["ids"].items():
        path = path.replace(f"<{title}>", book_id)
    ctx["response"] = reader(ctx).get(path)


@when(parsers.parse('they open the page of "{title}"'))
def open_book(ctx, title):
    ctx["response"] = reader(ctx).get(f"/books/{ctx['ids'][title]}")


@then(parsers.parse("the response status is {status:d}"))
def response_status(ctx, status):
    assert ctx["response"].status_code == status, ctx["response"].text[:500]


@then(parsers.parse('the page shows "{text}"'))
def page_shows(ctx, text):
    assert text in ctx["response"].text


@then(parsers.parse('the page does not show "{text}"'))
def page_hides(ctx, text):
    assert text not in ctx["response"].text


@then(parsers.parse('they end up on "{path}"'))
def ends_up_on(ctx, path):
    assert re.sub(r"\?.*", "", ctx["response"].url.path) == path
