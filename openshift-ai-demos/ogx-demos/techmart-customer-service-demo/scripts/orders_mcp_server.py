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
# All date calculations (e.g. days since delivery) in check_return_eligibility
# are relative to this date so the demo produces consistent results regardless
# of when it is actually run.
DEMO_TODAY = datetime(2024, 4, 21)

# Database connection parameters from environment.
# Use host.containers.internal to reach a host-side PostgreSQL from a container,
# or localhost for a plain Python process on the same machine.
DB_HOST = os.getenv('DB_HOST', 'host.containers.internal')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'techmart')
DB_USER = os.getenv('DB_USER', 'techmart')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'techmart123')
PORT = int(os.getenv("PORT", "9001"))

# Initialize FastMCP server
mcp = FastMCP(
    "TechMart Orders Server",
    host="0.0.0.0",
    port=PORT,
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


def _row_to_order(row: dict) -> dict[str, Any]:
    """Normalise a raw DB row dict to a plain serialisable order dict."""
    order = dict(row)
    if order.get('order_date'):
        order['order_date'] = order['order_date'].strftime('%Y-%m-%d')
    if order.get('delivery_date'):
        order['delivery_date'] = order['delivery_date'].strftime('%Y-%m-%d')
    if 'price' in order:
        order['price'] = str(order['price'])
    return order


def _fetch_all_orders() -> list[dict[str, Any]]:
    """Query all orders from PostgreSQL. Called on every request that needs them."""
    orders = []
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM orders ORDER BY order_date DESC")
                orders = [_row_to_order(dict(row)) for row in cursor.fetchall()]
        logger.info(f"Fetched {len(orders)} orders from database")
    except Exception as e:
        logger.error(f"Error fetching orders from database: {e}")
    return orders


def _fetch_order_by_id(order_id: str) -> dict[str, Any] | None:
    """Query a single order by order_id. Returns None if not found."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM orders WHERE order_id = %s",
                    (order_id,)
                )
                row = cursor.fetchone()
                return _row_to_order(dict(row)) if row else None
    except Exception as e:
        logger.error(f"Error fetching order {order_id} from database: {e}")
        return None


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


# ---------------------------------------------------------------------------
# MCP resource
# ---------------------------------------------------------------------------

@mcp.resource("orders://info")
def get_orders_resource() -> str:
    """Expose a live summary of orders as an MCP resource."""
    orders = _fetch_all_orders()
    return json.dumps({
        "orders_count": len(orders),
        "data_source": "PostgreSQL Database",
        "demo_date": DEMO_TODAY.strftime('%Y-%m-%d'),
        "sample_orders": [order['order_id'] for order in orders[:5]],
    })


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------

@mcp.tool()
def reload_orders() -> dict[str, Any]:
    """
    ADMINISTRATIVE TOOL — Verify database connectivity and return current order count.

    Orders are always read directly from PostgreSQL on every request, so there
    is no in-memory cache to refresh. This tool exists to let the AI confirm
    that the database is reachable and report how many orders are present.

    USE THIS TOOL when:
    - Asked to reload, refresh, or sync orders.
    - The user wants to confirm the database has the latest data.

    DO NOT USE THIS TOOL for:
    - Looking up order details (use get_order instead).
    - Any customer-facing request.

    Returns:
        success (bool): True if the database query completed without error.
        orders_count (int): Number of orders currently in the database.
        message (str): Human-readable status summary.
    """
    orders = _fetch_all_orders()
    success = len(orders) > 0
    return {
        "success": success,
        "message": f"Database is reachable. {len(orders)} orders available." if success else "No orders returned. Check database connectivity.",
        "orders_count": len(orders),
    }


@mcp.tool()
def get_order(order_id: str) -> dict[str, Any]:
    """
    Look up a single order by its order ID and return its raw details.

    This is a data-only tool. It returns factual order information from the
    database. Return eligibility, refund calculations, and policy application
    are performed by the AI agent using retrieved policy documents — not here.

    USE THIS TOOL when the customer asks about:
    - Order status or tracking: "Where is my order?", "What is the status of ORD-2024-001?"
    - Delivery information: "When was it delivered?", "Has it arrived?"
    - Product details: "What product did I buy?", "What did I order?"
    - Price or receipt: "How much did I pay?", "What was the cost?"
    - Return eligibility: "Can I return ORD-2024-001?" — fetch the order first,
      then apply the return policy retrieved from the knowledge base.

    Args:
        order_id: The order ID to look up, e.g. "ORD-2024-001".

    Returns on success:
        success (True), order_id, customer_email, product_name, category,
        order_date, delivery_date, price (float), status (enum), status_display,
        is_opened (bool).

    Returns on failure:
        success (False), error ("ORDER_NOT_FOUND"), message (str).
    """
    order = _fetch_order_by_id(order_id)
    if order is None:
        return _order_not_found(order_id)

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


if __name__ == "__main__":
    logger.info("🚀 Orders MCP Server starting...")
    logger.info(f"🌐 Server will run on http://0.0.0.0:{PORT}")
    logger.info("🔧 Available tools: reload_orders, get_order")
    mcp.run(transport="sse")
