from google.adk.tools import ToolContext


def request_approval(action: str, rationale: str, tool_context: ToolContext) -> dict:
    """Ask the human operator to approve a proposed high-stakes action before it is treated as final.

    Use for any action that affects people: sending alerts, ordering evacuations, dispatching teams.
    The run pauses for a human Approve/Reject (ADK tool confirmation).

    Args:
        action: the exact action proposed, in one sentence.
        rationale: why, with the key numbers/evidence.

    Returns:
        dict with status 'approved'. Approved actions are recorded in session state.
    """
    approved = tool_context.state.get("approved_actions", [])
    tool_context.state["approved_actions"] = approved + [{"action": action, "rationale": rationale}]
    return {"status": "approved", "action": action}
