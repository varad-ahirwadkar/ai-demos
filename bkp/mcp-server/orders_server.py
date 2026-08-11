from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
import logging
import sys
import csv
import os
from typing import Any
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

logger.info("=" * 60)
logger.info("🛍️ TechMart Orders MCP Server")
logger.info("=" * 60)
logger.info("Server Name: OrdersServer")
logger.info("Endpoint: http://localhost:9001/sse")
logger.info("")
logger.info("Available Tools:")
logger.info("  • get_order(order_id) - Get order details")
logger.info("  • check_return_eligibility(order_id) - Check if order can be returned")
logger.info("=" * 60)
logger.info("Server is running... Press Ctrl+C to stop")
logger.info("")

mcp = FastMCP(
    "OrdersServer",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
        allowed_hosts=["*"],
        allowed_origins=["*"],
    )
)

# Path to orders CSV file
ORDERS_FILE = os.path.join(os.path.dirname(__file__), "../sample-data/orders.csv")

def load_orders():
    """Load orders from CSV file"""
    orders = {}
    try:
        with open(ORDERS_FILE, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                orders[row['order_id']] = row
        logger.info(f"Loaded {len(orders)} orders from CSV")
    except Exception as e:
        logger.error(f"Error loading orders: {e}")
    return orders

@mcp.tool()
def get_order(order_id: str) -> dict[str, Any]:
    """
    Get order details by order ID.
    
    Args:
        order_id: The order ID (e.g., ORD-2024-001)
        
    Returns:
        Dictionary with order details
    """
    try:
        orders = load_orders()
        
        if order_id not in orders:
            return {"error": f"Order {order_id} not found"}
        
        order = orders[order_id]
        logger.info(f"Retrieved order {order_id}")
        
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
    except Exception as e:
        logger.error(f"Error: {e}")
        return {"error": str(e)}

@mcp.tool()
def check_return_eligibility(order_id: str) -> dict[str, Any]:
    """
    Check if an order is eligible for return based on policy.
    
    Args:
        order_id: The order ID (e.g., ORD-2024-001)
        
    Returns:
        Dictionary with eligibility status and details
    """
    try:
        orders = load_orders()
        
        if order_id not in orders:
            return {"error": f"Order {order_id} not found"}
        
        order = orders[order_id]
        
        # Parse delivery date
        delivery_date = datetime.strptime(order['delivery_date'], '%Y-%m-%d')
        days_since_delivery = (datetime.now() - delivery_date).days
        
        # Determine return window based on category
        if order['category'] == 'Electronics':
            return_window = 15
        else:
            return_window = 30
        
        # Check eligibility
        is_eligible = days_since_delivery <= return_window
        
        # Calculate restocking fee
        restocking_fee = 0
        if order['is_opened'] == 'yes':
            if order['category'] == 'Electronics':
                restocking_fee = 15  # 15% for opened electronics
            else:
                restocking_fee = 10  # 10% for opened standard items
        
        result = {
            "order_id": order['order_id'],
            "product_name": order['product_name'],
            "category": order['category'],
            "delivery_date": order['delivery_date'],
            "days_since_delivery": days_since_delivery,
            "return_window_days": return_window,
            "is_eligible": is_eligible,
            "is_opened": order['is_opened'],
            "restocking_fee_percent": restocking_fee,
            "price": float(order['price']),
            "estimated_refund": float(order['price']) * (1 - restocking_fee/100) if is_eligible else 0
        }
        
        if is_eligible:
            result["message"] = f"Order is eligible for return. {return_window - days_since_delivery} days remaining."
        else:
            result["message"] = f"Order is NOT eligible. Return window ({return_window} days) has expired."
        
        logger.info(f"Checked eligibility for {order_id}: {is_eligible}")
        return result
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return {"error": str(e)}

@mcp.resource("info://server")
def get_server_info() -> dict[str, Any]:
    """Get server information"""
    return {
        "name": "OrdersServer",
        "version": "1.0.0",
        "description": "TechMart orders MCP server for customer service",
        "tools": ["get_order", "check_return_eligibility"],
        "transport": "sse",
        "endpoint": "http://localhost:9001/sse"
    }

# Made with Bob