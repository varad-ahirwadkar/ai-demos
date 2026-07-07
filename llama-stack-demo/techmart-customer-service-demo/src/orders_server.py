from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
import csv
import json
from datetime import datetime, timedelta
from typing import Any
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Static reference date for demo consistency (April 21, 2024)
# This ensures the demo works regardless of when it's run
DEMO_TODAY = datetime(2024, 4, 21)

# Determine data path (handle both development and container environments)
if os.path.exists('orders.csv'):
    ORDERS_PATH = 'orders.csv'
elif os.path.exists('../data/orders.csv'):
    ORDERS_PATH = '../data/orders.csv'
else:
    ORDERS_PATH = 'data/orders.csv'

# Initialize FastMCP server
mcp = FastMCP(
    "TechMart Orders Server",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
        allowed_hosts=["*"],
        allowed_origins=["*"],
    )
)

def load_orders() -> list[dict[str, Any]]:
    """Load orders from CSV file"""
    orders = []
    try:
        with open(ORDERS_PATH, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                orders.append(row)
        logger.info(f"Loaded {len(orders)} orders from {ORDERS_PATH}")
    except FileNotFoundError:
        logger.error(f"orders.csv not found at {ORDERS_PATH}")
    return orders

# Load orders at startup
ORDERS = load_orders()

@mcp.resource("orders://info")
def get_orders_resource() -> str:
    """Get information about currently loaded orders as an MCP resource"""
    return json.dumps({
        "orders_count": len(ORDERS),
        "orders_file": ORDERS_PATH,
        "demo_date": DEMO_TODAY.strftime('%Y-%m-%d'),
        "sample_orders": [order['order_id'] for order in ORDERS[:5]]
    })

@mcp.tool()
def reload_orders() -> dict[str, Any]:
    """
    Reload orders from the CSV file
    
    Use this after manually updating the orders.csv file to refresh the data
    
    Returns:
        Status message with count of loaded orders
    """
    global ORDERS
    ORDERS = load_orders()
    return {
        "status": "success",
        "message": f"Reloaded {len(ORDERS)} orders from {ORDERS_PATH}",
        "orders_count": len(ORDERS)
    }

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
        message = f"Order is eligible for return. {days_remaining} days remaining in the return window."
    else:
        message = f"Order is not eligible for return. Return window expired {abs(days_remaining)} days ago."
    
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
    # Configure transport security to allow connections from containers
    security_settings = TransportSecuritySettings(
        allowed_hosts=["*"]  # Allow all hosts for container networking
    )
    
    logger.info("🚀 Orders MCP Server starting...")
    logger.info(f"📊 Loaded {len(ORDERS)} orders from {ORDERS_PATH}")
    logger.info("🌐 Server will run on http://0.0.0.0:9001")
    logger.info("🔧 Available tools: get_order, check_return_eligibility")
    
    # Note: Port and host are configured via CLI when running with fastmcp
    # Example: fastmcp run orders_mcp_server.py --transport sse --host 0.0.0.0 --port 9001

# Made with Bob
