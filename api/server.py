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
"""

import asyncio
import json
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Import agent (tool registration happens here)
from agent import Agent
from agent.tools.hospital import get_patient_full_json, list_patients_json, patient_exists

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


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serve the web UI."""
    html_path = WEB_DIR / "index.html"
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
      Server sends: multiple {"type": "thought"|"action"|"observation"|"answer", "content": "..."}
      Server sends: {"type": "done"} when complete
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

            user_message = payload.get("message", "").strip()
            if not user_message:
                continue

            # Stream each ReAct step to the client.
            # The agent generator makes blocking LLM calls, so pull each
            # step in a worker thread to keep the event loop responsive.
            step_gen = _agent.run(user_message)
            done = object()
            while True:
                step = await asyncio.to_thread(next, step_gen, done)
                if step is done:
                    break
                await websocket.send_text(json.dumps(step.to_dict()))

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
