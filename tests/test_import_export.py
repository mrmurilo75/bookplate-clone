from conftest import FIXTURES, jpeg, reader, sign_up
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("import_export.feature")


@given("registration is open")
def registration_open(open_registration):
    pass


@given(parsers.parse('"{title}" has notes with an image, progress, a cover and a word'))
def everything(ctx, title):
    client, book_id = reader(ctx), ctx["ids"][title]
    url = client.post(
        "/api/notes/images", data={"book": book_id}, files={"file": ("p.jpg", jpeg(40, 40), "image/jpeg")}
    ).json()["url"]
    client.post(f"/books/{book_id}/notes", data={"markdown": f"Spice ![]({url})"})
    client.post(f"/books/{book_id}/progress", data={"value": 300, "date": "2024-03-01"})
    client.post(
        f"/books/{book_id}/edit",
        data={
            "title": title,
            "author": "Frank Herbert",
            "status": "read",
            "pages": "600",
            "date_read": "2024-03-10",
            "rating": "5",
        },
        files={"cover": ("c.jpg", jpeg(300, 450), "image/jpeg")},
    )
    client.post("/vocabulary", data={"word": "kanly", "definition": "a formal feud", "book_id": book_id})
    ctx["image"] = url


@when("they export the library")
def export(ctx):
    res = reader(ctx).get("/api/export")
    assert res.headers["content-type"] == "application/zip"
    ctx["zip"] = res.content


@when(parsers.parse('"{name}" signs up and imports that export'))
def import_elsewhere(ctx, name):
    sign_up(ctx, name)
    res = reader(ctx).post("/api/import", files={"file": ("export.zip", ctx["zip"], "application/zip")})
    assert res.json() == {"books": 1, "words": 1, "notes": 1, "images": 2, "skipped": 0}


@then(parsers.parse('"{name}" has 1 book, 1 word, 1 progress entry and the notes of "{title}"'))
def has_everything(ctx, name, title):
    client, book_id = ctx["readers"][name], ctx["ids"][title]
    assert len(client.get("/api/books").json()["books"]) == 1
    assert len(client.get("/api/vocabulary").json()["words"]) == 1
    assert client.get("/api/progress").json()["progress"] == [
        {"bookId": book_id, "date": "2024-03-01", "percent": 50.0, "page": 300}
    ]
    assert client.get(f"/api/notes/{book_id}").json()["notes"].startswith("Spice")


@then(parsers.parse('"{name}" can load the cover and note image of "{title}"'))
def loads_images(ctx, name, title):
    client = ctx["readers"][name]
    book = client.get("/api/books").json()["books"][0]
    assert client.get(book["coverImage"]).status_code == 200
    assert client.get(ctx["image"]).status_code == 200


@when(parsers.parse('they import "{content}" as a library zip'))
def import_junk(ctx, content):
    ctx["response"] = reader(ctx).post("/api/import", files={"file": ("x.zip", content.encode(), "application/zip")})


@when(parsers.parse('they import "{content}" as a CSV'))
def import_junk_csv(ctx, content):
    data = content.replace("\\n", "\n").encode()
    ctx["response"] = reader(ctx).post("/api/import/csv", files={"file": ("x.csv", data, "text/csv")})


@then(parsers.parse('the response says "{text}"'))
def response_says(ctx, text):
    assert text in ctx["response"].json()["error"]


EXPORTS = {"Goodreads": "goodreads_library_export.csv", "StoryGraph": "storygraph_export.csv"}


def send(ctx, service, mode):
    data = (FIXTURES / EXPORTS[service]).read_bytes()
    ctx["response"] = reader(ctx).post(
        "/api/import/csv", data={"mode": mode}, files={"file": ("export.csv", data, "text/csv")}
    )
    assert ctx["response"].status_code == 200, ctx["response"].text
    ctx["summary"] = ctx["response"].json()["summary"]


@when(parsers.parse("they preview the {service} export"))
def preview(ctx, service):
    send(ctx, service, "preview")


@given(parsers.parse("they imported the {service} export"))
@when(parsers.parse("they import the {service} export"))
def apply(ctx, service):
    send(ctx, service, "apply")


@then(parsers.parse("the summary has {pairs}"))
def summary_has(ctx, pairs):
    for pair in pairs.split(", "):
        key, value = pair.split(" ")
        assert str(ctx["summary"][key]) == value, (key, ctx["summary"])


@then(parsers.parse("the library has {count:d} books"))
def book_count(ctx, count):
    assert len(reader(ctx).get("/api/books").json()["books"]) == count


def book(ctx, book_id):
    return next(b for b in reader(ctx).get("/api/books").json()["books"] if b["id"] == book_id)


@then(parsers.parse('book "{book_id}" is "{title}" with ISBN "{isbn}", rating {rating:d} and read on "{day}"'))
def book_is(ctx, book_id, title, isbn, rating, day):
    b = book(ctx, book_id)
    assert (b["title"], b["isbn"], b["rating"], b["dateRead"]) == (title, isbn, rating, day)


@then(parsers.parse("the notes of \"{book_id}\" contain '{text}'"))
def notes_contain(ctx, book_id, text):
    assert text in reader(ctx).get(f"/api/notes/{book_id}").json()["notes"]


@then(parsers.parse('book "{book_id}" has status "{status}"'))
def book_status(ctx, book_id, status):
    assert book(ctx, book_id)["status"] == status


@then(parsers.parse('"{title}" appears once, with status "{status}", rating {rating:d} and its own id'))
def appears_once(ctx, title, status, rating):
    matches = [b for b in reader(ctx).get("/api/books").json()["books"] if b["title"] == title]
    assert len(matches) == 1
    assert (matches[0]["id"], matches[0]["status"], matches[0]["rating"]) == (ctx["ids"][title], status, rating)
