import io

from conftest import jpeg, reader
from PIL import Image
from pytest_bdd import given, parsers, scenarios, then, when

from bookplate import storage

scenarios("notes.feature")


@given(parsers.parse('they saved the notes of "{title}" as "{text}"'))
@when(parsers.parse('they save the notes of "{title}" as "{text}"'))
def save_notes(ctx, title, text):
    res = reader(ctx).post(f"/books/{ctx['ids'][title]}/notes", data={"markdown": text.replace("\\n", "\n")})
    assert res.status_code == 200


@given(parsers.parse('they pasted an image into the notes of "{title}"'))
def paste_image(ctx, title):
    res = reader(ctx).post(
        "/api/notes/images",
        data={"book": ctx["ids"][title]},
        files={"file": ("paste.png", jpeg(2400, 1200), "image/jpeg")},
    )
    ctx["image"] = res.json()["url"]


@when(parsers.parse('they save the notes of "{title}" with the pasted image'))
def save_with_image(ctx, title):
    save_notes(ctx, title, f"Look: ![]({ctx['image']})")


@when(parsers.parse('they cancel editing the notes of "{title}"'))
def cancel(ctx, title):
    reader(ctx).post(f"/books/{ctx['ids'][title]}/notes", data={"markdown": "unsaved", "action": "cancel"})


def stored_images(ctx, title):
    return [p for p in storage.config.uploads_dir.rglob(f"notes/{ctx['ids'][title]}/*") if p.is_file()]


@then(parsers.parse('"{title}" has {count:d} stored note images'))
def image_count(ctx, title, count):
    assert len(stored_images(ctx, title)) == count


@then("the pasted image can be loaded")
def image_loads(ctx):
    res = reader(ctx).get(ctx["image"])
    assert res.status_code == 200 and res.headers["content-type"] == "image/jpeg"
    assert max(Image.open(io.BytesIO(res.content)).size) == 1600  # downscaled long edge


@then(parsers.parse('the notes of "{title}" are "{text}"'))
def notes_are(ctx, title, text):
    assert reader(ctx).get(f"/api/notes/{ctx['ids'][title]}").json() == {"notes": text}
