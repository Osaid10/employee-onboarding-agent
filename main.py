"""
Intelligent Employee Onboarding Agent - Main Entry Point
=========================================================
AI407L Capstone Project

Usage:
    python main.py                  # Interactive multi-agent session
    python main.py --single         # Single-agent ReAct mode
    python main.py --seed           # Seed the HRIS database
    python main.py --ingest         # Run RAG ingestion pipeline
    python main.py --demo           # Run full demo (seed + ingest + agent)
"""

import argparse
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def seed_database():
    """Seed the HRIS database with sample employees and tasks."""
    from src.database.seed import seed
    print("=" * 50)
    print("  Seeding HRIS Database")
    print("=" * 50)
    seed()
    print("\nDatabase seeded successfully!")


def run_ingestion():
    """Run the RAG ingestion pipeline."""
    from src.ingestion.ingest_data import ingest_all
    print("=" * 50)
    print("  Running RAG Ingestion Pipeline")
    print("=" * 50)
    ingest_all()
    print("\nIngestion complete!")


def run_single_agent():
    """Run the single-agent ReAct loop interactively."""
    from src.agents.graph import build_react_graph
    from langchain_core.messages import HumanMessage

    print("=" * 50)
    print("  Onboarding Agent (Single-Agent ReAct Mode)")
    print("=" * 50)
    print("Type your request (or 'quit' to exit):\n")

    graph = build_react_graph()

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break
        if not user_input:
            continue

        result = graph.invoke({
            "messages": [HumanMessage(content=user_input)]
        })

        last_msg = result["messages"][-1]
        print(f"\nAgent: {last_msg.content}\n")


def run_multi_agent():
    """Run the multi-agent system interactively."""
    from src.agents.multi_agent_graph import build_multi_agent_graph
    from langchain_core.messages import HumanMessage

    print("=" * 50)
    print("  Onboarding Agent (Multi-Agent Mode)")
    print("=" * 50)
    print("  HR Coordinator -> Action Executor")
    print("Type your request (or 'quit' to exit):\n")

    graph = build_multi_agent_graph()

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break
        if not user_input:
            continue

        result = graph.invoke({
            "messages": [HumanMessage(content=user_input)],
            "current_agent": "hr_coordinator",
            "handover_summary": "",
            "task_complete": False,
        })

        last_msg = result["messages"][-1]
        print(f"\nAgent: {last_msg.content}\n")


def run_demo():
    """Run the full demo: seed DB, ingest docs, then run a sample query."""
    from langchain_core.messages import HumanMessage

    seed_database()
    print()
    run_ingestion()
    print()

    print("=" * 50)
    print("  Running Demo Query")
    print("=" * 50)

    from src.agents.multi_agent_graph import build_multi_agent_graph
    graph = build_multi_agent_graph()

    demo_query = (
        "Check on employee EMP-003 (Priya Patel). Are there any overdue tasks? "
        "If so, send appropriate reminders and escalate any compliance issues."
    )
    print(f"\nDemo Query: {demo_query}\n")

    result = graph.invoke({
        "messages": [HumanMessage(content=demo_query)],
        "current_agent": "hr_coordinator",
        "handover_summary": "",
        "task_complete": False,
    })

    last_msg = result["messages"][-1]
    print(f"\nFinal Response:\n{last_msg.content}")


def main():
    parser = argparse.ArgumentParser(
        description="Intelligent Employee Onboarding Agent"
    )
    parser.add_argument(
        "--single", action="store_true",
        help="Run in single-agent ReAct mode"
    )
    parser.add_argument(
        "--seed", action="store_true",
        help="Seed the HRIS database"
    )
    parser.add_argument(
        "--ingest", action="store_true",
        help="Run RAG ingestion pipeline"
    )
    parser.add_argument(
        "--demo", action="store_true",
        help="Run full demo (seed + ingest + multi-agent query)"
    )
    args = parser.parse_args()

    if args.seed:
        seed_database()
    elif args.ingest:
        run_ingestion()
    elif args.demo:
        run_demo()
    elif args.single:
        run_single_agent()
    else:
        run_multi_agent()


if __name__ == "__main__":
    main()
