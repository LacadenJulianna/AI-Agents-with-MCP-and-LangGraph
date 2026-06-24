# MCP Integration Comparison: LangGraph vs CrewAI
**Brand Knowledge Agent (June 2026) vs Shopping Assistant MCP (June 11, 2026)**
**Author:** Julianna Lacaden
**Date:** June 24, 2026

---

## 1. Overview

This document compares two MCP-based agent projects built during the internship exploration period. Both projects use FastMCP (or raw MCP SDK) as the server layer, but differ in orchestration framework, model, transport, and what was ultimately accessible from the MCP server.

| | **Project 1: Shopping Assistant MCP** | **Project 2: Brand Knowledge Agent** |
|---|---|---|
| Date | June 11, 2026 | June 22–24, 2026 |
| MCP Server | FastMCP (Python) | Raw `mcp` SDK (Python) |
| Orchestration | CrewAI + MCPServerAdapter | LangGraph + langchain-mcp-adapters |
| Model | llama3.2 (Ollama) | qwen2.5 (Ollama) |
| Transport | Streamable HTTP (switched from stdio) | stdio (from the start) |
| Tools exposed | 4 (search, compare, check seller, reviews) | 4 (inventory, promotions, reviews, profile) |
| Resources exposed | ❌ Not accessible via MCPServerAdapter | ✅ Accessible via raw MCP SDK |
| Input validation | ❌ Not implemented | ✅ `_validate_dealer_id()` at tool boundary |
| Type coercion | ❌ Discovered mid-debug | ✅ Applied at build time |
| End-to-end result | Partial — tool discovery worked, compare_products failed | Full — all 4 queries passed, no hallucination |

---

## 2. MCP Server

### Project 1 — FastMCP
The Shopping Assistant used FastMCP to define four tools and one resource. FastMCP is a high-level wrapper around the `mcp` SDK that reduces boilerplate significantly — tools are defined as decorated Python functions.

```python
@mcp.tool()
def search_products(query: str) -> list:
    ...

@mcp.resource("catalog://{category}")
def catalog_resource(category: str) -> str:
    ...
```

**Finding:** FastMCP's ASCII banner and INFO logs print to stdout on startup. When spawned as a subprocess by a client adapter, this corrupts the JSON-RPC stream. The client reads stdout expecting pure protocol messages, fails to parse the banner, and closes the connection. This was the root cause of repeated `McpError: Connection closed` errors in the Brand Knowledge Agent and is why FastMCP was replaced with the raw SDK.

### Project 2 — Raw `mcp` SDK
The Brand Knowledge Agent switched to the raw `mcp` SDK after hitting the FastMCP stdout issue. Tools are defined by implementing `list_tools()` and `call_tool()` handlers directly — more verbose but fully transparent.

```python
server = Server("BrandKnowledgeAgent")

@server.list_tools()
async def list_tools():
    return [types.Tool(name="get_inventory", ...)]

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    ...
```

**Tradeoff:** More boilerplate, but zero unexpected stdout output. Reliable for subprocess stdio spawning. FastMCP remains appropriate for standalone servers tested via MCP Inspector.

---

## 3. Transport

### Project 1 — HTTP (forced switch)
The Shopping Assistant originally attempted stdio transport, which produced repeated "Connection closed" errors. After hours of debugging (raw MCP SDK, fastmcp version changes, mcpadapt reinstall), the fix was switching to **Streamable HTTP transport**. This resolved the connection issue but introduced network overhead and was environment-specific.

### Project 2 — stdio (from the start)
The Brand Knowledge Agent used stdio from the start, informed by the June 11 debugging session. The architecture document explicitly selected stdio over HTTP as a pre-build decision, not a mid-debug fallback.

However, the same `McpError: Connection closed` error appeared — not from transport mismatch this time, but from FastMCP's stdout contamination (Project 1's real lesson was different from what was initially documented). Once FastMCP was replaced with raw `mcp` SDK, stdio worked without modification.

**Key insight:** The June 11 fix (switching to HTTP) solved the symptom, not the cause. The actual cause was FastMCP's stdout contamination, which was only correctly diagnosed in Project 2. stdio is the correct transport choice — the workaround of switching to HTTP was unnecessary.

---

## 4. Orchestration Framework

