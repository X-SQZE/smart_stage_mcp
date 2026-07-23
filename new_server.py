"""Serveur MCP SmartStage et Elyora combine.

Ce fichier conserve tous les outils deja valides dans mon_serveur.py, puis ajoute
les ressources et outils SmartStage presents dans le serveur fourni en reference.
"""

from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timedelta
from typing import Any

from mon_serveur import BASE_DIR, mcp
from tools.github_tools import (
    active_repo_full_name,
    fetch_github_doc,
    get_json,
    paginated,
    repo_api_url,
)
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.core import StorageContext, load_index_from_storage, Settings

# Tool de RAG:
sys.path.append(os.path.join(os.path.dirname(__file__), "llamaindex_pipeline"))
import configu

# Configurer les modeles (embedding + LLM)
Settings.embed_model = HuggingFaceEmbedding(model_name=configu.EMBED_MODEL_NAME)
Settings.llm = GoogleGenAI(model=configu.LLM_MODEL_NAME, api_key=configu.GEMINI_API_KEY)

# Charger l'index deja construit par ingest.py
storage_context = StorageContext.from_defaults(persist_dir=configu.STORAGE_DIR)
index = load_index_from_storage(storage_context)

# Creer le query_engine:
query_engine = index.as_query_engine(similarity_top_k=5)


def _extract_markdown_section(content: str, query: str) -> str | None:
    lines = content.splitlines()
    headers: list[tuple[int, int, str]] = []
    for index, line in enumerate(lines):
        match = re.match(r"^(#{2,4})\s+(.*)", line)
        if match:
            headers.append((index, len(match.group(1)), match.group(2).strip()))
    if not headers:
        return None

    query_lower = query.lower()
    match_position = next((pos for pos, (_, _, title) in enumerate(headers) if query_lower in title.lower()), None)
    if match_position is None:
        return None

    start_line, start_level, _ = headers[match_position]
    end_line = len(lines)
    for line_index, level, _ in headers[match_position + 1:]:
        if level <= start_level:
            end_line = line_index
            break
    return "\n".join(lines[start_line:end_line]).strip()


def _grep_markdown(content: str, keyword: str, context: int = 2) -> list[str]:
    lines = content.splitlines()
    keyword_lower = keyword.lower()
    snippets: list[str] = []
    for index, line in enumerate(lines):
        if keyword_lower in line.lower():
            start = max(0, index - context)
            end = min(len(lines), index + context + 1)
            snippets.append("\n".join(lines[start:end]))
    return snippets


def _parse_markdown_table(content: str) -> list[dict[str, str]] | None:
    table_lines = [line for line in content.splitlines() if line.strip().startswith("|")]
    if len(table_lines) < 2:
        return None

    header = [cell.strip() for cell in table_lines[0].strip("|").split("|")]
    rows: list[dict[str, str]] = []
    for line in table_lines[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) == len(header):
            rows.append(dict(zip(header, cells)))
    return rows or None


def _lookup_markdown(content: str, query: str) -> dict[str, Any] | None:
    section = _extract_markdown_section(content, query)
    if section:
        return {"match_type": "section", "content": section}

    table = _parse_markdown_table(content)
    if table:
        query_lower = query.lower()
        rows = [row for row in table if any(query_lower in str(value).lower() for value in row.values())]
        if rows:
            return {"match_type": "table_rows", "rows": rows}

    snippets = _grep_markdown(content, query)
    if snippets:
        return {"match_type": "snippets", "matches": snippets}
    return None


def _parse_commit(commit_data: dict[str, Any]) -> dict[str, Any]:
    commit = commit_data.get("commit", {})
    author_info = commit.get("author", {})
    author_login = (commit_data.get("author") or {}).get("login")
    return {
        "sha": commit_data.get("sha", "")[:10],
        "author": author_login or author_info.get("name") or "inconnu",
        "date": author_info.get("date"),
        "message": (commit.get("message") or "").split("\n")[0],
        "url": commit_data.get("html_url"),
    }


