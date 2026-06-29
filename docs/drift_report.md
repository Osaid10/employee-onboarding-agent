# Drift Report — Lab 11
## Feedback Analysis & Failure Categorization

---

## 1. Aggregate Statistics

| Metric | Value |
|--------|-------|
| Total Interactions Logged | 12 |
| Positive Feedback (+1) | 8 |
| Negative Feedback (-1) | 3 |
| Neutral Feedback (0) | 1 |
| Satisfaction Rate | 66.7% |

---

## 2. Failure Category Breakdown

| Category | Count | Percentage |
|----------|-------|------------|
| Incomplete Answer | 1 | 33.3% |
| Hallucination | 1 | 33.3% |
| Tool Error | 1 | 33.3% |

---

## 3. Sample Failed Interactions

### Feedback #3 — Incomplete Answer
- **User Input:** Check the onboarding status for EMP-001 and tell me what to do about overdue tasks.
- **Agent Response:** Here is the onboarding status for EMP-001: 5/15 tasks completed (33%). There are 3 overdue tasks...
- **User Comment:** Agent listed the overdue tasks but didn't actually recommend what to do about them.

### Feedback #7 — Hallucination
- **User Input:** What is the company's policy on remote work during onboarding?
- **Agent Response:** The company allows remote work during the first week of onboarding for employees in the engineering department...
- **User Comment:** This information isn't in our policies. The agent made it up.

### Feedback #10 — Tool Error
- **User Input:** Send a reminder to EMP-002 about the IT Equipment Setup task.
- **Agent Response:** I'll send a reminder about the IT Equipment Setup task. However, I encountered an error...
- **User Comment:** The agent tried to call the tool with wrong task name format.

---

## 4. Recommendations

Based on the failure analysis:

1. **Incomplete Answer (33%)**: The agent sometimes answers the "what" but not the "what to do." Add explicit instructions to the system prompt requiring the agent to provide actionable recommendations when listing problems.

2. **Hallucination (33%)**: The agent occasionally generates information not present in the retrieved context. Strengthen the system prompt to emphasize: "Only use information from tool results. If the information is not available in the knowledge base, say so explicitly."

3. **Tool Error (33%)**: The agent sometimes paraphrases task names instead of using exact names from the database. Improve tool result formatting to include "use this exact name" hints, and add few-shot examples to the system prompt.

---

## 5. Action Items

- [x] Review and revise system prompt (see `improved_prompt.txt`)
- [ ] Add few-shot examples for multi-step workflows
- [ ] Improve tool result formatting with explicit name hints
- [ ] Re-run evaluation pipeline after prompt changes

See `improved_prompt.txt` for the revised system prompt incorporating these fixes.
