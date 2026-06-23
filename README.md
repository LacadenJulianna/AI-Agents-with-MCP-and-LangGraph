# Brand Knowledge Agent — Architecture Document
**Phase 1: Knowledge Feed Layer**
**Author:** Julianna Lacaden
**Date:** June 22, 2026
**Status:** Planning — Pending supervisor confirmation of scope

---

## ⚠️ Working Assumption

This document was drafted proactively during an unassigned period. The scope assumes the company's directive — *"strengthen brand to feed to LLMs"* — maps to **Phase 1: a structured, LLM-queryable knowledge layer** for dealer brand data. This must be confirmed with the supervisor before development begins.

---

## 1. Problem Statement

Car dealer clients are underrepresented or inaccurately represented in LLM-generated answers. When a user asks an LLM about a specific dealer — their inventory, promotions, or reputation — the model either hallucinates, falls back to generic information, or omits the dealer entirely.

The goal of this agent is to build a **structured, MCP-accessible knowledge layer** that feeds accurate, up-to-date dealer brand data to an LLM at query time, so responses about that dealer are grounded in real information.

This is Phase 1. Phase 2 (not scoped here) will build a monitoring agent on top of this layer to measure how accurately LLMs represent the brand *without* the knowledge feed — establishing a before/after baseline.

---

## 2. Architecture Overview

```
Dealer Brand Data (mock)
        │
        ▼
  ┌─────────────────────────┐
  │      MCP Server         │  ← FastMCP (Python), stdio transport
  │  Tools:                 │
  │  - get_inventory        │
  │  - get_promotions       │
  │  - get_reviews          │
  │  - get_dealer_profile   │
  │                         │
  │  Resource:              │
  │  - dealer://{id}/profile│  ← requires raw MCP SDK (see §4.1)
  └───────────┬─────────────┘
              │  stdio
              ▼
  ┌─────────────────────────┐
  │  Orchestration Agent    │  ← LangGraph (Python)
  │  Model: qwen2.5 (Ollama)│
  │  Routing: conditional   │
  └───────────┬─────────────┘
              │
              ▼
  ┌─────────────────────────┐
  │    Test Interface       │  ← CLI or lightweight HTML
  │  "What inventory does   │
  │   Dealer X have?"       │
  └─────────────────────────┘

  - - - - - - - - - - - - - - - - (Phase 2, not built here)
  ┌─────────────────────────┐
  │  Monitoring Agent       │  ← Queries multiple LLMs, scores brand
  │  (future)               │     accuracy against MCP server as ground
  └─────────────────────────┘     truth
```

---

## 3. Scope

### In scope (Phase 1)
- MCP server with four tools and one resource exposing mock dealer data
- LangGraph orchestration agent that queries MCP tools to answer brand questions
- Type-coercion helpers on the MCP server side for model compatibility
- Mock dealer data schema (no real client data required in Phase 1)
- CLI test interface or simple HTML page
- Documentation of all architectural decisions and known limitations

### Out of scope (Phase 1)
- Real dealer data integration (pending client onboarding)
- Phase 2 monitoring/scoring agent
- Multi-dealer support (single mock dealer is sufficient for Phase 1 validation)
- Frontend UI beyond a minimal test interface
- Deployment or hosting

---

## 4. Technical Design

### 4.1 MCP Server

**Framework:** FastMCP (Python)
**Transport:** stdio

stdio is selected over HTTP for two reasons grounded in prior debugging:
- HTTP (Streamable HTTP) introduced "Connection closed" errors requiring hours of debugging in an earlier build (June 11, 2026).
- `genkitx-mcp` SSE transport produced 400 errors against FastMCP's HTTP endpoint (June 19, 2026).
stdio has been validated as stable across both CrewAI and Genkit integrations.

**Tools (four):**

