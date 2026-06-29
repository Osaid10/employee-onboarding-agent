"""
Lab 5 — Human-in-the-Loop (HITL) Approval Logic.

Demonstrates interrupt_before on the action_tools node so that a human
can review, approve, edit, or cancel high-risk tool calls before they
are executed.

Run:
    python -m src.persistence.approval_logic
"""

import json
import os

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.sqlite import SqliteSaver

from src.config import CHECKPOINT_DB
from src.agents.multi_agent_graph import build_multi_agent_graph, MultiAgentState


THREAD_ID = "hitl-demo-001"


def print_separator(label: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}\n")


def get_last_ai_message(result: dict) -> AIMessage | None:
    """Return the last AIMessage from the graph result."""
    for msg in reversed(result["messages"]):
        if isinstance(msg, AIMessage):
            return msg
    return None


def display_pending_tool_calls(ai_message: AIMessage) -> None:
    """Pretty-print the pending tool calls for human review."""
    print("PENDING TOOL CALL(S) — requires your approval:\n")
    for i, tc in enumerate(ai_message.tool_calls, 1):
        print(f"  [{i}] Tool: {tc['name']}")
        print(f"      Arguments:")
        for key, value in tc["args"].items():
            # Truncate long values for display
            display_val = str(value)
            if len(display_val) > 120:
                display_val = display_val[:120] + "..."
            print(f"        {key}: {display_val}")
        print()


def get_human_decision() -> str:
    """Prompt the human for a decision: proceed, cancel, or edit."""
    while True:
        print("What would you like to do?")
        print('  Type "proceed" to approve and execute the tool call')
        print('  Type "cancel"  to reject the tool call')
        print('  Type "edit"    to modify the tool call arguments')
        decision = input("\nYour decision: ").strip().lower()
        if decision in ("proceed", "cancel", "edit"):
            return decision
        print(f"Invalid input '{decision}'. Please type proceed, cancel, or edit.\n")


def edit_tool_call_args(ai_message: AIMessage) -> AIMessage:
    """Allow the human to edit tool call arguments interactively.

    Returns a new AIMessage with the modified tool calls.
    """
    modified_tool_calls = []

    for tc in ai_message.tool_calls:
        print(f"\nEditing tool call: {tc['name']}")
        print("Current arguments:")

        new_args = dict(tc["args"])

        for key, value in new_args.items():
            print(f"\n  {key} (current value):")
            print(f"  {value}")
            new_value = input(
                f"  Enter new value for '{key}' (press Enter to keep current): "
            ).strip()
            if new_value:
                new_args[key] = new_value

        modified_tool_calls.append(
            {
                "name": tc["name"],
                "args": new_args,
                "id": tc["id"],
                "type": "tool_call",
            }
        )

        print(f"\nUpdated arguments for {tc['name']}:")
        for key, value in new_args.items():
            print(f"  {key}: {value}")

    # Create a new AIMessage with modified tool calls
    return AIMessage(
        content=ai_message.content,
        tool_calls=modified_tool_calls,
    )


def cancel_tool_calls(graph, config, ai_message: AIMessage) -> dict:
    """Cancel pending tool calls by injecting ToolMessages with cancellation
    notices, then resume execution so the agent can respond gracefully."""
    cancel_messages = []
    for tc in ai_message.tool_calls:
        cancel_messages.append(
            ToolMessage(
                content=f"[CANCELLED BY HUMAN] The tool call '{tc['name']}' "
                f"was rejected by the human reviewer.",
                tool_call_id=tc["id"],
            )
        )

    # Update state with cancellation messages and resume
    result = graph.invoke(
        {"messages": cancel_messages},
        config=config,
    )
    return result


def main() -> None:
    print_separator("LAB 5 — HUMAN-IN-THE-LOOP APPROVAL DEMO")

    # Clean up previous checkpoint for a fresh demo
    hitl_db = CHECKPOINT_DB.replace(".sqlite", "_hitl.sqlite")
    if os.path.exists(hitl_db):
        os.remove(hitl_db)

    with SqliteSaver.from_conn_string(hitl_db) as checkpointer:
        # Build multi-agent graph with interrupt_before on action_tools
        graph = build_multi_agent_graph(
            checkpointer=checkpointer,
            interrupt_before=["action_tools"],
        )

        config = {"configurable": {"thread_id": THREAD_ID}}

        # --- Initial request ---
        print_separator("STEP 1: Sending request to multi-agent system")

        user_request = (
            "Check the onboarding status of employee EMP-003. "
            "If there are any overdue tasks, send them a reminder email "
            "about the most critical overdue task."
        )
        print(f"User: {user_request}\n")

        # First invocation — HR Coordinator gathers info, hands over,
        # then Action Executor proposes tool calls which get interrupted
        result = graph.invoke(
            {
                "messages": [HumanMessage(content=user_request)],
                "current_agent": "hr_coordinator",
                "handover_summary": "",
                "task_complete": False,
            },
            config=config,
        )

        # --- Check if we hit the interrupt ---
        snapshot = graph.get_state(config)

        if snapshot.next and "action_tools" in snapshot.next:
            print_separator("STEP 2: Execution paused — action_tools interrupted")

            # Get the last AI message with tool calls
            ai_msg = get_last_ai_message(result)
            if ai_msg and ai_msg.tool_calls:
                display_pending_tool_calls(ai_msg)

                # --- Human decision ---
                print_separator("STEP 3: Human review")
                decision = get_human_decision()

                if decision == "proceed":
                    print_separator("STEP 4: Approved — resuming execution")
                    # Resume by invoking with None (continues from checkpoint)
                    result = graph.invoke(None, config=config)

                    ai_response = get_last_ai_message(result)
                    if ai_response:
                        print(f"\nAgent: {ai_response.content}")

                elif decision == "edit":
                    print_separator("STEP 4: Editing tool call arguments")

                    # Let human edit the arguments
                    modified_msg = edit_tool_call_args(ai_msg)

                    print_separator("STEP 5: Executing with edited arguments")

                    # Update the state with the modified AI message
                    # We need to replace the last message in state
                    graph.update_state(
                        config,
                        {"messages": [modified_msg]},
                    )

                    # Now resume execution
                    result = graph.invoke(None, config=config)

                    ai_response = get_last_ai_message(result)
                    if ai_response:
                        print(f"\nAgent: {ai_response.content}")

                elif decision == "cancel":
                    print_separator("STEP 4: Cancelled — rejecting tool call")
                    result = cancel_tool_calls(graph, config, ai_msg)

                    ai_response = get_last_ai_message(result)
                    if ai_response:
                        print(f"\nAgent: {ai_response.content}")

            else:
                print("No pending tool calls found at interrupt point.")
        else:
            # No interrupt hit — the agent completed without needing action tools
            print_separator("COMPLETED (no action tools were invoked)")
            ai_response = get_last_ai_message(result)
            if ai_response:
                print(f"Agent: {ai_response.content}")

    print_separator("DEMO COMPLETE")
    print("This demo showed the human-in-the-loop pattern:")
    print("  1. The HR Coordinator gathered information (read-only)")
    print("  2. It handed over to the Action Executor")
    print("  3. The Action Executor proposed a high-risk tool call")
    print("  4. Execution paused for human review (interrupt_before)")
    print("  5. The human could proceed, edit, or cancel the action")


if __name__ == "__main__":
    main()
