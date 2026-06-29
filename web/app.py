"""
Web Frontend — FastAPI server for the Onboarding Agent.

Provides REST API endpoints for:
  - Employee dashboard & details
  - Task management
  - Compliance status
  - Escalations & email logs
  - AI chat (single-agent & multi-agent)

Run:
    python -m web.app
"""

import os
import sys
import json
import asyncio
import traceback
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from typing import Optional

# Add project root to path
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session as DBSession
from langgraph.checkpoint.sqlite import SqliteSaver

from pydantic import BaseModel
from src.config import DB_PATH, LLM_MODEL, CHECKPOINT_DB
from src.database.models import Employee, OnboardingTask, Escalation, EmailLog
from web.schema import ChatRequest, ChatResponse, ToolCallInfo, ErrorResponse

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)

# Global checkpointer — initialised once at startup, closed on shutdown
_checkpointer: SqliteSaver | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise the SqliteSaver checkpointer at app startup so it persists
    across requests instead of reconnecting on every call (Lab 8 Task 2)."""
    global _checkpointer
    import sqlite3
    conn = sqlite3.connect(CHECKPOINT_DB, check_same_thread=False)
    _checkpointer = SqliteSaver(conn)
    _checkpointer.setup()
    yield
    # Cleanup on shutdown
    conn.close()
    _checkpointer = None


app = FastAPI(title="Onboarding Agent", version="1.0.0", lifespan=lifespan)

# Serve static files
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── Helpers ──────────────────────────────────────────────────────────────

def _json_serial(obj):
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def _employee_dict(emp: Employee) -> dict:
    return {
        "id": emp.id,
        "employeeId": emp.employee_id,
        "firstName": emp.first_name,
        "lastName": emp.last_name,
        "email": emp.email,
        "role": emp.role,
        "department": emp.department,
        "manager": emp.manager,
        "startDate": emp.start_date.isoformat() if emp.start_date else None,
        "location": emp.location,
        "status": emp.status,
    }


def _task_dict(t: OnboardingTask) -> dict:
    overdue = (
        t.status != "complete"
        and t.due_date
        and t.due_date < date.today()
    )
    return {
        "id": t.id,
        "taskName": t.task_name,
        "description": t.description,
        "category": t.category,
        "status": "overdue" if overdue else t.status,
        "dueDate": t.due_date.isoformat() if t.due_date else None,
        "completedDate": t.completed_date.isoformat() if t.completed_date else None,
        "reminderCount": t.reminder_count,
    }


def _escalation_dict(e: Escalation) -> dict:
    return {
        "id": e.id,
        "employeeId": e.employee_id,
        "taskId": e.task_id,
        "reason": e.reason,
        "urgency": e.urgency,
        "createdAt": e.created_at.isoformat() if e.created_at else None,
        "resolvedAt": e.resolved_at.isoformat() if e.resolved_at else None,
        "resolvedBy": e.resolved_by,
    }


def _email_dict(e: EmailLog) -> dict:
    return {
        "id": e.id,
        "recipient": e.recipient,
        "subject": e.subject,
        "body": e.body,
        "sentAt": e.sent_at.isoformat() if e.sent_at else None,
        "emailType": e.email_type,
    }


# ── Dashboard / Stats ───────────────────────────────────────────────────

@app.get("/api/stats")
def get_stats():
    with DBSession(engine) as db:
        total_emp = db.query(Employee).count()
        total_tasks = db.query(OnboardingTask).count()
        completed = db.query(OnboardingTask).filter(OnboardingTask.status == "complete").count()
        overdue = db.query(OnboardingTask).filter(
            OnboardingTask.status != "complete",
            OnboardingTask.due_date < date.today(),
        ).count()
        pending = total_tasks - completed - overdue
        if pending < 0:
            pending = 0
        escalations = db.query(Escalation).filter(Escalation.resolved_at.is_(None)).count()
        emails_sent = db.query(EmailLog).count()

        # Compliance: employees with all compliance tasks complete
        compliant = 0
        for emp in db.query(Employee).all():
            comp_tasks = [t for t in emp.tasks if t.category == "compliance"]
            if comp_tasks and all(t.status == "complete" for t in comp_tasks):
                compliant += 1

        return {
            "totalEmployees": total_emp,
            "totalTasks": total_tasks,
            "completedTasks": completed,
            "overdueTasks": overdue,
            "pendingTasks": pending,
            "openEscalations": escalations,
            "emailsSent": emails_sent,
            "compliantEmployees": compliant,
            "completionRate": round(completed / total_tasks * 100, 1) if total_tasks else 0,
        }


# ── Employees ────────────────────────────────────────────────────────────

@app.get("/api/employees")
def list_employees():
    with DBSession(engine) as db:
        emps = db.query(Employee).all()
        result = []
        for emp in emps:
            d = _employee_dict(emp)
            tasks = emp.tasks
            total = len(tasks)
            done = sum(1 for t in tasks if t.status == "complete")
            overdue_count = sum(
                1 for t in tasks
                if t.status != "complete" and t.due_date and t.due_date < date.today()
            )
            d["taskProgress"] = {
                "total": total,
                "completed": done,
                "overdue": overdue_count,
                "percentage": round(done / total * 100) if total else 0,
            }
            result.append(d)
        return result


@app.get("/api/employees/{employee_id}")
def get_employee(employee_id: str):
    with DBSession(engine) as db:
        emp = db.query(Employee).filter(Employee.employee_id == employee_id).first()
        if not emp:
            raise HTTPException(404, f"Employee {employee_id} not found")
        d = _employee_dict(emp)
        d["tasks"] = [_task_dict(t) for t in emp.tasks]
        d["escalations"] = [_escalation_dict(e) for e in emp.escalations]
        d["emails"] = [_email_dict(e) for e in emp.emails]

        # Compliance summary
        comp_tasks = [t for t in emp.tasks if t.category == "compliance"]
        comp_done = sum(1 for t in comp_tasks if t.status == "complete")
        d["compliance"] = {
            "total": len(comp_tasks),
            "completed": comp_done,
            "status": "COMPLIANT" if comp_done == len(comp_tasks) and comp_tasks else "NON-COMPLIANT",
        }

        # Category breakdown
        categories = {}
        for t in emp.tasks:
            cat = t.category or "other"
            if cat not in categories:
                categories[cat] = {"total": 0, "completed": 0}
            categories[cat]["total"] += 1
            if t.status == "complete":
                categories[cat]["completed"] += 1
        d["categoryBreakdown"] = categories

        return d


# ── Tasks ────────────────────────────────────────────────────────────────

class TaskUpdate(BaseModel):
    status: str


@app.put("/api/tasks/{task_id}")
def update_task(task_id: int, body: TaskUpdate):
    with DBSession(engine) as db:
        task = db.query(OnboardingTask).filter(OnboardingTask.id == task_id).first()
        if not task:
            raise HTTPException(404, "Task not found")
        task.status = body.status
        if body.status == "complete":
            task.completed_date = date.today()
        db.commit()
        db.refresh(task)
        return _task_dict(task)


# ── Escalations ──────────────────────────────────────────────────────────

@app.get("/api/escalations")
def list_escalations():
    with DBSession(engine) as db:
        escs = (
            db.query(Escalation)
            .order_by(Escalation.created_at.desc())
            .limit(50)
            .all()
        )
        result = []
        for e in escs:
            d = _escalation_dict(e)
            # Add employee & task info
            emp = db.query(Employee).get(e.employee_id)
            task = db.query(OnboardingTask).get(e.task_id) if e.task_id else None
            d["employeeName"] = f"{emp.first_name} {emp.last_name}" if emp else "Unknown"
            d["employeeCode"] = emp.employee_id if emp else "?"
            d["taskName"] = task.task_name if task else "N/A"
            result.append(d)
        return result


# ── Email Logs ───────────────────────────────────────────────────────────

@app.get("/api/emails")
def list_emails():
    with DBSession(engine) as db:
        emails = (
            db.query(EmailLog)
            .order_by(EmailLog.sent_at.desc())
            .limit(50)
            .all()
        )
        result = []
        for e in emails:
            d = _email_dict(e)
            emp = db.query(Employee).get(e.employee_id)
            d["employeeName"] = f"{emp.first_name} {emp.last_name}" if emp else "Unknown"
            d["employeeCode"] = emp.employee_id if emp else "?"
            result.append(d)
        return result


# ── AI Chat ──────────────────────────────────────────────────────────────

def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [p["text"] for p in content if isinstance(p, dict) and p.get("type") == "text"]
        return "\n".join(parts)
    return str(content)


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """POST /chat — Invoke the onboarding agent and return the full response."""
    from langchain_core.messages import HumanMessage, AIMessage

    try:
        # Resolve thread_id: use the client-supplied value or generate a new one
        thread_id = req.thread_id or str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}

        if req.mode == "multi":
            from src.agents.multi_agent_graph import build_multi_agent_graph
            graph = build_multi_agent_graph(checkpointer=_checkpointer)
            result = graph.invoke(
                {
                    "messages": [HumanMessage(content=req.message)],
                    "current_agent": "hr_coordinator",
                    "handover_summary": "",
                    "task_complete": False,
                },
                config=config,
            )
        else:
            from src.agents.graph import build_react_graph
            graph = build_react_graph(checkpointer=_checkpointer)
            result = graph.invoke(
                {"messages": [HumanMessage(content=req.message)]},
                config=config,
            )

        # Collect tool calls and final response
        tool_calls = []
        final_response = ""
        for msg in result["messages"]:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_calls.append(ToolCallInfo(name=tc["name"], args=tc["args"]))
            if isinstance(msg, AIMessage):
                text = _extract_text(msg.content)
                if text.strip():
                    final_response = text

        return ChatResponse(
            response=final_response,
            tool_calls=tool_calls,
            mode=req.mode,
            thread_id=thread_id,
            status="success",
        )
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            return JSONResponse(status_code=429, content={
                "error": "Rate limit exceeded. Please wait a minute and try again.",
                "detail": "Gemini API free tier quota exhausted.",
            })
        return JSONResponse(status_code=500, content={
            "error": f"Agent error: {error_msg}",
        })


@app.post("/api/stream")
async def stream_chat(req: ChatRequest):
    """POST /stream — Stream the agent's response node-by-node using SSE."""
    from langchain_core.messages import HumanMessage, AIMessage

    # Resolve thread_id for persistent streaming sessions
    thread_id = req.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    async def event_generator():
        try:
            if req.mode == "multi":
                from src.agents.multi_agent_graph import build_multi_agent_graph
                graph = build_multi_agent_graph(checkpointer=_checkpointer)
                input_state = {
                    "messages": [HumanMessage(content=req.message)],
                    "current_agent": "hr_coordinator",
                    "handover_summary": "",
                    "task_complete": False,
                }
            else:
                from src.agents.graph import build_react_graph
                graph = build_react_graph(checkpointer=_checkpointer)
                input_state = {"messages": [HumanMessage(content=req.message)]}

            # Stream node-by-node
            for event in graph.stream(input_state, config=config):
                for node_name, node_output in event.items():
                    messages = node_output.get("messages", [])
                    for msg in messages:
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            for tc in msg.tool_calls:
                                data = json.dumps({
                                    "type": "tool_call",
                                    "node": node_name,
                                    "tool": tc["name"],
                                    "args": tc["args"],
                                })
                                yield f"data: {data}\n\n"
                        elif isinstance(msg, AIMessage):
                            text = _extract_text(msg.content)
                            if text.strip():
                                data = json.dumps({
                                    "type": "agent_response",
                                    "node": node_name,
                                    "content": text,
                                })
                                yield f"data: {data}\n\n"
                        elif hasattr(msg, "content") and hasattr(msg, "name") and msg.name:
                            data = json.dumps({
                                "type": "tool_result",
                                "node": node_name,
                                "tool": msg.name,
                                "content": _extract_text(msg.content)[:500],
                            })
                            yield f"data: {data}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            error_data = json.dumps({"type": "error", "content": str(e)})
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# ── Serve SPA ────────────────────────────────────────────────────────────

@app.get("/")
def serve_index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/{path:path}")
def catch_all(path: str):
    # Try static file first
    file_path = STATIC_DIR / path
    if file_path.exists() and file_path.is_file():
        return FileResponse(str(file_path))
    return FileResponse(str(STATIC_DIR / "index.html"))


# ── Entry Point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print(f"\n  Onboarding Agent Web UI")
    print(f"  http://localhost:5000\n")
    uvicorn.run(app, host="0.0.0.0", port=5000)
