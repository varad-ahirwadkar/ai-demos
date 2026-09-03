from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
import json
from typing import Any
import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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


def get_server_info() -> dict[str, Any]:
    """Return static metadata about this MCP server."""
    return {
        "name": "TechMart Orders Server",
        "version": "1.0.0",
        "description": (
            "MCP server providing raw order data for TechMart customer service. "
            "Return eligibility and refund calculations are performed by the AI agent "
            "using retrieved policy documents from the knowledge base."
        ),
        "port": 9001,
        "transport": "sse",
        "tools": ["reload_orders", "get_order"],
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", "9001"))
    logger.info("🚀 Orders MCP Server starting...")
    logger.info(f"📊 Loaded {len(ORDERS)} orders from PostgreSQL database")
    logger.info(f"🌐 Server will run on http://0.0.0.0:{port}")
    logger.info("🔧 Available tools: reload_orders, get_order")
    mcp.run(transport="sse")
