"""
Test script for TechMart Orders MCP Server
"""

import asyncio
from mcp.client.sse import sse_client
from mcp import ClientSession

MCP_SERVER_URL = "http://localhost:9001/sse"

async def test_mcp_server():
    """Test the MCP server tools"""
    
    print("🧪 Testing TechMart Orders MCP Server")
    print("=" * 50)
    print()
    
    try:
        async with sse_client(MCP_SERVER_URL) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize session
                await session.initialize()
                print("✅ Connected to MCP server")
                print()
                
                # Test 1: Get order details
                print("Test 1: Getting order details for ORD-2024-001...")
                print("-" * 50)
                result = await session.call_tool(
                    "get_order",
                    arguments={"order_id": "ORD-2024-001"}
                )
                
                if result and len(result.content) > 0:
                    print("✅ Success!")
                    print(result.content[0].text)
                else:
                    print("❌ Failed to get order details")
                
                print()
                
                # Test 2: Check return eligibility
                print("Test 2: Checking return eligibility for ORD-2024-001...")
                print("-" * 50)
                result = await session.call_tool(
                    "check_return_eligibility",
                    arguments={"order_id": "ORD-2024-001"}
                )
                
                if result and len(result.content) > 0:
                    print("✅ Success!")
                    print(result.content[0].text)
                else:
                    print("❌ Failed to check eligibility")
                
                print()
                print("=" * 50)
                print("🎉 All tests completed!")
                print()
                print("Example questions to try in the UI:")
                print("  - Can I return order ORD-2024-001?")
                print("  - Show me details for order ORD-2024-005")
                print("  - Is order ORD-2024-007 eligible for return?")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        print()
        print("Make sure the MCP server is running:")
        print("  cd .. && fastmcp run src/orders_mcp_server.py --transport sse --host 0.0.0.0 --port 9001")

if __name__ == "__main__":
    asyncio.run(test_mcp_server())

# Made with Bob
