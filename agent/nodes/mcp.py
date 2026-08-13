from agent.nodes.mcp_client import get_mcp_tools, unwrap_mcp_result
from agent.state import AgentState


async def mcp_node(state: AgentState) -> dict:
    print("--- 4. L'agent écrit le code généré et ouvre la PR ---")

    tools = await get_mcp_tools()
    branch_name = state["branch_name"]
    files_to_write = state["files_to_write"]

    if not branch_name or not files_to_write:
        print("--- Aucun fichier à écrire (plan vide) ---")
        return {"pull_request_url": ""}

    for file_entry in files_to_write:
        commit_result = unwrap_mcp_result(
            await tools["create_branch_and_commit_code"].ainvoke(
                {
                    "branch_name": branch_name,
                    "filepath": file_entry["path"],
                    "file_content": file_entry["content"],
                    "commit_message": state["commit_message"] or f"Ajout de {file_entry['path']}",
                }
            )
        )
        if isinstance(commit_result, dict) and "error" in commit_result:
            print(f"--- Échec du commit pour {file_entry['path']} : {commit_result} ---")
            return {"pull_request_url": ""}

    pr_result = unwrap_mcp_result(
        await tools["open_pull_request"].ainvoke(
            {
                "branch_name": branch_name,
                "title": state["pr_title"] or state["commit_message"],
                "description": state["pr_description"] or "Généré automatiquement.",
            }
        )
    )
    if isinstance(pr_result, dict) and "error" in pr_result:
        print(f"--- Échec de la création de la PR : {pr_result} ---")
        return {"pull_request_url": ""}

    url_pr_genere = pr_result.get("pr_url", "") if isinstance(pr_result, dict) else ""
    print(f"--- Pull Request créée avec succès : {url_pr_genere} ---")

    return {"pull_request_url": url_pr_genere}