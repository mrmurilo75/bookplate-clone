import io

from conftest import jpeg, reader
from PIL import Image
from pytest_bdd import given, parsers, scenarios, then, when
from sqlmodel import Session, select

from bookplate import storage
from bookplate.db import engine
from bookplate.models import Book, Note, ReadingProgress

scenarios("library.feature")


@given("registration is open")
def registration_open(open_registration):
    pass


@when(parsers.parse('they add "{title}" by "{author}" with status "{status}" and rating {rating}'))
def add(ctx, title, author, status, rating):
    ctx["response"] = reader(ctx).post(
        "/books", data={"title": title, "author": author, "status": status, "rating": rating, "date_read": "2024-05-01"}
    )


@when("they add a book without a title")
def add_untitled(ctx):
    ctx["response"] = reader(ctx).post("/books", data={"title": " ", "author": "Frank Herbert"})


@then(parsers.parse('"{first}" comes before "{second}"'))
def order(ctx, first, second):
    assert ctx["response"].text.index(first) < ctx["response"].text.index(second)


@when(parsers.parse('they change the genre of "{title}" to "{genre}"'))
def change_genre(ctx, title, genre):
    book_id = ctx["ids"][title]
    res = reader(ctx).post(
        f"/books/{book_id}/edit", data={"title": title, "author": "Frank Herbert", "status": "reading", "genre": genre}
    )
    assert res.status_code == 200


@when(parsers.parse('they upload a {w:d}x{h:d} cover for "{title}"'))
def upload_cover(ctx, w, h, title):
    res = reader(ctx).post(
        f"/books/{ctx['ids'][title]}/edit",
        data={"title": title, "author": "Frank Herbert", "status": "read"},
        files={"cover": ("c.jpg", jpeg(w, h), "image/jpeg")},
    )
    assert res.status_code == 200


@then(parsers.parse('the stored cover of "{title}" is a 600x900 JPEG'))
def stored_cover(ctx, title):
    book = reader(ctx).get("/api/books").json()["books"][0]
    assert book["coverImage"].startswith(f"/api/covers/{ctx['ids'][title]}.jpg?v=")
    res = reader(ctx).get(book["coverImage"])
    img = Image.open(io.BytesIO(res.content))
    assert (img.format, img.size) == ("JPEG", (600, 900))


@given(parsers.parse('"{title}" has notes, progress and a cover'))
def notes_progress_cover(ctx, title):
    book_id = ctx["ids"][title]
    client = reader(ctx)
    url = client.post(
        "/api/notes/images", data={"book": book_id}, files={"file": ("x.jpg", jpeg(50, 50), "image/jpeg")}
    ).json()["url"]
    client.put(f"/api/notes/{book_id}", json={"notes": f"Spice ![]({url})"})
    client.put(f"/api/progress/{book_id}", json={"date": "2024-01-01", "percent": 10})
    path = client.post(
        "/api/covers", data={"id": book_id}, files={"file": ("c.jpg", jpeg(60, 90), "image/jpeg")}
    ).json()["path"]
    book = client.get("/api/books").json()["books"][0]
    assert client.put(f"/api/books/{book_id}", json=book | {"coverImage": path}).status_code == 200


@when(parsers.parse('they delete "{title}"'))
def delete(ctx, title):
    reader(ctx).post(f"/books/{ctx['ids'][title]}/delete")


@then(parsers.parse('nothing of "{title}" is left'))
def nothing_left(ctx, title):
    book_id = ctx["ids"][title]
    with Session(engine) as db:
        for model in (Book, Note, ReadingProgress):
            id_col = model.id if model is Book else model.book_id
            assert not db.exec(select(model).where(id_col == book_id)).all()
    assert not any(p for p in storage.config.uploads_dir.rglob("*") if p.is_file())
