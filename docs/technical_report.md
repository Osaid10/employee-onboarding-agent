# Technical Report -- Intelligent Employee Onboarding Agent
## AI407L Mid-Term Examination | Spring 2026

**Student:** Osaid
**Course:** AI407L -- Agentic AI Systems

---

## Executive Summary

This report documents the design, implementation, and evaluation of the
**Intelligent Employee Onboarding Agent** -- an AI system that automates the
coordination, monitoring, and compliance enforcement of employee onboarding
across HR, IT, and departmental workflows.

The project is structured across two examination parts:

**Part A** covers the full agentic pipeline: a RAG-based knowledge foundation
grounded in company policies (Lab 2), a single-agent ReAct reasoning loop
(Lab 3), multi-agent orchestration with an HR Coordinator and Action Executor
(Lab 4), and persistent state management with human-in-the-loop safety
controls (Lab 5).

**Part B** demonstrates the Model Context Protocol (MCP) as an alternative
tool integration standard -- a standalone Weather & News Briefing server and
client showing how MCP enables process-isolated, language-agnostic, and
dynamically discoverable tool exposure.

---

## Part A -- Agent System

### Lab 2: RAG Pipeline and Knowledge Engineering

#### Problem

An LLM has no knowledge of internal company onboarding policies, compliance
requirements, department-specific handbooks, or benefits enrollment deadlines.
Without domain grounding, the agent would hallucinate policy details, invent
deadlines, and generate incorrect compliance guidance -- unacceptable in an
HR context where regulatory violations carry legal consequences.

#### Solution: RAG Pipeline (`src/ingestion/ingest_data.py`)

The pipeline ingests five Markdown policy documents from `data/policies/`:

| Document | Content |
|----------|---------|
| `onboarding_policy.md` | Master onboarding checklist, pre-boarding requirements, timelines |
| `compliance_guidelines.md` | I-9, W-4, EEOC, OSHA regulatory requirements |
| `engineering_handbook.md` | Dev environment setup, code review guidelines, architecture overview |
| `benefits_guide.md` | Health insurance, 401(k), dental/vision enrollment windows |
| `sales_handbook.md` | CRM access, product certification, sales playbook review |

**Stage 1 -- Load:** Reads all `.md` files from the policies directory using
Python file I/O.

**Stage 2 -- Clean:** Normalizes whitespace (collapses 3+ newlines to 2),
strips trailing whitespace, and fixes malformed markdown headers (ensures
space after `#`).

**Stage 3 -- Semantic Chunking:** Splits documents on `##` and `###` header
boundaries rather than fixed character counts. This preserves each policy
section as a complete, self-contained chunk. A question about "I-9 requirements"
returns the full compliance section rather than a fragment split mid-sentence.
Chunks shorter than 30 characters are discarded (header-only artifacts).

**Stage 4 -- Metadata Enrichment:** Attaches seven metadata tags to each chunk:
- `doc_type`: policy, compliance, handbook, benefits, sales
- `department`: all, engineering, hr, sales (derived from filename)
- `priority_level`: critical/high/medium/low (inferred from keyword presence)
- `source_file`: original filename for source attribution
- `last_updated`: document revision date
- `section_header`: the markdown heading text
- `header_level`: heading depth (1, 2, or 3)

Priority inference uses three keyword lists: critical keywords (must, required,
mandatory, I-9, W-4, HIPAA, termination), high keywords (deadline, within,
background check, NDA), and medium keywords (recommended, should, training,
benefits).

**Stage 5 -- Embedding:** Uses Google's `gemini-embedding-001` model. Batched
in groups of 80 with 60-second waits between batches to respect the Gemini
free-tier rate limit of 100 requests/minute.

**Stage 6 -- Storage:** Persists chunks into ChromaDB persistent collection
`onboarding_knowledge` at `./chroma_db/` using cosine similarity
(`hnsw:space: cosine`). The collection is deleted and recreated on each
ingestion run for idempotency.

#### Retrieval Verification (`docs/retrieval_test.md`)

Three queries confirm the pipeline's precision:

1. **General policy query** (no filter): "What forms does a new hire need to
   submit before their start date?" -- top chunk (score 0.87) lists all 5
   required forms (I-9, W-4, NDA, background check, direct deposit).

2. **Department filter** (`department: engineering`): "What development tools
   does an engineer need to set up?" -- top chunk (score 0.91) lists Docker,
   monorepo access, IDE config, VPN, CI/CD. Filter prevents contamination
   from general IT or sales tool content.

3. **Priority filter** (`priority_level: critical`): "What is the deadline
   for health insurance enrollment?" -- top chunk (score 0.93) gives the
   exact 30-day window, plan options with dollar amounts, and consequences
   of missing the deadline.

---

### Lab 3: ReAct Reasoning Loop (`src/agents/graph.py`, `src/tools/tools.py`)

#### Architecture

The single-agent system implements the ReAct (Reason + Act) pattern using
LangGraph's `StateGraph`.

**State:**
```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
```

