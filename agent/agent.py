import sys
import os
import asyncio
import json
from typing import TypedDict, Annotated
from langchain_ollama import ChatOllama
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

# --- State ---
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    dealer_id: str
    query_type: str  # "inventory" | "promotions" | "reviews" | "profile" | "comparison"

# --- System prompt ---
SYSTEM_PROMPT = (
    "You are a Toyota dealer brand assistant. "
    "You have access to tools that retrieve real dealer data. "
    "You must only state facts that appear in the tool results. "
    "If the tool did not return a piece of information, say you "
    "don't have that information. Never infer, estimate, or "
    "generate details not present in the tool output. "
    "Known dealer IDs: 'toyota-metro-manila-01', 'toyota-cebu-south-02'."
)

async def build_agent():
    client = MultiServerMCPClient(
        {
            "brand-knowledge": {
                "command": sys.executable,
                "args": [os.path.abspath("mcp_server/server.py")],
                "transport": "stdio",
                "env": {**os.environ, "PYTHONUNBUFFERED": "1"},
            }
        }
    )

    tools = await client.get_tools()
    model = ChatOllama(model="qwen2.5").bind_tools(tools)
    tool_node = ToolNode(tools)

    # --- Nodes ---
    async def call_model(state: AgentState) -> dict:
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
        response = await model.ainvoke(messages)
        return {"messages": [response]}

    def route_after_model(state: AgentState) -> str:
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return END

    # --- Graph ---
    graph = StateGraph(AgentState)
    graph.add_node("model", call_model)
    graph.add_node("tools", tool_node)

    graph.set_entry_point("model")
    graph.add_conditional_edges("model", route_after_model)
    graph.add_edge("tools", "model")

    return graph.compile()


async def run_agent(query: str):
    agent = await build_agent()

    initial_state: AgentState = {
        "messages": [HumanMessage(content=query)],
        "dealer_id": "",
        "query_type": ""
    }

    result = await agent.ainvoke(initial_state)

    final = result["messages"][-1].content
    print("\n=== Agent Response ===")
    print(final)
    return final


if __name__ == "__main__":
    test_queries = [
        "What vehicles does Toyota Metro Manila currently have in stock?",
        "What promotions are available at Toyota Cebu South right now?",
        "Which dealer has better customer reviews — Metro Manila or Cebu South?",
        "What makes Toyota Cebu South different from Toyota Metro Manila?",
    ]

    for query in test_queries:
        print(f"\n=== Query: {query} ===")
        asyncio.run(run_agent(query))
        print("-" * 60)