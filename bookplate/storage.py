"""Images on local disk, every key under the owning user (lib/storage). Covers are
normalised server-side to the original's 2:3, 600×900 JPEG; pasted note images
are capped at a 1600px long edge — the work the browser did in the original."""

import io
import re
import shutil
from pathlib import Path

from PIL import Image, ImageOps

from .config import config

SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")
SAFE_FILE = re.compile(r"^[A-Za-z0-9_-]+\.(jpg|jpeg|png|gif|webp)$")
CONTENT_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
}


def is_safe_id(value: str) -> bool:
    return bool(SAFE_ID.match(value))


def is_safe_file(name: str) -> bool:
    return bool(SAFE_FILE.match(name))


def content_type(name: str) -> str:
    return CONTENT_TYPES.get(name.rsplit(".", 1)[-1].lower(), "application/octet-stream")


def detect_image_type(data: bytes) -> str | None:
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def cover_key(user_id: str, name: str) -> str:
    return f"{user_id}/covers/{name}"


def notes_dir(user_id: str, book_id: str) -> str:
    return f"{user_id}/notes/{book_id}"


def _path(key: str) -> Path:
    return config.uploads_dir / key


def put(key: str, data: bytes) -> None:
    path = _path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def get(key: str) -> bytes | None:
    path = _path(key)
    return path.read_bytes() if path.is_file() else None


def delete(key: str) -> None:
    _path(key).unlink(missing_ok=True)


def delete_prefix(prefix: str) -> None:
    shutil.rmtree(_path(prefix), ignore_errors=True)


def list_dir(prefix: str) -> list[str]:
    path = _path(prefix)
    return sorted(f"{prefix}/{p.name}" for p in path.iterdir() if p.is_file()) if path.is_dir() else []


def _jpeg(img: Image.Image) -> bytes:
    out = io.BytesIO()
    img.convert("RGB").save(out, "JPEG", quality=82, optimize=True)
    return out.getvalue()


def make_cover(data: bytes) -> bytes:
    """Centre-crops to book proportions (2:3) and caps at 600×900."""
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
    w, h = img.size
    tw, th = (w, round(w * 1.5)) if h >= w * 1.5 else (round(h / 1.5), h)
    img = ImageOps.fit(img, (tw, th))
    if tw > 600:
        img = img.resize((600, 900), Image.LANCZOS)
    return _jpeg(img)


def downscale(data: bytes, long_edge: int = 1600) -> bytes:
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
    img.thumbnail((long_edge, long_edge))
    return _jpeg(img)
