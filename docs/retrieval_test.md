# RAG Retrieval Test Results

**Project**: Intelligent Employee Onboarding Agent
**Lab**: Lab 2 - RAG Pipeline & Vector Database
**Date**: 2026-05-05
**Vector Store**: ChromaDB (collection: `onboarding_knowledge`)
**Embedding Model**: Google `gemini-embedding-001` (768 dimensions, cosine similarity)
**Chunking Strategy**: Semantic header-based chunking — splits on `##` and `###` Markdown headers
to keep logically complete sections together (e.g., a full compliance clause or a full IT setup list).
**Knowledge Base Documents (8 total)**:
`onboarding_policy.md`, `compliance_guidelines.md`, `engineering_handbook.md`,
`benefits_guide.md`, `sales_handbook.md`, `hr_handbook.md`, `finance_handbook.md`,
`marketing_handbook.md`

---

## Test 1: General Policy Query (No Metadata Filter)

**Query**: "What forms does a new hire need to submit before their start date?"

**Filter**: None (full collection search, `k=3`)

**Expected Source**: `onboarding_policy.md` -- Pre-Boarding Checklist section

**Sample Retrieved Text**:

> **Chunk 1** (score: 0.87):
> "All new hires must complete the following forms prior to their official start date:
> 1. **I-9 Employment Eligibility Verification** -- Must be completed no later than the first day of employment. Failure to submit constitutes a federal compliance violation.
> 2. **W-4 Federal Tax Withholding Certificate** -- Required for payroll processing. State-specific withholding forms (e.g., IT-2104 for New York) may also be required.
> 3. **Non-Disclosure Agreement (NDA)** -- Standard company NDA covering proprietary information, trade secrets, and client data.
> 4. **Background Check Authorization** -- Consent form for third-party background screening via Checkr. Results typically take 3-5 business days.
> 5. **Direct Deposit Enrollment** -- Routing and account number for payroll deposit setup."
>
> *Source*: `onboarding_policy.md` | *Section*: Pre-Boarding Checklist | *Priority*: critical

> **Chunk 2** (score: 0.79):
> "The HR Coordinator must verify that all pre-boarding documents have been received at least 48 hours before the employee's start date. If any critical documents are missing, an escalation alert is generated and sent to the HR Manager. The onboarding status remains 'pre_boarding' until all mandatory forms are submitted and verified."
>
> *Source*: `onboarding_policy.md` | *Section*: Compliance Verification | *Priority*: critical

> **Chunk 3** (score: 0.72):
> "New hires will receive an automated welcome email 7 days before their start date containing links to the employee self-service portal where they can upload all required documents digitally. A reminder email is sent at the 3-day and 1-day marks if any forms remain incomplete."
>
> *Source*: `onboarding_policy.md` | *Section*: Automated Communications | *Priority*: standard

**Relevance Assessment**: **HIGH** -- The top-ranked chunk directly and comprehensively answers the question by listing all five required forms. The second chunk provides additional context about the verification timeline, and the third explains the digital submission workflow. All three chunks originate from the expected source document. The retrieval correctly prioritized the most specific answer over tangentially related content.

---

## Test 2: Department-Specific Query (Metadata Filter by Department)

**Query**: "What development tools does an engineer need to set up?"

**Filter**: `{"department": "engineering"}`

**Expected Source**: `engineering_handbook.md` -- Development Environment Setup section

**Sample Retrieved Text**:

> **Chunk 1** (score: 0.91):
> "**Development Environment Setup (Engineering)**
> All new engineering hires must configure the following tools within their first 3 days:
> 1. **Docker Desktop** (v4.25+) -- Required for running microservices locally. Install via IT self-service portal; license key provided by DevOps.
> 2. **Monorepo Access** -- Clone the primary monorepo from GitHub Enterprise. Ensure SSH keys are configured and 2FA is enabled on your GitHub account.
> 3. **IDE Configuration** -- VS Code is the recommended IDE. Install the company extension pack (`acme-eng-tools`) which includes linting rules, Prettier config, and internal API snippets.
> 4. **VPN & Cloud Access** -- Request AWS IAM credentials through the IT ticketing system. VPN client (Tailscale) is pre-configured on issued laptops.
> 5. **CI/CD Pipeline** -- Familiarize yourself with the GitHub Actions workflows in `.github/workflows/`. Run your first build within Day 2."
>
> *Source*: `engineering_handbook.md` | *Department*: engineering | *Priority*: standard

> **Chunk 2** (score: 0.84):
> "Engineering onboarding includes a mandatory 'Dev Environment Bootcamp' session on Day 2, led by a senior engineer from the new hire's assigned team. This session covers: monorepo structure walkthrough, local Docker Compose setup for the core services, running the test suite, and submitting a 'hello world' pull request to verify the full development pipeline is operational."
>
> *Source*: `engineering_handbook.md` | *Department*: engineering | *Priority*: standard

> **Chunk 3** (score: 0.76):
> "Engineers are expected to complete the security training module specific to source code handling within their first week. This includes: secure coding practices review, secrets management (HashiCorp Vault), dependency vulnerability scanning (Snyk integration), and code review protocols."
>
> *Source*: `engineering_handbook.md` | *Department*: engineering | *Priority*: critical

**Relevance Assessment**: **HIGH** -- The metadata filter successfully restricted retrieval to engineering-specific documents only, preventing contamination from general onboarding content or other department handbooks (e.g., marketing, finance). The top chunk directly lists the five core development tools with version requirements and setup instructions. Without the department filter, a general query about "tools to set up" would likely have returned mixed results including HR software tools or general IT equipment -- the filter eliminates this ambiguity entirely. This demonstrates the value of metadata-enriched chunking for department-specific retrieval.

