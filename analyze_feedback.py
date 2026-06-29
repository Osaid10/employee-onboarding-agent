"""
Lab 11 — Drift & Failure Analysis Script.

Acts as a "Drift Monitor" by analyzing the feedback_log.db database.
Filters negative feedback, categorizes errors using an LLM judge, and
generates a drift_report.md with findings and recommendations.

Usage:
    python analyze_feedback.py
"""

import json
import os
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

FEEDBACK_DB = os.path.join(PROJECT_ROOT, "feedback_log.db")
DRIFT_REPORT_PATH = os.path.join(PROJECT_ROOT, "docs", "drift_report.md")


def get_negative_feedback() -> list[dict]:
    """Retrieve all negative feedback entries."""
    conn = sqlite3.connect(FEEDBACK_DB)
    rows = conn.execute(
        "SELECT id, timestamp, user_input, agent_response, optional_comment "
        "FROM feedback WHERE feedback_score = -1 ORDER BY timestamp DESC"
    ).fetchall()
    conn.close()

    return [
        {
            "id": r[0],
            "timestamp": r[1],
            "user_input": r[2],
            "agent_response": r[3],
            "comment": r[4] or "",
        }
        for r in rows
    ]


def get_all_feedback_stats() -> dict:
    """Get aggregate feedback statistics."""
    conn = sqlite3.connect(FEEDBACK_DB)
    total = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
    positive = conn.execute("SELECT COUNT(*) FROM feedback WHERE feedback_score = 1").fetchone()[0]
    negative = conn.execute("SELECT COUNT(*) FROM feedback WHERE feedback_score = -1").fetchone()[0]
    neutral = conn.execute("SELECT COUNT(*) FROM feedback WHERE feedback_score = 0").fetchone()[0]
    conn.close()

    return {
        "total": total,
        "positive": positive,
        "negative": negative,
        "neutral": neutral,
        "satisfaction_rate": round(positive / total * 100, 1) if total else 0,
    }


def categorize_with_llm(feedback_entries: list[dict]) -> list[dict]:
    """Use LLM judge to categorize each negative feedback entry.

    Categories: Hallucination, Tool Error, Wrong Tone, Incomplete Answer,
    Off-Topic Response, Other.
    """
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from src.config import GOOGLE_API_KEY, LLM_MODEL

        llm = ChatGoogleGenerativeAI(
            model=LLM_MODEL,
            google_api_key=GOOGLE_API_KEY,
            temperature=0,
        )

        categorized = []
        for entry in feedback_entries:
            prompt = f"""Categorize the following failed agent interaction.

Categories:
- Hallucination: Agent made up facts not in the retrieved context
- Tool Error: Agent called the wrong tool or passed wrong arguments
- Wrong Tone: Agent's tone was inappropriate
- Incomplete Answer: Agent did not fully address the query
- Off-Topic Response: Agent responded about something unrelated
- Other: Does not fit above categories

User Input: {entry['user_input']}
Agent Response: {entry['agent_response'][:500]}
User Comment: {entry['comment']}

Respond with ONLY the category name (one of the above)."""

            result = llm.invoke(prompt)
            category = result.content.strip()

            # Normalize
            valid = ["Hallucination", "Tool Error", "Wrong Tone", "Incomplete Answer", "Off-Topic Response", "Other"]
            if category not in valid:
                category = "Other"

            entry["category"] = category
            categorized.append(entry)

        return categorized

    except Exception as e:
        print(f"LLM categorization failed: {e}. Falling back to keyword analysis.")
        return categorize_with_keywords(feedback_entries)


