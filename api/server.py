"""
api/server.py — FastAPI Web Server
------------------------------------
Provides REST + WebSocket endpoints for the web UI.

Endpoints:
  GET  /                          → Serve web UI
  POST /chat                      → Send a message, get full response
  WS   /ws                        → WebSocket for real-time step streaming
  GET  /tools                     → List available tools
  POST /reset                     → Clear conversation memory
  GET  /health                    → Health check
  GET  /patients                  → List/search patients (instant, no LLM call)
  GET  /patients/{id}             → Full structured record (instant, no LLM call)
  GET  /patients/{id}/summary     → AI-generated clinical summary (structured + document data)
  GET  /doctors                   → List/search doctors, optional specialty filter (instant, no LLM call)
  GET  /doctors/{id}              → Full profile: qualifications, availability, recent patients
  GET  /doctors/{id}/summary      → AI-generated doctor bio (profile + recent activity)
"""

import asyncio
import json
import logging
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Import agent (tool registration happens here)
from agent import Agent
from agent.tools.hospital import (
    doctor_exists,
    get_doctor_full_json,
    get_patient_full_json,
    list_doctors_json,
    list_patients_json,
    patient_exists,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Hello Agent API",
    description="Reference AI agent with ReAct loop, tools, and memory.",
    version="1.0.0",
)

# Mount static files for web UI
WEB_DIR = Path(__file__).parent.parent / "web"
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

# Single agent instance (in production, use per-session instances)
_agent = Agent()


def _run_agent(agent: Agent, message: str) -> tuple:
    """Drain the ReAct loop for one message, returning (final_answer, steps)."""
    steps = []
    answer = ""
    for step in agent.run(message):
        steps.append(step.to_dict())
        if step.type == "answer":
            answer = step.content
    return answer, steps


# ──────────────────────────────────────────────
# Request/Response Models
# ──────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    answer: str
    steps: list

class PatientSummaryResponse(BaseModel):
    patient_id: int
    summary: str

