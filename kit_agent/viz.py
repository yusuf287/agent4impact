from google.adk.agents import Agent
from google.adk.code_executors import BuiltInCodeExecutor

from .model import make_model, shared_config
from .prompts import VISUALIZATION_DESCRIPTION, visualization_instructions


def build_visualization_agent() -> Agent:
    """Code-execution agent. Must stay alone (no other tools) and be used via AgentTool."""
    return Agent(name="visualization_agent", model=make_model(), generate_content_config=shared_config(),
                 description=VISUALIZATION_DESCRIPTION, instruction=visualization_instructions(),
                 code_executor=BuiltInCodeExecutor())
