"""kit rehearse [questions...]  — run the demo questions end to end and report PASS/FAIL.

domain.yaml:
demo_questions:
  - "plain question"
  - {q: "compound question", expect_tools: [run_model_predictions, visualization_agent]}
Writes a transcript to logs/rehearsal_<time>.md (kept forever) — also useful as a backup of what the demo does."""
import asyncio
import datetime as dt
import time

from kit import ROOT
from kit.common import D
from kit_core.ops import Ops


async def _ask(q: str):
    from google.adk.runners import InMemoryRunner
    from google.genai import types
    from kit_agent.agent import root_agent
    runner = InMemoryRunner(agent=root_agent, app_name="rehearse")
    s = await runner.session_service.create_session(app_name="rehearse", user_id="rehearsal")
    msg = types.Content(role="user", parts=[types.Part(text=q)])
    tools, texts = [], []
    async for ev in runner.run_async(user_id="rehearsal", session_id=s.id, new_message=msg):
        for fc in (ev.get_function_calls() if hasattr(ev, "get_function_calls") else []):
            tools.append(fc.name)
        if ev.content and ev.content.parts and ev.is_final_response():
            texts += [p.text for p in ev.content.parts if getattr(p, "text", None)]
    return tools, "\n".join(texts)


def run(args):
    ops = Ops("rehearse")
    qs = [{"q": q} for q in args.questions] or [
        {"q": x} if isinstance(x, str) else x for x in D.load_domain().get("demo_questions", [])]
    if not qs:
        raise SystemExit("No questions: pass some or add demo_questions: to domain.yaml")
    out = ROOT / "logs" / f"rehearsal_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    fails = 0
    lines = ["# Rehearsal transcript\n"]
    for item in qs:
        t0 = time.time()
        try:
            tools, text = asyncio.run(_ask(item["q"]))
            miss = [t for t in item.get("expect_tools", []) if t not in tools]
            status = "PASS" if text and not miss else "FAIL"
            note = f" missing tools: {miss}" if miss else ""
        except Exception as e:
            tools, text, status, note = [], "", "FAIL", f" error: {e}"
        fails += status == "FAIL"
        ops.log(f"{status} ({time.time() - t0:.0f}s) {item['q'][:70]} tools={sorted(set(tools))}{note}")
        lines += [f"## {status}: {item['q']}", f"tools: {tools}{note}", "", text, ""]
    out.write_text("\n".join(lines), encoding="utf-8")
    ops.log(f"Transcript: {out}")
    raise SystemExit(1 if fails else 0)


def add_parser(sub):
    p = sub.add_parser("rehearse", help="run demo questions end to end; PASS/FAIL + transcript")
    p.add_argument("questions", nargs="*")
    p.set_defaults(fn=run)
