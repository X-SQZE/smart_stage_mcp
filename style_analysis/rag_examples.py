"""Collecte des 'Representative Examples' du Project Style Analyzer.

Réutilise le retriever RAG déjà chargé dans `mon_serveur.py`
(`_rag_retriever`, même index LlamaIndex que `search_code()`) plutôt que de
re-télécharger et ré-indexer des fichiers : chaque catégorie de convention
est illustrée par les extraits de code les plus proches d'une requête
sémantique ciblée, déjà présents dans l'index.
"""
from __future__ import annotations

from typing import Any, Callable

RetrieverFn = Callable[[str], list[dict[str, Any]]]

# Une requête sémantique ciblée par catégorie, pour aller chercher dans
# l'index RAG déjà construit des extraits représentatifs de chaque
# convention plutôt qu'une seule recherche générique.
_CATEGORY_QUERIES: dict[str, str] = {
    "controller_pattern": "Spring Boot REST controller class handling HTTP requests",
    "service_pattern": "Spring Boot service class with business logic",
    "repository_pattern": "Spring Data JPA repository interface",
    "exception_hierarchy": "custom exception class extending a base exception",
    "dependency_injection_style": "constructor dependency injection Spring component",
    "logging_style": "class using Slf4j logger",
    "test_organization": "JUnit test class with assertions",
    "docstring_format": "class or method with a Javadoc comment",
}


def collect_representative_examples(
    retriever: RetrieverFn, max_examples_per_category: int = 2
) -> dict[str, list[dict[str, Any]]]:
    """Interroge le retriever RAG une fois par catégorie et renvoie, pour
    chacune, un court extrait représentatif avec sa source."""
    examples: dict[str, list[dict[str, Any]]] = {}
    for category, query in _CATEGORY_QUERIES.items():
        try:
            chunks = retriever(query) or []
        except Exception:
            chunks = []
        picked = []
        for chunk in chunks[:max_examples_per_category]:
            text = (chunk.get("text") or "").strip()
            picked.append(
                {
                    "source": chunk.get("source", "unknown"),
                    "score": chunk.get("score"),
                    "snippet": text[:400],
                }
            )
        if picked:
            examples[category] = picked
    return examples
