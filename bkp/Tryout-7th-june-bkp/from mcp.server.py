from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
import json
from datetime import datetime
from typing import Any
import os
import logging
import pyodbc

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Static reference date for demo consistency (April 21, 2024)
# This ensures the demo works regardless of when it's run
DEMO_TODAY = datetime(2024, 4, 21)

# IBM i DB2 connection parameters from environment
# IMPORTANT: All credentials MUST be provided via environment variables
DB_SYSTEM = os.getenv('DB_SYSTEM')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_SCHEMA = os.getenv('DB_SCHEMA', 'TECHMART')

# Validate required configuration
if not DB_SYSTEM or not DB_USER or not DB_PASSWORD:
    logger.error("❌ FATAL: Missing required database configuration")
    logger.error("   Required environment variables:")
    logger.error("   - DB_SYSTEM: IBM i system IP or hostname")
    logger.error("   - DB_USER: Database username")
    logger.error("   - DB_PASSWORD: Database password")
    logger.error("   - DB_SCHEMA: Database schema (optional, default: TECHMART)")
    exit(1)

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
    """Get IBM i DB2 connection via ODBC"""
    conn_str = (
        f"DRIVER={{IBM i Access ODBC Driver}};"
        f"SYSTEM={DB_SYSTEM};"
        f"UID={DB_USER};"
        f"PWD={DB_PASSWORD};"
        f"DBQ={DB_SCHEMA};"
    )
    return pyodbc.connect(conn_str)

def load_orders() -> list[dict[str, Any]]:
    """Load orders from IBM i DB2 database"""
    orders = []
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {DB_SCHEMA}.ORDERS ORDER BY ORDER_DATE DESC")
    
    # Get column names
    columns = [column[0] for column in cursor.description]
    
    rows = cursor.fetchall()
    for row in rows:
        # Convert row to dict using column names
        order = {}
        for i, col_name in enumerate(columns):
            value = row[i]
            # Convert dates to strings
            if isinstance(value, datetime):
                order[col_name.lower()] = value.strftime('%Y-%m-%d')
            elif hasattr(value, 'date'):  # Handle date objects
                order[col_name.lower()] = value.strftime('%Y-%m-%d')
            # Convert Decimal to string for price
            elif col_name.upper() == 'PRICE' and value is not None:
                order[col_name.lower()] = str(value)
            # Convert boolean/integer for is_opened
            elif col_name.upper() == 'IS_OPENED':
                order[col_name.lower()] = 'yes' if value else 'no'
            else:
                order[col_name.lower()] = value
        orders.append(order)
    
    cursor.close()
    conn.close()
    logger.info(f"Loaded {len(orders)} orders from IBM i DB2 database")
    return orders

def verify_database_connection():
    """Verify database connection at startup - fail fast if unable to connect"""
    try:
        logger.info("🔍 Verifying database connection...")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {DB_SCHEMA}.ORDERS")
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        logger.info(f"✅ Database connection verified: {count} orders available")
        return True
    except Exception as e:
        logger.error(f"❌ FATAL: Cannot connect to IBM i DB2 database")
        logger.error(f"   System: {DB_SYSTEM}")
        logger.error(f"   Schema: {DB_SCHEMA}")
        logger.error(f"   User: {DB_USER}")
        logger.error(f"   Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

# Verify database connection before starting
if not verify_database_connection():
    logger.error("❌ MCP Server cannot start without database connection")
    logger.error("   Please check:")
    logger.error("   1. IBM i system is accessible")
    logger.error("   2. Database credentials are correct")
    logger.error("   3. IBM i Access ODBC Driver is installed")
    logger.error("   4. Network attributes allow ODBC access (DDMACC, PCSACC)")
    exit(1)

# Load orders at startup
try:
    ORDERS = load_orders()
except Exception as e:
    logger.error(f"❌ FATAL: Failed to load orders from database: {e}")
    import traceback
    logger.error(traceback.format_exc())
    exit(1)

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
        "data_source": "IBM i DB2 Database (via ODBC)",
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
    logger.info(f"🔍 get_order called with order_id: {order_id}")
    
    for order in ORDERS:
        if order['order_id'] == order_id:
            result = {
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
            logger.info(f"✅ Found order: {order_id}")
            logger.info(f"   Product: {result['product_name']}")
            logger.info(f"   Category: {result['category']}")
            logger.info(f"   Price: ${result['price']}")
            logger.info(f"   Delivery: {result['delivery_date']}")
            logger.info(f"   Status: {result['status']}")
            logger.info(f"   Opened: {result['is_opened']}")
            return result
    
    logger.warning(f"❌ Order not found: {order_id}")
    return {"error": f"Order {order_id} not found"}

@mcp.tool()
def list_orders(limit: int = 25) -> dict[str, Any]:
    """
    List all orders with basic information
    
    Args:
        limit: Maximum number of orders to return (default: 25)
    
    Returns:
        List of orders with order_id, customer_email, product_name, status
    """
    orders_list = []
    for order in ORDERS[:limit]:
        orders_list.append({
            "order_id": order['order_id'],
            "customer_email": order['customer_email'],
            "product_name": order['product_name'],
            "category": order['category'],
            "status": order['status'],
            "order_date": order['order_date'],
            "delivery_date": order['delivery_date']
        })
    
    return {
        "orders": orders_list,
        "total_count": len(ORDERS),
        "returned_count": len(orders_list)
    }

@mcp.tool()
def search_orders(customer_email: str | None = None, status: str | None = None, category: str | None = None) -> dict[str, Any]:
    """
    Search orders by customer email, status, or category
    
    Args:
        customer_email: Filter by customer email (optional)
        status: Filter by order status (optional)
        category: Filter by product category (optional)
    
    Returns:
        List of matching orders
    """
    filtered_orders = ORDERS
    
    if customer_email:
        filtered_orders = [o for o in filtered_orders if customer_email.lower() in o['customer_email'].lower()]
    
    if status:
        filtered_orders = [o for o in filtered_orders if status.lower() in o['status'].lower()]
    
    if category:
        filtered_orders = [o for o in filtered_orders if category.lower() in o['category'].lower()]
    
    orders_list = []
    for order in filtered_orders:
        orders_list.append({
            "order_id": order['order_id'],
            "customer_email": order['customer_email'],
            "product_name": order['product_name'],
            "category": order['category'],
            "status": order['status'],
            "order_date": order['order_date'],
            "delivery_date": order['delivery_date'],
            "price": float(order['price']),
            "is_opened": order['is_opened']
        })
    
    return {
        "orders": orders_list,
        "count": len(orders_list)
    }

def get_server_info():
    """Return server information"""
    return {
        "name": "TechMart Orders Server",
        "version": "2.0.0",
        "description": "MCP server providing database operations for orders (retrieval only, no business logic)",
        "port": 9001,
        "transport": "sse",
        "tools": [
            "get_order",
            "list_orders",
            "search_orders",
            "reload_orders"
        ]
    }

if __name__ == "__main__":
    
    logger.info("🚀 Orders MCP Server starting...")
    logger.info(f"📊 Loaded {len(ORDERS)} orders from IBM i DB2 database")
    logger.info(f"🔗 Connected to: {DB_SYSTEM} (Schema: {DB_SCHEMA})")
    logger.info("🌐 Server will run on http://0.0.0.0:9001")
    logger.info("🔧 Available tools: get_order, list_orders, search_orders, reload_orders")
    logger.info("💡 Business logic (return eligibility) handled by AI using RAG policy documents")
    
    # Start the MCP server
    mcp.run(transport="sse")