def categorize_with_keywords(feedback_entries: list[dict]) -> list[dict]:
    """Fallback keyword-based categorization."""
    for entry in feedback_entries:
        comment = (entry["comment"] or "").lower()
        response = (entry["agent_response"] or "").lower()

        if any(w in comment for w in ["hallucin", "made up", "incorrect", "wrong fact"]):
            entry["category"] = "Hallucination"
        elif any(w in comment for w in ["tool", "error", "failed", "crash"]):
            entry["category"] = "Tool Error"
        elif any(w in comment for w in ["tone", "rude", "unprofessional"]):
            entry["category"] = "Wrong Tone"
        elif any(w in comment for w in ["incomplete", "missing", "partial", "didn't answer"]):
            entry["category"] = "Incomplete Answer"
        elif any(w in comment for w in ["off-topic", "unrelated", "wrong topic"]):
            entry["category"] = "Off-Topic Response"
        else:
            entry["category"] = "Other"

    return feedback_entries


def generate_drift_report(stats: dict, categorized: list[dict]) -> str:
    """Generate the drift_report.md content."""
    lines = [
        "# Drift Report — Lab 11",
        "## Feedback Analysis & Failure Categorization",
        "",
        "---",
        "",
        "## 1. Aggregate Statistics",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total Interactions Logged | {stats['total']} |",
        f"| Positive Feedback (👍) | {stats['positive']} |",
        f"| Negative Feedback (👎) | {stats['negative']} |",
        f"| Neutral Feedback (😐) | {stats['neutral']} |",
        f"| Satisfaction Rate | {stats['satisfaction_rate']}% |",
        "",
        "---",
        "",
        "## 2. Failure Category Breakdown",
        "",
    ]

    if categorized:
        # Count by category
        cat_counts = {}
        for entry in categorized:
            cat = entry["category"]
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        lines.append("| Category | Count | Percentage |")
        lines.append("|----------|-------|------------|")
        for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
            pct = round(count / len(categorized) * 100, 1)
            lines.append(f"| {cat} | {count} | {pct}% |")

        lines.extend([
            "",
            "---",
            "",
            "## 3. Sample Failed Interactions",
            "",
        ])

        for entry in categorized[:5]:
            lines.extend([
                f"### Feedback #{entry['id']} — {entry['category']}",
                f"- **User Input:** {entry['user_input'][:200]}",
                f"- **Agent Response:** {entry['agent_response'][:200]}...",
                f"- **User Comment:** {entry['comment'] or 'N/A'}",
                "",
            ])
    else:
        lines.append("No negative feedback entries found. The agent is performing well!")

    lines.extend([
        "---",
        "",
        "## 4. Recommendations",
        "",
        "Based on the failure analysis:",
        "",
        "1. **Hallucination**: Add stronger grounding instructions to the system prompt "
        "emphasizing that the agent should only use information from tool results.",
        "2. **Tool Error**: Review tool docstrings and add more explicit usage examples "
        "to help the LLM select the correct tool.",
        "3. **Incomplete Answer**: Add instructions to the system prompt requiring the agent "
        "to explicitly address every part of multi-part questions.",
        "4. **Wrong Tone**: Add tone guidelines (professional, empathetic) to the system prompt.",
        "",
        "See `improved_prompt.txt` for the revised system prompt incorporating these fixes.",
    ])

    return "\n".join(lines)


def main():
    print("=" * 60)
    print("  Lab 11 — Drift & Failure Analysis")
    print("=" * 60)

    if not os.path.exists(FEEDBACK_DB):
        print("\nNo feedback database found. Run the Streamlit app first to collect feedback.")
        sys.exit(0)

    stats = get_all_feedback_stats()
    print(f"\nTotal feedback: {stats['total']}")
    print(f"  Positive: {stats['positive']}")
    print(f"  Negative: {stats['negative']}")
    print(f"  Neutral:  {stats['neutral']}")
    print(f"  Satisfaction: {stats['satisfaction_rate']}%")

    negative = get_negative_feedback()

    if negative:
        print(f"\nCategorizing {len(negative)} negative entries...")
        categorized = categorize_with_llm(negative)
    else:
        print("\nNo negative feedback found.")
        categorized = []

    report = generate_drift_report(stats, categorized)

    with open(DRIFT_REPORT_PATH, "w") as f:
        f.write(report)

    print(f"\nDrift report saved to: {DRIFT_REPORT_PATH}")


if __name__ == "__main__":
    main()
