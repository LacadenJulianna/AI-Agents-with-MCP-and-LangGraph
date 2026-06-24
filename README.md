# Brand Knowledge Agent
A standalone AI agent that exposes structured Toyota dealer brand data to an LLM via MCP (Model Context Protocol), grounding responses in verified dealer information rather than hallucinated or generic content.

Built during an internship exploration period at an AI product company focused on brand intelligence for LLM ingestion.

---

## What It Does

When a user asks a question about a Toyota dealer — inventory, promotions, reviews, or profile — the agent:

1. Routes the query to the appropriate MCP tool
2. Retrieves structured data from the MCP server
3. Returns a grounded, accurate response using only what the tool returned

No hallucination. No generic filler. Only verified dealer data.

---

## Architecture

```
Mock Dealer Data (JSON)
        │
        ▼
┌───────────────────────────┐
│        MCP Server         │  raw mcp SDK, stdio transport
│  - get_inventory          │
│  - get_promotions         │
│  - get_reviews            │
│  - get_dealer_profile     │
│  - dealer://{id}/profile  │  MCP Resource
└─────────────┬─────────────┘
              │ stdio subprocess
              ▼
┌───────────────────────────┐
│    LangGraph StateGraph   │  qwen2.5 via Ollama
│  - call_model node        │
│  - tools node (ToolNode)  │
│  - conditional routing    │
│  - loop-back edge         │
└───────────────────────────┘
```

### Why these choices

| Decision | Choice | Reason |
|---|---|---|
| MCP server framework | Raw `mcp` SDK | FastMCP's stdout banner corrupts JSON-RPC stream when spawned as subprocess |
| Transport | stdio | HTTP introduced connection errors in prior builds; stdio is stable for subprocess spawning |
| Orchestration | LangGraph `StateGraph` | Explicit nodes, conditional edges, loop-backs; CrewAI's `MCPServerAdapter` exposes Tools only |
| Model | qwen2.5 (Ollama) | llama3.2 sends typed tool arguments as strings, breaking schema validation — closed finding |
| Python version | 3.11 | Python 3.14 incompatible with `anyio` subprocess stdio handling |

---

## Project Structure

```
brand-knowledge-agent/
├── mcp_server/
│   ├── server.py                ← MCP server (4 tools + 1 resource)
│   └── mock_dealer_data.json    ← Two Toyota dealers (mock data)
├── agent/
│   └── agent.py                 ← LangGraph StateGraph agent
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Mock Data

Two Toyota dealers, intentionally differentiated to force meaningful routing:

| | Toyota Metro Manila | Toyota Cebu South |
|---|---|---|
| `dealer_id` | `toyota-metro-manila-01` | `toyota-cebu-south-02` |
| Location | Quezon City, NCR | Cebu City, Visayas |
| Inventory | 5 models | 4 models |
| Promotions | Financing-focused | Process-focused |
| Hours | Mon–Sat | Mon–Sun incl. holidays |
| Avg. review rating | 4.4 | 4.2 |

> This is mock data. Real dealer data integration is a Phase 2 dependency.

---

## Setup

**Requirements:**
- Python 3.11 (3.14 is incompatible — see Known Issues)
- [Ollama](https://ollama.com) running locally with `qwen2.5` pulled

**Install Ollama model:**
```bash
ollama pull qwen2.5
```

**Clone and set up the project:**
```bash
git clone https://github.com/LacadenJulianna/AI-Agents-with-MCP-and-LangGraph.git
cd AI-Agents-with-MCP-and-LangGraph

py -3.11 -m venv venv
source venv/Scripts/activate   # Git Bash
# or
venv\Scripts\activate          # cmd

pip install -r requirements.txt
```

---

## Running the Agent

```bash
python agent/agent.py
```

The agent runs four test queries automatically and prints results to console. The MCP server is spawned as a subprocess — you do not run it separately.

**Sample output:**
```
=== Query: What vehicles does Toyota Metro Manila currently have in stock? ===

=== Agent Response ===
Toyota Metro Manila currently has the following vehicles in stock:
- Toyota Vios (1.3 XLE CVT, 2025): PHP 798,000 — 4 units in stock
- Toyota Fortuner (2.4 G Diesel 4x2 AT, 2025): PHP 1,950,000 — 2 units in stock
...
```

---

## Testing the MCP Server (MCP Inspector)

To test individual tools without the agent, use MCP Inspector:

```cmd
npx @modelcontextprotocol/inspector python mcp_server/server.py
```

> Run this from **cmd**, not Git Bash — the Inspector's npx script does not resolve correctly in Git Bash on Windows.

Test cases to run:
- `get_inventory` with `toyota-metro-manila-01` → 5 vehicles
- `get_inventory` with `toyota-cebu-south-02` → 4 vehicles
- `get_inventory` with `fake-dealer-99` → clean error with available IDs
- `get_reviews` with `limit: 3` → 3 reviews with average rating
- Resources tab → `List Templates` → `dealer://{dealer_id}/profile`

---

## Dependencies

```
mcp==1.28.0
fastmcp==2.3.3
langgraph
langchain-ollama
langchain-mcp-adapters==0.3.0
```

---

## Known Issues

| Issue | Status | Notes |
|---|---|---|
| Python 3.14 incompatible | Confirmed | `anyio` 4.14.0 TaskGroup subprocess stdio fails on Python 3.14. Use Python 3.11. |
| FastMCP stdout corrupts stdio | Confirmed | FastMCP 3.x banner prints to stdout, breaking JSON-RPC handshake. Raw `mcp` SDK used instead. |
| `create_react_agent` deprecation warning | Cosmetic | Deprecated in LangGraph V1.0, not removed until V2.0. Resolved by upgrading to real `StateGraph`. |
| Git Bash heredoc syntax | Confirmed | `cat > file << 'EOF'` writes the command itself into the file on Git Bash/Windows. Use VS Code to create files instead. |

---

## Phase 2 (Planned)

Phase 2 will add a monitoring agent that:
1. Sends dealer queries to multiple LLMs **without** the MCP knowledge feed
2. Compares responses against the MCP server as ground truth
3. Scores brand accuracy per LLM using a conditional edge and loop-back

This reuses the same MCP server (Phase 1 output = ground truth) and the same LangGraph conditional edge pattern. Blocked on real dealer data availability.

---

## Documentation

| File | Description |
|---|---|
| `brand-knowledge-agent-architecture.md` | Architecture document — planning decisions, build sequence, bug log, test results |
| `brand-knowledge-agent-project-doc.md` | Full project documentation from problem statement to implementation |
| `mcp-langgraph-vs-crewai-comparison.md` | Comparison with the June 11 CrewAI + MCP Shopping Assistant project |

---

## Author

Julianna Lacaden — CS Intern, June 2026