def _read_prompt_file(filename: str, fallback: str) -> str:
    path = os.path.join(BASE_DIR, "prompts", filename)
    if not os.path.exists(path):
        return fallback
    with open(path, encoding="utf-8") as file:
        return file.read()


@mcp.resource("smartstage://docs/readme", mime_type="text/markdown")
def lire_smartstage_readme() -> str:
    return fetch_github_doc("smartstage-docs/README.md")


@mcp.resource("smartstage://docs/architecture", mime_type="text/markdown")
def lire_smartstage_architecture() -> str:
    return fetch_github_doc("smartstage-docs/ARCHITECTURE.md")


@mcp.resource("smartstage://docs/roles", mime_type="text/markdown")
def lire_smartstage_roles() -> str:
    return fetch_github_doc("smartstage-docs/ROLES_UTILISATEURS.md")


@mcp.resource("smartstage://docs/modules", mime_type="text/markdown")
def lire_smartstage_modules() -> str:
    return fetch_github_doc("smartstage-docs/MODULES_FONCTIONNELS.md")


@mcp.resource("smartstage://docs/modele-donnees", mime_type="text/markdown")
def lire_smartstage_modele_donnees() -> str:
    return fetch_github_doc("smartstage-docs/MODELE_DONNEES.md")


@mcp.resource("smartstage://docs/api-endpoints", mime_type="text/markdown")
def lire_smartstage_api_endpoints() -> str:
    return fetch_github_doc("smartstage-docs/API_ENDPOINTS.md")


@mcp.resource("smartstage://docs/planning", mime_type="text/markdown")
def lire_smartstage_planning() -> str:
    return fetch_github_doc("smartstage-docs/PLANNING_LIVRABLES.md")


@mcp.resource("elyora://prompts/unit-test-criteria", mime_type="text/markdown")
def lire_criteres_tests_unitaires() -> str:
    return _read_prompt_file(
        "unit_test_criteria.md",
        "# Criteres de tests unitaires\n\nFichier prompts/unit_test_criteria.md absent.",
    )


@mcp.tool()
def get_smartstage_overview() -> dict[str, str]:
    """Retourne en un seul appel le README, l'architecture et les roles SmartStage."""
    return {
        "readme": fetch_github_doc("smartstage-docs/README.md"),
        "architecture": fetch_github_doc("smartstage-docs/ARCHITECTURE.md"),
        "roles": fetch_github_doc("smartstage-docs/ROLES_UTILISATEURS.md"),
    }


@mcp.tool()
def get_smartstage_module_detail(module_name: str) -> dict[str, Any]:
    """Retourne la section de MODULES_FONCTIONNELS.md correspondant au module demande."""
    content = fetch_github_doc("smartstage-docs/MODULES_FONCTIONNELS.md")
    result = _lookup_markdown(content, module_name)
    if result is None:
        return {
            "error": "module_not_found",
            "module_name": module_name,
            "suggestion": "Consultez smartstage://docs/modules pour la liste complete des modules.",
        }
    return {"module_name": module_name, **result}


@mcp.tool()
def get_smartstage_role_permissions(role: str) -> dict[str, Any]:
    """Retourne la section de ROLES_UTILISATEURS.md correspondant au role demande."""
    content = fetch_github_doc("smartstage-docs/ROLES_UTILISATEURS.md")
    result = _lookup_markdown(content, role)
    if result is None:
        return {
            "error": "role_not_found",
            "role": role,
            "suggestion": "Consultez smartstage://docs/roles pour la liste complete des roles.",
        }
    return {"role": role, **result}


@mcp.tool()
def get_smartstage_data_model(entity: str) -> dict[str, Any]:
    """Retourne les informations de MODELE_DONNEES.md sur l'entite demandee."""
    content = fetch_github_doc("smartstage-docs/MODELE_DONNEES.md")
    result = _lookup_markdown(content, entity)
    if result is None:
        return {
            "error": "entity_not_found",
            "entity": entity,
            "suggestion": "Consultez smartstage://docs/modele-donnees pour la liste complete des entites.",
        }
    return {"entity": entity, **result}


