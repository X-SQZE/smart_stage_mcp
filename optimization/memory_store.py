"""Mémoire de conversation légère, stockée dans la base SQLite partagée.

Le projet n'ayant pas de "Memory Manager" préexistant, ce module en
fournit une version minimale : quelques échanges récents par
`conversation_id`, utilisés par `context_builder.py` comme une des
sources de contexte. Réutilise `optimization/db.py`, aucune nouvelle
base n'est créée.
"""
from __future__ import annotations

import logging
import time

from .db import get_connection

logger = logging.getLogger(__name__)

_TABLE_READY = False


def ensure_table() -> None:
    global _TABLE_READY
    if _TABLE_READY:
        return
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS conversation_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
        """
    )
    conn.commit()
    _TABLE_READY = True


def add_entry(conversation_id: str, role: str, content: str) -> None:
    """Ajoute un échange à la mémoire d'une conversation."""
    ensure_table()
    conn = get_connection()
    conn.execute(
        "INSERT INTO conversation_memory (conversation_id, role, content, timestamp) "
        "VALUES (?, ?, ?, ?)",
        (conversation_id, role, content, time.strftime("%Y-%m-%dT%H:%M:%S")),
    )
    conn.commit()


def get_recent(conversation_id: str, limit: int = 5) -> list[dict]:
    """Retourne les derniers échanges d'une conversation, du plus ancien au plus récent."""
    ensure_table()
    conn = get_connection()
    rows = conn.execute(
        "SELECT role, content, timestamp FROM conversation_memory "
        "WHERE conversation_id = ? ORDER BY id DESC LIMIT ?",
        (conversation_id, limit),
    ).fetchall()
    return [dict(r) for r in reversed(rows)]
