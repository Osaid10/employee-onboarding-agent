"""
Lab 4 — Multi-Agent LangGraph with Handover Logic.

Two-agent architecture:
  1. HR Coordinator Agent  — gathers information using read-only tools
  2. Action Executor Agent — takes action using write/action tools

The HR Coordinator works first. When it includes "HANDOVER:" in its response,
the router hands control to the Action Executor, passing along the summary.
"""

from typing import Annotated, Union

from langchain_core.messages import AIMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

from src.config import GOOGLE_API_KEY, LLM_MODEL
from src.agents.agents_config import (
    HR_COORDINATOR_TOOLS,
    HR_COORDINATOR_PROMPT,
    ACTION_EXECUTOR_TOOLS,
    ACTION_EXECUTOR_PROMPT,
)


def _extract_text(content) -> str:
    """Extract plain text from AIMessage content (str or list of dicts)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [p["text"] for p in content if isinstance(p, dict) and p.get("type") == "text"]
        return "\n".join(parts)
    return ""


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
class MultiAgentState(TypedDict):
    """State carried through the multi-agent graph."""
    messages: Annotated[list, add_messages]
    current_agent: str
    handover_summary: str
    task_complete: bool


# ---------------------------------------------------------------------------
# LLMs (one per agent, each bound to its own tool set)
# ---------------------------------------------------------------------------
def _get_hr_llm():
    return ChatGoogleGenerativeAI(
        model=LLM_MODEL,
        google_api_key=GOOGLE_API_KEY,
        temperature=0,
    ).bind_tools(HR_COORDINATOR_TOOLS)


def _get_action_llm():
    return ChatGoogleGenerativeAI(
        model=LLM_MODEL,
        google_api_key=GOOGLE_API_KEY,
        temperature=0,
    ).bind_tools(ACTION_EXECUTOR_TOOLS)


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------
def hr_coordinator_node(state: MultiAgentState) -> dict:
    """HR Coordinator Agent — gathers information with read-only tools."""
    llm = _get_hr_llm()
    messages = list(state["messages"])

    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=HR_COORDINATOR_PROMPT)] + messages

    response = llm.invoke(messages)
    return {"messages": [response], "current_agent": "hr_coordinator"}


def action_executor_node(state: MultiAgentState) -> dict:
    """Action Executor Agent — executes actions based on handover summary."""
    llm = _get_action_llm()
    messages = list(state["messages"])

    handover = state.get("handover_summary", "")
    executor_system = ACTION_EXECUTOR_PROMPT
    if handover:
        executor_system += (
            f"\n\n## Handover from HR Coordinator\n{handover}\n\n"
            "Please execute the recommended actions above."
        )

    # Only keep HumanMessages and this agent's own prior messages (AIMessage
    # without HR-coordinator tool calls, plus corresponding ToolMessages).
    # The simplest approach: pass the original user request + any action
    # executor's own prior tool results.
    from langchain_core.messages import HumanMessage, ToolMessage as TM
    clean = []
    for m in messages:
        if isinstance(m, HumanMessage):
            clean.append(m)
        elif isinstance(m, TM) and state.get("current_agent") == "action_executor":
            clean.append(m)
        elif isinstance(m, AIMessage) and state.get("current_agent") == "action_executor":
            # Keep action executor's own prior AI messages (with its tool calls)
            if hasattr(m, "tool_calls") and m.tool_calls:
                clean.append(m)

    new_messages = [SystemMessage(content=executor_system)] + clean

    response = llm.invoke(new_messages)
    return {"messages": [response], "current_agent": "action_executor"}


# Tool nodes
hr_tool_node = ToolNode(HR_COORDINATOR_TOOLS)
action_tool_node = ToolNode(ACTION_EXECUTOR_TOOLS)


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
def route_hr_coordinator(state: MultiAgentState) -> str:
    last_message = state["messages"][-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "hr_tools"

    content = ""
    if isinstance(last_message, AIMessage):
        content = _extract_text(last_message.content)

    if "HANDOVER:" in content:
        handover_idx = content.index("HANDOVER:")
        summary = content[handover_idx + len("HANDOVER:"):].strip()
        state["handover_summary"] = summary
        return "action_executor"

    return END


def route_action_executor(state: MultiAgentState) -> str:
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "action_tools"
    return END


# ---------------------------------------------------------------------------
# Handover edge
# ---------------------------------------------------------------------------
def handover_passthrough(state: MultiAgentState) -> dict:
    handover_summary = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, AIMessage):
            content = _extract_text(msg.content)
            if "HANDOVER:" in content:
                idx = content.index("HANDOVER:")
                handover_summary = content[idx + len("HANDOVER:"):].strip()
                break

    return {"handover_summary": handover_summary, "current_agent": "action_executor"}


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------
def build_multi_agent_graph(checkpointer=None, interrupt_before=None):
    """Build and compile the multi-agent graph."""
    graph = StateGraph(MultiAgentState)

    graph.add_node("hr_coordinator", hr_coordinator_node)
    graph.add_node("hr_tools", hr_tool_node)
    graph.add_node("handover", handover_passthrough)
    graph.add_node("action_executor", action_executor_node)
    graph.add_node("action_tools", action_tool_node)

    graph.set_entry_point("hr_coordinator")

    graph.add_conditional_edges(
        "hr_coordinator",
        route_hr_coordinator,
        {"hr_tools": "hr_tools", "action_executor": "handover", END: END},
    )
    graph.add_edge("hr_tools", "hr_coordinator")
    graph.add_edge("handover", "action_executor")

    graph.add_conditional_edges(
        "action_executor",
        route_action_executor,
        {"action_tools": "action_tools", END: END},
    )
    graph.add_edge("action_tools", "action_executor")

    compile_kwargs = {}
    if checkpointer is not None:
        compile_kwargs["checkpointer"] = checkpointer
    if interrupt_before is not None:
        compile_kwargs["interrupt_before"] = interrupt_before

    return graph.compile(**compile_kwargs)