@mcp.tool()
def find_smartstage_endpoint(keyword: str) -> dict[str, Any]:
    """Recherche les endpoints d'API SmartStage correspondant a un mot-cle."""
    content = fetch_github_doc("smartstage-docs/API_ENDPOINTS.md")
    result = _lookup_markdown(content, keyword)
    if result is None:
        return {
            "error": "endpoint_not_found",
            "keyword": keyword,
            "suggestion": "Consultez smartstage://docs/api-endpoints pour la liste complete des routes.",
        }
    return {"keyword": keyword, **result}


@mcp.tool()
def get_smartstage_planning_status() -> dict[str, Any]:
    """Retourne le planning mensuel et les livrables attendus de SmartStage."""
    content = fetch_github_doc("smartstage-docs/PLANNING_LIVRABLES.md")
    result: dict[str, Any] = {}
    table = _parse_markdown_table(content)
    if table is not None:
        result["development_plan"] = table
    deliverables_section = _extract_markdown_section(content, "Livrables Attendus")
    if deliverables_section is not None:
        result["deliverables"] = deliverables_section
    if not result:
        result["raw_content"] = content
    return result


@mcp.tool()
def guide_smartstage_contributor(intent: str) -> dict[str, Any]:
    """Oriente un contributeur SmartStage vers le bon fichier ou module."""
    stopwords = {
        "je", "veux", "comment", "ou", "est", "le", "la", "les", "un", "une",
        "de", "du", "des", "pour", "dans", "sur", "add", "want", "how", "the",
    }
    keywords = [word.lower() for word in re.findall(r"\w+", intent) if len(word) > 2 and word.lower() not in stopwords]

    code_findings: list[dict[str, str]] = []
    for keyword in keywords[:5]:
        data = get_json(
            "https://api.github.com/search/code",
            params={"q": f"{keyword} repo:{active_repo_full_name()}", "per_page": 5},
        )
        if isinstance(data, dict) and "error" not in data:
            code_findings.extend({
                "keyword_matched": keyword,
                "file": item["path"],
                "url": item.get("html_url", ""),
            } for item in data.get("items", []))
    unique_code_files = list({item["file"]: item for item in code_findings}.values())

    modules_doc = fetch_github_doc("smartstage-docs/MODULES_FONCTIONNELS.md")
    matched_modules: list[str] = []
    for keyword in keywords[:5]:
        result = _lookup_markdown(modules_doc, keyword)
        if result is None:
            continue
        snippet = result.get("content") or "\n".join(result.get("matches", []))
        if snippet and snippet not in matched_modules:
            matched_modules.append(snippet[:500])

    return {
        "intent": intent,
        "relevant_files": unique_code_files or "Aucun fichier trouve. Verifiez le token GitHub ou reformulez l'intention.",
        "matched_module_sections": matched_modules or "Aucune section de MODULES_FONCTIONNELS.md ne correspond a l'intention.",
        "next_step": "Consultez smartstage://docs/readme, puis smartstage://docs/architecture et smartstage://docs/roles.",
    }


@mcp.tool()
def get_commit_history(ref: str = "main", path: str = "", limit: int = 20) -> list[dict[str, Any]] | dict[str, Any]:
    """Liste l'historique des commits du depot actif."""
    params: dict[str, Any] = {"sha": ref, "per_page": max(1, min(limit, 100))}
    if path:
        params["path"] = path
    data = get_json(f"{repo_api_url()}/commits", params=params)
    if isinstance(data, dict) and "error" in data:
        return data
    if not isinstance(data, list):
        return {"error": "unexpected_github_response", "detail": data}
    return [_parse_commit(item) for item in data]


@mcp.tool()
def get_file_history(filepath: str, limit: int = 20) -> list[dict[str, Any]] | dict[str, Any]:
    """Historique des commits ayant modifie un fichier precis."""
    return get_commit_history(path=filepath, limit=limit)


