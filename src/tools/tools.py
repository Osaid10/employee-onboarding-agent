"""
Lab 3 — Onboarding Agent Tools.

Eight LangChain tools that the ReAct agent can invoke to query policies,
inspect employee records, manage tasks, send reminders, escalate issues,
and generate reports.
"""

from datetime import datetime, date, timezone
from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.config import DB_PATH
from src.database.models import (
    Employee,
    OnboardingTask,
    Escalation,
    EmailLog,
    TASK_STATUS_VALUES,
    URGENCY_VALUES,
)
from src.ingestion.ingest_data import query_knowledge_base


# ---------------------------------------------------------------------------
# Database helper
# ---------------------------------------------------------------------------
_engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)


def _get_session() -> Session:
    return Session(_engine)


# ---------------------------------------------------------------------------
# 1. query_onboarding_policy
# ---------------------------------------------------------------------------
class QueryOnboardingPolicyInput(BaseModel):
    """Input schema for querying the onboarding knowledge base."""
    query: str = Field(description="Natural-language question about onboarding policies.")
    department: Optional[str] = Field(
        default=None,
        description="Optional department filter (e.g. 'engineering', 'sales', 'hr', 'all').",
    )


@tool(args_schema=QueryOnboardingPolicyInput)
def query_onboarding_policy(query: str, department: Optional[str] = None) -> str:
    """Search the onboarding policy knowledge base using RAG.

    Use this tool when the user asks about company policies, compliance
    requirements, onboarding procedures, benefits, or any documented process.
    Returns the most relevant policy excerpts from the vector database.
    """
    try:
        filters = None
        if department:
            filters = {"department": department}

        results = query_knowledge_base(query, filters=filters, k=3)

        if not results:
            return "No relevant policy information found for your query."

        output_parts: list[str] = []
        for i, doc in enumerate(results, 1):
            meta = doc.metadata
            source = meta.get("source_file", "unknown")
            section = meta.get("section_header", "N/A")
            score = meta.get("relevance_score", "N/A")
            priority = meta.get("priority_level", "N/A")
            output_parts.append(
                f"--- Result {i} (relevance: {score}, priority: {priority}) ---\n"
                f"Source: {source} | Section: {section}\n\n"
                f"{doc.page_content}\n"
            )
        return "\n".join(output_parts)
    except Exception as e:
        return f"Error querying knowledge base: {e}"


# ---------------------------------------------------------------------------
# 2. get_employee_info
# ---------------------------------------------------------------------------
class GetEmployeeInfoInput(BaseModel):
    """Input schema for retrieving employee information."""
    employee_id: str = Field(description="The employee ID (e.g. 'EMP-001').")


@tool(args_schema=GetEmployeeInfoInput)
def get_employee_info(employee_id: str) -> str:
    """Retrieve an employee's profile from the HRIS database.

    Use this tool to look up employee details such as name, department,
    role, manager, start date, location, and current onboarding status.
    """
    session = _get_session()
    try:
        employee = (
            session.query(Employee)
            .filter(Employee.employee_id == employee_id)
            .first()
        )
        if not employee:
            return f"No employee found with ID '{employee_id}'."

        return (
            f"Employee Record:\n"
            f"  ID:         {employee.employee_id}\n"
            f"  Name:       {employee.first_name} {employee.last_name}\n"
            f"  Email:      {employee.email}\n"
            f"  Role:       {employee.role}\n"
            f"  Department: {employee.department}\n"
            f"  Manager:    {employee.manager}\n"
            f"  Start Date: {employee.start_date}\n"
            f"  Location:   {employee.location}\n"
            f"  Status:     {employee.status}"
        )
    except Exception as e:
        return f"Error retrieving employee info: {e}"
    finally:
        session.close()


# ---------------------------------------------------------------------------
# 3. get_task_status
# ---------------------------------------------------------------------------
class GetTaskStatusInput(BaseModel):
    """Input schema for retrieving onboarding task statuses."""
    employee_id: str = Field(description="The employee ID (e.g. 'EMP-001').")


