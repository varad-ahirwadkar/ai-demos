import asyncio
from mcp.client.sse import sse_client
from mcp import ClientSession


async def test_k8s_mcp():
    """Test the K8s MCP server"""
    print("=" * 60)
    print("Testing K8s MCP Server")
    print("=" * 60)
    print()
    
    async with sse_client("http://localhost:9000/sse") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("✓ Connected to K8s MCP server")
            print()
            
            # List available tools
            tools = await session.list_tools()
            print(f"Available tools: {len(tools.tools)}")
            for tool in tools.tools:
                print(f"  • {tool.name}: {tool.description}")
            print()
            
            # Test 1: List all pods
            print("Test 1: Listing all pods...")
            print("-" * 60)
            result = await session.call_tool("list_pods", {})
            print(result.content[0].text if result.content else "No result")
            print()
            
            # # Test 2: Get crashing pods
            # print("Test 2: Getting crashing pods...")
            # print("-" * 60)
            # result = await session.call_tool("get_crashing_pods", {})
            # print(result.content[0].text if result.content else "No result")
            # print()
            
            # # Test 3: Get pod logs (you'll need to replace 'my-pod' with actual pod name)
            # print("Test 3: Getting pod logs...")
            # print("-" * 60)
            # print("Note: Replace 'my-pod' with an actual pod name from your cluster")
            # # Uncomment and update pod name to test:
            # # result = await session.call_tool("get_pod_logs", {"pod_name": "my-pod"})
            # # print(result.content[0].text if result.content else "No result")
            # print()
            
            print("=" * 60)
            print("✅ Tests completed!")


if __name__ == "__main__":
    asyncio.run(test_k8s_mcp())

# Made with Bob