@mcp.tool()
def get_commit_details(sha: str) -> dict[str, Any]:
    """Retourne le detail complet d'un commit."""
    data = get_json(f"{repo_api_url()}/commits/{sha}")
    if isinstance(data, dict) and "error" in data:
        return data
    commit = data.get("commit", {})
    author_info = commit.get("author", {})
    return {
        "sha": data.get("sha"),
        "author": (data.get("author") or {}).get("login") or author_info.get("name") or "inconnu",
        "date": author_info.get("date"),
        "message": commit.get("message"),
        "stats": data.get("stats"),
        "files": [
            {
                "filename": file["filename"],
                "status": file["status"],
                "additions": file["additions"],
                "deletions": file["deletions"],
                "patch": file.get("patch"),
            }
            for file in data.get("files", [])
        ],
    }


@mcp.tool()
def get_recent_activity(days: int = 7) -> dict[str, Any]:
    """Vue d'ensemble de l'activite recente sur le depot actif."""
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

    commits_data = get_json(f"{repo_api_url()}/commits", params={"since": since, "per_page": 100})
    if isinstance(commits_data, dict) and "error" in commits_data:
        return commits_data
    commits = [_parse_commit(item) for item in commits_data] if isinstance(commits_data, list) else []

    prs_data = get_json(
        f"{repo_api_url()}/pulls",
        params={"state": "all", "sort": "updated", "direction": "desc", "per_page": 30},
    )
    recent_prs: list[dict[str, Any]] = []
    if isinstance(prs_data, list):
        for pr in prs_data:
            if pr.get("updated_at", "") >= since:
                recent_prs.append({
                    "number": pr["number"],
                    "title": pr["title"],
                    "author": pr["user"]["login"],
                    "state": pr["state"],
                    "created_at": pr["created_at"],
                    "updated_at": pr["updated_at"],
                    "merged_at": pr.get("merged_at"),
                })

    return {"since": since, "commits": commits, "pull_requests": recent_prs}


@mcp.tool()
async def search_code(question: str) -> str:
    """Recherche dans le code source indexe et repond a une question sur le projet."""
    response = await query_engine.aquery(question)
    return str(response)


@mcp.tool()
async def suggest_unit_tests(file_path: str) -> str:
    """Propose des cas de tests unitaires pour un fichier via le RAG."""
    response = await query_engine.aquery(
        f"Analyse le fichier {file_path} et propose une liste de cas de tests unitaires "
        "pertinents (nom du test, ce qu'il verifie, cas limites a couvrir). "
        "Concentre-toi sur la logique metier, pas juste la syntaxe."
    )
    return str(response)


SUGGEST_UNIT_TESTS_TEMPLATE = _read_prompt_file(
    "suggest_unit_tests.md",
    "Propose des tests unitaires pertinents pour le fichier {file_path}.",
)


@mcp.prompt(name="suggest-unit-tests", description="Propose des tests unitaires pertinents pour un fichier du depot")
def suggest_unit_tests_prompt(file_path: str) -> str:
    return SUGGEST_UNIT_TESTS_TEMPLATE.format(file_path=file_path)


SUGGEST_SONAR_FIXES_TEMPLATE = _read_prompt_file(
    "suggest_sonar_fixes.md",
    "Propose des corrections concretes pour les problemes Sonar de la PR {pr_number}. {severity_filter}",
)


@mcp.prompt(name="suggest-sonar-fixes", description="Propose des solutions concretes pour les problemes Sonar d'une PR")
def suggest_sonar_fixes_prompt(pr_number: str, severity_filter: str = "") -> str:
    return SUGGEST_SONAR_FIXES_TEMPLATE.format(pr_number=pr_number, severity_filter=severity_filter)


@mcp.prompt(name="guide-smartstage-contributor", description="Oriente un contributeur vers le bon module SmartStage")
def guide_smartstage_contributor_prompt(intent: str) -> str:
    template = _read_prompt_file(
        "guide_contributor.md",
        "Oriente un contributeur vers le bon module SmartStage pour cette intention : {intent}",
    )
    return template.format(intent=intent)


if __name__ == "__main__":
    mcp.run(transport="stdio")
