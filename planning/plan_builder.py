"""Assemblage du plan d'exécution structuré (Automatic Code Planner).

Workflow complet (voir `planner_tools.generate_execution_plan`) :

    Feature Request
        -> Repository Analysis    (planning.repository_analyzer)
        -> RAG Retrieval          (mon_serveur._rag_retriever, déjà chargé)
        -> Architecture Analysis  (planning.repository_analyzer)
        -> Dependency Analysis    (planning.repository_analyzer)
        -> Execution Plan         (ce module)

Le planificateur ne génère jamais de code : un seul appel LLM est fait ici,
avec un prompt qui l'interdit explicitement, pour produire uniquement un
plan JSON structuré. Tout le contexte récupéré passe par
`optimization/context_builder.py` (via un `RawContext` construit à la main
ici, car les sources ne sont pas de simples fichiers `ressources-Smartstage/`)
puis `optimization/context_optimizer.py`, exactement comme pour
`search_code()` dans `mon_serveur.py` — pour éviter de dupliquer la logique
de déduplication / classement / respect du budget de tokens.

Les imports vers `mon_serveur` sont faits à l'intérieur de la fonction
principale (import tardif) pour éviter toute dépendance circulaire au
chargement du module : `mon_serveur.py` importe ce paquet en tout dernier,
via `planner_tools.py`.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from optimization import estimate_tokens, optimize, token_monitor
from optimization.context_builder import ContextChunk, RawContext

from .repository_analyzer import (
    analyze_dependencies,
    analyze_repository_structure,
    find_related_code_and_modules,
)

logger = logging.getLogger(__name__)

MCP_TOOL_NAME = "generate_execution_plan"
DEFAULT_TOKEN_BUDGET = 4000

# Clés exactes attendues dans le plan JSON final.
PLAN_JSON_SCHEMA_KEYS: tuple[str, ...] = (
    "Goal",
    "Required Files",
    "Existing Files to Modify",
    "New Files",
    "Dependencies",
    "Required Resources",
    "Similar Existing Implementations",
    "Risks",
    "Estimated Complexity",
    "Testing Strategy",
    "Documentation Updates",
)

_PLANNER_SYSTEM_PROMPT = """Tu es un architecte logiciel senior sur le projet SmartStage \
(backend Spring Boot, frontend Angular — voir le contexte fourni ci-dessous). On te donne \
une demande de fonctionnalité ainsi que le résultat d'une analyse automatique du dépôt \
existant : modules, code similaire (RAG), tests, dépendances et architecture.

Règle absolue : tu ne dois JAMAIS écrire de code, de pseudo-code, ni de diff. Ta seule \
tâche est de produire un PLAN D'EXÉCUTION structuré. Tu dois toujours préférer étendre un \
module, service, repository, composant ou fichier existant plutôt que d'en créer un \
nouveau — n'ajoute un nouveau fichier que si le contexte fourni montre clairement \
qu'aucun composant existant ne convient.

Réponds UNIQUEMENT avec un objet JSON valide (aucun texte avant ou après, aucun bloc de \
code Markdown), avec exactement ces clés : {schema}

