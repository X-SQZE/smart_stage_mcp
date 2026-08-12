"""Tests unitaires du Project Style Analyzer (style_analysis/).

Comme `tests/test_planner.py`, ces tests ne nécessitent ni GEMINI_API_KEY,
ni GITHUB_TOKEN, ni index LlamaIndex construit : `mon_serveur` est remplacé
par un faux module dans `sys.modules` (tous les imports vers `mon_serveur`
dans `style_analysis/` sont tardifs). La persistance SQLite est testée sur
une base temporaire (jamais la vraie `smartstage_mcp.db` du dépôt).

Lancer avec : python -m unittest tests.test_style_analyzer -v
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, ".")

import optimization.db as db_module
from style_analysis import store
from style_analysis.content_pattern_analyzer import analyze_code_patterns
from style_analysis.repository_scanner import scan_repository_structure
from style_analysis.style_learner import CONVENTION_CATEGORIES, learn_project_style

JAVA_CONTROLLER = """
package com.smartstage.controller;

import org.springframework.web.bind.annotation.RestController;

/**
 * Handles user-related HTTP requests.
 */
@RestController
public class UserController {
    private static final org.slf4j.Logger log = org.slf4j.LoggerFactory.getLogger(UserController.class);

    private final UserService userService;

    public UserController(UserService userService) {
        this.userService = userService;
    }

    public ResponseEntity<User> getUser(Long id) {
        return ResponseEntity.ok(userService.findById(id));
    }
}
"""

JAVA_SERVICE = """
package com.smartstage.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;

@Service
@RequiredArgsConstructor
public class UserService {
    private final UserRepository userRepository;

    public User findById(Long id) {
        return userRepository.findById(id).orElseThrow();
    }
}
"""

JAVA_REPOSITORY = """
package com.smartstage.repository;

import org.springframework.data.jpa.repository.JpaRepository;

public interface UserRepository extends JpaRepository<User, Long> {
}
"""

JAVA_EXCEPTION = """
package com.smartstage.exception;

public class UserNotFoundException extends RuntimeException {
    public UserNotFoundException(String message) {
        super(message);
    }
}
"""

JAVA_LEGACY_FIELD_INJECTION = """
package com.smartstage.service;

import org.springframework.beans.factory.annotation.Autowired;

public class LegacyService {
    @Autowired
    private UserRepository userRepository;

