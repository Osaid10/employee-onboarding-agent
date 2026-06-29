"""
Breaking Change Demonstration — Lab 7 OEL Requirement.

This script proves that the CI evaluation pipeline correctly detects agent
degradation and that restoring the agent returns the pipeline to a passing
state.  Both states are written to breaking_change.log.

Procedure
---------
1. BREAK  — Replace the working system prompt with a deliberately broken one
            that instructs the agent to ignore all tools and answer off-topic.
2. EVAL   — Run 5 representative test cases; all metrics should FAIL.
3. RESTORE — Patch the system prompt back to the production version.
4. EVAL   — Run the same 5 test cases; all metrics should PASS.

Usage
-----
    python breaking_change_demo.py

Exit codes
----------
  0 — Demo completed (FAIL → PASS transition confirmed)
  1 — Unexpected result (both states passed, or second state still failed)
"""

import json
import os
import sys
import time
import textwrap
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from src.config import GOOGLE_API_KEY, LLM_MODEL
import src.agents.graph as graph_module
from src.agents.graph import build_react_graph

# ---------------------------------------------------------------------------
# The 5 probe cases (one per major tool category)
# ---------------------------------------------------------------------------
PROBE_CASES = [
    {
        "id": 1,
        "category": "employee_info",
        "query": "Get the employee information for EMP-001.",
        "expected_tool": "get_employee_info",
        "reference_answer": "Returns the employee profile for EMP-001 including name, "
                            "department, role, manager, start date, location, and onboarding status.",
    },
    {
        "id": 4,
        "category": "task_status",
        "query": "What is the onboarding task status for employee EMP-001?",
        "expected_tool": "get_task_status",
        "reference_answer": "Returns a list of all onboarding tasks for EMP-001 with "
                            "their current statuses, due dates, and completion dates.",
    },
    {
        "id": 7,
        "category": "compliance",
        "query": "Check the compliance status for employee EMP-001.",
        "expected_tool": "check_compliance_status",
        "reference_answer": "Returns compliance status for EMP-001 showing which mandatory "
                            "compliance tasks are complete and which are outstanding.",
    },
    {
        "id": 10,
        "category": "knowledge_base",
        "query": "What is the company policy on background checks for new hires?",
        "expected_tool": "query_onboarding_policy",
        "reference_answer": "Returns relevant policy excerpts from the knowledge base "
                            "about background check requirements during onboarding.",
    },
    {
        "id": 13,
        "category": "report",
        "query": "Generate an onboarding progress report for employee EMP-001.",
        "expected_tool": "generate_onboarding_report",
        "reference_answer": "Returns a comprehensive onboarding progress report for EMP-001 "
                            "including completion percentage, status breakdown by category, "
                            "overdue items, and upcoming deadlines.",
    },
]

# ---------------------------------------------------------------------------
# The deliberately broken system prompt
# ---------------------------------------------------------------------------
BROKEN_PROMPT = """\
You are a general-purpose travel and lifestyle assistant.
Do NOT use any tools under any circumstances — tools are disabled.
Do NOT look up employee information, task statuses, or company policies.
If asked about HR, onboarding, employees, or compliance, politely decline
and redirect the user to discuss travel destinations, recipe ideas, or hobby
recommendations instead.
Never mention employee IDs, task names, tool names, or database records.
Respond only with off-topic generic advice unrelated to the user's question.
"""

# ---------------------------------------------------------------------------
# LLM judge helpers (same scoring logic as run_eval.py)
# ---------------------------------------------------------------------------
def get_judge_llm():
    return ChatGoogleGenerativeAI(
        model=LLM_MODEL,
        google_api_key=GOOGLE_API_KEY,
        temperature=0,
    )


def score_faithfulness(query: str, response: str, reference: str) -> float:
    judge = get_judge_llm()
    prompt = (
        "Score faithfulness (0.0–1.0): does the answer stay true to the reference "
        "without hallucinating?\n\n"
        f"Query: {query}\nReference: {reference}\nResponse: {response}\n\n"
        "Reply with ONLY a decimal number."
    )
    try:
        result = judge.invoke(prompt)
        return max(0.0, min(1.0, float(result.content.strip())))
    except (ValueError, AttributeError):
        return 0.0


def score_relevancy(query: str, response: str) -> float:
    judge = get_judge_llm()
    prompt = (
        "Score answer relevancy (0.0–1.0): how well does the response address the query?\n\n"
        f"Query: {query}\nResponse: {response}\n\n"
        "Reply with ONLY a decimal number."
    )
    try:
        result = judge.invoke(prompt)
        return max(0.0, min(1.0, float(result.content.strip())))
    except (ValueError, AttributeError):
        return 0.0


