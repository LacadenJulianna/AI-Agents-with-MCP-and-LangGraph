# Brand Knowledge Agent — Architecture Document
**Phase 1: Knowledge Feed Layer**
**Author:** Julianna Lacaden
**Date:** June 22, 2026 (Updated: June 24, 2026)
**Status:** Complete — Phase 1 implemented and validated

---

## Change Log

| Date | Change |
|---|---|
| June 22, 2026 | Initial architecture document drafted during unassigned period |
| June 24, 2026 | Updated to reflect actual implementation — MCP server framework changed from FastMCP to raw `mcp` SDK; LangGraph agent upgraded from `create_react_agent` to real `StateGraph`; build sequence outcomes documented; open questions updated |

---

## 1. Problem Statement

Car dealer clients are underrepresented or inaccurately represented in LLM-generated answers. When a user asks an LLM about a specific dealer — their inventory, promotions, or reputation — the model either hallucinates, falls back to generic information, or omits the dealer entirely.

The goal of this agent is to build a **structured, MCP-accessible knowledge layer** that feeds accurate, up-to-date dealer brand data to an LLM at query time, so responses about that dealer are grounded in real information.

This is Phase 1. Phase 2 (not scoped here) will build a monitoring agent on top of this layer to measure how accurately LLMs represent the brand *without* the knowledge feed — establishing a before/after baseline.

---

## 2. Architecture Overview

```
Dealer Brand Data (mock JSON)
        │
        ▼
  ┌─────────────────────────────────┐
  │         MCP Server              │  ← raw mcp SDK (Python), stdio transport
  │  Tools:                         │    (FastMCP replaced — see §7, Bug Log)
  │  - get_inventory                │
  │  - get_promotions               │
  │  - get_reviews                  │
  │  - get_dealer_profile           │
  │                                 │
  │  Resource:                      │
  │  - dealer://{id}/profile        │
  └───────────────┬─────────────────┘
                  │  stdio subprocess
                  ▼
  ┌─────────────────────────────────┐
  │      Orchestration Agent        │  ← LangGraph StateGraph (Python)
  │  Model: qwen2.5 (Ollama, local) │
  │                                 │
  │  Nodes:                         │
  │  - call_model                   │
  │  - tools (ToolNode)             │
  │                                 │
  │  Edges:                         │
  │  - START → call_model           │
  │  - call_model → tools (cond.)   │
  │  - call_model → END (cond.)     │
  │  - tools → call_model (loop)    │
  └───────────────┬─────────────────┘
                  │
                  ▼
  ┌─────────────────────────────────┐
  │        CLI Test Interface       │
  │  4 test queries, console output │
  └─────────────────────────────────┘

  - - - - - - - - - - - - - - - - - (Phase 2, not built here)
  ┌─────────────────────────────────┐
  │       Monitoring Agent          │  ← Queries multiple LLMs, scores brand
  │       (future)                  │     accuracy against MCP server as
  └─────────────────────────────────┘     ground truth
```

---

## 3. Scope

### In scope (Phase 1) — all completed
- MCP server with four tools and one resource exposing mock dealer data
- LangGraph `StateGraph` orchestration agent with typed state, conditional routing, and loop-back
- Type-coercion helpers on the MCP server side for model compatibility
- Input validation at every tool boundary
- Two-dealer mock dataset (Toyota Metro Manila, Toyota Cebu South)
- CLI test interface (four test queries, console output)
- Documentation of all architectural decisions, bugs, and findings

### Out of scope (Phase 1)
- Real dealer data integration (pending client onboarding)
- Phase 2 monitoring/scoring agent
- Frontend UI beyond CLI test harness
- Deployment or hosting

---

## 4. Technical Design

### 4.1 MCP Server

**Framework:** Raw `mcp` SDK (`mcp.server.Server` + `mcp.server.stdio.stdio_server`)
**Transport:** stdio

> **Note:** The original architecture plan specified FastMCP. FastMCP was replaced during implementation due to a critical incompatibility: FastMCP 3.4.2 prints a rich ASCII banner and INFO logs to stdout on startup. When spawned as a subprocess by `langchain-mcp-adapters`, the client reads stdout expecting pure JSON-RPC protocol messages. The banner corrupts the stream, causing `McpError: Connection closed` before the handshake completes. Raw `mcp` SDK produces no stdout output, resolving the issue completely. See §7 Bug Log, Bug 3.

stdio is selected over HTTP:
- HTTP introduced "Connection closed" errors in the June 11 CrewAI build (later determined to be a separate FastMCP stdout issue, but stdio remains the correct choice for subprocess spawning).
- `genkitx-mcp` SSE transport produced 400 errors against FastMCP's HTTP endpoint (June 19, 2026).

**Tools (four):**

| Tool | Input | Output |
|---|---|---|
| `get_inventory` | `dealer_id: str` | Vehicle listings with model, variant, year, price, colors, stock count |
| `get_promotions` | `dealer_id: str` | Active promotions with dates, applicable models, details |
| `get_reviews` | `dealer_id: str`, `limit: int = 5` | Customer reviews with computed average rating |
| `get_dealer_profile` | `dealer_id: str` | Name, location, contact, hours, USPs |

