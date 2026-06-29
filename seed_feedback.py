"""
Lab 11 — Seed feedback_log.db with realistic sample interactions.

Creates 15 logged interactions (mixed thumbs-up / thumbs-down) so that:
  - analyze_feedback.py has enough negative entries to categorize
  - drift_report.md reflects real error patterns
  - The Lab 11 submission requirement of 10+ interactions is met

Usage:
    python seed_feedback.py
"""

import sqlite3
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent)
FEEDBACK_DB = os.path.join(PROJECT_ROOT, "feedback_log.db")


SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp        TEXT NOT NULL,
    thread_id        TEXT,
    user_input       TEXT NOT NULL,
    agent_response   TEXT NOT NULL,
    feedback_score   INTEGER NOT NULL,
    optional_comment TEXT DEFAULT ''
);
"""

# 15 realistic interactions — mixed scores to enable drift analysis
SAMPLE_INTERACTIONS = [
    # ── POSITIVE (thumbs up, score=+1) ────────────────────────────────────
    {
        "timestamp": (datetime.now(timezone.utc) - timedelta(days=14)).isoformat(),
        "thread_id": "thread-001",
        "user_input": "Get the onboarding status for EMP-001.",
        "agent_response": (
            "Employee EMP-001 (Marcus Chen, Software Engineer, Engineering) has 20 onboarding tasks. "
            "12 are complete, 3 are in progress, and 5 are pending. Compliance tasks are 100% complete. "
            "Next upcoming deadline: 'Enroll in health insurance' due in 4 days."
        ),
        "feedback_score": 1,
        "optional_comment": "Clear and accurate summary.",
    },
    {
        "timestamp": (datetime.now(timezone.utc) - timedelta(days=13)).isoformat(),
        "thread_id": "thread-002",
        "user_input": "What benefits can a new hire enroll in?",
        "agent_response": (
            "Based on the benefits guide, new hires can enroll in: (1) Health insurance — medical, dental, "
            "and vision plans must be selected within 30 days of start date via the benefits portal. "
            "(2) 401(k) retirement savings plan with company matching, also within 30 days. "
            "(3) Flexible spending accounts (FSA) for healthcare and dependent care."
        ),
        "feedback_score": 1,
        "optional_comment": "Exactly what I needed.",
    },
    {
        "timestamp": (datetime.now(timezone.utc) - timedelta(days=12)).isoformat(),
        "thread_id": "thread-003",
        "user_input": "Check compliance for EMP-002 and send a reminder if anything is overdue.",
        "agent_response": (
            "EMP-002 (Sarah Johnson) is NON-COMPLIANT. The 'Complete background check' task is 2 days overdue. "
            "I have sent a reminder email to sarah.j@company.com with subject 'Action Required: Complete background check'. "
            "The email has been logged in the system."
        ),
        "feedback_score": 1,
        "optional_comment": None,
    },
    {
        "timestamp": (datetime.now(timezone.utc) - timedelta(days=11)).isoformat(),
        "thread_id": "thread-004",
        "user_input": "Generate an onboarding report for EMP-004.",
        "agent_response": (
            "Onboarding Report — James Wilson (EMP-004, Product Manager):\n"
            "Overall completion: 65% (13/20 tasks done).\n"
            "Compliance: 5/6 complete — 'Sign acceptable use policy' pending.\n"
            "IT Setup: 3/4 complete.\n"
            "Training: 3/6 complete — 'Attend user research session' and 'Meet cross-functional stakeholders' overdue.\n"
            "HR/Benefits: 2/4 complete."
        ),
        "feedback_score": 1,
        "optional_comment": "Great breakdown by category.",
    },
    {
        "timestamp": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
        "thread_id": "thread-005",
        "user_input": "What are the I-9 verification requirements?",
        "agent_response": (
            "Per the compliance guidelines, I-9 verification requires the new hire to present valid identity "
            "and employment authorization documents within 3 days of their start date. Acceptable documents include "
            "a US passport, permanent resident card, or a combination of a driver's license and Social Security card. "
            "HR must retain the I-9 form for 3 years after hire date or 1 year after termination."
        ),
        "feedback_score": 1,
        "optional_comment": None,
    },
    {
        "timestamp": (datetime.now(timezone.utc) - timedelta(days=9)).isoformat(),
        "thread_id": "thread-006",
        "user_input": "Send escalation for EMP-003's overdue tasks to their manager David Kim.",
        "agent_response": (
            "Escalation created for EMP-003 (Priya Patel). 4 tasks are overdue with urgency levels: "
            "'Complete background check' — CRITICAL (14 days overdue), 'Submit W-4 Form' — HIGH (12 days overdue). "
            "Manager David Kim has been notified via Slack. Escalation IDs: ESC-0031, ESC-0032."
        ),
        "feedback_score": 1,
        "optional_comment": "Fast and complete escalation.",
    },
    {
        "timestamp": (datetime.now(timezone.utc) - timedelta(days=8)).isoformat(),
        "thread_id": "thread-007",
        "user_input": "Mark the 'Complete orientation' task as done for EMP-005.",
        "agent_response": (
            "Task 'Complete orientation' for EMP-005 (Elena Rodriguez) has been updated to COMPLETE. "
            "Completion date recorded as today. Overall onboarding progress updated to 6%."
        ),
        "feedback_score": 1,
        "optional_comment": None,
    },
    {
        "timestamp": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),
        "thread_id": "thread-008",
        "user_input": "What are the engineering-specific onboarding requirements?",
        "agent_response": (
            "Based on the engineering handbook, new engineering hires must complete: "
            "(1) Development environment setup — clone repos, install toolchains, verify local build. "
            "(2) GitHub/GitLab repository access request. "
            "(3) Code review guidelines training — read team standards and best practices. "
            "(4) Architecture overview session — scheduled walkthrough led by a staff engineer. "
            "All 4 tasks are due within the first 5 days."
        ),
        "feedback_score": 1,
        "optional_comment": "Very helpful for planning the new hire's first week.",
    },
    # ── NEGATIVE (thumbs down, score=-1) ─────────────────────────────────
    {
        "timestamp": (datetime.now(timezone.utc) - timedelta(days=6)).isoformat(),
        "thread_id": "thread-009",
        "user_input": "How many total employees are currently onboarding?",
        "agent_response": (
            "I was unable to find a specific count of currently onboarding employees. "
            "You may want to check the HR dashboard directly."
        ),
        "feedback_score": -1,
        "optional_comment": "The agent should have called get_employee_info or generate_onboarding_report to count employees.",
    },
    {
        "timestamp": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
        "thread_id": "thread-010",
        "user_input": "What is the deadline for enrolling in the 401k for EMP-001?",
        "agent_response": (
            "The 401(k) enrollment deadline varies depending on company policy. "
            "Please contact HR directly for the specific deadline for EMP-001."
        ),
        "feedback_score": -1,
        "optional_comment": "Wrong — the agent should query the knowledge base for the 30-day enrollment window and also check EMP-001's start date via get_employee_info.",
    },
    {
        "timestamp": (datetime.now(timezone.utc) - timedelta(days=4)).isoformat(),
        "thread_id": "thread-011",
        "user_input": "Send a reminder to EMP-002 about ALL overdue tasks at once.",
        "agent_response": (
            "Reminder sent to EMP-002 about the overdue 'Complete background check' task."
        ),
        "feedback_score": -1,
        "optional_comment": "Only sent one reminder when there were multiple overdue tasks. The agent should have called get_task_status first to identify all overdue items, then send_reminder_email for each.",
    },
    {
        "timestamp": (datetime.now(timezone.utc) - timedelta(days=3)).isoformat(),
        "thread_id": "thread-012",
        "user_input": "Is EMP-007 compliant with finance department requirements?",
        "agent_response": (
            "Employee EMP-007 is compliant with all onboarding requirements."
        ),
        "feedback_score": -1,
        "optional_comment": "Hallucination — EMP-007 (Carlos Mendez) has overdue compliance tasks. The agent gave an incorrect COMPLIANT verdict without actually calling check_compliance_status.",
    },
    {
        "timestamp": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
        "thread_id": "thread-013",
        "user_input": "Summarize all onboarding progress across all departments.",
        "agent_response": (
            "I can provide individual employee reports but do not have a tool to summarize "
            "all departments at once. Please query each employee individually."
        ),
        "feedback_score": -1,
        "optional_comment": "Tool error — should have iterated over employees or used generate_onboarding_report for multiple employees. Wrong tone — the response felt unhelpful.",
    },
    {
        "timestamp": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        "thread_id": "thread-014",
        "user_input": "What is the HIPAA training requirement for the HR department?",
        "agent_response": (
            "HIPAA training is required for all HR employees who handle protected health information (PHI). "
            "Training must be completed within 60 days of hire and renewed annually."
        ),
        "feedback_score": 1,
        "optional_comment": None,
    },
    {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "thread_id": "thread-015",
        "user_input": "Generate a compliance report for EMP-006 and escalate any critical issues.",
        "agent_response": (
            "Compliance report for EMP-006 (Maya Thompson, HR Business Partner):\n"
            "Total compliance tasks: 7. Complete: 5. Overdue: 2.\n"
            "Critical overdue: 'Complete employment law compliance training' — 3 days overdue.\n"
            "Escalation created with HIGH urgency and manager Rachel Green notified."
        ),
        "feedback_score": 1,
        "optional_comment": "Perfect multi-step workflow.",
    },
]


def seed_feedback() -> None:
    conn = sqlite3.connect(FEEDBACK_DB)
    conn.execute(SCHEMA)

    # Check existing count
    existing = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
    if existing >= 10:
        print(f"feedback_log.db already has {existing} entries — skipping seed.")
        conn.close()
        return

    for entry in SAMPLE_INTERACTIONS:
        conn.execute(
            """
            INSERT INTO feedback
                (timestamp, thread_id, user_input, agent_response, feedback_score, optional_comment)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                entry["timestamp"],
                entry["thread_id"],
                entry["user_input"],
                entry["agent_response"],
                entry["feedback_score"],
                entry["optional_comment"] or "",
            ),
        )

    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
    positive = conn.execute("SELECT COUNT(*) FROM feedback WHERE feedback_score = 1").fetchone()[0]
    negative = conn.execute("SELECT COUNT(*) FROM feedback WHERE feedback_score = -1").fetchone()[0]
    conn.close()

    print(f"Seeded feedback_log.db (feedback table):")
    print(f"  Total interactions : {total}")
    print(f"  Thumbs up  (+1)    : {positive}")
    print(f"  Thumbs down (-1)   : {negative}")
    print(f"  Saved to           : {FEEDBACK_DB}")


if __name__ == "__main__":
    seed_feedback()
