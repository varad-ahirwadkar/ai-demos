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

# Static reference date for demo consistency (April 21, 2024)
# This ensures the demo works regardless of when it's run
DEMO_TODAY = datetime(2024, 4, 21)

# Database connection parameters from environment
# Use host.containers.internal for containers to reach host PostgreSQL
# Use localhost for local Python execution
DB_HOST = os.getenv('DB_HOST', 'host.containers.internal')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'techmart')
DB_USER = os.getenv('DB_USER', 'llamastack')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'llamastack')

# Initialize FastMCP server
mcp = FastMCP(
    "TechMart Orders Server",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
        allowed_hosts=["*"],
        allowed_origins=["*"],
    )
)

def get_db_connection():
    """Get database connection"""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        cursor_factory=RealDictCursor
    )

def load_orders() -> list[dict[str, Any]]:
    """Load orders from PostgreSQL database"""
    orders = []
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders ORDER BY order_date DESC")
        rows = cursor.fetchall()
        for row in rows:
            # Convert RealDictRow to regular dict and format dates as strings
            order = dict(row)
            if 'order_date' in order and order['order_date']:
                order['order_date'] = order['order_date'].strftime('%Y-%m-%d')
            if 'delivery_date' in order and order['delivery_date']:
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

# Load orders at startup
ORDERS = load_orders()

@mcp.tool()
def reload_orders() -> dict[str, Any]:
    """
    Reload orders from the database without restarting the server
    
    Returns:
        Status message with count of loaded orders
    """
    global ORDERS
    ORDERS = load_orders()
    return {
        "success": True,
        "message": f"Reloaded {len(ORDERS)} orders from database",
        "orders_count": len(ORDERS)
    }

@mcp.resource("orders://info")
def get_orders_resource() -> str:
    """Get information about currently loaded orders as an MCP resource"""
    return json.dumps({
        "orders_count": len(ORDERS),
        "data_source": "PostgreSQL Database",
        "demo_date": DEMO_TODAY.strftime('%Y-%m-%d'),
        "sample_orders": [order['order_id'] for order in ORDERS[:5]]
    })


@mcp.tool()
def get_order(order_id: str) -> dict[str, Any]:
    """
    Get order details by order ID
    
    Args:
        order_id: The order ID to look up (e.g., "ORD-2024-001")
    
    Returns:
        Order details including product, price, dates, and status
    """
    for order in ORDERS:
        if order['order_id'] == order_id:
            return {
                "order_id": order['order_id'],
                "customer_email": order['customer_email'],
                "product_name": order['product_name'],
                "category": order['category'],
                "order_date": order['order_date'],
                "delivery_date": order['delivery_date'],
                "price": float(order['price']),
                "status": order['status'],
                "is_opened": order['is_opened']
            }
    
    return {"error": f"Order {order_id} not found"}

@mcp.tool()
def check_return_eligibility(order_id: str) -> dict[str, Any]:
    """
    Check if an order is eligible for return and calculate refund
    
    Args:
        order_id: The order ID to check (e.g., "ORD-2024-001")
    
    Returns:
        Eligibility status, days remaining, restocking fee, and estimated refund
    """
    # Get order details
    order = get_order(order_id)
    if "error" in order:
        return order
    
    # Parse delivery date
    try:
        delivery_date = datetime.strptime(order['delivery_date'], '%Y-%m-%d')
    except ValueError:
        return {"error": "Invalid delivery date format"}
    
    # Calculate days since delivery using static demo date
    today = DEMO_TODAY
    days_since_delivery = (today - delivery_date).days
    
    # Determine return window based on category
    category = order['category'].lower()
    if 'electronics' in category:
        return_window_days = 15
        restocking_fee_percent = 15 if order['is_opened'] == 'yes' else 0
    else:
        return_window_days = 30
        restocking_fee_percent = 10 if order['is_opened'] == 'yes' else 0
    
    # Check eligibility
    is_eligible = days_since_delivery <= return_window_days
    days_remaining = return_window_days - days_since_delivery
    
    # Calculate refund
    price = order['price']
    restocking_fee = price * (restocking_fee_percent / 100)
    estimated_refund = price - restocking_fee
    
    # Generate message
    if is_eligible:
        if days_remaining == 0:
            message = "Order is eligible for return. This is the LAST DAY of the return window - must be returned TODAY."
        elif days_remaining == 1:
            message = "Order is eligible for return. 1 day remaining - must be returned by tomorrow."
        else:
            message = f"Order is eligible for return. {days_remaining} days remaining in the return window."
    else:
        message = f"Order is NOT eligible for return. Return window expired {abs(days_remaining)} days ago."
    
    return {
        "order_id": order_id,
        "is_eligible": is_eligible,
        "days_since_delivery": days_since_delivery,
        "return_window_days": return_window_days,
        "days_remaining": days_remaining,
        "restocking_fee_percent": restocking_fee_percent,
        "restocking_fee_amount": round(restocking_fee, 2),
        "estimated_refund": round(estimated_refund, 2),
        "message": message
    }

def get_server_info():
    """Return server information"""
    return {
        "name": "TechMart Orders Server",
        "version": "1.0.0",
        "description": "MCP server providing order lookup and return eligibility tools",
        "port": 9001,
        "transport": "sse",
        "tools": [
            "get_order",
            "check_return_eligibility"
        ]
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", "9001"))
    logger.info("🚀 Orders MCP Server starting...")
    logger.info(f"📊 Loaded {len(ORDERS)} orders from PostgreSQL database")
    logger.info(f"🌐 Server will run on http://0.0.0.0:{port}")
    logger.info("🔧 Available tools: get_order, check_return_eligibility")
    mcp.run(transport="sse", host="0.0.0.0", port=port)