| Tool | Input | Output | Notes |
|---|---|---|---|
| `get_inventory` | `dealer_id: str` | List of vehicle listings | Core tool, validated first |
| `get_promotions` | `dealer_id: str` | List of active promos | |
| `get_reviews` | `dealer_id: str, limit: int` | List of customer reviews | |
| `get_dealer_profile` | `dealer_id: str` | Dealer name, location, USPs | Duplicates resource content for Tools-only adapters |

**Resource (one):**

```
dealer://{id}/profile
```

Returns structured JSON with dealer name, location, contact info, and USPs.

> **Limitation note:** If the orchestration layer uses CrewAI's `MCPServerAdapter`, this resource will not be exposed — the adapter only surfaces Tools. The `get_dealer_profile` tool is included as a fallback so the resource content remains accessible regardless of the adapter used. If Resources are required, use raw MCP SDK instead of the adapter.

**Type coercion helpers (mandatory):**

qwen2.5 and other local models occasionally pass integer arguments as strings (e.g. `"3"` instead of `3`) and list arguments as comma-separated strings or JSON-encoded strings (e.g. `"[1,2]"` instead of `[1, 2]`). These helpers must be included in the MCP server from the start:

```python
def _to_int(val) -> int:
    if isinstance(val, int):
        return val
    return int(str(val).strip())

def _to_int_list(val) -> list[int]:
    if isinstance(val, list):
        return [int(v) for v in val]
    val = str(val).strip().strip("[]")
    return [int(v.strip()) for v in val.split(",") if v.strip()]
```

This pattern was validated on June 19, 2026. Do not defer this to debugging — apply it at build time.

---

### 4.2 Orchestration Layer

**Framework:** LangGraph (Python)

LangGraph is selected over CrewAI for the following reasons:

| Consideration | LangGraph | CrewAI |
|---|---|---|
| MCP Resources/Prompts | Accessible via raw MCP SDK | Blocked — `MCPServerAdapter` exposes Tools only |
| Conditional routing | First-class (conditional edges) | Workaround via task chaining |
| Loop-back support | Built-in (validated June 18) | Not native |
| Phase 2 fit | Credibility scoring = conditional edges (already prototyped) | Would require rebuilding orchestration layer |

LangGraph's conditional edges and loop-back patterns were validated in the June 18 multi-node research pipeline. Phase 2's monitoring agent (score → loop if accuracy below threshold) reuses the same pattern. Choosing CrewAI now means rebuilding the orchestration layer when Phase 2 is scoped.

**Model:** qwen2.5 (via Ollama, local)

qwen2.5 is selected over llama3.2. This is a closed finding from two independent validation sessions (June 11 CrewAI integration, June 19 Genkit integration): llama3.2 sends tool arguments as strings instead of typed values, breaking schema validation. qwen2.5 handles function calling correctly.

**Graph structure (Phase 1):**

```
[START]
   │
   ▼
[router_node] ─── decides which MCP tool to call based on query
   │
   ▼
[tool_call_node] ─── calls MCP server via stdio, gets result
   │
   ▼
[response_node] ─── formats LLM answer grounded in tool output
   │
   ▼
[END]
```

Phase 2 will insert a `[scoring_node]` with a conditional edge between `[response_node]` and `[END]` — the same pattern used in the June 18 credibility-scoring pipeline.

---

### 4.3 Mock Data Schema

Phase 1 does not require real client data. The following mock schema is sufficient to validate all four tools and the resource:

```json
{
  "dealer_id": "toyota-metro-01",
  "name": "Toyota Metro",
  "location": "Quezon City, Metro Manila",
  "contact": "+63 2 8123 4567",
  "usps": [
    "10-year powertrain warranty",
    "Same-day financing approval",
    "Free first year PMS"
  ],
  "inventory": [
    { "model": "Toyota Vios", "year": 2025, "price_php": 798000, "stock": 4 },
    { "model": "Toyota Fortuner", "year": 2025, "price_php": 1950000, "stock": 2 }
  ],
  "promotions": [
    { "title": "Zero interest June promo", "valid_until": "2026-06-30", "details": "0% interest for 24 months on Vios" }
  ],
  "reviews": [
    { "author": "Juan D.", "rating": 5, "text": "Fast processing and friendly staff." },
    { "author": "Maria S.", "rating": 4, "text": "Good experience but waiting area could be improved." }
  ]
}
```