### Project 1 — CrewAI + MCPServerAdapter

CrewAI uses `MCPServerAdapter` to wrap an MCP server and expose its tools to a CrewAI agent.

```python
from crewai_tools import MCPServerAdapter

with MCPServerAdapter(server_params) as mcp_tools:
    agent = Agent(tools=mcp_tools, ...)
```

**Critical limitation:** `MCPServerAdapter` only exposes **Tools**. Resources and Prompts defined on the MCP server are not surfaced. This means the `catalog://{category}` resource defined in Project 1's server was never accessible to the CrewAI agent, despite being correctly implemented and verified in MCP Inspector.

This is not a bug — it is a documented architectural constraint of the adapter. It means any MCP feature beyond Tools (Resources, Prompts) requires a different orchestration framework.

### Project 2 — LangGraph + langchain-mcp-adapters

LangGraph uses `MultiServerMCPClient` from `langchain-mcp-adapters` to connect to the MCP server and load tools via the raw MCP SDK's session layer. The agent is implemented as a real `StateGraph` — not the prebuilt `create_react_agent` wrapper — with explicit typed state, nodes, and conditional edges:

```python
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    dealer_id: str
    query_type: str

# Nodes
graph.add_node("call_model", call_model)
graph.add_node("tools", ToolNode(tools))

# Edges
graph.set_entry_point("call_model")
graph.add_conditional_edges("call_model", route_after_model)  # → tools or END
graph.add_edge("tools", "call_model")                         # loop-back
```

The conditional edge (`route_after_model`) checks whether the model produced tool calls. If yes, route to `tools`. If no, route to `END`. The `tools → call_model` loop-back allows multi-step reasoning — validated in Query 3 where the agent made two sequential `get_reviews` calls before generating a final comparison answer.

**Advantage over CrewAI:** Because `langchain-mcp-adapters` communicates directly with the MCP SDK session layer (not through a high-level adapter), it exposes Resources as well as Tools. The `dealer://{id}/profile` resource defined in the Brand Knowledge Agent's server is accessible — verified in MCP Inspector. Not accessible via CrewAI's `MCPServerAdapter`.

**Additional advantage:** LangGraph's explicit graph structure makes it significantly more suited to multi-step pipelines. Phase 2's monitoring logic — score a response, loop back if accuracy is below threshold — maps directly to the same conditional edge pattern used here, and was already prototyped in the June 18 research pipeline.

---

## 5. Model

### Project 1 — llama3.2

llama3.2 was the model used in the Shopping Assistant. Two tool-argument bugs were observed:

**Bug 1 — Array arguments sent as strings:**
`compare_products` expected `product_ids: list[int]` but received `"[1, 2]"` (a JSON-encoded string) instead of `[1, 2]`. The tool failed and the agent hallucinated a final recommendation.

**Bug 2 — Integer arguments sent as strings:**
Tools expecting `int` arguments received `"3"` instead of `3`, causing type errors.

These are not random failures — they are consistent behavior of llama3.2's function-calling implementation. Confirmed across multiple runs in Project 1 and a separate validation in the MCP + Genkit integration (June 19).

**Status:** Closed finding. llama3.2 is not suitable for MCP tool calling without extensive type coercion on every tool argument.

### Project 2 — qwen2.5

qwen2.5 was selected specifically because of the llama3.2 finding. It handles function calling correctly — arguments are passed with correct types and the model routes to the right tool based on docstring descriptions.

**Validation across 4 queries:**
- Correctly called `get_inventory` for inventory questions
- Correctly called `get_promotions` for promotion questions
- Correctly made two sequential `get_reviews` calls for a cross-dealer comparison
- Correctly called `get_dealer_profile` for both dealers in a differentiator comparison

No argument type errors were observed. Type coercion helpers (`_to_int`, `_to_str`) were still applied as a defensive measure but were not triggered during testing.

---

## 6. Input Validation

### Project 1 — None
No input validation was implemented in the Shopping Assistant. Invalid tool arguments were passed directly to the data layer. When llama3.2 sent malformed arguments, the error surfaced as an unhandled exception inside the tool function.

### Project 2 — Explicit validation at tool boundary
`_validate_dealer_id()` is called at the start of every tool handler, before any data lookup:

