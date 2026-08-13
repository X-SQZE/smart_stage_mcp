from langgraph.graph import END, StateGraph

from agent.state import AgentState

from agent.nodes.repository import repository_node
from agent.nodes.planning import planning_node
from agent.nodes.scope_check import scope_check_node
from agent.nodes.mcp import mcp_node


workflow = StateGraph(AgentState)

workflow.add_node("repository", repository_node)
workflow.add_node("planning", planning_node)
workflow.add_node("scope_check", scope_check_node)
workflow.add_node("mcp", mcp_node)


workflow.set_entry_point("repository")

workflow.add_edge("repository", "planning")
workflow.add_edge("planning", "scope_check")


def route_after_scope_check(state: AgentState) -> str:
    # Si le scope n'est pas OK et qu'on a des questions, on s'arrête.
    if not state.get("scope_ok", True) and state.get("clarifying_questions"):
        return END

    return "mcp"


workflow.add_conditional_edges(
    "scope_check",
    route_after_scope_check,
    {
        "mcp": "mcp",
        END: END,
    },
)

workflow.add_edge("mcp", END)

app = workflow.compile()