"""JSON API (app/api/*). Every route starts with require_user and only calls the
user-scoped helpers in library.py."""

import time

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response
from sqlmodel import Session
from starlette.concurrency import run_in_threadpool

from .. import archive, csv_import, library, outbound, storage
from ..auth import require_user
from ..config import config
from ..db import get_session
from ..models import Book, User, VocabEntry
from ..validate import DATE_RE, is_valid_book, is_valid_progress, is_valid_vocab

router = APIRouter(prefix="/api")


def check_book_limit(db: Session, user_id: str, book_id: str) -> None:
    """Anything that adds books checks the per-account limit first (lib/limits.ts)."""
    if config.limit_books and not library.get_book(db, user_id, book_id):
        if library.count_books(db, user_id) >= config.limit_books:
            raise HTTPException(403, f"You've reached the limit of {config.limit_books} books.")


def check_word_limit(db: Session, user_id: str, word_id: str) -> None:
    if config.limit_words and not db.get(VocabEntry, (user_id, word_id)):
        if library.count_words(db, user_id) >= config.limit_words:
            raise HTTPException(403, f"You've reached the limit of {config.limit_words} words.")


async def read_upload(file: UploadFile, limit: int) -> bytes:
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, "That file is too large.")
    return data


def store_cover(user_id: str, book_id: str, data: bytes) -> str:
    """Normalises any image to a 2:3 JPEG cover and returns its URL."""
    if not storage.detect_image_type(data):
        raise HTTPException(415, "Covers must be images.")
    try:
        cover = storage.make_cover(data)
    except storage.BadImage as e:
        raise HTTPException(415, "That image couldn't be read.") from e
    name = f"{book_id}.jpg"
    storage.put(storage.cover_key(user_id, name), cover)
    return f"/api/covers/{name}?v={int(time.time() * 1000)}"


def image_response(data: bytes | None, name: str) -> Response:
    if data is None:
        raise HTTPException(404, "Not found")
    return Response(data, media_type=storage.content_type(name), headers={"Cache-Control": "private, max-age=86400"})


@router.get("/health")
def health():
    return {"ok": True, "version": config.version}


# ── Books ──────────────────────────────────────────────────────────────────


@router.get("/books")
def books(user: User = Depends(require_user), db: Session = Depends(get_session)):
    return {"books": [library.book_json(b) for b in library.list_books(db, user.id)]}


@router.put("/books/{book_id}")
def put_book(
    book_id: str, body: dict = Body(...), user: User = Depends(require_user), db: Session = Depends(get_session)
):
    if not storage.is_safe_id(book_id) or not is_valid_book(body) or body["id"] != book_id:
        raise HTTPException(400, "Invalid book")
    check_book_limit(db, user.id, book_id)
    library.save_book(
        db, library.from_json(Book, user.id, body | {"status": body.get("status") or "to-read"}, library.BOOK_FIELDS)
    )
    return {"ok": True}


@router.delete("/books/{book_id}")
def delete_book(book_id: str, user: User = Depends(require_user), db: Session = Depends(get_session)):
    library.delete_book(db, user.id, book_id)
    return {"ok": True}


# ── Covers ─────────────────────────────────────────────────────────────────


@router.post("/covers")
async def upload_cover(id: str = Form(...), file: UploadFile = File(...), user: User = Depends(require_user)):
    if not storage.is_safe_id(id):
        raise HTTPException(400, "Invalid upload")
    data = await read_upload(file, config.upload_bytes)
    return {"path": await run_in_threadpool(store_cover, user.id, id, data)}


@router.get("/covers/{name}")
def cover(name: str, user: User = Depends(require_user)):
    if not storage.is_safe_file(name):
        raise HTTPException(404, "Not found")
    return image_response(storage.get(storage.cover_key(user.id, name)), name)


@router.get("/booksearch")
def booksearch(q: str = "", user: User = Depends(require_user)):
    if not q.strip():
        return {"results": []}
    try:
        return {"results": outbound.search_books(q.strip())}
    except Exception:
        return JSONResponse({"error": "Search failed"}, status_code=502)


@router.get("/booksearch/cover")
def booksearch_cover(id: int | None = None, t: str = "", a: str = "", user: User = Depends(require_user)):
    data = outbound.find_cover(cover_id=id, title=t, author=a)
    return image_response(data, "cover.jpg")


# ── Notes ──────────────────────────────────────────────────────────────────


@router.get("/notes/{book_id}")
def get_notes(book_id: str, user: User = Depends(require_user), db: Session = Depends(get_session)):
    """A book's markdown notes, or null when none have been written."""
    return {"notes": library.read_notes(db, user.id, book_id)}


@router.put("/notes/{book_id}")
def put_notes(
    book_id: str, body: dict = Body(...), user: User = Depends(require_user), db: Session = Depends(get_session)
):
    """Replaces the whole note; every save doubles as garbage collection for removed images."""
    if not storage.is_safe_id(book_id) or not isinstance(body.get("notes"), str) or len(body["notes"]) > 2 * 1024**2:
        raise HTTPException(400, "Invalid notes payload")
    library.write_notes(db, user.id, book_id, body["notes"])
    return {"ok": True}


