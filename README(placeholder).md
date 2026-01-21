# Table Tennis AI Coach — Architecture & Integration Plan

## 1. Purpose of This Project

This project is part of a long-term learning and system-building journey to create a local-first, AI-powered **Table Tennis Coach**.

The goal is **not** to build one monolithic “AI app” immediately, but to:

- Learn core AI patterns properly  
- Keep systems testable and reusable  
- Build production-grade mental models (services, orchestration, interfaces)

This repository focuses on **semantic search**, but it exists within a broader system that includes:

- Search  
- Recommendations (multi-armed bandit)  
- Notifications  
- Chat as an interface (not a brain)

---

## 2. Core Mental Model (Most Important)

**Chat is NOT the system.  
Chat is only an interface.**

The system is composed of **capabilities (services)** that can be called by:

- Chat  
- UI pages  
- Scheduled jobs  
- APIs  

### High-level model

```
UI Layer
├─ Search Page
├─ Chat Page
├─ Notification Settings
└─ History / Progress

Service Layer (Capabilities)
├─ Semantic Search
├─ Recommendation / Bandit
├─ Notification Engine
└─ (Future) Supervised Models / CV

Data Layer
├─ Drill metadata
├─ User history
├─ Rewards / feedback
└─ Logs
```

Each capability:
- Can exist independently
- Can be tested without chat
- Can later be composed into one app

---

## 3. What Exists Today

### A. Recommendation / Bandit (existing repo)

Purpose:
- Decide **what drill / tip / action** to recommend
- Learn from user feedback over time

Characteristics:
- Contextual multi-armed bandit
- Local-first
- Small-data friendly
- Explainable (“why this was chosen”)

This repo **should not be rewritten**.  
It will be **reused**.

---

### B. Notifications (existing repo)

Purpose:
- Decide **when** and **what type** of notification to send
- Deliver output to the user

Characteristics:
- Scheduling + channel logic
- Uses bandit outputs
- Chat may configure it, but does not own it

---

### C. Semantic Search (this repo)

Purpose:
- Retrieve relevant drills / content based on intent
- Power both:
  - classic search UI
  - chat-based “find me …” queries

Search is a **capability**, not a UI.

This repo exists so search can be:
- Tested independently
- Used without any LLM
- Reused by multiple interfaces



---

## 4. Why Search Is Separate from Chat

Search must work in **all of these scenarios**:

1. User types into a search bar  
2. Chat says: “Find drills for backhand topspin”  
3. Recommendation system needs candidates to choose from  
4. Offline evaluation / testing  

Therefore:

- Search logic must **not live inside chat**
- Chat only **calls** search

This is intentional and non-negotiable.

---

## 5. How Chat Fits In (Now and Later)

Chat is an **orchestrator**.

It does NOT:
- store data
- rank results
- decide recommendations
- learn user preferences

It DOES:
- parse user intent
- call the right capability
- present results in natural language

### Example flow

```
User: “What should I practice today?”

Chat:
→ calls bandit.select(context)
→ bandit returns drill + reason
→ chat explains it

User: “Find similar drills”

Chat:
→ calls search.search(query)
→ returns ranked results
```

Chat is replaceable.  
The system is not.

---

## 6. Repository Strategy (Now vs Later)

### Current phase (learning-first)

Separate repos:

- table-tennis-multi-armed-bandit  
- tt-bandit-notifications  
- tt-semantic-search (this repo)

Benefits:
- Clear mental boundaries
- Easier debugging
- No premature abstraction
- Faster learning

---

### Later phase (integration)

Create a **shell / integration repo**:

- tt-coach-app

Responsibilities:
- UI
- Chat
- Orchestration
- Dependency wiring

This repo **imports or calls** the others.  
It does not duplicate logic.

---

## 7. Reusing the Existing Bandit Repo

There are two supported reuse paths.

### Option A — Python package import (recommended for now)

- Treat bandit repo as a library
- Import functions directly

Best for:
- Local-first
- Fast iteration
- Learning focus

---

### Option B — Local API services (later)

- Run bandit + search as FastAPI services
- Chat/UI calls them via HTTP

Best for:
- Production realism

Not required at this stage.

---

## 8. Near-Term Execution Plan

### Phase 1 — Semantic Search (this repo)

Goal:
- A single, clean function:

```python
search(query: str, top_k: int) -> list[SearchResult]
```

Characteristics:
- No chat dependency
- No bandit dependency
- CLI-testable

---

### Phase 2 — Minimal Chat Shell

Goal:
- Prove orchestration works

Chat can:
- Call search
- Call bandit
- Explain outputs

No UI polish required.

---

### Phase 3 — Integration App

Goal:
- One coherent local app

Includes:
- Search page
- Chat page
- Notification settings
- History

---

## 9. Guiding Principles

1. Capabilities > Interfaces  
2. Decision logic ≠ presentation  
3. Local-first by default  
4. Small data is a feature, not a bug  
5. Never merge systems just to “feel complete”

---

## 10. One-Sentence Summary

Search, bandit, and notifications are **capabilities**.  
Chat is an **interface**.  
Capabilities live independently and are composed later.
