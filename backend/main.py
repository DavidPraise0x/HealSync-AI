import asyncio
import json
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import os

from backend.db import db_manager
from backend.agent import remediation_agent

app = FastAPI(title="HealSync AI Console")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active log queues for SSE streaming
log_queues = {}

class IncidentCreate(BaseModel):
    title: str
    description: str
    symptoms: str
    severity: str # 'low', 'medium', 'high', 'critical'

@app.get("/api/incidents")
def get_incidents():
    return db_manager.get_incidents()

@app.get("/api/runbooks")
def get_runbooks():
    cursor = db_manager.conn.cursor()
    cursor.execute("SELECT id, name, description, symptoms, remediation_steps FROM runbooks")
    return [dict(row) for row in cursor.fetchall()]

@app.get("/api/incidents/{incident_id}")
def get_incident(incident_id: int):
    inc = db_manager.get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    return inc

@app.get("/api/stats")
def get_stats():
    incidents = db_manager.get_incidents(limit=100)
    total = len(incidents)
    active = sum(1 for i in incidents if i["status"] == "active" or i["status"] == "remediating")
    resolved = sum(1 for i in incidents if i["status"] == "resolved")
    failed = sum(1 for i in incidents if i["status"] == "failed")
    
    return {
        "total": total,
        "active": active,
        "resolved": resolved,
        "failed": failed
    }

async def run_remediation_task(incident_id: int):
    # Initialize log queue if not exists
    if incident_id not in log_queues:
        log_queues[incident_id] = asyncio.Queue()
        
    async def log_callback(msg):
        # Push message to queue
        await log_queues[incident_id].put(msg)

    # Run agent remediation loop
    try:
        await remediation_agent.run_remediation(incident_id, log_callback)
    except Exception as e:
        err_msg = f"Agent encountered error during remediation: {str(e)}"
        await log_callback(err_msg)
        db_manager.update_incident_status(incident_id, 'failed', log_message=err_msg)
    finally:
        # Send complete sentinel
        await log_queues[incident_id].put("[COMPLETE]")

@app.post("/api/incidents")
async def trigger_incident(incident: IncidentCreate, background_tasks: BackgroundTasks):
    incident_id = db_manager.create_incident(
        title=incident.title,
        description=incident.description,
        symptoms=incident.symptoms,
        severity=incident.severity
    )
    
    # Initialize queue for this incident
    log_queues[incident_id] = asyncio.Queue()
    
    # Run agent as a background task
    background_tasks.add_task(run_remediation_task, incident_id)
    
    return {"status": "triggered", "incident_id": incident_id}

@app.get("/api/stream/{incident_id}")
def stream_incident_logs(incident_id: int):
    if incident_id not in log_queues:
        # Check if the incident exists and is already resolved
        inc = db_manager.get_incident(incident_id)
        if not inc:
            raise HTTPException(status_code=404, detail="Incident not found")
        
        # Generator for already resolved incidents
        async def static_log_generator():
            logs = json.loads(inc["remediation_logs"]) if inc["remediation_logs"] else []
            for log in logs:
                yield f"data: {log}\n\n"
                await asyncio.sleep(0.05)
            yield "data: [COMPLETE]\n\n"
            
        return StreamingResponse(static_log_generator(), media_type="text/event-stream")

    async def event_generator():
        queue = log_queues[incident_id]
        while True:
            msg = await queue.get()
            yield f"data: {msg}\n\n"
            if msg == "[COMPLETE]":
                break
        # Clean up queue
        if incident_id in log_queues:
            del log_queues[incident_id]
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# Serve frontend static assets
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="static")
else:
    @app.get("/")
    def read_root():
        return {"message": "HealSync API server. Frontend folder not found."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