    public void doWork() {
        System.out.println("working");
    }
}
"""

TS_SERVICE = """
import { Injectable } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class UserService {
  getUser(id: string): User {
    return this.http.get(id);
  }
}
"""


def _fake_tree_entries() -> list[dict[str, str]]:
    return [
        {"path": "backend/src/main/java/com/smartstage/controller/UserController.java", "type": "blob"},
        {"path": "backend/src/main/java/com/smartstage/service/UserService.java", "type": "blob"},
        {"path": "backend/src/main/java/com/smartstage/service/LegacyService.java", "type": "blob"},
        {"path": "backend/src/main/java/com/smartstage/repository/UserRepository.java", "type": "blob"},
        {"path": "backend/src/main/java/com/smartstage/exception/UserNotFoundException.java", "type": "blob"},
        {"path": "backend/src/test/java/com/smartstage/service/UserServiceTest.java", "type": "blob"},
        {"path": "frontend/src/app/user/user.service.ts", "type": "blob"},
        {"path": "badFileName.java", "type": "blob"},  # ne respecte pas PascalCase pour un nom de fichier .java
        {"path": "ressources-Smartstage/architecture.md", "type": "blob"},
        {"path": "backend", "type": "tree"},
    ]


_FILE_CONTENTS = {
    "backend/src/main/java/com/smartstage/controller/UserController.java": JAVA_CONTROLLER,
    "backend/src/main/java/com/smartstage/service/UserService.java": JAVA_SERVICE,
    "backend/src/main/java/com/smartstage/service/LegacyService.java": JAVA_LEGACY_FIELD_INJECTION,
    "backend/src/main/java/com/smartstage/repository/UserRepository.java": JAVA_REPOSITORY,
    "backend/src/main/java/com/smartstage/exception/UserNotFoundException.java": JAVA_EXCEPTION,
    "frontend/src/app/user/user.service.ts": TS_SERVICE,
}


def _fake_fetch_github_doc(path: str) -> str:
    return _FILE_CONTENTS.get(path, "# Erreur\n\nFichier introuvable.")


def _install_fake_mon_serveur(llm_response_text: str = "# Guide de style\n\nRègles détectées.") -> types.ModuleType:
    fake = types.ModuleType("mon_serveur")
    fake.list_repository_tree = MagicMock(
        return_value={"ref": "main", "truncated": False, "entries": _fake_tree_entries()}
    )
    fake.fetch_github_doc = MagicMock(side_effect=_fake_fetch_github_doc)
    fake._rag_retriever = MagicMock(
        return_value=[{"text": "@RestController class UserController { ... }", "source": "UserController.java", "score": 0.9}]
    )

    fake_llm = MagicMock()

    async def _acomplete(prompt: str):
        return llm_response_text

    fake_llm.acomplete = _acomplete
    fake.Settings = types.SimpleNamespace(llm=fake_llm)
    fake.configu = types.SimpleNamespace(LLM_MODEL_NAME="models/gemini-3-flash-preview")

    sys.modules["mon_serveur"] = fake
    return fake


class RepositoryScannerTests(unittest.TestCase):
    def setUp(self) -> None:
        _install_fake_mon_serveur()

    def tearDown(self) -> None:
        sys.modules.pop("mon_serveur", None)

    def test_folder_organization_detects_layered_dirs(self) -> None:
        result = scan_repository_structure()
        folder = result["conventions"]["folder_organization"]
        self.assertGreater(folder["confidence"], 0.0)
        self.assertIn("controller", folder["description"])

    def test_naming_conventions_flags_bad_java_filename(self) -> None:
        result = scan_repository_structure()
        # 7 fichiers .java au total (6 bien nommés + badFileName.java qui respecte quand même
        # PascalCase par accident car il commence par une minuscule -> à vérifier)
        detail = result["naming_conventions_detail"][".java"]
        self.assertEqual(detail["total_files"], 7)
        self.assertLess(detail["matching_convention"], detail["total_files"])

    def test_test_organization_finds_mirrored_test_file(self) -> None:
        result = scan_repository_structure()
        test_org = result["conventions"]["test_organization"]
        self.assertEqual(test_org["sample_size"], 1)
        self.assertEqual(test_org["confidence"], 1.0)

    def test_candidate_paths_grouped_by_role(self) -> None:
        result = scan_repository_structure()
        candidates = result["candidate_paths"]
        self.assertIn("controller", candidates)
        self.assertIn("service", candidates)
        self.assertIn("repository", candidates)
        self.assertIn("exception", candidates)
        self.assertIn("typescript", candidates)


class ContentPatternAnalyzerTests(unittest.TestCase):
    def setUp(self) -> None:
        _install_fake_mon_serveur()
        self.candidates = {
            "controller": ["backend/src/main/java/com/smartstage/controller/UserController.java"],
            "service": [
                "backend/src/main/java/com/smartstage/service/UserService.java",
                "backend/src/main/java/com/smartstage/service/LegacyService.java",
            ],
            "repository": ["backend/src/main/java/com/smartstage/repository/UserRepository.java"],
            "exception": ["backend/src/main/java/com/smartstage/exception/UserNotFoundException.java"],
            "typescript": ["frontend/src/app/user/user.service.ts"],
        }

    def tearDown(self) -> None:
        sys.modules.pop("mon_serveur", None)

    def test_detects_constructor_and_field_injection_mix(self) -> None:
        result = analyze_code_patterns(self.candidates)
        di = result["dependency_injection_style"]
        self.assertIn("constructeur", di["description"])
        self.assertGreater(di["sample_size"], 0)

    def test_detects_exception_base_class(self) -> None:
        result = analyze_code_patterns(self.candidates)
        exc = result["exception_hierarchy"]
        self.assertIn("RuntimeException", exc["description"])
        self.assertEqual(exc["confidence"], 1.0)

    def test_detects_logging_style_mix(self) -> None:
        result = analyze_code_patterns(self.candidates)
        logging_style = result["logging_style"]
        self.assertEqual(logging_style["sample_size"], 2)  # 1 avec logger, 1 avec println

    def test_detects_repository_and_service_and_controller_patterns(self) -> None:
        result = analyze_code_patterns(self.candidates)
        self.assertEqual(result["controller_pattern"]["confidence"], 1.0)
        self.assertEqual(result["repository_pattern"]["confidence"], 1.0)

    def test_detects_docstring_and_type_hints(self) -> None:
        result = analyze_code_patterns(self.candidates)
        self.assertGreaterEqual(result["docstring_format"]["sample_size"], 1)
        self.assertGreaterEqual(result["type_hints"]["sample_size"], 1)


class StoreIncrementalMergeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_db_path = db_module.DB_PATH
        self._original_connection = db_module._connection
        self._tmp_dir = tempfile.TemporaryDirectory()
        db_module.DB_PATH = os.path.join(self._tmp_dir.name, "test_style.db")
        db_module._connection = None
        store._TABLES_READY = False

    def tearDown(self) -> None:
        if db_module._connection is not None:
            db_module._connection.close()
        db_module.DB_PATH = self._original_db_path
        db_module._connection = self._original_connection
        store._TABLES_READY = False
        self._tmp_dir.cleanup()

    def test_first_upsert_stores_observation_as_is(self) -> None:
        result = store.upsert_convention(
            "logging_style", category="logging_style", description="desc", confidence=0.8, sample_size=10, examples=["a"]
        )
        self.assertEqual(result["confidence"], 0.8)
        self.assertEqual(result["sample_size"], 10)

    def test_second_upsert_uses_weighted_average(self) -> None:
        store.upsert_convention("logging_style", category="logging_style", description="d1", confidence=1.0, sample_size=10)
        result = store.upsert_convention("logging_style", category="logging_style", description="d2", confidence=0.0, sample_size=10)
        # moyenne pondérée de 1.0 (n=10) et 0.0 (n=10) -> 0.5
        self.assertAlmostEqual(result["confidence"], 0.5, places=4)
        self.assertEqual(result["sample_size"], 20)

    def test_load_profile_returns_persisted_rows(self) -> None:
        store.upsert_convention("imports", category="imports", description="d", confidence=0.7, sample_size=5)
        profile = store.load_profile()
        self.assertIn("imports", profile)
        self.assertEqual(profile["imports"]["confidence"], 0.7)

    def test_record_run_appends_history(self) -> None:
        store.record_run("run-1", "main", 15, 0.6)
        store.record_run("run-2", "main", 15, 0.65)
        history = store.get_run_history(limit=10)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["run_id"], "run-2")  # le plus récent en premier


class LearnProjectStyleEndToEndTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_db_path = db_module.DB_PATH
        self._original_connection = db_module._connection
        self._tmp_dir = tempfile.TemporaryDirectory()
        db_module.DB_PATH = os.path.join(self._tmp_dir.name, "test_style_e2e.db")
        db_module._connection = None
        store._TABLES_READY = False

    def tearDown(self) -> None:
        if db_module._connection is not None:
            db_module._connection.close()
        db_module.DB_PATH = self._original_db_path
        db_module._connection = self._original_connection
        store._TABLES_READY = False
        self._tmp_dir.cleanup()
        sys.modules.pop("mon_serveur", None)

    def test_returns_full_report_and_persists_profile(self) -> None:
        _install_fake_mon_serveur()
        result = asyncio.run(learn_project_style())

        for key in CONVENTION_CATEGORIES:
            self.assertIn(key, result["detected_conventions"])
        self.assertIsInstance(result["confidence_score"], float)
        self.assertIn("suggested_style_guide", result)
        self.assertTrue(result["suggested_style_guide"])
        self.assertIn("controller_pattern", result["representative_examples"])

        persisted = store.load_profile()
        self.assertIn("controller_pattern", persisted)

    def test_profile_improves_across_two_runs(self) -> None:
        """Deuxième exécution : le profil stocké doit refléter une fusion,
        pas un simple écrasement (sample_size cumulé augmente)."""
        _install_fake_mon_serveur()
        asyncio.run(learn_project_style())
        first_sample_size = store.load_profile()["controller_pattern"]["sample_size"]

        asyncio.run(learn_project_style())
        second_sample_size = store.load_profile()["controller_pattern"]["sample_size"]

        self.assertGreater(second_sample_size, first_sample_size)

    def test_llm_failure_falls_back_to_deterministic_guide(self) -> None:
        fake = _install_fake_mon_serveur()

        async def _boom(prompt: str):
            raise RuntimeError("quota LLM dépassé")

        fake.Settings.llm.acomplete = _boom
        result = asyncio.run(learn_project_style())
        self.assertIn("# Guide de style SmartStage", result["suggested_style_guide"])


if __name__ == "__main__":
    unittest.main()
