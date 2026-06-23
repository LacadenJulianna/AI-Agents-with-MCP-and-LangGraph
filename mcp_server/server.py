import json
from pathlib import Path
from fastmcp import FastMCP

# --- Load mock data ---
DATA_PATH = Path(__file__).parent / "mock_dealer_data.json"
with open(DATA_PATH, "r", encoding="utf-8") as f:
    DEALER_DATA = json.load(f)

def _get_dealer(dealer_id: str) -> dict | None:
    for dealer in DEALER_DATA["dealers"]:
        if dealer["dealer_id"] == dealer_id:
            return dealer
    return None

# --- Type coercion helpers (apply now, not later) ---
def _to_str(val) -> str:
    return str(val).strip()

# --- MCP server ---
mcp = FastMCP("BrandKnowledgeAgent")

@mcp.tool()
def get_inventory(dealer_id: str) -> dict:
    """
    Returns the full vehicle inventory for a specific dealer.
    Use this when the user asks about available cars, stock,
    models, variants, prices, or colors at a specific dealer.
    
    Args:
        dealer_id: The unique dealer identifier.
                   Known values: 'toyota-metro-manila-01', 
                   'toyota-cebu-south-02'
    """
    dealer_id = _to_str(dealer_id)
    dealer = _get_dealer(dealer_id)

    if not dealer:
        return {
            "error": f"No dealer found with id '{dealer_id}'.",
            "available_dealer_ids": [
                d["dealer_id"] for d in DEALER_DATA["dealers"]
            ]
        }

    return {
        "dealer_id": dealer["dealer_id"],
        "dealer_name": dealer["name"],
        "location": dealer["location"],
        "inventory": dealer["inventory"],
        "total_models": len(dealer["inventory"])
    }

if __name__ == "__main__":
    mcp.run(transport="stdio")