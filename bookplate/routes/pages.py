"""Server-rendered pages (``app/*/page.tsx``). Forms post back here and redirect."""

import random
import uuid
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt
from sqlmodel import Session
from starlette.concurrency import run_in_threadpool

from .. import archive, auth, csv_import, library, outbound, showcase, stats, storage
from ..config import config
from ..db import get_session
from ..domain import (
    FEATURES,
    FORMAT_LABELS,
    PALETTE,
    STATUS_LABELS,
    date_label,
    normalise_source,
    palette_for,
    source_label,
    summarize,
    today_iso,
)
from ..models import Book, User, VocabEntry, iso_now
from ..validate import is_iso_date
from .api import check_book_limit, check_word_limit, image_response, read_upload, store_cover

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")
markdown = MarkdownIt("commonmark", {"html": False})  # raw HTML off, as in the original
templates.env.globals.update(
    STATUS_LABELS=STATUS_LABELS,
    FORMAT_LABELS=FORMAT_LABELS,
    PALETTE=PALETTE,
    FEATURES=FEATURES,
    palette_for=palette_for,
    source_label=source_label,
    date_label=date_label,
    config=config,
)
templates.env.filters["markdown"] = markdown.render
templates.env.filters["dict_merge"] = lambda a, b: {**a, **b}
templates.env.filters["urlencode_clean"] = lambda d: urlencode({k: v for k, v in d.items() if v})
SORTS = {
    "added": lambda b: b.added_at,
    "title": lambda b: b.title.lower(),
    "author": lambda b: b.author.lower(),
    "rating": lambda b: b.rating,
    "date": lambda b: b.date_read or "",
}
DESCENDING = {"added", "rating", "date"}


def render(
    request: Request, template: str, user: User | None = None, status_code: int = 200, **context
) -> HTMLResponse:
    return templates.TemplateResponse(request, template, {"user": user, **context}, status_code=status_code)


def redirect(url: str, **params) -> RedirectResponse:
    return RedirectResponse(f"{url}?{urlencode(params)}" if params else url, status_code=303)


def owned_book(db: Session, user: User, book_id: str) -> Book:
    if not (book := library.get_book(db, user.id, book_id)):
        raise HTTPException(404, "No such book")
    return book


# ── Sign in, sign up ───────────────────────────────────────────────────────


def signed_in(db: Session, user: User, to: str = "/") -> RedirectResponse:
    response = redirect(to)
    auth.set_cookie(response, auth.create_session(db, user))
    return response


@router.get("/login")
def login_page(request: Request, db: Session = Depends(get_session)):
    if not auth.has_users(db):
        return redirect("/setup")
    return render(request, "auth.html", mode="login", can_sign_up=auth.can_sign_up(db))


@router.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_session)):
    try:
        return signed_in(db, auth.sign_in(db, email, password))
    except auth.AuthError as e:
        return render(
            request,
            "auth.html",
            mode="login",
            error=str(e),
            email=email,
            status_code=400,
            can_sign_up=auth.can_sign_up(db),
        )


@router.get("/setup")
@router.get("/signup")
def signup_page(request: Request, db: Session = Depends(get_session)):
    if not auth.can_sign_up(db):
        return redirect("/login")
    return render(request, "auth.html", mode="setup" if not auth.has_users(db) else "signup")


@router.post("/signup")
def signup(
    request: Request,
    name: str = Form(""),
    email: str = Form(""),
    password: str = Form(""),
    db: Session = Depends(get_session),
):
    try:
        return signed_in(db, auth.sign_up(db, name, email, password))
    except auth.AuthError as e:
        mode = "setup" if not auth.has_users(db) else "signup"
        return render(request, "auth.html", mode=mode, error=str(e), name=name, email=email, status_code=400)


@router.post("/logout")
def logout(request: Request, user: User = Depends(auth.page_user), db: Session = Depends(get_session)):
    auth.end_sessions(db, user.id, request.cookies.get(auth.COOKIE))
    response = redirect("/login")
    response.delete_cookie(auth.COOKIE)
    return response


