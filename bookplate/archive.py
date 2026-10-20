"""The export format (lib/archive.ts): a zip laid out like the original data/ folder.

manifest.json                 { format: "bookplate-export", formatVersion: 1, … }
library.json                  { books: [...] }
vocabulary.json               { words: [...] }
progress.json                 { progress: [...] }
notes/<bookId>.md             one markdown file per book
notes/images/<bookId>/<file>  images pasted into those notes
covers/<file>                 cropped covers
"""

import io
import json
import re
import zipfile
from dataclasses import asdict, dataclass

from sqlmodel import Session, select

from . import library, storage
from .config import config
from .models import Note, iso_now
from .validate import is_valid_book, is_valid_progress, is_valid_vocab

FORMAT_VERSION = 1


class ImportError_(Exception):
    pass


def _dump(data: object) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def build_export(db: Session, user_id: str) -> bytes:
    books = library.list_books(db, user_id)
    notes = db.exec(select(Note).where(Note.user_id == user_id)).all()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        manifest = {
            "format": "bookplate-export",
            "formatVersion": FORMAT_VERSION,
            "appVersion": config.version,
            "exportedAt": iso_now(),
        }
        z.writestr("manifest.json", _dump(manifest))
        z.writestr("library.json", _dump({"books": [library.book_json(b) for b in books]}))
        words = [library.to_json(w, library.VOCAB_FIELDS) for w in library.list_vocabulary(db, user_id)]
        z.writestr("vocabulary.json", _dump({"words": words}))
        progress = [library.progress_json(p) for p in library.list_progress(db, user_id)]
        z.writestr("progress.json", _dump({"progress": progress}))
        for n in notes:
            z.writestr(f"notes/{n.book_id}.md", n.markdown)
            for key in storage.list_dir(storage.notes_dir(user_id, n.book_id)):
                if data := storage.get(key):
                    z.writestr(f"notes/images/{n.book_id}/{key.rsplit('/', 1)[1]}", data, zipfile.ZIP_STORED)
        for b in books:
            m = library.COVER_NAME.search(b.cover_image or "")
            if m and storage.is_safe_file(m[1]) and (data := storage.get(storage.cover_key(user_id, m[1]))):
                z.writestr(f"covers/{m[1]}", data, zipfile.ZIP_STORED)  # JPEGs don't compress further
    return buf.getvalue()


@dataclass
class ImportSummary:
    books: int
    words: int
    notes: int
    images: int
    skipped: int


def _json(entries: dict[str, bytes], path: str) -> dict:
    if path not in entries:
        return {}
    try:
        return json.loads(entries[path])
    except ValueError as e:
        raise ImportError_("A JSON file in the zip could not be read.") from e


def _is_image_named(name: str, data: bytes) -> bool:
    return storage.detect_image_type(data) == storage.content_type(name)


def import_archive(db: Session, user_id: str, data: bytes) -> ImportSummary:
    """Reads a Bookplate export (or a zip of an original data/ folder, possibly inside a
    top-level folder). Records with the same ids are overwritten; nothing is deleted."""
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        if sum(i.file_size for i in z.infolist()) > 2 * config.import_bytes:
            raise ImportError_("That zip unpacks to more than this server allows.")
        entries = {i.filename: z.read(i) for i in z.infolist() if not i.is_dir()}
    except zipfile.BadZipFile as e:
        raise ImportError_("That file isn't a readable zip.") from e

    candidates = sorted((p for p in entries if p.split("/")[-1] == "library.json" and "__MACOSX/" not in p), key=len)
    if not candidates:
        raise ImportError_("No library.json found in the zip.")
    root = candidates[0][: -len("library.json")]
    if (_json(entries, root + "manifest.json").get("formatVersion") or 0) > FORMAT_VERSION:
        raise ImportError_("This export was made by a newer version of Bookplate. Update this server first.")

    raw_books = _json(entries, candidates[0]).get("books")
    if not isinstance(raw_books, list):
        raise ImportError_("library.json has no books list.")
    raw_words = _json(entries, root + "vocabulary.json").get("words", [])
    raw_progress = _json(entries, root + "progress.json").get("progress", [])
    books = [b | {"status": b.get("status") or "to-read"} for b in raw_books if is_valid_book(b)]
    words = [w for w in raw_words if is_valid_vocab(w)]
    progress = [p for p in raw_progress if is_valid_progress(p)]
    skipped = len(raw_books) + len(raw_words) + len(raw_progress) - len(books) - len(words) - len(progress)

    notes: dict[str, str] = {}
    images: list[tuple[str, bytes]] = []
    for path, content in entries.items():
        if not path.startswith(root):
            continue
        rel = path[len(root) :]
        if (m := re.fullmatch(r"notes/([^/]+)\.md", rel)) and storage.is_safe_id(m[1]):
            notes[m[1]] = content.decode("utf-8")
        elif (m := re.fullmatch(r"notes/images/([^/]+)/([^/]+)", rel)) and storage.is_safe_id(m[1]):
            if storage.is_safe_file(m[2]) and _is_image_named(m[2], content):
                images.append((f"{storage.notes_dir(user_id, m[1])}/{m[2]}", content))
            else:
                skipped += 1
        elif m := re.fullmatch(r"covers/([^/]+)", rel):
            if storage.is_safe_file(m[1]) and _is_image_named(m[1], content):
                images.append((storage.cover_key(user_id, m[1]), content))
            else:
                skipped += 1

    if config.limit_books and len(library.list_books(db, user_id)) + len(books) > config.limit_books:
        raise ImportError_(f"This import would go over the limit of {config.limit_books} books.")
    for key, content in images:  # images first: if the database write fails, a retry overwrites them
        storage.put(key, content)
    library.import_records(db, user_id, books, words, notes, progress)
    return ImportSummary(len(books), len(words), len(notes), len(images), skipped)


def summary_dict(s: ImportSummary) -> dict:
    return asdict(s)
