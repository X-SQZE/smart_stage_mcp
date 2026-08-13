from agent.nodes.mcp import mcp_node
from agent.nodes.planning import planning_node
from agent.nodes.repository import repository_node
from agent.nodes.scope_check import scope_check_node
from agent.state import AgentState
from langgraph.graph import END, StateGraph

workflow = StateGraph(AgentState)

workflow.add_node("repository_step", repository_node)
workflow.add_node("planning_step", planning_node)
workflow.add_node("scope_check_step", scope_check_node)
workflow.add_node("mcp_step", mcp_node)

workflow.set_entry_point("repository_step")
workflow.add_edge("repository_step", "planning_step")
workflow.add_edge("planning_step", "scope_check_step")


def route_after_scope_check(state: AgentState) -> str:
    return "mcp_step" if state.get("scope_ok") else END


workflow.add_conditional_edges(
    "scope_check_step",
    route_after_scope_check,
    {"mcp_step": "mcp_step", END: END},
)
workflow.add_edge("mcp_step", END)

app = workflow.compile()