Règles de remplissage :
- "Goal" : une phrase claire résumant l'objectif de la fonctionnalité.
- "Required Files" : tous les fichiers (existants et/ou nouveaux) nécessaires à la tâche.
- "Existing Files to Modify" : uniquement des chemins qui apparaissent dans le contexte \
fourni (fichiers réellement existants du dépôt).
- "New Files" : liste vide si l'existant peut être étendu ; sinon uniquement les nouveaux \
fichiers strictement nécessaires, chacun avec une courte justification.
- "Dependencies" : librairies/packages déjà présents à réutiliser (voir la section \
dépendances du contexte), et seulement si indispensable, les nouvelles dépendances à \
ajouter.
- "Required Resources" : ressources non-code nécessaires (variables d'environnement, \
migrations de base de données, accès API externe, configuration, etc.).
- "Similar Existing Implementations" : fichiers/extraits du contexte RAG qui ressemblent à \
ce qui est demandé, à utiliser comme référence de pattern de code.
- "Risks" : risques techniques ou de régression identifiables à partir du contexte fourni.
- "Estimated Complexity" : "low", "medium" ou "high", avec une courte justification.
- "Testing Strategy" : tests existants à réutiliser/étendre en priorité, puis tests \
manquants à ajouter.
- "Documentation Updates" : fichiers de documentation du dépôt à mettre à jour.
""".format(schema=json.dumps(list(PLAN_JSON_SCHEMA_KEYS), ensure_ascii=False))


def _build_raw_context(
    feature_description: str,
    repo_structure: dict[str, Any],
    related: dict[str, Any],
    dependencies: dict[str, Any],
    rag_chunks: list[dict[str, Any]],
) -> RawContext:
    """Construit le `RawContext` consommé par `optimization.optimize()`.

    Même format que celui produit par `context_builder.build_context()`
    (kinds "rag" / "resource") afin de rester compatible avec la
    déduplication, le classement et le respect du budget de tokens déjà
    implémentés dans `optimization/context_optimizer.py`.
    """
    context = RawContext(task=feature_description, mcp_tool=MCP_TOOL_NAME, conversation_id="default")

    for chunk in rag_chunks:
        context.chunks.append(
            ContextChunk(
                text=chunk.get("text", ""),
                source=chunk.get("source", "rag_chunk"),
                kind="rag",
                score=float(chunk.get("score") or 0.0),
            )
        )

    context.chunks.append(
        ContextChunk(
            text=json.dumps(repo_structure, ensure_ascii=False, indent=2),
            source="repository_analysis",
            kind="resource",
        )
    )
    context.chunks.append(
        ContextChunk(
            text=json.dumps(
                {
                    "relevant_existing_files": related.get("relevant_existing_files"),
                    "matched_module_sections": related.get("matched_module_sections"),
                },
                ensure_ascii=False,
                indent=2,
            ),
            source="architecture_analysis",
            kind="resource",
        )
    )
    if related.get("architecture_summary"):
        context.chunks.append(
            ContextChunk(
                text=related["architecture_summary"],
                source="ressources-Smartstage/architecture.md",
                kind="resource",
            )
        )
    if dependencies.get("dependency_files_content"):
        context.chunks.append(
            ContextChunk(
                text=json.dumps(dependencies["dependency_files_content"], ensure_ascii=False)[:6000],
                source="dependency_analysis",
                kind="resource",
            )
        )
    return context


def _parse_plan_json(raw_text: str) -> dict[str, Any]:
    """Parse la réponse LLM en JSON, avec un repli robuste si elle est
    malformée (ex: entourée de ```json``` malgré la consigne)."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text[:4].lower() == "json":
            text = text[4:]
        text = text.strip()
    try:
        parsed = json.loads(text)
    except (ValueError, TypeError):
        logger.warning("Réponse LLM non-JSON pour %s, repli sur un plan brut.", MCP_TOOL_NAME)
        return {"raw_response": raw_text, "parse_error": True}
    if not isinstance(parsed, dict):
        return {"raw_response": raw_text, "parse_error": True}
    for key in PLAN_JSON_SCHEMA_KEYS:
        parsed.setdefault(key, None)
    return parsed


async def build_execution_plan(feature_description: str) -> dict[str, Any]:
    """Exécute le pipeline complet et renvoie le plan d'exécution structuré.

    Ne génère jamais de code : uniquement le plan JSON (clés
    `PLAN_JSON_SCHEMA_KEYS`), accompagné du détail de chaque étape d'analyse
    pour audit/traçabilité.
    """
    from mon_serveur import Settings, _rag_retriever, configu

    start = time.perf_counter()
    request_id = token_monitor.new_request_id()

    # 1) Repository Analysis
    repo_structure = analyze_repository_structure()
    # 2) RAG Retrieval — réutilise le retriever LlamaIndex déjà chargé dans
    #    mon_serveur.py (même index que search_code), aucune ré-ingestion.
    rag_chunks = _rag_retriever(feature_description)
    # 3) Architecture Analysis
    related = find_related_code_and_modules(feature_description)
    # 4) Dependency Analysis
    dependencies = analyze_dependencies()

    raw_context = _build_raw_context(feature_description, repo_structure, related, dependencies, rag_chunks)
    optimized = optimize(raw_context, token_budget=DEFAULT_TOKEN_BUDGET)

    prompt = (
        f"{_PLANNER_SYSTEM_PROMPT}\n\n"
        f"Contexte du dépôt (résultat de l'analyse automatique) :\n{optimized.text}\n\n"
        f"Demande de fonctionnalité : {feature_description}\n\n"
        "Plan d'exécution (JSON uniquement) :"
    )

    status = "success"
    try:
        response = await Settings.llm.acomplete(prompt)
        plan = _parse_plan_json(str(response))
    except Exception as exc:
        logger.exception("Échec de la génération du plan d'exécution")
        plan = {"error": str(exc)}
        status = "error"

    response_time_ms = (time.perf_counter() - start) * 1000
    token_monitor.record_request(
        request_id=request_id,
        conversation_id="default",
        mcp_tool=MCP_TOOL_NAME,
        user_task=feature_description,
        prompt_tokens=optimized.final_tokens,
        completion_tokens=estimate_tokens(json.dumps(plan, ensure_ascii=False)),
        model=configu.LLM_MODEL_NAME,
        response_time_ms=response_time_ms,
        status=status,
        context_breakdown={
            "rag_chunks": sum(1 for c in raw_context.chunks if c.kind == "rag"),
            "resource_chunks": sum(1 for c in raw_context.chunks if c.kind == "resource"),
            "sources": [[c.source, c.kind] for c in raw_context.chunks],
        },
    )
    token_monitor.record_optimization(request_id, optimized)

    return {
        "request_id": request_id,
        "feature_request": feature_description,
        "workflow": [
            "repository_analysis",
            "rag_retrieval",
            "architecture_analysis",
            "dependency_analysis",
            "execution_plan",
        ],
        "analysis": {
            "repository_analysis": repo_structure,
            "rag_retrieval": {
                "chunks_found": len(rag_chunks),
                "sources": [c.get("source") for c in rag_chunks],
            },
            "architecture_analysis": {
                "relevant_existing_files": related.get("relevant_existing_files"),
                "matched_module_sections_count": len(related.get("matched_module_sections") or []),
            },
            "dependency_analysis": {
                "dependency_files_found": dependencies.get("dependency_files_found"),
            },
        },
        "plan": plan,
    }
