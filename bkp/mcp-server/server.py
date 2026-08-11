from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
import logging
import sys
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

logger.info("=" * 60)
logger.info("🚀 Math Operations MCP Server")
logger.info("=" * 60)
logger.info("Server Name: MathOperationsServer")
logger.info("Transport: SSE (Server-Sent Events)")
logger.info("Endpoint: http://localhost:8000/sse")
logger.info("")
logger.info("Available Tools:")
logger.info("  • add(a, b) - Add two numbers")
logger.info("  • multiply(a, b) - Multiply two numbers")
logger.info("Resources:")
logger.info("  • info://server - Server information")
logger.info("=" * 60)
logger.info("Server is running... Press Ctrl+C to stop")
logger.info("")

logger.info("")

# mcp = FastMCP("MathOperationsServer")
mcp = FastMCP(
    "MathOperationsServer",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
        # Add your specific gateway or domain here
        allowed_hosts=["*"],
        allowed_origins=["*"],
    )
)

@mcp.tool()
def add(a: int, b: int) -> int:
    """
    Add two numbers together.
    
    Args:
        a: First number
        b: Second number
        
    Returns:
        Sum of a and b
    """
    result = a + b
    logger.info(f"Addition: {a} + {b} = {result}")
    return result

@mcp.tool()
def multiply(a: int, b: int) -> int:
    """
    Multiply two numbers.
    
    Args:
        a: First number
        b: Second number
        
    Returns:
        Product of a and b
    """
    result = a * b
    logger.info(f"Multiplication: {a} × {b} = {result}")
    return result

# Add a resource for server info
@mcp.resource("info://server")
def get_server_info() -> dict[str, Any]:
    """
    Get information about this MCP server.
    
    Returns:
        Server metadata and capabilities
    """
    return {
        "name": "MathOperationsServer",
        "version": "1.0.0",
        "description": "Simple MCP server providing math operation tools",
        "tools": [
            "add", "subtract", "multiply", "divide", 
            "power", "calculate_percentage"
        ],
        "transport": "sse",
        "endpoint": "http://localhost:8000/sse"
    }