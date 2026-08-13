"""Client MCP partagé : lance mon_serveur.py en stdio et expose ses tools."""

from __future__ import annotations

import json
import os
import sys

from langchain_mcp_adapters.client import MultiServerMCPClient

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SERVER_SCRIPT_PATH = os.path.join(PROJECT_ROOT, "mon_serveur.py")

_client: MultiServerMCPClient | None = None
_tools_cache: dict | None = None


def _get_client() -> MultiServerMCPClient:
    global _client
    if _client is None:
        _client = MultiServerMCPClient(
            {
                "smartstage": {
                    "command": sys.executable,
                    "args": [SERVER_SCRIPT_PATH],
                    "transport": "stdio",
                }
            }
        )
    return _client


async def get_mcp_tools() -> dict:
    global _tools_cache
    if _tools_cache is None:
        client = _get_client()
        tools = await client.get_tools()
        _tools_cache = {tool.name: tool for tool in tools}
    return _tools_cache


def unwrap_mcp_result(result):
    """Normalise le retour d'un tool MCP (dict, str JSON, ou liste de content
    blocks type [{'type': 'text', 'text': '...'}]) en dict/valeur Python."""
    if isinstance(result, dict):
        return result

    if isinstance(result, str):
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return result

    if isinstance(result, list):
        for item in result:
            text = None
            if isinstance(item, dict):
                text = item.get("text")
            elif hasattr(item, "text"):
                text = item.text
            if text is not None:
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return text
        return result

    return result