**Resource (one):**

```
dealer://{dealer_id}/profile
```

Returns full dealer profile as structured JSON. Verified accessible via raw MCP SDK + MCP Inspector. Not accessible via CrewAI's `MCPServerAdapter` (Tools only).

**Input validation:**

```python
VALID_DEALER_IDS = {"toyota-metro-manila-01", "toyota-cebu-south-02"}

def _validate_dealer_id(dealer_id: str):
    cleaned = _to_str(dealer_id).lower()
    if cleaned not in VALID_DEALER_IDS:
        return None
    return cleaned
```

Applied at the start of every tool handler before any data lookup. Invalid IDs return a structured error with `available_dealer_ids` so the model can self-correct.

**Type coercion helpers:**

```python
def _to_str(val) -> str:
    return str(val).strip()

def _to_int(val) -> int:
    if isinstance(val, int):
        return val
    return int(str(val).strip())
```

Applied defensively — qwen2.5 did not trigger these during testing, but they are retained as a guard against other models or edge-case inputs.

---

### 4.2 Orchestration Layer

**Framework:** LangGraph `StateGraph`
**Pattern:** ReAct (Reasoning + Acting) — explicit node and edge implementation
**Model:** qwen2.5 (via `ChatOllama`, Ollama local)
**MCP connection:** `MultiServerMCPClient` from `langchain-mcp-adapters` 0.3.0

> **Note:** The original architecture plan described a router_node → tool_call_node → response_node graph. The actual implementation uses LangGraph's `ToolNode` pattern, which is more idiomatic and handles multi-tool, multi-step reasoning automatically through the loop-back edge.

**Typed state:**

```python
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    dealer_id: str
    query_type: str
```

**Graph structure (actual implementation):**

```
[START]
   │
   ▼
[call_model] ──── model decides: tool call needed?
   │                       │
   │  yes (tool_calls)     │  no
   ▼                       ▼
[tools]                  [END]
   │
   └──── loop back to [call_model]
```

**Conditional edge:**

```python
def route_after_model(state: AgentState) -> str:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return END
```

The loop-back (`tools → call_model`) allows the agent to make multiple sequential tool calls before generating a final response — validated in Query 3 (cross-dealer review comparison), where the agent called `get_reviews` for both dealers before answering.

**Why LangGraph over CrewAI:**

| Consideration | LangGraph | CrewAI |
|---|---|---|
| MCP Resources | Accessible via raw MCP SDK | Blocked — `MCPServerAdapter` exposes Tools only |
| Conditional routing | First-class (`add_conditional_edges`) | Workaround via task chaining |
| Loop-back support | Built-in, explicit edge | Not native |
| Typed state | `TypedDict` + `Annotated` reducers | Not available |
| Phase 2 fit | Scoring node = conditional edge (pattern already validated June 18) | Requires full orchestration rebuild |

**System prompt (grounding instruction):**

```
You are a Toyota dealer brand assistant.
You have access to tools that retrieve real dealer data.
You must only state facts that appear in the tool results.
If the tool did not return a piece of information, say you
don't have that information. Never infer, estimate, or
generate details not present in the tool output.
Known dealer IDs: 'toyota-metro-manila-01', 'toyota-cebu-south-02'.
```

Validated across all four test queries — no hallucinated facts detected.

---

### 4.3 Mock Data

Two Toyota dealers, intentionally differentiated to force meaningful routing and comparison:

| | Toyota Metro Manila | Toyota Cebu South |
|---|---|---|
| `dealer_id` | `toyota-metro-manila-01` | `toyota-cebu-south-02` |
| Location | Quezon City, NCR | Cebu City, Visayas |
| Inventory | 5 models | 4 models |
| Promotions | Financing-focused | Process-focused |
| Hours | Mon–Sat | Mon–Sun incl. holidays |
| Avg. review rating | 4.4 | 4.2 |

Full schema: `mcp_server/mock_dealer_data.json`

**Note:** This is mock data. Real dealer data integration is a Phase 2 dependency.

---

## 5. Known Limitations and Risks

| Limitation | Status | Notes |
|---|---|---|
| Mock data only | Open | Real data integration is Phase 2 dependency |
| `MCPServerAdapter` exposes Tools only | Documented, mitigated | `get_dealer_profile` tool included as fallback; LangGraph chosen to avoid this constraint |
| qwen2.5 non-determinism on ambiguous inputs | Open | Observed June 18 (scores of 67 vs 20 on identical input). Not triggered in Phase 1 testing but relevant for Phase 2 scoring logic |
| FastMCP stdout contamination | Resolved | Replaced with raw `mcp` SDK |
| Python 3.14 incompatibility | Resolved | Venv recreated with Python 3.11 |
| `MultiServerMCPClient` context manager removed | Resolved | Client instantiated directly (langchain-mcp-adapters 0.1.0+ change) |

---

## 6. Build Sequence — Actual Outcomes

