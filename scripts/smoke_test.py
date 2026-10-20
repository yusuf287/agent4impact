"""Programmatic smoke test (lab 1 pattern: Runner + session + types.Content).
Run:  python scripts/smoke_test.py "How many days per year has Dallas gone above 100F?"
Prints every tool call / result as it happens, then the final answer, so you can see progress."""
import asyncio
import json
import pathlib
import sys
import warnings

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
warnings.filterwarnings("ignore", category=UserWarning)  # hide ADK "[EXPERIMENTAL] feature" notices

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

from kit_agent.agent import root_agent  # noqa: E402


def _short(x, n=300):
    s = json.dumps(x, default=str)
    return s if len(s) <= n else s[:n] + "…"


async def main(q: str):
    runner = InMemoryRunner(agent=root_agent, app_name="smoke")
    session = await runner.session_service.create_session(app_name="smoke", user_id="u")
    msg = types.Content(role="user", parts=[types.Part(text=q)])
    print(f">>> {q}\n(working… multi-agent answers can take 1-3 minutes)\n", flush=True)
    async for ev in runner.run_async(user_id="u", session_id=session.id, new_message=msg):
        for fc in ev.get_function_calls() or []:
            print(f"  -> [{ev.author}] calls {fc.name} {_short(fc.args, 200)}", flush=True)
        for fr in ev.get_function_responses() or []:
            print(f"  <- {fr.name}: {_short(fr.response)}", flush=True)
        if ev.content and ev.content.parts:
            for p in ev.content.parts:
                if p.text and not getattr(p, "thought", False):
                    print(f"\n[{ev.author}] {p.text}", flush=True)
    print("\n=== done ===")


if __name__ == "__main__":
    asyncio.run(main(" ".join(sys.argv[1:]) or "Give me a one-line summary of the data you can access."))
