#!/usr/bin/env python3
"""
Test client for Math Operations MCP Server
Demonstrates how to interact with the MCP server
"""

import asyncio
import json
from typing import Any


async def test_mcp_server():
    """Test the MCP server tools"""
    
    print("=" * 60)
    print("Testing Math Operations MCP Server")
    print("=" * 60)
    print()
    
    # In a real implementation, you would use the MCP client library
    # For demonstration, we'll show the expected interactions
    
    test_cases = [
        {
            "tool": "add",
            "args": {"a": 10, "b": 5},
            "expected": 15,
            "description": "Adding 10 + 5"
        },
        {
            "tool": "subtract",
            "args": {"a": 20, "b": 8},
            "expected": 12,
            "description": "Subtracting 20 - 8"
        },
        {
            "tool": "multiply",
            "args": {"a": 6, "b": 7},
            "expected": 42,
            "description": "Multiplying 6 × 7"
        },
        {
            "tool": "divide",
            "args": {"a": 100, "b": 4},
            "expected": 25.0,
            "description": "Dividing 100 ÷ 4"
        },
        {
            "tool": "power",
            "args": {"base": 2, "exponent": 8},
            "expected": 256,
            "description": "Calculating 2^8"
        },
        {
            "tool": "calculate_percentage",
            "args": {"value": 200, "percentage": 15},
            "expected": 30.0,
            "description": "Calculating 15% of 200"
        }
    ]
    
    print("Test Cases:")
    print("-" * 60)
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n{i}. {test['description']}")
        print(f"   Tool: {test['tool']}")
        print(f"   Arguments: {json.dumps(test['args'])}")
        print(f"   Expected Result: {test['expected']}")
        
        # Simulate the call
        print(f"   ✓ Test passed (simulated)")
    
    print("\n" + "=" * 60)
    print("Integration with Llama Stack Example:")
    print("=" * 60)
    print()
    
    example_code = '''
from llama_stack_client import LlamaStackClient

# Initialize client
client = LlamaStackClient(base_url="http://llama-stack:8321")

# Use MCP tool directly
result = client.tools.invoke(
    tool_name="math-operations/add",
    arguments={"a": 10, "b": 5}
)
print(f"Result: {result}")  # Output: 15

# Use in AI conversation
response = client.inference.chat_completion(
    model_id="llama-32-3b-instruct",
    messages=[{
        "role": "user",
        "content": "Calculate 25% of 80 using the percentage tool"
    }],
    tools=["math-operations/calculate_percentage"]
)
print(response.completion_message.content)
'''
    
    print(example_code)
    
    print("\n" + "=" * 60)
    print("Real-World Use Case Example:")
    print("=" * 60)
    print()
    
    use_case = '''
User Query: "I have $5000 to invest. If I split it 60/40 between 
stocks and bonds, and stocks return 8% while bonds return 3%, 
what's my total return?"

AI Agent Process:
1. calculate_percentage(5000, 60) → $3000 in stocks
2. calculate_percentage(5000, 40) → $2000 in bonds
3. calculate_percentage(3000, 8) → $240 stock returns
4. calculate_percentage(2000, 3) → $60 bond returns
5. add(240, 60) → $300 total returns
6. calculate_percentage(5000, 6) → 6% overall return

AI Response: "With a 60/40 split, your $5000 investment would 
generate $300 in returns (6% overall). Stocks would contribute 
$240 and bonds $60."
'''
    
    print(use_case)
    
    print("\n" + "=" * 60)
    print("To run the actual server:")
    print("  python server.py")
    print()
    print("To deploy to OpenShift:")
    print("  oc apply -f deployment.yaml")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_mcp_server())

# Made with Bob
