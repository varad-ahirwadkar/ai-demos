#!/usr/bin/env python3
"""
Simple MCP Server for Math Operations
Demonstrates MCP integration with Llama Stack
"""

import logging
import sys
import os
from typing import Any
import uvicorn

# Configure allowed hosts for Docker/container connections
# This must be set BEFORE importing FastMCP
# allowed_hosts = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,host.containers.internal,host.docker.internal,*")
os.environ["MCP_ALLOW_ALL_HOSTS"] = "true"
# Configure logging to stderr only (stdout is reserved for JSON-RPC)
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def serve() -> None:
    """
    Start a local MCP server that exposes simple math operation tools.
    This server can be integrated with Llama Stack for enhanced capabilities.
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        print("❌ Missing dependency 'mcp'. Install with: pip install mcp")
        return

    # Initialize MCP server
    mcp = FastMCP("MathOperationsServer")

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
    def subtract(a: int, b: int) -> int:
        """
        Subtract b from a.
        
        Args:
            a: Number to subtract from
            b: Number to subtract
            
        Returns:
            Difference of a and b
        """
        result = a - b
        logger.info(f"Subtraction: {a} - {b} = {result}")
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

    @mcp.tool()
    def divide(a: float, b: float) -> float:
        """
        Divide a by b.
        
        Args:
            a: Dividend
            b: Divisor
            
        Returns:
            Quotient of a and b
            
        Raises:
            ValueError: If b is zero
        """
        if b == 0:
            raise ValueError("Cannot divide by zero")
        result = a / b
        logger.info(f"Division: {a} ÷ {b} = {result}")
        return result

    @mcp.tool()
    def power(base: float, exponent: float) -> float:
        """
        Raise base to the power of exponent.
        
        Args:
            base: Base number
            exponent: Exponent
            
        Returns:
            base raised to the power of exponent
        """
        result = base ** exponent
        logger.info(f"Power: {base}^{exponent} = {result}")
        return result

    @mcp.tool()
    def calculate_percentage(value: float, percentage: float) -> float:
        """
        Calculate percentage of a value.
        
        Args:
            value: The base value
            percentage: Percentage to calculate (e.g., 20 for 20%)
            
        Returns:
            The calculated percentage value
        """
        result = (value * percentage) / 100
        logger.info(f"Percentage: {percentage}% of {value} = {result}")
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

    # Log to stderr (stdout is reserved for JSON-RPC messages)
    logger.info("=" * 60)
    logger.info("🚀 Math Operations MCP Server")
    logger.info("=" * 60)
    logger.info("Server Name: MathOperationsServer")
    logger.info("Transport: SSE (Server-Sent Events)")
    logger.info("Endpoint: http://localhost:8000/sse")
    logger.info("")
    logger.info("Available Tools:")
    logger.info("  • add(a, b) - Add two numbers")
    logger.info("  • subtract(a, b) - Subtract b from a")
    logger.info("  • multiply(a, b) - Multiply two numbers")
    logger.info("  • divide(a, b) - Divide a by b")
    logger.info("  • power(base, exponent) - Raise to power")
    logger.info("  • calculate_percentage(value, percentage) - Calculate percentage")
    logger.info("")
    logger.info("Resources:")
    logger.info("  • info://server - Server information")
    logger.info("=" * 60)
    logger.info("Server is running... Press Ctrl+C to stop")
    logger.info("")

    logger.info("")
    
    mcp.run(transport="sse")
    # app = mcp.app

    # uvicorn.run(app, host="0.0.0.0", port=8080)


if __name__ == "__main__":
    serve()

# Made with Bob
