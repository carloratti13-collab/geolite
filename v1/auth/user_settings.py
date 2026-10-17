"""Impostazioni per-utente (API key AI) sullo stesso SQLite degli account.

Le chiavi API sono dati sensibili dell'utente locale: vengono salvate in
chiaro solo nel database locale dell'installazione (come v0.1 faceva con le
preferenze), mai trasmesse altrove se non al provider AI configurato.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .auth import _connect, _normalize_username

_TABLE = """CREATE TABLE IF NOT EXISTS user_ai_settings (
    username TEXT PRIMARY KEY COLLATE NOCASE,
    api_key TEXT NOT NULL DEFAULT '',
    base_url TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT ''
)"""


def _ensure_table(connection: sqlite3.Connection) -> None:
    connection.execute(_TABLE)


def save_ai_settings(
    username: str,
    api_key: str = "",
    base_url: str = "",
    model: str = "",
    db_path: str | Path | None = None,
) -> None:
    """Salva (o sostituisce) le impostazioni AI dell'utente.

    ATTENZIONE: è una sostituzione completa della riga — i campi non passati
    (es. api_key="") vengono SOVRASCRITTI con il valore di default vuoto.
    Per aggiornare un solo campo, leggere prima con load_ai_settings e
    risalvare tutti e tre i valori.
    """
    from datetime import datetime, timezone

    normalized = _normalize_username(username)
    with _connect(db_path) as connection:
        _ensure_table(connection)
        connection.execute(
            """INSERT INTO user_ai_settings (username, api_key, base_url, model, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(username) DO UPDATE SET
                 api_key = excluded.api_key,
                 base_url = excluded.base_url,
                 model = excluded.model,
                 updated_at = excluded.updated_at""",
            (
                normalized,
                api_key.strip(),
                base_url.strip(),
                model.strip(),
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def load_ai_settings(username: str, db_path: str | Path | None = None) -> dict[str, str]:
    """Ritorna {api_key, base_url, model} dell'utente; vuoto se non salvate."""
    normalized = _normalize_username(username)
    with _connect(db_path) as connection:
        _ensure_table(connection)
        record = connection.execute(
            "SELECT api_key, base_url, model FROM user_ai_settings WHERE username = ?",
            (normalized,),
        ).fetchone()
    if record is None:
        return {"api_key": "", "base_url": "", "model": ""}
    return {"api_key": record[0] or "", "base_url": record[1] or "", "model": record[2] or ""}


def delete_ai_settings(username: str, db_path: str | Path | None = None) -> None:
    """Rimuove le impostazioni AI dell'utente (es. con l'eliminazione account)."""
    normalized = _normalize_username(username)
    with _connect(db_path) as connection:
        _ensure_table(connection)
        connection.execute("DELETE FROM user_ai_settings WHERE username = ?", (normalized,))
