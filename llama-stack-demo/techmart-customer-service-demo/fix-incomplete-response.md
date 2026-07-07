# Fix for Incomplete LLM Responses

## Problem
The LLM calls MCP tools successfully but stops with: "To find the restocking fee policy, I'll search for relevant information."

## Root Cause
The LLM is planning to call another tool (`file_search`) but Llama Stack returns control after the MCP tool calls complete. The response shows `status='completed'` even though the answer is incomplete.

## Solutions

### Solution 1: Add `stream=False` and Better Instructions (Recommended)

```python
response = client.with_options(timeout=120.0).responses.create(
    model=model_id,
    input=query,
    stream=False,  # Ensure complete response
    instructions="""You are a helpful TechMart customer service assistant.
    
    IMPORTANT: After using tools, you MUST provide a complete final answer.
    
    Steps:
    1. Use MCP tools to get order details and check eligibility
    2. Use file_search tool to get policy information if needed
    3. Provide a COMPLETE answer with all details including:
       - Order information
       - Eligibility status
       - Restocking fees (if applicable)
       - Estimated refund amount
       - Next steps for the customer
    
    Do not stop after calling tools - always provide the final answer.""",
    tools=[
        {
            "type": "file_search",
            "vector_store_ids": [vector_store_id],
        },
        {
            "type": "mcp",
            "server_label": "TechMartOrdersServer",
            "server_url": MCP_SERVER_URL,
        }
    ],
)
```

### Solution 2: Increase max_tool_calls

```python
response = client.with_options(timeout=120.0).responses.create(
    model=model_id,
    input=query,
    max_tool_calls=10,  # Allow multiple tool calls in one turn
    instructions="...",
    tools=[...],
)
```

### Solution 3: Use Agentic Loop (Most Reliable)

```python
def get_complete_answer(query, max_iterations=5):
    """Keep calling until we get a final text answer"""
    messages = [{"role": "user", "content": query}]
    
    for i in range(max_iterations):
        response = client.with_options(timeout=120.0).responses.create(
            model=model_id,
            input=query if i == 0 else None,
            messages=messages if i > 0 else None,
            instructions="""You are a helpful TechMart customer service assistant.
            Use tools as needed, then provide a complete final answer.""",
            tools=[
                {"type": "file_search", "vector_store_ids": [vector_store_id]},
                {"type": "mcp", "server_label": "TechMartOrdersServer", "server_url": MCP_SERVER_URL}
            ],
        )
        
        # Check if we have a final text answer
        if response.output_text and len(response.output_text) > 50:
            # Got a substantial answer
            return response.output_text
        
        # Add response to messages and continue
        messages.append({"role": "assistant", "content": response.output_text or ""})
        messages.append({"role": "user", "content": "Please provide the complete answer now."})
    
    return response.output_text

# Use it
answer = get_complete_answer("I have order ORD-2024-003. Can I return it?")
print(answer)
```

### Solution 4: Simpler Approach - Separate Tool Calls

```python
# Step 1: Get order info via MCP
order_response = client.responses.create(
    model=model_id,
    input=f"Get details and check return eligibility for order {order_id}",
    tools=[{"type": "mcp", "server_label": "TechMartOrdersServer", "server_url": MCP_SERVER_URL}],
)

# Step 2: Get policy info via RAG
policy_response = client.responses.create(
    model=model_id,
    input="What is the return policy for opened electronics?",
    tools=[{"type": "file_search", "vector_store_ids": [vector_store_id]}],
)

# Step 3: Combine with final synthesis
final_response = client.responses.create(
    model=model_id,
    input=f"""Based on this information, provide a complete answer:

Order Info: {order_response.output_text}
Policy Info: {policy_response.output_text}

Customer Question: {original_question}

Provide a clear, complete answer.""",
)

print(final_response.output_text)
```

## Recommended Fix for Notebook

Update the integrated scenarios (Section 7) with Solution 1:

```python
response = client.with_options(timeout=120.0).responses.create(
    model=model_id,
    input=query,
    stream=False,
    max_tool_calls=10,
    instructions="""You are a helpful TechMart customer service assistant.

CRITICAL: You MUST provide a complete final answer after using tools.

Process:
1. Use MCP tools to get order details and eligibility
2. Use file_search if you need policy information
3. Synthesize ALL information into a COMPLETE answer

Your answer must include:
- Order status and details
- Return eligibility (yes/no)
- Days remaining or expired
- Restocking fees (if any)
- Estimated refund amount
- Clear next steps

Do NOT stop after calling tools. Always provide the final synthesized answer.""",
    tools=[
        {"type": "file_search", "vector_store_ids": [vector_store_id]},
        {"type": "mcp", "server_label": "TechMartOrdersServer", "server_url": MCP_SERVER_URL}
    ],
)
```

## Why This Happens

1. **Tool Calling Pattern**: LLMs often plan tool calls in sequence
2. **Turn Completion**: Llama Stack completes the turn after tool execution
3. **Missing Synthesis Step**: The LLM needs explicit instruction to synthesize results

## Testing

After applying the fix, you should see complete responses like:

```
Based on the order details and our return policy:

Order ORD-2024-003 (Office Chair, Home & Garden category) is ELIGIBLE for return.

Details:
- Delivered: March 29, 2024
- Days since delivery: 23 days
- Return window: 30 days (7 days remaining)
- Item condition: Opened
- Restocking fee: 10% ($25.00)
- Original price: $249.99
- Estimated refund: $224.99

Next Steps:
1. Log into your TechMart account
2. Go to "My Orders"
3. Select order ORD-2024-003
4. Click "Return Item"
5. Print the return label
6. Ship within 5 business days

Your refund will be processed within 5-7 business days after we receive the item.