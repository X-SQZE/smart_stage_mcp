"""Connexion SQLite partagée pour la couche d'optimisation IA.

Le projet SmartStage MCP ne contenait pas encore de base SQLite au
moment de l'écriture de ce module : il n'y avait ni fichier .db, ni
"Memory Manager". Ce module crée donc une seule base
(`smartstage_mcp.db`, à la racine du dépôt) qui est ensuite réutilisée
par tout le reste de `optimization/` (monitoring des tokens, mémoire de
conversation légère). Aucune autre base n'est créée ailleurs dans le
projet : c'est le point d'entrée SQLite unique de la couche
d'optimisation.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import threading

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "smartstage_mcp.db")

_lock = threading.Lock()
_connection: sqlite3.Connection | None = None


def get_connection() -> sqlite3.Connection:
    """Retourne la connexion SQLite partagée (créée au premier appel)."""
    global _connection
    with _lock:
        if _connection is None:
            logger.debug("Ouverture de la base SQLite d'optimisation: %s", DB_PATH)
            _connection = sqlite3.connect(DB_PATH, check_same_thread=False)
            _connection.row_factory = sqlite3.Row
            _connection.execute("PRAGMA journal_mode=WAL;")
        return _connection
