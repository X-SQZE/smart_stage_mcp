"""Tests unitaires de l'Automatic Code Planner (planning/).

Ces tests ne nécessitent ni GEMINI_API_KEY, ni GITHUB_TOKEN, ni index
LlamaIndex construit : ils remplacent `mon_serveur` par un faux module dans
`sys.modules` avant d'appeler le planificateur, puisque tous les imports
vers `mon_serveur` dans `planning/` sont volontairement tardifs (à
l'intérieur des fonctions). Cela permet de tester le pipeline
(Repository Analysis -> RAG Retrieval -> Architecture Analysis ->
Dependency Analysis -> Execution Plan) de bout en bout, avec un faux LLM
qui renvoie un plan JSON déterministe.

Lancer avec : python -m unittest tests.test_planner -v
"""
from __future__ import annotations

import asyncio
import json
import sys
import types
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, ".")

from planning.plan_builder import PLAN_JSON_SCHEMA_KEYS, _parse_plan_json, build_execution_plan
from planning.repository_analyzer import (
    analyze_dependencies,
    analyze_repository_structure,
    find_related_code_and_modules,
)


FAKE_PLAN = {key: f"valeur pour {key}" for key in PLAN_JSON_SCHEMA_KEYS}


def _install_fake_mon_serveur(llm_response_text: str = json.dumps(FAKE_PLAN)) -> types.ModuleType:
    """Installe un faux module `mon_serveur` dans sys.modules, avec juste ce
    que `planning/` en importe (tardivement)."""
    fake = types.ModuleType("mon_serveur")

    fake.list_repository_tree = MagicMock(
        return_value={
            "ref": "main",
            "truncated": False,
            "entries": [
                {"path": "backend/src/main/java/com/smartstage/service/UserService.java", "type": "blob"},
                {"path": "backend/src/test/java/com/smartstage/service/UserServiceTest.java", "type": "blob"},
                {"path": "frontend/src/app/user/user.service.ts", "type": "blob"},
                {"path": "ressources-Smartstage/architecture.md", "type": "blob"},
                {"path": "backend", "type": "tree"},
            ],
        }
    )
    fake.guide_smartstage_contributor = MagicMock(
        return_value={
            "relevant_files": ["backend/src/main/java/com/smartstage/service/UserService.java"],
            "matched_module_sections": ["## Gestion des utilisateurs\nDétails du module..."],
        }
    )
    fake.get_smartstage_overview = MagicMock(
        return_value={"readme": "# SmartStage", "architecture": "Architecture en couches...", "roles": "RH, Employé"}
    )
    fake.fetch_github_doc = MagicMock(
        side_effect=lambda path: (
            '{"dependencies": {"spring-boot-starter-web": "3.2.0"}}'
            if path == "backend/pom.xml"
            else f"# Erreur\n\nLe fichier `{path}` n'est pas un fichier texte lisible."
        )
    )
    fake._rag_retriever = MagicMock(
        return_value=[
            {"text": "class UserService { ... }", "source": "backend/.../UserService.java", "score": 0.87},
        ]
    )

    fake_llm = MagicMock()

    async def _acomplete(prompt: str):
        return llm_response_text

    fake_llm.acomplete = _acomplete
    fake.Settings = types.SimpleNamespace(llm=fake_llm)

    fake.configu = types.SimpleNamespace(LLM_MODEL_NAME="models/gemini-3-flash-preview")

    sys.modules["mon_serveur"] = fake
    return fake


class RepositoryAnalyzerTests(unittest.TestCase):
    def setUp(self) -> None:
        _install_fake_mon_serveur()

    def tearDown(self) -> None:
        sys.modules.pop("mon_serveur", None)

    def test_analyze_repository_structure_separates_tests_and_docs(self) -> None:
        result = analyze_repository_structure()
        self.assertIn("backend", result["top_level_modules"])
        self.assertIn(
            "backend/src/test/java/com/smartstage/service/UserServiceTest.java",
            result["existing_test_files"],
        )
        self.assertIn("ressources-Smartstage/architecture.md", result["existing_documentation_files"])
        self.assertNotIn(
            "backend/src/test/java/com/smartstage/service/UserServiceTest.java",
            result["existing_source_files_sample"],
        )

    def test_find_related_code_and_modules_normalizes_error_strings(self) -> None:
        fake = sys.modules["mon_serveur"]
        fake.guide_smartstage_contributor.return_value = {
            "relevant_files": "Aucun fichier trouvé.",
            "matched_module_sections": "Aucune section ne correspond.",
        }
        result = find_related_code_and_modules("gérer les congés")
        self.assertEqual(result["relevant_existing_files"], [])
        self.assertEqual(result["matched_module_sections"], [])

    def test_analyze_dependencies_only_keeps_existing_files(self) -> None:
        result = analyze_dependencies()
        self.assertIn("backend/pom.xml", result["dependency_files_found"])
        self.assertNotIn("requirements.txt", result["dependency_files_found"])


class PlanJsonParsingTests(unittest.TestCase):
    def test_parses_clean_json(self) -> None:
        parsed = _parse_plan_json(json.dumps(FAKE_PLAN))
        for key in PLAN_JSON_SCHEMA_KEYS:
            self.assertIn(key, parsed)

    def test_strips_markdown_code_fence(self) -> None:
        fenced = "```json\n" + json.dumps(FAKE_PLAN) + "\n```"
        parsed = _parse_plan_json(fenced)
        self.assertEqual(parsed["Goal"], FAKE_PLAN["Goal"])

    def test_falls_back_gracefully_on_invalid_json(self) -> None:
        parsed = _parse_plan_json("réponse non structurée du LLM")
        self.assertTrue(parsed.get("parse_error"))
        self.assertIn("raw_response", parsed)


class BuildExecutionPlanTests(unittest.TestCase):
    def tearDown(self) -> None:
        sys.modules.pop("mon_serveur", None)

    def test_end_to_end_returns_full_schema_and_analysis(self) -> None:
        _install_fake_mon_serveur()
        result = asyncio.run(build_execution_plan("Ajouter la possibilité de filtrer les stages par ville"))

        self.assertEqual(result["feature_request"], "Ajouter la possibilité de filtrer les stages par ville")
        self.assertEqual(
            result["workflow"],
            ["repository_analysis", "rag_retrieval", "architecture_analysis", "dependency_analysis", "execution_plan"],
        )
        for key in PLAN_JSON_SCHEMA_KEYS:
            self.assertIn(key, result["plan"])
        self.assertEqual(result["analysis"]["rag_retrieval"]["chunks_found"], 1)
        self.assertIn("backend/pom.xml", result["analysis"]["dependency_analysis"]["dependency_files_found"])

    def test_never_generates_code_only_a_plan(self) -> None:
        """Le prompt interdit explicitement le code ; ce test vérifie que le
        plan renvoyé reste un objet JSON de métadonnées, pas un bloc de code."""
        _install_fake_mon_serveur()
        result = asyncio.run(build_execution_plan("Ajouter un export PDF des évaluations"))
        plan = result["plan"]
        self.assertIsInstance(plan, dict)
        self.assertNotIn("code", plan)

    def test_llm_failure_is_reported_without_raising(self) -> None:
        fake = _install_fake_mon_serveur()

        async def _boom(prompt: str):
            raise RuntimeError("quota LLM dépassé")

        fake.Settings.llm.acomplete = _boom
        result = asyncio.run(build_execution_plan("Ajouter des notifications push"))
        self.assertIn("error", result["plan"])


if __name__ == "__main__":
    unittest.main()
