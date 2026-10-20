"""Programmatic smoke test (lab 1 pattern: Runner + session + types.Content).
Run:  python scripts/smoke_test.py "How many neighborhoods are in the data?"
Use it before every demo to confirm credentials, dataset and tools are alive."""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

from kit_agent.agent import root_agent  # noqa: E402


async def main(q: str):
    runner = InMemoryRunner(agent=root_agent, app_name="smoke")
    session = await runner.session_service.create_session(app_name="smoke", user_id="u")
    msg = types.Content(role="user", parts=[types.Part(text=q)])
    async for ev in runner.run_async(user_id="u", session_id=session.id, new_message=msg):
        if ev.content and ev.content.parts:
            for p in ev.content.parts:
                if p.text:
                    print(f"[{ev.author}] {p.text}")


if __name__ == "__main__":
    asyncio.run(main(" ".join(sys.argv[1:]) or "Give me a one-line summary of the data you can access."))