# ── Library ────────────────────────────────────────────────────────────────


@router.get("/")
def library_page(
    request: Request,
    q: str = "",
    status: str = "all",
    sort: str = "added",
    view: str = "covers",
    notes: bool = False,
    user: User = Depends(auth.page_user),
    db: Session = Depends(get_session),
):
    books = library.list_books(db, user.id)
    noted = library.noted_book_ids(db, user.id)
    counts = {s: sum(1 for b in books if b.status == s) for s in STATUS_LABELS}
    if q.strip():
        needle = q.strip().lower()
        hay = {
            b.id: " ".join(
                filter(
                    None,
                    [
                        b.title,
                        b.author,
                        b.genre,
                        b.short_notes,
                        library.read_notes(db, user.id, b.id) if b.id in noted else None,
                    ],
                )
            )
            for b in books
        }
        books = [b for b in books if needle in hay[b.id].lower()]
    if status in STATUS_LABELS:
        books = [b for b in books if b.status == status]
    sort = sort if sort in SORTS else "added"
    books.sort(key=SORTS[sort], reverse=sort in DESCENDING)
    progress = library.list_progress(db, user.id)
    percents = {b.id: s.percent for b in books if b.status == "reading" and (s := summarize(b, progress))}
    return render(
        request,
        "library.html",
        user,
        books=books,
        noted=noted,
        counts=counts,
        q=q,
        status=status,
        sort=sort,
        view=view if view in ("covers", "ledger") else "covers",
        show_notes=notes,
        percents=percents,
        total_pages=sum(b.pages or 0 for b in books),
    )


def book_form(request: Request, user: User, book: Book | None, error: str | None = None, editing: bool = False):
    # A new book gets a random binding colour, as in the original.
    color = book.color_index if book else random.randrange(len(PALETTE))
    return render(
        request,
        "book_form.html",
        user,
        book=book,
        editing=editing,
        color=color,
        error=error,
        today=today_iso(),
        status_code=400 if error else 200,
    )


@router.get("/books/new")
def new_book_page(request: Request, user: User = Depends(auth.page_user)):
    return book_form(request, user, None)


@router.get("/books/{book_id}/edit")
def edit_book_page(
    request: Request, book_id: str, user: User = Depends(auth.page_user), db: Session = Depends(get_session)
):
    return book_form(request, user, owned_book(db, user, book_id), editing=True)


@router.post("/books")
@router.post("/books/{book_id}/edit")
async def save_book(
    request: Request,
    book_id: str | None = None,
    title: str = Form(""),
    author: str = Form(""),
    genre: str = Form(""),
    pages: str = Form(""),
    status: str = Form("to-read"),
    rating: float = Form(0),
    date_read: str = Form(""),
    source: str = Form(""),
    source_custom: str = Form(""),
    has_copy: bool = Form(False, alias="copy"),
    isbn: str = Form(""),
    ol_work_id: str = Form(""),
    ol_cover_id: str = Form(""),
    color_index: int | None = Form(None),
    remove_cover: bool = Form(False),
    cover: UploadFile | None = File(None),
    user: User = Depends(auth.page_user),
    db: Session = Depends(get_session),
):
    existing = owned_book(db, user, book_id) if book_id else None
    book = existing or Book(
        user_id=user.id,
        id=str(uuid.uuid4()),
        title="",
        author="",
        color_index=random.randrange(len(PALETTE)),
        added_at=iso_now(),
    )
    book.title, book.author = title.strip(), author.strip()
    book.genre = genre.strip() or None
    book.pages = int(pages) if pages.strip().isdigit() and int(pages) > 0 else None
    book.status = status if status in STATUS_LABELS else "to-read"
    book.rating = min(5.0, max(0.0, round(rating * 2) / 2))
    book.date_read = date_read if date_read and book.status in ("read", "dnf") else None
    typed = source_custom if source == "other" else source
    book.format = normalise_source(typed) if typed.strip() else None
    book.has_copy = has_copy or None
    book.isbn = isbn.strip() or None
    book.ol_work_id = ol_work_id.strip() or None
    if color_index is not None:
        book.color_index = color_index % len(PALETTE)
    editing = existing is not None
    if not book.title or not book.author:
        return book_form(request, user, book, "A book needs a title and an author.", editing)
    if book.date_read and not is_iso_date(book.date_read):
        return book_form(request, user, book, "Enter the date as a calendar day.", editing)
    if not existing:
        check_book_limit(db, user.id, book.id)

    # The old cover file goes only once the book is saved without it, so a failed upload keeps it.
    removed = library.cover_file(book.cover_image) if remove_cover else None
    if remove_cover:
        book.cover_image = None
    if cover and cover.filename:
        try:
            data = await read_upload(cover, config.upload_bytes)
            book.cover_image = await run_in_threadpool(store_cover, user.id, book.id, data)
        except HTTPException as e:
            return book_form(request, user, book, e.detail, editing)
    elif ol_cover_id.isdigit() and (
        data := await run_in_threadpool(outbound.find_cover, int(ol_cover_id), None, book.title, book.author)
    ):
        book.cover_image = await run_in_threadpool(store_cover, user.id, book.id, data)
    library.save_book(db, book)
    if removed and not book.cover_image:
        storage.delete(storage.cover_key(user.id, removed))
    return redirect(f"/books/{book.id}")


