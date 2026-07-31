"""Orchestrateur du Project Style Analyzer : `learn_project_style()`.

Pipeline :

    (déclenché à la demande, via l'outil MCP)
        -> Repository scan (Tier 1: chemins)      style_analysis.repository_scanner
        -> Content pattern analysis (Tier 2)       style_analysis.content_pattern_analyzer
        -> RAG representative examples             style_analysis.rag_examples (mon_serveur._rag_retriever)
        -> Merge incrémental avec le profil stocké  style_analysis.store (SQLite, optimization/db.py)
        -> Synthèse d'un guide de style (LLM)       optimization/ (context_builder, context_optimizer, token_monitor)

Comme pour `planning/plan_builder.py`, un seul appel LLM est fait, et
uniquement pour rédiger une version lisible du guide de style : un guide de
repli déterministe (construit uniquement à partir des conventions
détectées) est toujours disponible, même si le LLM échoue ou n'est pas
configuré — le profil de conventions structuré, lui, ne dépend jamais du LLM.

Les imports vers `mon_serveur` sont tardifs pour la même raison que dans
`planning/plan_builder.py` : `mon_serveur.py` importe ce paquet en tout
dernier, via `style_tools.py`.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from optimization import estimate_tokens, optimize, token_monitor
from optimization.context_builder import ContextChunk, RawContext

from . import store
from .content_pattern_analyzer import analyze_code_patterns
from .rag_examples import collect_representative_examples
from .repository_scanner import scan_repository_structure

logger = logging.getLogger(__name__)

MCP_TOOL_NAME = "learn_project_style"
DEFAULT_TOKEN_BUDGET = 4000

CONVENTION_CATEGORIES: tuple[str, ...] = (
    "folder_organization",
    "naming_conventions",
    "class_naming",
    "function_naming",
    "dependency_injection_style",
    "exception_hierarchy",
    "logging_style",
    "docstring_format",
    "type_hints",
    "repository_pattern",
    "service_pattern",
    "controller_pattern",
    "test_organization",
    "imports",
    "code_formatting",
)

_STYLE_GUIDE_SYSTEM_PROMPT = """Tu es un architecte logiciel senior sur le projet SmartStage. On te donne \
un profil de conventions de code détectées automatiquement dans le dépôt (avec un score de confiance et \
des exemples pour chacune), ainsi que des extraits de code représentatifs. Rédige un GUIDE DE STYLE court \
et actionnable pour ce projet, à destination d'une IA qui génère du code : une section par convention \
listée, chacune formulée comme une règle à suivre (pas une description passive). N'invente rien qui ne \
soit pas soutenu par le contexte fourni ; si la confiance d'une convention est faible, formule la règle \
avec prudence (« semble préférer », « à confirmer ») plutôt que comme une certitude. Réponds en Markdown, \
sans préambule."""


