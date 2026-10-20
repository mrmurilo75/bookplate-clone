"""Server-side commands (scripts/reset-password.mjs)."""

import getpass
import sys

from sqlmodel import Session, select

from . import auth
from .db import engine, migrate
from .models import User


def reset_password() -> None:
    """bookplate-reset-password you@example.com — asks for the new password twice and signs out every device."""
    if len(sys.argv) != 2:
        sys.exit("Usage: bookplate-reset-password <email>")
    migrate()
    with Session(engine) as db:
        user = db.exec(select(User).where(User.email == sys.argv[1].strip().lower())).first()
        if not user:
            sys.exit("No account with that email.")
        password = getpass.getpass("New password: ")
        if password != getpass.getpass("Again: "):
            sys.exit("The passwords don't match.")
        if len(password) < auth.MIN_PASSWORD:
            sys.exit(f"Use at least {auth.MIN_PASSWORD} characters.")
        user.password_hash = auth.hash_password(password)
        db.add(user)
        db.commit()
        auth.end_sessions(db, user.id)
        print("Password changed; every device is signed out.")