@router.post("/books/{book_id}/delete")
def delete_book(book_id: str, user: User = Depends(auth.page_user), db: Session = Depends(get_session)):
    library.delete_book(db, user.id, book_id)
    return redirect("/")


# ── A book's page: details, progress, notes ────────────────────────────────


@router.get("/books/{book_id}")
def book_page(
    request: Request,
    book_id: str,
    edit: bool = False,
    user: User = Depends(auth.page_user),
    db: Session = Depends(get_session),
):
    book = owned_book(db, user, book_id)
    words = [w for w in library.list_vocabulary(db, user.id) if w.book_id == book_id]
    return render(
        request,
        "book.html",
        user,
        book=book,
        notes=library.read_notes(db, user.id, book_id) or "",
        edit=edit,
        words=sorted(words, key=lambda w: w.word.lower()),
        today=today_iso(),
        progress=summarize(book, library.list_progress(db, user.id)),
    )


@router.post("/books/{book_id}/notes")
def save_notes(
    book_id: str,
    markdown_text: str = Form("", alias="markdown"),
    action: str = Form("save"),
    user: User = Depends(auth.page_user),
    db: Session = Depends(get_session),
):
    """Save stores the text; Cancel keeps the stored text but still bins images pasted meanwhile."""
    owned_book(db, user, book_id)
    if action == "cancel":
        markdown_text = library.read_notes(db, user.id, book_id) or ""
    library.write_notes(db, user.id, book_id, markdown_text)
    return redirect(f"/books/{book_id}")


@router.post("/books/{book_id}/progress")
def log_progress(
    book_id: str,
    value: float = Form(...),
    day: str = Form("", alias="date"),
    user: User = Depends(auth.page_user),
    db: Session = Depends(get_session),
):
    """Pages when the book has a page count, otherwise a percentage."""
    book = owned_book(db, user, book_id)
    day = day or today_iso()
    if not is_iso_date(day):
        raise HTTPException(400, "Enter the date as a calendar day.")
    if book.pages:
        page = max(0, min(int(value), book.pages))
        library.save_progress(db, user.id, book_id, day, page / book.pages * 100, page)
    else:
        library.save_progress(db, user.id, book_id, day, max(0.0, min(value, 100.0)), None)
    if book.status == "to-read":  # the first update marks the book as started
        book.status = "reading"
        library.save_book(db, book)
    return redirect(f"/books/{book_id}")


@router.post("/books/{book_id}/progress/{day}/delete")
def remove_progress(book_id: str, day: str, user: User = Depends(auth.page_user), db: Session = Depends(get_session)):
    library.delete_progress(db, user.id, book_id, day)
    return redirect(f"/books/{book_id}")


# ── Vocabulary ─────────────────────────────────────────────────────────────


