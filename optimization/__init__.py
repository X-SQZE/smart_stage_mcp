"""Couche légère d'optimisation IA pour SmartStage MCP.

Se place entre le pipeline RAG existant et le LLM, sans créer de
nouveau serveur ni modifier le workflow existant :

    Outil MCP -> context_builder.build_context()
              -> context_optimizer.optimize()
              -> LLM
              -> token_monitor.record_request()

Voir `search_code` dans mon_serveur.py pour l'exemple d'intégration.
"""
from __future__ import annotations

from . import token_monitor
from .context_builder import ContextChunk, RawContext, build_context
from .context_optimizer import DEFAULT_TOKEN_BUDGET, OptimizedContext, optimize
from .token_utils import estimate_tokens

__all__ = [
    "build_context",
    "RawContext",
    "ContextChunk",
    "optimize",
    "OptimizedContext",
    "DEFAULT_TOKEN_BUDGET",
    "token_monitor",
    "estimate_tokens",
]
