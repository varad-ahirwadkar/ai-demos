# MCP Server for Math Operations

A simple Model Context Protocol (MCP) server that provides math operation tools for integration with Llama Stack.

## Features

- **6 Math Tools**: add, subtract, multiply, divide, power, calculate_percentage
- **SSE Transport**: Server-Sent Events for real-time communication
- **Configurable Port**: Run on any port via environment variable
- **Resource Endpoint**: Server information available at `info://server`

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the Server

**Default Port (8000):**
```bash
python server.py
```

**Or export the variable:**
```bash
export MCP_SERVER_PORT=8333
python server.py
```

### 3. Test the Server

**Test on default port:**
```bash
python test1.py
```

## Available Tools

### 1. add(a: int, b: int) -> int
Add two numbers together.

**Example:**
```python
result = await session.call_tool("add", {"a": 10, "b": 20})
# Returns: 30
```

### 2. subtract(a: int, b: int) -> int
Subtract b from a.

**Example:**
```python
result = await session.call_tool("subtract", {"a": 50, "b": 20})
# Returns: 30
```

### 3. multiply(a: int, b: int) -> int
Multiply two numbers.

**Example:**
```python
result = await session.call_tool("multiply", {"a": 6, "b": 7})
# Returns: 42
```

### 4. divide(a: float, b: float) -> float
Divide a by b.

**Example:**
```python
result = await session.call_tool("divide", {"a": 100, "b": 4})
# Returns: 25.0
```

### 5. power(base: float, exponent: float) -> float
Raise base to the power of exponent.

**Example:**
```python
result = await session.call_tool("power", {"base": 2, "exponent": 8})
# Returns: 256.0
```

### 6. calculate_percentage(value: float, percentage: float) -> float
Calculate percentage of a value.

**Example:**
```python
result = await session.call_tool("calculate_percentage", {"value": 200, "percentage": 15})
# Returns: 30.0 (15% of 200)
```

## Port Configuration

The server uses the `MCP_SERVER_PORT` environment variable to determine which port to run on.

### Why Port Configuration?

You might need to run the server on a different port if:
- Port 8000 is already in use by another application
- You want to run multiple MCP servers simultaneously
- Your firewall or network configuration requires a specific port

### Setting the Port

**Method 1: Environment Variable (Recommended)**
```bash
export MCP_SERVER_PORT=8333
python server.py
```

**Method 2: Inline**
```bash
MCP_SERVER_PORT=8333 python server.py
```

**Method 3: In Docker/Kubernetes**
```yaml
env:
  - name: MCP_SERVER_PORT
    value: "8333"
```

### Default Behavior

If `MCP_SERVER_PORT` is not set, the server defaults to port 8000.

## Running Multiple Servers

You can run multiple instances on different ports:

**Terminal 1:**
```bash
MCP_SERVER_PORT=8000 python server.py
```

**Terminal 2:**
```bash
MCP_SERVER_PORT=8333 python server.py
```

**Terminal 3:**
```bash
MCP_SERVER_PORT=9000 python server.py
```

## Integration with Llama Stack

### 1. Configure Llama Stack

Add the MCP server to your Llama Stack configuration:

```yaml
providers:
  remote:
    - provider_id: mcp-math
      provider_type: remote::mcp
      config:
        url: http://localhost:8333/sse  # Use your configured port
        method: sse
```

### 2. Use in Llama Stack

```python
from llama_stack_client import LlamaStackClient

client = LlamaStackClient(base_url="http://localhost:5001")

# The math tools are now available through Llama Stack
response = client.agents.create(
    agent_config={
        "model": "Llama3.2-3B-Instruct",
        "instructions": "You are a helpful math assistant",
        "tools": ["mcp-math::add", "mcp-math::multiply"]
    }
)
```

## Testing

### Basic Test
```bash
python test1.py
```

### Test with Custom Port
```bash
MCP_SERVER_PORT=8333 python test1.py
```

### Test Script
```bash
chmod +x test_port.sh
./test_port.sh
```

## Troubleshooting

### Port Already in Use

**Error:**
```
OSError: [Errno 48] Address already in use
```

**Solution:**
```bash
# Use a different port
MCP_SERVER_PORT=8333 python server.py
```

### Cannot Connect to Server

**Check if server is running:**
```bash
curl http://localhost:8333/sse
```

**Check port configuration:**
```bash
echo $MCP_SERVER_PORT
```

### Import Errors

**Error:**
```
ImportError: No module named 'mcp'
```

**Solution:**
```bash
pip install -r requirements.txt
```

## Docker Deployment

### Build Image
```bash
docker build -t mcp-math-server .
```

### Run Container (Default Port)
```bash
docker run -p 8000:8000 mcp-math-server
```

### Run Container (Custom Port)
```bash
docker run -p 8333:8333 -e MCP_SERVER_PORT=8333 mcp-math-server
```

## OpenShift Deployment

The server includes OpenShift deployment manifests in `deployment.yaml`.

### Deploy
```bash
oc apply -f deployment.yaml
```

### Configure Port
Edit the deployment and set the environment variable:
```yaml
env:
  - name: MCP_SERVER_PORT
    value: "8333"
```

## Architecture

```
┌─────────────────┐
│  Llama Stack    │
│   (Port 5001)   │
└────────┬────────┘
         │
         │ MCP Protocol (SSE)
         │
┌────────▼────────┐
│   MCP Server    │
│  (Port 8333)    │  ← Configurable via MCP_SERVER_PORT
│                 │
│  Tools:         │
│  • add          │
│  • subtract     │
│  • multiply     │
│  • divide       │
│  • power        │
│  • percentage   │
└─────────────────┘
```

## API Reference

### Server Endpoint
- **URL**: `http://localhost:{PORT}/sse`
- **Transport**: SSE (Server-Sent Events)
- **Protocol**: MCP (Model Context Protocol)

### Resource Endpoint
- **URI**: `info://server`
- **Returns**: Server metadata and capabilities

## Development

### Adding New Tools

1. Add a new tool function with the `@mcp.tool()` decorator:

```python
@mcp.tool()
def square_root(value: float) -> float:
    """Calculate square root of a value."""
    import math
    result = math.sqrt(value)
    logger.info(f"Square root: √{value} = {result}")
    return result
```

2. Update the server info resource
3. Add test cases to `test1.py`

### Logging

All logs are written to stderr to avoid interfering with JSON-RPC communication on stdout.

```python
logger.info("This goes to stderr")
```

## License

See LICENSE file in the project root.

## Support

For issues and questions:
- Check the troubleshooting section above
- Review the Llama Stack documentation
- Check MCP protocol documentation

---

**Made with Bob** 🤖