| Step | Planned | Outcome |
|---|---|---|
| 1. Mock data | JSON file, two dealers | ✅ Completed — `mock_dealer_data.json` |
| 2. `get_inventory` tool | Build and test in Inspector | ✅ Passed all 3 test cases (valid ×2, invalid ×1) |
| 3. Add remaining 3 tools | `get_promotions`, `get_reviews`, `get_dealer_profile` | ✅ Passed all 6 test cases — found missing `_to_int` helper during `get_reviews` test |
| 4. Input validation | `_validate_dealer_id()` at all tool boundaries | ✅ Handles uppercase and whitespace-padded inputs |
| 5. MCP Resource | `dealer://{id}/profile` | ✅ Verified in MCP Inspector Resources tab |
| 6. LangGraph agent | `StateGraph` with conditional routing | ✅ Upgraded from `create_react_agent` to real `StateGraph` |
| 7. End-to-end test | 4 queries, log results | ✅ All 4 passed, no hallucination detected |

---

## 7. Bug Log

### Bug 1 — `_to_int` not defined
**Discovered:** MCP Inspector test of `get_reviews`
**Fix:** Added `_to_int` helper to server file
**Lesson:** Apply all helpers at file creation

### Bug 2 — `MultiServerMCPClient` context manager removed
**Error:** `NotImplementedError` on `async with MultiServerMCPClient`
**Fix:** Removed `async with`, instantiated client directly
**Lesson:** Check adapter changelog before assuming API compatibility

### Bug 3 — FastMCP stdout banner corrupts JSON-RPC stream
**Error:** `McpError: Connection closed` on every agent run
**Root cause:** FastMCP 3.4.2 prints ASCII banner and INFO logs to stdout. Client reads stdout expecting pure JSON-RPC — banner corrupts stream, connection closes before handshake.
**Fix:** Replaced FastMCP with raw `mcp` SDK. No stdout output, clean handshake.
**Lesson:** FastMCP is suitable for Inspector-tested standalone servers. For subprocess stdio spawning via client adapters, use raw `mcp` SDK.

### Bug 4 — Python 3.14 asyncio incompatibility
**Error:** Same `Connection closed` error, different root cause
**Root cause:** Python 3.14.5 has asyncio changes conflicting with `anyio` 4.14.0 TaskGroup subprocess stdio handling
**Fix:** Recreated venv with Python 3.11. Error persisted (Bug 3 was primary cause), confirming Python version was a contributing factor but not the only one.
**Lesson:** Use Python 3.11 or 3.12 for LangGraph + MCP adapter projects.

### Bug 5 — `create_react_agent` deprecation
**Warning:** `LangGraphDeprecatedSinceV10: create_react_agent has been moved to langchain.agents`
**Attempted fix:** Updated import → `ModuleNotFoundError: No module named 'langchain'`
**Resolution:** Replaced `create_react_agent` entirely with a real `StateGraph` implementation — resolves the deprecation and produces a more architecturally sound result.

---

## 8. Test Results

| Query | Tool(s) Called | Result | Hallucination |
|---|---|---|---|
| What vehicles does Toyota Metro Manila have in stock? | `get_inventory("toyota-metro-manila-01")` | All 5 vehicles, correct variants and stock counts | None |
| What promotions are available at Toyota Cebu South? | `get_promotions("toyota-cebu-south-02")` | All 3 promotions, correct dates and details | None |
| Which dealer has better reviews? | `get_reviews("toyota-metro-manila-01")` + `get_reviews("toyota-cebu-south-02")` | Correct averages (4.4 vs 4.2), two sequential tool calls | None |
| What makes Cebu South different from Metro Manila? | `get_dealer_profile("toyota-cebu-south-02")` + `get_dealer_profile("toyota-metro-manila-01")` | All USPs correctly attributed to each dealer | None |

---

## 9. Open Questions — Updated

| Question | Status |
|---|---|
| Scope confirmation: knowledge feed first, monitoring second? | ⚠️ Not yet confirmed by supervisor — proceed with Phase 1 as working assumption |
| Real data timeline and format? | Open |
| Cloud vs local model preference? | Open |
| Deployment target? | Open |
| Multi-dealer requirement? | Resolved in Phase 1 — two dealers implemented |

---

## 10. Phase 2 Sketch

Phase 2 builds a monitoring agent on top of this architecture:

1. Take a dealer query
2. Send it to multiple LLMs **without** the MCP knowledge feed
3. Compare responses against the MCP server's ground truth
4. Score brand accuracy per LLM using a conditional edge (score → loop if below threshold)

Reuses:
- Same MCP server (Phase 1 output = ground truth)
- LangGraph conditional edges — same pattern as June 18 credibility-scoring pipeline
- `AgentState` — extend with `accuracy_score: float` and `loop_count: int`

**Blocked on:** real dealer data. Mock data is not sufficient for meaningful accuracy scoring.

---

## 11. Dependencies

```
mcp==1.28.0
fastmcp==2.3.3          # retained for MCP Inspector testing only
langgraph
langchain-ollama
langchain-mcp-adapters==0.3.0
```

**Python:** 3.11 required — 3.14 incompatible with anyio subprocess stdio
**Model:** qwen2.5 via Ollama (must be running locally)

---

*Last updated: June 24, 2026 — Phase 1 complete.*