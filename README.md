---
title: Cognee Precedent Compliance
emoji: 📋
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
tags:
  - cognee
  - agent-memory
  - procurement
  - compliance
  - knowledge-graph
  - openenv
---

# Cognee Precedent Compliance

**An AI procurement compliance reviewer that never forgets.** Built on [Cognee Cloud](https://platform.cognee.ai)'s hybrid graph-vector memory layer, this environment gives a compliance-review agent persistent, precedent-aware memory — so every new decision is informed by everything that came before it, not evaluated in isolation.

🔗 **Live demo:** [prathmesh1243-cognee-precedent-compliance.hf.space](https://prathmesh1243-cognee-precedent-compliance.hf.space)

Built for the [WeMakeDevs × Cognee "The Hangover Part AI" Hackathon](https://www.wemakedevs.org/hackathons/cognee).

---

## The Problem

Every call to an LLM is stateless by default. A compliance-review agent evaluating a purchase request has no memory of the vendor's history, no awareness of past violations by the same department, and no ability to notice patterns across requests. Every decision starts from zero — exactly like waking up with no memory of what happened yesterday.

In real procurement and compliance teams, this is a genuine, expensive problem. Repeat-offender vendors slip through because nobody cross-references six months of past decisions by hand. Institutional knowledge walks out the door when a reviewer leaves. Audit trails exist, but nothing *reasons* over them.

## The Solution

This project wraps a procurement compliance grading environment with Cognee's full memory lifecycle — **remember, recall, improve, forget** — so the agent reviewing a new request can draw on real precedent before making a decision, the same way an experienced human reviewer would.

```
New request comes in
        │
        ▼
  recall() policy + vendor/department history from Cognee
        │
        ▼
  Agent makes a decision, informed by precedent
        │
        ▼
  remember() the outcome back into Cognee
        │
        ▼
  Next request from the same vendor/department
  now recalls this decision as precedent
```

---

## Live Frontend

A working browser UI ships alongside the API, served directly from the same FastAPI app (`server/app.py` → `static/index.html`) — no separate frontend deployment or build step required.

**What it shows, end to end:**

- **Load Request** — pulls a procurement scenario (item, amount, budget, vendor status, policy notes) into a clean review card
- **Cognee Recall panel** — displays the live policy text and precedent history Cognee's `recall()` surfaces for that department/vendor, including a generated immediate-action checklist
- **Check Vendor Memory** — queries `/memory/vendor-history` directly, so you can see recalled precedent change *before* and *after* a decision is submitted
- **Submit Compliance Decision** — posts the reviewer's judgment to `/step`, which grades it and writes the outcome back into Cognee via `remember()`

This turns the "it remembers" behavior from a curl-command demo into something a judge can click through themselves in the browser.

---

## How Cognee Powers This

| Operation | What it does here |
|---|---|
| **`remember()`** | Ingests procurement policy documents and every past compliance decision (department, vendor status, item type, outcome) into Cognee's knowledge graph. |
| **`recall()`** | Before grading a new request, queries Cognee for (1) the relevant policy text and (2) prior decisions involving the same department/vendor — surfaced via Cognee's hybrid graph + vector search. |
| **`improve()`** | Re-derives graph relationships and enriches the memory as new decisions accumulate, so precedent gets sharper over time. |
| **`forget()`** | Prunes stale history datasets — modeling real data-retention requirements in enterprise compliance systems. |

All four operations run against **Cognee Cloud** (not a local/self-hosted instance), connected via `cognee.serve()` and the managed CloudClient API.

---

## Demo: The "It Remembers" Moment

1. A request from **Engineering**, vendor status **unapproved**, comes in. Cognee has no history — the agent evaluates it cold and denies it, routing to Security for vendor onboarding.
2. `remember()` stores that outcome.
3. A second request from the **same department and vendor status** comes in later. This time, `recall()` surfaces the first denial as precedent *before* the agent even sees the new request — informing the decision instead of starting from scratch.

This is the core behavior a stateless LLM call cannot replicate on its own. You can watch this happen live in the frontend by using **Check Vendor Memory** before and after submitting a decision.

---

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Serves the frontend UI |
| `/api` | GET | Service info |
| `/health` | GET | Health check |
| `/tasks` | GET | List all available task IDs |
| `/reset` | POST | Start a new review episode; recalls policy + precedent for the request |
| `/step` | POST | Submit a compliance decision; grades it and remembers the outcome |
| `/state` | GET | Current episode state |
| `/memory/vendor-history` | GET | Directly query recalled history for a department + vendor status |
| `/memory/improve` | POST | Trigger graph enrichment (memify) |
| `/memory/forget` | POST | Prune stale history data |

### Example: submitting a decision

```bash
curl -X POST https://prathmesh1243-cognee-precedent-compliance.hf.space/reset \
  -H "Content-Type: application/json" \
  -d '{"task_id": "easy_001"}'

curl -X POST https://prathmesh1243-cognee-precedent-compliance.hf.space/step \
  -H "Content-Type: application/json" \
  -d '{
    "policy_compliance": "compliant",
    "approval_decision": "approved",
    "risk_level": "low",
    "route_to": [],
    "missing_requirements": []
  }'

curl "https://prathmesh1243-cognee-precedent-compliance.hf.space/memory/vendor-history?department=Engineering&vendor_status=approved"
```

---

## Architecture

```
├── memory.py              # Cognee Cloud integration (remember/recall/improve/forget)
├── models.py              # Pydantic schemas for requests/observations/state
├── data/tasks.json        # Procurement request scenarios + expected grading output
├── server/
│   ├── app.py             # FastAPI routes, static frontend mount, and /memory/* endpoints
│   └── environment.py     # Core grading logic + Cognee recall/remember wiring
├── static/
│   └── index.html         # Frontend UI — request review, Cognee recall panel, decision form
├── Dockerfile              # HF Spaces / container deployment
└── .devcontainer/          # GitHub Codespaces configuration
```

The grading logic itself is a deterministic, weighted-partial-credit grader that scores five dimensions of a compliance decision (policy compliance, approval decision, risk level, routing, and missing requirements) against expected outputs, with difficulty-based scoring adjustments.

---

## Tech Stack

- **Cognee Cloud** — hybrid graph-vector memory layer (the core of this project)
- **FastAPI** — REST API server and frontend host
- **HTML/CSS/JS** — lightweight, dependency-free frontend served as a static file
- **Pydantic** — request/response schema validation
- **Docker** — containerized deployment on Hugging Face Spaces
- **GitHub Codespaces** — development environment

---

## Setup

Requires a free [Cognee Cloud](https://platform.cognee.ai) account.

```bash
pip install -r requirements.txt

export COGNEE_API_KEY="your_key_from_platform.cognee.ai"
export COGNEE_SERVICE_URL="your_tenant_url_from_the_api_keys_page"

uvicorn server.app:app --host 0.0.0.0 --port 7860
```

On startup, the server automatically seeds all policy notes from `data/tasks.json` into Cognee. Once running, open `http://localhost:7860` in a browser to use the frontend directly.

---

## Why This Matters Beyond the Hackathon

This pattern — precedent-aware decision-making backed by persistent memory — applies anywhere a stateless AI call currently makes isolated judgments that would benefit from institutional history: compliance review, customer support, audit trails, vendor risk management. Procurement compliance is the concrete example built here, but the underlying architecture generalizes to any workflow where "has this happened before?" is the question that actually matters.

---

### Proof — Live Recall in Production

A real response from the deployed Cognee Cloud API. On a second `/reset` call for the same department, Cognee's `recall()` automatically surfaced the outcome of an earlier decision as precedent — no hardcoded lookup, no manual logic:

> **"REQ-001 | Approved | Software | Approved (policy-compliant) | Low risk, risk score 0.90"**
> — recalled from Cognee's knowledge graph on a fresh `/reset` call, referencing a decision made in an earlier `/step`

This is the exact capability a stateless LLM call cannot replicate — the agent reasons with institutional memory instead of evaluating each request from zero.

## Acknowledgments

Built for the WeMakeDevs × Cognee hackathon. Thanks to the Cognee team for the memory API and Cognee Cloud infrastructure this project runs on.