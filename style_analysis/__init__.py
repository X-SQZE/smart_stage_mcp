"""Project Style Analyzer pour SmartStage MCP.

Apprend les conventions de code utilisées dans le dépôt (organisation des
dossiers, nommage, injection de dépendances, hiérarchie d'exceptions,
logging, docstrings, type hints, patterns repository/service/controller,
organisation des tests, imports, formatage) et stocke un profil de style en
SQLite, exposé par l'unique outil MCP `learn_project_style()` (voir
`style_tools.py` à la racine du dépôt).

Pipeline :

    learn_project_style()
        -> Repository scan (chemins)       repository_scanner.scan_repository_structure
        -> Content pattern analysis        content_pattern_analyzer.analyze_code_patterns
        -> RAG representative examples     rag_examples.collect_representative_examples
        -> Fusion incrémentale + stockage  store (SQLite, réutilise optimization/db.py)
        -> Synthèse du guide de style      LLM (best-effort, repli déterministe sinon)

Ce paquet ne réimplémente rien de ce qui existe déjà :
- le pipeline RAG LlamaIndex déjà chargé dans `mon_serveur.py` ;
- les outils GitHub déjà présents (`list_repository_tree`, `fetch_github_doc`) ;
- `planning.repository_analyzer.analyze_repository_structure` (Automatic
  Code Planner), réutilisé pour la structure de base du dépôt ;
- la connexion SQLite partagée et la couche d'optimisation de contexte
  (`optimization/`), y compris le monitoring (`token_monitor`).

Chaque appel de `learn_project_style()` affine le profil déjà stocké plutôt
que de l'écraser : il s'améliore au fil des évolutions du dépôt.
"""
from __future__ import annotations

from .style_learner import CONVENTION_CATEGORIES, learn_project_style

__all__ = ["learn_project_style", "CONVENTION_CATEGORIES"]