@router.get("/vocabulary")
def vocabulary_page(
    request: Request,
    q: str = "",
    book: str = "",
    sort: str = "added",
    user: User = Depends(auth.page_user),
    db: Session = Depends(get_session),
):
    words = library.list_vocabulary(db, user.id)
    books = {b.id: b for b in library.list_books(db, user.id)}
    if q.strip():
        needle = q.strip().lower()
        words = [w for w in words if needle in f"{w.word} {w.definition} {w.example or ''}".lower()]
    if book:
        words = [w for w in words if w.book_id == book]
    if sort == "word":
        words.sort(key=lambda w: w.word.lower())
    else:
        words.sort(key=lambda w: w.added_at, reverse=True)
    return render(
        request,
        "vocabulary.html",
        user,
        words=words,
        books=books,
        q=q,
        book=book,
        sort=sort,
        shelf=sorted(books.values(), key=lambda b: b.title.lower()),
    )


@router.post("/vocabulary")
@router.post("/vocabulary/{word_id}")
def save_word(
    word_id: str | None = None,
    word: str = Form(...),
    definition: str = Form(...),
    part_of_speech: str = Form(""),
    example: str = Form(""),
    book_id: str = Form(""),
    phonetic: str | None = Form(None),
    back: str = Form("/vocabulary"),
    user: User = Depends(auth.page_user),
    db: Session = Depends(get_session),
):
    existing = db.get(VocabEntry, (user.id, word_id)) if word_id else None
    entry = existing or VocabEntry(user_id=user.id, id=str(uuid.uuid4()), word="", definition="")
    if not existing:
        check_word_limit(db, user.id, entry.id)
    entry.word, entry.definition = word.strip(), definition.strip()
    entry.part_of_speech = part_of_speech.strip() or None
    entry.example = example.strip() or None
    if phonetic is not None:  # the forms don't carry it: keep what the dictionary or an import gave
        entry.phonetic = phonetic.strip() or None
    entry.book_id = book_id if book_id and library.get_book(db, user.id, book_id) else None
    if entry.word and entry.definition:
        library.save_vocab(db, entry)
    # Only back to a page of this app: "//host" would leave it.
    return redirect(back if back.startswith("/") and not back.startswith(("//", "/\\")) else "/vocabulary")


@router.post("/vocabulary/{word_id}/delete")
def delete_word(word_id: str, user: User = Depends(auth.page_user), db: Session = Depends(get_session)):
    library.delete_vocab(db, user.id, word_id)
    return redirect("/vocabulary")


# ── Statistics ─────────────────────────────────────────────────────────────


@router.get("/statistics")
def statistics_page(
    request: Request,
    drill: str = "",
    v: str = "",
    user: User = Depends(auth.page_user),
    db: Session = Depends(get_session),
):
    books = library.list_books(db, user.id)
    overview = stats.overview(books, library.list_progress(db, user.id))
    return render(request, "statistics.html", user, s=overview, drill=stats.drill(books, drill, v) if drill else None)


# ── Settings ───────────────────────────────────────────────────────────────


def settings(request: Request, user: User, db: Session, **context):
    return render(
        request,
        "settings.html",
        user,
        showcases=showcase.list_showcases(db, user.id),
        this_year=date.today().year,
        status_code=400 if context.get("error") else 200,
        **context,
    )


@router.get("/settings")
def settings_page(
    request: Request, msg: str = "", user: User = Depends(auth.page_user), db: Session = Depends(get_session)
):
    return settings(request, user, db, msg=msg)


@router.post("/settings/profile")
def save_profile(name: str = Form(...), user: User = Depends(auth.page_user), db: Session = Depends(get_session)):
    if name.strip():
        user.name = name.strip()
        db.add(user)
        db.commit()
    return redirect("/settings", msg="Profile saved.")


@router.post("/settings/features")
async def save_features(request: Request, user: User = Depends(auth.page_user), db: Session = Depends(get_session)):
    form = await request.form()
    user.features = [f for f in FEATURES if form.get(f)]
    db.add(user)
    db.commit()
    return redirect("/settings", msg="Preferences saved.")


