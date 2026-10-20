"""All configuration comes from environment variables (lib/config.ts)."""

import os
import re
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path


def _database_url() -> str:
    """Accepts the original's postgres:// form and uses the psycopg 3 driver for it."""
    url = os.environ.get("DATABASE_URL", "sqlite:///./bookplate.db")
    return re.sub(r"^postgres(ql)?://", "postgresql+psycopg://", url)


def _int(name: str) -> int | None:
    value = os.environ.get(name, "").strip()
    return int(value) if value else None


@dataclass(frozen=True)
class Config:
    version: str = field(default_factory=lambda: metadata.version("bookplate"))
    database_url: str = field(default_factory=_database_url)
    public_url: str = field(default_factory=lambda: os.environ.get("PUBLIC_URL", "http://localhost:8000").rstrip("/"))
    registration_open: bool = field(default_factory=lambda: os.environ.get("REGISTRATION", "closed") == "open")
    uploads_dir: Path = field(default_factory=lambda: Path(os.environ.get("UPLOADS_DIR", "./data/uploads")))
    contact_email: str | None = field(default_factory=lambda: os.environ.get("CONTACT_EMAIL") or None)
    limit_books: int | None = field(default_factory=lambda: _int("LIMIT_BOOKS"))
    limit_words: int | None = field(default_factory=lambda: _int("LIMIT_WORDS"))
    upload_bytes: int = field(default_factory=lambda: (_int("LIMIT_UPLOAD_MB") or 8) * 1024 * 1024)
    import_bytes: int = field(default_factory=lambda: (_int("LIMIT_IMPORT_MB") or 1024) * 1024 * 1024)

    @property
    def secure_cookies(self) -> bool:
        return self.public_url.startswith("https://")

    @property
    def user_agent(self) -> str:
        contact = f"; {self.contact_email}" if self.contact_email else ""
        return f"Bookplate/{self.version} (+https://github.com/LeoPhh/bookplate{contact})"


config = Config()
