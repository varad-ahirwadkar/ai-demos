from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
import json
from datetime import datetime
from typing import Any
import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Static reference date for demo consistency (April 21, 2024).
# All date calculations (e.g. days since delivery) are relative to this date
# so the demo produces consistent results regardless of when it is actually run.
DEMO_TODAY = datetime(2024, 4, 21)

# Database connection parameters from environment.
# Use host.containers.internal to reach a host-side PostgreSQL from a container,
# or localhost for a plain Python process on the same machine.
DB_HOST = os.getenv('DB_HOST', 'host.containers.internal')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'techmart')
DB_USER = os.getenv('DB_USER', 'llamastack')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'llamastack')

# Initialize FastMCP server
mcp = FastMCP(
    "TechMart Orders Server",
    host="0.0.0.0",
    port=int(os.getenv("PORT", "9001")),
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
        allowed_hosts=["*"],
        allowed_origins=["*"],
    )
)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db_connection():
    """Open and return a new PostgreSQL connection using RealDictCursor."""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        cursor_factory=RealDictCursor
    )


def load_orders() -> list[dict[str, Any]]:
    """
    Fetch all orders from PostgreSQL and return them as a list of plain dicts.
    Dates are serialised to ISO-8601 strings; price is cast to str to avoid
    Decimal serialisation issues downstream.
    """
    orders = []
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders ORDER BY order_date DESC")
        rows = cursor.fetchall()
        for row in rows:
            order = dict(row)
            if order.get('order_date'):
                order['order_date'] = order['order_date'].strftime('%Y-%m-%d')
            if order.get('delivery_date'):
                order['delivery_date'] = order['delivery_date'].strftime('%Y-%m-%d')
            if 'price' in order:
                order['price'] = str(order['price'])
            orders.append(order)
        cursor.close()
        conn.close()
        logger.info(f"Loaded {len(orders)} orders from database")
    except Exception as e:
        logger.error(f"Error loading orders from database: {e}")
    return orders