class DoctorSummaryResponse(BaseModel):
    doctor_id: int
    summary: str


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serve the web UI."""
    html_path = WEB_DIR / "index.html"
    return HTMLResponse(content=html_path.read_text())


@app.get("/login", response_class=HTMLResponse)
async def serve_login():
    """
    Serve the sign-in page. This is a demo-only gate — any non-empty
    username/password is accepted client-side (web/login.js); there's no
    server-side session, user table, or credential check. It exists for the
    professional-hospital-software look and flow, not for real access
    control (this project has no auth backend by design — see
    HOSPITAL_RAG_ARCHITECTURE.md's "Current Limitations" section).
    """
    html_path = WEB_DIR / "login.html"
    return HTMLResponse(content=html_path.read_text())


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "agent": _agent.name, "model": _agent.model_name}


@app.get("/tools")
async def get_tools():
    """List all available tools."""
    from agent.tools.registry import list_tools
    tools = list_tools()
    return {
        name: {
            "description": t.description,
            "parameters": t.parameters,
            "examples": t.examples,
        }
        for name, t in tools.items()
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send a message and get the full response with all intermediate steps.
    Use /ws for real-time streaming.
    """
    # The agent makes blocking LLM calls — run it off the event loop
    answer, steps = await asyncio.to_thread(_run_agent, _agent, request.message)
    return ChatResponse(answer=answer, steps=steps)


@app.get("/patients")
async def patients_list(query: str = "", limit: int = 50):
    """List/search patients — direct DB read, no LLM call, instant for UI browsing."""
    return {"patients": list_patients_json(query=query, limit=limit)}


@app.get("/patients/{patient_id}")
async def patient_detail(patient_id: int):
    """Full structured record for one patient — direct DB read, no LLM call."""
    record = get_patient_full_json(patient_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"No patient found with ID {patient_id}")
    return record


@app.get("/patients/{patient_id}/summary", response_model=PatientSummaryResponse)
async def patient_summary(patient_id: int):
    """
    Generate an AI clinical summary for one patient, combining structured
    records (admissions, prescriptions, labs, surgeries) with unstructured
    documents (discharge summaries, scan reports, doctor's notes via RAG).

    Uses a fresh, stateless Agent per call — independent of the shared
    chat agent's conversation memory, since this is a one-shot report,
    not a turn in an ongoing conversation.
    """
    if not patient_exists(patient_id):
        raise HTTPException(status_code=404, detail=f"No patient found with ID {patient_id}")

    prompt = (
        f"Generate a clinical summary for patient ID {patient_id}. Include demographics, "
        f"admission history, prescriptions, lab reports, and surgeries from their record. "
        f"Also check their documents for relevant discharge summaries, scan/radiology "
        f"reports, or doctor's notes, and incorporate key findings. Structure the summary "
        f"with clear sections."
    )

    def run() -> tuple:
        return _run_agent(Agent(), prompt)

    answer, steps = await asyncio.to_thread(run)
    if not answer:
        error_step = next((s for s in steps if s["type"] == "error"), None)
        detail = error_step["content"] if error_step else "Agent failed to produce a summary."
        raise HTTPException(status_code=502, detail=detail)
    return PatientSummaryResponse(patient_id=patient_id, summary=answer)


@app.get("/doctors")
async def doctors_list(query: str = "", specialty: str = "", limit: int = 50):
    """List/search doctors, optionally filtered by specialty — direct DB read, no LLM call."""
    return {"doctors": list_doctors_json(query=query, specialty=specialty, limit=limit)}


@app.get("/doctors/{doctor_id}")
async def doctor_detail(doctor_id: int):
    """Full doctor profile: qualifications, weekly availability, recent patient encounters."""
    record = get_doctor_full_json(doctor_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"No doctor found with ID {doctor_id}")
    return record


@app.get("/doctors/{doctor_id}/summary", response_model=DoctorSummaryResponse)
async def doctor_summary(doctor_id: int):
    """
    Generate an AI-written bio for one doctor, combining their profile with
    recent patient activity. Uses a fresh, stateless Agent per call — same
    reasoning as /patients/{id}/summary.
    """
    if not doctor_exists(doctor_id):
        raise HTTPException(status_code=404, detail=f"No doctor found with ID {doctor_id}")

    prompt = (
        f"Look up doctor ID {doctor_id} and write a short professional profile summary: "
        f"their specialty, qualifications, experience, and weekly availability, plus a "
        f"one-sentence note on their recent patient activity. Keep it concise and well-organized."
    )

    def run() -> tuple:
        return _run_agent(Agent(), prompt)

    answer, steps = await asyncio.to_thread(run)
    if not answer:
        error_step = next((s for s in steps if s["type"] == "error"), None)
        detail = error_step["content"] if error_step else "Agent failed to produce a summary."
        raise HTTPException(status_code=502, detail=detail)
    return DoctorSummaryResponse(doctor_id=doctor_id, summary=answer)


@app.post("/reset")
async def reset():
    """Clear conversation memory — start fresh."""
    _agent.reset()
    return {"status": "ok", "message": "Conversation memory cleared."}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time step streaming.

    Protocol:
      Client sends: {"message": "What is 2+2?"}
      Client sends: {"action": "cancel"}   → abort the request currently in flight
      Client sends: {"action": "reset"}    → clear conversation memory
      Server sends: multiple {"type": "thought"|"action"|"observation"|"answer"|"error"|"cancelled", "content": "..."}
      Server sends: {"type": "done"} when complete

    Cancellation is cooperative, not instant: the agent loop (agent/core.py)
    only checks for it between LLM round-trips and tool calls, since neither
    provider SDK is called in a way that supports aborting a request already
    in flight. To keep the UI responsive anyway, this handler sends the
    "cancelled" step to the client as soon as the cancel message arrives,
    without waiting for the agent's own generator to unwind — that generator
    keeps running in its worker thread until its current checkpoint, but its
    (now unused) result is simply dropped.
    """
    await websocket.accept()
    logger.info("WebSocket client connected")

    try:
        while True:
            # Receive user message
            data = await websocket.receive_text()
            payload = json.loads(data)

            if payload.get("action") == "reset":
                _agent.reset()
                await websocket.send_text(json.dumps({"type": "reset", "content": "Memory cleared."}))
                continue

            if payload.get("action") == "cancel":
                continue  # nothing in flight at the top of the loop

            user_message = payload.get("message", "").strip()
            if not user_message:
                continue

            # Captured so a cancelled turn's user message (and any tool
            # observations already recorded before cancel took effect) can be
            # rolled back — otherwise it lingers as an "unanswered" turn and
            # the next message's LLM call tries to address it too.
            mark = len(_agent.memory)
            cancel_event = threading.Event()
            step_gen = _agent.run(user_message, cancel_event=cancel_event)
            done_sentinel = object()
            last_step_type = None

            async def drain_steps():
                nonlocal last_step_type
                # The agent generator makes blocking LLM calls, so pull each
                # step in a worker thread to keep the event loop responsive.
                while True:
                    step = await asyncio.to_thread(next, step_gen, done_sentinel)
                    if step is done_sentinel:
                        return
                    last_step_type = step.type
                    await websocket.send_text(json.dumps(step.to_dict()))
                    if step.type in ("answer", "error", "cancelled"):
                        return

            async def listen_for_cancel():
                # Runs concurrently with drain_steps() on the same socket,
                # watching for an out-of-band cancel message.
                while True:
                    msg = await websocket.receive_text()
                    try:
                        p = json.loads(msg)
                    except json.JSONDecodeError:
                        continue
                    if p.get("action") == "cancel":
                        cancel_event.set()
                        return

            drain_task = asyncio.create_task(drain_steps())
            listen_task = asyncio.create_task(listen_for_cancel())
            done, _pending = await asyncio.wait(
                {drain_task, listen_task}, return_when=asyncio.FIRST_COMPLETED
            )

            cancelled = False
            if listen_task in done:
                exc = listen_task.exception()
                drain_task.cancel()
                try:
                    await drain_task
                except (asyncio.CancelledError, Exception):
                    pass
                if exc is not None:
                    raise exc  # e.g. client disconnected — let the outer handler deal with it
                await websocket.send_text(json.dumps({"type": "cancelled", "content": "Request cancelled.", "tool_name": ""}))
                cancelled = True
            else:
                listen_task.cancel()
                try:
                    await listen_task
                except asyncio.CancelledError:
                    pass
                drain_task.result()  # re-raise any exception from drain_steps()
                cancelled = last_step_type == "cancelled"

            if cancelled:
                # Safe because turns are processed strictly one at a time on
                # this connection: nothing else can have appended to memory
                # between `mark` being captured and now.
                _agent.memory.truncate_to(mark)

            # Signal completion
            await websocket.send_text(json.dumps({"type": "done"}))

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_text(json.dumps({"type": "error", "content": str(e)}))
        except Exception:
            pass  # socket already closed
