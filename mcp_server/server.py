import logging
import sys
import json
import asyncio
from pathlib import Path
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

logging.basicConfig(stream=sys.stderr, level=logging.WARNING)

# --- Load mock data ---
DATA_PATH = Path(__file__).parent / "mock_dealer_data.json"
with open(DATA_PATH, "r", encoding="utf-8") as f:
    DEALER_DATA = json.load(f)

VALID_DEALER_IDS = {"toyota-metro-manila-01", "toyota-cebu-south-02"}

# --- Helpers ---
def _to_str(val) -> str:
    return str(val).strip()

def _to_int(val) -> int:
    if isinstance(val, int):
        return val
    return int(str(val).strip())

def _validate_dealer_id(dealer_id: str):
    cleaned = _to_str(dealer_id).lower()
    if cleaned not in VALID_DEALER_IDS:
        return None
    return cleaned

def _get_dealer(dealer_id: str):
    for dealer in DEALER_DATA["dealers"]:
        if dealer["dealer_id"] == dealer_id:
            return dealer
    return None

# --- MCP Server ---
server = Server("BrandKnowledgeAgent")

@server.list_tools()
async def list_tools():
    return [
        types.Tool(
            name="get_inventory",
            description=(
                "Returns the full vehicle inventory for a specific dealer. "
                "Use when the user asks about available cars, stock, models, "
                "variants, prices, or colors at a specific dealer. "
                "Known dealer IDs: 'toyota-metro-manila-01', 'toyota-cebu-south-02'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "dealer_id": {"type": "string"}
                },
                "required": ["dealer_id"]
            }
        ),
        types.Tool(
            name="get_promotions",
            description=(
                "Returns all active promotions for a specific dealer. "
                "Use when the user asks about deals, discounts, promos, offers, "
                "interest rates, or special packages at a specific dealer. "
                "Known dealer IDs: 'toyota-metro-manila-01', 'toyota-cebu-south-02'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "dealer_id": {"type": "string"}
                },
                "required": ["dealer_id"]
            }
        ),
        types.Tool(
            name="get_reviews",
            description=(
                "Returns customer reviews for a specific dealer. "
                "Use when the user asks about reputation, feedback, customer "
                "experience, ratings, or reviews at a specific dealer. "
                "Known dealer IDs: 'toyota-metro-manila-01', 'toyota-cebu-south-02'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "dealer_id": {"type": "string"},
                    "limit": {
                        "type": "integer",
                        "description": "Number of reviews to return. Defaults to 5."
                    }
                },
                "required": ["dealer_id"]
            }
        ),
        types.Tool(
            name="get_dealer_profile",
            description=(
                "Returns the full profile of a specific dealer including name, "
                "location, contact info, operating hours, and unique selling points. "
                "Use when the user asks who the dealer is, where they are located, "
                "how to contact them, or what makes them stand out. "
                "Known dealer IDs: 'toyota-metro-manila-01', 'toyota-cebu-south-02'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "dealer_id": {"type": "string"}
                },
                "required": ["dealer_id"]
            }
        ),
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    dealer_id = _validate_dealer_id(arguments.get("dealer_id", ""))

    if dealer_id is None:
        result = {
            "error": "Invalid dealer_id. Must be one of the known dealer IDs.",
            "available_dealer_ids": list(VALID_DEALER_IDS)
        }
        return [types.TextContent(type="text", text=json.dumps(result))]

    dealer = _get_dealer(dealer_id)

    if name == "get_inventory":
        result = {
            "dealer_id": dealer["dealer_id"],
            "dealer_name": dealer["name"],
            "location": dealer["location"],
            "inventory": dealer["inventory"],
            "total_models": len(dealer["inventory"])
        }
    elif name == "get_promotions":
        result = {
            "dealer_id": dealer["dealer_id"],
            "dealer_name": dealer["name"],
            "promotions": dealer["promotions"],
            "total_promotions": len(dealer["promotions"])
        }
    elif name == "get_reviews":
        limit = _to_int(arguments.get("limit", 5))
        reviews = dealer["reviews"][:limit]
        avg_rating = round(
            sum(r["rating"] for r in reviews) / len(reviews), 2
        ) if reviews else 0
        result = {
            "dealer_id": dealer["dealer_id"],
            "dealer_name": dealer["name"],
            "average_rating": avg_rating,
            "reviews_returned": len(reviews),
            "reviews": reviews
        }
    elif name == "get_dealer_profile":
        result = {
            "dealer_id": dealer["dealer_id"],
            "name": dealer["name"],
            "location": dealer["location"],
            "contact": dealer["contact"],
            "operating_hours": dealer["operating_hours"],
            "usps": dealer["usps"]
        }
    else:
        result = {"error": f"Unknown tool: {name}"}

    return [types.TextContent(type="text", text=json.dumps(result))]

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())