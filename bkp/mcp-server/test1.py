# Test script - connects to existing MCP server via SSE
import asyncio
import httpx


async def test_add():
    """Test the MCP server using SSE transport (connects to existing server)"""
    
    print("=" * 60)
    print("Testing Math Operations MCP Server (SSE)")
    print("=" * 60)
    print()
    print("Connecting to: http://localhost:8000/sse")
    print()
    
    try:
        from mcp import ClientSession
        from mcp.client.sse import sse_client
    except ImportError:
        print("❌ Error: MCP client library not installed")
        print("Install with: pip install mcp")
        return
    
    try:
        # Connect to existing server via SSE
        async with sse_client("http://localhost:8000/sse") as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize session
                await session.initialize()
                print("✓ Connected to MCP server")
                print()
                
                # List available tools
                tools_response = await session.list_tools()
                print(f"Available tools: {len(tools_response.tools)}")
                for tool in tools_response.tools:
                    print(f"  • {tool.name}: {tool.description}")
                print()
                
                # Test cases
                test_cases = [
                    ("add", {"a": 10, "b": 10}, "10 + 10"),
                    ("subtract", {"a": 20, "b": 8}, "20 - 8"),
                    ("multiply", {"a": 6, "b": 7}, "6 × 7"),
                    ("divide", {"a": 100, "b": 4}, "100 ÷ 4"),
                    ("power", {"base": 2, "exponent": 8}, "2^8"),
                    ("calculate_percentage", {"value": 200, "percentage": 15}, "15% of 200"),
                ]
                
                print("Running tests:")
                print("-" * 60)
                
                for tool_name, args, description in test_cases:
                    try:
                        result = await session.call_tool(tool_name, args)
                        # Extract the actual result value
                        result_value = result.content[0].text if result.content else "No result"
                        print(f"✓ {description} = {result_value}")
                    except Exception as e:
                        print(f"✗ {description} failed: {e}")
                
                print("-" * 60)
                print()
                print("✅ All tests completed!")
                
    except Exception as e:
        print(f"❌ Error connecting to server: {e}")
        print()
        print("Make sure the server is running:")
        print("  python server.py")
        print()
        print("Or check if it's accessible:")
        print("  curl http://localhost:8000/sse")


if __name__ == "__main__":
    asyncio.run(test_add())

# Made with Bob
