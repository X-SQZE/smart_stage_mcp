from agent.nodes.mcp_client import get_mcp_tools, unwrap_mcp_result
from agent.state import AgentState


async def mcp_node(state: AgentState) -> dict:
    print("--- 4. L'agent écrit le code généré et ouvre la PR ---")

    tools = await get_mcp_tools()
    branch_name = state.get("branch_name")
    files_to_write = state.get("files_to_write")

    if not branch_name or not files_to_write:
        print("--- Aucun fichier à écrire (plan vide ou manquant) ---")
        return {"pull_request_url": ""}

    for file_entry in files_to_write:
        filepath = file_entry.get("path") or file_entry.get("file")
        if not filepath:
            continue
        commit_result = unwrap_mcp_result(
            await tools["create_branch_and_commit_code"].ainvoke(
                {
                    "branch_name": branch_name,
                    "filepath": filepath,
                    "file_content": file_entry.get("content", ""),
                    "commit_message": state.get("commit_message") or f"Ajout de {filepath}",
                }
            )
        )
        if isinstance(commit_result, dict) and "error" in commit_result:
            print(f"--- Échec du commit pour {filepath} : {commit_result} ---")
            return {"pull_request_url": ""}

    pr_result = unwrap_mcp_result(
        await tools["open_pull_request"].ainvoke(
            {
                "branch_name": branch_name,
                "title": state.get("pr_title") or state.get("commit_message") or "Update from Agent_Rag",
                "description": state.get("pr_description") or "Généré automatiquement.",
            }
        )
    )
    if isinstance(pr_result, dict) and "error" in pr_result:
        print(f"--- Échec de la création de la PR : {pr_result} ---")
        return {"pull_request_url": ""}

    url_pr_genere = pr_result.get("pr_url", "") if isinstance(pr_result, dict) else ""
    print(f"--- Pull Request créée avec succès : {url_pr_genere} ---")

    return {"pull_request_url": url_pr_genere}