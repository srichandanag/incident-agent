import os
import uvicorn
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import uuid
import logging

# Local imports
from agent import create_triage_graph, get_checkpointer, get_connection_pool

# Simple in‑memory store for pending HITL actions (conversation_id -> dict)
_pending_actions: Dict[str, Dict[str, Any]] = {}

logger = logging.getLogger(__name__)

app = FastAPI(title="Incident Triage API")

# Mount Gradio UI (ui.demo) at the root path 


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

# Dependency to provide a graph and checkpointer per request (reuse across calls)
def get_graph_and_saver():
    # Create a single connection pool for the application (cached)
    if not hasattr(get_graph_and_saver, "pool"):
        get_graph_and_saver.pool = get_connection_pool()
    if not hasattr(get_graph_and_saver, "saver"):
        get_graph_and_saver.saver = get_checkpointer(get_graph_and_saver.pool)
    if not hasattr(get_graph_and_saver, "graph"):
        get_graph_and_saver.graph = create_triage_graph(checkpointer=get_graph_and_saver.saver)
    return get_graph_and_saver.graph, get_graph_and_saver.saver


class IncidentRequest(BaseModel):
    description: str = Field(..., description="Brief description of the incident")
    payload: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional incident data")

class IncidentResponse(BaseModel):
    conversation_id: str = Field(..., description="Identifier for the LangGraph thread")
    hitl_required: bool = Field(..., description="Whether human approval is needed for a pending action")
    message: Optional[str] = None

@app.post("/incident", response_model=IncidentResponse)
async def submit_incident(request: IncidentRequest):
    """Create or resume a LangGraph thread for the incident and run the first step.
    Returns a conversation_id that can be used for subsequent calls.
    """
    conversation_id = str(uuid.uuid4())
    graph, saver = get_graph_and_saver()

    # Create initial state with incident details
    inputs = {"description": request.description, "payload": request.payload}
    try:
        result = graph.invoke(inputs, config={"configurable": {"thread_id": conversation_id}})
        hitl_required = result.get("hitl_required", False) if isinstance(result, dict) else False
        # Store pending HITL info in in‑memory store for test purposes
        if hitl_required:
            _pending_actions[conversation_id] = {
                "approved": None,
                "pending_id": result.get("pending_id", ""),
                "hitl_required": True,
            }
        return IncidentResponse(conversation_id=conversation_id, hitl_required=hitl_required)
    except Exception as e:
        logger.error("Error processing incident: %s", e)
        raise HTTPException(status_code=500, detail="Failed to process incident")

@app.get("/incident/{conversation_id}/result")
async def get_result(conversation_id: str):
    """Retrieve the latest investigation result for a conversation/thread."""
    graph, saver = get_graph_and_saver()
    try:
        checkpoint = saver.get_latest_checkpoint(conversation_id)
        state = checkpoint.get("values", {}) if checkpoint else {}
        return JSONResponse(content={"conversation_id": conversation_id, "state": state})
    except Exception as e:
        logger.error("Failed to retrieve result for %s: %s", conversation_id, e)
        raise HTTPException(status_code=404, detail="Conversation not found")

@app.post("/incident/{conversation_id}/approve")
async def approve_action(conversation_id: str):
    """Resolve a pending HITL escalation by approving it."""
    # Mark the pending action as approved and resume the graph.
    pending = _pending_actions.get(conversation_id)
    if not pending:
        raise HTTPException(status_code=404, detail="No pending HITL action for this conversation")
    pending["approved"] = True
    # In a real implementation we would update the checkpoint and invoke the graph again.
    logger.info("HITL approval received for conversation %s", conversation_id)
    return {"conversation_id": conversation_id, "approved": True, "pending_id": pending.get("pending_id")}

@app.post("/incident/{conversation_id}/reject")
async def reject_action(conversation_id: str):
    """Resolve a pending HITL escalation by rejecting it."""
    # Mark the pending action as rejected and resume without executing the sensitive tool.
    pending = _pending_actions.get(conversation_id)
    if not pending:
        raise HTTPException(status_code=404, detail="No pending HITL action for this conversation")
    pending["approved"] = False
    logger.info("HITL rejection received for conversation %s", conversation_id)
    return {"conversation_id": conversation_id, "rejected": True, "pending_id": pending.get("pending_id")}


@app.post("/sensitive/{conversation_id}/run")
async def run_sensitive_action(conversation_id: str):
    """Endpoint that would execute a sensitive tool – allowed only after approval."""
    pending = _pending_actions.get(conversation_id)
    if not pending:
        raise HTTPException(status_code=404, detail="No pending action found")
    if pending.get("approved") is not True:
        raise HTTPException(status_code=403, detail="Human approval required for sensitive action")
    # Here we would resume the graph and let it execute the pending tool.
    # For test purposes we simply acknowledge execution.
    return {"conversation_id": conversation_id, "status": "sensitive action executed"}

@app.get("/health")
async def health_check():
    """Simple health/readiness endpoint for deployments."""
    return JSONResponse(content={"status": "ok"})

# Mount Gradio UI (ui.demo) at the root path after all routes are defined
import gradio as gr
from ui import demo
app = gr.mount_gradio_app(app, demo, path="/")

