"""Analyse 'Tier 1' (basée uniquement sur les chemins, pas le contenu) du
Project Style Analyzer : Folder organization, Naming conventions (fichiers)
et Test organization.

Réutilise `list_repository_tree()` (déjà un outil MCP dans `mon_serveur.py`)
et `planning.repository_analyzer.analyze_repository_structure()` (déjà
utilisé par l'Automatic Code Planner) plutôt que de réimplémenter un accès
au dépôt : ce module ne fait qu'ajouter des statistiques de convention par
dessus des données déjà récupérées.

Imports vers `mon_serveur` volontairement tardifs (voir
`planning/repository_analyzer.py` pour la même règle) : `mon_serveur.py`
importe ce paquet en tout dernier, via `style_tools.py`.
"""
from __future__ import annotations

import re
from typing import Any

# Dossiers "métier" attendus dans une architecture en couches Spring Boot,
# tels que documentés dans ressources-Smartstage/architecture.md.
_EXPECTED_LAYERS = ("controller", "service", "repository", "model", "entity", "dto", "exception", "config")

_FILENAME_PATTERNS: dict[str, re.Pattern[str]] = {
    ".java": re.compile(r"^[A-Z][A-Za-z0-9]*\.java$"),  # PascalCase
    ".ts": re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*(?:\.[a-z]+)*\.ts$"),  # kebab-case (+ suffixe de rôle)
    ".py": re.compile(r"^[a-z_][a-z0-9_]*\.py$"),  # snake_case
}

_ROLE_HINTS = {
    "controller": ("controller",),
    "service": ("service",),
    "repository": ("repository", "repo"),
    "exception": ("exception", "error"),
    "test": ("test", "spec"),
}


def _confidence_entry(category: str, description: str, confidence: float, sample_size: int, examples: list[str]) -> dict[str, Any]:
    return {
        "category": category,
        "description": description,
        "confidence": round(confidence, 4) if sample_size else 0.0,
        "sample_size": sample_size,
        "examples": examples[:5],
    }


def _analyze_filename_conventions(blob_paths: list[str]) -> dict[str, Any]:
    """Naming conventions : pour chaque extension connue, quelle proportion
    des noms de fichiers respecte la convention de casse attendue."""
    by_extension: dict[str, list[str]] = {}
    for path in blob_paths:
        for ext in _FILENAME_PATTERNS:
            if path.endswith(ext):
                by_extension.setdefault(ext, []).append(path)
                break

    per_extension_report: dict[str, Any] = {}
    total_matched = 0
    total_files = 0
    matched_examples: list[str] = []
    for ext, paths in by_extension.items():
        pattern = _FILENAME_PATTERNS[ext]
        matched = [p for p in paths if pattern.match(p.rsplit("/", 1)[-1])]
        per_extension_report[ext] = {
            "total_files": len(paths),
            "matching_convention": len(matched),
            "confidence": round(len(matched) / len(paths), 4) if paths else 0.0,
        }
        total_matched += len(matched)
        total_files += len(paths)
        matched_examples.extend(matched[:2])

    description = "; ".join(
        f"{ext}: {report['matching_convention']}/{report['total_files']} fichiers respectent la convention de casse attendue"
        for ext, report in per_extension_report.items()
    ) or "Aucun fichier avec une extension reconnue n'a été trouvé."

    return {
        "naming_conventions": _confidence_entry(
            "naming_conventions", description,
            (total_matched / total_files) if total_files else 0.0,
            total_files, matched_examples,
        ),
        "per_extension": per_extension_report,
    }


def _analyze_folder_layout(top_level_modules: list[str], blob_paths: list[str]) -> dict[str, Any]:
    """Folder organization : combien des couches attendues d'une architecture
    en couches (controller/service/repository/...) sont effectivement
    présentes comme dossiers dans le dépôt."""
    lowered_paths = "\n".join(p.lower() for p in blob_paths)
    present_layers = [layer for layer in _EXPECTED_LAYERS if f"/{layer}" in lowered_paths or f"{layer}/" in lowered_paths]
    confidence = len(present_layers) / len(_EXPECTED_LAYERS)
    description = (
        f"{len(present_layers)}/{len(_EXPECTED_LAYERS)} couches d'architecture en couches détectées "
        f"comme dossiers : {', '.join(present_layers) or 'aucune'}. Modules de premier niveau : "
        f"{', '.join(top_level_modules[:10]) or 'aucun'}."
    )
    return _confidence_entry("folder_organization", description, confidence, len(_EXPECTED_LAYERS), present_layers)


