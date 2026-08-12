"""Analyse 'Tier 2' (basée sur le contenu d'un échantillon borné de
fichiers) du Project Style Analyzer : Class naming, Function naming,
Dependency Injection style, Exception hierarchy, Logging style, Docstring
format, Type hints, Repository/Service/Controller pattern, Imports, Code
formatting.

Réutilise `fetch_github_doc()` (déjà utilisé partout dans `mon_serveur.py`,
avec son cache mémoire) pour lire le contenu des fichiers candidats fournis
par `repository_scanner.scan_repository_structure()` — aucun nouvel accès
au dépôt n'est créé ici, uniquement des heuristiques par expression
régulière appliquées au contenu déjà récupéré.

Import vers `mon_serveur` volontairement tardif, voir
`repository_scanner.py` pour la même règle.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any, Callable

FetchFn = Callable[[str], str]

_CLASS_DECL = re.compile(r"\bclass\s+([A-Za-z_]\w*)")
_JAVA_METHOD_DECL = re.compile(
    r"(?:public|private|protected)\s+(?:static\s+)?(?:final\s+)?[\w<>\[\],\s.]+?\s(\w+)\s*\([^;{]*\)\s*\{"
)
_CAMEL_CASE = re.compile(r"^[a-z][A-Za-z0-9]*$")
_PASCAL_CASE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
_AUTOWIRED_FIELD = re.compile(r"@Autowired\s+(?:private|protected|public)?\s*[\w<>]+\s+\w+;")
_LOMBOK_CTOR = re.compile(r"@RequiredArgsConstructor|@AllArgsConstructor")
_CTOR_INJECTION = re.compile(r"public\s+\w+\s*\([^)]*\)\s*\{")
_EXTENDS_EXCEPTION = re.compile(r"class\s+\w*Exception\w*\s+extends\s+(\w+)")
_LOGGER_DECL = re.compile(r"LoggerFactory\.getLogger|@Slf4j")
_SYSTEM_PRINT = re.compile(r"System\.out\.println")
_JAVADOC_BLOCK = re.compile(r"/\*\*.*?\*/", re.DOTALL)
_TS_TYPED_PARAM = re.compile(r"\(\s*\w+\s*:\s*[\w<>\[\]]+")
_TS_UNTYPED_FUNC = re.compile(r"function\s+\w+\s*\([^):]*\)|=>\s*\{")
_REST_CONTROLLER = re.compile(r"@RestController|@Controller")
_SERVICE_ANNOTATION = re.compile(r"@Service\b")
_REPOSITORY_ANNOTATION = re.compile(
    r"@Repository\b|extends\s+(?:JpaRepository|CrudRepository|PagingAndSortingRepository)"
)
_WILDCARD_IMPORT = re.compile(r"^import\s+[\w.]+\.\*;", re.MULTILINE)
_IMPORT_LINE = re.compile(r"^import\s+[\w.]+;", re.MULTILINE)
_OPEN_BRACE_SAME_LINE = re.compile(r"\)\s*\{")
_OPEN_BRACE_NEW_LINE = re.compile(r"\)\s*\n\s*\{")
_TAB_INDENT = re.compile(r"^\t", re.MULTILINE)
_SPACE_INDENT = re.compile(r"^ {2,}", re.MULTILINE)


def _entry(category: str, description: str, confidence: float, sample_size: int, examples: list[str]) -> dict[str, Any]:
    return {
        "category": category,
        "description": description,
        "confidence": round(confidence, 4) if sample_size else 0.0,
        "sample_size": sample_size,
        "examples": examples[:5],
    }


def _ratio(matched: int, total: int) -> float:
    return matched / total if total else 0.0


def _fetch_samples(fetch: FetchFn, paths: list[str]) -> dict[str, str]:
    samples: dict[str, str] = {}
    for path in paths:
        content = fetch(path)
        if content and not content.startswith("# Erreur"):
            samples[path] = content
    return samples


def _check_class_naming(java_samples: dict[str, str]) -> dict[str, Any]:
    total, matched, examples = 0, 0, []
    for path, content in java_samples.items():
        for name in _CLASS_DECL.findall(content):
            total += 1
            if _PASCAL_CASE.match(name):
                matched += 1
                if len(examples) < 5:
                    examples.append(f"{path}: class {name}")
    return _entry(
        "class_naming",
        f"{matched}/{total} classes échantillonnées suivent PascalCase.",
        _ratio(matched, total), total, examples,
    )


def _check_function_naming(java_samples: dict[str, str]) -> dict[str, Any]:
    total, matched, examples = 0, 0, []
    for path, content in java_samples.items():
        for name in _JAVA_METHOD_DECL.findall(content):
            total += 1
            if _CAMEL_CASE.match(name):
                matched += 1
                if len(examples) < 5:
                    examples.append(f"{path}: {name}(...)")
    return _entry(
        "function_naming",
        f"{matched}/{total} méthodes échantillonnées suivent camelCase.",
        _ratio(matched, total), total, examples,
    )


def _check_dependency_injection(java_samples: dict[str, str]) -> dict[str, Any]:
    field_injection = 0
    constructor_injection = 0
    examples: list[str] = []
    for path, content in java_samples.items():
        has_autowired_field = bool(_AUTOWIRED_FIELD.search(content))
        has_ctor_style = bool(_LOMBOK_CTOR.search(content)) or (
            "final" in content and bool(_CTOR_INJECTION.search(content))
        )
        if has_autowired_field:
            field_injection += 1
            if len(examples) < 3:
                examples.append(f"{path}: injection par champ (@Autowired)")
        if has_ctor_style:
            constructor_injection += 1
            if len(examples) < 5:
                examples.append(f"{path}: injection par constructeur")
    total = field_injection + constructor_injection
    dominant = "injection par constructeur" if constructor_injection >= field_injection else "injection par champ (@Autowired)"
    confidence = _ratio(max(field_injection, constructor_injection), total)
    return _entry(
        "dependency_injection_style",
        f"Style dominant : {dominant} ({constructor_injection} constructeur vs {field_injection} champ, "
        f"sur {len(java_samples)} fichiers échantillonnés).",
        confidence, total, examples,
    )


def _check_exception_hierarchy(exception_samples: dict[str, str]) -> dict[str, Any]:
    bases: Counter[str] = Counter()
    examples: list[str] = []
    for path, content in exception_samples.items():
        for base in _EXTENDS_EXCEPTION.findall(content):
            bases[base] += 1
            if len(examples) < 5:
                examples.append(f"{path}: extends {base}")
    total = sum(bases.values())
    if not total:
        return _entry("exception_hierarchy", "Aucune classe d'exception échantillonnée n'a été trouvée.", 0.0, 0, [])
    dominant_base, dominant_count = bases.most_common(1)[0]
    return _entry(
        "exception_hierarchy",
        f"Hiérarchie dominante : la majorité des exceptions personnalisées étendent `{dominant_base}` "
        f"({dominant_count}/{total}).",
        _ratio(dominant_count, total), total, examples,
    )


def _check_logging_style(all_samples: dict[str, str]) -> dict[str, Any]:
    proper_logger, println_only, examples = 0, 0, []
    for path, content in all_samples.items():
        has_logger = bool(_LOGGER_DECL.search(content))
        has_println = bool(_SYSTEM_PRINT.search(content))
        if has_logger:
            proper_logger += 1
            if len(examples) < 5:
                examples.append(f"{path}: utilise Slf4j/LoggerFactory")
        elif has_println:
            println_only += 1
    total = proper_logger + println_only
    description = (
        f"{proper_logger}/{total} fichiers avec du logging utilisent Slf4j/LoggerFactory plutôt que "
        "System.out.println." if total else "Aucun usage de logging détecté dans l'échantillon."
    )
    return _entry("logging_style", description, _ratio(proper_logger, total), total, examples)


def _check_docstring_format(all_samples: dict[str, str]) -> dict[str, Any]:
    with_javadoc, examples = 0, []
    for path, content in all_samples.items():
        blocks = _JAVADOC_BLOCK.findall(content)
        if blocks:
            with_javadoc += 1
            if len(examples) < 5:
                examples.append(f"{path}: {blocks[0][:120].strip()}...")
    total = len(all_samples)
    return _entry(
        "docstring_format",
        f"{with_javadoc}/{total} fichiers échantillonnés utilisent des blocs Javadoc `/** ... */`.",
        _ratio(with_javadoc, total), total, examples,
    )


def _check_type_hints(ts_samples: dict[str, str]) -> dict[str, Any]:
    typed, untyped, examples = 0, 0, []
    for path, content in ts_samples.items():
        typed_params = len(_TS_TYPED_PARAM.findall(content))
        any_func = len(_TS_UNTYPED_FUNC.findall(content))
        if typed_params:
            typed += 1
            if len(examples) < 5:
                examples.append(f"{path}: paramètres typés explicitement")
        elif any_func:
            untyped += 1
    total = typed + untyped
    description = (
        f"{typed}/{total} fichiers TypeScript échantillonnés typent explicitement leurs paramètres."
        if total else "Aucun fichier TypeScript échantillonné."
    )
    return _entry("type_hints", description, _ratio(typed, total), total, examples)


_LAYER_LABELS = {
    "controller_pattern": "@RestController/@Controller",
    "service_pattern": "@Service",
    "repository_pattern": "@Repository / extends *Repository",
}


def _check_layer_pattern(category: str, samples: dict[str, str], annotation_pattern: re.Pattern[str]) -> dict[str, Any]:
    matched, examples = 0, []
    for path, content in samples.items():
        if annotation_pattern.search(content):
            matched += 1
            if len(examples) < 5:
                examples.append(path)
    total = len(samples)
    label = _LAYER_LABELS[category]
    description = (
        f"{matched}/{total} fichiers échantillonnés dans le rôle correspondant utilisent l'annotation attendue ({label})."
        if total else f"Aucun fichier échantillonné pour le rôle '{category}'."
    )
    return _entry(category, description, _ratio(matched, total), total, examples)


def _check_imports(all_samples: dict[str, str]) -> dict[str, Any]:
    total_imports, wildcard_imports, examples = 0, 0, []
    for path, content in all_samples.items():
        explicit = len(_IMPORT_LINE.findall(content))
        wildcard = len(_WILDCARD_IMPORT.findall(content))
        total_imports += explicit + wildcard
        wildcard_imports += wildcard
        if wildcard and len(examples) < 5:
            examples.append(f"{path}: import wildcard détecté")
    explicit_imports = total_imports - wildcard_imports
    description = (
        f"{explicit_imports}/{total_imports} imports échantillonnés sont explicites (pas de wildcard `.*`)."
        if total_imports else "Aucune ligne d'import détectée dans l'échantillon."
    )
    return _entry("imports", description, _ratio(explicit_imports, total_imports), total_imports, examples)


def _check_code_formatting(all_samples: dict[str, str]) -> dict[str, Any]:
    same_line, new_line, tabs, spaces = 0, 0, 0, 0
    for content in all_samples.values():
        new_line_matches = len(_OPEN_BRACE_NEW_LINE.findall(content))
        same_line += max(len(_OPEN_BRACE_SAME_LINE.findall(content)) - new_line_matches, 0)
        new_line += new_line_matches
        tabs += len(_TAB_INDENT.findall(content))
        spaces += len(_SPACE_INDENT.findall(content))
    brace_total = same_line + new_line
    dominant_brace = "accolade sur la même ligne" if same_line >= new_line else "accolade sur une nouvelle ligne"
    dominant_indent = "tabulations" if tabs >= spaces else "espaces"
    confidence = _ratio(same_line, brace_total) if brace_total else 0.0
    return _entry(
        "code_formatting",
        f"Style dominant : {dominant_brace} pour les accolades, indentation par {dominant_indent} "
        f"({tabs} lignes en tabulations vs {spaces} en espaces).",
        confidence, brace_total, [f"indentation dominante: {dominant_indent}"] if (tabs + spaces) else [],
    )


def analyze_code_patterns(candidate_paths: dict[str, list[str]]) -> dict[str, dict[str, Any]]:
    """Point d'entrée Tier 2. `candidate_paths` vient de
    `repository_scanner.scan_repository_structure()['candidate_paths']`."""
    from mon_serveur import fetch_github_doc

    samples_by_role = {role: _fetch_samples(fetch_github_doc, paths) for role, paths in candidate_paths.items()}

    java_roles = ("controller", "service", "repository", "exception", "other_java")
    java_samples: dict[str, str] = {}
    for role in java_roles:
        java_samples.update(samples_by_role.get(role, {}))

    all_samples: dict[str, str] = dict(java_samples)
    all_samples.update(samples_by_role.get("typescript", {}))
    all_samples.update(samples_by_role.get("test", {}))

    return {
        "class_naming": _check_class_naming(java_samples),
        "function_naming": _check_function_naming(java_samples),
        "dependency_injection_style": _check_dependency_injection(java_samples),
        "exception_hierarchy": _check_exception_hierarchy(samples_by_role.get("exception", {})),
        "logging_style": _check_logging_style(all_samples),
        "docstring_format": _check_docstring_format(all_samples),
        "type_hints": _check_type_hints(samples_by_role.get("typescript", {})),
        "controller_pattern": _check_layer_pattern(
            "controller_pattern", samples_by_role.get("controller", {}), _REST_CONTROLLER
        ),
        "service_pattern": _check_layer_pattern(
            "service_pattern", samples_by_role.get("service", {}), _SERVICE_ANNOTATION
        ),
        "repository_pattern": _check_layer_pattern(
            "repository_pattern", samples_by_role.get("repository", {}), _REPOSITORY_ANNOTATION
        ),
        "imports": _check_imports(all_samples),
        "code_formatting": _check_code_formatting(all_samples),
    }
