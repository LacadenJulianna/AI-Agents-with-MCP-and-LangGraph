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

def _to_int(val) -> int:
    if isinstance(val, int):
        return val
    return int(str(val).strip())

VALID_DEALER_IDS = {"toyota-metro-manila-01", "toyota-cebu-south-02"}

def _validate_dealer_id(dealer_id: str) -> str | None:
    cleaned = _to_str(dealer_id).lower()
    if cleaned not in VALID_DEALER_IDS:
        return None
    return cleaned

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
    dealer_id = _validate_dealer_id(dealer_id)
    if not dealer_id:
        return {
            "error": f"Invalid dealer id '{dealer_id}'.",
            "available_dealer_ids": list(VALID_DEALER_IDS)
        }
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

@mcp.tool()
def get_promotions(dealer_id: str) -> dict:
    """
    Returns all active promotions for a specific dealer.
    Use this when the user asks about deals, discounts, promos,
    offers, interest rates, or special packages at a specific dealer.

    Args:
        dealer_id: The unique dealer identifier.
                   Known values: 'toyota-metro-manila-01',
                   'toyota-cebu-south-02'
    """
    dealer_id = _validate_dealer_id(dealer_id)
    if not dealer_id:
        return {
            "error": f"Invalid dealer id '{dealer_id}'.",
            "available_dealer_ids": list(VALID_DEALER_IDS)
        }
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
        "promotions": dealer["promotions"],
        "total_promotions": len(dealer["promotions"])
    }


@mcp.tool()
def get_reviews(dealer_id: str, limit: int = 5) -> dict:
    """
    Returns customer reviews for a specific dealer.
    Use this when the user asks about reputation, feedback,
    customer experience, ratings, or reviews at a specific dealer.

    Args:
        dealer_id: The unique dealer identifier.
                   Known values: 'toyota-metro-manila-01',
                   'toyota-cebu-south-02'
        limit: Number of reviews to return. Defaults to 5.
    """
    dealer_id = _validate_dealer_id(dealer_id)
    if not dealer_id:
        return {
            "error": f"Invalid dealer id '{dealer_id}'.",
            "available_dealer_ids": list(VALID_DEALER_IDS)
        }  
    limit = _to_int(limit)
    dealer = _get_dealer(dealer_id)

    if not dealer:
        return {
            "error": f"No dealer found with id '{dealer_id}'.",
            "available_dealer_ids": [
                d["dealer_id"] for d in DEALER_DATA["dealers"]
            ]
        }

    reviews = dealer["reviews"][:limit]
    avg_rating = round(
        sum(r["rating"] for r in reviews) / len(reviews), 2
    ) if reviews else 0

    return {
        "dealer_id": dealer["dealer_id"],
        "dealer_name": dealer["name"],
        "average_rating": avg_rating,
        "reviews_returned": len(reviews),
        "reviews": reviews
    }


@mcp.tool()
def get_dealer_profile(dealer_id: str) -> dict:
    """
    Returns the full profile of a specific dealer including
    name, location, contact info, operating hours, and unique
    selling points (USPs).
    Use this when the user asks who the dealer is, where they
    are located, how to contact them, or what makes them stand out.

    Args:
        dealer_id: The unique dealer identifier.
                   Known values: 'toyota-metro-manila-01',
                   'toyota-cebu-south-02'
    """
    dealer_id = _validate_dealer_id(dealer_id)
    if not dealer_id:
        return {
            "error": f"Invalid dealer id '{dealer_id}'.",
            "available_dealer_ids": list(VALID_DEALER_IDS)
        }
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
        "name": dealer["name"],
        "location": dealer["location"],
        "contact": dealer["contact"],
        "operating_hours": dealer["operating_hours"],
        "usps": dealer["usps"]
    }

@mcp.resource("dealer://{dealer_id}/profile")
def dealer_profile_resource(dealer_id: str) -> str:
    """
    Returns the full brand profile for a dealer as a structured
    text resource. Used when the agent needs to load dealer context
    before answering brand-related questions.
    """
    dealer_id = _validate_dealer_id(dealer_id)
    if dealer_id is None:
        return json.dumps({
            "error": "Invalid dealer_id.",
            "available_dealer_ids": list(VALID_DEALER_IDS)
        })

    dealer = _get_dealer(dealer_id)
    return json.dumps({
        "dealer_id": dealer["dealer_id"],
        "name": dealer["name"],
        "location": dealer["location"],
        "contact": dealer["contact"],
        "operating_hours": dealer["operating_hours"],
        "usps": dealer["usps"]
    }, indent=2)

if __name__ == "__main__":
    mcp.run(transport="stdio")