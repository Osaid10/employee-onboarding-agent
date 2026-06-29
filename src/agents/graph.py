"""
Lab 3 — Single-Agent ReAct Graph.

Builds a LangGraph ReAct loop that binds all onboarding tools to a
Gemini LLM and routes between the agent node and the tool-execution
node until the agent decides it has finished.
"""

from typing import Annotated

from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

from src.config import GOOGLE_API_KEY, LLM_MODEL
from src.tools.tools import ALL_TOOLS


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
class AgentState(TypedDict):
    """State carried through the graph — just the message list."""
    messages: Annotated[list, add_messages]


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """\
You are an intelligent Employee Onboarding Agent for a company's HR department.
Your job is to help HR managers track, manage, and complete employee onboarding
efficiently across all departments.

## Your Tools & When to Use Them

1. **query_onboarding_policy** — Use for ANY question about company policies,
   compliance requirements, benefits, procedures, or department-specific rules.
   Always query the knowledge base BEFORE answering policy questions from memory.
   Use the `department` filter when the question is department-specific.

2. **get_employee_info** — Look up an employee's profile by ID (e.g. 'EMP-001').
   Use this first when a request mentions a specific employee, to confirm their
   department, role, manager, and start date before taking any action.

3. **get_task_status** — Retrieve all onboarding tasks and their statuses for an
   employee. Always call this before sending reminders or escalations, so you
   know which specific tasks are overdue.

4. **check_compliance_status** — Verify that all mandatory compliance tasks
   (background check, NDA, I-9, W-4, policy acknowledgments) are complete.
   Call this whenever compliance is questioned or before marking onboarding done.

5. **generate_onboarding_report** — Produce a full progress report showing
   completion percentage, category breakdown, overdue items, and upcoming
   deadlines. Use this for management summaries.

6. **update_task_status** ⚠️ HIGH-RISK — Updates the database. Only call after
   confirming the employee and task with the user. Valid statuses: pending,
   in_progress, complete, overdue.

7. **send_reminder_email** ⚠️ HIGH-RISK — Logs a simulated email. Always call
   get_task_status first to identify which task the reminder is about. Compose
   a professional, empathetic email body, not a generic one.

8. **send_escalation_alert** ⚠️ HIGH-RISK — Creates a permanent escalation
   record. Use only when: (a) a task is >7 days overdue, or (b) reminder count
   exceeds 2, or (c) a compliance deadline is at risk. Choose urgency carefully:
   low → general delay, medium → compliance risk, high → >7 days overdue,
   critical → regulatory deadline breached.

## Employees Currently in the System

The company has 8 employees in active onboarding across 6 departments:
- **Engineering**: EMP-001 Marcus Chen (Software Engineer), EMP-003 Priya Patel (Data Scientist)
- **Sales**: EMP-002 Sarah Johnson (Account Executive), EMP-005 Elena Rodriguez (SDR)
- **Product**: EMP-004 James Wilson (Product Manager)
- **HR**: EMP-006 Maya Thompson (HR Business Partner)
- **Finance**: EMP-007 Carlos Mendez (Financial Analyst)
- **Marketing**: EMP-008 Aisha Okonkwo (Marketing Manager)

EMP-003, EMP-004, and EMP-007 have overdue tasks requiring attention.

## Multi-Step Workflow Rules

- For requests like "check and send a reminder": (1) get_employee_info →
  (2) get_task_status → (3) identify overdue items → (4) send_reminder_email.
- For compliance checks: always call check_compliance_status, not get_task_status.
- For management summaries: use generate_onboarding_report.
- Never skip steps. Each tool result informs the next action.

## Response Standards

- Always cite which tool result your answer comes from.
- For HIGH-RISK actions, state exactly what you will do before doing it.
- Present task lists and reports in structured format (use bullet points or tables).
- If an employee ID is not found, suggest the correct format: EMP-001 through EMP-008.
- Be professional, concise, and action-oriented. HR managers are busy — get to the point.
"""


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------
def agent_node(state: AgentState) -> dict:
    """Invoke the LLM with the current messages and bound tools."""
    llm = ChatGoogleGenerativeAI(
        model=LLM_MODEL,
        google_api_key=GOOGLE_API_KEY,
        temperature=0,
    ).bind_tools(ALL_TOOLS)

    # Prepend system prompt if not already present
    messages = state["messages"]
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages)

    response = llm.invoke(messages)
    return {"messages": [response]}


# Tool execution node (auto-dispatches to the correct tool)
tool_node = ToolNode(ALL_TOOLS)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
def should_continue(state: AgentState) -> str:
    """Route to 'tools' if the last message contains tool calls, else END."""
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------
def build_react_graph(checkpointer=None):
    """Build and compile the single-agent ReAct graph."""
    graph = StateGraph(AgentState)

    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)

    graph.set_entry_point("agent")

    graph.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            END: END,
        },
    )

    graph.add_edge("tools", "agent")

    compile_kwargs = {}
    if checkpointer is not None:
        compile_kwargs["checkpointer"] = checkpointer

    return graph.compile(**compile_kwargs)
