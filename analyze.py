"""
analyze.py — Feedback Analysis Script (Part A, AI407L Final Exam)

Reads feedback_log.db and prints:
  1. Total number of responses logged
  2. Total negative feedback count
  3. Top 3 failed queries (queries that received thumbs-down)

Usage:
    python analyze.py
"""

import os
import sqlite3
from pathlib import Path

FEEDBACK_DB = Path(__file__).resolve().parent / "feedback_log.db"


def load_feedback_db() -> sqlite3.Connection:
    if not FEEDBACK_DB.exists():
        print("ERROR: feedback_log.db not found.")
        print("Run 'python seed_feedback.py' first to populate the database.")
        raise SystemExit(1)
    return sqlite3.connect(FEEDBACK_DB)


def count_total_responses(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]


def count_negative_feedback(conn: sqlite3.Connection) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM feedback WHERE feedback_score = -1"
    ).fetchone()[0]


def get_top3_failed_queries(conn: sqlite3.Connection) -> list[tuple]:
    """Return the 3 most recent queries that received negative feedback."""
    rows = conn.execute(
        """
        SELECT user_input, agent_response, optional_comment, timestamp
        FROM   feedback
        WHERE  feedback_score = -1
        ORDER  BY timestamp DESC
        LIMIT  3
        """
    ).fetchall()
    return rows


def main():
    print("=" * 60)
    print("  AI407L Final Exam - Part A: Feedback Analysis")
    print("=" * 60)

    conn = load_feedback_db()

    total = count_total_responses(conn)
    negative = count_negative_feedback(conn)
    positive = conn.execute(
        "SELECT COUNT(*) FROM feedback WHERE feedback_score = 1"
    ).fetchone()[0]
    neutral = conn.execute(
        "SELECT COUNT(*) FROM feedback WHERE feedback_score = 0"
    ).fetchone()[0]
    satisfaction = round(positive / total * 100, 1) if total else 0.0

    print(f"\n--- Summary ---")
    print(f"  Total responses logged : {total}")
    print(f"  Positive (+1)          : {positive}")
    print(f"  Negative (-1)          : {negative}")
    print(f"  Neutral  ( 0)          : {neutral}")
    print(f"  Satisfaction rate      : {satisfaction}%")

    print(f"\n--- Top 3 Failed Queries ---")
    failed = get_top3_failed_queries(conn)

    if not failed:
        print("  No negative feedback found — the agent is performing well!")
    else:
        for rank, (user_input, agent_response, comment, timestamp) in enumerate(failed, 1):
            print(f"\n  #{rank}  [{timestamp[:10]}]")
            print(f"  Query   : {user_input}")
            print(f"  Response: {agent_response[:120]}{'...' if len(agent_response) > 120 else ''}")
            if comment:
                print(f"  Comment : {comment}")

    conn.close()
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
