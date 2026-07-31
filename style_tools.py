"""Outil MCP du Project Style Analyzer.

Ce module n'ajoute aucune logique métier propre : il expose seulement
l'outil MCP `learn_project_style` demandé, au-dessus de `style_analysis/`,
qui réutilise lui-même le pipeline RAG, les outils GitHub, la connexion
SQLite partagée et la couche `optimization/` déjà présents dans
`mon_serveur.py`.

Importé une seule fois, à la toute fin de `mon_serveur.py` (après
`planner_tools`), pour enregistrer cet outil sur l'instance FastMCP déjà
existante — aucun nouveau serveur n'est créé.
"""
from __future__ import annotations

from typing import Any

from mon_serveur import mcp  # instance FastMCP partagée, déjà créée

from style_analysis import learn_project_style as _learn_project_style


@mcp.tool()
async def learn_project_style(ref: str = "main") -> dict[str, Any]:
    """Analyse le dépôt SmartStage pour apprendre ses conventions de code
    (organisation des dossiers, nommage de classes/fonctions, style
    d'injection de dépendances, hiérarchie d'exceptions, logging,
    docstrings, type hints, patterns repository/service/controller,
    organisation des tests, imports, formatage) et stocke le profil appris
    en SQLite. Chaque appel affine le profil déjà stocké plutôt que de
    l'écraser : le profil s'améliore quand le dépôt évolue.

    Retourne : `detected_conventions` (une entrée par convention, avec
    description, score de confiance et exemples), `confidence_score`
    (score global pondéré), `representative_examples` (extraits de code
    issus du pipeline RAG existant) et `suggested_style_guide` (guide de
    style Markdown prêt à être utilisé par une IA générant du code pour ce
    projet).
    """
    return await _learn_project_style(ref=ref)
