from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from models import ProcurementAction
from server.environment import ProcurementComplianceEnvironment
import memory as cognee_memory

app = FastAPI(title="Procurement Compliance Review Environment")

env = ProcurementComplianceEnvironment()


class ResetRequest(BaseModel):
    seed: Optional[int] = None
    episode_id: Optional[str] = None
    task_id: Optional[str] = None


@app.on_event("startup")
async def seed_policy_memory():
    """
    Ingest all policy_notes from every task into Cognee once at startup,
    so recall_policy() has something real to search from day one.
    Wrapped in try/except so the server still boots if COGNEE_API_KEY
    isn't set yet (e.g. first-time local run before you add secrets).
    """
    try:
        seen = set()
        for task in env.tasks:
            note = task["request"]["policy_notes"]
            if note not in seen:
                await cognee_memory.remember_policy(note)
                seen.add(note)
        print(f"[startup] Seeded {len(seen)} unique policy notes into Cognee.")
    except Exception as e:
        print(f"[startup] Skipping Cognee policy seed (memory unavailable): {e}")


@app.get("/")
def root():
    return {
        "name": "Procurement Compliance Review Environment",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/tasks")
def list_tasks():
    """Return all available task IDs — used by validators to discover tasks."""
    return {
        "task_ids": env.get_task_ids(),
        "total": len(env.get_task_ids()),
    }


@app.post("/reset")
async def reset(request: ResetRequest = None):
    try:
        obs = await env.reset(
            seed=request.seed if request else None,
            episode_id=request.episode_id if request else None,
            task_id=request.task_id if request else None,
        )
        return obs.model_dump()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/step")
async def step(action: ProcurementAction):
    try:
        obs = await env.step(action)
        return obs.model_dump()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/state")
def state():
    try:
        return env.state().model_dump()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Cognee memory endpoints — these are what you demo on camera.
# ---------------------------------------------------------------------------

@app.get("/memory/vendor-history")
async def vendor_history(department: str, vendor_status: str = "unapproved"):
    """
    Directly query what the agent 'remembers' about a department/vendor.
    Call this before and after a /step to show the memory changing —
    this is your money-shot demo endpoint.
    """
    try:
        history = await cognee_memory.recall_history(department, vendor_status)
        return {"department": department, "vendor_status": vendor_status, "recalled_history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/memory/improve")
async def memory_improve():
    """
    Triggers memify — re-derives graph relationships over accumulated history.
    Call periodically (e.g. every N decisions) or manually for the demo.
    """
    try:
        await cognee_memory.improve()
        return {"status": "memory improved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/memory/forget")
async def memory_forget():
    """
    Prunes stale history data. In production you'd filter by retention date;
    here it demonstrates the forget() operation explicitly.
    """
    try:
        result = await cognee_memory.forget_stale_history()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def main():
    import uvicorn
    uvicorn.run(
        "server.app:app",
        host="0.0.0.0",
        port=7860,
        reload=False,
    )


if __name__ == "__main__":
    main()