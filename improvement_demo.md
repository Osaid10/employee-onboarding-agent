# Improvement Demo — Part A (AI407L Final Exam)
## Issue Identification, Fix, and Before vs. After Results

---

## 1. Issue Identified

**Category:** Hallucination  
**Source:** Failed Query #2 from `analysis_report.md`  
**Query:** `"What is the company policy on remote work during onboarding?"`

### What Went Wrong

The agent was asked about a remote work policy that does **not exist** in the knowledge base. Instead of acknowledging the absence of information, the agent fabricated a confident-sounding policy:

> *"The company allows remote work during the first week of onboarding for employees in the engineering department. Other departments may have different policies..."*

This is a **hallucination** — the agent invented plausible-sounding content not grounded in any retrieved document. This is the most critical failure mode for an enterprise agent, as incorrect policy information can cause compliance issues.

### Root Cause

The original system prompt did not include an explicit instruction to refuse answering when retrieved documents do not contain the relevant information. The agent defaulted to using its general training knowledge instead.

**Original System Prompt (before fix) — excerpt:**

```
You are an AI-powered HR Onboarding Assistant. Your role is to help HR managers 
track employee onboarding progress, answer policy questions, and take appropriate 
actions. Use the available tools to retrieve information and take actions.
```

No instruction was given on what to do when no relevant information is found.

---

## 2. Fix Applied

**Fix type:** System prompt improvement

The following instruction was added to the system prompt in `src/agents/agents_config.py`:

```python
# ADDED to HR_COORDINATOR_SYSTEM_PROMPT
GROUNDING_RULE = """
IMPORTANT — Grounding Policy:
- Only answer policy questions using information retrieved from the knowledge base tools.
- If the knowledge base does not contain information about a topic, respond with:
  "I could not find this information in the company's policy documents. 
   Please contact HR directly for guidance on this topic."
- Do NOT use general knowledge or assumptions to fill in missing policy details.
- Do NOT invent, infer, or speculate about company policies under any circumstance.
"""
```

The full updated system prompt now reads:

```
You are an AI-powered HR Onboarding Assistant. Your role is to help HR managers 
track employee onboarding progress, answer policy questions, and take appropriate 
actions. Use the available tools to retrieve information and take actions.

IMPORTANT — Grounding Policy:
- Only answer policy questions using information retrieved from the knowledge base tools.
- If the knowledge base does not contain information about a topic, respond with:
  "I could not find this information in the company's policy documents. 
   Please contact HR directly for guidance on this topic."
- Do NOT use general knowledge or assumptions to fill in missing policy details.
- Do NOT invent, infer, or speculate about company policies under any circumstance.
```

---

## 3. Before vs. After Results

### Query Used
`"What is the company policy on remote work during onboarding?"`

---

### BEFORE (original system prompt — no grounding rule)

**Agent execution trace:**
```
[Agent] Received query: "What is the company policy on remote work during onboarding?"
[Tool Call] query_onboarding_policy(query="remote work policy during onboarding")
[Tool Result] No relevant documents found (similarity score below threshold)
[Agent] Generating response using general knowledge...
```

**Agent response:**
```
The company allows remote work during the first week of onboarding for employees 
in the engineering department. Other departments may have different policies 
depending on role requirements. New hires are expected to be on-site for mandatory 
orientation sessions. After the first two weeks, standard remote/hybrid policies 
apply based on your team's agreement with your manager.
```

**User feedback:** Thumbs down (-1)  
**Comment:** "This information isn't in our policies. The agent made it up."

**Problem:** The agent fabricated a complete policy that does not exist in any company document.

---

### AFTER (updated system prompt — grounding rule added)

**Agent execution trace:**
```
[Agent] Received query: "What is the company policy on remote work during onboarding?"
[Tool Call] query_onboarding_policy(query="remote work policy during onboarding")
[Tool Result] No relevant documents found (similarity score below threshold)
[Agent] No relevant documents found — applying grounding policy...
```

**Agent response:**
```
I could not find information about a remote work policy during onboarding in 
the company's policy documents. The knowledge base covers onboarding procedures, 
compliance requirements, benefits, and department-specific handbooks, but does 
not contain a dedicated remote work policy.

Please contact HR directly for guidance on this topic, or check if a remote 
work policy document has been added to the company's intranet.
```

**User feedback:** Thumbs up (+1)  
**Comment:** "Perfect — honest answer, and tells me what to do next."

---

## 4. Summary

| Aspect | Before | After |
|--------|--------|-------|
| Response source | General LLM knowledge (hallucinated) | Retrieved documents only |
| Accuracy | Incorrect — policy does not exist | Correct — honestly reports absence |
| User trust | Broken (false information stated as fact) | Maintained (transparent about limits) |
| Feedback score | -1 (thumbs down) | +1 (thumbs up) |
| Compliance risk | HIGH — wrong policy could mislead HR | NONE |

The fix demonstrates that **a single system prompt instruction** can eliminate hallucination on out-of-scope queries, transforming the agent from confidently wrong to transparently honest.

---

*AI407L Final Exam — Part A | Improvement Demo*