@router.post("/settings/password")
def save_password(
    request: Request,
    current: str = Form(...),
    new: str = Form(...),
    user: User = Depends(auth.page_user),
    db: Session = Depends(get_session),
):
    try:
        auth.change_password(db, user, current, new)
    except auth.AuthError as e:
        return settings(request, user, db, error=str(e))
    auth.end_sessions(db, user.id)  # sign out every device, then sign this one back in
    return signed_in(db, user, "/settings?msg=Password+changed.")


@router.post("/settings/delete")
def delete_account(
    request: Request,
    password: str = Form(...),
    user: User = Depends(auth.page_user),
    db: Session = Depends(get_session),
):
    if not auth.verify_password(password, user.password_hash):
        return settings(request, user, db, error="The password is wrong.")
    storage.delete_prefix(user.id)
    db.delete(user)
    db.commit()
    response = redirect("/login")
    response.delete_cookie(auth.COOKIE)
    return response


@router.post("/settings/import")
async def import_zip(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(auth.page_user),
    db: Session = Depends(get_session),
):
    data = await read_upload(file, config.import_bytes)
    try:
        s = await run_in_threadpool(archive.import_archive, db, user.id, data)
    except archive.ImportError_ as e:
        return settings(request, user, db, error=str(e))
    return redirect(
        "/settings",
        msg=f"Imported {s.books} books, {s.words} words, {s.notes} notes and {s.images} images ({s.skipped} skipped).",
    )


@router.post("/settings/import-csv")
async def import_csv(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(auth.page_user),
    db: Session = Depends(get_session),
):
    text = (await read_upload(file, config.import_bytes)).decode("utf-8", errors="replace")
    try:
        s = await run_in_threadpool(csv_import.apply_csv_import, db, user.id, text)
    except csv_import.CsvImportError as e:
        return settings(request, user, db, error=str(e))
    return redirect(
        "/settings",
        msg=f"From {s.source.title()}: {s.added} books added, {s.updated} updated, {s.notes} reviews became notes.",
    )


@router.post("/settings/showcase")
def save_showcase(
    request: Request,
    year: int = Form(...),
    include: str = Form("both"),
    name: str = Form(""),
    user: User = Depends(auth.page_user),
    db: Session = Depends(get_session),
):
    try:
        year, include, shown_name = showcase.parse_showcase(year, include, name, date.today().year)
    except showcase.ShowcaseError as e:
        return settings(request, user, db, error=str(e))
    s = showcase.save_showcase(db, user.id, year, include, shown_name)
    return redirect("/settings", msg=f"Your {year} showcase is at {config.public_url}/s/{s.id}")


@router.post("/settings/showcase/{showcase_id}/delete")
def delete_showcase(showcase_id: str, user: User = Depends(auth.page_user), db: Session = Depends(get_session)):
    showcase.delete_showcase(db, user.id, showcase_id)
    return redirect("/settings", msg="Showcase turned off.")


# ── Public showcase pages ──────────────────────────────────────────────────


@router.get("/s/{showcase_id}")
def showcase_page(request: Request, showcase_id: str, db: Session = Depends(get_session)):
    if not (found := showcase.load_showcase(db, showcase_id)):
        return render(request, "not_found.html", status_code=404)
    s, view = found
    return render(
        request,
        "showcase.html",
        s=s,
        view=view,
        months=showcase.MONTHS,
        title=f"{showcase.possessive(s.name)} {s.year} in books" if s.name else f"{s.year} in books",
        can_sign_up=auth.can_sign_up(db),
    )


@router.get("/s/{showcase_id}/covers/{name}")
def showcase_cover(showcase_id: str, name: str, db: Session = Depends(get_session)) -> Response:
    found = showcase.load_showcase(db, showcase_id)
    if not found or not storage.is_safe_file(name) or not showcase.cover_file_of(found[1], name):
        raise HTTPException(404, "Not found")
    return image_response(storage.get(storage.cover_key(found[0].user_id, name)), name)
