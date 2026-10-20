"""Accounts and sessions (lib/auth.ts). Passwords are hashed with scrypt, as
Better Auth does; a sign-in lasts 30 days from the last visit."""

import hashlib
import hmac
import secrets
import uuid
from datetime import timedelta

from fastapi import Depends, HTTPException, Request
from sqlmodel import Session, delete, func, select

from .config import config
from .db import get_session
from .models import Session as UserSession
from .models import User, now

COOKIE = "bookplate_session"
SESSION_DAYS = 30
MIN_PASSWORD = 8


class AuthError(Exception):
    pass


def _scrypt(password: str, salt: str) -> str:
    key = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=16, p=1, dklen=64, maxmem=64 * 1024 * 1024)
    return key.hex()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    return f"{salt}:{_scrypt(password, salt)}"


def verify_password(password: str, stored: str) -> bool:
    salt, key = stored.split(":", 1)
    return hmac.compare_digest(_scrypt(password, salt), key)


def has_users(db: Session) -> bool:
    return db.exec(select(func.count()).select_from(User)).one() > 0


def can_sign_up(db: Session) -> bool:
    """The first visit creates the owner's account; after that only with REGISTRATION=open."""
    return config.registration_open or not has_users(db)


def sign_up(db: Session, name: str, email: str, password: str) -> User:
    email = email.strip().lower()
    if not can_sign_up(db):
        raise AuthError("Sign-up is closed on this Bookplate.")
    if not name.strip() or "@" not in email:
        raise AuthError("Enter your name and a valid email.")
    if len(password) < MIN_PASSWORD:
        raise AuthError(f"Use at least {MIN_PASSWORD} characters for the password.")
    if db.exec(select(User).where(User.email == email)).first():
        raise AuthError("An account with that email already exists.")
    user = User(id=uuid.uuid4().hex, name=name.strip(), email=email, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    return user


def sign_in(db: Session, email: str, password: str) -> User:
    user = db.exec(select(User).where(User.email == email.strip().lower())).first()
    if not user or not verify_password(password, user.password_hash):
        raise AuthError("Wrong email or password.")
    return user


def change_password(db: Session, user: User, current: str, new: str) -> None:
    if not verify_password(current, user.password_hash):
        raise AuthError("The current password is wrong.")
    if len(new) < MIN_PASSWORD:
        raise AuthError(f"Use at least {MIN_PASSWORD} characters for the password.")
    user.password_hash = hash_password(new)
    db.add(user)
    db.commit()


def create_session(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    db.add(UserSession(token=token, user_id=user.id, expires_at=now() + timedelta(days=SESSION_DAYS)))
    db.commit()
    return token


def end_sessions(db: Session, user_id: str, token: str | None = None) -> None:
    """Ends one session, or every session of the account."""
    q = delete(UserSession).where(UserSession.user_id == user_id)
    db.exec(q.where(UserSession.token == token) if token else q)
    db.commit()


def set_cookie(response, token: str) -> None:
    response.set_cookie(
        COOKIE, token, max_age=SESSION_DAYS * 86400, httponly=True, samesite="lax", secure=config.secure_cookies
    )


def user_from_request(request: Request, db: Session) -> User | None:
    token = request.cookies.get(COOKIE)
    session = db.get(UserSession, token) if token else None
    if not session or session.expires_at < now():
        return None
    user = db.get(User, session.user_id)
    # Slide the expiry and mark the account seen, at most once a day.
    if user and session.expires_at - now() < timedelta(days=SESSION_DAYS - 1):
        session.expires_at = now() + timedelta(days=SESSION_DAYS)
        user.last_seen_at = now()
        db.add_all([session, user])
        db.commit()
        request.state.renew_session = token  # the app's middleware re-sends the cookie with the new expiry
    return user


class LoginRequired(Exception):
    """Raised by page dependencies; the app turns it into a redirect to /login."""


def require_user(request: Request, db: Session = Depends(get_session)) -> User:
    """For JSON API routes: 401 when signed out."""
    user = user_from_request(request, db)
    if not user:
        raise HTTPException(401, "Sign in first")
    return user


def page_user(request: Request, db: Session = Depends(get_session)) -> User:
    """For pages: redirects to the sign-in page when signed out."""
    user = user_from_request(request, db)
    if not user:
        raise LoginRequired()
    return user
