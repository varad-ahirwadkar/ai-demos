import asyncio
from mcp.client.sse import sse_client
from mcp import ClientSession


async def test_orders_mcp():
    """Test the Orders MCP server"""
    print("=" * 60)
    print("Testing TechMart Orders MCP Server")
    print("=" * 60)
    print()
    
    async with sse_client("http://localhost:9001/sse") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("✓ Connected to Orders MCP server")
            print()
            
            # List available tools
            tools = await session.list_tools()
            print(f"Available tools: {len(tools.tools)}")
            for tool in tools.tools:
                print(f"  • {tool.name}: {tool.description}")
            print()
            
            # Test 1: Get order details
            print("Test 1: Getting order details for ORD-2024-001...")
            print("-" * 60)
            result = await session.call_tool("get_order", {"order_id": "ORD-2024-001"})
            print(result.content[0].text if result.content else "No result")
            print()
            
            # Test 2: Check return eligibility for recent order
            print("Test 2: Checking return eligibility for ORD-2024-002 (recent order)...")
            print("-" * 60)
            result = await session.call_tool("check_return_eligibility", {"order_id": "ORD-2024-002"})
            print(result.content[0].text if result.content else "No result")
            print()
            
            # Test 3: Check return eligibility for old order
            print("Test 3: Checking return eligibility for ORD-2024-007 (old order)...")
            print("-" * 60)
            result = await session.call_tool("check_return_eligibility", {"order_id": "ORD-2024-007"})
            print(result.content[0].text if result.content else "No result")
            print()
            
            print("=" * 60)
            print("✅ Tests completed!")
            print()
            print("Example Questions for RAG + MCP Integration:")
            print("- 'Can I return order ORD-2024-001?'")
            print("- 'What is the return policy for electronics?'")
            print("- 'I want to return my laptop, order ORD-2024-001'")
            print("- 'How much refund will I get for order ORD-2024-005?'")


if __name__ == "__main__":
    asyncio.run(test_orders_mcp())

# Made with Bob