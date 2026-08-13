import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from agent.state import AgentState
from agent.nodes.graph import app
from agent.nodes.repository import repository_node
from agent.nodes.planning import planning_node
from agent.nodes.scope_check import scope_check_node
from agent.nodes.mcp import mcp_node


class TestLangGraph(unittest.IsolatedAsyncioTestCase):
    def test_graph_compiles(self):
        # Point 6: Le graph peut être compilé.
        self.assertIsNotNone(app)

    @patch("agent.nodes.repository.get_mcp_tools")
    async def test_repository_node(self, mock_get_tools):
        # Mock tools
        mock_tools = {
            "explore_repo_structure": AsyncMock(),
            "search_code": AsyncMock(),
        }
        mock_tools["explore_repo_structure"].ainvoke.return_value = {
            "likely_context_files": [{"path": "file1.py"}, {"path": "file2.py"}]
        }
        mock_tools["search_code"].ainvoke.return_value = "Mocked RAG Context"
        mock_get_tools.return_value = mock_tools

        state = {"user_request": "Ajouter une feature"}
        result = await repository_node(state)

        # Point 2: repository_node remplit repository_context et relevant_files.
        self.assertEqual(result["repository_context"], "Mocked RAG Context")
        self.assertEqual(result["relevant_files"], ["file1.py", "file2.py"])
        # Point 8: verifying keys
        self.assertIn("repository_context", result)
        self.assertIn("relevant_files", result)

    @patch("agent.nodes.planning.get_mcp_tools")
    async def test_planning_node(self, mock_get_tools):
        mock_tools = {
            "read_repo_file": AsyncMock()
        }
        mock_tools["read_repo_file"].ainvoke.return_value = "Contenu du fichier"
        mock_get_tools.return_value = mock_tools

        state = {
            "repository_context": "Mocked RAG",
            "relevant_files": ["file1.py"]
        }
        result = await planning_node(state)

        # Point 3: planning_node reçoit correctement les données précédentes
        self.assertIn("architectural_plan", result)
        self.assertIn("Mocked RAG", result["architectural_plan"])
        self.assertIn("file1.py", result["architectural_plan"])
        self.assertIn("Contenu du fichier", result["architectural_plan"])

    @patch("agent.nodes.scope_check.get_mcp_tools")
    async def test_scope_check_node(self, mock_get_tools):
        mock_tools = {
            "generate_implementation_plan": AsyncMock()
        }
        mock_tools["generate_implementation_plan"].ainvoke.return_value = {
            "scope_ok": True,
            "questions": [],
            "branch_name": "feature/test",
            "commit_message": "Test commit",
            "pr_title": "Test PR",
            "pr_description": "Test Desc",
            "files": [{"path": "file1.py", "content": "print('hello')"}]
        }
        mock_get_tools.return_value = mock_tools

        state = {
            "user_request": "Ajouter une feature",
            "architectural_plan": "Plan"
        }
        result = await scope_check_node(state)

        # Point 4: scope_check_node remplit correctement le State
        self.assertTrue(result["scope_ok"])
        self.assertEqual(result["branch_name"], "feature/test")
        self.assertEqual(len(result["files_to_write"]), 1)

    @patch("agent.nodes.mcp.get_mcp_tools")
    async def test_mcp_node(self, mock_get_tools):
        mock_tools = {
            "create_branch_and_commit_code": AsyncMock(),
            "open_pull_request": AsyncMock()
        }
        mock_tools["create_branch_and_commit_code"].ainvoke.return_value = {"status": "success"}
        mock_tools["open_pull_request"].ainvoke.return_value = {"pr_url": "http://github.com/pr/1"}
        mock_get_tools.return_value = mock_tools

        state = {
            "branch_name": "feature/test",
            "files_to_write": [{"path": "file1.py", "content": "print('hello')"}],
            "commit_message": "Test commit",
            "pr_title": "Test PR",
            "pr_description": "Test Desc"
        }
        result = await mcp_node(state)

        # Point 5: mcp_node récupère correctement files_to_write.
        self.assertEqual(result["pull_request_url"], "http://github.com/pr/1")

    @patch("agent.nodes.mcp.get_mcp_tools")
    @patch("agent.nodes.scope_check.get_mcp_tools")
    @patch("agent.nodes.planning.get_mcp_tools")
    @patch("agent.nodes.repository.get_mcp_tools")
    async def test_full_workflow(
        self,
        mock_repo_tools,
        mock_planning_tools,
        mock_scope_tools,
        mock_mcp_tools
    ):
        # Point 1: Le State circule correctement entre les nodes.
        # Point 7: Le workflow complet peut être exécuté avec des MCP tools mockés.
        
        mock_r_tools = {
            "explore_repo_structure": AsyncMock(),
            "search_code": AsyncMock(),
        }
        mock_r_tools["explore_repo_structure"].ainvoke.return_value = {
            "likely_context_files": [{"path": "file1.py"}]
        }
        mock_r_tools["search_code"].ainvoke.return_value = "Mocked Context"
        mock_repo_tools.return_value = mock_r_tools

        mock_p_tools = {"read_repo_file": AsyncMock()}
        mock_p_tools["read_repo_file"].ainvoke.return_value = "Contenu de file1.py"
        mock_planning_tools.return_value = mock_p_tools

        mock_s_tools = {"generate_implementation_plan": AsyncMock()}
        mock_s_tools["generate_implementation_plan"].ainvoke.return_value = {
            "scope_ok": True,
            "questions": [],
            "branch_name": "feature/full-test",
            "commit_message": "Full Test commit",
            "pr_title": "Full Test PR",
            "pr_description": "Full Test Desc",
            "files": [{"path": "file1.py", "content": "print('full')"}],
        }
        mock_scope_tools.return_value = mock_s_tools

        mock_m_tools = {
            "create_branch_and_commit_code": AsyncMock(),
            "open_pull_request": AsyncMock()
        }
        mock_m_tools["create_branch_and_commit_code"].ainvoke.return_value = {"status": "success"}
        mock_m_tools["open_pull_request"].ainvoke.return_value = {"pr_url": "http://github.com/pr/full"}
        mock_mcp_tools.return_value = mock_m_tools

        state = {"user_request": "Test complet"}
        
        # Act
        result = await app.ainvoke(state)
        
        # Assert workflow ran successfully
        self.assertIn("pull_request_url", result)
        self.assertEqual(result["pull_request_url"], "http://github.com/pr/full")
        self.assertEqual(result["branch_name"], "feature/full-test")

if __name__ == '__main__':
    unittest.main()