@router.delete("/notes/{book_id}")
def delete_notes(book_id: str, user: User = Depends(require_user), db: Session = Depends(get_session)):
    library.delete_notes(db, user.id, book_id)
    return {"ok": True}


@router.post("/notes/images")
async def upload_note_image(book: str = Form(...), file: UploadFile = File(...), user: User = Depends(require_user)):
    """Stores an image pasted or dropped into a book's notes, downscaled to a 1600px long edge."""
    data = await read_upload(file, config.upload_bytes)
    if not storage.is_safe_id(book) or not storage.detect_image_type(data):
        raise HTTPException(400, "Invalid image")
    try:
        image = await run_in_threadpool(storage.downscale, data)
    except storage.BadImage as e:
        raise HTTPException(400, "Invalid image") from e
    name = f"{int(time.time() * 1000)}.jpg"
    storage.put(f"{storage.notes_dir(user.id, book)}/{name}", image)
    return {"url": f"/api/notes/images/{book}/{name}"}


@router.get("/notes/images/{book_id}/{name}")
def note_image(book_id: str, name: str, user: User = Depends(require_user)):
    if not storage.is_safe_id(book_id) or not storage.is_safe_file(name):
        raise HTTPException(404, "Not found")
    return image_response(storage.get(f"{storage.notes_dir(user.id, book_id)}/{name}"), name)


# ── Reading progress ───────────────────────────────────────────────────────


@router.get("/progress")
def progress(user: User = Depends(require_user), db: Session = Depends(get_session)):
    return {"progress": [library.progress_json(p) for p in library.list_progress(db, user.id)]}


@router.put("/progress/{book_id}")
def put_progress(
    book_id: str, body: dict = Body(...), user: User = Depends(require_user), db: Session = Depends(get_session)
):
    entry = body | {"bookId": book_id}
    if not is_valid_progress(entry):
        raise HTTPException(400, "Invalid progress")
    if not (book := library.get_book(db, user.id, book_id)):
        raise HTTPException(404, "No such book")
    if entry.get("page") is not None and book.pages and entry["page"] > book.pages:
        raise HTTPException(400, f"This book has {book.pages} pages")
    library.save_progress(db, user.id, book_id, entry["date"], entry["percent"], entry.get("page"))
    return {"ok": True}


@router.delete("/progress/{book_id}")
def delete_progress(book_id: str, date: str, user: User = Depends(require_user), db: Session = Depends(get_session)):
    if not DATE_RE.match(date):
        raise HTTPException(400, "Invalid date")
    library.delete_progress(db, user.id, book_id, date)
    return {"ok": True}


# ── Vocabulary ─────────────────────────────────────────────────────────────


@router.get("/vocabulary")
def vocabulary(user: User = Depends(require_user), db: Session = Depends(get_session)):
    return {"words": [library.to_json(w, library.VOCAB_FIELDS) for w in library.list_vocabulary(db, user.id)]}


@router.put("/vocabulary/{word_id}")
def put_word(
    word_id: str, body: dict = Body(...), user: User = Depends(require_user), db: Session = Depends(get_session)
):
    if not is_valid_vocab(body) or body["id"] != word_id:
        raise HTTPException(400, "Invalid word")
    check_word_limit(db, user.id, word_id)
    library.save_vocab(db, library.from_json(VocabEntry, user.id, body, library.VOCAB_FIELDS))
    return {"ok": True}


@router.delete("/vocabulary/{word_id}")
def delete_word(word_id: str, user: User = Depends(require_user), db: Session = Depends(get_session)):
    library.delete_vocab(db, user.id, word_id)
    return {"ok": True}


@router.get("/define")
def define(word: str = "", user: User = Depends(require_user)):
    """Proxies Wiktionary; {entry: null} when the word has no English entry."""
    if not word.strip():
        return {"entry": None}
    try:
        return {"entry": outbound.define(word)}
    except Exception:
        return JSONResponse({"error": "Lookup failed"}, status_code=502)


# ── Import & export ────────────────────────────────────────────────────────


@router.get("/export")
def export(user: User = Depends(require_user), db: Session = Depends(get_session)):
    return Response(
        archive.build_export(db, user.id),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="bookplate-export.zip"'},
    )


@router.post("/import")
async def import_zip(
    file: UploadFile = File(...), user: User = Depends(require_user), db: Session = Depends(get_session)
):
    data = await read_upload(file, config.import_bytes)
    try:
        return archive.summary_dict(await run_in_threadpool(archive.import_archive, db, user.id, data))
    except archive.ImportError_ as e:
        raise HTTPException(400, str(e)) from e


@router.post("/import/csv")
async def import_csv(
    file: UploadFile = File(...),
    mode: str = Form("apply"),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """mode=preview reports what an import would do without saving; apply saves it."""
    text = (await read_upload(file, config.import_bytes)).decode("utf-8", errors="replace")
    try:
        if mode == "preview":
            summary, _, _ = await run_in_threadpool(csv_import.plan, db, user.id, text)
            return {"summary": csv_import.summary_json(summary)}
        summary = await run_in_threadpool(csv_import.apply_csv_import, db, user.id, text)
        return {"summary": csv_import.summary_json(summary), "coverIds": summary.cover_ids}
    except csv_import.CsvImportError as e:
        raise HTTPException(400, str(e)) from e
