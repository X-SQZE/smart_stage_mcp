"""Étapes 'Repository Analysis', 'Architecture Analysis' et 'Dependency Analysis'
du planificateur d'exécution automatique (voir planning/plan_builder.py).

Règle de conception : ce module ne fait AUCUN appel HTTP/GitHub lui-même.
Il réutilise uniquement les fonctions déjà exposées comme outils MCP dans
`mon_serveur.py` (`list_repository_tree`, `fetch_github_doc`,
`guide_smartstage_contributor`, `get_smartstage_overview`) — exactement
comme `optimization_tools.py` réutilise `optimization/` plutôt que de
réimplémenter le monitoring de tokens. Aucun nouvel accès au dépôt n'est
créé ici.

Les imports vers `mon_serveur` sont volontairement faits à l'intérieur des
fonctions (imports tardifs) : `mon_serveur.py` importe ce paquet en tout
dernier (via `planner_tools.py`), donc un import en tête de fichier créerait
une dépendance circulaire au chargement du module.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Extensions de code source considérées lors de l'inventaire des modules
# existants (backend Spring Boot en Java, frontend Angular en TypeScript,
# scripts/outils en Python — voir ressources-Smartstage/architecture.md).
_SOURCE_EXTENSIONS = (".java", ".ts", ".js", ".py")
_TEST_PATH_HINTS = ("test", "Test", "spec", "__tests__")

# Fichiers de dépendances connus du projet SmartStage (backend Spring Boot +
# frontend Angular) et de smart_stage_mcp lui-même. Sert de base à l'étape
# 'Dependency Analysis' : on ne devine pas, on lit les fichiers réels s'ils
# existent dans le dépôt.
DEPENDENCY_FILES: tuple[str, ...] = (
    "backend/pom.xml",
    "pom.xml",
    "backend/build.gradle",
    "frontend/package.json",
    "package.json",
    "requirements.txt",
)


def analyze_repository_structure(ref: str = "main") -> dict[str, Any]:
    """Étape 'Repository Analysis'.

    Réutilise `list_repository_tree()` (déjà un outil MCP dans
    `mon_serveur.py`) pour inventorier les modules, services, tests et
    fichiers de documentation existants, sans dupliquer l'appel GitHub.
    """
    from mon_serveur import list_repository_tree

    tree = list_repository_tree(ref=ref)
    if isinstance(tree, dict) and "error" in tree:
        return {
            "error": tree,
            "top_level_modules": [],
            "existing_source_files_sample": [],
            "existing_test_files": [],
            "existing_documentation_files": [],
            "total_files": 0,
        }

    entries = tree.get("entries", [])
    top_level_dirs = sorted({e["path"].split("/")[0] for e in entries if "/" in e["path"]})
    test_files = [e["path"] for e in entries if any(hint in e["path"] for hint in _TEST_PATH_HINTS)]
    doc_files = [e["path"] for e in entries if e["path"].endswith(".md")]
    source_files = [
        e["path"]
        for e in entries
        if e.get("type") == "blob"
        and e["path"].endswith(_SOURCE_EXTENSIONS)
        and not any(hint in e["path"] for hint in _TEST_PATH_HINTS)
    ]

    return {
        "ref": ref,
        "truncated": tree.get("truncated", False),
        "top_level_modules": top_level_dirs,
        # échantillons plafonnés : le contexte complet reste géré par
        # optimization/context_optimizer.py (budget de tokens), inutile de
        # lui envoyer des milliers d'entrées brutes.
        "existing_source_files_sample": source_files[:60],
        "existing_test_files": test_files[:40],
        "existing_documentation_files": doc_files[:40],
        "total_files": len(entries),
    }


def find_related_code_and_modules(feature_description: str) -> dict[str, Any]:
    """Étape 'Architecture Analysis' (+ affinage de 'Repository Analysis').

    Réutilise `guide_smartstage_contributor()` — qui fait déjà une recherche
    de code GitHub par mots-clés et un rapprochement avec
    `MODULES_FONCTIONNELS.md` — plutôt que de réimplémenter une recherche de
    mots-clés distincte. Réutilise aussi `get_smartstage_overview()` pour le
    contexte d'architecture en couches (README/architecture/rôles).
    """
    from mon_serveur import get_smartstage_overview, guide_smartstage_contributor

    guidance = guide_smartstage_contributor(feature_description)
    overview = get_smartstage_overview()

    relevant_files = guidance.get("relevant_files", [])
    matched_modules = guidance.get("matched_module_sections", [])

    return {
        # ces deux clés peuvent aussi contenir un message d'erreur textuel
        # (voir guide_smartstage_contributor) plutôt qu'une liste — on le
        # normalise ici pour que plan_builder.py ait toujours une liste.
        "relevant_existing_files": relevant_files if isinstance(relevant_files, list) else [],
        "matched_module_sections": matched_modules if isinstance(matched_modules, list) else [],
        "architecture_summary": (overview.get("architecture") or "")[:4000],
        "roles_summary": (overview.get("roles") or "")[:1500],
    }


def analyze_dependencies(ref: str = "main") -> dict[str, Any]:
    """Étape 'Dependency Analysis'.

    Lit les fichiers de dépendances connus (`pom.xml`, `package.json`, ...)
    via `fetch_github_doc()`, déjà utilisé partout ailleurs dans
    `mon_serveur.py` pour lire un fichier du dépôt (avec son cache mémoire).
    Ne parse pas le XML/JSON en profondeur : le LLM du planificateur lit le
    contenu brut (tronqué) pour identifier les dépendances pertinentes.
    """
    from mon_serveur import fetch_github_doc

    found: dict[str, str] = {}
    for path in DEPENDENCY_FILES:
        content = fetch_github_doc(path)
        if content.startswith("# Erreur"):
            continue
        found[path] = content[:6000]

    return {
        "dependency_files_found": list(found.keys()),
        "dependency_files_content": found,
    }
