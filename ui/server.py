"""Demo UI with a VISIBLE agent loop: chat on the left, live tool-call trace on the right,
Approve/Reject buttons for human approval, charts rendered from saved artifacts.
Run:  python -m kit ui   -> http://localhost:8080
Streams server-sent events: {kind: session|tool_call|tool_result|confirm|text|image|error|done}"""
import base64
import json
import uuid
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from google.adk.runners import InMemoryRunner
from google.genai import types

from kit_agent.agent import root_agent

APP, USER = "kit_ui", "ui"
CONFIRM = "adk_request_confirmation"  # ADK's function-call name for FunctionTool(require_confirmation=True)

app = FastAPI()
runner = InMemoryRunner(agent=root_agent, app_name=APP)
_sessions: dict[str, str] = {}
HTML = (Path(__file__).parent / "index.html").read_text(encoding="utf-8")


class Chat(BaseModel):
    session_id: str = ""
    message: str


class Confirm(BaseModel):
    session_id: str
    call_id: str
    approved: bool


@app.get("/", response_class=HTMLResponse)
def index():
    return HTML


def _sse(obj) -> str:
    return f"data: {json.dumps(obj, default=str)}\n\n"


def _short(obj, n=600):
    s = json.dumps(obj, default=str)
    return s if len(s) <= n else s[:n] + "…"


async def _session(sid: str) -> str:
    if sid not in _sessions:
        s = await runner.session_service.create_session(app_name=APP, user_id=USER)
        _sessions[sid] = s.id
    return _sessions[sid]


def _stream(sid: str, adk_sid: str, message: types.Content):
    async def gen():
        yield _sse({"kind": "session", "session_id": sid})
        try:
            async for ev in runner.run_async(user_id=USER, session_id=adk_sid, new_message=message):
                for fc in ev.get_function_calls() or []:
                    if fc.name == CONFIRM:  # run is paused until the human answers
                        orig = (fc.args or {}).get("originalFunctionCall", {})
                        yield _sse({"kind": "confirm", "call_id": fc.id, "data": _short(orig.get("args", fc.args))})
                    else:
                        yield _sse({"kind": "tool_call", "author": ev.author, "name": fc.name, "data": _short(fc.args)})
                for fr in ev.get_function_responses() or []:
                    yield _sse({"kind": "tool_result", "author": ev.author, "name": fr.name, "data": _short(fr.response)})
                # Charts: the code executor saves images as artifacts (not inline parts)
                delta = getattr(getattr(ev, "actions", None), "artifact_delta", None) or {}
                for fname, ver in delta.items():
                    art = await runner.artifact_service.load_artifact(
                        app_name=APP, user_id=USER, session_id=adk_sid, filename=fname, version=ver)
                    if art and art.inline_data and (art.inline_data.mime_type or "").startswith("image/"):
                        b64 = base64.b64encode(art.inline_data.data).decode()
                        yield _sse({"kind": "image", "data": f"data:{art.inline_data.mime_type};base64,{b64}"})
                if ev.content and ev.content.parts and ev.is_final_response():
                    for p in ev.content.parts:
                        if getattr(p, "inline_data", None) and (p.inline_data.mime_type or "").startswith("image/"):
                            b64 = base64.b64encode(p.inline_data.data).decode()
                            yield _sse({"kind": "image", "data": f"data:{p.inline_data.mime_type};base64,{b64}"})
                        elif getattr(p, "text", None):
                            yield _sse({"kind": "text", "author": ev.author, "data": p.text})
        except Exception as e:  # show failures in the UI instead of hanging
            yield _sse({"kind": "error", "data": str(e)})
        yield _sse({"kind": "done"})

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/api/chat")
async def chat(req: Chat):
    sid = req.session_id or str(uuid.uuid4())
    adk_sid = await _session(sid)
    return _stream(sid, adk_sid, types.Content(role="user", parts=[types.Part(text=req.message)]))


@app.post("/api/confirm")
async def confirm(req: Confirm):
    adk_sid = await _session(req.session_id)
    resp = types.Part(function_response=types.FunctionResponse(
        id=req.call_id, name=CONFIRM, response={"confirmed": req.approved}))
    return _stream(req.session_id, adk_sid, types.Content(role="user", parts=[resp]))