```python
def _validate_dealer_id(dealer_id: str):
    cleaned = _to_str(dealer_id).lower()
    if cleaned not in VALID_DEALER_IDS:
        return None
    return cleaned
```

If the dealer ID is invalid, the tool returns a structured error response with `available_dealer_ids` — allowing the model to self-correct on the next call rather than failing with an unhandled exception.

Additionally, the validator handles edge cases the model might realistically send:
- Uppercase input (`"TOYOTA-METRO-MANILA-01"`) → normalized by `.lower()`
- Whitespace-padded input (`"  toyota-cebu-south-02  "`) → normalized by `.strip()`

---

## 7. Type Coercion

### Project 1 — Discovered mid-debug
The array argument bug (`"[1,2]"` instead of `[1, 2]`) was discovered when `compare_products` failed mid-run. The finding was documented but the fix was not implemented in Project 1 because the root cause (llama3.2's function-calling behavior) was not yet identified at that point.

In the MCP + Genkit integration (June 19), type coercion helpers (`_to_int`, `_to_int_list`) were added to the MCP server as a fix after the same bug resurfaced.

### Project 2 — Applied at build time
Based on the June 11 and June 19 findings, type coercion helpers were written into the architecture document before any code was written:

```python
def _to_int(val) -> int:
    if isinstance(val, int):
        return val
    return int(str(val).strip())
```

This is the correct approach: a known, closed finding should become a standard build practice, not a bug to rediscover.

**Note:** `_to_int` was still accidentally omitted from the initial server file (found during `get_reviews` Inspector testing) — showing that "apply at build time" requires discipline, not just intent.

---

## 8. End-to-End Results

### Project 1 — Partial success
- Tool discovery: ✅ Agent found all 4 MCP tools
- `search_products`: ✅ Worked correctly
- `compare_products`: ❌ Failed — llama3.2 sent `product_ids` as `"[1,2]"` string instead of `[1, 2]` array
- Final recommendation: ❌ Hallucinated — agent invented a conclusion without valid tool output
- Resource access: ❌ `catalog://{category}` resource not accessible via MCPServerAdapter

### Project 2 — Full success
- Orchestration: ✅ Real `StateGraph` with typed `AgentState`, conditional edges, and loop-back — not a prebuilt wrapper
- Tool discovery: ✅ All 4 tools loaded via langchain-mcp-adapters
- Query 1 (inventory): ✅ Correct tool called, all 5 vehicles returned, no hallucination
- Query 2 (promotions): ✅ Correct tool called, all 3 promotions returned, no hallucination
- Query 3 (cross-dealer reviews): ✅ Two sequential tool calls via loop-back edge, correct averages computed, no hallucination
- Query 4 (cross-dealer profile): ✅ Both dealer profiles retrieved and compared accurately, no hallucination
- Resource access: ✅ `dealer://{id}/profile` resource verified in MCP Inspector

---

## 9. Summary of Lessons Applied

| Lesson from Project 1 | Application in Project 2 |
|---|---|
| llama3.2 sends typed arguments as strings | Switched to qwen2.5; added type coercion helpers at build time |
| stdio "Connection closed" misdiagnosed as transport issue | Correctly diagnosed as FastMCP stdout contamination; switched to raw `mcp` SDK |
| MCPServerAdapter exposes Tools only | Switched to LangGraph + langchain-mcp-adapters for Resource access |
| No input validation caused unhandled exceptions | `_validate_dealer_id()` applied at every tool boundary |
| All components wired together before individual validation | Sequential build: mock data → one tool → Inspector test → next tool |

---

## 10. Recommendation

For MCP-based agent projects in this stack:

- **Use raw `mcp` SDK for servers that will be spawned as subprocesses.** FastMCP is appropriate for Inspector-tested standalone servers only.
- **Use LangGraph over CrewAI** when MCP Resources or Prompts are needed, or when the pipeline requires conditional routing and loop-backs.
- **Use qwen2.5 over llama3.2** for any task involving MCP tool calling. llama3.2's function-calling behavior is a closed finding — it is not suitable without full type coercion coverage on every argument.
- **Apply type coercion helpers and input validation at file creation**, not after the first bug surfaces.
- **Use Python 3.11.** Python 3.14 is incompatible with `anyio`'s subprocess stdio handling used by `langchain-mcp-adapters`.