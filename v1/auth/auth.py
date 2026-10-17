"""Persistent username/password authentication backed by SQLite."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DATABASE = Path(__file__).resolve().parents[1] / "data" / "geobrain_users.sqlite3"
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]{3,24}$")
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_KEY_LENGTH = 64
DUMMY_SALT = b"GeoBrain-auth-dummy-salt"


class RegistrationError(ValueError):
    """Expected user-facing registration validation error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _database_path(db_path: str | Path | None = None) -> Path:
    configured_path = db_path or os.environ.get("GEOBRAIN_DB_PATH") or DEFAULT_DATABASE
    return Path(configured_path).expanduser().resolve()


def _connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = _database_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.execute("PRAGMA busy_timeout = 10000")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute(
        """CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY COLLATE NOCASE,
            salt BLOB NOT NULL,
            password_hash BLOB NOT NULL,
            created_at TEXT NOT NULL
        )"""
    )
    return connection


def _normalize_username(username: str) -> str:
    return username.strip().lower()


def _validate_credentials(username: str, password: str) -> str:
    normalized_username = _normalize_username(username)
    if not USERNAME_PATTERN.fullmatch(normalized_username):
        raise RegistrationError("invalid_username")
    if not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
        raise RegistrationError("invalid_password")
    return normalized_username


def _password_hash(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_KEY_LENGTH,
        maxmem=64 * 1024 * 1024,
    )


def register_user(username: str, password: str, db_path: str | Path | None = None) -> dict[str, str]:
    normalized_username = _validate_credentials(username, password)
    salt = os.urandom(16)
    password_hash = _password_hash(password, salt)
    created_at = datetime.now(timezone.utc).isoformat()
    with _connect(db_path) as connection:
        try:
            connection.execute(
                "INSERT INTO users (username, salt, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (normalized_username, salt, password_hash, created_at),
            )
        except sqlite3.IntegrityError as error:
            raise RegistrationError("username_taken") from error
    return {"username": normalized_username, "tier": "student"}


def authenticate(username: str, password: str, db_path: str | Path | None = None) -> dict[str, str] | None:
    normalized_username = _normalize_username(username)
    with _connect(db_path) as connection:
        record = connection.execute(
            "SELECT salt, password_hash FROM users WHERE username = ?",
            (normalized_username,),
        ).fetchone()
    if record is None:
        _password_hash(password[:PASSWORD_MAX_LENGTH], DUMMY_SALT)
        return None
    salt, expected_hash = record
    actual_hash = _password_hash(password[:PASSWORD_MAX_LENGTH], salt)
    if not hmac.compare_digest(actual_hash, expected_hash):
        return None
    return {"username": normalized_username, "tier": "student"}


def delete_account(username: str, password: str, db_path: str | Path | None = None) -> bool:
    normalized_username = _normalize_username(username)
    with _connect(db_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        record = connection.execute(
            "SELECT salt, password_hash FROM users WHERE username = ?",
            (normalized_username,),
        ).fetchone()
        if record is None:
            _password_hash(password[:PASSWORD_MAX_LENGTH], DUMMY_SALT)
            return False
        salt, expected_hash = record
        actual_hash = _password_hash(password[:PASSWORD_MAX_LENGTH], salt)
        if not hmac.compare_digest(actual_hash, expected_hash):
            return False
        connection.execute("DELETE FROM users WHERE username = ?", (normalized_username,))
    # Import locale: user_settings importa da auth, un import di modulo
    # creerebbe un circolo.
    from .user_settings import delete_ai_settings

    delete_ai_settings(normalized_username, db_path)
    return True


def logout() -> None:
    import streamlit as st

    st.session_state.pop("user", None)
    st.session_state.pop("qwen-messages", None)