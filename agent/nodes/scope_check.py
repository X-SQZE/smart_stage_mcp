from agent.nodes.mcp_client import get_mcp_tools, unwrap_mcp_result
from agent.state import AgentState


async def scope_check_node(state: AgentState) -> dict:
    print("--- 3. Génération du plan d'implémentation (ou des questions) ---")

    tools = await get_mcp_tools()
    result = await tools["generate_implementation_plan"].ainvoke(
        {
            "user_request": state["user_request"],
            "project_context": state["architectural_plan"],
        }
    )

    plan = unwrap_mcp_result(result)

    return {
        "scope_ok": plan.get("scope_ok", False),
        "clarifying_questions": plan.get("questions", []),
        "branch_name": plan.get("branch_name", ""),
        "commit_message": plan.get("commit_message", ""),
        "pr_title": plan.get("pr_title", ""),
        "pr_description": plan.get("pr_description", ""),
        "files_to_write": plan.get("files", []),
    }