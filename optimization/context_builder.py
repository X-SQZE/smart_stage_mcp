"""Construction du contexte IA.

Point d'entrée unique que tous les outils MCP doivent utiliser pour
assembler leur contexte, au lieu de le faire manuellement. Rassemble :

- les résultats de récupération RAG (via une fonction injectée, pour ne
  pas dupliquer le pipeline LlamaIndex déjà chargé dans mon_serveur.py)
- les ressources du projet (ressources-Smartstage/*.md)
- la mémoire de conversation (optimization/memory_store.py)
- les templates de prompt (prompts/*.md)

Retourne un objet `RawContext` structuré, qui est ensuite passé à
`context_optimizer.optimize()`.
"""
from __future__ import annotations

import glob
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable

from . import memory_store
from .token_utils import estimate_tokens

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESSOURCES_DIR = os.path.join(BASE_DIR, "ressources-Smartstage")
PROMPTS_DIR = os.path.join(BASE_DIR, "prompts")

# Fonction injectée par l'appelant (mon_serveur.py) pour interroger le
# pipeline RAG déjà chargé, sans dépendance circulaire ni double
# initialisation de l'index LlamaIndex.
RetrieverFn = Callable[[str], list[dict[str, Any]]]


@dataclass
class ContextChunk:
    text: str
    source: str
    kind: str  # "rag" | "resource" | "memory" | "prompt"
    score: float = 0.0


@dataclass
class RawContext:
    task: str
    mcp_tool: str
    conversation_id: str
    chunks: list[ContextChunk] = field(default_factory=list)

    def total_tokens(self) -> int:
        return sum(estimate_tokens(c.text) for c in self.chunks)


def _load_resources(keywords: list[str] | None) -> list[ContextChunk]:
    chunks: list[ContextChunk] = []
    if not os.path.isdir(RESSOURCES_DIR):
        return chunks
    for path in sorted(glob.glob(os.path.join(RESSOURCES_DIR, "*.md"))):
        name = os.path.basename(path)
        if keywords and not any(k.lower() in name.lower() for k in keywords):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except OSError as exc:
            logger.warning("Impossible de lire la ressource %s: %s", path, exc)
            continue
        chunks.append(ContextChunk(text=text, source=name, kind="resource"))
    return chunks


def _load_prompt_template(filename: str | None) -> ContextChunk | None:
    if not filename:
        return None
    path = os.path.join(PROMPTS_DIR, filename)
    if not os.path.isfile(path):
        logger.warning("Template de prompt introuvable: %s", path)
        return None
    with open(path, encoding="utf-8") as f:
        text = f.read()
    return ContextChunk(text=text, source=filename, kind="prompt")


def _load_rag(task: str, retriever_fn: RetrieverFn | None) -> list[ContextChunk]:
    if retriever_fn is None:
        return []
    try:
        nodes = retriever_fn(task)
    except Exception as exc:
        logger.warning("Échec de la récupération RAG: %s", exc)
        return []
    chunks = []
    for node in nodes:
        text = node.get("text", "")
        if not text:
            continue
        chunks.append(
            ContextChunk(
                text=text,
                source=node.get("source", "rag_chunk"),
                kind="rag",
                score=float(node.get("score") or 0.0),
            )
        )
    return chunks


def _load_memory(conversation_id: str, limit: int) -> list[ContextChunk]:
    try:
        entries = memory_store.get_recent(conversation_id, limit=limit)
    except Exception as exc:
        logger.warning("Échec de lecture de la mémoire de conversation: %s", exc)
        return []
    return [
        ContextChunk(text=f"[{e['role']}] {e['content']}", source="memory", kind="memory")
        for e in entries
    ]


def build_context(
    task: str,
    mcp_tool: str,
    conversation_id: str = "default",
    retriever_fn: RetrieverFn | None = None,
    resource_keywords: list[str] | None = None,
    prompt_template_file: str | None = None,
    include_memory: bool = True,
    memory_limit: int = 5,
) -> RawContext:
    """Assemble le contexte brut (non optimisé) pour une tâche donnée.

    `retriever_fn(task)` doit retourner une liste de dicts
    `{"text": ..., "source": ..., "score": ...}` — voir l'exemple
    d'intégration dans `search_code` (mon_serveur.py).
    """
    context = RawContext(task=task, mcp_tool=mcp_tool, conversation_id=conversation_id)
    context.chunks.extend(_load_rag(task, retriever_fn))
    context.chunks.extend(_load_resources(resource_keywords))
    if include_memory:
        context.chunks.extend(_load_memory(conversation_id, memory_limit))
    template_chunk = _load_prompt_template(prompt_template_file)
    if template_chunk:
        context.chunks.append(template_chunk)
    return context