def _merge_tier_findings(scan: dict[str, Any], content: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    findings = dict(scan["conventions"])  # folder_organization, naming_conventions, test_organization
    findings.update(content)  # les 12 autres catégories
    return findings


def _build_deterministic_style_guide(merged_profile: dict[str, dict[str, Any]]) -> str:
    lines = ["# Guide de style SmartStage (généré automatiquement)", ""]
    for key in CONVENTION_CATEGORIES:
        entry = merged_profile.get(key)
        if not entry:
            continue
        confidence_pct = round(entry.get("confidence", 0.0) * 100)
        lines.append(f"## {key.replace('_', ' ').title()} (confiance {confidence_pct}%)")
        lines.append(f"- {entry.get('description', '')}")
        lines.append("")
    return "\n".join(lines).strip()


def _build_raw_context(
    merged_profile: dict[str, dict[str, Any]],
    representative_examples: dict[str, list[dict[str, Any]]],
) -> RawContext:
    context = RawContext(task="learn_project_style", mcp_tool=MCP_TOOL_NAME, conversation_id="default")
    context.chunks.append(
        ContextChunk(
            text=json.dumps(merged_profile, ensure_ascii=False, indent=2),
            source="detected_conventions",
            kind="resource",
        )
    )
    for category, examples in representative_examples.items():
        for example in examples:
            context.chunks.append(
                ContextChunk(
                    text=f"[{category}] {example.get('snippet', '')}",
                    source=example.get("source", category),
                    kind="rag",
                    score=float(example.get("score") or 0.0),
                )
            )
    return context


def _overall_confidence(merged_profile: dict[str, dict[str, Any]]) -> float:
    weighted_sum, total_weight = 0.0, 0
    for entry in merged_profile.values():
        weight = max(entry.get("sample_size", 0), 1)
        weighted_sum += entry.get("confidence", 0.0) * weight
        total_weight += weight
    return round(weighted_sum / total_weight, 4) if total_weight else 0.0


async def learn_project_style(ref: str = "main") -> dict[str, Any]:
    """Exécute le pipeline complet et renvoie le profil de style appris.

    Chaque appel affine le profil déjà stocké en base (voir
    `style_analysis/store.py`) au lieu de le remplacer : le profil
    s'améliore au fil des exécutions, à mesure que le dépôt évolue.
    """
    from mon_serveur import Settings, _rag_retriever, configu

    start = time.perf_counter()
    run_id = token_monitor.new_request_id()

    # 1) Repository scan (Tier 1 : chemins uniquement)
    scan = scan_repository_structure(ref=ref)
    # 2) Content pattern analysis (Tier 2 : contenu d'un échantillon borné)
    content_findings = analyze_code_patterns(scan["candidate_paths"])
    # 3) RAG representative examples (réutilise le retriever déjà chargé)
    representative_examples = collect_representative_examples(_rag_retriever)

    raw_findings = _merge_tier_findings(scan, content_findings)

    # 4) Fusion incrémentale avec le profil déjà persisté (SQLite)
    merged_profile: dict[str, dict[str, Any]] = {}
    for key in CONVENTION_CATEGORIES:
        finding = raw_findings.get(key)
        if not finding:
            continue
        merged_profile[key] = store.upsert_convention(
            key,
            category=finding.get("category", key),
            description=finding.get("description", ""),
            confidence=finding.get("confidence", 0.0),
            sample_size=finding.get("sample_size", 0),
            examples=finding.get("examples", []),
        )

    overall_confidence = _overall_confidence(merged_profile)
    deterministic_guide = _build_deterministic_style_guide(merged_profile)

    # 5) Synthèse du guide de style par le LLM (best-effort ; repli déterministe sinon)
    raw_context = _build_raw_context(merged_profile, representative_examples)
    optimized = optimize(raw_context, token_budget=DEFAULT_TOKEN_BUDGET)
    prompt = f"{_STYLE_GUIDE_SYSTEM_PROMPT}\n\nContexte :\n{optimized.text}\n\nGuide de style :"

    status = "success"
    style_guide = deterministic_guide
    try:
        response = await Settings.llm.acomplete(prompt)
        llm_text = str(response).strip()
        if llm_text:
            style_guide = llm_text
    except Exception:
        logger.exception("Échec de la synthèse LLM du guide de style, repli sur le guide déterministe.")
        status = "llm_fallback"

    response_time_ms = (time.perf_counter() - start) * 1000
    token_monitor.record_request(
        request_id=run_id,
        conversation_id="default",
        mcp_tool=MCP_TOOL_NAME,
        user_task="learn_project_style",
        prompt_tokens=optimized.final_tokens,
        completion_tokens=estimate_tokens(style_guide),
        model=configu.LLM_MODEL_NAME,
        response_time_ms=response_time_ms,
        status=status,
        context_breakdown={
            "rag_chunks": sum(1 for c in raw_context.chunks if c.kind == "rag"),
            "resource_chunks": sum(1 for c in raw_context.chunks if c.kind == "resource"),
            "sources": [[c.source, c.kind] for c in raw_context.chunks],
        },
    )
    token_monitor.record_optimization(run_id, optimized)
    store.record_run(run_id, ref, len(merged_profile), overall_confidence)

    return {
        "run_id": run_id,
        "detected_conventions": merged_profile,
        "confidence_score": overall_confidence,
        "representative_examples": representative_examples,
        "suggested_style_guide": style_guide,
        "profile_history": store.get_run_history(limit=5),
    }
