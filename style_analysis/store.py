"""Persistance du profil de style appris (Project Style Analyzer).

Réutilise la connexion SQLite partagée de `optimization/db.py`
(`smartstage_mcp.db`, à la racine du dépôt) : aucune nouvelle base n'est
créée. Deux tables, créées seulement si absentes :

- `style_profile` : une ligne par convention détectée (clé unique
  `convention_key`), avec sa confiance courante et le nombre d'échantillons
  cumulés ayant servi à l'estimer. Chaque nouvel appel de
  `learn_project_style()` met à jour cette ligne par une moyenne pondérée
  (voir `upsert_convention`), plutôt que de l'écraser : le profil
  s'améliore/s'ajuste au fil des exécutions, il ne repart jamais de zéro.
- `style_profile_runs` : historique append-only de chaque exécution de
  l'analyseur, pour suivre l'évolution du profil dans le temps.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from optimization.db import get_connection

logger = logging.getLogger(__name__)

# Plafond sur le nombre d'échantillons cumulés utilisé dans la moyenne
# pondérée : au-delà, les nouvelles observations gardent un poids constant
# plutôt que de peser de moins en moins. Sans ce plafond, un profil ayant
# accumulé des milliers d'échantillons deviendrait quasi figé et
# n'évoluerait plus quand le dépôt change de convention.
MAX_SAMPLE_WEIGHT = 200

_TABLES_READY = False


def ensure_tables() -> None:
    global _TABLES_READY
    if _TABLES_READY:
        return
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS style_profile (
            convention_key TEXT PRIMARY KEY,
            category TEXT,
            description TEXT,
            confidence REAL,
            sample_size INTEGER,
            examples TEXT,
            last_updated TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS style_profile_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT,
            ref TEXT,
            total_conventions INTEGER,
            overall_confidence REAL,
            timestamp TEXT
        )
        """
    )
    conn.commit()
    _TABLES_READY = True


def upsert_convention(
    convention_key: str,
    *,
    category: str,
    description: str,
    confidence: float,
    sample_size: int,
    examples: list[str] | None = None,
) -> dict[str, Any]:
    """Fusionne une observation fraîche avec le profil déjà stocké pour cette
    convention (moyenne pondérée par le nombre d'échantillons), puis
    persiste le résultat. Retourne la ligne fusionnée.

    C'est ce mécanisme qui permet au profil de "s'améliorer quand le dépôt
    évolue" : chaque exécution affine la confiance au lieu de la remplacer.
    """
    ensure_tables()
    conn = get_connection()
    row = conn.execute(
        "SELECT confidence, sample_size FROM style_profile WHERE convention_key = ?",
        (convention_key,),
    ).fetchone()

    sample_size = max(0, sample_size)
    if row is None or row["sample_size"] in (None, 0):
        merged_confidence = confidence
        merged_sample_size = sample_size
    else:
        old_confidence, old_n = row["confidence"], min(row["sample_size"], MAX_SAMPLE_WEIGHT)
        total_n = old_n + sample_size
        merged_confidence = (
            (old_confidence * old_n + confidence * sample_size) / total_n if total_n else confidence
        )
        merged_sample_size = row["sample_size"] + sample_size

    conn.execute(
        """
        INSERT INTO style_profile
            (convention_key, category, description, confidence, sample_size, examples, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(convention_key) DO UPDATE SET
            category=excluded.category,
            description=excluded.description,
            confidence=excluded.confidence,
            sample_size=excluded.sample_size,
            examples=excluded.examples,
            last_updated=excluded.last_updated
        """,
        (
            convention_key,
            category,
            description,
            merged_confidence,
            merged_sample_size,
            json.dumps(examples or [], ensure_ascii=False),
            time.strftime("%Y-%m-%dT%H:%M:%S"),
        ),
    )
    conn.commit()

    return {
        "convention_key": convention_key,
        "category": category,
        "description": description,
        "confidence": round(merged_confidence, 4),
        "sample_size": merged_sample_size,
        "examples": examples or [],
    }


def record_run(run_id: str, ref: str, total_conventions: int, overall_confidence: float) -> None:
    """Journalise une exécution de `learn_project_style()` (best-effort, ne
    lève jamais)."""
    try:
        ensure_tables()
        conn = get_connection()
        conn.execute(
            """
            INSERT INTO style_profile_runs
                (run_id, ref, total_conventions, overall_confidence, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (run_id, ref, total_conventions, overall_confidence, time.strftime("%Y-%m-%dT%H:%M:%S")),
        )
        conn.commit()
    except Exception:
        logger.exception("Échec de l'enregistrement de l'exécution du style analyzer (run_id=%s)", run_id)


def load_profile() -> dict[str, dict[str, Any]]:
    """Retourne le profil de style actuellement persisté, indexé par
    `convention_key`."""
    ensure_tables()
    conn = get_connection()
    rows = conn.execute(
        "SELECT convention_key, category, description, confidence, sample_size, examples, last_updated "
        "FROM style_profile"
    ).fetchall()
    profile: dict[str, dict[str, Any]] = {}
    for row in rows:
        entry = dict(row)
        entry["examples"] = json.loads(entry.get("examples") or "[]")
        profile[entry["convention_key"]] = entry
    return profile


def get_run_history(limit: int = 10) -> list[dict[str, Any]]:
    ensure_tables()
    conn = get_connection()
    rows = conn.execute(
        "SELECT run_id, ref, total_conventions, overall_confidence, timestamp "
        "FROM style_profile_runs ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]