**Agent Node:** Prepends a system prompt and invokes Google Gemini
(`gemini-flash-latest`) with all 8 tools bound. The system prompt defines
8 specific responsibilities and guidelines for handling high-risk actions.

**Tool Node:** `ToolNode(ALL_TOOLS)` auto-dispatches tool calls and appends
results as `ToolMessage` objects.

**Conditional Router:**
```python
def should_continue(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END
```

#### Tool Design (`src/tools/tools.py`)

All 8 tools use `@tool` with `args_schema=<PydanticModel>`. The Pydantic
schemas enforce argument types at the framework level. Each tool has a
descriptive docstring that serves as the LLM's instruction for when to
invoke it.

| Tool | Type | Description |
|------|------|-------------|
| `query_onboarding_policy` | Read | RAG search over ChromaDB with optional department filter |
| `get_employee_info` | Read | SQLAlchemy query for employee profile from HRIS |
| `get_task_status` | Read | All onboarding tasks with statuses, due dates, overdue flags |
| `check_compliance_status` | Read | COMPLIANT/NON-COMPLIANT assessment of mandatory tasks |
| `generate_onboarding_report` | Read | Progress summary with completion %, category breakdown |
| `update_task_status` | Write | Modifies task status in SQLite; marks completion date |
| `send_reminder_email` | Action | Simulated email, logged to EmailLog table for audit |
| `send_escalation_alert` | Action | Creates Escalation record with urgency level |

The database is a real SQLite database (`hris.db`) with 4 SQLAlchemy models:
`Employee`, `OnboardingTask`, `Escalation`, `EmailLog` -- all with proper
foreign keys, relationships, and cascading deletes.

---

### Lab 4: Multi-Agent Orchestration

#### Motivation

A single agent handling both information gathering and action execution
suffers from two problems: (1) instruction creep as context fills with tool
results, and (2) safety risk -- a hallucinated tool call during research
could accidentally send an email or update a status.

#### Agent Specialization

**HR Coordinator Agent** (5 read-only tools):
- Goal: gather raw facts, assess compliance, identify issues
- Constraint: cannot send emails, update statuses, or create escalations
- System prompt includes a 10-year HR analyst persona for grounding

**Action Executor Agent** (3 write/action tools):
- Goal: execute recommended actions from HR Coordinator's handover
- Tools: `update_task_status`, `send_reminder_email`, `send_escalation_alert`
- System prompt includes guidelines for email tone, escalation urgency levels

#### Handoff Protocol

The HR Coordinator ends its analysis with `HANDOVER:` followed by a structured
summary. The `route_hr_coordinator()` function detects this string:

```python
if "HANDOVER:" in content:
    summary = content[content.index("HANDOVER:") + len("HANDOVER:"):].strip()
    state["handover_summary"] = summary
    return "action_executor"
```

A `handover_passthrough` node extracts the summary and sets
`current_agent = "action_executor"` before passing to Agent B.

#### Graph Topology

5 nodes: `hr_coordinator`, `hr_tools`, `handover`, `action_executor`,
`action_tools`. Each tool node is scoped -- `hr_tool_node = ToolNode(HR_COORDINATOR_TOOLS)`
only knows 5 tools. Even if the LLM hallucinates `send_reminder_email`,
the ToolNode cannot find it, enforcing the boundary at the execution layer.

#### State Schema

```python
class MultiAgentState(TypedDict):
    messages: Annotated[list, add_messages]
    current_agent: str
    handover_summary: str
    task_complete: bool
```

The `handover_summary` field carries the structured findings from Agent A
to Agent B, ensuring the action agent has clear instructions.

---

### Lab 5: State Management and Human-in-the-Loop

#### Task 1 -- Persistent Memory (`src/persistence/persistence_test.py`)

`SqliteSaver` is used as the checkpointer, persisting full State to
`checkpoint_db.sqlite` keyed by `thread_id`.

**Verification:** Session 1 asks about EMP-003's onboarding status and
compliance. Session 2 (simulating an app restart with a new graph instance
but same checkpointer and thread_id) asks: "Based on what you found earlier
about EMP-003, which tasks are overdue and what actions would you recommend?"
The pronoun "what you found earlier" is only resolvable if the checkpoint
restored Session 1's context. The agent answers correctly.

#### Task 2 -- Safety Breakpoints (`src/persistence/approval_logic.py`)

The multi-agent graph is compiled with
`interrupt_before=["action_tools"]`. When the Action Executor proposes a
high-risk tool call (any of its 3 tools), LangGraph:

1. Saves pending State to SQLite
2. Returns control to the Python caller
3. The caller inspects `graph.get_state(config)` and displays pending tool
   calls with full argument details

The human then chooses:
- **Proceed** -- `graph.invoke(None, config)` resumes execution
- **Cancel** -- Injects `ToolMessage` with `[CANCELLED BY HUMAN]` content
  for each pending tool call, then resumes so the agent responds gracefully
- **Edit** -- Interactive modification of each argument

#### Task 3 -- State Editing

The `edit_tool_call_args()` function iterates over each pending tool call's
arguments, prompting the human for new values. A new `AIMessage` is
constructed with the modified `tool_calls` and pushed via
`graph.update_state(config, {"messages": [modified_msg]})`. The graph then
resumes and executes the human-edited version.

