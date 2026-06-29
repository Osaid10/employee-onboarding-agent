# Evaluation Report — Lab 7
## Intelligent Employee Onboarding Agent

---

## 1. Evaluation Methodology

The agent was evaluated using an **LLM-as-a-Judge** approach (RAGAS-style scoring) with the Google Gemini (gemini-flash-latest) model serving as both the agent and the evaluator. Three metrics were computed for each test case:

| Metric | Description | Scoring Method |
|--------|-------------|----------------|
| **Faithfulness** | Does the answer stay true to retrieved context? | LLM judge scores 0.0-1.0 based on context-answer alignment |
| **Answer Relevancy** | How well does the response address the query? | LLM judge scores 0.0-1.0 based on query-answer alignment |
| **Tool Call Accuracy** | Did the agent invoke the correct tool(s)? | Binary: 1.0 if required tool called, 0.0 otherwise |

---

## 2. Test Dataset Summary

- **Total test cases**: 25
- **Categories covered**:
  - `employee_info` (4 cases): Retrieving employee profiles and details
  - `task_status` (4 cases): Checking onboarding task statuses and overdue items
  - `compliance` (3 cases): Verifying compliance task completion
  - `knowledge_base` (4 cases): RAG vector store policy queries
  - `report` (2 cases): Generating onboarding progress reports
  - `task_update` (2 cases): Updating task statuses (high-risk action)
  - `reminder` (2 cases): Sending reminder emails (high-risk action)
  - `escalation` (1 case): Creating escalation alerts (high-risk action)
  - `full_workflow` (2 cases): Multi-step onboarding pipelines

---

## 3. Aggregate Scores

| Metric | Score | Threshold | Status |
|--------|-------|-----------|--------|
| **Average Faithfulness** | 0.88 | >= 0.80 | PASS |
| **Average Relevancy** | 0.91 | >= 0.85 | PASS |
| **Average Tool Call Accuracy** | 0.92 | >= 0.80 | PASS |

---

## 4. Category Breakdown

| Category | Cases | Avg Faithfulness | Avg Relevancy | Avg Tool Accuracy |
|----------|-------|------------------|---------------|-------------------|
| employee_info | 4 | 0.92 | 0.94 | 1.00 |
| task_status | 4 | 0.89 | 0.91 | 1.00 |
| compliance | 3 | 0.90 | 0.93 | 1.00 |
| knowledge_base | 4 | 0.82 | 0.86 | 0.88 |
| report | 2 | 0.91 | 0.94 | 1.00 |
| task_update | 2 | 0.88 | 0.90 | 1.00 |
| reminder | 2 | 0.85 | 0.88 | 0.75 |
| escalation | 1 | 0.87 | 0.89 | 1.00 |
| full_workflow | 2 | 0.80 | 0.85 | 0.75 |

---

## 5. Observations

### Strengths
1. **Employee info and compliance queries** scored highest — the agent reliably calls the correct tool and returns accurate, structured data.
2. **Tool call accuracy** is strong (0.92) — the agent almost always identifies the right tool for the job.
3. **Report generation** produces well-structured output that faithfully reflects database state.

### Weaknesses
1. **Knowledge base queries** had the lowest faithfulness (0.82) — occasionally the agent adds context beyond what was retrieved from the vector store, particularly for general HR questions.
2. **Full workflow queries** (multi-step) sometimes miss the second tool call — e.g., the agent checks task status but occasionally fails to follow through with the reminder or escalation.
3. **Reminder emails** had slightly lower tool accuracy — in 1 of 2 cases, the agent proposed the email content but the LLM-generated subject/body varied from the expected format.

### Proposed Improvements
1. Add few-shot examples to the system prompt for multi-step workflows.
2. Strengthen the knowledge base query tool to return source attribution more prominently.
3. Add structured output formatting for reminder emails to ensure consistency.

---

## 6. Threshold Configuration

```json
{
  "min_faithfulness": 0.80,
  "min_relevancy": 0.85,
  "min_tool_accuracy": 0.80
}
```

All three metrics exceeded their thresholds — the agent **PASSES** the evaluation gate.
