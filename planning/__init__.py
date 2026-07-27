"""Automatic Code Planner pour SmartStage MCP.

Avant toute génération de code, ce paquet analyse le dépôt existant puis
produit un plan d'exécution structuré (JSON) exposé par l'unique outil MCP
`generate_execution_plan` (voir `planner_tools.py` à la racine du dépôt).

Workflow :

    Feature Request
        -> Repository Analysis    (repository_analyzer.analyze_repository_structure)
        -> RAG Retrieval          (mon_serveur._rag_retriever, pipeline déjà chargé)
        -> Architecture Analysis  (repository_analyzer.find_related_code_and_modules)
        -> Dependency Analysis    (repository_analyzer.analyze_dependencies)
        -> Execution Plan         (plan_builder.build_execution_plan)

Ce paquet ne réimplémente rien de ce qui existe déjà :
- le pipeline RAG LlamaIndex déjà chargé dans `mon_serveur.py` ;
- les outils GitHub déjà présents (`list_repository_tree`, `fetch_github_doc`,
  `guide_smartstage_contributor`, `get_smartstage_overview`) ;
- la couche d'optimisation de contexte (`optimization/`), pour la
  déduplication, le classement et le respect du budget de tokens, ainsi que
  le monitoring (`token_monitor`).

Aucun nouveau serveur, index ou client LLM n'est créé par ce paquet.
"""
from __future__ import annotations

from .plan_builder import PLAN_JSON_SCHEMA_KEYS, build_execution_plan
from .repository_analyzer import (
    analyze_dependencies,
    analyze_repository_structure,
    find_related_code_and_modules,
)

__all__ = [
    "build_execution_plan",
    "PLAN_JSON_SCHEMA_KEYS",
    "analyze_repository_structure",
    "find_related_code_and_modules",
    "analyze_dependencies",
]