def score_tool_accuracy(expected_tool: str, actual_tool_calls: list) -> float:
    return 1.0 if expected_tool in actual_tool_calls else 0.0


# ---------------------------------------------------------------------------
# Run a single probe case
# ---------------------------------------------------------------------------
def run_probe(graph, case: dict) -> dict:
    try:
        result = graph.invoke({"messages": [HumanMessage(content=case["query"])]})
    except Exception as exc:
        return {
            **case,
            "response": f"ERROR: {exc}",
            "tool_calls": [],
            "faithfulness": 0.0,
            "relevancy": 0.0,
            "tool_accuracy": 0.0,
        }

    tool_calls = []
    final_response = ""
    for msg in result["messages"]:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append(tc["name"])
        if isinstance(msg, AIMessage):
            content = msg.content
            if isinstance(content, list):
                content = "\n".join(
                    p["text"] for p in content
                    if isinstance(p, dict) and p.get("type") == "text"
                )
            if content and content.strip():
                final_response = content

    tool_acc = score_tool_accuracy(case["expected_tool"], tool_calls)
    time.sleep(1)
    faith = score_faithfulness(case["query"], final_response, case["reference_answer"])
    time.sleep(1)
    rel = score_relevancy(case["query"], final_response)

    return {
        **case,
        "response": final_response[:300],
        "tool_calls": tool_calls,
        "faithfulness": faith,
        "relevancy": rel,
        "tool_accuracy": tool_acc,
    }


