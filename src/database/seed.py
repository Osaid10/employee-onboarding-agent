"""
Seed the HRIS database with sample employees and onboarding tasks.

Usage:
    python -m src.database.seed
"""

import json
import os
from datetime import date, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config import DB_PATH, EMPLOYEES_DIR
from src.database.models import (
    Base,
    Employee,
    OnboardingTask,
    Escalation,
    create_tables,
)


# ---------------------------------------------------------------------------
# Task templates
# ---------------------------------------------------------------------------
# Each tuple: (task_name, description, category, days_offset_from_start)
#   Negative offset = due BEFORE start date
#   Positive offset = due AFTER start date
#   Zero            = due ON start date

COMMON_TASKS: list[tuple[str, str, str, int]] = [
    # Compliance tasks (pre-start)
    (
        "Complete background check",
        "Authorize and complete the pre-employment background check via the HR portal.",
        "compliance",
        -10,
    ),
    (
        "Sign NDA",
        "Review and sign the Non-Disclosure Agreement through DocuSign.",
        "compliance",
        -7,
    ),
    (
        "Submit W-4 Form",
        "Complete federal tax withholding form W-4 in the payroll system.",
        "compliance",
        -5,
    ),
    (
        "Submit I-9 Form",
        "Provide identity and employment authorization documents for I-9 verification.",
        "compliance",
        -3,
    ),
    (
        "Sign employee handbook acknowledgment",
        "Read the employee handbook and sign the acknowledgment form.",
        "compliance",
        -2,
    ),
    (
        "Sign acceptable use policy",
        "Review and agree to the IT acceptable use policy.",
        "compliance",
        -1,
    ),
    # IT setup (around start date)
    (
        "Set up laptop",
        "IT will image and provision a laptop for the new hire. Pick up from IT office.",
        "it_setup",
        0,
    ),
    (
        "Get building access badge",
        "Visit Security desk to have your badge photo taken and badge activated.",
        "it_setup",
        0,
    ),
    (
        "Configure email and Slack accounts",
        "IT creates corporate email, Slack, and Google Workspace accounts.",
        "it_setup",
        0,
    ),
    (
        "Set up VPN access",
        "Install corporate VPN client and verify remote connectivity.",
        "it_setup",
        1,
    ),
    # Training (first two weeks)
    (
        "Complete orientation",
        "Attend the half-day new-hire orientation session with HR.",
        "training",
        0,
    ),
    (
        "Meet with manager",
        "Schedule and attend an introductory 1:1 with your direct manager.",
        "training",
        1,
    ),
    (
        "Complete security awareness training",
        "Finish the mandatory cybersecurity awareness e-learning module.",
        "training",
        7,
    ),
    (
        "Complete anti-harassment training",
        "Complete the required workplace anti-harassment online course.",
        "training",
        14,
    ),
    # HR / benefits
    (
        "Enroll in health insurance",
        "Select medical, dental, and vision plans through the benefits portal.",
        "hr",
        30,
    ),
    (
        "Enroll in 401(k)",
        "Set up retirement savings plan contributions and choose investments.",
        "hr",
        30,
    ),
]

# Department-specific extras
ENGINEERING_TASKS: list[tuple[str, str, str, int]] = [
    (
        "Set up development environment",
        "Clone repos, install toolchains, and verify local build passes.",
        "it_setup",
        1,
    ),
    (
        "Get GitHub/GitLab repository access",
        "Request access to relevant source code repositories from your tech lead.",
        "it_setup",
        1,
    ),
    (
        "Complete code review guidelines training",
        "Read the engineering team's code review standards and best practices.",
        "training",
        3,
    ),
    (
        "Attend architecture overview session",
        "Join the scheduled system architecture walkthrough led by a staff engineer.",
        "training",
        5,
    ),
]

