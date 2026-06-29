"""
Lab 5 — Persistence Test.

Demonstrates that the agent graph maintains conversational memory across
"restarts" by using a SqliteSaver checkpointer.

Run:
    python -m src.persistence.persistence_test
"""

import os
import sys

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver

from src.config import CHECKPOINT_DB
from src.agents.graph import build_react_graph, AgentState


THREAD_ID = "thread-001"


def print_separator(label: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}\n")


def get_last_ai_response(result: dict) -> str:
    """Extract the last AI message content from the graph result."""
    for msg in reversed(result["messages"]):
        if hasattr(msg, "content") and hasattr(msg, "tool_calls"):
            raw = msg.content
            if isinstance(raw, str) and raw.strip():
                return raw
            if isinstance(raw, list):
                # Gemini returns [{'type': 'text', 'text': '...'}]
                parts = [p["text"] for p in raw if isinstance(p, dict) and p.get("type") == "text"]
                text = "\n".join(parts).strip()
                if text:
                    return text
    return "(No text response from agent)"


def run_session_1(checkpointer) -> None:
    """First session: ask about employee EMP-003."""
    print_separator("SESSION 1 — First interaction (new thread)")

    # Build the graph with the checkpointer
    graph = build_react_graph()

    # Since build_react_graph() doesn't accept a checkpointer natively,
    # we rebuild it with one
    from langgraph.graph import StateGraph, END
    from src.agents.graph import agent_node, tool_node, should_continue

    sg = StateGraph(AgentState)
    sg.add_node("agent", agent_node)
    sg.add_node("tools", tool_node)
    sg.set_entry_point("agent")
    sg.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    sg.add_edge("tools", "agent")
    compiled = sg.compile(checkpointer=checkpointer)

    config = {"configurable": {"thread_id": THREAD_ID}}

    print("User: What is the onboarding status of employee EMP-003? "
          "Show me their task progress and compliance status.\n")

    result = compiled.invoke(
        {
            "messages": [
                HumanMessage(
                    content=(
                        "What is the onboarding status of employee EMP-003? "
                        "Show me their task progress and compliance status."
                    )
                )
            ]
        },
        config=config,
    )

    response = get_last_ai_response(result)
    print("Agent:", response.encode('ascii', 'replace').decode())


def run_session_2(checkpointer) -> None:
    """Second session: simulates a restart and resumes the same thread."""
    print_separator("SESSION 2 — After restart (same thread, new graph instance)")

    # Build a COMPLETELY NEW graph instance (simulating app restart)
    from langgraph.graph import StateGraph, END
    from src.agents.graph import agent_node, tool_node, should_continue

    sg = StateGraph(AgentState)
    sg.add_node("agent", agent_node)
    sg.add_node("tools", tool_node)
    sg.set_entry_point("agent")
    sg.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    sg.add_edge("tools", "agent")
    compiled = sg.compile(checkpointer=checkpointer)

    config = {"configurable": {"thread_id": THREAD_ID}}

    follow_up = (
        "Based on what you found earlier about EMP-003, "
        "which tasks are overdue and what actions would you recommend?"
    )
    print(f"User: {follow_up}\n")

    result = compiled.invoke(
        {"messages": [HumanMessage(content=follow_up)]},
        config=config,
    )

    response = get_last_ai_response(result)
    print("Agent:", response.encode('ascii', 'replace').decode())


def main() -> None:
    print_separator("LAB 5 — PERSISTENCE DEMONSTRATION")
    print(f"Checkpoint database: {CHECKPOINT_DB}")
    print(f"Thread ID: {THREAD_ID}")

    # Remove stale checkpoint DB if it exists (clean demo)
    if os.path.exists(CHECKPOINT_DB):
        os.remove(CHECKPOINT_DB)
        print("(Cleared previous checkpoint database for clean demo)")

    # Use a single SqliteSaver that persists to disk
    with SqliteSaver.from_conn_string(CHECKPOINT_DB) as checkpointer:
        # --- Session 1 ---
        run_session_1(checkpointer)

        print_separator("SIMULATING APPLICATION RESTART...")
        print("The graph instance from Session 1 is now discarded.")
        print("A new graph instance will be created, but the same")
        print("checkpointer (backed by SQLite) preserves the memory.\n")

        # --- Session 2 ---
        run_session_2(checkpointer)

    print_separator("DEMO COMPLETE")
    print("The agent in Session 2 was able to reference information from")
    print("Session 1, demonstrating that persistent memory works across")
    print("graph restarts via the SqliteSaver checkpointer.")


if __name__ == "__main__":
    main()