def _analyze_test_organization(test_files: list[str]) -> dict[str, Any]:
    """Test organization : convention de nommage des fichiers de test
    (`*Test.java` / `*Tests.java` / `*.spec.ts`) et présence d'une
    arborescence de test miroir de l'arborescence principale."""
    if not test_files:
        return _confidence_entry("test_organization", "Aucun fichier de test détecté dans l'arborescence.", 0.0, 0, [])

    name_pattern = re.compile(r"(Test|Tests)\.java$|\.spec\.ts$|test_\w+\.py$|_test\.py$")
    named_correctly = [f for f in test_files if name_pattern.search(f)]
    mirrored = [f for f in test_files if "src/test/" in f and "src/main/" not in f]

    confidence = len(named_correctly) / len(test_files)
    description = (
        f"{len(named_correctly)}/{len(test_files)} fichiers de test suivent une convention de nommage "
        f"reconnue (*Test.java, *.spec.ts, test_*.py). "
        f"{len(mirrored)}/{len(test_files)} sont placés dans une arborescence src/test/ dédiée."
    )
    return _confidence_entry("test_organization", description, confidence, len(test_files), named_correctly)


def _select_candidate_paths(blob_paths: list[str], max_per_role: int = 8) -> dict[str, list[str]]:
    """Sélectionne un échantillon borné de fichiers par rôle métier, pour que
    l'analyse de contenu (`content_pattern_analyzer.py`) ne télécharge pas
    tout le dépôt.

    L'extension prime sur les indices de nom de fichier : un fichier
    `user.service.ts` doit atterrir dans le bucket `typescript`, pas dans le
    bucket Java `service`, même si "service" apparaît dans son chemin.
    """
    candidates: dict[str, list[str]] = {role: [] for role in _ROLE_HINTS}
    candidates["typescript"] = []
    candidates["other_java"] = []

    for path in blob_paths:
        lowered = path.lower()
        is_test = any(hint in lowered for hint in _ROLE_HINTS["test"])

        if path.endswith(".ts"):
            if is_test and len(candidates["test"]) < max_per_role:
                candidates["test"].append(path)
            elif len(candidates["typescript"]) < max_per_role:
                candidates["typescript"].append(path)
            continue

        if not path.endswith(".java"):
            continue

        matched_role = False
        for role in ("test", "controller", "service", "repository", "exception"):
            hints = _ROLE_HINTS[role]
            if any(hint in lowered for hint in hints) and len(candidates[role]) < max_per_role:
                candidates[role].append(path)
                matched_role = True
                break
        if not matched_role and len(candidates["other_java"]) < max_per_role:
            candidates["other_java"].append(path)

    return {role: paths for role, paths in candidates.items() if paths}


def scan_repository_structure(ref: str = "main") -> dict[str, Any]:
    """Point d'entrée Tier 1 : Folder organization, Naming conventions et
    Test organization, plus la sélection des fichiers candidats pour
    l'analyse de contenu (Tier 2)."""
    from mon_serveur import list_repository_tree

    from planning.repository_analyzer import analyze_repository_structure

    base = analyze_repository_structure(ref=ref)

    tree = list_repository_tree(ref=ref)
    entries = tree.get("entries", []) if isinstance(tree, dict) else []
    blob_paths = [e["path"] for e in entries if e.get("type") == "blob"]

    filename_report = _analyze_filename_conventions(blob_paths)
    folder_report = _analyze_folder_layout(base.get("top_level_modules", []), blob_paths)
    test_report = _analyze_test_organization(base.get("existing_test_files", []))

    return {
        "ref": ref,
        "total_files": len(blob_paths),
        "conventions": {
            "folder_organization": folder_report,
            "naming_conventions": filename_report["naming_conventions"],
            "test_organization": test_report,
        },
        "naming_conventions_detail": filename_report["per_extension"],
        "candidate_paths": _select_candidate_paths(blob_paths),
    }
