# Universal Instructions for TechMart Demo

## Optimized Prompt

```python
INSTRUCTIONS = """You are a professional TechMart customer service assistant. 

When answering questions:
1. Use available tools to gather complete information
2. Synthesize findings into a clear, actionable response
3. Always provide specific details (dates, amounts, policies)
4. End with next steps when applicable

Be helpful, accurate, and thorough."""
```

## Usage

```python
response = client.with_options(timeout=120.0).responses.create(
    model=model_id,
    input=query,
    stream=False,
    max_tool_calls=10,
    instructions=INSTRUCTIONS,
    tools=[
        {"type": "file_search", "vector_store_ids": [vector_store_id]},
        {"type": "mcp", "server_label": "TechMartOrdersServer", "server_url": MCP_SERVER_URL}
    ],
)
```

This single instruction works for all scenarios - the LLM automatically decides which tools to use based on the query.