@tool(args_schema=GetTaskStatusInput)
def get_task_status(employee_id: str) -> str:
    """Get all onboarding tasks and their statuses for an employee.

    Use this tool to see what tasks have been assigned, which are complete,
    which are pending or in progress, and which are overdue.
    """
    session = _get_session()
    try:
        employee = (
            session.query(Employee)
            .filter(Employee.employee_id == employee_id)
            .first()
        )
        if not employee:
            return f"No employee found with ID '{employee_id}'."

        tasks = (
            session.query(OnboardingTask)
            .filter(OnboardingTask.employee_id == employee.id)
            .order_by(OnboardingTask.due_date)
            .all()
        )

        if not tasks:
            return f"No onboarding tasks found for employee '{employee_id}'."

        lines = [f"Onboarding Tasks for {employee.first_name} {employee.last_name} ({employee_id}):\n"]
        for t in tasks:
            overdue_flag = ""
            if t.status != "complete" and t.due_date and t.due_date < date.today():
                overdue_flag = " [OVERDUE]"
            lines.append(
                f"  - {t.task_name}\n"
                f"    Category: {t.category} | Status: {t.status}{overdue_flag}\n"
                f"    Due: {t.due_date} | Completed: {t.completed_date or 'N/A'}\n"
                f"    Reminders sent: {t.reminder_count}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Error retrieving task status: {e}"
    finally:
        session.close()


# ---------------------------------------------------------------------------
# 4. update_task_status  [HIGH-RISK]
# ---------------------------------------------------------------------------
class UpdateTaskStatusInput(BaseModel):
    """Input schema for updating an onboarding task's status."""
    employee_id: str = Field(description="The employee ID (e.g. 'EMP-001').")
    task_name: str = Field(description="The exact name of the task to update.")
    new_status: str = Field(
        description="The new status for the task. Must be one of: pending, in_progress, complete, overdue."
    )


@tool(args_schema=UpdateTaskStatusInput)
def update_task_status(employee_id: str, task_name: str, new_status: str) -> str:
    """Update the status of a specific onboarding task for an employee.

    **This is a HIGH-RISK action that modifies data.** Use only when you
    are confident the status change is correct. Valid statuses are:
    pending, in_progress, complete, overdue.
    """
    if new_status not in TASK_STATUS_VALUES:
        return (
            f"Invalid status '{new_status}'. "
            f"Must be one of: {', '.join(TASK_STATUS_VALUES)}"
        )

    session = _get_session()
    try:
        employee = (
            session.query(Employee)
            .filter(Employee.employee_id == employee_id)
            .first()
        )
        if not employee:
            return f"No employee found with ID '{employee_id}'."

        task = (
            session.query(OnboardingTask)
            .filter(
                OnboardingTask.employee_id == employee.id,
                OnboardingTask.task_name == task_name,
            )
            .first()
        )
        if not task:
            return (
                f"No task named '{task_name}' found for employee '{employee_id}'."
            )

        old_status = task.status
        task.status = new_status
        if new_status == "complete":
            task.completed_date = date.today()
        session.commit()

        return (
            f"Task '{task_name}' for {employee_id} updated: "
            f"{old_status} -> {new_status}."
        )
    except Exception as e:
        session.rollback()
        return f"Error updating task status: {e}"
    finally:
        session.close()


# ---------------------------------------------------------------------------
# 5. send_reminder_email  [HIGH-RISK]
# ---------------------------------------------------------------------------
class SendReminderEmailInput(BaseModel):
    """Input schema for sending a reminder email."""
    employee_id: str = Field(description="The employee ID (e.g. 'EMP-001').")
    subject: str = Field(description="Email subject line.")
    body: str = Field(description="Email body content.")


@tool(args_schema=SendReminderEmailInput)
def send_reminder_email(employee_id: str, subject: str, body: str) -> str:
    """Send a reminder email to an employee and log it in the database.

    **This is a HIGH-RISK action.** The email is simulated (not actually
    sent) but is recorded in the EmailLog table for audit purposes.
    """
    session = _get_session()
    try:
        employee = (
            session.query(Employee)
            .filter(Employee.employee_id == employee_id)
            .first()
        )
        if not employee:
            return f"No employee found with ID '{employee_id}'."

        email_log = EmailLog(
            employee_id=employee.id,
            recipient=employee.email,
            subject=subject,
            body=body,
            sent_at=datetime.now(timezone.utc),
            email_type="reminder",
        )
        session.add(email_log)
        session.commit()

        return (
            f"Reminder email sent (simulated) to {employee.email}.\n"
            f"  Subject: {subject}\n"
            f"  Logged in EmailLog with id={email_log.id}."
        )
    except Exception as e:
        session.rollback()
        return f"Error sending reminder email: {e}"
    finally:
        session.close()


# ---------------------------------------------------------------------------
# 6. send_escalation_alert  [HIGH-RISK]
# ---------------------------------------------------------------------------
class SendEscalationAlertInput(BaseModel):
    """Input schema for creating an escalation alert."""
    employee_id: str = Field(description="The employee ID (e.g. 'EMP-001').")
    task_name: str = Field(description="The name of the task being escalated.")
    reason: str = Field(description="Reason for the escalation.")
    urgency: str = Field(
        description="Urgency level. Must be one of: low, medium, high, critical."
    )


@tool(args_schema=SendEscalationAlertInput)
def send_escalation_alert(
    employee_id: str, task_name: str, reason: str, urgency: str
) -> str:
    """Create an escalation record and simulate a Slack-style alert.

    **This is a HIGH-RISK action.** Use when a task is critically overdue,
    repeated reminders have failed, or a compliance deadline is at risk.
    Valid urgency levels: low, medium, high, critical.
    """
    if urgency not in URGENCY_VALUES:
        return (
            f"Invalid urgency '{urgency}'. "
            f"Must be one of: {', '.join(URGENCY_VALUES)}"
        )

    session = _get_session()
    try:
        employee = (
            session.query(Employee)
            .filter(Employee.employee_id == employee_id)
            .first()
        )
        if not employee:
            return f"No employee found with ID '{employee_id}'."

        task = (
            session.query(OnboardingTask)
            .filter(
                OnboardingTask.employee_id == employee.id,
                OnboardingTask.task_name == task_name,
            )
            .first()
        )
        if not task:
            return (
                f"No task named '{task_name}' found for employee '{employee_id}'."
            )

        escalation = Escalation(
            employee_id=employee.id,
            task_id=task.id,
            reason=reason,
            urgency=urgency,
            created_at=datetime.now(timezone.utc),
        )
        session.add(escalation)
        session.commit()

        slack_msg = (
            f"[ESCALATION - {urgency.upper()}]\n"
            f"Employee: {employee.first_name} {employee.last_name} ({employee_id})\n"
            f"Task: {task_name}\n"
            f"Reason: {reason}\n"
            f"Manager: {employee.manager}\n"
            f"Escalation ID: {escalation.id}"
        )

        return (
            f"Escalation created and Slack alert simulated.\n\n{slack_msg}"
        )
    except Exception as e:
        session.rollback()
        return f"Error creating escalation: {e}"
    finally:
        session.close()


# ---------------------------------------------------------------------------
# 7. generate_onboarding_report
# ---------------------------------------------------------------------------
class GenerateOnboardingReportInput(BaseModel):
    """Input schema for generating an onboarding progress report."""
    employee_id: str = Field(description="The employee ID (e.g. 'EMP-001').")


@tool(args_schema=GenerateOnboardingReportInput)
def generate_onboarding_report(employee_id: str) -> str:
    """Generate a comprehensive onboarding progress report for an employee.

    Returns a formatted summary including overall completion percentage,
    status breakdown by category, overdue items, and upcoming deadlines.
    """
    session = _get_session()
    try:
        employee = (
            session.query(Employee)
            .filter(Employee.employee_id == employee_id)
            .first()
        )
        if not employee:
            return f"No employee found with ID '{employee_id}'."

        tasks = (
            session.query(OnboardingTask)
            .filter(OnboardingTask.employee_id == employee.id)
            .order_by(OnboardingTask.due_date)
            .all()
        )

        if not tasks:
            return f"No onboarding tasks found for employee '{employee_id}'."

        total = len(tasks)
        completed = sum(1 for t in tasks if t.status == "complete")
        in_progress = sum(1 for t in tasks if t.status == "in_progress")
        pending = sum(1 for t in tasks if t.status == "pending")
        overdue = sum(
            1 for t in tasks
            if t.status != "complete" and t.due_date and t.due_date < date.today()
        )
        completion_pct = round((completed / total) * 100, 1) if total else 0

        # Category breakdown
        categories: dict[str, dict] = {}
        for t in tasks:
            cat = t.category
            if cat not in categories:
                categories[cat] = {"total": 0, "complete": 0}
            categories[cat]["total"] += 1
            if t.status == "complete":
                categories[cat]["complete"] += 1

        # Overdue items
        overdue_items = [
            t for t in tasks
            if t.status != "complete" and t.due_date and t.due_date < date.today()
        ]

        # Upcoming deadlines (next 7 days, not complete)
        upcoming = [
            t for t in tasks
            if t.status != "complete"
            and t.due_date
            and date.today() <= t.due_date
            and (t.due_date - date.today()).days <= 7
        ]

        # Build report
        lines = [
            "=" * 50,
            f"ONBOARDING PROGRESS REPORT",
            f"Employee: {employee.first_name} {employee.last_name} ({employee_id})",
            f"Department: {employee.department} | Role: {employee.role}",
            f"Start Date: {employee.start_date} | Status: {employee.status}",
            "=" * 50,
            "",
            f"Overall Completion: {completion_pct}% ({completed}/{total} tasks)",
            f"  Completed:   {completed}",
            f"  In Progress: {in_progress}",
            f"  Pending:     {pending}",
            f"  Overdue:     {overdue}",
            "",
            "--- Category Breakdown ---",
        ]
        for cat, info in sorted(categories.items()):
            cat_pct = round((info["complete"] / info["total"]) * 100, 1)
            lines.append(f"  {cat}: {info['complete']}/{info['total']} ({cat_pct}%)")

        if overdue_items:
            lines.append("")
            lines.append("--- OVERDUE ITEMS (action required) ---")
            for t in overdue_items:
                days_late = (date.today() - t.due_date).days
                lines.append(f"  * {t.task_name} — due {t.due_date} ({days_late} days late)")

        if upcoming:
            lines.append("")
            lines.append("--- Upcoming Deadlines (next 7 days) ---")
            for t in upcoming:
                days_left = (t.due_date - date.today()).days
                lines.append(f"  * {t.task_name} — due {t.due_date} ({days_left} day(s) left)")

        lines.append("")
        lines.append("=" * 50)
        return "\n".join(lines)
    except Exception as e:
        return f"Error generating report: {e}"
    finally:
        session.close()


# ---------------------------------------------------------------------------
# 8. check_compliance_status
# ---------------------------------------------------------------------------
class CheckComplianceStatusInput(BaseModel):
    """Input schema for checking compliance status."""
    employee_id: str = Field(description="The employee ID (e.g. 'EMP-001').")


@tool(args_schema=CheckComplianceStatusInput)
def check_compliance_status(employee_id: str) -> str:
    """Check whether all compliance-related onboarding tasks are complete.

    Returns a compliance status summary listing which required compliance
    tasks are done and which are still outstanding. Use this to determine
    if an employee has met all regulatory and legal onboarding requirements.
    """
    session = _get_session()
    try:
        employee = (
            session.query(Employee)
            .filter(Employee.employee_id == employee_id)
            .first()
        )
        if not employee:
            return f"No employee found with ID '{employee_id}'."

        compliance_tasks = (
            session.query(OnboardingTask)
            .filter(
                OnboardingTask.employee_id == employee.id,
                OnboardingTask.category == "compliance",
            )
            .order_by(OnboardingTask.due_date)
            .all()
        )

        if not compliance_tasks:
            return (
                f"No compliance tasks found for employee '{employee_id}'. "
                f"This may indicate tasks have not been assigned yet."
            )

        total = len(compliance_tasks)
        completed = [t for t in compliance_tasks if t.status == "complete"]
        incomplete = [t for t in compliance_tasks if t.status != "complete"]

        all_done = len(incomplete) == 0
        status_label = "COMPLIANT" if all_done else "NON-COMPLIANT"

        lines = [
            f"Compliance Status for {employee.first_name} {employee.last_name} ({employee_id}): {status_label}",
            f"Compliance Tasks: {len(completed)}/{total} complete",
            "",
        ]

        if completed:
            lines.append("Completed:")
            for t in completed:
                lines.append(f"  [done] {t.task_name} (completed {t.completed_date})")

        if incomplete:
            lines.append("Outstanding:")
            for t in incomplete:
                overdue_note = ""
                if t.due_date and t.due_date < date.today():
                    days_late = (date.today() - t.due_date).days
                    overdue_note = f" ** OVERDUE by {days_late} days **"
                lines.append(
                    f"  [{t.status}] {t.task_name} — due {t.due_date}{overdue_note}"
                )

        return "\n".join(lines)
    except Exception as e:
        return f"Error checking compliance status: {e}"
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Convenience list of all tools for the agent graph
# ---------------------------------------------------------------------------
ALL_TOOLS = [
    query_onboarding_policy,
    get_employee_info,
    get_task_status,
    update_task_status,
    send_reminder_email,
    send_escalation_alert,
    generate_onboarding_report,
    check_compliance_status,
]