SALES_TASKS: list[tuple[str, str, str, int]] = [
    (
        "Get Salesforce CRM access",
        "Request Salesforce license and complete introductory CRM training.",
        "it_setup",
        1,
    ),
    (
        "Complete product knowledge certification",
        "Pass the product knowledge assessment with a score of 80% or above.",
        "training",
        14,
    ),
    (
        "Shadow a senior rep on calls",
        "Attend at least 5 customer/prospect calls with a senior team member.",
        "training",
        7,
    ),
    (
        "Review sales playbook",
        "Read the full sales playbook including objection handling scripts.",
        "training",
        3,
    ),
]

PRODUCT_TASKS: list[tuple[str, str, str, int]] = [
    (
        "Get Jira/Linear access",
        "Request access to the product management tool and join relevant boards.",
        "it_setup",
        1,
    ),
    (
        "Review product roadmap",
        "Read the current quarterly and annual product roadmap documents.",
        "training",
        3,
    ),
    (
        "Attend user research session",
        "Observe at least one scheduled user research or usability testing session.",
        "training",
        7,
    ),
    (
        "Meet cross-functional stakeholders",
        "Schedule intro meetings with engineering leads, design lead, and marketing.",
        "training",
        5,
    ),
]

HR_TASKS: list[tuple[str, str, str, int]] = [
    (
        "Complete HR systems access (Workday/BambooHR)",
        "Request access to the HRIS platform and complete the introductory walkthrough.",
        "it_setup",
        1,
    ),
    (
        "Review HR policies and procedures manual",
        "Read the full HR policies manual including leave, performance, and disciplinary procedures.",
        "training",
        3,
    ),
    (
        "Complete employment law compliance training",
        "Finish the mandatory employment law e-learning module covering FLSA, ADA, and FMLA.",
        "compliance",
        7,
    ),
    (
        "Shadow an HR generalist for one week",
        "Observe HR operations including recruitment, onboarding, and employee relations processes.",
        "training",
        5,
    ),
]

FINANCE_TASKS: list[tuple[str, str, str, int]] = [
    (
        "Get ERP system access (SAP/NetSuite)",
        "Request ERP credentials and complete the finance system orientation training.",
        "it_setup",
        1,
    ),
    (
        "Complete financial compliance training",
        "Finish mandatory training on SOX controls, expense policies, and financial reporting standards.",
        "compliance",
        7,
    ),
    (
        "Review chart of accounts and budget structure",
        "Study the company's chart of accounts, cost centers, and annual budget framework.",
        "training",
        3,
    ),
    (
        "Meet with treasury and accounting leads",
        "Schedule introductory meetings with accounts payable, accounts receivable, and treasury teams.",
        "training",
        5,
    ),
]

MARKETING_TASKS: list[tuple[str, str, str, int]] = [
    (
        "Get marketing tools access (HubSpot/Marketo)",
        "Request access to marketing automation platform and complete the introductory course.",
        "it_setup",
        1,
    ),
    (
        "Review brand guidelines and content standards",
        "Study the company brand book, messaging framework, and content style guide.",
        "training",
        3,
    ),
    (
        "Complete digital marketing compliance training",
        "Finish training on CAN-SPAM, GDPR for marketing, and social media policy.",
        "compliance",
        7,
    ),
    (
        "Attend product demo and competitive analysis session",
        "Join a scheduled product demo and review the competitive landscape document.",
        "training",
        5,
    ),
]