Flag in any handoff: **this is mock data.** Real dealer data integration is a Phase 2 dependency, not a Phase 1 blocker.

---

### 4.4 Test Interface

A minimal CLI interface is sufficient for Phase 1 validation:

```bash
python test_agent.py --query "What promotions does Toyota Metro have this month?"
```

Optional: a simple HTML page (similar to the Genkit test page built June 16–17) that sends a query and displays the agent's response. This is not a deliverable — it's a test harness.

---

## 5. Known Limitations and Risks

| Limitation | Impact | Mitigation |
|---|---|---|
| Mock data only | Cannot validate against real dealer content | Flag clearly; Phase 2 requires real data |
| `MCPServerAdapter` exposes Tools only | Resource `dealer://{id}/profile` inaccessible via CrewAI adapter | `get_dealer_profile` tool included as fallback; raw MCP SDK as alternative |
| qwen2.5 inconsistency on ambiguous inputs | Observed in June 18 credibility scoring: same input produced scores of 67 and 20 on separate runs | Document as known limitation; do not build scoring logic on top of qwen2.5 without a deterministic fallback |
| Single-dealer scope | Phase 1 validates architecture, not scale | Multi-dealer support deferred to post-Phase-1 |
| Supervisor scope unconfirmed | This doc may be planning against the wrong target | Send scope confirmation question before development begins |

---

## 6. Build Sequence

This is the order in which to build, not a daily schedule. Each step must be validated before the next begins.

1. **Define and validate mock data** — JSON file, no code yet
2. **Build `get_inventory` tool only** — smallest working MCP tool, test with MCP Inspector
3. **Wire one LangGraph node to one MCP tool** — thin vertical slice proving the pipeline
4. **Add remaining three tools** — `get_promotions`, `get_reviews`, `get_dealer_profile`
5. **Add MCP Resource** (`dealer://{id}/profile`) — only if raw MCP SDK is used; skip if adapter is final choice
6. **Add router node** — conditional routing based on query type
7. **Add type coercion helpers** — do not skip; apply before any model testing
8. **End-to-end test** — three sample queries, log results
9. **Document findings** — bugs, model behavior, transport observations

---

## 7. Phase 2 Sketch (not scoped, for reference only)

Phase 2 builds a monitoring agent on top of this architecture. Its job: take the same dealer query, send it to multiple LLMs *without* the MCP knowledge feed, then compare their answers against the MCP server's ground truth and score accuracy.

This reuses:
- The same MCP server (Phase 1 output becomes the ground truth source)
- LangGraph conditional edges (scoring node → loop-back if score below threshold)
- The credibility-scoring pattern already validated June 18

Phase 2 is not blocked on Phase 1 being complete — it can be planned in parallel once Phase 1's architecture is confirmed. It is blocked on having a real answer to "what does accurate brand representation actually look like?" — which requires real dealer data.

---

## 8. Open Questions (requires supervisor input)

1. **Scope confirmation:** Is Phase 1 correct — build a knowledge feed first, monitoring second?
2. **Real data timeline:** When will actual dealer data be available, and in what format?
3. **Model preference:** Is there a company preference for cloud models (Gemini, OpenAI) over local Ollama for the orchestration layer?
4. **Deployment target:** Is this a local tool, a server-side service, or an API endpoint?
5. **Multi-dealer requirement:** Does Phase 1 need to handle more than one dealer, or is single-dealer sufficient for validation?

---

*This document is a living planning artifact. It should be updated after each supervisor sync and after each major build milestone.*