---

## Test 3: Metadata Filtering by Priority Level (Benefits - Critical)

**Query**: "What is the deadline for health insurance enrollment?"

**Filter**: `{"priority_level": "critical"}`

**Expected Source**: `benefits_guide.md` -- Enrollment Deadlines section

**Sample Retrieved Text**:

> **Chunk 1** (score: 0.93):
> "**Health Insurance Enrollment Deadline**
> New employees have a **30-calendar-day enrollment window** starting from their official hire date to select a health insurance plan. This is a hard deadline mandated by the insurance carrier and cannot be extended.
> - **Plan Options**: PPO Standard ($185/mo employee contribution), PPO Premium ($245/mo), HSA-Compatible HDHP ($120/mo with $1,500 annual HSA employer contribution).
> - **Dependent Coverage**: Must be elected during the same 30-day window. Adding dependents after the window closes requires a Qualifying Life Event (QLE).
> - **Failure to Enroll**: Employees who miss the 30-day window will not have health coverage until the next Open Enrollment period (November annually). No exceptions."
>
> *Source*: `benefits_guide.md` | *Section*: Enrollment Deadlines | *Priority*: critical

> **Chunk 2** (score: 0.85):
> "In addition to health insurance, the following benefits must also be elected within the 30-day enrollment window: dental coverage (Delta Dental, $32/mo), vision coverage (VSP, $18/mo), and basic life insurance (1x salary, company-paid, opt-in for supplemental). The 401(k) retirement plan enrollment is separate and can be initiated at any time, though the company match (4% of salary) begins after 90 days of employment."
>
> *Source*: `benefits_guide.md` | *Section*: Additional Benefits | *Priority*: critical

> **Chunk 3** (score: 0.78):
> "HR must send a benefits enrollment reminder email at the following intervals: Day 1 (welcome packet), Day 14 (mid-window reminder), Day 25 (urgent final reminder). If an employee has not completed enrollment by Day 27, an escalation alert is sent to the HR Manager for personal follow-up. All enrollment actions are logged in the compliance tracking system."
>
> *Source*: `benefits_guide.md` | *Section*: Enrollment Compliance Tracking | *Priority*: critical

**Relevance Assessment**: **HIGH** -- The priority-level metadata filter effectively surfaced only chunks tagged as `critical`, ensuring the retrieval focused on legally and contractually binding information rather than general benefits overviews. The top chunk provides the exact deadline (30 calendar days), specific dollar amounts for plan options, and the consequences of missing the window -- all of which are the kind of precise, actionable details an onboarding agent must retrieve accurately. This test validates that the metadata enrichment strategy (tagging chunks with `priority_level`) enables the agent to distinguish between informational and compliance-critical content.

---

## Test 4: New Department Query — Finance (Metadata Filter by Department)

**Query**: "What are the SOX compliance requirements for Finance new hires?"

**Filter**: `{"department": "finance"}`

**Expected Source**: `finance_handbook.md` — SOX Compliance Requirements section

**Sample Retrieved Text**:

> **Chunk 1** (score: 0.94):
> "**SOX Compliance Requirements**
> All Finance department employees are subject to Sarbanes-Oxley (SOX) Act requirements:
> 1. Segregation of duties — No single employee may initiate, approve, and record a financial
> transaction.
> 2. Access controls — ERP access must be reviewed and re-certified quarterly.
> 3. Documentation — All journal entries above $10,000 must have supporting documentation in NetSuite.
> 4. Month-end close — Finance staff must complete assigned close tasks by the 3rd business day.
> 5. Audit readiness — Financial records must be retained for a minimum of 7 years."
>
> *Source*: `finance_handbook.md` | *Department*: finance | *Priority*: critical

> **Chunk 2** (score: 0.86):
> "Finance new hires must complete SOX Compliance & Internal Controls e-learning by Day 7, along
> with the Insider Trading & MNPI Policy training. Both are mandatory compliance modules."
>
> *Source*: `finance_handbook.md` | *Department*: finance | *Priority*: critical

**Relevance Assessment**: **HIGH** — The department metadata filter correctly returned only Finance-specific content, preventing irrelevant results from HR or Engineering handbooks. This demonstrates that the expanded 8-document knowledge base maintains retrieval precision even as the corpus grows. The filter is especially important for compliance queries where cross-department contamination could produce incorrect policy guidance.

---

## Summary of Retrieval Quality

| Test | Query Type | Filter Used | Top Score | Source Match | Assessment |
|------|-----------|-------------|-----------|--------------|------------|
| 1 | General policy | None | 0.87 | onboarding_policy.md | HIGH |
| 2 | Department-specific | `department: engineering` | 0.91 | engineering_handbook.md | HIGH |
| 3 | Priority-filtered | `priority_level: critical` | 0.93 | benefits_guide.md | HIGH |
| 4 | New dept (Finance) | `department: finance` | 0.94 | finance_handbook.md | HIGH |

**Key Observations**:
- Semantic header-based chunking keeps full policy sections intact (e.g., an entire SOX requirements list), producing higher-quality retrievals than fixed-size chunking that can split mid-clause.
- Metadata filtering consistently improves precision by narrowing the search space to the relevant department or priority level.
- The knowledge base scales cleanly from 5 to 8 documents without degrading retrieval quality — the cosine similarity scores remain high (0.87–0.94).
- No hallucination risk was observed — all retrieved chunks contain verifiable, source-attributed information grounded in the actual policy documents.
- **Embedding model note**: Google `gemini-embedding-001` produces 768-dimensional vectors stored in ChromaDB with cosine distance metric. This configuration was chosen for tight integration with the Gemini LLM used for the agent itself.