DEPARTMENT_TASKS: dict[str, list[tuple[str, str, str, int]]] = {
    "Engineering": ENGINEERING_TASKS,
    "Sales": SALES_TASKS,
    "Product": PRODUCT_TASKS,
    "HR": HR_TASKS,
    "Finance": FINANCE_TASKS,
    "Marketing": MARKETING_TASKS,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_tasks_for_employee(
    employee_db_id: int,
    start_date: date,
    department: str,
) -> list[OnboardingTask]:
    """Generate OnboardingTask objects from templates."""

    templates = list(COMMON_TASKS)
    templates.extend(DEPARTMENT_TASKS.get(department, []))

    tasks: list[OnboardingTask] = []
    for task_name, description, category, day_offset in templates:
        due = start_date + timedelta(days=day_offset)
        tasks.append(
            OnboardingTask(
                employee_id=employee_db_id,
                task_name=task_name,
                description=description,
                category=category,
                status="pending",
                due_date=due,
                completed_date=None,
                reminder_count=0,
            )
        )
    return tasks


def _mark_overdue_tasks(session, employee_db_id: int, today: date) -> None:
    """Mark tasks whose due_date has passed as 'overdue' and bump reminder counts."""
    overdue_tasks = (
        session.query(OnboardingTask)
        .filter(
            OnboardingTask.employee_id == employee_db_id,
            OnboardingTask.due_date < today,
            OnboardingTask.status.in_(["pending", "in_progress"]),
        )
        .all()
    )
    for task in overdue_tasks:
        task.status = "overdue"
        task.reminder_count = 3  # already past escalation threshold


def _create_escalations_for_overdue(session, employee_db_id: int) -> None:
    """Create escalation records for every overdue task on this employee."""
    overdue_tasks = (
        session.query(OnboardingTask)
        .filter(
            OnboardingTask.employee_id == employee_db_id,
            OnboardingTask.status == "overdue",
        )
        .all()
    )
    for task in overdue_tasks:
        days_overdue = (date.today() - task.due_date).days
        if days_overdue > 7:
            urgency = "critical"
        elif days_overdue > 3:
            urgency = "high"
        else:
            urgency = "medium"

        escalation = Escalation(
            employee_id=employee_db_id,
            task_id=task.id,
            reason=(
                f"Task '{task.task_name}' is {days_overdue} day(s) overdue. "
                f"Reminder count ({task.reminder_count}) exceeds threshold."
            ),
            urgency=urgency,
            created_at=datetime.utcnow(),
        )
        session.add(escalation)


# ---------------------------------------------------------------------------
# Main seed function
# ---------------------------------------------------------------------------

def seed_database() -> None:
    """Drop existing data, recreate tables, and populate with sample data."""

    # Remove old DB file if present so we start fresh
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed existing database at {DB_PATH}")

    engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
    create_tables(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # ------------------------------------------------------------------
    # 1. Load employees from JSON
    # ------------------------------------------------------------------
    employees_json_path = os.path.join(EMPLOYEES_DIR, "sample_employees.json")
    with open(employees_json_path, "r", encoding="utf-8") as f:
        employees_data = json.load(f)

    print(f"Loaded {len(employees_data)} employees from {employees_json_path}")

    employee_records: list[Employee] = []
    for emp in employees_data:
        record = Employee(
            employee_id=emp["employee_id"],
            first_name=emp["first_name"],
            last_name=emp["last_name"],
            email=emp["email"],
            role=emp["role"],
            department=emp["department"],
            manager=emp["manager"],
            start_date=date.fromisoformat(emp["start_date"]),
            location=emp["location"],
            status=emp["status"],
        )
        session.add(record)
        employee_records.append(record)

    # Flush to get auto-generated IDs
    session.flush()

    # ------------------------------------------------------------------
    # 2. Generate onboarding tasks for each employee
    # ------------------------------------------------------------------
    today = date.today()

    for record in employee_records:
        tasks = _build_tasks_for_employee(
            employee_db_id=record.id,
            start_date=record.start_date,
            department=record.department,
        )
        session.add_all(tasks)
        print(
            f"  {record.employee_id} ({record.first_name} {record.last_name}): "
            f"{len(tasks)} tasks created"
        )

    session.flush()

    # ------------------------------------------------------------------
    # 3. Mark overdue tasks for several employees (demo escalation)
    # ------------------------------------------------------------------
    for emp_code in ("EMP-003", "EMP-004", "EMP-007"):
        emp = (
            session.query(Employee)
            .filter(Employee.employee_id == emp_code)
            .one()
        )
        _mark_overdue_tasks(session, emp.id, today)
        _create_escalations_for_overdue(session, emp.id)
        print(f"  {emp_code}: overdue tasks flagged and escalations created")

    # ------------------------------------------------------------------
    # Commit
    # ------------------------------------------------------------------
    session.commit()
    session.close()
    engine.dispose()

    print(f"\nDatabase seeded successfully at {DB_PATH}")


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    seed_database()
