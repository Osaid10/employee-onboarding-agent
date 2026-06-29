# Employee Onboarding Agent

> An autonomous, multi-agent system that runs employee onboarding end-to-end — tracking tasks across HR/IT systems, answering policy questions with grounded citations, and proactively chasing blockers without human intervention.

Built with **LangGraph**, **LLMs**, **RAG**, **FastAPI**, and **Streamlit** — fully containerized with Docker.

---

## The Problem

Employee onboarding spans 30–90 days and pulls in HR, IT, facilities, and managers. In practice it's chaotic:

- HR spends **15–20 hours per hire** manually tracking documents, approvals, and task completion
- Policies are scattered across PDFs, wikis, and tribal knowledge
- ~40% of new hires miss critical deadlines (tax forms, benefits) for lack of proactive reminders
- Managers have no real-time view of onboarding status
- Missing I-9s, background checks, or training certs create compliance risk

## The Solution

An agentic system that owns the onboarding workflow. It monitors 20+ tasks per employee across connected systems, answers new-hire questions from official policy documents via RAG, and autonomously sends reminders and escalates blockers — cutting simulated onboarding coordination from 15–20 hours to under 5 per hire.

## Key Features

- **Multi-agent orchestration** — specialized agents coordinated by a LangGraph state machine
- **RAG over policy documents** — grounded, citation-backed answers from company PDFs (ChromaDB)
- **Autonomous task tracking** — monitors document submission, approvals, and completion across HRIS, email, and task systems
- **Proactive reminders & escalation** — chases overdue items and flags blockers without a human in the loop
- **Tool use via MCP** — Model Context Protocol integration for external tool access
- **Web + API interfaces** — FastAPI backend with a Streamlit dashboard and a lightweight web UI
- **Evaluation suite** — automated evaluation harness with configurable quality thresholds
- **Dockerized** — single `docker-compose up` deployment

## Tech Stack

| Layer | Tools |
|---|---|
| Orchestration | LangGraph, LangChain |
| LLM | Google Gemini |
| Retrieval | ChromaDB (RAG) |
| Backend | FastAPI |
| UI | Streamlit + static web UI |
| Tooling | MCP (Model Context Protocol) |
| Infra | Docker, docker-compose |

## Architecture

```
                 ┌──────────────┐
   New hire ──▶  │  Streamlit / │  ──▶  FastAPI API
   / HR user     │   Web UI     │
                 └──────────────┘
                        │
                        ▼
            ┌────────────────────────┐
            │   LangGraph State Machine │
            │  ┌──────┐  ┌──────────┐  │
            │  │ Task │  │ Policy   │  │
            │  │ Agent│  │ RAG Agent│  │
            │  └──────┘  └──────────┘  │
            │  ┌──────────────────┐    │
            │  │ Reminder/Escalate│    │
            │  └──────────────────┘    │
            └────────────────────────┘
                 │            │
                 ▼            ▼
            HRIS / Email   ChromaDB (policies)
            / Task systems
```

## Getting Started

### Prerequisites
- Python 3.11+
- Docker (optional, for containerized run)
- A Google Gemini API key

### Setup

```bash
# 1. Clone
git clone https://github.com/Osaid10/employee-onboarding-agent.git
cd employee-onboarding-agent

# 2. Configure environment
cp .env.example .env
# edit .env and add your GOOGLE_API_KEY

# 3. Install dependencies
pip install -r requirements.txt

# 4. Seed data and ingest policy documents
python -m src.database.seed
python -m src.ingestion.ingest_data
```

### Run

```bash
# Streamlit dashboard
streamlit run streamlit_app.py

# or the FastAPI service
python api_main.py
```

### Docker

```bash
docker-compose up --build
```

## Evaluation

```bash
python run_eval.py
```
Thresholds are configurable in `eval_threshold_config.json`.

## Project Layout

```
src/
├── agents/        # LangGraph agents, graphs, guardrails
├── database/      # models + seed data
├── ingestion/     # policy document ingestion (RAG)
├── persistence/   # approval logic, state persistence
└── tools/         # agent tools
mcp/               # Model Context Protocol client + server
web/               # FastAPI app + static web UI
docs/              # design notes, evaluation & technical reports
```

## Documentation

See [`PRD.md`](PRD.md) for the full product requirements document, and [`docs/`](docs/) for technical, evaluation, and security reports.

---

*Built as a capstone project demonstrating production-grade agentic AI, RAG, and MLOps practices.*