def _normalize_is_opened(value: Any) -> bool:
    """Normalize the is_opened DB value to a Python bool."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == 'yes'


def _normalize_status(value: str) -> tuple[str, str]:
    """
    Return (status_enum, status_display) from a raw DB status string.
    status_enum is uppercase with underscores for machine reasoning.
    status_display is the original human-readable form.
    """
    display = value or ""
    return display.upper().replace(" ", "_"), display


def _order_not_found(order_id: str) -> dict[str, Any]:
    """Return a structured error payload for a missing order."""
    return {
        "success": False,
        "error": "ORDER_NOT_FOUND",
        "message": f"Order {order_id} was not found. Please verify the order ID and try again.",
    }


# Load orders at startup
ORDERS = load_orders()


# ---------------------------------------------------------------------------
# MCP resource
# ---------------------------------------------------------------------------

@mcp.resource("orders://info")
def get_orders_resource() -> str:
    """Expose a summary of currently loaded orders as an MCP resource."""
    return json.dumps({
        "orders_count": len(ORDERS),
        "data_source": "PostgreSQL Database",
        "demo_date": DEMO_TODAY.strftime('%Y-%m-%d'),
        "sample_orders": [order['order_id'] for order in ORDERS[:5]],
    })


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------

@mcp.tool()
def reload_orders() -> dict[str, Any]:
    """
    ADMINISTRATIVE TOOL — Refresh the in-memory order cache from PostgreSQL.

    USE THIS TOOL when:
    - Asked to reload, refresh, or sync orders.
    - Data may have changed in the database since the server started.

    DO NOT USE THIS TOOL for:
    - Looking up order details (use get_order instead).
    - Checking return eligibility (use check_return_eligibility instead).
    - Any customer-facing request.

    Returns:
        success (bool): True if the reload completed without error.
        orders_count (int): Number of orders now loaded in memory.
        message (str): Human-readable status summary.
    """
    global ORDERS
    ORDERS = load_orders()
    return {
        "success": True,
        "message": f"Reloaded {len(ORDERS)} orders from database.",
        "orders_count": len(ORDERS),
    }


@mcp.tool()
def get_order(order_id: str) -> dict[str, Any]:
    """
    Look up a single order by its order ID and return its details.

    USE THIS TOOL when the customer asks about:
    - Order status or tracking: "Where is my order?", "What is the status of ORD-2024-001?"
    - Delivery information: "When was it delivered?", "Has it arrived?"
    - Product details: "What product did I buy?", "What did I order?"
    - Price or receipt: "How much did I pay?", "What was the cost?"

    DO NOT USE THIS TOOL for:
    - Return eligibility, refund amounts, or restocking fees
      (use check_return_eligibility instead, which calls this internally).
    - Listing all orders or reloading data.

    Args:
        order_id: The order ID to look up, e.g. "ORD-2024-001".

    Returns on success:
        success (True), order_id, customer_email, product_name, category,
        order_date, delivery_date, price (float), status, status_display,
        is_opened (bool).

    Returns on failure:
        success (False), error ("ORDER_NOT_FOUND"), message (str).
    """
    for order in ORDERS:
        if order['order_id'] == order_id:
            status_enum, status_display = _normalize_status(order['status'])
            return {
                "success": True,
                "order_id": order['order_id'],
                "customer_email": order['customer_email'],
                "product_name": order['product_name'],
                "category": order['category'],
                "order_date": order['order_date'],
                "delivery_date": order['delivery_date'],
                "price": float(order['price']),
                "status": status_enum,
                "status_display": status_display,
                "is_opened": _normalize_is_opened(order['is_opened']),
            }

    return _order_not_found(order_id)


@mcp.tool()
def check_return_eligibility(order_id: str) -> dict[str, Any]:
    """
    Check whether an order is eligible for return and calculate the refund.

    USE THIS TOOL when the customer asks about:
    - Returning an order: "Can I return ORD-2024-001?", "I want to return my order."
    - Refund amounts: "How much refund will I get?", "What will I be refunded?"
    - Return window: "Is my return window still open?", "How many days do I have left?"
    - Restocking fees: "What is the restocking fee?", "Will I be charged a fee?"
    - Eligibility: "Am I eligible for a return?", "Can I still return this?"

    DO NOT USE THIS TOOL for:
    - General order status or delivery information (use get_order instead).
    - Questions that do not involve returns or refunds.

    Args:
        order_id: The order ID to check, e.g. "ORD-2024-001".

    Returns on success:
        success (True), order_id (str)
        eligible (bool)              — True if the return window is still open.
        reason (str)                 — RETURN_WINDOW_OPEN | RETURN_WINDOW_EXPIRED.
        days_since_delivery (int)    — Days elapsed since delivery.
        return_window_days (int)     — Total return window for this category.
        days_remaining (int)         — Days left; negative means window expired.
        return_window_expired (bool) — True if the return window has passed.
        days_expired (int)           — How many days ago the window closed (0 if still open).
        restocking_fee_percent (int) — Fee percentage (0 if ineligible or unopened).
        restocking_fee_amount (float)— Fee in currency units (0 if ineligible).
        estimated_refund (float)     — Refund amount (0 if ineligible).
        order (dict)                 — Summary of the order (product_name, category, status, is_opened).
        message (str)                — Customer-friendly explanation.

    Returns on failure:
        success (False), error (ORDER_NOT_FOUND | INVALID_DELIVERY_DATE), message (str).
    """
    # Resolve the order — propagate structured errors immediately
    order = get_order(order_id)
    if not order["success"]:
        return order

    # Parse delivery date
    try:
        delivery_date = datetime.strptime(order['delivery_date'], '%Y-%m-%d')
    except ValueError:
        return {
            "success": False,
            "error": "INVALID_DELIVERY_DATE",
            "message": f"Order {order_id} has an unrecognised delivery date format.",
        }

    # Date arithmetic (all relative to the static demo date)
    today = DEMO_TODAY
    days_since_delivery = (today - delivery_date).days

    # Return window and restocking fee policy by category
    category = order['category'].lower()
    is_opened = order['is_opened']  # already a bool after get_order normalisation
    if 'electronics' in category:
        return_window_days = 15
        restocking_fee_percent = 15 if is_opened else 0
    else:
        return_window_days = 30
        restocking_fee_percent = 10 if is_opened else 0

    days_remaining = return_window_days - days_since_delivery
    eligible = days_remaining >= 0
    return_window_expired = not eligible
    days_expired = abs(days_remaining) if return_window_expired else 0

    price = float(order['price'])

    # Refund is only calculated when the return is actually eligible.
    # An ineligible order returns zero amounts to avoid misleading the customer.
    if eligible:
        restocking_fee_amount = round(price * restocking_fee_percent / 100, 2)
        estimated_refund = round(price - restocking_fee_amount, 2)
        reason = "RETURN_WINDOW_OPEN"

        if days_remaining == 0:
            message = (
                "This order is eligible for return. "
                "Today is the LAST DAY of the return window — it must be returned today."
            )
        elif days_remaining == 1:
            message = (
                "This order is eligible for return. "
                "1 day remaining — it must be returned by tomorrow."
            )
        else:
            message = (
                f"This order is eligible for return. "
                f"{days_remaining} days remaining in the {return_window_days}-day return window."
            )
        if restocking_fee_percent:
            message += (
                f" A {restocking_fee_percent}% restocking fee applies because the item was opened, "
                f"so the estimated refund is ${estimated_refund:.2f} (fee: ${restocking_fee_amount:.2f})."
            )
        else:
            message += f" Estimated refund: ${estimated_refund:.2f} (no restocking fee)."
    else:
        restocking_fee_amount = 0.0
        estimated_refund = 0.0
        reason = "RETURN_WINDOW_EXPIRED"
        message = (
            f"This order is NOT eligible for return. "
            f"The {return_window_days}-day return window expired {days_expired} day(s) ago."
        )

    return {
        "success": True,
        "order_id": order_id,
        # Structured fields for LLM reasoning
        "eligible": eligible,
        "reason": reason,
        "return_window_expired": return_window_expired,
        "days_expired": days_expired,
        # Temporal details
        "days_since_delivery": days_since_delivery,
        "return_window_days": return_window_days,
        "days_remaining": days_remaining,
        # Financial details (zero when ineligible)
        "restocking_fee_percent": restocking_fee_percent if eligible else 0,
        "restocking_fee_amount": restocking_fee_amount,
        "estimated_refund": estimated_refund,
        # Order summary — avoids requiring the LLM to call get_order separately
        "order": {
            "product_name": order["product_name"],
            "category": order["category"],
            "status": order["status"],
            "status_display": order["status_display"],
            "is_opened": order["is_opened"],
        },
        # Human-readable summary
        "message": message,
    }


def get_server_info() -> dict[str, Any]:
    """Return static metadata about this MCP server."""
    return {
        "name": "TechMart Orders Server",
        "version": "1.0.0",
        "description": "MCP server providing order lookup and return eligibility tools for TechMart customer service.",
        "port": 9001,
        "transport": "sse",
        "tools": ["reload_orders", "get_order", "check_return_eligibility"],
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", "9001"))
    logger.info("🚀 Orders MCP Server starting...")
    logger.info(f"📊 Loaded {len(ORDERS)} orders from PostgreSQL database")
    logger.info(f"🌐 Server will run on http://0.0.0.0:{port}")
    logger.info("🔧 Available tools: reload_orders, get_order, check_return_eligibility")
    mcp.run(transport="sse")
