import sys
import os
import asyncio
from langchain_ollama import ChatOllama
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

async def run_agent(query: str):
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

    model = ChatOllama(model="qwen2.5")

    agent = create_react_agent(model, tools)

    system_prompt = (
        "You are a Toyota dealer brand assistant. "
        "You have access to tools that retrieve real dealer data. "
        "You must only state facts that appear in the tool results. "
        "If the tool did not return a piece of information, say you "
        "don't have that information. Never infer, estimate, or "
        "generate details not present in the tool output. "
        "Known dealer IDs: 'toyota-metro-manila-01', "
        "'toyota-cebu-south-02'."
    )

    result = await agent.ainvoke({
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]
    })

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