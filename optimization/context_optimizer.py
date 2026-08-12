"""Optimisation du contexte produit par `context_builder.py`.

Étapes, dans l'ordre :

1. Déduplication des chunks identiques (hash du texte normalisé).
2. Classement par pertinence sémantique (score déjà fourni par le RAG,
   sinon embeddings injectés, sinon repli sur un score par mots-clés).
3. Compression des ressources volumineuses.
4. Sélection des chunks dans la limite du budget de tokens, avec une
   nouvelle passe (compression plus agressive) si le budget est encore
   dépassé.

Retourne un `OptimizedContext` avec le texte final et le détail complet
de ce qui a été gardé/retiré/compressé (utilisé par `explain_token_usage`
et `optimize_context`).
"""
from __future__ import annotations

import hashlib
import logging
import math
import re
from dataclasses import dataclass, field
from typing import Callable

from .context_builder import ContextChunk, RawContext
from .token_utils import estimate_tokens

logger = logging.getLogger(__name__)

EmbedFn = Callable[[str], list[float]]

DEFAULT_TOKEN_BUDGET = 3000
MAX_OPTIMIZATION_PASSES = 3
COMPRESS_THRESHOLD_TOKENS = 400  # ressource compressée au-delà de ce seuil
COMPRESS_KEEP_RATIO = 0.4


@dataclass
class OptimizedContext:
    text: str
    original_tokens: int
    final_tokens: int
    tokens_saved: int
    selected_chunks: list[str] = field(default_factory=list)
    removed_chunks: list[str] = field(default_factory=list)
    compressed_resources: list[str] = field(default_factory=list)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _dedupe(chunks: list[ContextChunk]) -> tuple[list[ContextChunk], list[str]]:
    seen: set[str] = set()
    kept: list[ContextChunk] = []
    removed: list[str] = []
    for chunk in chunks:
        digest = hashlib.sha1(_normalize(chunk.text).encode("utf-8")).hexdigest()
        if digest in seen:
            removed.append(chunk.source)
            continue
        seen.add(digest)
        kept.append(chunk)
    return kept, removed


def _keyword_overlap_score(task: str, text: str) -> float:
    task_words = set(_normalize(task).split())
    if not task_words:
        return 0.0
    text_words = set(_normalize(text).split())
    if not text_words:
        return 0.0
    return len(task_words & text_words) / len(task_words)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _rank(task: str, chunks: list[ContextChunk], embed_fn: EmbedFn | None) -> list[ContextChunk]:
    if embed_fn is not None:
        try:
            task_vec = embed_fn(task)
            for chunk in chunks:
                if chunk.kind == "rag" and chunk.score:
                    continue  # score déjà fourni par le moteur RAG
                chunk.score = _cosine(task_vec, embed_fn(chunk.text[:1000]))
            return sorted(chunks, key=lambda c: c.score, reverse=True)
        except Exception as exc:
            logger.warning("Repli sur le score par mots-clés (embeddings indisponibles): %s", exc)
    for chunk in chunks:
        if chunk.kind == "rag" and chunk.score:
            continue
        chunk.score = _keyword_overlap_score(task, chunk.text)
    return sorted(chunks, key=lambda c: c.score, reverse=True)


def _compress(chunk: ContextChunk) -> ContextChunk:
    if estimate_tokens(chunk.text) <= COMPRESS_THRESHOLD_TOKENS:
        return chunk
    sentences = re.split(r"(?<=[.!?])\s+", chunk.text)
    keep_n = max(1, int(len(sentences) * COMPRESS_KEEP_RATIO))
    compressed_text = " ".join(sentences[:keep_n])
    return ContextChunk(text=compressed_text, source=chunk.source, kind=chunk.kind, score=chunk.score)


def optimize(
    raw: RawContext,
    token_budget: int = DEFAULT_TOKEN_BUDGET,
    embed_fn: EmbedFn | None = None,
) -> OptimizedContext:
    """Déduplique, classe, compresse et fait respecter le budget de tokens."""
    original_tokens = raw.total_tokens()

    chunks, removed = _dedupe(raw.chunks)
    chunks = _rank(raw.task, chunks, embed_fn)

    budget = token_budget
    selected: list[ContextChunk] = []
    budget_removed: list[str] = []
    compressed_sources: list[str] = []
    running_tokens = 0

    for pass_number in range(1, MAX_OPTIMIZATION_PASSES + 1):
        selected, budget_removed, compressed_sources, running_tokens = [], [], [], 0
        for chunk in chunks:
            candidate = chunk
            if chunk.kind == "resource":
                compressed = _compress(chunk)
                if compressed.text != chunk.text:
                    compressed_sources.append(chunk.source)
                    candidate = compressed
            candidate_tokens = estimate_tokens(candidate.text)
            if running_tokens + candidate_tokens > budget:
                budget_removed.append(candidate.source)
                continue
            selected.append(candidate)
            running_tokens += candidate_tokens

        if running_tokens <= token_budget:
            break
        logger.info(
            "Budget de tokens encore dépassé après la passe %s (%s > %s), nouvelle passe.",
            pass_number, running_tokens, token_budget,
        )
        budget = int(budget * 0.8)  # resserre le budget interne pour forcer plus de compression

    text = "\n\n".join(f"[{c.kind}:{c.source}]\n{c.text}" for c in selected)
    final_tokens = estimate_tokens(text)

    return OptimizedContext(
        text=text,
        original_tokens=original_tokens,
        final_tokens=final_tokens,
        tokens_saved=max(0, original_tokens - final_tokens),
        selected_chunks=[c.source for c in selected],
        removed_chunks=removed + budget_removed,
        compressed_resources=compressed_sources,
    )
