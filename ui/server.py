"""Demo UI with a VISIBLE agent loop (judges' #4 criterion): chat on the left, live tool-call trace on the right.
Run:  python -m kit ui   -> http://localhost:8080
Streams server-sent events: {kind: tool_call|tool_result|text|image|done, author, name, data}"""
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

app = FastAPI()
runner = InMemoryRunner(agent=root_agent, app_name="kit_ui")
_sessions: dict[str, str] = {}
HTML = (Path(__file__).parent / "index.html").read_text(encoding="utf-8")


class Chat(BaseModel):
    session_id: str = ""
    message: str


@app.get("/", response_class=HTMLResponse)
def index():
    return HTML


def _short(obj, n=600):
    s = json.dumps(obj, default=str)
    return s if len(s) <= n else s[:n] + "…"


@app.post("/api/chat")
async def chat(req: Chat):
    sid = req.session_id or str(uuid.uuid4())
    if sid not in _sessions:
        s = await runner.session_service.create_session(app_name="kit_ui", user_id="ui")
        _sessions[sid] = s.id
    msg = types.Content(role="user", parts=[types.Part(text=req.message)])

    async def gen():
        yield f"data: {json.dumps({'kind': 'session', 'session_id': sid})}\n\n"
        try:
            async for ev in runner.run_async(user_id="ui", session_id=_sessions[sid], new_message=msg):
                for fc in ev.get_function_calls() or []:
                    yield f"data: {json.dumps({'kind': 'tool_call', 'author': ev.author, 'name': fc.name, 'data': _short(fc.args)})}\n\n"
                for fr in ev.get_function_responses() or []:
                    yield f"data: {json.dumps({'kind': 'tool_result', 'author': ev.author, 'name': fr.name, 'data': _short(fr.response)})}\n\n"
                if ev.content and ev.content.parts:
                    for p in ev.content.parts:
                        if getattr(p, "inline_data", None) and p.inline_data.mime_type.startswith("image/"):
                            b64 = base64.b64encode(p.inline_data.data).decode()
                            yield f"data: {json.dumps({'kind': 'image', 'data': 'data:%s;base64,%s' % (p.inline_data.mime_type, b64)})}\n\n"
                        elif getattr(p, "text", None) and ev.is_final_response():
                            yield f"data: {json.dumps({'kind': 'text', 'author': ev.author, 'data': p.text})}\n\n"
        except Exception as e:  # show failures in the UI instead of hanging
            yield f"data: {json.dumps({'kind': 'error', 'data': str(e)})}\n\n"
        yield f"data: {json.dumps({'kind': 'done'})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
