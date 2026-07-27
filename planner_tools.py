"""Outil MCP de l'Automatic Code Planner.

Ce module n'ajoute aucune logique métier propre : il expose seulement
l'outil MCP `generate_execution_plan` demandé, au-dessus de
`planning/repository_analyzer.py` et `planning/plan_builder.py`, qui
réutilisent eux-mêmes le pipeline RAG et les outils GitHub déjà présents
dans `mon_serveur.py`, ainsi que la couche `optimization/` existante.

Il est importé une seule fois, à la toute fin de `mon_serveur.py` (après
`optimization_tools`), pour enregistrer cet outil sur l'instance FastMCP
déjà existante — aucun nouveau serveur n'est créé.
"""
from __future__ import annotations

from typing import Any

from mon_serveur import mcp  # instance FastMCP partagée, déjà créée

from planning.plan_builder import build_execution_plan


@mcp.tool()
async def generate_execution_plan(feature_description: str) -> dict[str, Any]:
    """Analyse le dépôt SmartStage puis génère un plan d'exécution structuré
    pour la fonctionnalité demandée. NE GÉNÈRE JAMAIS DE CODE : uniquement
    un plan JSON, à valider/affiner avant toute implémentation.

    Pipeline : Feature Request -> Repository Analysis -> RAG Retrieval ->
    Architecture Analysis -> Dependency Analysis -> Execution Plan.

    Le plan (clé `plan` du résultat) contient : Goal, Required Files,
    Existing Files to Modify, New Files, Dependencies, Required Resources,
    Similar Existing Implementations, Risks, Estimated Complexity, Testing
    Strategy, Documentation Updates. La clé `analysis` contient le détail de
    chaque étape (fichiers existants trouvés, chunks RAG, dépendances lues)
    pour audit/traçabilité.
    """
    return await build_execution_plan(feature_description)