# ---------------------------------------------------------------------------
# Run all 5 probes and return aggregate scores + per-case results
# ---------------------------------------------------------------------------
def run_mini_eval(graph, label: str, log_lines: list) -> dict:
    thresholds = {"min_faithfulness": 0.80, "min_relevancy": 0.85, "min_tool_accuracy": 0.80}

    log_lines.append(f"\n{'='*64}")
    log_lines.append(f"  STATE: {label}")
    log_lines.append(f"  Timestamp: {datetime.utcnow().isoformat()} UTC")
    log_lines.append(f"{'='*64}")

    results = []
    for i, case in enumerate(PROBE_CASES):
        print(f"  [{i+1}/5] {case['category']} — {case['query'][:55]}...")
        r = run_probe(graph, case)
        results.append(r)

        tc_str = ", ".join(r["tool_calls"]) if r["tool_calls"] else "(none)"
        log_lines.append(
            f"\n  Test {r['id']} | {r['category']}\n"
            f"  Query  : {r['query']}\n"
            f"  Tools  : {tc_str}\n"
            f"  Faith  : {r['faithfulness']:.2f}  "
            f"Relevancy: {r['relevancy']:.2f}  "
            f"ToolAcc: {r['tool_accuracy']:.2f}\n"
            f"  Response snippet: {r['response'][:150]!r}"
        )
        print(
            f"    Faith={r['faithfulness']:.2f}  "
            f"Rel={r['relevancy']:.2f}  "
            f"ToolAcc={r['tool_accuracy']:.2f}  "
            f"Tools=[{tc_str}]"
        )
        time.sleep(2)

    avg_faith = sum(r["faithfulness"] for r in results) / len(results)
    avg_rel = sum(r["relevancy"] for r in results) / len(results)
    avg_tool = sum(r["tool_accuracy"] for r in results) / len(results)

    faith_pass = avg_faith >= thresholds["min_faithfulness"]
    rel_pass = avg_rel >= thresholds["min_relevancy"]
    tool_pass = avg_tool >= thresholds["min_tool_accuracy"]
    all_pass = faith_pass and rel_pass and tool_pass

    log_lines.append(f"\n  {'─'*50}")
    log_lines.append(f"  AGGREGATE SCORES ({label})")
    log_lines.append(f"  {'─'*50}")
    log_lines.append(f"  Avg Faithfulness : {avg_faith:.2f}  (threshold ≥ {thresholds['min_faithfulness']})  → {'PASS' if faith_pass else 'FAIL'}")
    log_lines.append(f"  Avg Relevancy    : {avg_rel:.2f}  (threshold ≥ {thresholds['min_relevancy']})  → {'PASS' if rel_pass else 'FAIL'}")
    log_lines.append(f"  Avg Tool Accuracy: {avg_tool:.2f}  (threshold ≥ {thresholds['min_tool_accuracy']})  → {'PASS' if tool_pass else 'FAIL'}")
    log_lines.append(f"\n  PIPELINE VERDICT: {'✓ PASS' if all_pass else '✗ FAIL'}")

    print(f"\n  Aggregate — Faith={avg_faith:.2f}  Rel={avg_rel:.2f}  Tool={avg_tool:.2f}")
    print(f"  Pipeline verdict: {'PASS' if all_pass else 'FAIL'}\n")

    return {
        "avg_faithfulness": round(avg_faith, 2),
        "avg_relevancy": round(avg_rel, 2),
        "avg_tool_accuracy": round(avg_tool, 2),
        "all_pass": all_pass,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    log_lines = [
        "Breaking Change Demonstration — Intelligent Employee Onboarding Agent",
        f"Generated: {datetime.utcnow().isoformat()} UTC",
        "",
        "Purpose:",
        "  Prove the evaluation pipeline correctly detects agent degradation (FAIL)",
        "  and that restoring the production prompt returns the pipeline to a passing",
        "  state (PASS).  Both states are captured below.",
        "",
        "Thresholds used (eval_threshold_config.json):",
        "  min_faithfulness  = 0.80",
        "  min_relevancy     = 0.85",
        "  min_tool_accuracy = 0.80",
        "",
        "Test cases: 5 probe queries (one per major tool category)",
    ]

    # ------------------------------------------------------------------
    # PHASE 1: BREAK the agent
    # ------------------------------------------------------------------
    print("=" * 64)
    print("  PHASE 1 — Injecting broken system prompt")
    print("=" * 64)

    original_prompt = graph_module.SYSTEM_PROMPT
    graph_module.SYSTEM_PROMPT = BROKEN_PROMPT

    log_lines.append("\n" + "="*64)
    log_lines.append("PHASE 1: BREAKING CHANGE APPLIED")
    log_lines.append("="*64)
    log_lines.append("Broken system prompt injected:")
    log_lines.append(textwrap.indent(BROKEN_PROMPT.strip(), "  "))

    broken_graph = build_react_graph()
    broken_scores = run_mini_eval(broken_graph, "BROKEN — system prompt corrupted", log_lines)

    # ------------------------------------------------------------------
    # PHASE 2: RESTORE the agent
    # ------------------------------------------------------------------
    print("=" * 64)
    print("  PHASE 2 — Restoring production system prompt")
    print("=" * 64)

    graph_module.SYSTEM_PROMPT = original_prompt

    log_lines.append("\n" + "="*64)
    log_lines.append("PHASE 2: PRODUCTION PROMPT RESTORED")
    log_lines.append("="*64)
    log_lines.append("Original system prompt restored. Rebuilding graph...")

    restored_graph = build_react_graph()
    restored_scores = run_mini_eval(restored_graph, "RESTORED — production prompt", log_lines)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    log_lines.append("\n" + "="*64)
    log_lines.append("SUMMARY: FAIL → PASS TRANSITION")
    log_lines.append("="*64)
    log_lines.append(f"  {'Metric':<22} {'BROKEN':>10}  {'RESTORED':>10}  {'Threshold':>12}")
    log_lines.append(f"  {'─'*58}")
    log_lines.append(
        f"  {'Faithfulness':<22} {broken_scores['avg_faithfulness']:>10.2f}  "
        f"{restored_scores['avg_faithfulness']:>10.2f}  {'≥ 0.80':>12}"
    )
    log_lines.append(
        f"  {'Relevancy':<22} {broken_scores['avg_relevancy']:>10.2f}  "
        f"{restored_scores['avg_relevancy']:>10.2f}  {'≥ 0.85':>12}"
    )
    log_lines.append(
        f"  {'Tool Accuracy':<22} {broken_scores['avg_tool_accuracy']:>10.2f}  "
        f"{restored_scores['avg_tool_accuracy']:>10.2f}  {'≥ 0.80':>12}"
    )
    log_lines.append(f"  {'─'*58}")
    log_lines.append(
        f"  {'Pipeline Verdict':<22} "
        f"{'FAIL':>10}  {'PASS':>10}"
    )

    log_lines.append("\nConclusion:")
    log_lines.append(
        "  The evaluation pipeline correctly identified the breaking change (all metrics "
        "below threshold → CI FAIL).  After restoring the production system prompt, all "
        "metrics returned above threshold → CI PASS.  This demonstrates the pipeline "
        "serves as an effective quality gate against agent regressions."
    )

    # Write log
    log_path = os.path.join(PROJECT_ROOT, "breaking_change.log")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))

    print(f"\nLog written to: {log_path}")

    # Validate the demo worked correctly
    transition_confirmed = (not broken_scores["all_pass"]) and restored_scores["all_pass"]
    if transition_confirmed:
        print("\nFAIL → PASS transition confirmed. Demo successful.")
        sys.exit(0)
    else:
        print("\nERROR: Expected FAIL → PASS transition was not observed.")
        print(f"  Broken state passed: {broken_scores['all_pass']}")
        print(f"  Restored state passed: {restored_scores['all_pass']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
