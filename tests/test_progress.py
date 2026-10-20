from conftest import reader
from pytest_bdd import parsers, scenarios, then, when

scenarios("progress.feature")


@when(parsers.parse('they log page {page:d} of "{title}" on {day}'))
def log_page(ctx, page, title, day):
    res = reader(ctx).post(f"/books/{ctx['ids'][title]}/progress", data={"value": page, "date": day})
    assert res.status_code == 200


@when(parsers.parse('they send page {page:d} of "{title}" to the API'))
def send_page(ctx, page, title):
    ctx["response"] = reader(ctx).put(
        f"/api/progress/{ctx['ids'][title]}", json={"date": "2024-03-01", "page": page, "percent": 100}
    )


def book(ctx, title):
    return next(b for b in reader(ctx).get("/api/books").json()["books"] if b["title"] == title)


@then(parsers.parse('"{title}" has status "{status}"'))
def has_status(ctx, title, status):
    assert book(ctx, title)["status"] == status


@then(parsers.parse('"{title}" has {count:d} progress entry at {percent:d} percent'))
def entries(ctx, title, count, percent):
    progress = reader(ctx).get("/api/progress").json()["progress"]
    assert len(progress) == count
    assert progress[0]["percent"] == percent  # Emma has no page count: the value is a percentage