---

## Part B -- MCP Pipeline

### B1 -- MCP Server (`mcp/server.py`)

#### Domain Choice

The Weather & News Briefing domain was chosen to be completely independent
of the Part A onboarding codebase. No imports from `src/` appear in Part B.

#### MCP Component Mapping

| MCP Concept | Implementation |
|-------------|---------------|
| **Model** | The AI client (`mcp/client.py`) that issues requests |
| **Context** | `app.create_initialization_options()` -- server name, capabilities |
| **Tools** | Three functions registered via `@app.list_tools()` |
| **Execution** | `stdio_server` transport + `asyncio.run(app.run(...))` |

#### 4-Layer Architecture

The server is explicitly structured into four layers:

1. **Model Layer** -- Static data dictionaries simulating external sources
   (weather data for 5 cities, news headlines across 4 categories)

2. **Context Layer** -- Input validation functions (`resolve_weather_params`,
   `resolve_news_params`) that validate city names against available data,
   enforce valid temperature units (celsius/fahrenheit), and check news
   count bounds (1-5)

3. **Tools Layer** -- MCP tool definitions with JSON schemas registered via
   `@app.list_tools()`. Three tools:
   - `get_weather` -- Returns temperature, condition, humidity, wind speed
     for a supported city with unit conversion
   - `get_news_headlines` -- Returns top-N headlines for a category with
     source and publication date
   - `get_daily_briefing` -- Combines weather and news into a formatted
     daily briefing string

4. **Execution Layer** -- `@app.call_tool()` dispatcher that routes tool
   names to execution handlers, with error handling for validation failures

#### Transport

The server communicates over stdio using JSON-RPC -- the standard MCP
transport. No HTTP server, no open ports.

---

### B2 -- MCP Client (`mcp/client.py`)

The client demonstrates the full MCP lifecycle:

**Step 1 -- Connection:** Spawns `server.py` as a subprocess via
`StdioServerParameters(command=python, args=[server.py])`.

**Step 2 -- Handshake:** `await session.initialize()` exchanges capabilities.

**Step 3 -- Tool Discovery:** `await session.list_tools()` returns all 3
tools with their names, descriptions, and JSON input schemas. The client
displays each tool's parameters with required/optional annotations.

**Step 4 -- Tool Invocation:** All 3 tools are called:
- `get_weather(city="Islamabad", units="celsius")`
- `get_news_headlines(category="technology", count=3)`
- `get_daily_briefing(city="Islamabad", news_category="technology")`

**Step 5 -- Response Handling:** JSON responses are parsed and formatted for
display.

---

### B3 -- Technical Comparison (`mcp/mcp_comparison.md`)

Key conclusions from the formal comparison:

| Dimension | Direct Invocation | LangGraph | MCP |
|-----------|------------------|-----------|-----|
| Coupling | Tight (import-time) | Medium (framework) | Loose (protocol) |
| Process boundary | None | None | Yes (separate OS process) |
| Language requirement | Python only | Python only | Any language |
| Tool discovery | Static (import) | Static (compile) | Dynamic (runtime) |
| Security | Minimal isolation | Framework-level | Process isolation + auth |
| Scalability | Vertical only | Framework-bound | Independent horizontal |

MCP improves production systems through:
- **Security**: Process isolation, credential scoping, network segmentation
- **Scalability**: Independent deployment and horizontal scaling per tool
- **System abstraction**: JSON Schema contracts, transport independence
- **Separation of concerns**: Model/Context/Tools/Protocol boundaries enable
  parallel development across teams

---

## Technology Choices -- Justification

| Choice | Rationale |
|--------|-----------|
| **Google Gemini (gemini-flash-latest)** | Free tier with tool-calling support, fast inference, native embeddings API |
| **ChromaDB** | Local persistence, Python-native, metadata filtering for department/priority queries |
| **SQLAlchemy + SQLite** | Real relational database with ORM; 4 models with foreign keys, relationships, cascading deletes -- not mock data |
| **LangGraph over CrewAI/AutoGen** | Explicit graph control enables deterministic routing; SqliteSaver is production-grade; interrupt_before is a first-class HITL primitive |
| **Header-based chunking** | Preserves semantic completeness of policy sections vs. fixed-size chunking that splits mid-sentence |
| **Keyword-based priority inference** | Enables filtered retrieval of compliance-critical content without manual tagging |

---

## Conclusion

The Intelligent Employee Onboarding Agent demonstrates a complete
production-grade agentic pipeline: domain knowledge grounded in company
policies via RAG (Lab 2), autonomous multi-tool reasoning via ReAct (Lab 3),
specialised collaboration via multi-agent orchestration with clear
read/write separation (Lab 4), and safe real-world execution via persistent
state and human-in-the-loop controls (Lab 5).

Part B extends this foundation by demonstrating MCP as a standardized
protocol for tool exposure -- enabling process-isolated, language-agnostic,
and dynamically discoverable tool integration that is essential for
production multi-team AI deployments.
