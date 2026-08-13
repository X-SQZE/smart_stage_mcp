from agent.nodes.mcp_client import get_mcp_tools
from agent.state import AgentState


async def planning_node(state: AgentState) -> dict:
    print("--- 2. L'agent rassemble le contexte documentaire disponible ---")

    tools = await get_mcp_tools()
    fichiers_pertinents = state["relevant_files"]

    contenus_docs = []
    for filepath in fichiers_pertinents:
        contenu = await tools["read_repo_file"].ainvoke({"filepath": filepath})
        contenus_docs.append(f"--- {filepath} ---\n{contenu}")

    contexte_complet = (
        f"Contexte RAG : {state['repository_context']}\n\n"
        "Documentation consultée :\n"
        + ("\n\n".join(contenus_docs) if contenus_docs else "(aucune documentation trouvée — repo probablement vide ou nouveau)")
    )

    return {"architectural_plan": contexte_complet}