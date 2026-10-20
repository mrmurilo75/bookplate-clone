import re

from conftest import jpeg, new_client, reader
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("showcase.feature")


@given(parsers.parse('"{title}" has the notes "{text}" and a cover'))
def notes_and_cover(ctx, title, text):
    book_id = ctx["ids"][title]
    reader(ctx).post(f"/books/{book_id}/notes", data={"markdown": text})
    reader(ctx).post(
        f"/books/{book_id}/edit",
        data={"title": title, "author": "Frank Herbert", "status": "read", "date_read": "2024-03-10", "rating": "5"},
        files={"cover": ("c.jpg", jpeg(300, 450), "image/jpeg")},
    )


@given(parsers.parse("they showcased {year:d}"))
@when(parsers.parse('they showcase {year:d} as "{name}"'))
def showcase(ctx, year, name="Ada"):
    res = reader(ctx).post("/settings/showcase", data={"year": year, "include": "both", "name": name})
    ctx["showcase"] = re.search(r"/s/([A-Za-z0-9_-]{16})", res.text)[1]


@when(parsers.parse("they try to showcase reading books for {year:d}"))
def showcase_reading(ctx, year):
    ctx["response"] = reader(ctx).post("/settings/showcase", data={"year": year, "include": "reading"})


@when("a stranger opens the showcase")
def stranger_opens(ctx):
    ctx["stranger"] = new_client()
    ctx["response"] = ctx["stranger"].get(f"/s/{ctx['showcase']}")


@then(parsers.parse('the stranger can load the cover of "{title}"'))
def stranger_cover(ctx, title):
    src = re.search(rf'src="(/s/{ctx["showcase"]}/covers/{ctx["ids"][title]}\.jpg[^"]*)"', ctx["response"].text)[1]
    assert ctx["stranger"].get(src.replace("&amp;", "&")).status_code == 200
    # Only covers of books the showcase shows, and never through the private route.
    assert ctx["stranger"].get(f"/api/covers/{ctx['ids'][title]}.jpg").status_code == 401


@then(parsers.parse('there is {count:d} showcase with the name "{name}"'))
def one_showcase(ctx, count, name):
    page = reader(ctx).get("/settings").text
    assert page.count('<div class="showcase-row">') == count
    assert f"as “{name}”" in page


@when("they turn the showcase off")
def turn_off(ctx):
    reader(ctx).post(f"/settings/showcase/{ctx['showcase']}/delete")
