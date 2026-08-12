"""Outils MCP de la couche d'optimisation IA.

Ce module n'ajoute aucune logique métier : il expose seulement les
trois outils MCP demandés (`token_usage_report`, `explain_token_usage`,
`optimize_context`) au-dessus de `optimization/token_monitor.py`,
`optimization/context_builder.py` et `optimization/context_optimizer.py`.

Il est importé une seule fois, à la toute fin de `mon_serveur.py`
(après la création de l'instance `mcp` et du pipeline RAG), pour
enregistrer ces outils sur l'instance FastMCP déjà existante — aucun
nouveau serveur n'est créé.
"""
from __future__ import annotations

from typing import Any

from mon_serveur import mcp  # instance FastMCP partagée, déjà créée

from optimization import build_context, optimize, token_monitor


@mcp.tool()
def token_usage_report() -> dict[str, Any]:
    """Rapport global de consommation de tokens: requêtes, coûts, outils."""
    return token_monitor.get_usage_report()


@mcp.tool()
def explain_token_usage(request_id: str) -> dict[str, Any]:
    """Explique pourquoi une requête (`request_id`) a consommé autant de tokens."""
    detail = token_monitor.get_request_detail(request_id)
    if detail is None:
        return {"error": f"Aucune requête trouvée pour request_id={request_id}"}

    breakdown = detail.get("context_breakdown") or {}
    optimization = detail.get("optimization")

    suggestions: list[str] = []
    if optimization:
        if optimization["removed_chunks"]:
            suggestions.append(
                f"{len(optimization['removed_chunks'])} chunk(s) redondant(s) ou hors "
                "budget ont déjà été retirés par context_optimizer.py."
            )
        if optimization["compressed_resources"]:
            suggestions.append(
                f"{len(optimization['compressed_resources'])} ressource(s) volumineuse(s) "
                "ont été compressées automatiquement."
            )
        if not optimization["removed_chunks"] and not optimization["compressed_resources"]:
            suggestions.append("Le contexte était déjà compact, aucune optimisation supplémentaire trouvée.")
    else:
        suggestions.append(
            "Cette requête n'est pas passée par context_optimizer.py: "
            "appeler optimize_context() sur la même tâche permettrait d'estimer les économies possibles."
        )

    return {
        "request_id": request_id,
        "mcp_tool": detail["mcp_tool"],
        "user_task": detail["user_task"],
        "prompt_tokens": detail["prompt_tokens"],
        "completion_tokens": detail["completion_tokens"],
        "total_tokens": detail["total_tokens"],
        "estimated_cost": detail["estimated_cost"],
        "prompt_breakdown": {
            "rag_chunks": breakdown.get("rag_chunks", 0),
            "resource_chunks": breakdown.get("resource_chunks", 0),
            "memory_chunks": breakdown.get("memory_chunks", 0),
            "sources": breakdown.get("sources", []),
        },
        "retrieved_resources": [s for s, kind in breakdown.get("sources", []) if kind == "resource"],
        "memory_usage": breakdown.get("memory_chunks", 0),
        "rag_chunks": breakdown.get("rag_chunks", 0),
        "optimization_suggestions": suggestions,
        "estimated_token_savings": optimization["tokens_saved"] if optimization else 0,
    }


@mcp.tool()
def optimize_context(task: str, mcp_tool: str = "manual", token_budget: int = 3000) -> dict[str, Any]:
    """Lance context_optimizer.py indépendamment pour une tâche donnée."""
    raw = build_context(task=task, mcp_tool=mcp_tool)
    result = optimize(raw, token_budget=token_budget)
    return {
        "original_tokens": result.original_tokens,
        "final_tokens": result.final_tokens,
        "tokens_saved": result.tokens_saved,
        "selected_chunks": result.selected_chunks,
        "removed_chunks": result.removed_chunks,
        "compressed_resources": result.compressed_resources,
    }
