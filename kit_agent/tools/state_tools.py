from google.adk.tools import ToolContext


def append_to_state(tool_context: ToolContext, field: str, response: str) -> dict:
    """Append text to a list stored in session state under `field`.

    Use to accumulate feedback or findings across loop iterations or agents.

    Args:
        field: state key to append to.
        response: text to append.

    Returns:
        dict with status.
    """
    existing = tool_context.state.get(field, [])
    tool_context.state[field] = existing + [response]
    return {"status": "success"}
