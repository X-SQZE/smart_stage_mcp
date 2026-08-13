from agent.nodes.mcp_client import get_mcp_tools
from agent.state import AgentState


async def repository_node(state: AgentState) -> dict:
    print("--- 1. L'agent analyse le dépôt et récupère le contexte via le RAG MCP ---")

    user_prompt = state["user_request"]
    tools = await get_mcp_tools()

    structure = await tools["explore_repo_structure"].ainvoke({"ref": "main"})
    rag_result = await tools["search_code"].ainvoke({"question": user_prompt})

    fichiers_trouves = [doc["path"] for doc in structure.get("likely_context_files", [])] \
        if isinstance(structure, dict) else []

    return {
        "repository_context": str(rag_result),
        "relevant_files": fichiers_trouves,
    }