"""
Lab 6 — Secured LangGraph with Guardrail Nodes.

Wraps the single-agent ReAct graph with:
  - A guardrail_node that runs BEFORE the agent_node
  - An alert_node that returns a standardized refusal
  - Output sanitization on every agent response

If input is classified as UNSAFE, the graph routes directly to the
alert_node — the agent LLM is never invoked.
"""

from typing import Annotated

from langchain_core.messages import AIMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

from src.config import GOOGLE_API_KEY, LLM_MODEL
from src.tools.tools import ALL_TOOLS
from src.agents.graph import SYSTEM_PROMPT
from src.agents.guardrails_config import (
    run_deterministic_guardrail,
    run_llm_judge_guardrail,
    sanitize_output,
    SafetyVerdict,
)


# ---------------------------------------------------------------------------
# State (extended with guardrail fields)
# ---------------------------------------------------------------------------
class SecuredAgentState(TypedDict):
    messages: Annotated[list, add_messages]
    guardrail_verdict: str
    guardrail_reason: str


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------
def guardrail_node(state: SecuredAgentState) -> dict:
    """Run input through both guardrail layers before the agent sees it.

    Layer 1 (Deterministic): Fast regex + keyword check.
    Layer 2 (LLM-as-a-Judge): Secondary check for subtle attacks.
    """
    # Extract the latest user message
    user_input = ""
    for msg in reversed(state["messages"]):
        if hasattr(msg, "content") and hasattr(msg, "type") and msg.type == "human":
            user_input = msg.content if isinstance(msg.content, str) else str(msg.content)
            break

    if not user_input:
        return {"guardrail_verdict": "SAFE", "guardrail_reason": "No user input found."}

    # Layer 1: Deterministic
    det_result = run_deterministic_guardrail(user_input)
    if det_result.verdict == SafetyVerdict.UNSAFE:
        return {
            "guardrail_verdict": "UNSAFE",
            "guardrail_reason": f"[Deterministic] {det_result.reason} (Rule: {det_result.matched_rule})",
        }

    # Layer 2: LLM-as-a-Judge
    try:
        llm_result = run_llm_judge_guardrail(user_input)
        if llm_result.verdict == SafetyVerdict.UNSAFE:
            return {
                "guardrail_verdict": "UNSAFE",
                "guardrail_reason": f"[LLM Judge] {llm_result.reason}",
            }
    except Exception:
        # If LLM judge fails, fall back to deterministic-only (already passed)
        pass

    return {"guardrail_verdict": "SAFE", "guardrail_reason": "Input passed all guardrails."}


def agent_node(state: SecuredAgentState) -> dict:
    """Invoke the LLM with the current messages and bound tools."""
    llm = ChatGoogleGenerativeAI(
        model=LLM_MODEL,
        google_api_key=GOOGLE_API_KEY,
        temperature=0,
    ).bind_tools(ALL_TOOLS)

    messages = list(state["messages"])
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages

    response = llm.invoke(messages)

    # Apply output sanitization
    if isinstance(response.content, str):
        response = AIMessage(
            content=sanitize_output(response.content),
            tool_calls=response.tool_calls if hasattr(response, "tool_calls") else [],
        )

    return {"messages": [response]}


def alert_node(state: SecuredAgentState) -> dict:
    """Return a standardized refusal when input is classified as UNSAFE."""
    reason = state.get("guardrail_reason", "")

    refusal = (
        "I've detected a prompt manipulation attempt. I must stay on topic and "
        "follow my designated instructions. I am the Employee Onboarding Agent "
        "and can only assist with:\n"
        "- Looking up onboarding policies and compliance requirements\n"
        "- Retrieving employee information and task statuses\n"
        "- Sending reminders and escalation alerts\n"
        "- Generating onboarding progress reports\n"
        "- Checking compliance status\n\n"
        "How can I help with your onboarding needs?"
    )

    return {"messages": [AIMessage(content=refusal)]}


# Tool execution node
tool_node = ToolNode(ALL_TOOLS)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
def route_after_guardrail(state: SecuredAgentState) -> str:
    """Route to agent if SAFE, alert if UNSAFE."""
    if state.get("guardrail_verdict") == "UNSAFE":
        return "alert"
    return "agent"


def should_continue(state: SecuredAgentState) -> str:
    """Route to 'tools' if the last message contains tool calls, else END."""
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------
def build_secured_graph(checkpointer=None):
    """Build and compile the secured single-agent graph with guardrails."""
    graph = StateGraph(SecuredAgentState)

    graph.add_node("guardrail", guardrail_node)
    graph.add_node("agent", agent_node)
    graph.add_node("alert", alert_node)
    graph.add_node("tools", tool_node)

    graph.set_entry_point("guardrail")

    graph.add_conditional_edges(
        "guardrail",
        route_after_guardrail,
        {"agent": "agent", "alert": "alert"},
    )

    graph.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", END: END},
    )

    graph.add_edge("tools", "agent")
    graph.add_edge("alert", END)

    compile_kwargs = {}
    if checkpointer is not None:
        compile_kwargs["checkpointer"] = checkpointer

    return graph.compile(**compile_kwargs)
