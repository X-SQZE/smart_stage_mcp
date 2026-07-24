"""Suivi de la consommation de tokens pour chaque requête LLM.

Réutilise la base SQLite partagée de `optimization/db.py`. Crée
uniquement les tables nécessaires si elles n'existent pas déjà —
aucune autre base n'est créée.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from .db import get_connection

logger = logging.getLogger(__name__)

# Tarifs approximatifs en USD / 1000 tokens. SmartStage utilise Gemini
# (voir llamaindex_pipeline/configu.py -> LLM_MODEL_NAME) : ces valeurs
# sont indicatives et à ajuster selon le tarif réel du modèle utilisé.
PRICING_PER_1K_TOKENS = {
    "default": {"prompt": 0.00015, "completion": 0.0006},
    "models/gemini-3-flash-preview": {"prompt": 0.00015, "completion": 0.0006},
}

_TABLES_READY = False


def ensure_tables() -> None:
    global _TABLES_READY
    if _TABLES_READY:
        return
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS token_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT UNIQUE NOT NULL,
            conversation_id TEXT,
            mcp_tool TEXT,
            user_task TEXT,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            total_tokens INTEGER,
            estimated_cost REAL,
            model TEXT,
            response_time_ms REAL,
            status TEXT,
            timestamp TEXT,
            context_breakdown TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS optimization_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT,
            original_tokens INTEGER,
            final_tokens INTEGER,
            tokens_saved INTEGER,
            selected_chunks TEXT,
            removed_chunks TEXT,
            compressed_resources TEXT,
            timestamp TEXT
        )
        """
    )
    conn.commit()
    _TABLES_READY = True


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    rates = PRICING_PER_1K_TOKENS.get(model, PRICING_PER_1K_TOKENS["default"])
    cost = (prompt_tokens / 1000) * rates["prompt"] + (completion_tokens / 1000) * rates["completion"]
    return round(cost, 6)


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


def record_request(
    *,
    request_id: str,
    conversation_id: str,
    mcp_tool: str,
    user_task: str,
    prompt_tokens: int,
    completion_tokens: int,
    model: str,
    response_time_ms: float,
    status: str = "success",
    context_breakdown: dict[str, Any] | None = None,
) -> None:
    """Enregistre une requête LLM. Ne lève jamais d'exception (best-effort)."""
    try:
        ensure_tables()
        conn = get_connection()
        total_tokens = prompt_tokens + completion_tokens
        conn.execute(
            """
            INSERT OR REPLACE INTO token_usage
                (request_id, conversation_id, mcp_tool, user_task, prompt_tokens,
                 completion_tokens, total_tokens, estimated_cost, model,
                 response_time_ms, status, timestamp, context_breakdown)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id, conversation_id, mcp_tool, user_task,
                prompt_tokens, completion_tokens, total_tokens,
                estimate_cost(model, prompt_tokens, completion_tokens), model,
                response_time_ms, status, time.strftime("%Y-%m-%dT%H:%M:%S"),
                json.dumps(context_breakdown or {}, ensure_ascii=False),
            ),
        )
        conn.commit()
    except Exception:
        logger.exception("Échec de l'enregistrement du monitoring de tokens (request_id=%s)", request_id)


def record_optimization(request_id: str, optimized: Any) -> None:
    """Enregistre le résultat de context_optimizer.optimize() pour une requête."""
    try:
        ensure_tables()
        conn = get_connection()
        conn.execute(
            """
            INSERT INTO optimization_log
                (request_id, original_tokens, final_tokens, tokens_saved,
                 selected_chunks, removed_chunks, compressed_resources, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id, optimized.original_tokens, optimized.final_tokens,
                optimized.tokens_saved,
                json.dumps(optimized.selected_chunks, ensure_ascii=False),
                json.dumps(optimized.removed_chunks, ensure_ascii=False),
                json.dumps(optimized.compressed_resources, ensure_ascii=False),
                time.strftime("%Y-%m-%dT%H:%M:%S"),
            ),
        )
        conn.commit()
    except Exception:
        logger.exception("Échec de l'enregistrement de l'optimisation (request_id=%s)", request_id)


def get_usage_report(recent_limit: int = 5, top_expensive_limit: int = 5) -> dict[str, Any]:
    ensure_tables()
    conn = get_connection()

    totals = conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(total_tokens), 0) AS tokens, "
        "COALESCE(SUM(estimated_cost), 0) AS cost FROM token_usage"
    ).fetchone()
    total_requests = totals["n"]
    total_tokens = totals["tokens"]

    recent = conn.execute(
        "SELECT request_id, mcp_tool, total_tokens, estimated_cost, timestamp "
        "FROM token_usage ORDER BY id DESC LIMIT ?",
        (recent_limit,),
    ).fetchall()

    top_expensive = conn.execute(
        "SELECT request_id, mcp_tool, total_tokens, estimated_cost, timestamp "
        "FROM token_usage ORDER BY estimated_cost DESC LIMIT ?",
        (top_expensive_limit,),
    ).fetchall()

    tool_stats = conn.execute(
        "SELECT mcp_tool, COUNT(*) AS requests, SUM(total_tokens) AS tokens, "
        "SUM(estimated_cost) AS cost FROM token_usage "
        "GROUP BY mcp_tool ORDER BY tokens DESC"
    ).fetchall()

    return {
        "total_requests": total_requests,
        "total_tokens": total_tokens,
        "estimated_cost": round(totals["cost"], 6),
        "average_tokens_per_request": round(total_tokens / total_requests, 2) if total_requests else 0,
        "recent_requests": [dict(r) for r in recent],
        "top_expensive_requests": [dict(r) for r in top_expensive],
        "tool_statistics": [dict(r) for r in tool_stats],
    }


def get_request_detail(request_id: str) -> dict[str, Any] | None:
    ensure_tables()
    conn = get_connection()
    row = conn.execute("SELECT * FROM token_usage WHERE request_id = ?", (request_id,)).fetchone()
    if row is None:
        return None

    request = dict(row)
    request["context_breakdown"] = json.loads(request.get("context_breakdown") or "{}")

    opt_row = conn.execute(
        "SELECT * FROM optimization_log WHERE request_id = ? ORDER BY id DESC LIMIT 1",
        (request_id,),
    ).fetchone()
    optimization = None
    if opt_row is not None:
        optimization = dict(opt_row)
        for key in ("selected_chunks", "removed_chunks", "compressed_resources"):
            optimization[key] = json.loads(optimization.get(key) or "[]")
    request["optimization"] = optimization
    return request
