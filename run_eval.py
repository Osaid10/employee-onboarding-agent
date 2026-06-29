"""
Lab 7 — Evaluation Pipeline (CI-ready).

Runs the onboarding agent through a test dataset and scores it using
LLM-as-a-Judge (RAGAS-style) on three metrics:
  - Faithfulness:      Does the answer stay true to retrieved context?
  - Answer Relevancy:  How well does the response address the query?
  - Tool Call Accuracy: Did the agent invoke the correct tool(s)?

Exit codes:
  0 — All scores meet thresholds (CI pass)
  1 — One or more scores below threshold (CI fail)

Usage:
    python run_eval.py
"""

import json
import os
import sys
import time
from pathlib import Path

# Ensure project root is on path
PROJECT_ROOT = str(Path(__file__).resolve().parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from langchain_core.messages import HumanMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from src.config import GOOGLE_API_KEY, LLM_MODEL
from src.agents.graph import build_react_graph


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
TEST_DATASET_PATH = os.path.join(PROJECT_ROOT, "test_dataset.json")
THRESHOLD_CONFIG_PATH = os.path.join(PROJECT_ROOT, "eval_threshold_config.json")


def load_test_dataset() -> list[dict]:
    with open(TEST_DATASET_PATH, "r") as f:
        return json.load(f)


def load_thresholds() -> dict:
    with open(THRESHOLD_CONFIG_PATH, "r") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# LLM Judge scoring
# ---------------------------------------------------------------------------
def get_judge_llm():
    return ChatGoogleGenerativeAI(
        model=LLM_MODEL,
        google_api_key=GOOGLE_API_KEY,
        temperature=0,
    )


def score_faithfulness(query: str, response: str, reference: str) -> float:
    """Score how faithful the response is to the reference context."""
    judge = get_judge_llm()
    prompt = f"""Score the faithfulness of the following response on a scale of 0.0 to 1.0.
Faithfulness means: does the answer stay true to the reference context without hallucinating?

Query: {query}
Reference Context: {reference}
Agent Response: {response}

Respond with ONLY a decimal number between 0.0 and 1.0 (e.g., 0.85).
"""
    result = judge.invoke(prompt)
    try:
        score = float(result.content.strip())
        return max(0.0, min(1.0, score))
    except ValueError:
        return 0.5


def score_relevancy(query: str, response: str) -> float:
    """Score how well the response addresses the user's query."""
    judge = get_judge_llm()
    prompt = f"""Score the answer relevancy of the following response on a scale of 0.0 to 1.0.
Answer relevancy means: how well does the response address the user's original query?

Query: {query}
Agent Response: {response}

Respond with ONLY a decimal number between 0.0 and 1.0 (e.g., 0.90).
"""
    result = judge.invoke(prompt)
    try:
        score = float(result.content.strip())
        return max(0.0, min(1.0, score))
    except ValueError:
        return 0.5


def score_tool_accuracy(expected_tool: str, actual_tool_calls: list[str]) -> float:
    """Binary score: 1.0 if the expected tool was called, 0.0 otherwise."""
    return 1.0 if expected_tool in actual_tool_calls else 0.0


# ---------------------------------------------------------------------------
# Run a single test case
# ---------------------------------------------------------------------------
def run_test_case(graph, test_case: dict) -> dict:
    """Execute a single test case and return scores."""
    query = test_case["query"]
    expected_tool = test_case["expected_tool"]
    reference = test_case["reference_answer"]

    try:
        result = graph.invoke({"messages": [HumanMessage(content=query)]})
    except Exception as e:
        print(f"  ERROR running query: {e}")
        return {
            "id": test_case["id"],
            "category": test_case["category"],
            "query": query,
            "response": f"ERROR: {e}",
            "tool_calls": [],
            "faithfulness": 0.0,
            "relevancy": 0.0,
            "tool_accuracy": 0.0,
        }

    # Extract response and tool calls
    tool_calls = []
    final_response = ""
    for msg in result["messages"]:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append(tc["name"])
        if isinstance(msg, AIMessage):
            content = msg.content
            if isinstance(content, list):
                parts = [p["text"] for p in content if isinstance(p, dict) and p.get("type") == "text"]
                content = "\n".join(parts)
            if content and content.strip():
                final_response = content

    # Score
    tool_acc = score_tool_accuracy(expected_tool, tool_calls)

    # Rate limit: small delay between LLM judge calls
    time.sleep(1)
    faithfulness = score_faithfulness(query, final_response, reference)

    time.sleep(1)
    relevancy = score_relevancy(query, final_response)

    return {
        "id": test_case["id"],
        "category": test_case["category"],
        "query": query,
        "response": final_response[:300],
        "tool_calls": tool_calls,
        "faithfulness": faithfulness,
        "relevancy": relevancy,
        "tool_accuracy": tool_acc,
    }


# ---------------------------------------------------------------------------
# Main evaluation loop
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("  Lab 7 — Evaluation Pipeline")
    print("=" * 60)

    dataset = load_test_dataset()
    thresholds = load_thresholds()

    print(f"\nTest cases: {len(dataset)}")
    print(f"Thresholds: {json.dumps(thresholds, indent=2)}")
    print()

    graph = build_react_graph()

    results = []
    for i, test_case in enumerate(dataset):
        print(f"[{i+1}/{len(dataset)}] Category: {test_case['category']} — {test_case['query'][:60]}...")
        result = run_test_case(graph, test_case)
        results.append(result)
        print(f"  Faithfulness: {result['faithfulness']:.2f} | "
              f"Relevancy: {result['relevancy']:.2f} | "
              f"Tool Accuracy: {result['tool_accuracy']:.1f} | "
              f"Tools: {result['tool_calls']}")

        # Rate limit between test cases
        time.sleep(2)

    # Aggregate scores
    avg_faithfulness = sum(r["faithfulness"] for r in results) / len(results)
    avg_relevancy = sum(r["relevancy"] for r in results) / len(results)
    avg_tool_accuracy = sum(r["tool_accuracy"] for r in results) / len(results)

    print("\n" + "=" * 60)
    print("  AGGREGATE SCORES")
    print("=" * 60)
    print(f"  Average Faithfulness:      {avg_faithfulness:.2f}  (threshold: {thresholds['min_faithfulness']})")
    print(f"  Average Relevancy:         {avg_relevancy:.2f}  (threshold: {thresholds['min_relevancy']})")
    print(f"  Average Tool Call Accuracy: {avg_tool_accuracy:.2f}  (threshold: {thresholds['min_tool_accuracy']})")

    # Pass/fail
    faith_pass = avg_faithfulness >= thresholds["min_faithfulness"]
    rel_pass = avg_relevancy >= thresholds["min_relevancy"]
    tool_pass = avg_tool_accuracy >= thresholds["min_tool_accuracy"]

    print(f"\n  Faithfulness:  {'PASS' if faith_pass else 'FAIL'}")
    print(f"  Relevancy:     {'PASS' if rel_pass else 'FAIL'}")
    print(f"  Tool Accuracy: {'PASS' if tool_pass else 'FAIL'}")

    all_pass = faith_pass and rel_pass and tool_pass
    print(f"\n  Overall: {'PASS' if all_pass else 'FAIL'}")

    # Save results
    output_path = os.path.join(PROJECT_ROOT, "eval_results.json")
    with open(output_path, "w") as f:
        json.dump({
            "results": results,
            "aggregate": {
                "avg_faithfulness": round(avg_faithfulness, 2),
                "avg_relevancy": round(avg_relevancy, 2),
                "avg_tool_accuracy": round(avg_tool_accuracy, 2),
            },
            "thresholds": thresholds,
            "pass": all_pass,
        }, f, indent=2)

    print(f"\nDetailed results saved to: {output_path}")

    # Exit code for CI
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
